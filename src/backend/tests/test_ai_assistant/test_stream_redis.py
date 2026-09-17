import re
from uuid import uuid4

from django.conf import settings
from django.core.cache import caches
from django_redis import get_redis_connection

from services.web.ai_assistant.constants import PlatformStreamEvent
from services.web.ai_assistant.schemas import UIStreamEvent
from services.web.ai_assistant.streaming import RedisLiveStore, build_stream_key
from tests.base import TestCase


def business_event(text: str) -> UIStreamEvent:
    return UIStreamEvent(data={"content": text})


class RedisLiveStoreTest(TestCase):
    """使用真实 Redis 6 验证 execution 独立尾流、滑动 TTL 与增量读取。"""

    def setUp(self):
        self.store = RedisLiveStore()
        self.client = get_redis_connection("redis")
        self.attachment_uid = uuid4()
        self.logical_keys: set[str] = set()

    def tearDown(self):
        # 测试只清理本次 UUID 生成的 key，禁止 flushdb 影响共享 Redis。
        physical_keys = [self.store.physical_key(logical_key) for logical_key in self.logical_keys]
        if physical_keys:
            self.client.delete(*physical_keys)

    def make_redis_key(self, *, attachment_uid=None) -> str:
        redis_key = build_stream_key(
            attachment_uid=attachment_uid or self.attachment_uid,
            execution_id=uuid4(),
        )
        self.logical_keys.add(redis_key)
        return redis_key

    def test_logical_stream_key_is_namespaced_and_physical_key_uses_cache_prefix(self):
        execution_id = uuid4()

        stream_key = build_stream_key(attachment_uid=self.attachment_uid, execution_id=execution_id)

        self.assertEqual(stream_key, f"ai_assistant:attachment_stream:{self.attachment_uid}:{execution_id}")
        self.assertEqual(self.store.physical_key(stream_key), caches["redis"].make_key(stream_key))
        self.assertNotEqual(self.store.physical_key(stream_key), stream_key)

    def test_append_atomically_adds_entry_and_refreshes_sliding_ttl(self):
        redis_key = self.make_redis_key()

        first = self.store.append(redis_key=redis_key, event=business_event("a"))
        physical_key = self.store.physical_key(redis_key)
        first_ttl = self.client.ttl(physical_key)
        self.client.expire(physical_key, 1)
        second = self.store.append(redis_key=redis_key, event=business_event("b"))

        self.assertIsNotNone(re.fullmatch(r"\d+-\d+", first.stream_id))
        self.assertIsNotNone(re.fullmatch(r"\d+-\d+", second.stream_id))
        self.assertEqual(
            self.store.read(redis_key=redis_key, after_id="0-0", block_ms=1).events,
            [first, second],
        )
        self.assertGreater(first_ttl, 0)
        self.assertLessEqual(first_ttl, settings.AI_ASSISTANT_STREAM_TTL)
        refreshed_ttl = self.client.ttl(physical_key)
        self.assertGreaterEqual(refreshed_ttl, settings.AI_ASSISTANT_STREAM_TTL - 1)
        self.assertLessEqual(refreshed_ttl, settings.AI_ASSISTANT_STREAM_TTL)

    def test_append_without_activation_creates_no_current_pointer_key(self):
        redis_key = self.make_redis_key()
        current_key = f"ai_assistant:attachment_stream:{self.attachment_uid}:current"

        published = self.store.append(redis_key=redis_key, event=business_event("a"))

        self.assertEqual(published.data, {"content": "a"})
        self.assertFalse(self.client.exists(self.store.physical_key(current_key)))

    def test_append_can_write_reset_directly_to_old_execution_stream(self):
        old_redis_key = self.make_redis_key()
        new_redis_key = self.make_redis_key()

        reset = self.store.append(
            redis_key=old_redis_key,
            event=UIStreamEvent(
                event=PlatformStreamEvent.STREAM_RESET,
                data={"reason": "execution_replaced"},
            ),
        )

        self.assertEqual(
            self.store.read(redis_key=old_redis_key, after_id="0-0", block_ms=1).events,
            [reset],
        )
        self.assertEqual(
            self.store.read(redis_key=new_redis_key, after_id="0-0", block_ms=1).events,
            [],
        )

    def test_read_after_cursor_returns_only_newer_entries_for_independent_readers(self):
        redis_key = self.make_redis_key()
        first = self.store.append(redis_key=redis_key, event=business_event("a"))
        second = self.store.append(redis_key=redis_key, event=business_event("b"))

        # 两个独立 reader 都能从 0-0 读到完整事件，证明未使用 Consumer Group。
        for reader in (RedisLiveStore(), RedisLiveStore()):
            self.assertEqual(
                reader.read(redis_key=redis_key, after_id="0-0", block_ms=1).events,
                [first, second],
            )
        self.assertEqual(
            self.store.read(redis_key=redis_key, after_id=first.stream_id, block_ms=1).events,
            [second],
        )
        self.assertEqual(
            self.store.read(redis_key=redis_key, after_id=second.stream_id, block_ms=1).events,
            [],
        )

    def test_read_skips_entries_with_missing_or_invalid_payload(self):
        redis_key = self.make_redis_key()
        valid = self.store.append(redis_key=redis_key, event=business_event("a"))
        physical_stream_key = self.store.physical_key(redis_key)
        self.client.xadd(physical_stream_key, {"other": b"1"})
        self.client.xadd(physical_stream_key, {"payload": b"not-json"})
        self.client.xadd(
            physical_stream_key,
            {"payload": b'{"event":"platform.progress","data":{}}'},
        )
        self.client.xadd(physical_stream_key, {"payload": b'{"unknown":true}'})

        result = self.store.read(redis_key=redis_key, after_id="0-0", block_ms=1)

        self.assertEqual(result.events, [valid])
        # 即使尾部都是脏 entry，也必须返回已扫描到的最新游标，
        # 否则 SSE 下一轮会立即重读同一批脏数据形成忙循环。
        self.assertIsNotNone(result.last_seen_stream_id)
        self.assertNotEqual(result.last_seen_stream_id, valid.stream_id)

    def test_read_skips_non_standard_json_values_and_advances_cursor(self):
        redis_key = self.make_redis_key()
        valid = self.store.append(redis_key=redis_key, event=business_event("a"))
        physical_stream_key = self.store.physical_key(redis_key)
        dirty_payloads = (
            b'{"event":null,"data":NaN}',
            b'{"event":null,"data":Infinity}',
            b'{"event":null,"data":{"nested":[-Infinity]}}',
        )
        dirty_stream_ids = [self.client.xadd(physical_stream_key, {"payload": payload}) for payload in dirty_payloads]

        result = self.store.read(redis_key=redis_key, after_id="0-0", block_ms=1)

        self.assertEqual(result.events, [valid])
        self.assertEqual(result.last_seen_stream_id, self.store._decode(dirty_stream_ids[-1]))

    def test_read_returns_empty_when_stream_key_is_missing(self):
        missing_key = self.make_redis_key()

        result = self.store.read(redis_key=missing_key, after_id="0-0", block_ms=1)
        self.assertEqual(result.events, [])
        self.assertIsNone(result.last_seen_stream_id)

    def test_streams_of_different_attachments_are_isolated(self):
        redis_key = self.make_redis_key()
        other_redis_key = self.make_redis_key(attachment_uid=uuid4())

        published = self.store.append(redis_key=redis_key, event=business_event("mine"))
        other_published = self.store.append(redis_key=other_redis_key, event=business_event("other"))

        self.assertEqual(
            self.store.read(redis_key=redis_key, after_id="0-0", block_ms=1).events,
            [published],
        )
        self.assertEqual(
            self.store.read(redis_key=other_redis_key, after_id="0-0", block_ms=1).events,
            [other_published],
        )
