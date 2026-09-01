"""日志工具共享的受控异常映射。"""

from bk_resource.exceptions import APIRequestError
from requests.exceptions import Timeout as RequestsTimeout

from services.web.query.ai_assistant.exceptions import (
    LogQueryFailed,
    LogQueryTimeout,
    LogToolException,
)


def map_log_query_error(error: BaseException) -> LogToolException:
    """将底层失败收敛为不泄露查询细节的日志工具异常。"""

    if isinstance(error, LogToolException):
        return error
    if isinstance(error, (RequestsTimeout, TimeoutError)) or (
        isinstance(error, APIRequestError)
        and (getattr(error, "status_code", None) in {408, 504} or has_timeout_in_chain(error))
    ):
        return LogQueryTimeout()
    return LogQueryFailed()


def has_timeout_in_chain(error: BaseException) -> bool:
    """识别 bk_resource 保留在 cause/context 中的网络超时。"""

    pending = [error]
    visited = set()
    while pending:
        current = pending.pop()
        if id(current) in visited:
            continue
        visited.add(id(current))
        if isinstance(current, (RequestsTimeout, TimeoutError)):
            return True
        pending.extend(item for item in (current.__cause__, current.__context__) if item is not None)
    return False
