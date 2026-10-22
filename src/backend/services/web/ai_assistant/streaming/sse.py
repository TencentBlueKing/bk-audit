"""原生 SSE 编码的审计异常适配。

帧格式和 heartbeat 由组件维护，本层只保留审计导入入口与公开异常类型。
编码不写存储、不建立连接，也不把内部归档身份暴露给客户端。
"""

from ui_stream.exceptions import InvalidEvent
from ui_stream.sse import encode_sse_event as component_encode_sse_event
from ui_stream.sse import encode_sse_heartbeat

from services.web.ai_assistant.exceptions import InvalidStreamEvent
from services.web.ai_assistant.schemas import UIStreamEvent


def encode_sse_event(event: UIStreamEvent) -> bytes:
    """编码为 UTF-8 SSE 帧；非法 JSON 转为不携带业务正文的 InvalidStreamEvent。"""

    try:
        return component_encode_sse_event(event)
    except InvalidEvent:
        raise InvalidStreamEvent(data={"field_name": "data"}) from None


def encode_sse_item(event: UIStreamEvent | None) -> bytes:
    """保留审计异常映射，并把读取器的 None 编码为 heartbeat。"""

    return encode_sse_heartbeat() if event is None else encode_sse_event(event)


__all__ = ["encode_sse_event", "encode_sse_heartbeat", "encode_sse_item"]
