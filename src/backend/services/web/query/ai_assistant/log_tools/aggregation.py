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
    StatisticsBudgetExceeded,
    StatisticsResponseTooLarge,
    UnsupportedAggregation,
    UnsupportedFieldType,
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
    AggregationDimensionType,
    AggregationMetricType,
    AggregationQuerySummary,
    AggregationResultDataType,
)
from services.web.query.ai_assistant.log_tools.sensitive import (
    SensitiveLogFieldPermissionService,
)
from services.web.query.ai_assistant.log_tools.statistics_budget import build_time_axis
from services.web.query.ai_assistant.log_tools.statistics_result import (
    StatisticsResultParser,
    UnsupportedStatisticsNumber,
    statistics_count,
)
from services.web.query.ai_assistant.log_tools.statistics_sql import (
    StatisticsSQLBuilder,
)


class LogAggregationService:
    """统一执行全范围分组和时序，成功结果通过完整性及多维预算校验。"""

    @classmethod
    def aggregate(cls, *, username: str, namespace: str, request: AggregateLogsRequest) -> AggregateLogsResponse:
        """校验并执行聚合，系统权限异常保留平台协议，查询错误统一安全映射。"""
        try:
            request = AggregateLogsRequest.model_validate(request.model_dump())
        except PydanticValidationError as err:
            raise UnsupportedAggregation() from err
        context = LogQueryContextService.build(username=username, namespace=namespace, condition=request.condition)
        try:
            builder = StatisticsSQLBuilder.from_request(context, request)
            result, axis, took_ms = cls._execute(builder, numeric_columns=len(request.metrics) + 2)
            response = AggregateLogsResponse(
                columns=cls._columns(request, axis),
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
                    requested_interval=axis.requested_interval,
                    effective_interval=axis.effective_interval,
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

    @classmethod
    def _execute(cls, builder, *, numeric_columns):
        """可信后端指定预算列数；预检只规划，AUTO 超限丢弃快照并完整重查。"""
        request = builder.request
        # 时间维度不进入 SQL 类别字段集，但其可见值同样必须授权。
        fields = [item.field for item in (*request.dimensions, *request.metrics)]
        fields.append(builder.summary_field)
        fields.extend(item.field for item in builder.context.condition.conditions)
        SensitiveLogFieldPermissionService.ensure_access(
            username=builder.context.username,
            system_id=builder.context.condition.scope_id,
            fields=SensitiveLogFieldPermissionService.collect_field_paths(fields),
        )
        time_dimension = next((d for d in request.dimensions if d.type == AggregationDimensionType.TIME_BUCKET), None)
        builder.numeric_columns = numeric_columns
        took_ms = 0
        group_count = 0
        if time_dimension:
            raw, elapsed = cls._query(builder, preflight=True)
            took_ms += elapsed
            if not isinstance(raw.get("list"), list) or len(raw["list"]) != 1:
                raise ValueError("invalid statistics preflight")
            preflight = raw["list"][0]
            if statistics_count(preflight.get("invalid_type_count")):
                raise UnsupportedFieldType()
            if statistics_count(preflight.get("invalid_number_count")):
                raise UnsupportedStatisticsNumber()
            group_count = statistics_count(preflight.get("group_count"))
            if group_count > (request.top_n + 2 if builder.dimensions else 1):
                raise ValueError("unbounded statistics preflight")
        axis = build_time_axis(
            start_time=builder.context.condition.start_time,
            end_time=builder.context.condition.end_time,
            interval=time_dimension.interval if time_dimension else None,
            group_count=group_count,
            numeric_columns=numeric_columns,
        )
        while True:
            builder.time_axis = axis if time_dimension else None
            raw, elapsed = cls._query(builder)
            took_ms += elapsed
            try:
                result = StatisticsResultParser(
                    request, builder.time_axis, numeric_columns, builder.summary_field
                ).parse(raw)
                return result, axis, took_ms
            except StatisticsBudgetExceeded as err:
                suggestion = err.data["suggested_interval"]
                if not time_dimension or time_dimension.interval != "AUTO" or suggestion is None:
                    raise
                retry_axis = build_time_axis(
                    start_time=builder.context.condition.start_time,
                    end_time=builder.context.condition.end_time,
                    interval=suggestion,
                    group_count=err.actual_group_count,
                    numeric_columns=numeric_columns,
                )
                axis = type(axis)(
                    axis.requested_interval,
                    retry_axis.effective_interval,
                    retry_axis.timezone,
                    retry_axis.bucket_starts,
                )

    @staticmethod
    def _query(builder, preflight=False):
        """仅提交一个最终逻辑 SQL；bulk 保留既有 BKBase 执行链及超时映射。"""
        requests = [
            {
                "sql": builder.build_preflight_sql() if preflight else builder.build_complete_sql(),
                "prefer_storage": StorageType.DORIS.value,
            }
        ]
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
    def _columns(cls, request, axis=None):
        """维度声明由服务端元信息给出；JSON 使用 scalar，类型见每个 group value。"""
        dimensions = tuple(
            AggregationColumn(
                id=d.id,
                name=d.id,
                role=AggregationColumnRole.DIMENSION,
                data_type=AggregationResultDataType.TIMESTAMP
                if d.type == AggregationDimensionType.TIME_BUCKET
                else AggregationResultDataType.SCALAR
                if d.field.keys
                else AggregationResultDataType(AGGREGATION_STANDARD_FIELD_TYPES[d.field.raw_name]),
                effective_time_interval=axis.effective_interval
                if axis and d.type == AggregationDimensionType.TIME_BUCKET
                else None,
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
