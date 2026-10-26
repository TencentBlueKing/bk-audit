"""程序字段统计的固定领域结果。

附件消费者直接保存此包，不引入图表协议；typed 标量沿聚合内核保真。
请求、权限、时间轴和结果预算由共用查询链路执行。
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from services.web.query.ai_assistant.log_tools.schemas import (
    AggregationEffectiveTimeInterval,
    AggregationTimeInterval,
    LogQueryExecutionSummary,
    StatisticsKind,
    serialize_statistics_number,
)


class StatisticsField(BaseModel):
    """经过服务端解析的业务字段，显示名不来自调用方提示。"""

    raw_name: str = Field(description='服务端解析后的日志根字段名。')
    keys: tuple[str, ...] = Field(description='JSON 子路径，按层级排列；普通字段为空数组。')
    display_name: str = Field(description='服务端字段定义的展示名；声明子字段复用内置中文别名；动态路径使用最后一段 key。')


class FieldStatisticsOverview(BaseModel):
    """全范围存在性计数，空字符串计入 present。"""

    total_count: int = Field(description='完整检索范围内的日志总数。')
    present_count: int = Field(description='字段存在且非 null 的日志数；空字符串计入存在。')
    missing_count: int = Field(description='字段缺失或为 null 的日志数；与 present_count 之和等于 total_count。')
    present_ratio: float | None = Field(
        description='present_count / total_count，范围 0 至 1；输出保留 4 位小数，前端展示百分比时建议保留 2 位；总数为 0 时为 null。'
    )

    @field_serializer("present_ratio")
    def serialize_present_ratio(self, value):
        """概览存在率与 MCP 使用相同的四位小数输出精度。"""
        return serialize_statistics_number(value)


class FieldDistributionGroup(BaseModel):
    """单字段 typed 类别；合成组的 value/value_type 均为 null。"""

    model_config = ConfigDict(strict=True)
    group_id: str = Field(description='本次结果内稳定的类别标识，用于关联 time_series.series；不要解析其内容。')
    kind: Literal["VALUE", "MISSING"] = Field(description="VALUE 为真实类别，MISSING 为缺失或 null；不合并其他类别。")
    value_type: Literal["number", "string", "boolean"] | None = Field(description='VALUE 的标量类型，区分数字、字符串和布尔；合成组为 null。')
    value: str | int | float | bool | None = Field(description='保留原始标量类型和空字符串；MISSING 为 null，不能用展示文本区分合成组。')
    value_label: str | None = Field(default=None, description="内置枚举中文名称；未知值/动态路径/MISSING 为 null，原始 value 不变。")
    count: int = Field(description='完整检索范围内该类别的日志数。')
    ratio: float | None = Field(
        description='count / overview.total_count，范围 0 至 1；输出保留 4 位小数，前端展示百分比时建议保留 2 位；总数为 0 时为 null。'
    )

    @field_serializer("ratio")
    def serialize_ratio(self, value):
        """分布占比与 MCP 使用相同的四位小数输出精度。"""
        return serialize_statistics_number(value)


class FieldDistribution(BaseModel):
    """全范围所有真实类别及实际缺失组。"""

    groups: tuple[FieldDistributionGroup, ...] = Field(description="所有 typed 类别及实际存在的 MISSING；与时序共享类别集合。")


class FieldCountSeries(BaseModel):
    """counts 与完整 bucket_starts 一一对齐。"""

    group_id: str = Field(description='对应 distribution.groups 中的类别标识。')
    counts: tuple[int, ...] = Field(description='与 bucket_starts 等长且同序的日志计数；空时间桶补 0。')


class FieldTimeSeries(BaseModel):
    """共享规划器生成的完整可信时间轴。"""

    requested_interval: AggregationTimeInterval = Field(
        description='请求的时间粒度，AUTO 按完整范围从月到分钟选首个达到桶数阈值的粒度（默认12，后端可配置），容量独立检查。'
    )
    effective_interval: AggregationEffectiveTimeInterval = Field(description='实际使用的 MINUTE/HOUR/DAY/MONTH 粒度。')
    timezone: str = Field(description='时间桶划分采用的服务端有效时区。')
    bucket_starts: tuple[str, ...] = Field(description='按时间升序排列的完整时间桶起点，ISO 8601 带时区；首尾桶统计仍受原检索范围约束。')
    series: tuple[FieldCountSeries, ...] = Field(description='分布中各类别的完整计数序列，按 group_id 关联。')


class FieldNumericSummary(BaseModel):
    """同一最终查询的原生数值摘要；浮点数输出四位小数，无有效数字时所有摘要为 null。"""

    min: int | float | None = Field(description='完整范围内原生数值的最小值，浮点数输出保留 4 位小数；无有效数字为 null。')
    max: int | float | None = Field(description='完整范围内原生数值的最大值，浮点数输出保留 4 位小数；无有效数字为 null。')
    avg: int | float | None = Field(description='完整范围内原生数值的平均值，浮点数输出保留 4 位小数；无有效数字为 null。')
    median: int | float | None = Field(description='完整范围内原生数值的近似中位数，浮点数输出保留 4 位小数；无有效数字为 null。')
    median_is_approximate: Literal[True] = Field(default=True, description='恒为 true，明确中位数使用近似分位数算法。')
    valid_count: int = Field(description='完整范围内原生数值数量；不将字符串或布尔转换为数字。')
    conversion_failed_count: int = Field(description='存在但非原生数值的数量；当前仅对全范围数值字段生成摘要，因此成功返回时为 0。')

    @field_serializer("min", "max", "avg", "median")
    def serialize_summary_value(self, value):
        """数值摘要和 MCP 指标共用输出精度，整数与空值保持原类型。"""
        return serialize_statistics_number(value)


class FieldStatisticsQuerySummary(LogQueryExecutionSummary):
    """程序统计的实际范围及完整结果规模，不包含 MCP 的 TopN 元数据。"""

    returned_count: int = Field(ge=0, description="完整类别与完整时间轴的计数单元数。")
    total_count: int = Field(ge=0, description="实际完整范围内的日志总数。")
    scope_id: str = Field(description="实际查询的业务系统 ID。")
    start_time: str = Field(description="实际查询开始时间，闭区间。")
    end_time: str = Field(description="实际查询结束时间，闭区间。")
    requested_interval: AggregationTimeInterval = Field(description="请求粒度，包含 AUTO。")
    effective_interval: AggregationEffectiveTimeInterval = Field(description="实际粒度，包含自然月，不包含 AUTO。")
    timezone: str = Field(description="解释时间和划分桶的服务端时区。")
    complete: Literal[True] = Field(description="成功必为完整类别、完整时间轴，不返回截断结果。")


class FieldStatisticsResult(BaseModel):
    """程序统计固定包，供附件处理器直接消费。"""

    field: StatisticsField = Field(description='服务端解析的字段标识与展示名。')
    statistics_kind: StatisticsKind = Field(description='NUMERIC 为声明数值字段或全范围存在值均为原生数值；其他为 CATEGORICAL，不依据样本决定。')
    overview: FieldStatisticsOverview = Field(description='完整检索范围的存在性概览。')
    distribution: FieldDistribution = Field(description='全范围所有类别及实际存在的 MISSING；无 TopN/OTHER。')
    time_series: FieldTimeSeries = Field(description='与分布共享类别集合的完整时间序列。')
    numeric_summary: FieldNumericSummary | None = Field(description='仅 NUMERIC 统计包返回数值摘要；CATEGORICAL 为 null。')
    query_summary: FieldStatisticsQuerySummary = Field(description='本次统计实际范围、执行时间及预算决策；不代表分页。')
