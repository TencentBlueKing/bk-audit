"""类型化日志聚合：预检敏感字段后执行一次受控 Doris 批量查询。"""

import re
import time
from typing import Dict

from bk_resource import api
from django.conf import settings
from django.utils import timezone
from pydantic import ValidationError as PydanticValidationError

from api.bk_base.constants import StorageType
from services.web.query.ai_assistant.exceptions import (
    LogQueryResponseTooLarge,
    UnsupportedAggregation,
)
from services.web.query.ai_assistant.log_tools.context import LogQueryContextService
from services.web.query.ai_assistant.log_tools.errors import map_log_query_error
from services.web.query.ai_assistant.log_tools.schemas import (
    AGGREGATION_RESPONSE_MAX_BYTES,
    AGGREGATION_STANDARD_FIELD_TYPES,
    AggregateLogsRequest,
    AggregateLogsResponse,
    AggregationColumn,
    AggregationColumnRole,
    AggregationDataQuality,
    AggregationMetricType,
    AggregationQuerySummary,
    AggregationResultDataType,
)
from services.web.query.ai_assistant.log_tools.sensitive import (
    SensitiveLogFieldPermissionService,
)
from services.web.query.ai_assistant.log_tools.sql import LogAggregationSQLBuilder


class LogAggregationService:
    """执行受控聚合；分组结果不能逐行脱敏，因此敏感字段一律查询前拒绝。"""

    @classmethod
    def aggregate(cls, *, username: str, namespace: str, request: AggregateLogsRequest) -> AggregateLogsResponse:
        """执行限量聚合。SQL 由公共查询 Resource 按排障策略记录，业务层不额外记录原始行。"""

        try:
            request = AggregateLogsRequest.model_validate(request.model_dump())
        except PydanticValidationError as err:
            raise UnsupportedAggregation() from err

        # 系统无权属于平台权限协议，必须保留原 403、权限信息和申请地址；
        # 仅 Doris 执行及其响应解析进入日志工具异常映射。
        context = LogQueryContextService.build(username=username, namespace=namespace, condition=request.condition)
        try:
            field_refs = [item.field for item in request.dimensions]
            field_refs.extend(item.field for item in request.metrics)
            field_refs.extend(item.field for item in context.condition.conditions)
            SensitiveLogFieldPermissionService.ensure_access(
                username=username,
                system_id=request.condition.scope_id,
                fields=SensitiveLogFieldPermissionService.collect_field_paths(field_refs),
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
            cls._ensure_response_within_budget(response)
            return response
        except Exception as err:  # noqa: BLE001
            mapped_error = map_log_query_error(err)
            if mapped_error is err:
                raise
            raise mapped_error from err

    @staticmethod
    def _ensure_response_within_budget(response: AggregateLogsResponse) -> None:
        """聚合业务 data 按 UTF-8 JSON 计费，超限不返回原始维度值。"""

        response_limit = min(
            AGGREGATION_RESPONSE_MAX_BYTES,
            max(0, settings.AI_LOG_AGGREGATION_RESPONSE_MAX_BYTES),
        )
        if len(response.model_dump_json().encode("utf-8")) > response_limit:
            raise LogQueryResponseTooLarge()

    @staticmethod
    def _query(builder: LogAggregationSQLBuilder) -> tuple[tuple[dict, ...], int]:
        requests = [{"sql": builder.build_data_sql(), "prefer_storage": StorageType.DORIS.value}]
        if any(metric.needs_conversion for metric in builder.request.metrics):
            requests.append({"sql": builder.build_quality_sql(), "prefer_storage": StorageType.DORIS.value})
        started_at = time.perf_counter()
        responses = api.bk_base.safe_query_sync.bulk_request(requests)
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
    def _dimension_data_type(dimension, builder: LogAggregationSQLBuilder) -> AggregationResultDataType:
        if dimension.id in builder.effective_time_intervals:
            return AggregationResultDataType.DATETIME
        if dimension.field.keys:
            return AggregationResultDataType.STRING
        return AggregationResultDataType(AGGREGATION_STANDARD_FIELD_TYPES[dimension.field.raw_name])

    @staticmethod
    def _metric_data_type(metric) -> AggregationResultDataType:
        if metric.type in {AggregationMetricType.COUNT, AggregationMetricType.DISTINCT_COUNT}:
            return AggregationResultDataType.LONG
        if metric.type in {AggregationMetricType.AVG, AggregationMetricType.PERCENTILE_APPROX}:
            return AggregationResultDataType.DOUBLE
        if metric.needs_conversion:
            return AggregationResultDataType(metric.value_type.value.lower())
        field_type = AGGREGATION_STANDARD_FIELD_TYPES[metric.field.raw_name]
        if metric.type == AggregationMetricType.SUM:
            return (
                AggregationResultDataType.DOUBLE
                if field_type in {AggregationResultDataType.FLOAT, AggregationResultDataType.DOUBLE}
                else AggregationResultDataType.LONG
            )
        return AggregationResultDataType(field_type)
