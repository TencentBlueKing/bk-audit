"""原生 SSE 帧编码：业务事件、命名平台事件与注释 heartbeat。

设计考量
--------
- 严格遵循 W3C Server-Sent Events 规范：event/id/data 行顺序固定，双换行结尾。
- event 行仅在平台事件（如 stream_end/stream_reset）时输出，普通业务事件省略
  event 行，客户端统一走 onmessage 回调。
- id 行仅在事件来自 Redis（有 stream_id）时输出，合成事件不写 id，
  避免客户端 Last-Event-ID 错误续传到不存在的游标。
- heartbeat 使用 SSE 注释行（冒号开头），客户端 EventSource 自动忽略，
  仅用于探测连接存活并阻止中间层（Nginx/LB）超时断开。
"""

from services.web.ai_assistant.schemas import UIStreamEvent
from services.web.ai_assistant.schemas.stream import serialize_stream_data

# SSE 注释行；只用于保持连接活跃，客户端 EventSource 会自动忽略。
SSE_HEARTBEAT = b": heartbeat\n\n"


def encode_sse_event(event: UIStreamEvent) -> bytes:
    """按可选 event、可选 id、必选 data 的顺序编码原生 SSE 帧。"""

    payload = serialize_stream_data(event.data).decode("utf-8")
    event_line = f"event: {event.event}\n" if event.event else ""
    # 只有来自 Redis 的事件才有游标；合成事件不写 id，避免客户端错误续传。
    id_line = f"id: {event.stream_id}\n" if event.stream_id else ""
    return f"{event_line}{id_line}data: {payload}\n\n".encode("utf-8")


def encode_sse_heartbeat() -> bytes:
    """返回心跳帧，用于在无新事件时探测连接并阻止中间层超时断开。"""

    return SSE_HEARTBEAT
