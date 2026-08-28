"""类型化日志聚合：预检敏感字段后执行一次受控 Doris 批量查询。"""

import re
import time
from typing import Dict, Set

from django.db.models import Q
from django.utils import timezone
from pydantic import ValidationError as PydanticValidationError

from api.bk_base.constants import StorageType
from apps.meta.constants import SensitiveUserData
from apps.meta.models import SensitiveObject
from apps.permission.handlers.service import PermissionService
from services.web.query.ai_assistant.exceptions import (
    SensitiveFieldPermissionDenied,
    UnsupportedAggregation,
)
from services.web.query.ai_assistant.log_tools.context import LogQueryContextService
from services.web.query.ai_assistant.log_tools.errors import map_log_query_error
from services.web.query.ai_assistant.log_tools.query_sync import safe_query_sync
from services.web.query.ai_assistant.log_tools.schemas import (
    AGGREGATION_STANDARD_FIELD_TYPES,
    AggregateLogsRequest,
    AggregateLogsResponse,
    AggregationColumn,
    AggregationColumnRole,
    AggregationDataQuality,
    AggregationMetricType,
    AggregationQuerySummary,
)
from services.web.query.ai_assistant.log_tools.sql import LogAggregationSQLBuilder


class LogAggregationService:
    """执行受控聚合；分组结果不能逐行脱敏，因此敏感字段一律查询前拒绝。"""

    @classmethod
    def aggregate(cls, *, username: str, namespace: str, request: AggregateLogsRequest) -> AggregateLogsResponse:
        """以当前用户和单系统 Context 执行限量聚合，不记录 SQL、条件或原始行。"""

        try:
            request = AggregateLogsRequest.model_validate(request.model_dump())
        except PydanticValidationError as err:
            raise UnsupportedAggregation() from err

        try:
            context = LogQueryContextService.build(username=username, namespace=namespace, condition=request.condition)
            cls._ensure_fields_aggregatable(
                username=username,
                system_id=request.condition.scope_id,
                fields=cls._requested_field_paths(request),
            )
            builder = LogAggregationSQLBuilder.from_request(context, request)
            responses, took_ms = cls._query(builder)
            rows = cls._response_rows(responses[0], request)
            quality = cls._response_quality(responses[1] if len(responses) > 1 else None, request)
            response = AggregateLogsResponse(
                columns=cls._columns(request, builder),
                rows=tuple(rows[: request.limit]),
                query_summary=AggregationQuerySummary(
                    returned_count=min(len(rows), request.limit),
                    has_more=len(rows) > request.limit,
                    took_ms=took_ms,
                    executed_at="",
                ),
                data_quality=quality,
            )
            response.query_summary.executed_at = timezone.now().isoformat()
            return response
        except Exception as err:  # noqa: BLE001
            mapped_error = map_log_query_error(err)
            if mapped_error is err:
                raise
            raise mapped_error from err

    @classmethod
    def _ensure_fields_aggregatable(cls, *, username: str, system_id: str, fields: Set[str]) -> None:
        """拒绝目标系统和全局用户数据中任何可能命中的未授权敏感字段。"""

        if not fields:
            return
        sensitive_objects = list(
            SensitiveObject._objects.filter(is_deleted=False).filter(
                Q(system_id=system_id)
                | Q(system_id=SensitiveUserData.SYSTEM_ID, resource_id=SensitiveUserData.RESOURCE_ID)
            )
        )
        matched = [
            sensitive_object
            for sensitive_object in sensitive_objects
            if cls._sensitive_field_names(sensitive_object).intersection(fields)
        ]
        if any(item.is_private for item in matched):
            raise SensitiveFieldPermissionDenied()
        if not matched:
            return
        permissions = PermissionService(username=username).get_sensitive_object_permissions(
            [item.id for item in matched]
        )
        if any(not permissions.get(str(item.id), False) for item in matched):
            raise SensitiveFieldPermissionDenied()

    @staticmethod
    def _sensitive_field_names(sensitive_object: SensitiveObject) -> Set[str]:
        return {
            item["field_name"]
            for item in sensitive_object.fields
            if isinstance(item, dict) and isinstance(item.get("field_name"), str)
        }

    @staticmethod
    def _requested_field_paths(request: AggregateLogsRequest) -> Set[str]:
        fields = [item.field for item in request.dimensions]
        fields.extend(item.field for item in request.metrics if item.type != AggregationMetricType.COUNT)
        return {".".join((field.raw_name, *field.keys)) for field in fields if field is not None}

    @staticmethod
    def _query(builder: LogAggregationSQLBuilder) -> tuple[tuple[dict, ...], int]:
        requests = [{"sql": builder.build_data_sql(), "prefer_storage": StorageType.DORIS.value}]
        if any(metric.needs_conversion for metric in builder.request.metrics):
            requests.append({"sql": builder.build_quality_sql(), "prefer_storage": StorageType.DORIS.value})
        started_at = time.perf_counter()
        responses = safe_query_sync.bulk_request(requests)
        took_ms = int((time.perf_counter() - started_at) * 1000)
        if not isinstance(responses, (tuple, list)) or len(responses) != len(requests):
            raise ValueError("invalid aggregation bulk response")
        if not all(isinstance(response, dict) for response in responses):
            raise ValueError("invalid aggregation bulk response")
        return tuple(responses), took_ms

    @staticmethod
    def _response_rows(response: dict, request: AggregateLogsRequest) -> list[Dict]:
        if not isinstance(response, dict) or "list" not in response:
            raise ValueError("invalid aggregation data response")
        rows = response["list"]
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise ValueError("invalid aggregation rows")
        allowed_ids = {item.id for item in (*request.dimensions, *request.metrics)}
        if any(not allowed_ids.issubset(row) for row in rows):
            raise ValueError("aggregation row misses declared columns")
        return [{key: value for key, value in row.items() if key in allowed_ids} for row in rows]

    @classmethod
    def _response_quality(
        cls, response: dict | None, request: AggregateLogsRequest
    ) -> tuple[AggregationDataQuality, ...]:
        conversion_metrics = [metric for metric in request.metrics if metric.needs_conversion]
        if not conversion_metrics:
            return ()
        if not isinstance(response, dict):
            raise ValueError("missing aggregation quality response")
        rows = response.get("list")
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise ValueError("invalid aggregation quality response")
        row = rows[0]
        quality = []
        for metric in conversion_metrics:
            required_columns = {
                f"{metric.id}_non_empty_count",
                f"{metric.id}_converted_count",
                f"{metric.id}_conversion_failed_count",
            }
            if not required_columns.issubset(row):
                raise ValueError("aggregation quality misses declared columns")
            item = AggregationDataQuality(
                metric_id=metric.id,
                non_empty_count=cls._count(row[f"{metric.id}_non_empty_count"]),
                converted_count=cls._count(row[f"{metric.id}_converted_count"]),
                conversion_failed_count=cls._count(row[f"{metric.id}_conversion_failed_count"]),
            )
            if item.converted_count + item.conversion_failed_count != item.non_empty_count:
                raise ValueError("inconsistent aggregation quality counts")
            quality.append(item)
        return tuple(quality)

    @staticmethod
    def _count(value) -> int:
        if isinstance(value, bool):
            raise ValueError("invalid aggregation quality count")
        if isinstance(value, int) and value >= 0:
            return value
        if isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
            return int(value)
        raise ValueError("invalid aggregation quality count")

    @staticmethod
    def _columns(request: AggregateLogsRequest, builder: LogAggregationSQLBuilder) -> tuple[AggregationColumn, ...]:
        dimensions = tuple(
            AggregationColumn(
                id=item.id,
                name=item.id,
                role=AggregationColumnRole.DIMENSION,
                data_type=LogAggregationService._dimension_data_type(item, builder),
                effective_time_interval=builder.effective_time_intervals.get(item.id),
            )
            for item in request.dimensions
        )
        metrics = tuple(
            AggregationColumn(
                id=item.id,
                name=item.id,
                role=AggregationColumnRole.METRIC,
                data_type=LogAggregationService._metric_data_type(item),
            )
            for item in request.metrics
        )
        return dimensions + metrics

    @staticmethod
    def _dimension_data_type(dimension, builder: LogAggregationSQLBuilder) -> str:
        if dimension.id in builder.effective_time_intervals:
            return "datetime"
        if dimension.field.keys:
            return "string"
        return AGGREGATION_STANDARD_FIELD_TYPES[dimension.field.raw_name]

    @staticmethod
    def _metric_data_type(metric) -> str:
        if metric.type in {AggregationMetricType.COUNT, AggregationMetricType.DISTINCT_COUNT}:
            return "long"
        if metric.type in {AggregationMetricType.AVG, AggregationMetricType.PERCENTILE_APPROX}:
            return "double"
        if metric.needs_conversion:
            return metric.value_type.value.lower()
        field_type = AGGREGATION_STANDARD_FIELD_TYPES[metric.field.raw_name]
        if metric.type == AggregationMetricType.SUM:
            return "double" if field_type in {"float", "double"} else "long"
        return field_type
