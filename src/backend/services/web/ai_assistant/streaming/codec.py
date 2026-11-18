"""把组件平台事件映射为审计 DTO 与持久化格式。

Runtime 事件进入 pending 前分配稳定身份；读取服务和超时巡检合成的控制事件不带身份。
公开 SSE 编码始终隐藏内部归档字段。
"""

from typing import Any
from uuid import uuid4

from ui_stream.codec import JsonEventCodec

from services.web.ai_assistant.schemas import UIStreamEvent
from services.web.ai_assistant.schemas.stream import serialize_stream_archive_event


def _new_stream_event(**fields: Any) -> UIStreamEvent:
    return UIStreamEvent(archive_id=uuid4(), **fields)


archive_codec = JsonEventCodec(event_factory=_new_stream_event, serializer=serialize_stream_archive_event)
control_codec = JsonEventCodec(event_factory=UIStreamEvent)
