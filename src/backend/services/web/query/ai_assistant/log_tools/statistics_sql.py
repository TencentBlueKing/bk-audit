"""单语句完整统计：规范化、全范围排名、原集合归组及有界结果帧。

预检只供规划使用，最终语句重新计算排名、质量及完整性计数。
所有 UNION 值显式走 STRING 通道，防止传输层提前解析数值类别。
"""
from datetime import datetime

from services.web.query.ai_assistant.exceptions import UnsupportedAggregation
from services.web.query.ai_assistant.log_tools.schemas import (
    AGGREGATION_STANDARD_FIELD_TYPES,
    AggregateLogsRequest,
    AggregationDimensionType,
    AggregationMetricType,
    AggregationValueType,
)
from services.web.query.ai_assistant.log_tools.statistics_budget import (
    budget_limits,
    build_time_axis,
)
from services.web.query.ai_assistant.log_tools.statistics_fields import (
    SCALAR_KINDS,
    StatisticsFieldSQL,
    literal,
)
from services.web.query.constants import TIMESTAMP_PARTITION_FIELD
from services.web.query.utils.doris import BaseDorisSQLBuilder

LONG_LITERAL_REGEXP = r"^-?[0-9]{1,18}$"
DOUBLE_LITERAL_REGEXP = r"^-?(?:[0-9]{1,15}(?:[.][0-9]{1,15})?|[.][0-9]{1,15})$"


class StatisticsSQLBuilder(BaseDorisSQLBuilder):
    """只使用已鉴权条件和复验 DTO；内部字段/指标序号不使用调用方标识符。"""

    def __init__(self, *, context, request):
        self.context = context
        self.request = AggregateLogsRequest.model_validate(request.model_dump())
        self.effective_time_intervals = {}
        self.time_axis = None
        self.numeric_columns = len(self.request.metrics) + 2
        self.dimensions = tuple(d for d in self.request.dimensions if d.type == AggregationDimensionType.FIELD)
        self.fields = []
        self._field_indices = {}
        for item in (*self.dimensions, *self.request.metrics):
            if item.field is not None:
                key = (item.field.raw_name, tuple(item.field.keys))
                if key not in self._field_indices:
                    self._field_indices[key] = len(self.fields)
                    self.fields.append(StatisticsFieldSQL(item.field, len(self.fields)))
        super().__init__(table=context.table, conditions=list(context.conditions), sort_list=[], page=1, page_size=1)

    @classmethod
    def from_request(cls, context, request):
        """保持领域消费者的构造接口，防御 model_construct 绕过验证。"""
        return cls(context=context, request=request)

    def field_prefix(self, field):
        """定位已复验且去重的业务字段。"""
        return f"f{self._field_indices[(field.raw_name, tuple(field.keys))]}"

    def _metric_value(self, metric):
        """原生数值保留原域；显式文本转换失败为 NULL，空串仍计 present。"""
        p = self.field_prefix(metric.field)
        if not metric.needs_conversion:
            return self._declared_numeric(p, metric)
        cast_type = "LARGEINT" if metric.value_type == AggregationValueType.LONG else "DOUBLE"
        regex = LONG_LITERAL_REGEXP if metric.value_type == AggregationValueType.LONG else DOUBLE_LITERAL_REGEXP
        native = f"CAST({p}_key AS {cast_type})"
        if metric.value_type == AggregationValueType.LONG:
            native = f"CASE WHEN {p}_key REGEXP {literal(LONG_LITERAL_REGEXP)} THEN {native} END"
        return (
            f"CASE WHEN {p}_type = 'number' THEN {native} "
            f"WHEN {p}_type = 'string' AND {p}_key REGEXP {literal(regex)} THEN CAST({p}_key AS {cast_type}) END"
        )

    @staticmethod
    def _declared_numeric(prefix, metric):
        """实际声明来自服务端，不能使用调用方提供的 field_type。"""
        from_type = metric.field.raw_name
        # 字段 SQL 已将正确原生域写入 i/d_raw；不能 COALESCE 让整数先升为 DOUBLE。
        return (
            f"{prefix}_i_safe"
            if AGGREGATION_STANDARD_FIELD_TYPES.get(from_type) in {"int", "long", "timestamp"}
            else f"{prefix}_d_safe"
        )

    def metric_aggregate(self, index):
        """指标只引用 normalized 原值，OTHER 的非可加函数不复用类别摘要。"""
        metric = self.request.metrics[index]
        if metric.type == AggregationMetricType.COUNT:
            return "COUNT(*)"
        if metric.type == AggregationMetricType.DISTINCT_COUNT:
            p = self.field_prefix(metric.field)
            return f"COUNT(DISTINCT {p}_type, {p}_key)"
        value = f"m{index}_value"
        if metric.type == AggregationMetricType.PERCENTILE_APPROX:
            return f"PERCENTILE_APPROX({value}, {metric.percentile})"
        return f"{metric.type.value}({value})"

    def _base_ctes(self):
        """构造全范围规范化关系；任何无效类型/数值均在 TopN 之前计数。"""
        columns = [column for field in self.fields for column in field.source_columns(self)]
        if self.time_axis:
            columns.append(f"`{TIMESTAMP_PARTITION_FIELD}` AS event_timestamp")
        base = str(self._build_where(self.query.select(1)))
        base = base.replace("SELECT 1", "SELECT " + (", ".join(columns) or "1 AS source_row"), 1)
        ctes = [f"source_values AS ({base})"]
        for name, source, method in (
            ("safe_values", "source_values", "safe_columns"),
            ("text_values", "safe_values", "text_columns"),
            ("canonical_values", "text_values", "canonical_columns"),
        ):
            expressions = [column for field in self.fields for column in getattr(field, method)()]
            ctes.append(f"{name} AS (SELECT *{', ' if expressions else ''}{', '.join(expressions)} FROM {source})")
        normalized = []
        for i, dimension in enumerate(self.dimensions):
            p = self.field_prefix(dimension.field)
            normalized.extend((f"{p}_type AS d{i}_type", f"{p}_key AS d{i}_key"))
        for i, metric in enumerate(self.request.metrics):
            if metric.is_numeric:
                normalized.append(f"{self._metric_value(metric)} AS m{i}_value")
        ctes.append(
            f"normalized AS (SELECT *{', ' if normalized else ''}{', '.join(normalized)} FROM canonical_values)"
        )
        bad_type = (
            " OR ".join(
                f"({f.prefix}_type IS NOT NULL AND {f.prefix}_observed NOT IN {SCALAR_KINDS})" for f in self.fields
            )
            or "FALSE"
        )
        bad_number = (
            " OR ".join(f"({f.prefix}_type = 'number' AND {f.prefix}_key IS NULL)" for f in self.fields) or "FALSE"
        )
        ctes.append(
            f"validation AS (SELECT COUNT(*) AS total_count, "
            f"COUNT(CASE WHEN {bad_type} THEN 1 END) AS invalid_type_count, "
            f"COUNT(CASE WHEN {bad_number} THEN 1 END) AS invalid_number_count FROM normalized)"
        )
        if self.dimensions:
            keys = ", ".join(f"d{i}_{suffix}" for i in range(len(self.dimensions)) for suffix in ("type", "key"))
            present = " AND ".join(f"d{i}_type IS NOT NULL" for i in range(len(self.dimensions)))
            metrics = ", ".join(f"{self.metric_aggregate(i)} AS m{i}" for i in range(len(self.request.metrics)))
            ctes.append(
                f"category_counts AS (SELECT {keys}, COUNT(*) AS log_count, {metrics} "
                f"FROM normalized WHERE {present} GROUP BY {keys})"
            )
        return ctes

    def _ordering(self):
        """显式排序应用全范围指标/typed 类别值，并追加稳定元组键打破并列。"""
        dimensions = {d.id: i for i, d in enumerate(self.dimensions)}
        metrics = {m.id: i for i, m in enumerate(self.request.metrics)}
        order = []
        for item in self.request.order_by:
            direction = item.direction.value
            if item.target_id in dimensions:
                i = dimensions[item.target_id]
                order.extend(
                    (
                        f"d{i}_type {direction}",
                        f"CASE WHEN d{i}_type = 'number' THEN CAST(d{i}_key AS DOUBLE) END {direction} NULLS LAST",
                        f"d{i}_key {direction}",
                    )
                )
            else:
                order.append(f"m{metrics[item.target_id]} {direction} NULLS LAST")
        if not order:
            order.append("log_count DESC")
        order.extend(f"d{i}_{suffix} ASC" for i in range(len(self.dimensions)) for suffix in ("type", "key"))
        return ", ".join(order)

    def build_preflight_sql(self):
        """一行全范围类型/类别计数供 Task4 规划；最终查询不会复用这些计数。"""
        ctes = self._base_ctes() + self._group_ctes()
        return (
            "WITH "
            + ",\n".join(ctes)
            + " SELECT CAST((SELECT COUNT(*) FROM aggregated) AS STRING) AS group_count, "
            + "CAST(invalid_type_count AS STRING) AS invalid_type_count, "
            + "CAST(invalid_number_count AS STRING) AS invalid_number_count FROM validation"
        )

    def _group_ctes(self):
        """TopN、OTHER 和 MISSING 的成员映射全部在 Doris 内完成。"""
        metrics = ", ".join(f"{self.metric_aggregate(i)} AS m{i}" for i in range(len(self.request.metrics)))
        if not self.dimensions:
            return [
                f"aggregated AS (SELECT 1 AS group_key, 'ALL' AS group_kind, "
                f"COUNT(*) AS log_count, {metrics} FROM normalized)"
            ]
        top_n = self.request.top_n
        missing = " OR ".join(f"n.d{i}_type IS NULL" for i in range(len(self.dimensions)))
        join = " AND ".join(
            f"n.d{i}_{part} = s.d{i}_{part}" for i in range(len(self.dimensions)) for part in ("type", "key")
        )
        group_key = (
            f"CASE WHEN {missing} THEN {top_n + 2} WHEN s.group_key IS NULL THEN {top_n + 1} ELSE s.group_key END"
        )
        return [
            f"ranked AS (SELECT *, ROW_NUMBER() OVER (ORDER BY {self._ordering()}) AS group_key FROM category_counts)",
            f"selected AS (SELECT * FROM ranked WHERE group_key <= {top_n})",
            f"mapped AS (SELECT n.*, {group_key} AS group_key FROM normalized n LEFT JOIN selected s ON {join})",
            f"aggregated AS (SELECT group_key, CASE WHEN group_key = {top_n + 2} THEN 'MISSING' "
            f"WHEN group_key = {top_n + 1} THEN 'OTHER' ELSE 'VALUE' END AS group_kind, "
            f"COUNT(*) AS log_count, {metrics} FROM mapped GROUP BY group_key)",
        ]

    def _frame(self, values, source):
        """给每个 UNION 分支显式补 STRING NULL，避免列类型提升破坏数值通道。"""
        names = ["frame", "key", "kind", "n", "a", "b", "c", "d", "e", "bucket"]
        names.extend(f"d{i}_{part}" for i in range(len(self.dimensions)) for part in ("type", "json"))
        names.extend(f"m{i}" for i in range(len(self.request.metrics)))
        return (
            "SELECT "
            + ", ".join(f"CAST({values.get(name, 'NULL')} AS STRING) AS {name}" for name in names)
            + " "
            + source
        )

    def build_complete_sql(self, effective_interval=None):
        """生成最终同快照帧；预算超限时只留 META 供受控失败或 AUTO 重查。"""
        time_dimensions = [d for d in self.request.dimensions if d.type == AggregationDimensionType.TIME_BUCKET]
        if time_dimensions and self.time_axis is None:
            effective_interval = effective_interval or time_dimensions[0].interval
            self.time_axis = build_time_axis(
                start_time=self.context.condition.start_time,
                end_time=self.context.condition.end_time,
                interval=effective_interval,
                group_count=0,
                numeric_columns=self.numeric_columns,
            )
        if not time_dimensions and effective_interval is not None:
            raise UnsupportedAggregation()
        ctes = self._base_ctes() + self._group_ctes()
        row_source = "aggregated"
        if self.time_axis:
            metrics = ", ".join(f"{self.metric_aggregate(i)} AS m{i}" for i in range(len(self.request.metrics)))
            source = "mapped" if self.dimensions else "normalized"
            group_key = "group_key" if self.dimensions else "1 AS group_key"
            grouping = "group_key, bucket" if self.dimensions else "bucket"
            ctes.append(f"bucketed AS (SELECT *, {self._bucket_expression()} AS bucket FROM {source})")
            ctes.append(
                f"time_rows AS (SELECT {group_key}, bucket, COUNT(*) AS log_count, {metrics} "
                f"FROM bucketed GROUP BY {grouping})"
            )
            row_source = "time_rows"
        quality_indices = [i for i, m in enumerate(self.request.metrics) if m.needs_conversion]
        for i in quality_indices:
            p = self.field_prefix(self.request.metrics[i].field)
            ctes.append(
                f"quality_{i} AS (SELECT COUNT({p}_type) AS present_count, "
                f"COUNT(m{i}_value) AS converted_count FROM normalized)"
            )
        guard = "validation.invalid_type_count = 0 AND validation.invalid_number_count = 0"
        bucket_count = len(self.time_axis.bucket_starts) if self.time_axis else 1
        guard += (
            f" AND (SELECT COUNT(*) FROM aggregated) * {bucket_count} * {self.numeric_columns} <= {budget_limits()[1]}"
        )
        frames = [
            self._frame(
                dict(
                    frame="'META'",
                    n="total_count",
                    a="(SELECT COUNT(*) FROM aggregated)",
                    b=f"(SELECT COUNT(*) FROM {row_source})",
                    c=str(len(quality_indices)),
                    d="invalid_type_count",
                    e="invalid_number_count",
                ),
                "FROM validation",
            )
        ]
        group = dict(frame="'GROUP'", key="g.group_key", kind="g.group_kind", n="g.log_count")
        for i in range(len(self.dimensions)):
            group[f"d{i}_type"] = f"s.d{i}_type"
            group[f"d{i}_json"] = f"CASE WHEN s.d{i}_type = 'string' THEN JSON_QUOTE(s.d{i}_key) ELSE s.d{i}_key END"
        join = " LEFT JOIN selected s ON g.group_key = s.group_key" if self.dimensions else ""
        frames.append(self._frame(group, f"FROM aggregated g{join} CROSS JOIN validation WHERE {guard}"))
        row = dict(frame="'ROW'", key="g.group_key", n="g.log_count")
        row.update({f"m{i}": f"g.m{i}" for i in range(len(self.request.metrics))})
        if self.time_axis:
            row["bucket"] = "g.bucket"
        frames.append(self._frame(row, f"FROM {row_source} g CROSS JOIN validation WHERE {guard}"))
        for i in quality_indices:
            frames.append(
                self._frame(
                    dict(
                        frame="'QUALITY'",
                        key=str(i),
                        n="present_count",
                        a="converted_count",
                        b="present_count - converted_count",
                    ),
                    f"FROM quality_{i} CROSS JOIN validation WHERE {guard}",
                )
            )
        return "WITH " + ",\n".join(ctes) + "\n" + "\nUNION ALL\n".join(frames)

    def _bucket_expression(self):
        """可信等间隔轴用整数毫秒归桶；仅跨不等长日区段使用少量 CASE 分支。"""
        starts = [int(datetime.fromisoformat(value).timestamp() * 1000) for value in self.time_axis.bucket_starts]
        if len(starts) == 1:
            return "0"
        segments = []
        index = 0
        while index < len(starts) - 1:
            step = starts[index + 1] - starts[index]
            end = index + 1
            while end < len(starts) - 1 and starts[end + 1] - starts[end] == step:
                end += 1
            expression = f"({index} + ((event_timestamp - {starts[index]}) DIV {step}))"
            segments.append((starts[end], expression))
            index = end
        if len(segments) == 1:
            # 最后一个桶可能只有闭区间终点，算术仍保留其独立索引。
            return f"CASE WHEN event_timestamp >= {starts[-1]} THEN {len(starts) - 1} ELSE {segments[0][1]} END"
        branches = " ".join(f"WHEN event_timestamp < {end} THEN {expression}" for end, expression in segments)
        return f"CASE {branches} ELSE {len(starts) - 1} END"
