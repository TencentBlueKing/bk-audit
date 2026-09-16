"""程序字段统计的固定领域结果。

附件消费者直接保存此包，不引入图表协议；typed 标量沿聚合内核保真。
请求、权限、时间轴和结果预算由共用查询链路执行。
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict

from services.web.query.ai_assistant.log_tools.schemas import (
    AggregationEffectiveTimeInterval,
    AggregationGroupKind,
    AggregationQuerySummary,
    AggregationTimeInterval,
    StatisticsKind,
)


class StatisticsField(BaseModel):
    """经过服务端解析的业务字段，显示名不来自调用方提示。"""

    raw_name: str
    keys: tuple[str, ...]
    display_name: str


class FieldStatisticsOverview(BaseModel):
    """全范围存在性计数，空字符串计入 present。"""

    total_count: int
    present_count: int
    missing_count: int
    present_ratio: float | None


class FieldDistributionGroup(BaseModel):
    """单字段 typed 类别；合成组的 value/value_type 均为 null。"""

    model_config = ConfigDict(strict=True)
    group_id: str
    kind: AggregationGroupKind
    value_type: Literal["number", "string", "boolean"] | None
    value: str | int | float | bool | None
    count: int
    ratio: float | None


class FieldDistribution(BaseModel):
    """全范围 TopN 与实际存在的 OTHER/MISSING。"""

    top_n: int
    has_other: bool
    groups: tuple[FieldDistributionGroup, ...]


class FieldCountSeries(BaseModel):
    """counts 与完整 bucket_starts 一一对齐。"""

    group_id: str
    counts: tuple[int, ...]


class FieldTimeSeries(BaseModel):
    """共享规划器生成的完整可信时间轴。"""

    requested_interval: AggregationTimeInterval
    effective_interval: AggregationEffectiveTimeInterval
    timezone: str
    bucket_starts: tuple[str, ...]
    series: tuple[FieldCountSeries, ...]


class FieldNumericSummary(BaseModel):
    """同一最终查询的原生数值摘要，无有效数字时所有摘要为 null。"""

    min: int | float | None
    max: int | float | None
    avg: int | float | None
    median: int | float | None
    median_is_approximate: Literal[True] = True
    valid_count: int
    conversion_failed_count: int


class FieldStatisticsResult(BaseModel):
    """程序统计固定包，供附件处理器直接消费。"""

    field: StatisticsField
    statistics_kind: StatisticsKind
    overview: FieldStatisticsOverview
    distribution: FieldDistribution
    time_series: FieldTimeSeries
    numeric_summary: FieldNumericSummary | None
    query_summary: AggregationQuerySummary
