"""保留日志工具的时间解析导入路径；实现由日志查询公共模块提供。"""

from services.web.query.utils.time_range import parse_log_time

__all__ = ["parse_log_time"]
