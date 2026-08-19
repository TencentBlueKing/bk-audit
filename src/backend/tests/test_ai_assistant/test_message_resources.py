from unittest import mock
from uuid import UUID, uuid4

from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import resolve

from services.web.ai_assistant.constants import (
    AttachmentType,
    ExecutionStatus,
    FeedbackSourceType,
    FeedbackType,
    MessageHistoryDirection,
    MessageType,
)
from services.web.ai_assistant.exceptions import (
    ConversationNotFound,
    InvalidMessageAnchor,
    InvalidMessageState,
    MessageNotFound,
    MessageSnapshotValidationError,
)
from services.web.ai_assistant.handlers import (
    attachment_handler_registry,
    message_handler_registry,
)
from services.web.ai_assistant.models import Attachment, Conversation, Feedback, Message
from services.web.ai_assistant.resources.message import (
    CreateMessage,
    GetMessage,
    ListMessages,
    RetryMessage,
)
from services.web.ai_assistant.serializers.feedback import FeedbackResponseSerializer
from services.web.ai_assistant.serializers.message import (
    AttachmentSummarySerializer,
    InitialMessageRequestSerializer,
    MessageCreateRequestSerializer,
    MessageDetailRequestSerializer,
    MessageListRequestSerializer,
    MessageResponseSerializer,
    MessageWindowResponseSerializer,
    _message_schema_mapping,
)
from services.web.ai_assistant.services.message import MessageService
from services.web.ai_assistant.services.message_execution import (
    finish_message_success,
    load_message_execution,
)
from tests.base import TestCase
from tests.test_ai_assistant.handlers import (
    EchoAsyncHandler,
    EchoAttachmentAsyncHandler,
    EchoInput,
    EchoOutput,
    EchoSyncHandler,
    FeedbackAttachmentEchoHandler,
    FeedbackEchoSyncHandler,
)


class MessageRequestSerializerTest(TestCase):
    def setUp(self):
        self.conversation_uid = str(uuid4())
        self.message_uid = str(uuid4())

    def test_create_request_requires_typed_business_input(self):
        serializer = MessageCreateRequestSerializer(
            data={
                "conversation_uid": self.conversation_uid,
                "message_type": MessageType.SYSTEM_SELECTION,
                "input_data": {"text": "system-a"},
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["conversation_uid"], UUID(self.conversation_uid))

    def test_create_request_rejects_missing_input_and_ignores_internal_fields(self):
        missing_input = MessageCreateRequestSerializer(
            data={
                "conversation_uid": self.conversation_uid,
                "message_type": MessageType.SYSTEM_SELECTION,
            }
        )
        internal_fields = MessageCreateRequestSerializer(
            data={
                "conversation_uid": self.conversation_uid,
                "message_type": MessageType.SYSTEM_SELECTION,
                "input_data": {"text": "system-a"},
                "status": ExecutionStatus.SUCCESS,
                "output_data": {"content": "forged"},
            }
        )

        self.assertFalse(missing_input.is_valid())
        self.assertTrue(internal_fields.is_valid(), internal_fields.errors)
        self.assertNotIn("status", internal_fields.validated_data)
        self.assertNotIn("output_data", internal_fields.validated_data)

    def test_history_anchor_and_direction_must_be_supplied_together(self):
        for data in (
            {"conversation_uid": self.conversation_uid, "anchor_uid": self.message_uid},
            {"conversation_uid": self.conversation_uid, "direction": MessageHistoryDirection.AFTER},
        ):
            with self.subTest(data=data):
                serializer = MessageListRequestSerializer(data=data)
                self.assertFalse(serializer.is_valid())

    def test_history_rejects_invalid_direction_and_limit(self):
        invalid_requests = (
            {"conversation_uid": self.conversation_uid, "limit": 0},
            {"conversation_uid": self.conversation_uid, "limit": 101},
            {
                "conversation_uid": self.conversation_uid,
                "anchor_uid": self.message_uid,
                "direction": "INVALID",
            },
        )

        for data in invalid_requests:
            with self.subTest(data=data):
                serializer = MessageListRequestSerializer(data=data)
                self.assertFalse(serializer.is_valid())

    def test_initial_message_only_accepts_system_selection(self):
        valid = InitialMessageRequestSerializer(
            data={"message_type": MessageType.SYSTEM_SELECTION, "input_data": {"systems": ["a"]}}
        )
        invalid = InitialMessageRequestSerializer(
            data={"message_type": MessageType.LOG_SEARCH, "input_data": {"query": {}}}
        )

        self.assertTrue(valid.is_valid(), valid.errors)
        self.assertFalse(invalid.is_valid())

    def test_all_message_api_fields_have_swagger_descriptions(self):
        serializer_classes = (
            AttachmentSummarySerializer,
            InitialMessageRequestSerializer,
            MessageCreateRequestSerializer,
            MessageDetailRequestSerializer,
            MessageListRequestSerializer,
            MessageResponseSerializer,
            MessageWindowResponseSerializer,
            FeedbackResponseSerializer,
        )

        for serializer_class in serializer_classes:
            for field_name, field in serializer_class().fields.items():
                with self.subTest(serializer=serializer_class.__name__, field=field_name):
                    self.assertTrue(field.help_text)

    def test_swagger_snapshot_schema_mapping_uses_registered_handler_models(self):
        sync_handler = EchoSyncHandler()
        async_handler = EchoAsyncHandler()
        message_handler_registry.register(sync_handler)
        message_handler_registry.register(async_handler)
        try:
            input_schemas = _message_schema_mapping("input_model")
            output_schemas = _message_schema_mapping("output_model")
        finally:
            message_handler_registry.unregister(MessageType.SYSTEM_SELECTION)
            message_handler_registry.unregister(MessageType.NATURAL_LANGUAGE_SEARCH)

        self.assertIs(input_schemas[MessageType.SYSTEM_SELECTION], EchoInput)
        self.assertIs(input_schemas[MessageType.NATURAL_LANGUAGE_SEARCH], EchoInput)
        self.assertIs(output_schemas[MessageType.SYSTEM_SELECTION], EchoOutput)
        self.assertIs(output_schemas[MessageType.NATURAL_LANGUAGE_SEARCH], EchoOutput)


@mock.patch("services.web.ai_assistant.resources.message.get_request_username", return_value="alice")
class MessageResourceTest(TestCase):
    def setUp(self):
        self.conversation = Conversation.objects.create(created_by="alice", updated_by="alice")
        self.sync_handler = FeedbackEchoSyncHandler()
        self.async_handler = EchoAsyncHandler()
        self.attachment_handler = FeedbackAttachmentEchoHandler()
        self.async_attachment_handler = EchoAttachmentAsyncHandler()
        message_handler_registry.register(self.sync_handler)
        message_handler_registry.register(self.async_handler)
        attachment_handler_registry.register(self.attachment_handler)
        attachment_handler_registry.register(self.async_attachment_handler)

    def tearDown(self):
        message_handler_registry.unregister(MessageType.SYSTEM_SELECTION)
        message_handler_registry.unregister(MessageType.NATURAL_LANGUAGE_SEARCH)
        attachment_handler_registry.unregister(AttachmentType.FIELD_STATISTICS)
        attachment_handler_registry.unregister(AttachmentType.AI_ANALYSIS)

    def test_create_sync_message_returns_success_without_internal_fields(self, _username):
        response = CreateMessage().request(
            {
                "conversation_uid": str(self.conversation.uid),
                "message_type": MessageType.SYSTEM_SELECTION,
                "input_data": {"text": "system-a"},
            }
        )

        self.assertEqual(response["status"], ExecutionStatus.SUCCESS)
        self.assertEqual(response["input_data"], {"text": "system-a"})
        self.assertNotIn("context_data", response)
        self.assertEqual(response["output_data"], {"content": "system:system-a"})
        self.assertIsNone(response["parent_message_uid"])
        self.assertEqual(response["attachments"], [])
        self.assertTrue(response["supports_feedback"])
        self.assertIsNone(response["feedback"])
        for internal_field in ("id", "task_id", "stream_config", "stream_archive"):
            self.assertNotIn(internal_field, response)

    def test_create_async_message_returns_processing_and_detail_observes_success(self, _username):
        with mock.patch.object(self.async_handler.async_task, "apply_async"):
            with self.captureOnCommitCallbacks(execute=True):
                created = CreateMessage().request(
                    {
                        "conversation_uid": str(self.conversation.uid),
                        "message_type": MessageType.NATURAL_LANGUAGE_SEARCH,
                        "input_data": {"text": "search"},
                    }
                )
        self.assertEqual(created["status"], ExecutionStatus.PROCESSING)
        self.assertIsNone(created["output_data"])

        message = Message.objects.get(uid=created["uid"])
        execution = load_message_execution(
            message_id=message.id,
            task_id=message.task_id,
            celery_task_id=message.task_id,
        )
        finish_message_success(
            execution=execution,
            task_id=message.task_id,
            output_data={"content": "async:search"},
        )

        detail = GetMessage().request({"message_uid": created["uid"]})
        self.assertEqual(detail["status"], ExecutionStatus.SUCCESS)
        self.assertEqual(detail["output_data"], {"content": "async:search"})

    def test_parent_message_uid_is_preserved(self, _username):
        parent = CreateMessage().request(
            {
                "conversation_uid": str(self.conversation.uid),
                "message_type": MessageType.SYSTEM_SELECTION,
                "input_data": {"text": "parent"},
            }
        )

        child = CreateMessage().request(
            {
                "conversation_uid": str(self.conversation.uid),
                "message_type": MessageType.SYSTEM_SELECTION,
                "parent_message_uid": parent["uid"],
                "input_data": {"text": "child"},
            }
        )

        self.assertEqual(child["parent_message_uid"], parent["uid"])

    def test_list_can_hide_content_but_keeps_status_and_attachment_summary(self, _username):
        created = CreateMessage().request(
            {
                "conversation_uid": str(self.conversation.uid),
                "message_type": MessageType.SYSTEM_SELECTION,
                "input_data": {"text": "system-a"},
            }
        )
        message = Message.objects.get(uid=created["uid"])
        attachment = Attachment.objects.create(
            source_message=message,
            attachment_type=AttachmentType.AI_ANALYSIS,
            title="风险分析",
            status=ExecutionStatus.PROCESSING,
            input_data={},
            context_data={},
            output_data=None,
            created_by="alice",
            updated_by="alice",
        )
        latest_attachment = Attachment.objects.create(
            source_message=message,
            attachment_type=AttachmentType.FIELD_STATISTICS,
            title="字段统计",
            status=ExecutionStatus.SUCCESS,
            input_data={},
            context_data={},
            output_data={"count": 1},
            created_by="alice",
            updated_by="alice",
        )

        window = ListMessages().request({"conversation_uid": str(self.conversation.uid), "include_content": False})

        self.assertEqual(window["first_uid"], created["uid"])
        self.assertEqual(window["last_uid"], created["uid"])
        item = window["results"][0]
        self.assertEqual(item["status"], ExecutionStatus.SUCCESS)
        self.assertNotIn("input_data", item)
        self.assertNotIn("context_data", item)
        self.assertNotIn("output_data", item)
        self.assertEqual(
            set(item["attachments"][0]),
            {"uid", "attachment_type", "status", "title", "content_updated_at", "created_at", "supports_feedback"},
        )
        self.assertEqual(
            [summary["uid"] for summary in item["attachments"]],
            [str(latest_attachment.uid), str(attachment.uid)],
        )

        detail = GetMessage().request({"message_uid": created["uid"]})
        self.assertEqual(detail["input_data"], {"text": "system-a"})
        self.assertNotIn("context_data", detail)

    def test_message_response_exposes_current_feedback_and_list_uses_one_feedback_query(self, _username):
        messages = [
            Message.objects.create(
                conversation=self.conversation,
                message_type=MessageType.SYSTEM_SELECTION,
                status=ExecutionStatus.SUCCESS,
                input_data={"text": f"message-{index}"},
                context_data={"prefix": "system"},
                output_data={"content": f"system:message-{index}"},
                created_by="alice",
                updated_by="alice",
            )
            for index in range(20)
        ]
        Feedback.objects.create(
            source_type=FeedbackSourceType.MESSAGE,
            source_id=messages[0].id,
            feedback_type=FeedbackType.LIKE,
            comment="有帮助",
            created_by="alice",
            updated_by="alice",
        )

        with CaptureQueriesContext(connection) as queries:
            window = MessageService(user="alice").list(
                conversation_uid=str(self.conversation.uid),
                limit=20,
                include_content=False,
            )
            response = MessageWindowResponseSerializer(window).data

        feedback_selects = [
            query["sql"]
            for query in queries.captured_queries
            if "ai_assistant_feedback" in query["sql"].lower() and query["sql"].lstrip().upper().startswith("SELECT")
        ]
        self.assertEqual(len(feedback_selects), 1)
        self.assertTrue(response["results"][0]["supports_feedback"])
        self.assertEqual(response["results"][0]["feedback"]["source_uid"], str(messages[0].uid))
        self.assertNotIn(
            "feedback", response["results"][0]["attachments"][0] if response["results"][0]["attachments"] else {}
        )

    def test_list_after_anchor_discovers_new_messages(self, _username):
        first = CreateMessage().request(
            {
                "conversation_uid": str(self.conversation.uid),
                "message_type": MessageType.SYSTEM_SELECTION,
                "input_data": {"text": "first"},
            }
        )
        second = CreateMessage().request(
            {
                "conversation_uid": str(self.conversation.uid),
                "message_type": MessageType.SYSTEM_SELECTION,
                "input_data": {"text": "second"},
            }
        )

        window = ListMessages().request(
            {
                "conversation_uid": str(self.conversation.uid),
                "anchor_uid": first["uid"],
                "direction": MessageHistoryDirection.AFTER,
            }
        )

        self.assertEqual([item["uid"] for item in window["results"]], [second["uid"]])

    def test_cross_user_resources_are_hidden(self, _username):
        foreign_conversation = Conversation.objects.create(created_by="bob", updated_by="bob")
        foreign_message = Message.objects.create(
            conversation=foreign_conversation,
            message_type=MessageType.SYSTEM_SELECTION,
            status=ExecutionStatus.SUCCESS,
            input_data={"text": "foreign"},
            context_data={"prefix": "system"},
            output_data={"content": "system:foreign"},
            created_by="bob",
            updated_by="bob",
        )

        with self.assertRaises(ConversationNotFound):
            CreateMessage().request(
                {
                    "conversation_uid": str(foreign_conversation.uid),
                    "message_type": MessageType.SYSTEM_SELECTION,
                    "input_data": {"text": "forbidden"},
                }
            )
        with self.assertRaises(MessageNotFound):
            GetMessage().request({"message_uid": str(foreign_message.uid)})
        with self.assertRaises(InvalidMessageAnchor):
            ListMessages().request(
                {
                    "conversation_uid": str(self.conversation.uid),
                    "anchor_uid": str(foreign_message.uid),
                    "direction": MessageHistoryDirection.AFTER,
                }
            )

    def test_corrupted_database_snapshot_is_rejected_on_read(self, _username):
        message = Message.objects.create(
            conversation=self.conversation,
            message_type=MessageType.SYSTEM_SELECTION,
            status=ExecutionStatus.SUCCESS,
            input_data={"invalid": True},
            context_data={"prefix": "system"},
            output_data={"content": "system:value"},
            created_by="alice",
            updated_by="alice",
        )

        with self.assertRaises(MessageSnapshotValidationError):
            GetMessage().request({"message_uid": str(message.uid)})

    def create_failed_async_message(self, **overrides):
        values = {
            "conversation": self.conversation,
            "message_type": MessageType.NATURAL_LANGUAGE_SEARCH,
            "status": ExecutionStatus.FAILED,
            "task_id": "task-old",
            "input_data": {"text": "search"},
            "context_data": {"prefix": "async"},
            "output_data": {"content": "old"},
            "error_code": "OLD_ERROR",
            "error_message": "旧错误",
            "created_by": "alice",
            "updated_by": "alice",
        }
        values.update(overrides)
        return Message.objects.create(**values)

    def test_retry_message_returns_original_uid_processing_dto(self, _username):
        message = self.create_failed_async_message()

        with mock.patch.object(self.async_handler.async_task, "apply_async"):
            with self.captureOnCommitCallbacks(execute=True):
                response = RetryMessage().request({"message_uid": str(message.uid)})

        self.assertEqual(response["uid"], str(message.uid))
        self.assertEqual(response["status"], ExecutionStatus.PROCESSING)
        self.assertEqual(response["input_data"], {"text": "search"})
        self.assertIsNone(response["output_data"])
        self.assertNotIn("context_data", response)
        self.assertNotIn("task_id", response)

    def test_retry_message_rejects_invalid_state(self, _username):
        message = self.create_failed_async_message(
            status=ExecutionStatus.PROCESSING,
            task_id="task-processing",
        )

        with self.assertRaises(InvalidMessageState):
            RetryMessage().request({"message_uid": str(message.uid)})

    def test_retry_message_hides_foreign_and_deleted_conversation(self, _username):
        foreign_conversation = Conversation.objects.create(created_by="bob", updated_by="bob")
        foreign = self.create_failed_async_message(
            conversation=foreign_conversation,
            created_by="bob",
            updated_by="bob",
        )
        deleted = self.create_failed_async_message(task_id="task-deleted")
        self.conversation.delete()

        for message in (foreign, deleted):
            with self.subTest(message=message.uid), self.assertRaises(MessageNotFound):
                RetryMessage().request({"message_uid": str(message.uid)})


@override_settings(ROOT_URLCONF="services.web.urls")
class MessageResourceRoutingTest(TestCase):
    def test_message_routes_use_external_uid(self):
        message_uid = str(uuid4())

        self.assertEqual(resolve("/api/v1/ai_assistant/messages/").url_name, "messages-list")
        nested_attachment_match = resolve(f"/api/v1/ai_assistant/messages/{message_uid}/attachments/")
        self.assertEqual(nested_attachment_match.kwargs, {"message_uid": message_uid})
        detail_match = resolve(f"/api/v1/ai_assistant/messages/{message_uid}/")
        self.assertEqual(detail_match.kwargs, {"message_uid": message_uid})
        retry_match = resolve(f"/api/v1/ai_assistant/messages/{message_uid}/retry/")
        self.assertEqual(retry_match.kwargs, {"message_uid": message_uid})
