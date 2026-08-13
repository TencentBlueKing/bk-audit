import traceback
from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import ValidationError

from services.web.ai_assistant.constants import ExecutionMode
from services.web.ai_assistant.exceptions import MessageSnapshotValidationError
from services.web.ai_assistant.schemas import (
    MessageSchema,
    dump_snapshot,
    parse_snapshot,
)
from tests.base import TestCase


class ExampleInput(MessageSchema):
    query_text: str
    requested_at: datetime
    request_uid: UUID


class MessageSchemaTest(TestCase):
    def setUp(self):
        self.requested_at = datetime(2026, 8, 13, 10, 30, tzinfo=timezone.utc)
        self.request_uid = uuid4()
        self.input_data = {
            "query_text": "查询登录日志",
            "requested_at": self.requested_at,
            "request_uid": self.request_uid,
        }

    def test_execution_mode_contains_only_sync_and_async(self):
        self.assertEqual(ExecutionMode.values, ["SYNC", "ASYNC"])

    def test_message_schema_rejects_unknown_fields(self):
        with self.assertRaises(ValidationError):
            ExampleInput.model_validate({**self.input_data, "unknown": True})

    def test_message_schema_is_frozen(self):
        snapshot = ExampleInput.model_validate(self.input_data)

        with self.assertRaises(ValidationError):
            snapshot.query_text = "修改后的条件"

    def test_parse_snapshot_returns_concrete_schema(self):
        snapshot = parse_snapshot(ExampleInput, self.input_data, field_name="input_data")

        self.assertIsInstance(snapshot, ExampleInput)
        self.assertEqual(snapshot.query_text, "查询登录日志")

    def test_parse_snapshot_accepts_same_schema_instance(self):
        original = ExampleInput.model_validate(self.input_data)

        snapshot = parse_snapshot(ExampleInput, original, field_name="input_data")

        self.assertIs(snapshot, original)

    def test_dump_snapshot_uses_json_mode(self):
        dumped = dump_snapshot(ExampleInput, self.input_data, field_name="input_data")

        self.assertEqual(
            dumped,
            {
                "query_text": "查询登录日志",
                "requested_at": "2026-08-13T10:30:00Z",
                "request_uid": str(self.request_uid),
            },
        )

    def test_snapshot_validation_error_does_not_expose_input_or_url(self):
        with self.assertRaises(MessageSnapshotValidationError) as context:
            parse_snapshot(
                ExampleInput,
                {
                    "requested_at": self.requested_at,
                    "request_uid": self.request_uid,
                    "secret": "must-not-leak",
                },
                field_name="input_data",
            )

        error = context.exception
        self.assertEqual(error.data["field_name"], "input_data")
        self.assertTrue(error.data["errors"])
        self.assertEqual(set(error.data["errors"][0]), {"type", "loc", "msg"})
        self.assertNotIn("must-not-leak", str(error.data))
        self.assertNotIn("url", str(error.data))
        formatted_exception = "".join(traceback.format_exception(error))
        self.assertNotIn("must-not-leak", formatted_exception)
        self.assertNotIn("errors.pydantic.dev", formatted_exception)
