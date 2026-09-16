"""程序单字段统计固定包的领域服务。

复用聚合上下文、授权、同快照 SQL、严格解析及预算，不调用 HTTP 或样本类型推断。
仅组织 count 分布和完整时间序列，数值摘要来自同一最终查询。
"""
from django.utils import timezone
from pydantic import ValidationError

from apps.meta.utils.fields import STANDARD_FIELDS, START_TIME
from services.web.query.ai_assistant.exceptions import UnsupportedAggregation
from services.web.query.ai_assistant.log_tools.aggregation import (
    LogAggregationService,
    LogQueryContextService,
)
from services.web.query.ai_assistant.log_tools.errors import map_log_query_error
from services.web.query.ai_assistant.log_tools.field_statistics_schemas import (
    FieldCountSeries,
    FieldDistribution,
    FieldDistributionGroup,
    FieldStatisticsOverview,
    FieldStatisticsResult,
    FieldTimeSeries,
    StatisticsField,
)
from services.web.query.ai_assistant.log_tools.schemas import (
    AgentSearchCondition,
    AggregateLogsRequest,
    AggregationQuerySummary,
    AggregationTimeInterval,
    LogFieldRef,
)
from services.web.query.ai_assistant.log_tools.statistics_sql import (
    StatisticsSQLBuilder,
)


class FieldStatisticsService:
    """单字段完整统计；输出不依赖调用方类型提示和预检观察。"""

    @classmethod
    def analyze(
        cls,
        *,
        username: str,
        namespace: str,
        condition: AgentSearchCondition,
        field: LogFieldRef,
        top_n: int = 100,
        interval: AggregationTimeInterval = AggregationTimeInterval.AUTO
    ) -> FieldStatisticsResult:
        """重验权限并生成固定包；非法请求、查询不完整及超预算抛领域异常。"""
        try:
            field = LogFieldRef.model_validate(field.model_dump())
            request = AggregateLogsRequest(
                condition=condition,
                dimensions=[
                    dict(id="value", type="FIELD", field=field),
                    dict(id="bucket", type="TIME_BUCKET", field=LogFieldRef(raw_name="start_time"), interval=interval),
                ],
                metrics=[dict(id="events", type="COUNT")],
                top_n=top_n,
            )
        except ValidationError as err:
            raise UnsupportedAggregation() from err
        context = LogQueryContextService.build(username=username, namespace=namespace, condition=request.condition)
        try:
            builder = StatisticsSQLBuilder.from_request(context, request, summary_field=field)
            result, axis, took_ms = LogAggregationService._execute(builder, numeric_columns=1)
            summary = result.field_summary
            groups = tuple(
                FieldDistributionGroup(
                    group_id=g.group_id,
                    kind=g.kind,
                    value_type=g.values[0].value_type if g.values else None,
                    value=g.values[0].value if g.values else None,
                    count=g.count,
                    ratio=g.ratio,
                )
                for g in result.groups
            )
            counts = {g.group_id: [] for g in groups}
            for row in result.rows:
                counts[row["group_id"]].append(row["events"])
            has_other = any(g.kind == "OTHER" for g in groups)
            response = FieldStatisticsResult(
                field=cls._field(field),
                statistics_kind=summary.kind,
                overview=FieldStatisticsOverview(
                    total_count=result.total_count,
                    present_count=summary.present_count,
                    missing_count=result.total_count - summary.present_count,
                    present_ratio=summary.present_count / result.total_count if result.total_count else None,
                ),
                distribution=FieldDistribution(top_n=request.top_n, has_other=has_other, groups=groups),
                time_series=FieldTimeSeries(
                    requested_interval=axis.requested_interval,
                    effective_interval=axis.effective_interval,
                    timezone=axis.timezone,
                    bucket_starts=axis.bucket_starts,
                    series=tuple(
                        FieldCountSeries(group_id=g.group_id, counts=tuple(counts[g.group_id])) for g in groups
                    ),
                ),
                numeric_summary=summary.numeric_summary,
                query_summary=AggregationQuerySummary(
                    returned_count=len(result.rows),
                    total_count=result.total_count,
                    top_n=request.top_n,
                    has_other=has_other,
                    scope_id=context.condition.scope_id,
                    start_time=context.condition.start_time,
                    end_time=context.condition.end_time,
                    requested_interval=axis.requested_interval,
                    effective_interval=axis.effective_interval,
                    timezone=axis.timezone,
                    complete=True,
                    took_ms=took_ms,
                    executed_at=timezone.now().isoformat(),
                ),
            )
            LogAggregationService._ensure_response_within_budget(response)
            return response
        except Exception as err:  # noqa: BLE001
            mapped = map_log_query_error(err)
            if mapped is err:
                raise
            raise mapped from err

    @staticmethod
    def _field(field):
        """根字段显示名复用服务端定义，JSON 子路径沿目录规则使用末段原文。"""
        if field.keys:
            display_name = field.keys[-1]
        else:
            definitions = {item.field_name: item for item in (*STANDARD_FIELDS, START_TIME)}
            definition = definitions.get(field.raw_name)
            display_name = (
                str(definition.description or definition.alias_name or definition.field_name)
                if definition
                else field.raw_name
            )
        return StatisticsField(raw_name=field.raw_name, keys=tuple(field.keys), display_name=display_name)
