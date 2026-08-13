from unittest import mock
from uuid import uuid4

from django.db import IntegrityError

from services.web.ai_assistant.constants import (
    ExecutionStatus,
    MessageErrorCode,
    MessageType,
)
from services.web.ai_assistant.exceptions import (
    InvalidParentMessage,
    MessageSnapshotValidationError,
)
from services.web.ai_assistant.handlers import (
    MessagePreparation,
    message_handler_registry,
)
from services.web.ai_assistant.models import Conversation, Message
from services.web.ai_assistant.services import MessageService
from tests.base import TestCase
from tests.test_ai_assistant.handlers import (
    EchoAsyncHandler,
    EchoContext,
    EchoInput,
    EchoOutput,
    EchoSyncHandler,
)


class RecordingSyncHandler(EchoSyncHandler):
    def __init__(self, *, fallback_parent: Message | None = None):
        super().__init__()
        self.fallback_parent = fallback_parent
        self.prepared_input = None
        self.prepared_parent = None
        self.executed_context = None

    def prepare(
        self,
        *,
        user: str,
        conversation: Conversation,
        parent_message: Message | None,
        input_data: EchoInput,
    ) -> MessagePreparation[EchoContext]:
        self.prepared_input = input_data
        self.prepared_parent = parent_message
        return MessagePreparation(
            parent_message=self.fallback_parent or parent_message,
            context_data=EchoContext(prefix=f"{user}:sync"),
        )

    def execute(self, *, input_data: EchoInput, context_data: EchoContext) -> EchoOutput:
        self.executed_context = context_data
        return EchoOutput(content=f"{context_data.prefix}:{input_data.text}")


class FailingSyncHandler(EchoSyncHandler):
    def execute(self, *, input_data: EchoInput, context_data: EchoContext) -> EchoOutput:
        raise RuntimeError("private detail")


class InvalidOutputSyncHandler(EchoSyncHandler):
    def execute(self, *, input_data: EchoInput, context_data: EchoContext) -> EchoOutput:
        return {"invalid": True}


class RejectingParentHandler(EchoSyncHandler):
    def prepare(
        self,
        *,
        user: str,
        conversation: Conversation,
        parent_message: Message | None,
        input_data: EchoInput,
    ) -> MessagePreparation[EchoContext]:
        if parent_message and parent_message.status != ExecutionStatus.SUCCESS:
            raise InvalidParentMessage(message="父消息状态不允许")
        return super().prepare(
            user=user,
            conversation=conversation,
            parent_message=parent_message,
            input_data=input_data,
        )


class MessageServiceTest(TestCase):
    def setUp(self):
        self.user = "alice"
        self.conversation = Conversation.objects.create(created_by=self.user, updated_by=self.user)
        self.sync_handler = RecordingSyncHandler()
        message_handler_registry.register(self.sync_handler)

    def tearDown(self):
        message_handler_registry.unregister(MessageType.SYSTEM_SELECTION)
        message_handler_registry.unregister(MessageType.NATURAL_LANGUAGE_SEARCH)

    def create_parent(
        self,
        *,
        conversation: Conversation | None = None,
        user: str | None = None,
        status: str = ExecutionStatus.SUCCESS,
    ) -> Message:
        owner = user or self.user
        return Message.objects.create(
            conversation=conversation or self.conversation,
            message_type=MessageType.SYSTEM_SELECTION,
            status=status,
            input_data={"text": "parent"},
            context_data={"prefix": "system"},
            output_data={"content": "system:parent"} if status == ExecutionStatus.SUCCESS else None,
            created_by=owner,
            updated_by=owner,
        )

    def test_sync_create_validates_and_saves_all_snapshots(self):
        message = MessageService.create(
            user=self.user,
            conversation=self.conversation,
            message_type=MessageType.SYSTEM_SELECTION,
            input_data={"text": "hello"},
        )

        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(message.status, ExecutionStatus.SUCCESS)
        self.assertIsNone(message.task_id)
        self.assertEqual(message.input_data, {"text": "hello"})
        self.assertEqual(message.context_data, {"prefix": "alice:sync"})
        self.assertEqual(message.output_data, {"content": "alice:sync:hello"})
        self.assertIsInstance(self.sync_handler.prepared_input, EchoInput)
        self.assertIsInstance(self.sync_handler.executed_context, EchoContext)

    def test_sync_execute_failure_does_not_create_message(self):
        message_handler_registry.unregister(MessageType.SYSTEM_SELECTION)
        message_handler_registry.register(FailingSyncHandler())

        with self.assertRaises(RuntimeError):
            MessageService.create(
                user=self.user,
                conversation=self.conversation,
                message_type=MessageType.SYSTEM_SELECTION,
                input_data={"text": "hello"},
            )

        self.assertFalse(Message.objects.exists())

    def test_sync_invalid_output_does_not_create_message(self):
        message_handler_registry.unregister(MessageType.SYSTEM_SELECTION)
        message_handler_registry.register(InvalidOutputSyncHandler())

        with self.assertRaises(MessageSnapshotValidationError):
            MessageService.create(
                user=self.user,
                conversation=self.conversation,
                message_type=MessageType.SYSTEM_SELECTION,
                input_data={"text": "hello"},
            )

        self.assertFalse(Message.objects.exists())

    def test_explicit_parent_is_resolved_before_prepare(self):
        parent = self.create_parent()

        message = MessageService.create(
            user=self.user,
            conversation=self.conversation,
            message_type=MessageType.SYSTEM_SELECTION,
            input_data={"text": "child"},
            parent_message_uid=str(parent.uid),
        )

        self.assertEqual(self.sync_handler.prepared_parent, parent)
        self.assertEqual(message.parent_message, parent)

    def test_handler_can_return_fallback_parent(self):
        parent = self.create_parent()
        message_handler_registry.unregister(MessageType.SYSTEM_SELECTION)
        message_handler_registry.register(RecordingSyncHandler(fallback_parent=parent))

        message = MessageService.create(
            user=self.user,
            conversation=self.conversation,
            message_type=MessageType.SYSTEM_SELECTION,
            input_data={"text": "child"},
        )

        self.assertEqual(message.parent_message, parent)

    def test_handler_owns_fallback_parent_validation(self):
        other_conversation = Conversation.objects.create(created_by=self.user, updated_by=self.user)
        foreign_parent = self.create_parent(conversation=other_conversation)
        message_handler_registry.unregister(MessageType.SYSTEM_SELECTION)
        message_handler_registry.register(RecordingSyncHandler(fallback_parent=foreign_parent))

        message = MessageService.create(
            user=self.user,
            conversation=self.conversation,
            message_type=MessageType.SYSTEM_SELECTION,
            input_data={"text": "child"},
        )

        self.assertEqual(message.parent_message, foreign_parent)

    def test_explicit_parent_must_exist_and_belong_to_user_and_conversation(self):
        other_conversation = Conversation.objects.create(created_by=self.user, updated_by=self.user)
        other_user_conversation = Conversation.objects.create(created_by="bob", updated_by="bob")
        invalid_parent_uids = [
            str(uuid4()),
            str(self.create_parent(conversation=other_conversation).uid),
            str(self.create_parent(conversation=other_user_conversation, user="bob").uid),
        ]

        for parent_uid in invalid_parent_uids:
            with self.subTest(parent_uid=parent_uid), self.assertRaises(InvalidParentMessage):
                MessageService.create(
                    user=self.user,
                    conversation=self.conversation,
                    message_type=MessageType.SYSTEM_SELECTION,
                    input_data={"text": "child"},
                    parent_message_uid=parent_uid,
                )

    def test_malformed_parent_uid_is_normalized_to_business_error(self):
        with self.assertRaises(InvalidParentMessage):
            MessageService.create(
                user=self.user,
                conversation=self.conversation,
                message_type=MessageType.SYSTEM_SELECTION,
                input_data={"text": "child"},
                parent_message_uid="not-a-uuid",
            )

    def test_parent_business_status_is_decided_by_handler(self):
        processing_parent = self.create_parent(status=ExecutionStatus.PROCESSING)
        message_handler_registry.unregister(MessageType.SYSTEM_SELECTION)
        message_handler_registry.register(RejectingParentHandler())

        with self.assertRaises(InvalidParentMessage) as context:
            MessageService.create(
                user=self.user,
                conversation=self.conversation,
                message_type=MessageType.SYSTEM_SELECTION,
                input_data={"text": "child"},
                parent_message_uid=str(processing_parent.uid),
            )

        self.assertEqual(context.exception.message, "父消息状态不允许")

    def test_deleted_or_foreign_conversation_is_rejected(self):
        foreign_conversation = Conversation.objects.create(created_by="bob", updated_by="bob")
        self.conversation.delete()

        for conversation in (self.conversation, foreign_conversation):
            with self.subTest(conversation=conversation.uid), self.assertRaises(InvalidParentMessage):
                MessageService.create(
                    user=self.user,
                    conversation=conversation,
                    message_type=MessageType.SYSTEM_SELECTION,
                    input_data={"text": "hello"},
                )

    def test_stale_conversation_instance_is_checked_against_database(self):
        Conversation._objects.filter(id=self.conversation.id).update(is_deleted=True)

        with self.assertRaises(InvalidParentMessage):
            MessageService.create(
                user=self.user,
                conversation=self.conversation,
                message_type=MessageType.SYSTEM_SELECTION,
                input_data={"text": "hello"},
            )

    def register_async_handler(self):
        handler = EchoAsyncHandler()
        message_handler_registry.register(handler)
        return handler

    def test_async_create_persists_processing_message_and_dispatches_after_commit(self):
        handler = self.register_async_handler()

        with mock.patch.object(handler.async_task, "apply_async") as apply_async:
            with self.captureOnCommitCallbacks(execute=True):
                message = MessageService.create(
                    user=self.user,
                    conversation=self.conversation,
                    message_type=MessageType.NATURAL_LANGUAGE_SEARCH,
                    input_data={"text": "hello"},
                )

        message.refresh_from_db()
        self.assertEqual(message.status, ExecutionStatus.PROCESSING)
        self.assertIsNotNone(message.task_id)
        self.assertEqual(message.input_data, {"text": "hello"})
        self.assertEqual(message.context_data, {"prefix": "async"})
        self.assertIsNone(message.output_data)
        apply_async.assert_called_once_with(
            kwargs={"message_id": message.id, "task_id": message.task_id},
            task_id=message.task_id,
        )

    def test_async_dispatch_failure_keeps_message_and_marks_failed(self):
        handler = self.register_async_handler()

        with mock.patch.object(handler.async_task, "apply_async", side_effect=RuntimeError("broker secret")):
            with self.captureOnCommitCallbacks(execute=True):
                message = MessageService.create(
                    user=self.user,
                    conversation=self.conversation,
                    message_type=MessageType.NATURAL_LANGUAGE_SEARCH,
                    input_data={"text": "hello"},
                )

        message.refresh_from_db()
        self.assertEqual(message.status, ExecutionStatus.FAILED)
        self.assertEqual(message.error_code, MessageErrorCode.TASK_DISPATCH_FAILED)
        self.assertEqual(message.error_message, "任务投递失败，请稍后重试")
        self.assertNotIn("broker secret", message.error_message)

    def test_database_create_failure_does_not_dispatch(self):
        handler = self.register_async_handler()

        with mock.patch.object(handler.async_task, "apply_async") as apply_async:
            with mock.patch.object(Message.objects, "create", side_effect=IntegrityError("write failed")):
                with self.assertRaises(IntegrityError):
                    MessageService.create(
                        user=self.user,
                        conversation=self.conversation,
                        message_type=MessageType.NATURAL_LANGUAGE_SEARCH,
                        input_data={"text": "hello"},
                    )

        apply_async.assert_not_called()
