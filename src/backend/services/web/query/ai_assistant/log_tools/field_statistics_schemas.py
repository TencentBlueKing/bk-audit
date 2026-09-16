"""程序字段统计的固定领域结果。

附件消费者直接保存此包，不引入图表协议；typed 标量沿聚合内核保真。
请求、权限、时间轴和结果预算由共用查询链路执行。
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from services.web.query.ai_assistant.log_tools.schemas import (
    AggregationEffectiveTimeInterval,
    AggregationGroupKind,
    AggregationQuerySummary,
    AggregationTimeInterval,
    StatisticsKind,
)


class StatisticsField(BaseModel):
    """经过服务端解析的业务字段，显示名不来自调用方提示。"""

    raw_name: str = Field(description='服务端解析后的日志根字段名。')
    keys: tuple[str, ...] = Field(description='JSON 子路径，按层级排列；普通字段为空数组。')
    display_name: str = Field(description='服务端字段定义的展示名；拓展字段使用最后一段 key。')


class FieldStatisticsOverview(BaseModel):
    """全范围存在性计数，空字符串计入 present。"""

    total_count: int = Field(description='完整检索范围内日志总数，不受 TopN 限制。')
    present_count: int = Field(description='字段存在且非 null 的日志数；空字符串计入存在。')
    missing_count: int = Field(description='字段缺失或为 null 的日志数；与 present_count 之和等于 total_count。')
    present_ratio: float | None = Field(description='present_count / total_count，范围 0 至 1；总数为 0 时为 null。')


class FieldDistributionGroup(BaseModel):
    """单字段 typed 类别；合成组的 value/value_type 均为 null。"""

    model_config = ConfigDict(strict=True)
    group_id: str = Field(description='本次结果内稳定的类别标识，用于关联 time_series.series；不要解析其内容。')
    kind: AggregationGroupKind = Field(description='VALUE 为真实类别，OTHER 汇总未入选 TopN 的非缺失类别，MISSING 汇总缺失值。')
    value_type: Literal["number", "string", "boolean"] | None = Field(description='VALUE 的标量类型，区分数字、字符串和布尔；合成组为 null。')
    value: str | int | float | bool | None = Field(description='保留原始标量类型和空字符串；OTHER/MISSING 为 null，不能用展示文本区分合成组。')
    count: int = Field(description='完整检索范围内该类别的日志数。')
    ratio: float | None = Field(description='count / overview.total_count，范围 0 至 1；总数为 0 时为 null。')


class FieldDistribution(BaseModel):
    """全范围 TopN 与实际存在的 OTHER/MISSING。"""

    top_n: int = Field(description='实际采用的非缺失类别上限；OTHER/MISSING 不占名额，最终组数可额外增加 2。')
    has_other: bool = Field(description='是否存在未入选 TopN 的非缺失类别并返回 OTHER 组。')
    groups: tuple[FieldDistributionGroup, ...] = Field(description='全范围按日志数选择的 TopN 类别及实际存在的 OTHER/MISSING；与时序共享类别集合。')


class FieldCountSeries(BaseModel):
    """counts 与完整 bucket_starts 一一对齐。"""

    group_id: str = Field(description='对应 distribution.groups 中的类别标识。')
    counts: tuple[int, ...] = Field(description='与 bucket_starts 等长且同序的日志计数；空时间桶补 0。')


class FieldTimeSeries(BaseModel):
    """共享规划器生成的完整可信时间轴。"""

    requested_interval: AggregationTimeInterval = Field(description='请求的时间粒度，AUTO 表示由服务端按范围及预算选择。')
    effective_interval: AggregationEffectiveTimeInterval = Field(description='实际使用的 MINUTE/HOUR/DAY 粒度。')
    timezone: str = Field(description='时间桶划分采用的服务端有效时区。')
    bucket_starts: tuple[str, ...] = Field(description='按时间升序排列的完整时间桶起点，ISO 8601 带时区；首尾桶统计仍受原检索范围约束。')
    series: tuple[FieldCountSeries, ...] = Field(description='分布中各类别的完整计数序列，按 group_id 关联。')


class FieldNumericSummary(BaseModel):
    """同一最终查询的原生数值摘要，无有效数字时所有摘要为 null。"""

    min: int | float | None = Field(description='完整范围内原生数值的最小值；无有效数字为 null。')
    max: int | float | None = Field(description='完整范围内原生数值的最大值；无有效数字为 null。')
    avg: int | float | None = Field(description='完整范围内原生数值的平均值；无有效数字为 null。')
    median: int | float | None = Field(description='完整范围内原生数值的近似中位数；无有效数字为 null。')
    median_is_approximate: Literal[True] = Field(default=True, description='恒为 true，明确中位数使用近似分位数算法。')
    valid_count: int = Field(description='完整范围内原生数值数量；不将字符串或布尔转换为数字。')
    conversion_failed_count: int = Field(description='存在但非原生数值的数量；当前仅对全范围数值字段生成摘要，因此成功返回时为 0。')


class FieldStatisticsResult(BaseModel):
    """程序统计固定包，供附件处理器直接消费。"""

    field: StatisticsField = Field(description='服务端解析的字段标识与展示名。')
    statistics_kind: StatisticsKind = Field(description='NUMERIC 为声明数值字段或全范围存在值均为原生数值；其他为 CATEGORICAL，不依据样本决定。')
    overview: FieldStatisticsOverview = Field(description='完整检索范围的存在性概览。')
    distribution: FieldDistribution = Field(description='全范围类别分布；默认 TopN 100，额外返回实际存在的 OTHER/MISSING。')
    time_series: FieldTimeSeries = Field(description='与分布共享类别集合的完整时间序列。')
    numeric_summary: FieldNumericSummary | None = Field(description='仅 NUMERIC 统计包返回数值摘要；CATEGORICAL 为 null。')
    query_summary: AggregationQuerySummary = Field(description='本次统计实际范围、执行时间及预算决策；不代表分页。')
