"""Redis Stream 实时尾流：低延迟事件推送与断线续传支持。

设计思路
--------
- 每次 execution 独占一个 Redis Stream key（按 attachment_uid + execution_id 隔离），
  避免多次执行的事件混杂，也让旧流自然过期而无需显式清理。
- 追加事件与刷新 TTL 通过 Lua 脚本原子完成，避免 XADD 成功但 EXPIRE 失败导致
  Stream 永不过期占用内存。
- 滑动 TTL 设计：只要有新事件写入就续期，执行结束后 Stream 自然过期。
  前端断线重连时若 Stream 已过期，回退到 MySQL 归档快照恢复。
- 脏 entry 容错：XREAD 解析失败的 entry 跳过但推进游标，不阻塞后续有效事件。

与 Archive 层的关系
-------------------
Redis 是“尽力而为”的实时通道，Archive 是 MySQL 持久快照通道。
Redis 故障时 Runtime 标记 DEGRADED 但继续归档；checkpoint 故障时尽量保留
进程内缓冲等待后续重试，已经完成的 Redis 推送不受回滚影响。
"""

import logging
from typing import Any
from uuid import UUID

from django.conf import settings
from django.core.cache import caches
from django_redis import get_redis_connection
from pydantic import ValidationError

from services.web.ai_assistant.exceptions import InvalidStreamEvent
from services.web.ai_assistant.schemas import UIStreamEvent, serialize_stream_event
from services.web.ai_assistant.streaming.types import StreamReadResult

logger = logging.getLogger(__name__)

# 逻辑 key 前缀；物理 key 仍通过 Django cache make_key() 继承 REDIS_KEY_PREFIX。
STREAM_KEY_PREFIX = "ai_assistant:attachment_stream"
# Redis Stream entry 中承载事件信封的固定字段名。
PAYLOAD_FIELD = "payload"
# 单次 XREAD 拉取的最大 entry 数，避免一次返回超大批量事件。
READ_COUNT = 100

# ── Lua 原子脚本 ──
# 设计意图：XADD 与 EXPIRE 必须原子执行，否则 XADD 成功但 EXPIRE 失败会导致
# Stream 永不过期、持续占用 Redis 内存。Lua 在 Redis 单线程中执行，无竞争。
_APPEND_SCRIPT = """
local stream_id = redis.call('XADD', KEYS[1], '*', ARGV[1], ARGV[2])
redis.call('EXPIRE', KEYS[1], ARGV[3])
return stream_id
"""


def build_stream_key(*, attachment_uid: UUID, execution_id: UUID) -> str:
    """单次执行独占的事件流逻辑 key。"""

    return f"{STREAM_KEY_PREFIX}:{attachment_uid}:{execution_id}"


class RedisLiveStore:
    """Attachment UI 事件的 Redis 实时尾流。

    设计要点：
    - 复用项目既有 Django cache 连接池与 key 前缀，无额外运维负担。
    - 每次 append 通过 Lua 原子刷新滑动 TTL，执行结束后 Stream 自然过期。
    - read 对脏 entry 容错：解析失败跳过但推进游标，不阻塞后续有效事件。
    """

    def __init__(self):
        self._client = get_redis_connection("redis")
        self._cache = caches["redis"]
        self._append_script = self._client.register_script(_APPEND_SCRIPT)

    @property
    def ttl(self) -> int:
        """execution Stream 的滑动 TTL；每次追加都会刷新。"""

        return settings.AI_ASSISTANT_STREAM_TTL

    def physical_key(self, logical_key: str) -> str:
        """通过 Django cache make_key() 继承 REDIS_KEY_PREFIX 与版本号。"""

        return self._cache.make_key(logical_key)

    def append(self, *, redis_key: str, event: UIStreamEvent) -> UIStreamEvent:
        """追加事件并刷新当前 execution 流的滑动 TTL。"""

        payload = serialize_stream_event(event, include_stream_id=False)
        stream_id = self._append_script(
            keys=[self.physical_key(redis_key)],
            args=[PAYLOAD_FIELD, payload, self.ttl],
        )
        return event.model_copy(update={"stream_id": self._decode(stream_id)})

    def read(self, *, redis_key: str, after_id: str, block_ms: int) -> StreamReadResult:
        """按 Redis 游标读取增量；脏 entry 不返回，但仍推进扫描游标。"""

        physical_stream_key = self.physical_key(redis_key)
        read_kwargs: dict[str, Any] = {"count": READ_COUNT}
        if block_ms > 0:
            read_kwargs["block"] = block_ms
        entries = self._client.xread({physical_stream_key: after_id}, **read_kwargs)
        events: list[UIStreamEvent] = []
        last_seen_stream_id: str | None = None
        for _, stream_entries in entries or []:
            for entry_id, fields in stream_entries:
                last_seen_stream_id = self._decode(entry_id)
                event = self._decode_entry(redis_key=redis_key, entry_id=entry_id, fields=fields)
                if event is not None:
                    events.append(event)
        return StreamReadResult(events=events, last_seen_stream_id=last_seen_stream_id)

    def _decode_entry(self, *, redis_key: str, entry_id: Any, fields: dict) -> UIStreamEvent | None:
        """严格解析 entry；脏数据不阻塞后续事件，也不写入日志正文。"""

        stream_id = self._decode(entry_id)
        payload = fields.get(PAYLOAD_FIELD.encode("utf-8")) or fields.get(PAYLOAD_FIELD)
        if payload is None:
            logger.warning(
                "AI 助手附件流事件缺少 payload 字段",
                extra={"redis_key": redis_key, "stream_id": stream_id},
            )
            return None
        try:
            event = UIStreamEvent.model_validate_json(payload)
            # Pydantic JSON 会接受 NaN/Infinity；再次使用严格编码器验证标准 JSON 兼容性。
            serialize_stream_event(event, include_stream_id=False)
        except (ValidationError, InvalidStreamEvent):
            logger.warning(
                "AI 助手附件流事件解析失败",
                extra={"redis_key": redis_key, "stream_id": stream_id},
            )
            return None
        return event.model_copy(update={"stream_id": stream_id})

    @staticmethod
    def _decode(value: Any) -> str:
        """统一把 Redis 返回的 bytes 解码为 str。"""

        return value.decode("utf-8") if isinstance(value, bytes) else str(value)
