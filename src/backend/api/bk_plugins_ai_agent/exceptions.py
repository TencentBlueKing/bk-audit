# -*- coding: utf-8 -*-
"""AG-UI 流式调用的受控异常类型。"""


class AGUIStreamProtocolError(Exception):
    """上游 SSE data 不是可交付给业务回调的 JSON 对象。"""
