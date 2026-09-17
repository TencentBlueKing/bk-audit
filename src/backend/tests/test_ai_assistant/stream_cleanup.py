"""按附件 uid SCAN Redis Stream key，避免只删除已跟踪 key 漏掉旧 execution。"""

from collections.abc import Iterable
from uuid import UUID

from services.web.ai_assistant.streaming import STREAM_KEY_PREFIX, RedisLiveStore


def _decode_key(key: bytes | str) -> str:
    return key.decode() if isinstance(key, bytes) else key


def scan_attachment_stream_keys(*, attachment_uids: Iterable[UUID | str]) -> list[str]:
    """扫描当前 Redis 中属于这些附件的 stream 物理 key。"""

    tokens = {str(uid) for uid in attachment_uids}
    if not tokens:
        return []
    redis_store = RedisLiveStore()
    found: list[str] = []
    for key in redis_store._client.scan_iter(match=f"*{STREAM_KEY_PREFIX}*", count=100):
        decoded = _decode_key(key)
        if any(token in decoded for token in tokens):
            found.append(decoded)
    return found


def delete_attachment_stream_keys(*, attachment_uids: Iterable[UUID | str]) -> list[str]:
    """删除这些附件的 stream key，返回删除后仍残留的物理 key。"""

    redis_store = RedisLiveStore()
    found = scan_attachment_stream_keys(attachment_uids=attachment_uids)
    if found:
        redis_store._client.delete(*found)
    return scan_attachment_stream_keys(attachment_uids=attachment_uids)
