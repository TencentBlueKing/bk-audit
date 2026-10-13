from uuid import uuid4

from services.web.ai_assistant.constants import PlatformStreamEvent, StreamArchiveStatus
from services.web.ai_assistant.exceptions import InvalidStreamEvent
from services.web.ai_assistant.schemas import (
    AttachmentStreamConfig,
    AttachmentStreamSnapshot,
    UIStreamEvent,
    parse_stream_archive,
    parse_stream_config,
    serialize_stream_event,
)
from tests.base import TestCase


class StreamEventSchemaTest(TestCase):
    """协议无关事件记录固定为 event/stream_id/data，业务协议由 data 自行定义。"""

    def test_business_event_defaults_to_no_name_and_accepts_json_data(self):
        event = UIStreamEvent(data={"delta": "内容"})

        self.assertEqual(
            event.model_dump(mode="json"),
            {
                "event": None,
                "stream_id": None,
                "data": {"delta": "内容"},
            },
        )

    def test_event_rejects_unknown_field_and_is_frozen(self):
        with self.assertRaises(ValueError):
            UIStreamEvent(unknown=True)

        event = UIStreamEvent()
        with self.assertRaises(ValueError):
            event.event = "changed"

    def test_platform_event_uses_stable_reserved_names(self):
        self.assertEqual(
            [
                PlatformStreamEvent.STREAM_RESET,
                PlatformStreamEvent.STREAM_END,
            ],
            ["platform.stream_reset", "platform.stream_end"],
        )

    def test_event_rejects_unregistered_platform_name(self):
        with self.assertRaises(ValueError):
            UIStreamEvent(event="platform.progress")

    def test_serialize_stream_event_returns_compact_utf8_bytes(self):
        event = UIStreamEvent(
            stream_id="1724140800000-0",
            data={"content": "中文"},
        )

        self.assertEqual(
            serialize_stream_event(event),
            b'{"event":null,"stream_id":"1724140800000-0",' b'"data":{"content":"\xe4\xb8\xad\xe6\x96\x87"}}',
        )
        self.assertEqual(
            serialize_stream_event(event, include_stream_id=False),
            b'{"event":null,"data":{"content":"\xe4\xb8\xad\xe6\x96\x87"}}',
        )
        self.assertNotIn(b'"type"', serialize_stream_event(event))

    def test_redis_payload_round_trip_keeps_business_data(self):
        event = UIStreamEvent(data=[1, {"a": None}])

        payload = serialize_stream_event(event, include_stream_id=False)
        restored = UIStreamEvent.model_validate_json(payload)

        self.assertEqual(restored, event)
        self.assertEqual(restored.model_copy(update={"stream_id": "1-0"}).stream_id, "1-0")

    def test_event_rejects_non_json_data(self):
        for invalid_data in (object(), {"value": object()}, float("nan"), float("inf"), bytes(1)):
            with self.subTest(invalid_data=type(invalid_data).__name__):
                with self.assertRaises(InvalidStreamEvent):
                    serialize_stream_event(UIStreamEvent(data=invalid_data))


class StreamConfigSchemaTest(TestCase):
    """流配置只在平台内部流转，必须能从 JSONField 原样还原。"""

    def test_stream_config_round_trip(self):
        config = AttachmentStreamConfig(
            task_id="task-1",
            execution_id=uuid4(),
            redis_key="ai_assistant:attachment_stream:a:b",
            archive_status=StreamArchiveStatus.COMPLETE,
        )

        self.assertEqual(parse_stream_config(config.model_dump(mode="json")), config)

    def test_parse_stream_config_returns_none_for_empty_value(self):
        for empty_value in (None, {}):
            with self.subTest(empty_value=empty_value):
                self.assertIsNone(parse_stream_config(empty_value))

    def test_parse_stream_config_rejects_invalid_internal_config(self):
        for invalid_value in (
            {"execution_id": "not-a-uuid", "redis_key": "key"},
            {"execution_id": str(uuid4()), "redis_key": ""},
            {"execution_id": str(uuid4())},
            {"execution_id": str(uuid4()), "redis_key": "key", "unknown": 1},
            [],
        ):
            with self.subTest(invalid_value=invalid_value):
                with self.assertRaises(InvalidStreamEvent):
                    parse_stream_config(invalid_value)


class StreamArchiveSchemaTest(TestCase):
    """归档是最佳努力快照，脏数据只降级展示，不影响最终产物。"""

    def test_parse_stream_archive_returns_events_and_complete_status(self):
        events = [
            UIStreamEvent(stream_id="1-0", data={"i": 1}),
            UIStreamEvent(event=PlatformStreamEvent.STREAM_END, stream_id="2-0", data={"status": "SUCCESS"}),
        ]

        parsed, status = parse_stream_archive([event.model_dump(mode="json") for event in events])

        self.assertEqual(parsed, events)
        self.assertEqual(status, StreamArchiveStatus.COMPLETE)

    def test_parse_stream_archive_keeps_valid_items_and_degrades_on_dirty_data(self):
        valid = UIStreamEvent(stream_id="1-0", data={"i": 1})

        parsed, status = parse_stream_archive(
            [
                valid.model_dump(mode="json"),
                {"event": "platform.progress", "stream_id": "2-0", "data": {}},
                {"unknown": True},
                "broken",
                None,
            ]
        )

        self.assertEqual(parsed, [valid])
        self.assertEqual(status, StreamArchiveStatus.DEGRADED)

    def test_parse_stream_archive_skips_non_standard_json_values(self):
        valid = UIStreamEvent(stream_id="1-0", data={"i": 1})
        dirty_items = [
            {"event": None, "stream_id": "2-0", "data": float("nan")},
            {"event": None, "stream_id": "3-0", "data": float("inf")},
            {"event": None, "stream_id": "4-0", "data": {"nested": [float("-inf")]}},
        ]

        parsed, status = parse_stream_archive([valid.model_dump(mode="json"), *dirty_items])

        self.assertEqual(parsed, [valid])
        self.assertEqual(status, StreamArchiveStatus.DEGRADED)

    def test_parse_stream_archive_accepts_empty_and_rejects_non_list(self):
        for empty_value in (None, []):
            with self.subTest(empty_value=empty_value):
                self.assertEqual(parse_stream_archive(empty_value), ([], StreamArchiveStatus.COMPLETE))

        parsed, status = parse_stream_archive({"not": "a list"})
        self.assertEqual(parsed, [])
        self.assertEqual(status, StreamArchiveStatus.DEGRADED)


class StreamSnapshotSchemaTest(TestCase):
    def test_snapshot_defaults_to_complete_and_serializes_events(self):
        event = UIStreamEvent(stream_id="1-0", data={"i": 1})

        snapshot = AttachmentStreamSnapshot(events=[event], latest_stream_id="1-0")

        self.assertEqual(
            snapshot.model_dump(mode="json"),
            {
                "events": [
                    {"event": None, "stream_id": "1-0", "data": {"i": 1}},
                ],
                "execution_id": None,
                "latest_stream_id": "1-0",
                "archive_status": "COMPLETE",
            },
        )
