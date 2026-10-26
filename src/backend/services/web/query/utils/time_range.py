"""日志查询共用的时间解析，不改变公共时间工具的历史行为。

无时区字符串按默认时区解释；显式偏移保留绝对时刻后转为默认时区。
条件校验、Doris分区和统计桶轴复用同一语义，避免UTC被当成本地时间。
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import arrow
from dateutil.parser import parse
from django.conf import settings


def parse_log_time(value: str) -> datetime:
    """解析日志时间并返回默认时区的aware datetime。

    Collector历史日期格式（如斜杠日期）保留支持，未提供的日期部分仍取月初/午夜；
    显式ISO时区由fromisoformat保留，不能将其直接替换成本地时区。

    Raises:
        ValueError: 时间字符串无法解析。
    """

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        # 沿用 Collector 原有格式边界，dateutil 仅用于保留历史格式中的显式偏移。
        arrow.get(value)
        parsed = parse(value, default=datetime(1, 1, 1))
    zone = ZoneInfo(settings.TIME_ZONE)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=zone)
    return parsed.astimezone(zone)
