import json
from unittest import mock
from uuid import UUID, uuid4

import yaml
from django import db
from django.core.signals import request_finished
from django.db import close_old_connections
from django.test import override_settings
from drf_spectacular.views import SpectacularAPIView
from redis.exceptions import RedisError
from rest_framework.test import APIRequestFactory

from services.web.ai_assistant.constants import (
    AttachmentType,
    ExecutionStatus,
    MessageType,
    PlatformStreamEvent,
    StreamArchiveStatus,
)
from services.web.ai_assistant.exceptions import (
    AttachmentNotFound,
    InvalidStreamCursor,
    StreamNotEnabled,
)
from services.web.ai_assistant.models import Attachment, Conversation, Message
from services.web.ai_assistant.resources.stream import (
    GetAttachmentStream,
    GetAttachmentStreamSnapshot,
)
from services.web.ai_assistant.schemas import AttachmentStreamConfig, UIStreamEvent
from services.web.ai_assistant.serializers.stream import (
    AttachmentStreamRequestSerializer,
    AttachmentStreamSnapshotResponseSerializer,
)
from services.web.ai_assistant.services.attachment_stream import AttachmentStreamService
from services.web.ai_assistant.streaming import StreamReadResult, build_stream_key
from services.web.ai_assistant.streaming.sse import (
    encode_sse_event,
    encode_sse_heartbeat,
)
from services.web.ai_assistant.views import AttachmentsViewSet
from tests.base import TestCase
from tests.test_ai_assistant.handlers import (
    AttachmentHandlerRegistryMixin,
    EchoAttachmentStreamHandler,
    use_attachment_handler,
)


def business_event(text: str, *, stream_id: str | None = None) -> UIStreamEvent:
    return UIStreamEvent(stream_id=stream_id, data={"content": text})


def platform_event(event: PlatformStreamEvent, *, stream_id: str | None = None) -> UIStreamEvent:
    return UIStreamEvent(event=event, stream_id=stream_id, data={})


class StreamRoundsExhausted(AssertionError):
    """预设轮次用尽仍继续读取；用于把无限循环转成明确失败。"""


class FakeRedisLiveStore:
    """按调用轮次返回预设事件，避免真实 XREAD 阻塞测试。"""

    def __init__(self, rounds: list[list[UIStreamEvent] | StreamReadResult | Exception]):
        self._rounds = list(rounds)
        self.calls: list[tuple[str, str]] = []
        self.block_ms_calls: list[int] = []

    def read(self, *, redis_key: str, after_id: str, block_ms: int) -> StreamReadResult:
        self.calls.append((redis_key, after_id))
        self.block_ms_calls.append(block_ms)
        if not self._rounds:
            # 生产循环会阻塞在 XREAD；测试必须显式失败而不是挂住。
            raise StreamRoundsExhausted(f"未预期的第 {len(self.calls)} 次读取")
        current = self._rounds.pop(0)
        if isinstance(current, Exception):
            raise current
        if isinstance(current, StreamReadResult):
            return current
        last_seen_stream_id = next((event.stream_id for event in reversed(current) if event.stream_id), None)
        return StreamReadResult(events=current, last_seen_stream_id=last_seen_stream_id)


class SSEEncodingTest(TestCase):
    """SSE 使用浏览器原生字段，data 只承载原始业务 JSON。"""

    def test_business_event_uses_default_sse_message(self):
        event = UIStreamEvent(stream_id="1-0", data={"delta": "内容"})

        self.assertEqual(
            encode_sse_event(event),
            b'id: 1-0\ndata: {"delta":"\xe5\x86\x85\xe5\xae\xb9"}\n\n',
        )

    def test_platform_event_uses_named_sse_event(self):
        event = UIStreamEvent(
            event=PlatformStreamEvent.STREAM_END,
            stream_id="2-0",
            data={"status": ExecutionStatus.SUCCESS},
        )

        self.assertEqual(
            encode_sse_event(event),
            b'event: platform.stream_end\nid: 2-0\ndata: {"status":"SUCCESS"}\n\n',
        )

    def test_encode_event_without_cursor_omits_id_line(self):
        chunk = encode_sse_event(business_event("A"))

        self.assertFalse(chunk.startswith(b"id:"))
        self.assertTrue(chunk.startswith(b"data: "))
        self.assertEqual(json.loads(chunk.split(b"data: ", 1)[1].strip()), {"content": "A"})

    def test_encode_event_keeps_payload_single_line_for_multiline_content(self):
        chunk = encode_sse_event(business_event("第一行\n第二行", stream_id="1-0"))

        # data 必须是单行，否则 SSE 会把换行解析成多个 data 段。
        self.assertEqual(chunk.count(b"\n"), 3)
        payload = json.loads(chunk.split(b"data: ", 1)[1].strip())
        self.assertEqual(payload, {"content": "第一行\n第二行"})

    def test_encode_heartbeat_is_comment_line(self):
        self.assertEqual(encode_sse_heartbeat(), b": heartbeat\n\n")


class StreamSerializerTest(TestCase):
    def test_request_serializer_validates_cursor_format(self):
        execution_id = uuid4()
        serializer = AttachmentStreamRequestSerializer(
            data={
                "attachment_uid": str(uuid4()),
                "execution_id": str(execution_id),
                "last_stream_id": "1724140800000-0",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["execution_id"], execution_id)
        self.assertEqual(serializer.validated_data["last_stream_id"], "1724140800000-0")

    def test_request_serializer_defers_cursor_validation_to_selected_source(self):
        for invalid_cursor in ("abc", "1-", "-0", "1_0", "1-0-0", ""):
            with self.subTest(invalid_cursor=invalid_cursor):
                serializer = AttachmentStreamRequestSerializer(
                    data={
                        "attachment_uid": str(uuid4()),
                        "execution_id": str(uuid4()),
                        "last_stream_id": invalid_cursor,
                    }
                )
                self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_request_serializer_allows_missing_cursor(self):
        serializer = AttachmentStreamRequestSerializer(
            data={"attachment_uid": str(uuid4()), "execution_id": str(uuid4())}
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIsNone(serializer.validated_data.get("last_stream_id"))

    def test_request_serializer_requires_execution_id(self):
        serializer = AttachmentStreamRequestSerializer(data={"attachment_uid": str(uuid4())})

        self.assertFalse(serializer.is_valid())
        self.assertIn("execution_id", serializer.errors)

    def test_all_stream_serializer_fields_document_help_text(self):
        for serializer_class in (
            AttachmentStreamRequestSerializer,
            AttachmentStreamSnapshotResponseSerializer,
        ):
            with self.subTest(serializer=serializer_class.__name__):
                for field_name, field in serializer_class().fields.items():
                    self.assertTrue(field.help_text, f"{serializer_class.__name__}.{field_name} 缺少 help_text")

    def test_snapshot_response_serializer_exposes_only_public_fields(self):
        snapshot_payload = {
            "events": [business_event("A", stream_id="1-0").model_dump(mode="json")],
            "execution_id": str(uuid4()),
            "latest_stream_id": "1-0",
            "archive_status": StreamArchiveStatus.COMPLETE,
        }

        data = AttachmentStreamSnapshotResponseSerializer(snapshot_payload).data

        self.assertEqual(set(data.keys()), {"events", "execution_id", "latest_stream_id", "archive_status"})
        self.assertEqual(set(data["events"][0].keys()), {"event", "stream_id", "data"})
        self.assertEqual(data["events"][0]["data"], {"content": "A"})


class AttachmentStreamServiceTestCase(AttachmentHandlerRegistryMixin, TestCase):
    def setUp(self):
        self.user = "alice"
        use_attachment_handler(self, EchoAttachmentStreamHandler())
        self.conversation = Conversation.objects.create(created_by=self.user, updated_by=self.user)
        self.source_message = Message.objects.create(
            conversation=self.conversation,
            message_type=MessageType.LOG_SEARCH,
            status=ExecutionStatus.SUCCESS,
            task_id="source-task",
            input_data={"text": "query"},
            context_data={"prefix": "source"},
            output_data={"content": "source"},
            created_by=self.user,
            updated_by=self.user,
        )
        self.attachment = self.create_attachment()

    def create_attachment(
        self,
        *,
        status: str = ExecutionStatus.PROCESSING,
        is_stream: bool = True,
        created_by: str | None = None,
        stream_config: dict | None = None,
        stream_archive: list | None = None,
    ) -> Attachment:
        owner = created_by or self.user
        return Attachment.objects.create(
            source_message=self.source_message,
            attachment_type=AttachmentType.AI_ANALYSIS,
            title="AI 分析",
            status=status,
            task_id="task-current",
            input_data={"text": "hello"},
            context_data={"prefix": "async"},
            output_data=None,
            is_stream=is_stream,
            stream_config=stream_config or {},
            stream_archive=stream_archive or [],
            created_by=owner,
            updated_by=owner,
        )

    def make_config(self, attachment: Attachment | None = None) -> AttachmentStreamConfig:
        attachment = attachment or self.attachment
        execution_id = uuid4()
        return AttachmentStreamConfig(
            task_id=attachment.task_id,
            execution_id=execution_id,
            redis_key=build_stream_key(attachment_uid=attachment.uid, execution_id=execution_id),
        )

    def set_config(self, config: AttachmentStreamConfig, *, attachment: Attachment | None = None) -> None:
        attachment = attachment or self.attachment
        Attachment.objects.filter(id=attachment.id).update(stream_config=config.model_dump(mode="json"))

    def service(self, rounds: list | None = None) -> tuple[AttachmentStreamService, FakeRedisLiveStore]:
        redis_store = FakeRedisLiveStore(rounds or [])
        return AttachmentStreamService(user=self.user, redis_store=redis_store), redis_store


class AttachmentStreamSnapshotTest(AttachmentStreamServiceTestCase):
    def test_get_snapshot_returns_persisted_events_and_cursor(self):
        config = self.make_config()
        self.set_config(config)
        Attachment.objects.filter(id=self.attachment.id).update(
            stream_archive=[
                business_event("A", stream_id="1-0").model_dump(mode="json"),
                business_event("B", stream_id="2-0").model_dump(mode="json"),
            ]
        )
        service, _ = self.service()

        snapshot = service.get_snapshot(attachment_uid=str(self.attachment.uid))

        self.assertEqual([event.data["content"] for event in snapshot.events], ["A", "B"])
        self.assertEqual(snapshot.execution_id, config.execution_id)
        self.assertEqual(snapshot.latest_stream_id, "2-0")
        self.assertEqual(snapshot.archive_status, StreamArchiveStatus.COMPLETE)

    def test_get_snapshot_of_empty_archive_is_valid(self):
        service, _ = self.service()

        snapshot = service.get_snapshot(attachment_uid=str(self.attachment.uid))

        self.assertEqual(snapshot.events, [])
        self.assertIsNone(snapshot.execution_id)
        self.assertIsNone(snapshot.latest_stream_id)
        self.assertEqual(snapshot.archive_status, StreamArchiveStatus.COMPLETE)

    def test_stream_attachment_query_defers_large_fields_by_usage(self):
        service = AttachmentStreamService(user=self.user)

        stream_attachment = service._attachment_service.get_for_stream(
            attachment_uid=str(self.attachment.uid),
            include_archive=False,
        )
        snapshot_attachment = service._attachment_service.get_for_stream(
            attachment_uid=str(self.attachment.uid),
            include_archive=True,
        )

        self.assertIn("stream_archive", stream_attachment.get_deferred_fields())
        self.assertNotIn("stream_archive", snapshot_attachment.get_deferred_fields())
        for field_name in ("input_data", "context_data", "output_data"):
            self.assertIn(field_name, stream_attachment.get_deferred_fields())
            self.assertIn(field_name, snapshot_attachment.get_deferred_fields())

    def test_get_snapshot_rejects_non_stream_attachment(self):
        attachment = self.create_attachment(is_stream=False, status=ExecutionStatus.SUCCESS)
        service, _ = self.service()

        with self.assertRaises(StreamNotEnabled):
            service.get_snapshot(attachment_uid=str(attachment.uid))

    def test_get_snapshot_rejects_other_user_and_missing_attachment(self):
        other_attachment = self.create_attachment(created_by="bob")
        service, _ = self.service()

        for case_name, attachment_uid in (
            ("other_user", str(other_attachment.uid)),
            ("missing", str(uuid4())),
        ):
            with self.subTest(case=case_name):
                with self.assertRaises(AttachmentNotFound):
                    service.get_snapshot(attachment_uid=attachment_uid)

    def test_get_snapshot_rejects_deleted_conversation(self):
        self.conversation.delete()
        service, _ = self.service()

        with self.assertRaises(AttachmentNotFound):
            service.get_snapshot(attachment_uid=str(self.attachment.uid))


class AttachmentStreamIterationTest(AttachmentStreamServiceTestCase):
    def test_iter_events_ends_when_config_is_missing_or_belongs_to_another_task(self):
        previous = self.make_config().model_dump(mode="json")
        previous["task_id"] = "task-before-manual-retry"
        previous["archive_status"] = StreamArchiveStatus.DEGRADED
        for case_name, stream_config in (("missing", {}), ("stale", previous)):
            with self.subTest(case=case_name):
                Attachment.objects.filter(id=self.attachment.id).update(stream_config=stream_config)
                service, redis_store = self.service()

                events = list(service.iter_events(attachment_uid=str(self.attachment.uid), last_stream_id="99-0"))

                self.assertEqual(events, [])
                self.assertEqual(redis_store.calls, [])

    def test_iter_events_reads_from_zero_cursor_by_default(self):
        config = self.make_config()
        self.set_config(config)
        first = business_event("A", stream_id="1-0")
        service, redis_store = self.service(
            [[first], [platform_event(PlatformStreamEvent.STREAM_END, stream_id="2-0")]]
        )

        events = list(service.iter_events(attachment_uid=str(self.attachment.uid), last_stream_id=None))

        self.assertEqual(redis_store.calls[0], (config.redis_key, "0-0"))
        self.assertEqual(events[0], first)
        self.assertEqual(events[-1].event, PlatformStreamEvent.STREAM_END)

    def test_iter_events_resumes_after_provided_cursor(self):
        config = self.make_config()
        self.set_config(config)
        service, redis_store = self.service([[platform_event(PlatformStreamEvent.STREAM_END)]])

        list(
            service.iter_events(
                attachment_uid=str(self.attachment.uid),
                execution_id=config.execution_id,
                last_stream_id="5-0",
            )
        )

        self.assertEqual(redis_store.calls[0], (config.redis_key, "5-0"))

    def test_iter_events_resets_when_snapshot_execution_has_been_replaced(self):
        config = self.make_config()
        self.set_config(config)
        service, redis_store = self.service()

        events = list(
            service.iter_events(
                attachment_uid=str(self.attachment.uid),
                execution_id=uuid4(),
                last_stream_id="99-0",
            )
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event, PlatformStreamEvent.STREAM_RESET)
        self.assertEqual(events[0].data, {"reason": "execution_replaced"})
        self.assertEqual(redis_store.calls, [])

    def test_iter_events_advances_cursor_across_rounds(self):
        config = self.make_config()
        self.set_config(config)
        service, redis_store = self.service(
            [
                [business_event("A", stream_id="1-0"), business_event("B", stream_id="2-0")],
                [platform_event(PlatformStreamEvent.STREAM_END, stream_id="3-0")],
            ]
        )

        list(service.iter_events(attachment_uid=str(self.attachment.uid), last_stream_id=None))

        self.assertEqual([call[1] for call in redis_store.calls], ["0-0", "2-0"])

    def test_iter_events_advances_cursor_when_redis_batch_contains_only_dirty_entries(self):
        config = self.make_config()
        self.set_config(config)
        service, redis_store = self.service(
            [
                StreamReadResult(events=[], last_seen_stream_id="4-0"),
                [platform_event(PlatformStreamEvent.STREAM_END, stream_id="5-0")],
            ]
        )

        events = list(service.iter_events(attachment_uid=str(self.attachment.uid), last_stream_id=None))

        self.assertEqual([call[1] for call in redis_store.calls], ["0-0", "4-0"])
        self.assertIsNone(events[0])
        self.assertEqual(events[-1].event, PlatformStreamEvent.STREAM_END)

    @override_settings(AI_ASSISTANT_STREAM_IDLE_TIMEOUT=300)
    @mock.patch("services.web.ai_assistant.services.attachment_stream.time.monotonic")
    def test_dirty_redis_entry_does_not_refresh_idle_timeout(self, monotonic):
        self.set_config(self.make_config())
        monotonic.side_effect = [0, 15, 300]
        service, redis_store = self.service(
            [
                StreamReadResult(events=[], last_seen_stream_id="4-0"),
                StreamReadResult(events=[], last_seen_stream_id="5-0"),
            ]
        )

        events = list(service.iter_events(attachment_uid=str(self.attachment.uid), last_stream_id=None))

        self.assertEqual(events, [None])
        self.assertEqual([call[1] for call in redis_store.calls], ["0-0", "4-0"])

    @override_settings(AI_ASSISTANT_STREAM_IDLE_TIMEOUT=300)
    @mock.patch("services.web.ai_assistant.services.attachment_stream.time.monotonic")
    def test_heartbeat_does_not_refresh_idle_timeout(self, monotonic):
        self.set_config(self.make_config())
        monotonic.side_effect = [0, 15, 300]
        service, redis_store = self.service([[], []])

        events = list(service.iter_events(attachment_uid=str(self.attachment.uid), last_stream_id=None))

        self.assertEqual(events, [None])
        self.assertTrue(all(block_ms == 15_000 for block_ms in redis_store.block_ms_calls))

    @override_settings(AI_ASSISTANT_STREAM_IDLE_TIMEOUT=300)
    @mock.patch("services.web.ai_assistant.services.attachment_stream.time.monotonic")
    def test_business_event_refreshes_idle_timeout_window(self, monotonic):
        self.set_config(self.make_config())
        event = business_event("A", stream_id="1-0")
        monotonic.side_effect = [0, 250, 549, 550]
        service, _ = self.service([[event], [], []])

        events = list(service.iter_events(attachment_uid=str(self.attachment.uid), last_stream_id=None))

        self.assertEqual(events, [event, None])

    def test_iter_events_rejects_malformed_cursor(self):
        self.set_config(self.make_config())
        service, _ = self.service()

        with self.assertRaises(InvalidStreamCursor):
            list(service.iter_events(attachment_uid=str(self.attachment.uid), last_stream_id="bad"))

    def test_iter_events_heartbeats_when_no_new_events(self):
        self.set_config(self.make_config())
        service, _ = self.service([[], [], [platform_event(PlatformStreamEvent.STREAM_END)]])

        events = list(service.iter_events(attachment_uid=str(self.attachment.uid), last_stream_id=None))

        self.assertEqual(events[:2], [None, None])
        self.assertEqual(events[2].event, PlatformStreamEvent.STREAM_END)

    def test_iter_events_closes_after_terminal_event(self):
        self.set_config(self.make_config())
        service, _ = self.service([[platform_event(PlatformStreamEvent.STREAM_END)], [business_event("late")]])

        events = list(service.iter_events(attachment_uid=str(self.attachment.uid), last_stream_id=None))

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event, PlatformStreamEvent.STREAM_END)

    def test_iter_events_closes_after_reset_event(self):
        self.set_config(self.make_config())
        service, _ = self.service([[platform_event(PlatformStreamEvent.STREAM_RESET)], [business_event("late")]])

        events = list(service.iter_events(attachment_uid=str(self.attachment.uid), last_stream_id=None))

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event, PlatformStreamEvent.STREAM_RESET)

    def test_iter_events_yields_events_before_terminal_in_same_batch(self):
        self.set_config(self.make_config())
        service, _ = self.service(
            [
                [
                    business_event("A", stream_id="1-0"),
                    platform_event(PlatformStreamEvent.STREAM_END, stream_id="2-0"),
                    business_event("after terminal", stream_id="3-0"),
                ]
            ]
        )

        events = list(service.iter_events(attachment_uid=str(self.attachment.uid), last_stream_id=None))

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].data, {"content": "A"})
        self.assertEqual(events[1].event, PlatformStreamEvent.STREAM_END)

    def test_iter_events_returns_initial_terminal_end_without_redis_config(self):
        cases = {
            ExecutionStatus.SUCCESS: PlatformStreamEvent.STREAM_END,
            ExecutionStatus.FAILED: PlatformStreamEvent.STREAM_END,
        }
        for status, expected_event in cases.items():
            with self.subTest(status=status):
                attachment = self.create_attachment()
                Attachment.objects.filter(id=attachment.id).update(status=status)
                service, redis_store = self.service()

                events = list(service.iter_events(attachment_uid=str(attachment.uid), last_stream_id=None))

                self.assertEqual(len(events), 1)
                self.assertEqual(events[0].event, expected_event)
                self.assertEqual(events[0].data, {"status": status})
                # 合成事件不来自 Redis，因此没有游标。
                self.assertIsNone(events[0].stream_id)
                self.assertEqual(redis_store.calls, [])

    def test_iter_events_queries_once_and_releases_connection_before_first_redis_read(self):
        config = self.make_config()
        self.set_config(config)
        service, redis_store = self.service([[platform_event(PlatformStreamEvent.STREAM_END)]])

        connection = mock.Mock(in_atomic_block=False)
        with mock.patch.object(db.transaction, "get_connection", return_value=connection):
            with mock.patch.object(db, "close_old_connections") as close_old_connections:
                with self.assertNumQueries(1):
                    iterator = service.iter_events(attachment_uid=str(self.attachment.uid), last_stream_id=None)

                close_old_connections.assert_called_once_with()
                self.assertEqual(redis_store.calls, [])
                events = list(iterator)

        self.assertEqual(events[0].event, PlatformStreamEvent.STREAM_END)

    def test_iter_events_does_not_release_connection_without_long_lived_redis_stream(self):
        for case_name, status, stream_config in (
            ("terminal", ExecutionStatus.SUCCESS, {}),
            ("missing_config", ExecutionStatus.PROCESSING, {}),
        ):
            with self.subTest(case=case_name):
                Attachment.objects.filter(id=self.attachment.id).update(status=status, stream_config=stream_config)
                service, redis_store = self.service()

                with mock.patch.object(db, "close_old_connections") as close_old_connections:
                    list(service.iter_events(attachment_uid=str(self.attachment.uid), last_stream_id=None))

                close_old_connections.assert_not_called()
                self.assertEqual(redis_store.calls, [])

    def test_iter_events_closes_on_redis_error_without_touching_attachment(self):
        self.set_config(self.make_config())
        service, _ = self.service([RedisError("redis down")])

        events = list(service.iter_events(attachment_uid=str(self.attachment.uid), last_stream_id=None))

        self.assertEqual(events, [])
        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.status, ExecutionStatus.PROCESSING)

    def test_iter_events_validates_visibility_before_iteration(self):
        other_attachment = self.create_attachment(created_by="bob")
        service, _ = self.service()

        with self.assertRaises(AttachmentNotFound):
            list(service.iter_events(attachment_uid=str(other_attachment.uid), last_stream_id=None))

    def test_iter_events_rejects_non_stream_attachment(self):
        attachment = self.create_attachment(is_stream=False, status=ExecutionStatus.SUCCESS)
        service, _ = self.service()

        with self.assertRaises(StreamNotEnabled):
            list(service.iter_events(attachment_uid=str(attachment.uid), last_stream_id=None))


@mock.patch("services.web.ai_assistant.resources.stream.get_request_username", return_value="alice")
class StreamResourceTest(AttachmentStreamServiceTestCase):
    def test_snapshot_resource_returns_json_serializable_payload(self, _username):
        config = self.make_config()
        self.set_config(config)
        Attachment.objects.filter(id=self.attachment.id).update(
            stream_archive=[business_event("A", stream_id="1-0").model_dump(mode="json")]
        )

        response = GetAttachmentStreamSnapshot()(attachment_uid=str(self.attachment.uid))

        self.assertEqual(
            response,
            {
                "events": [
                    {
                        "event": None,
                        "stream_id": "1-0",
                        "data": {"content": "A"},
                    }
                ],
                "execution_id": config.execution_id,
                "latest_stream_id": "1-0",
                "archive_status": StreamArchiveStatus.COMPLETE,
            },
        )

    def test_stream_resource_prefers_last_event_id_header_over_query(self, _username):
        config = self.make_config()
        self.set_config(config)
        request = APIRequestFactory().get("/stream/", HTTP_LAST_EVENT_ID="2-0")

        with mock.patch.object(AttachmentStreamService, "iter_events", return_value=iter(())) as iter_events:
            GetAttachmentStream()(
                attachment_uid=str(self.attachment.uid),
                execution_id=str(config.execution_id),
                last_stream_id="1-0",
                _request=request,
            )

        self.assertEqual(iter_events.call_args.kwargs["last_stream_id"], "2-0")
        self.assertEqual(iter_events.call_args.kwargs["execution_id"], config.execution_id)

    def test_stream_resource_uses_valid_header_when_query_cursor_is_invalid(self, _username):
        config = self.make_config()
        self.set_config(config)
        request = APIRequestFactory().get("/stream/", HTTP_LAST_EVENT_ID="2-0")

        with mock.patch.object(AttachmentStreamService, "iter_events", return_value=iter(())) as iter_events:
            GetAttachmentStream()(
                attachment_uid=str(self.attachment.uid),
                execution_id=str(config.execution_id),
                last_stream_id="not-a-cursor",
                _request=request,
            )

        self.assertEqual(iter_events.call_args.kwargs["last_stream_id"], "2-0")

    def test_stream_resource_rejects_invalid_header_even_when_query_cursor_is_valid(self, _username):
        config = self.make_config()
        self.set_config(config)
        request = APIRequestFactory().get("/stream/", HTTP_LAST_EVENT_ID="not-a-cursor")

        with self.assertRaises(InvalidStreamCursor):
            GetAttachmentStream()(
                attachment_uid=str(self.attachment.uid),
                execution_id=str(config.execution_id),
                last_stream_id="2-0",
                _request=request,
            )

    def test_stream_resource_falls_back_to_query_cursor(self, _username):
        config = self.make_config()
        self.set_config(config)
        request = APIRequestFactory().get("/stream/")

        with mock.patch.object(AttachmentStreamService, "iter_events", return_value=iter(())) as iter_events:
            GetAttachmentStream()(
                attachment_uid=str(self.attachment.uid),
                execution_id=str(config.execution_id),
                last_stream_id="1-0",
                _request=request,
            )

        self.assertEqual(iter_events.call_args.kwargs["last_stream_id"], "1-0")

    def test_stream_resource_ignores_blank_header(self, _username):
        config = self.make_config()
        self.set_config(config)
        request = APIRequestFactory().get("/stream/", HTTP_LAST_EVENT_ID="   ")

        with mock.patch.object(AttachmentStreamService, "iter_events", return_value=iter(())) as iter_events:
            GetAttachmentStream()(
                attachment_uid=str(self.attachment.uid),
                execution_id=str(config.execution_id),
                last_stream_id="1-0",
                _request=request,
            )

        self.assertEqual(iter_events.call_args.kwargs["last_stream_id"], "1-0")

    def test_stream_resource_returns_event_stream_response_with_no_buffering(self, _username):
        config = self.make_config()
        self.set_config(config)
        request = APIRequestFactory().get("/stream/")
        events = iter([business_event("A", stream_id="1-0"), None])

        with mock.patch.object(AttachmentStreamService, "iter_events", return_value=events):
            response = GetAttachmentStream()(
                attachment_uid=str(self.attachment.uid),
                execution_id=str(config.execution_id),
                _request=request,
            )

        self.assertEqual(response["Content-Type"], "text/event-stream")
        self.assertEqual(response["Cache-Control"], "no-cache")
        self.assertEqual(response["X-Accel-Buffering"], "no")
        self.assertTrue(response.streaming)
        chunks = list(response.streaming_content)
        self.assertTrue(chunks[0].startswith(b"id: 1-0\n"))
        self.assertEqual(chunks[1], encode_sse_heartbeat())

    def test_stream_resource_closes_inner_iterator_when_client_stops_consuming(self, _username):
        config = self.make_config()
        self.set_config(config)
        closed = []

        def events():
            try:
                yield business_event("A", stream_id="1-0")
                yield business_event("B", stream_id="2-0")
            finally:
                closed.append(True)

        with mock.patch.object(AttachmentStreamService, "iter_events", return_value=events()):
            response = GetAttachmentStream()(
                attachment_uid=str(self.attachment.uid),
                execution_id=str(config.execution_id),
                _request=APIRequestFactory().get("/stream/"),
            )

        next(iter(response.streaming_content))
        # TestCase 用外层事务隔离数据；避免 request_finished 关闭测试连接而污染后续用例。
        request_finished.disconnect(close_old_connections)
        try:
            response.close()
        finally:
            request_finished.connect(close_old_connections)

        self.assertEqual(closed, [True])

    def test_stream_resource_rejects_malformed_cursor_before_streaming(self, _username):
        config = self.make_config()
        self.set_config(config)
        request = APIRequestFactory().get("/stream/", HTTP_LAST_EVENT_ID="not-a-cursor")

        # 非法游标必须在建立流之前失败，让前端拿到明确的业务错误码。
        with self.assertRaises(InvalidStreamCursor):
            GetAttachmentStream()(
                attachment_uid=str(self.attachment.uid),
                execution_id=str(config.execution_id),
                _request=request,
            )

    @override_settings(ROOT_URLCONF="urls")
    def test_stream_view_accepts_event_stream_content_negotiation(self, _username):
        """SSE 请求必须通过 DRF 内容协商后进入资源执行链路。"""

        config = self.make_config()
        self.set_config(config)
        request = APIRequestFactory().get(
            f"/api/v1/ai_assistant/attachments/{self.attachment.uid}/stream/" f"?execution_id={config.execution_id}",
            HTTP_ACCEPT="text/event-stream",
        )
        request.user = mock.Mock(is_authenticated=True, username="alice")

        with mock.patch.object(AttachmentStreamService, "iter_events", return_value=iter(())):
            response = AttachmentsViewSet.as_view({"get": "stream"})(
                request,
                attachment_uid=str(self.attachment.uid),
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/event-stream")


class StreamOpenApiTest(TestCase):
    @override_settings(ROOT_URLCONF="urls")
    def test_stream_routes_expose_expected_openapi_contract(self):
        request = APIRequestFactory().get("/api/schema/")
        request.user = mock.Mock(is_staff=True, is_authenticated=True)
        response = SpectacularAPIView.as_view()(request)
        response.render()
        paths = yaml.safe_load(response.content)["paths"]

        snapshot_path = "/api/v1/ai_assistant/attachments/{attachment_uid}/stream/snapshot/"
        stream_path = "/api/v1/ai_assistant/attachments/{attachment_uid}/stream/"
        self.assertIn(snapshot_path, paths)
        self.assertIn(stream_path, paths)

        snapshot_content = paths[snapshot_path]["get"]["responses"]["200"]["content"]
        self.assertIn("application/json", snapshot_content)
        stream_content = paths[stream_path]["get"]["responses"]["200"]["content"]
        self.assertEqual(stream_content["text/event-stream"], {"schema": {"type": "string"}})

    @override_settings(ROOT_URLCONF="urls")
    def test_stream_cursor_is_documented_as_query_parameter(self):
        request = APIRequestFactory().get("/api/schema/")
        request.user = mock.Mock(is_staff=True, is_authenticated=True)
        response = SpectacularAPIView.as_view()(request)
        response.render()
        paths = yaml.safe_load(response.content)["paths"]

        parameters = paths["/api/v1/ai_assistant/attachments/{attachment_uid}/stream/"]["get"]["parameters"]
        cursor = next(item for item in parameters if item["name"] == "last_stream_id")
        execution = next(item for item in parameters if item["name"] == "execution_id")

        self.assertEqual(cursor["in"], "query")
        self.assertFalse(cursor.get("required", False))
        self.assertIn("Last-Event-ID", cursor["description"])
        self.assertEqual(execution["in"], "query")
        self.assertTrue(execution["required"])


class StreamUidTypeTest(AttachmentStreamServiceTestCase):
    def test_service_accepts_uuid_instance_and_string(self):
        self.set_config(self.make_config())

        for attachment_uid in (self.attachment.uid, str(self.attachment.uid)):
            with self.subTest(uid_type=type(attachment_uid).__name__):
                service, _ = self.service()
                snapshot = service.get_snapshot(attachment_uid=attachment_uid)
                self.assertIsInstance(self.attachment.uid, UUID)
                self.assertEqual(snapshot.events, [])
