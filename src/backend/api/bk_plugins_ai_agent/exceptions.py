# -*- coding: utf-8 -*-
"""AG-UI 流式调用的受控异常类型。"""


class AGUIStreamError(Exception):
    """AG-UI 流调用失败的基类，避免调用方依赖底层 HTTP/SSE 细节。"""


class AGUIStreamProtocolError(AGUIStreamError):
    """上游事件不满足完整 AG-UI 生命周期或消息协议。"""


class AGUIStreamCapacityExceeded(AGUIStreamError):
    """完整事件集超过平台既有流容量上限。"""
