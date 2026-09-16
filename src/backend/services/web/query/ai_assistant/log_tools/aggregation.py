"""完整日志聚合执行：重新授权、单语句查询及严格结果校验。

分组不能事后脱敏；维度、指标和过滤路径必须在 Doris 执行前统一授权。
SQL 内完成全范围计算，应用只接收有界结果，不截断、不拼接独立查询摘要。
"""
import time

from bk_resource import api
from django.conf import settings
from django.utils import timezone
from pydantic import ValidationError as PydanticValidationError

from api.bk_base.constants import StorageType
from services.web.query.ai_assistant.exceptions import (
    StatisticsResponseTooLarge,
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
    AggregationMetricType,
    AggregationQuerySummary,
    AggregationResultDataType,
)
from services.web.query.ai_assistant.log_tools.sensitive import (
    SensitiveLogFieldPermissionService,
)
from services.web.query.ai_assistant.log_tools.statistics_result import (
    StatisticsResultParser,
)
from services.web.query.ai_assistant.log_tools.statistics_sql import (
    StatisticsSQLBuilder,
)


class LogAggregationService:
    """执行无时间的完整聚合；Task4 在相同查询/解析边界扩展完整时轴和预算规划。"""

    @classmethod
    def aggregate(cls, *, username: str, namespace: str, request: AggregateLogsRequest) -> AggregateLogsResponse:
        """校验并执行聚合，系统权限异常保留平台协议，查询错误统一安全映射。"""
        try:
            request = AggregateLogsRequest.model_validate(request.model_dump())
        except PydanticValidationError as err:
            raise UnsupportedAggregation() from err
        context = LogQueryContextService.build(username=username, namespace=namespace, condition=request.condition)
        try:
            fields = [item.field for item in (*request.dimensions, *request.metrics)]
            fields.extend(item.field for item in context.condition.conditions)
            SensitiveLogFieldPermissionService.ensure_access(
                username=username,
                system_id=context.condition.scope_id,
                fields=SensitiveLogFieldPermissionService.collect_field_paths(fields),
            )
            builder = StatisticsSQLBuilder.from_request(context, request)
            raw, took_ms = cls._query(builder)
            result = StatisticsResultParser(request).parse(raw)
            response = AggregateLogsResponse(
                columns=cls._columns(request),
                rows=result.rows,
                groups=result.groups,
                data_quality=result.quality,
                query_summary=AggregationQuerySummary(
                    returned_count=len(result.rows),
                    total_count=result.total_count,
                    top_n=request.top_n,
                    has_other=any(g.kind == "OTHER" for g in result.groups),
                    scope_id=context.condition.scope_id,
                    start_time=context.condition.start_time,
                    end_time=context.condition.end_time,
                    requested_interval=None,
                    effective_interval=None,
                    timezone=settings.TIME_ZONE,
                    complete=True,
                    took_ms=took_ms,
                    executed_at=timezone.now().isoformat(),
                ),
            )
            cls._ensure_response_within_budget(response)
            return response
        except Exception as err:  # noqa: BLE001
            mapped = map_log_query_error(err)
            if mapped is err:
                raise
            raise mapped from err

    @staticmethod
    def _query(builder):
        """仅提交一个最终逻辑 SQL；bulk 保留既有 BKBase 执行链及超时映射。"""
        requests = [{"sql": builder.build_complete_sql(), "prefer_storage": StorageType.DORIS.value}]
        started = time.perf_counter()
        responses = api.bk_base.safe_query_sync.bulk_request(requests)
        took_ms = int((time.perf_counter() - started) * 1000)
        if not isinstance(responses, (tuple, list)) or len(responses) != 1 or not isinstance(responses[0], dict):
            raise ValueError("invalid statistics query response")
        return responses[0], took_ms

    @staticmethod
    def _ensure_response_within_budget(response):
        """按完整业务 JSON 的 UTF-8 字节检查，超限不能删行返回部分成功。"""
        limit = min(AGGREGATION_RESPONSE_MAX_BYTES, max(0, settings.AI_LOG_AGGREGATION_RESPONSE_MAX_BYTES))
        if len(response.model_dump_json().encode("utf-8")) > limit:
            raise StatisticsResponseTooLarge()

    @classmethod
    def _columns(cls, request):
        """维度声明由服务端元信息给出；JSON 使用 scalar，类型见每个 group value。"""
        dimensions = tuple(
            AggregationColumn(
                id=d.id,
                name=d.id,
                role=AggregationColumnRole.DIMENSION,
                data_type=AggregationResultDataType.SCALAR
                if d.field.keys
                else AggregationResultDataType(AGGREGATION_STANDARD_FIELD_TYPES[d.field.raw_name]),
            )
            for d in request.dimensions
        )
        metrics = tuple(
            AggregationColumn(id=m.id, name=m.id, role=AggregationColumnRole.METRIC, data_type=cls._metric_data_type(m))
            for m in request.metrics
        )
        return dimensions + metrics

    @staticmethod
    def _metric_data_type(metric):
        """描述指标值域，不信任客户端 field_type。"""
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
                if field_type in {"float", "double"}
                else AggregationResultDataType.LONG
            )
        return AggregationResultDataType(field_type)
