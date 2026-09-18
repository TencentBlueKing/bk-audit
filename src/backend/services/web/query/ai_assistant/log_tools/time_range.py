"""日志工具共享时间解析，保证 SQL 边界与统计时间轴指向同一时刻。

无时区字符串使用服务端默认时区；显式偏移保持其真实时刻，再转为默认时区。
先规范化再交给 Collector，避免其历史解析把 UTC 当作本地时间。
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings


def parse_log_time(value: str) -> datetime:
    """将接口允许的时间字符串转为默认时区的 aware datetime。

    Args:
        value: ISO 8601 时间或无时区的本地日期时间字符串。
    Raises:
        ValueError: 字符串不能解析为日期时间。
    """
    parsed = datetime.fromisoformat(value)
    # 使用 ZoneInfo，不能把 pytz 时区直接 replace 到 naive datetime（会落入历史 LMT）。
    zone = ZoneInfo(settings.TIME_ZONE)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=zone)
    return parsed.astimezone(zone)
