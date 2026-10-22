"""无数据库验证审计事件身份、幂等追加及内部字段的容量/公开协议边界。"""

import json
from unittest import mock
from uuid import UUID

from django.test import SimpleTestCase, override_settings
from ui_stream.archive import encoded_archive_bytes, fit_archive_events

from services.web.ai_assistant.constants import StreamArchiveStatus
from services.web.ai_assistant.models import Attachment
from services.web.ai_assistant.schemas import (
    AttachmentStreamConfig,
    UIStreamEvent,
    serialize_stream_event,
)
from services.web.ai_assistant.streaming import (
    AttachmentArchiveStore,
    StreamExecutionBinding,
    UIStreamRuntime,
)
from services.web.ai_assistant.streaming.archive import _encoded_event_bytes
from services.web.ai_assistant.streaming.sse import encode_sse_event


class StreamArchiveIdempotencyTest(SimpleTestCase):
    def setUp(self):
        self.config = AttachmentStreamConfig(
            task_id="synthetic-task",
            execution_id=UUID("00000000-0000-0000-0000-000000000001"),
            redis_key="synthetic-key",
        )
        self.attachment = Attachment(
            id=1,
            task_id="synthetic-task",
            stream_archive=[],
            stream_config=self.config.model_dump(mode="json"),
        )
        self.binding = StreamExecutionBinding(
            attachment_id=1,
            attachment_uid=UUID("00000000-0000-0000-0000-000000000002"),
            business_type="AI_ANALYSIS",
            config=self.config,
        )
        self.store = AttachmentArchiveStore()
        self.runtime = UIStreamRuntime(
            binding=self.binding,
            redis_store=mock.Mock(append=lambda *, event, redis_key: event),
            archive_store=self.store,
            archive_status=StreamArchiveStatus.COMPLETE,
        )

    def append(self, events):
        self.store._apply_events(
            attachment=self.attachment,
            binding=self.binding,
            events=events,
            incoming_status=StreamArchiveStatus.COMPLETE,
            enforce_capacity=True,
        )

    def test_runtime_assigns_stable_internal_identity_without_changing_public_payload(self):
        first = self.runtime.send({"delta": "hello"})
        second = self.runtime.send({"delta": "hello"})

        self.assertIsInstance(getattr(first, "archive_id", None), UUID)
        self.assertNotEqual(first.archive_id, second.archive_id)
        self.assertEqual(first.model_copy(update={"stream_id": "100-0"}).archive_id, first.archive_id)
        self.assertEqual(first.model_dump(mode="json"), {"event": None, "stream_id": None, "data": {"delta": "hello"}})
        self.assertEqual(
            serialize_stream_event(first, include_stream_id=False), b'{"event":null,"data":{"delta":"hello"}}'
        )
        self.assertEqual(encode_sse_event(first), b'data: {"delta":"hello"}\n\n')

    def test_repeated_pending_without_redis_cursor_is_archived_once(self):
        event = self.runtime.send({"delta": "hello"})
        self.assertIsNone(event.stream_id)

        self.append([event])
        self.append([event])

        self.assertEqual([item["data"] for item in self.attachment.stream_archive], [{"delta": "hello"}])

    def test_overlapping_pending_keeps_only_new_identity_in_order(self):
        first = self.runtime.send({"delta": "first"})
        second = self.runtime.send({"delta": "second"})

        self.append([first])
        self.append([first, second, second])

        self.assertEqual(
            [item["data"] for item in self.attachment.stream_archive], [{"delta": "first"}, {"delta": "second"}]
        )

    def test_capacity_statistics_separate_duplicate_and_dropped_events(self):
        first = self.runtime.send({"delta": "first"})
        second = self.runtime.send({"delta": "second"})
        third = self.runtime.send({"delta": "third"})
        self.append([first])

        with override_settings(
            AI_ASSISTANT_STREAM_ARCHIVE_MAX_BYTES=encoded_archive_bytes([first], event_size=_encoded_event_bytes)
        ):
            with self.assertLogs("services.web.ai_assistant.streaming.archive", level="WARNING") as logs:
                self.append([first, second, second, third])

        record = logs.records[0]
        self.assertEqual((record.accepted_count, record.duplicate_count, record.dropped_count), (0, 2, 2))
        self.assertEqual([item["data"] for item in self.attachment.stream_archive], [{"delta": "first"}])
        self.assertEqual(self.attachment.stream_config["archive_status"], StreamArchiveStatus.TRUNCATED)

    def test_distinct_events_with_identical_content_are_not_content_deduplicated(self):
        self.append([self.runtime.send({"delta": "hello"}), self.runtime.send({"delta": "hello"})])

        self.assertEqual(
            [item["data"] for item in self.attachment.stream_archive], [{"delta": "hello"}, {"delta": "hello"}]
        )

    def test_legacy_events_without_identity_are_preserved(self):
        event = UIStreamEvent(stream_id="100-0", data={"delta": "legacy"})
        self.append([event])
        self.append([event])

        self.assertEqual(len(self.attachment.stream_archive), 2)
        self.assertTrue(all("archive_id" not in item for item in self.attachment.stream_archive))

    def test_archive_budget_includes_hidden_identity_and_snapshot_excludes_it(self):
        event = self.runtime.send({"delta": "hello"})
        self.append([event])
        record = self.attachment.stream_archive[0]
        self.assertIn("archive_id", record)
        exact_size = len(json.dumps([record], ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

        self.assertEqual(encoded_archive_bytes([event], event_size=_encoded_event_bytes), exact_size)
        self.assertEqual(
            fit_archive_events(existing=[], incoming=[event], max_bytes=exact_size, event_size=_encoded_event_bytes),
            ([event], 1, False),
        )
        self.assertEqual(
            fit_archive_events(
                existing=[], incoming=[event], max_bytes=exact_size - 1, event_size=_encoded_event_bytes
            ),
            ([], 0, True),
        )
        restored = self.store.snapshot(attachment=self.attachment)
        self.assertEqual(restored.events[0].archive_id, event.archive_id)
        snapshot = restored.model_dump(mode="json")
        self.assertEqual(snapshot["events"], [{"event": None, "stream_id": None, "data": {"delta": "hello"}}])

    @override_settings(AI_ASSISTANT_STREAM_ARCHIVE_MAX_BYTES=90)
    def test_pending_byte_budget_counts_internal_identity(self):
        self.runtime.send({"delta": "hello"})

        # 公开事件不足90字节，加入内部UUID后的持久记录超过90字节。
        self.assertEqual(self.runtime.pending_count, 0)
        self.assertEqual(self.runtime.archive_status, StreamArchiveStatus.TRUNCATED)
