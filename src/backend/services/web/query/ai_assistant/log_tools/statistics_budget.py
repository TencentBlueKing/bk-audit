"""规划完整时间轴及数值单元格预算。

轴使用服务端时区，输入范围为闭区间；空类别占零单元格，ALL 由消费者传一组。
程序统计与 MCP 的 AUTO 共用可配置的可读性阈值，选粒度后独立检查预算。
"""
from dataclasses import dataclass
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo

from django.conf import settings

from services.web.query.ai_assistant.exceptions import StatisticsBudgetExceeded
from services.web.query.ai_assistant.log_tools.schemas import (
    AGGREGATION_MAX_CELLS,
    AGGREGATION_MAX_TIME_BUCKETS,
)
from services.web.query.ai_assistant.log_tools.time_range import parse_log_time

INTERVAL_SECONDS = {"MINUTE": 60, "HOUR": 3600}
INTERVALS = ("MINUTE", "HOUR", "DAY", "MONTH")


def budget_limits():
    """配置只能收紧协议上限，零预算关闭相应结果容量。"""
    return (
        min(AGGREGATION_MAX_TIME_BUCKETS, max(0, settings.AI_LOG_AGGREGATION_MAX_TIME_BUCKETS)),
        min(AGGREGATION_MAX_CELLS, max(0, settings.AI_LOG_AGGREGATION_MAX_CELLS)),
    )


@dataclass(frozen=True)
class StatisticsTimeAxis:
    """可信桶起点按真实时间递增；无时间维度用唯一 None 桶表示。"""

    requested_interval: str | None
    effective_interval: str | None
    timezone: str
    bucket_starts: tuple[str | None, ...]


def _bucket_starts(start, end, interval, limit):
    """最多构造上限加一项；分钟/小时沿 UTC 前进，日/月桶按当地日历推进。"""
    floor_args = dict(second=0, microsecond=0)
    if interval in {"HOUR", "DAY", "MONTH"}:
        floor_args["minute"] = 0
    if interval in {"DAY", "MONTH"}:
        floor_args["hour"] = 0
    if interval == "MONTH":
        floor_args["day"] = 1
    current = start.replace(**floor_args)
    buckets = []
    while current.timestamp() <= end.timestamp() and len(buckets) <= limit:
        buckets.append(current.isoformat())
        if interval == "MONTH":
            current = current.replace(year=current.year + current.month // 12, month=current.month % 12 + 1)
        elif interval == "DAY":
            current = current + timedelta(days=1)
        else:
            current = (current.astimezone(timezone.utc) + timedelta(seconds=INTERVAL_SECONDS[interval])).astimezone(
                start.tzinfo
            )
    return tuple(buckets)


def build_time_axis(
    *, start_time, end_time, interval, group_count, numeric_columns, minimum_buckets=None
) -> StatisticsTimeAxis:
    """返回完整轴；非法内部预算参数抛 ValueError，容量不足抛 StatisticsBudgetExceeded。"""
    if type(group_count) is not int or group_count < 0 or type(numeric_columns) is not int or numeric_columns < 1:
        raise ValueError("invalid statistics budget inputs")
    if minimum_buckets is None:
        minimum_buckets = settings.AI_LOG_STATISTICS_AUTO_MIN_BUCKETS
    if type(minimum_buckets) is not int or minimum_buckets < 1:
        raise ValueError("invalid readability threshold")
    max_buckets, max_cells = budget_limits()
    if interval is None:
        if group_count * numeric_columns > max_cells:
            raise StatisticsBudgetExceeded()
        return StatisticsTimeAxis(None, None, settings.TIME_ZONE, (None,))
    if interval not in {"AUTO", *INTERVALS}:
        raise ValueError("invalid statistics interval")
    zone = ZoneInfo(settings.TIME_ZONE)
    start, end = (parse_log_time(value) for value in (start_time, end_time))
    if start.timestamp() > end.timestamp():
        raise ValueError("invalid statistics time range")
    start, end = start.astimezone(zone), end.astimezone(zone)
    axes = {name: _bucket_starts(start, end, name, max(max_buckets, minimum_buckets)) for name in INTERVALS}
    candidates = {
        name: buckets
        for name, buckets in axes.items()
        if len(buckets) <= max_buckets and group_count * len(buckets) * numeric_columns <= max_cells
    }
    if interval == "AUTO":
        effective = next((name for name in reversed(INTERVALS) if len(axes[name]) >= minimum_buckets), "MINUTE")
    else:
        effective = interval
    if effective not in candidates:
        coarser = [name for name in candidates if INTERVALS.index(name) > INTERVALS.index(effective)]
        raise StatisticsBudgetExceeded(suggested_interval=coarser[0] if coarser else None)
    return StatisticsTimeAxis(interval, effective, settings.TIME_ZONE, candidates[effective])
