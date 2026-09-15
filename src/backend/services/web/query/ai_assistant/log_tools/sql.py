"""基于已验证字段引用的日志投影与聚合 SQL 构建器。"""

from datetime import timedelta
from typing import Dict, Sequence

from pypika.enums import Order
from pypika.functions import Avg, Cast, Count, Max, Min, Sum
from pypika.terms import Case, Criterion, Term

from core.sql.builder.functions import DateTrunc, FromUnixTime, PercentileApprox
from core.sql.builder.terms import PypikaField
from core.utils.time import parse_datetime
from services.web.query.ai_assistant.log_tools.context import LogQueryContext
from services.web.query.ai_assistant.log_tools.schemas import (
    AggregateLogsRequest,
    AggregationDimensionType,
    AggregationMetric,
    AggregationMetricType,
    AggregationTimeInterval,
    AggregationValueType,
    LogFieldRef,
)
from services.web.query.constants import TIMESTAMP_PARTITION_FIELD
from services.web.query.utils.doris import BaseDorisSQLBuilder

# LONG 限制为 18 位，避免文本值进入 Doris LARGEINT 时产生溢出或方言差异。
LONG_LITERAL_REGEXP = r"^-?[0-9]{1,18}$"
# DOUBLE 只接受有限十进制；不开放指数、无限长度或末尾小数点，确保 CAST 语义固定。
# 字符类避免 SQL 字符串再次解释反斜杠，兼容 Doris 的不同 sql_mode。
DOUBLE_LITERAL_REGEXP = r"^-?(?:[0-9]{1,15}(?:[.][0-9]{1,15})?|[.][0-9]{1,15})$"
NUMERIC_LITERAL_REGEXPS = {
    AggregationValueType.LONG: LONG_LITERAL_REGEXP,
    AggregationValueType.DOUBLE: DOUBLE_LITERAL_REGEXP,
}
AUTO_TIME_BUCKET_MINUTE_MAX = timedelta(hours=6)
AUTO_TIME_BUCKET_HOUR_MAX = timedelta(days=7)


class NumericRegexpCriterion(Criterion):
    """Doris 数值正则条件，模式固定且 field 已由 Builder 安全解析。"""

    def __init__(self, term: Term, value_type: AggregationValueType):
        super().__init__()
        self.term = term
        self.pattern = self.wrap_constant(NUMERIC_LITERAL_REGEXPS[value_type])

    def get_sql(self, **kwargs) -> str:
        return "{} REGEXP {}".format(
            self.term.get_sql(**kwargs),
            self.pattern.get_sql(**kwargs),
        )


class ProjectedLogSQLBuilder(BaseDorisSQLBuilder):
    """只生成显式字段投影，禁止退化为 SELECT *。"""

    def build_data_sql(self, fields: Sequence[LogFieldRef]) -> str:
        if not fields:
            raise ValueError("at least one projected field is required")

        validated_fields = []
        for field in fields:
            if not isinstance(field, LogFieldRef):
                raise TypeError("fields must be LogFieldRef instances")
            # model_construct 可绕过 Pydantic 校验，进入 SQL 层前重新验证安全边界。
            validated_fields.append(LogFieldRef.model_validate(field.model_dump()))

        terms = [self.get_pypika_field(field.raw_name, field.keys) for field in validated_fields]
        query = self._build_order_by(self._build_where(self.query.select(*terms)))
        return str(query.limit(self.page_size).offset(self.page_size * (self.page - 1)))


class LogAggregationSQLBuilder(BaseDorisSQLBuilder):
    """生成固定函数集合的 Doris 聚合 SQL。

    所有函数、别名、排序方向和 CAST 目标都来自已经复验的枚举；受控正则在
    CAST 前过滤文本，避免依赖 Doris 版本不一致的 TRY_CAST 语义。
    """

    def __init__(self, *, context: LogQueryContext, request: AggregateLogsRequest):
        self.context = context
        self.request = request
        self.effective_time_intervals = self._effective_time_intervals(request)
        super().__init__(
            table=context.table,
            conditions=list(context.conditions),
            sort_list=[],
            page=1,
            page_size=request.limit + 1,
        )

    @classmethod
    def from_request(cls, context: LogQueryContext, request: AggregateLogsRequest) -> "LogAggregationSQLBuilder":
        """重新验证对象图，防御 model_construct 绕开 Pydantic 协议。"""

        return cls(context=context, request=AggregateLogsRequest.model_validate(request.model_dump()))

    @classmethod
    def _effective_time_intervals(cls, request: AggregateLogsRequest) -> Dict[str, AggregationTimeInterval]:
        intervals = {}
        for dimension in request.dimensions:
            if dimension.type != AggregationDimensionType.TIME_BUCKET:
                continue
            interval = dimension.interval
            if interval == AggregationTimeInterval.AUTO:
                interval = cls._auto_interval(request)
            intervals[dimension.id] = interval
        return intervals

    @staticmethod
    def _auto_interval(request: AggregateLogsRequest) -> AggregationTimeInterval:
        """按已验证请求时间范围选桶，绝不读取当前时钟。"""

        span = parse_datetime(request.condition.end_time) - parse_datetime(request.condition.start_time)
        if span <= AUTO_TIME_BUCKET_MINUTE_MAX:
            return AggregationTimeInterval.MINUTE
        if span <= AUTO_TIME_BUCKET_HOUR_MAX:
            return AggregationTimeInterval.HOUR
        return AggregationTimeInterval.DAY

    def build_data_sql(self) -> str:
        """构造分组聚合，并通过 limit+1 仅判定是否还有分组行。"""

        dimensions = [(item.id, self._dimension_term(item)) for item in self.request.dimensions]
        metrics = [(item.id, self._metric_term(item)) for item in self.request.metrics]
        terms = (term.as_(identifier) for identifier, term in (*dimensions, *metrics))
        query = self._build_where(self.query.select(*terms))
        if dimensions:
            query = query.groupby(*(term for _identifier, term in dimensions))
        if self.request.order_by:
            for item in self.request.order_by:
                order = Order.desc if item.direction == "DESC" else Order.asc
                query = query.orderby(PypikaField(item.target_id), order=order)
        else:
            # 未指定排序时按已声明维度升序，保证 Agent 重试的行序稳定而不伪造 TopN 语义。
            for identifier, _term in dimensions:
                query = query.orderby(PypikaField(identifier), order=Order.asc)
        return str(query.limit(self.request.limit + 1))

    def build_quality_sql(self) -> str:
        """仅为文本/拓展数值生成一行质量计数，和聚合查询同批提交。"""

        terms = []
        for metric in self.request.metrics:
            if not metric.needs_conversion:
                continue
            field = self._field(metric.field)
            non_empty = self._non_empty_criterion(field)
            valid = self._valid_numeric_criterion(field, metric)
            # COUNT(CASE ...) 在空集稳定返回 0；SUM 在 Doris 空集会返回 NULL。
            non_empty_count = Count(Case().when(non_empty, 1)).as_(f"{metric.id}_non_empty_count")
            converted = Count(Case().when(non_empty & valid, 1)).as_(f"{metric.id}_converted_count")
            failed = Count(Case().when(non_empty & ~valid, 1)).as_(f"{metric.id}_conversion_failed_count")
            terms.extend((non_empty_count, converted, failed))
        if not terms:
            raise ValueError("quality SQL requires conversion metrics")
        return str(self._build_where(self.query.select(*terms)))

    def _dimension_term(self, dimension):
        """普通维度保留原字段，时间桶使用与 Web 统计一致的物理时间戳。"""

        if dimension.type != AggregationDimensionType.TIME_BUCKET:
            return self._field(dimension.field)
        # start_time 与采集时间戳数值相同；仅时间桶统一物理字段，不改变 WHERE 和普通投影。
        field = self.get_pypika_field(TIMESTAMP_PARTITION_FIELD.lower())
        return DateTrunc(FromUnixTime(field / 1000), self.effective_time_intervals[dimension.id].value)

    def _metric_term(self, metric: AggregationMetric):
        if metric.type == AggregationMetricType.COUNT:
            return Count("*")
        field = self._numeric_field(metric) if metric.is_numeric else self._field(metric.field)
        if metric.type == AggregationMetricType.DISTINCT_COUNT:
            return Count(field).distinct()
        if metric.type == AggregationMetricType.MIN:
            return Min(field)
        if metric.type == AggregationMetricType.MAX:
            return Max(field)
        if metric.type == AggregationMetricType.AVG:
            return Avg(field)
        if metric.type == AggregationMetricType.SUM:
            return Sum(field)
        if metric.type == AggregationMetricType.PERCENTILE_APPROX:
            return PercentileApprox(field, metric.percentile)
        raise ValueError("unsupported aggregation metric")

    def _numeric_field(self, metric: AggregationMetric):
        field = self._field(metric.field)
        if not metric.needs_conversion:
            return field
        cast_type = "LARGEINT" if metric.value_type == AggregationValueType.LONG else "DOUBLE"
        # CASE 保证不匹配正则的文本不会进入 CAST；失败值按 SQL NULL 被聚合函数忽略。
        return Case().when(self._valid_numeric_criterion(field, metric), Cast(field, cast_type))

    @staticmethod
    def _non_empty_criterion(field):
        """空串不计入质量；空白串作为非空非法文本，首期不引入 TRIM 方言依赖。"""

        return field.isnotnull() & (field != "")

    @staticmethod
    def _valid_numeric_criterion(field, metric: AggregationMetric) -> NumericRegexpCriterion:
        """所有转换和质量统计复用同一枚举驱动的正则条件。"""

        return NumericRegexpCriterion(field, metric.value_type)

    def _field(self, field: LogFieldRef):
        validated = LogFieldRef.model_validate(field.model_dump())
        return self.get_pypika_field(validated.raw_name, validated.keys)
