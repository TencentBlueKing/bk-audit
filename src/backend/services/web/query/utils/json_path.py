"""日志 JSON 子路径的查询能力校验。

Web、AI 条件和统计工具共用当前 BKBase/Doris 的路径限制，避免查询成功却漏值。
通用 SQL 编码与其他业务模块不依赖这里的限制。
"""

import unicodedata
from typing import List


def validate_log_json_keys(keys: List[str]) -> None:
    """校验日志字段原始子键；成功时无返回值，入口负责映射参数错误。

    Args:
        keys: JSON 对象逐层子键，未经空白裁剪或路径拼接。

    Raises:
        ValueError: 子键含当前日志查询链路不能可靠读取的字符。
    """
    if any(any(char.isspace() or unicodedata.category(char) == "Cc" or char in '\\"*' for char in key) for key in keys):
        raise ValueError(
            "unsupported JSON field key: whitespace, control characters, double quotes, backslashes or '*'"
        )
