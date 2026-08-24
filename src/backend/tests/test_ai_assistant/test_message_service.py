import threading
from unittest import mock
from uuid import uuid4

from django.db import IntegrityError, close_old_connections
from django.test import TransactionTestCase

from services.web.ai_assistant.constants import (
    ExecutionStatus,
    MessageErrorCode,
    MessageType,
)
from services.web.ai_assistant.exceptions import (
    InvalidInitialMessage,
    InvalidMessageState,
    InvalidParentMessage,
    MessageNotFound,
    MessageSnapshotValidationError,
    UnsupportedMessageType,
)
from services.web.ai_assistant.handlers import (
    MessagePreparation,
    message_handler_registry,
)
from services.web.ai_assistant.models import Conversation, Message
from services.web.ai_assistant.services import MessageService
from services.web.ai_assistant.services.message_execution import finish_message_failure
from tests.base import TestCase
from tests.test_ai_assistant.handlers import (
    EchoAsyncHandler,
    EchoContext,
    EchoInput,
    EchoOutput,
    EchoSyncHandler,
    register_test_message_handler,
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
        self.service = MessageService(user=self.user)
        self.conversation = Conversation.objects.create(created_by=self.user, updated_by=self.user)
        self.sync_handler = RecordingSyncHandler()
        register_test_message_handler(self.sync_handler)

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

    def test_service_binds_user_context(self):
        self.assertEqual(self.service.user, self.user)

    def test_prepare_initial_executes_handler_without_persisting_message(self):
        unsaved_conversation = Conversation(created_by=self.user, updated_by=self.user)

        prepared = self.service.prepare_initial(
            conversation=unsaved_conversation,
            message_type=MessageType.SYSTEM_SELECTION,
            input_data={"text": "hello"},
        )

        self.assertEqual(prepared.output_data, {"content": "alice:sync:hello"})
        self.assertFalse(Message.objects.exists())
        self.assertIsNone(unsaved_conversation.pk)

    def test_create_prepared_does_not_execute_handler_again(self):
        unsaved_conversation = Conversation(created_by=self.user, updated_by=self.user)
        prepared = self.service.prepare_initial(
            conversation=unsaved_conversation,
            message_type=MessageType.SYSTEM_SELECTION,
            input_data={"text": "hello"},
        )
        unsaved_conversation.save()

        with mock.patch.object(self.sync_handler, "execute", side_effect=AssertionError("must not execute")):
            message = self.service.create_prepared(
                conversation=unsaved_conversation,
                prepared=prepared,
            )

        self.assertEqual(message.status, ExecutionStatus.SUCCESS)
        self.assertEqual(message.output_data, {"content": "alice:sync:hello"})

    def test_prepare_initial_only_accepts_owned_unsaved_system_selection(self):
        parent = self.create_parent()
        invalid_cases = []

        self.register_async_handler()
        invalid_cases.append(
            (
                Conversation(created_by=self.user, updated_by=self.user),
                MessageType.NATURAL_LANGUAGE_SEARCH,
            )
        )
        invalid_cases.extend(
            [
                (self.conversation, MessageType.SYSTEM_SELECTION),
                (Conversation(created_by="bob", updated_by="bob"), MessageType.SYSTEM_SELECTION),
            ]
        )

        for conversation, message_type in invalid_cases:
            with self.subTest(message_type=message_type, user=conversation.created_by), self.assertRaises(
                InvalidInitialMessage
            ):
                self.service.prepare_initial(
                    conversation=conversation,
                    message_type=message_type,
                    input_data={"text": "hello"},
                )

        message_handler_registry.unregister(MessageType.SYSTEM_SELECTION)
        register_test_message_handler(RecordingSyncHandler(fallback_parent=parent))
        with self.assertRaises(InvalidInitialMessage):
            self.service.prepare_initial(
                conversation=Conversation(created_by=self.user, updated_by=self.user),
                message_type=MessageType.SYSTEM_SELECTION,
                input_data={"text": "hello"},
            )

    def test_sync_create_validates_and_saves_all_snapshots(self):
        message = self.service.create(
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
        register_test_message_handler(FailingSyncHandler())

        with self.assertRaises(RuntimeError):
            self.service.create(
                conversation=self.conversation,
                message_type=MessageType.SYSTEM_SELECTION,
                input_data={"text": "hello"},
            )

        self.assertFalse(Message.objects.exists())

    def test_sync_invalid_output_does_not_create_message(self):
        message_handler_registry.unregister(MessageType.SYSTEM_SELECTION)
        register_test_message_handler(InvalidOutputSyncHandler())

        with self.assertRaises(MessageSnapshotValidationError):
            self.service.create(
                conversation=self.conversation,
                message_type=MessageType.SYSTEM_SELECTION,
                input_data={"text": "hello"},
            )

        self.assertFalse(Message.objects.exists())

    def test_explicit_parent_is_resolved_before_prepare(self):
        parent = self.create_parent()

        message = self.service.create(
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
        register_test_message_handler(RecordingSyncHandler(fallback_parent=parent))

        message = self.service.create(
            conversation=self.conversation,
            message_type=MessageType.SYSTEM_SELECTION,
            input_data={"text": "child"},
        )

        self.assertEqual(message.parent_message, parent)

    def test_handler_owns_fallback_parent_validation(self):
        other_conversation = Conversation.objects.create(created_by=self.user, updated_by=self.user)
        foreign_parent = self.create_parent(conversation=other_conversation)
        message_handler_registry.unregister(MessageType.SYSTEM_SELECTION)
        register_test_message_handler(RecordingSyncHandler(fallback_parent=foreign_parent))

        message = self.service.create(
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
                self.service.create(
                    conversation=self.conversation,
                    message_type=MessageType.SYSTEM_SELECTION,
                    input_data={"text": "child"},
                    parent_message_uid=parent_uid,
                )

    def test_malformed_parent_uid_is_normalized_to_business_error(self):
        with self.assertRaises(InvalidParentMessage):
            self.service.create(
                conversation=self.conversation,
                message_type=MessageType.SYSTEM_SELECTION,
                input_data={"text": "child"},
                parent_message_uid="not-a-uuid",
            )

    def test_parent_business_status_is_decided_by_handler(self):
        processing_parent = self.create_parent(status=ExecutionStatus.PROCESSING)
        message_handler_registry.unregister(MessageType.SYSTEM_SELECTION)
        register_test_message_handler(RejectingParentHandler())

        with self.assertRaises(InvalidParentMessage) as context:
            self.service.create(
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
                self.service.create(
                    conversation=conversation,
                    message_type=MessageType.SYSTEM_SELECTION,
                    input_data={"text": "hello"},
                )

    def test_stale_conversation_instance_is_checked_against_database(self):
        Conversation._objects.filter(id=self.conversation.id).update(is_deleted=True)

        with self.assertRaises(InvalidParentMessage):
            self.service.create(
                conversation=self.conversation,
                message_type=MessageType.SYSTEM_SELECTION,
                input_data={"text": "hello"},
            )

    def register_async_handler(self):
        handler = EchoAsyncHandler()
        register_test_message_handler(handler)
        return handler

    def test_async_create_persists_processing_message_and_dispatches_after_commit(self):
        handler = self.register_async_handler()

        with mock.patch.object(handler.async_task, "apply_async") as apply_async:
            with self.captureOnCommitCallbacks(execute=True):
                message = self.service.create(
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
                message = self.service.create(
                    conversation=self.conversation,
                    message_type=MessageType.NATURAL_LANGUAGE_SEARCH,
                    input_data={"text": "hello"},
                )

        message.refresh_from_db()
        self.assertEqual(message.status, ExecutionStatus.FAILED)
        self.assertEqual(message.error_code, MessageErrorCode.TASK_DISPATCH_FAILED)
        self.assertEqual(message.error_message, "任务投递失败，请稍后重试")
        self.assertNotIn("broker secret", message.error_message)

    def test_async_dispatch_failure_updates_returned_message_instance(self):
        handler = self.register_async_handler()

        with mock.patch.object(handler.async_task, "apply_async", side_effect=RuntimeError("broker secret")):
            with self.captureOnCommitCallbacks(execute=True):
                message = self.service.create(
                    conversation=self.conversation,
                    message_type=MessageType.NATURAL_LANGUAGE_SEARCH,
                    input_data={"text": "hello"},
                )

        self.assertEqual(message.status, ExecutionStatus.FAILED)
        self.assertEqual(message.error_code, MessageErrorCode.TASK_DISPATCH_FAILED)
        self.assertEqual(message.error_message, "任务投递失败，请稍后重试")
        db_message = Message.objects.get(id=message.id)
        self.assertEqual(db_message.status, ExecutionStatus.FAILED)
        self.assertEqual(db_message.error_code, MessageErrorCode.TASK_DISPATCH_FAILED)

    def test_database_create_failure_does_not_dispatch(self):
        handler = self.register_async_handler()

        with mock.patch.object(handler.async_task, "apply_async") as apply_async:
            with mock.patch.object(Message.objects, "create", side_effect=IntegrityError("write failed")):
                with self.assertRaises(IntegrityError):
                    self.service.create(
                        conversation=self.conversation,
                        message_type=MessageType.NATURAL_LANGUAGE_SEARCH,
                        input_data={"text": "hello"},
                    )

        apply_async.assert_not_called()

    def create_failed_async_message(self, **overrides) -> Message:
        values = {
            "conversation": self.conversation,
            "message_type": MessageType.NATURAL_LANGUAGE_SEARCH,
            "status": ExecutionStatus.FAILED,
            "task_id": "task-old",
            "input_data": {"text": "hello"},
            "context_data": {"prefix": "async"},
            "output_data": {"content": "old"},
            "error_code": "OLD_ERROR",
            "error_message": "旧错误",
            "created_by": self.user,
            "updated_by": self.user,
        }
        values.update(overrides)
        return Message.objects.create(**values)

    def test_retry_reuses_original_message_snapshot_without_prepare(self):
        handler = self.register_async_handler()
        parent = self.create_parent()
        message = self.create_failed_async_message(parent_message=parent)
        old_uid = message.uid
        old_input = message.input_data
        old_context = message.context_data

        with mock.patch.object(handler, "prepare", side_effect=AssertionError("must not prepare")):
            with mock.patch.object(handler.async_task, "apply_async") as apply_async:
                with self.captureOnCommitCallbacks(execute=True):
                    retried = self.service.retry(message_uid=str(message.uid))

        self.assertEqual(retried.uid, old_uid)
        self.assertEqual(retried.parent_message, parent)
        self.assertEqual(retried.input_data, old_input)
        self.assertEqual(retried.context_data, old_context)
        self.assertEqual(retried.status, ExecutionStatus.PROCESSING)
        self.assertNotEqual(retried.task_id, "task-old")
        self.assertIsNone(retried.output_data)
        self.assertEqual(retried.error_code, "")
        self.assertEqual(retried.error_message, "")
        apply_async.assert_called_once_with(
            kwargs={"message_id": retried.id, "task_id": retried.task_id},
            task_id=retried.task_id,
        )

    def test_retry_rejects_invalid_state_mode_task_and_unregistered_type(self):
        self.register_async_handler()
        invalid_messages = (
            self.create_failed_async_message(status=ExecutionStatus.PROCESSING, task_id="task-processing"),
            self.create_failed_async_message(status=ExecutionStatus.SUCCESS, task_id="task-success"),
            self.create_failed_async_message(task_id=""),
            self.create_failed_async_message(
                message_type=MessageType.SYSTEM_SELECTION,
                task_id="task-sync",
            ),
        )
        for message in invalid_messages:
            with self.subTest(status=message.status, message_type=message.message_type), self.assertRaises(
                InvalidMessageState
            ):
                self.service.retry(message_uid=str(message.uid))

        unregistered = self.create_failed_async_message(
            message_type=MessageType.LOG_SEARCH,
            task_id="task-unregistered",
        )
        with self.assertRaises(UnsupportedMessageType):
            self.service.retry(message_uid=str(unregistered.uid))

    def test_retry_hides_foreign_or_deleted_conversation_message(self):
        self.register_async_handler()
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
                self.service.retry(message_uid=str(message.uid))

    def test_old_task_id_cannot_overwrite_retried_message(self):
        self.register_async_handler()
        message = self.create_failed_async_message()
        old_task_id = message.task_id

        with mock.patch("services.web.ai_assistant.services.message.transaction.on_commit"):
            retried = self.service.retry(message_uid=str(message.uid))
        updated = finish_message_failure(
            message_id=retried.id,
            task_id=old_task_id,
            exception=RuntimeError("old task"),
        )

        retried.refresh_from_db()
        self.assertFalse(updated)
        self.assertEqual(retried.status, ExecutionStatus.PROCESSING)
        self.assertNotEqual(retried.task_id, old_task_id)

    def test_retry_dispatch_failure_can_retry_same_message_again(self):
        handler = self.register_async_handler()
        message = self.create_failed_async_message()

        with mock.patch.object(handler.async_task, "apply_async", side_effect=RuntimeError("broker secret")):
            with self.captureOnCommitCallbacks(execute=True):
                failed = self.service.retry(message_uid=str(message.uid))
        self.assertEqual(failed.status, ExecutionStatus.FAILED)
        self.assertEqual(failed.error_code, MessageErrorCode.TASK_DISPATCH_FAILED)
        failed_task_id = failed.task_id

        with mock.patch.object(handler.async_task, "apply_async"):
            with self.captureOnCommitCallbacks(execute=True):
                retried = self.service.retry(message_uid=str(message.uid))
        self.assertEqual(retried.status, ExecutionStatus.PROCESSING)
        self.assertNotEqual(retried.task_id, failed_task_id)


class MessageServiceConcurrencyTest(TransactionTestCase):
    """使用独立数据库连接验证共享旧快照下只有一个重试 CAS 成功。"""

    available_apps = ["services.web.ai_assistant"]
    reset_sequences = True

    def setUp(self):
        self.user = "alice"
        self.conversation = Conversation.objects.create(created_by=self.user, updated_by=self.user)
        register_test_message_handler(EchoAsyncHandler())
        self.message = Message.objects.create(
            conversation=self.conversation,
            message_type=MessageType.NATURAL_LANGUAGE_SEARCH,
            status=ExecutionStatus.FAILED,
            task_id="task-old",
            input_data={"text": "hello"},
            context_data={"prefix": "async"},
            output_data={"content": "old"},
            error_code="OLD_ERROR",
            error_message="旧错误",
            created_by=self.user,
            updated_by=self.user,
        )

    def tearDown(self):
        message_handler_registry.unregister(MessageType.NATURAL_LANGUAGE_SEARCH)

    @staticmethod
    def run_threads(*targets):
        results = []
        errors = []

        def run(target):
            close_old_connections()
            try:
                results.append(target())
            except Exception as error:  # noqa: BLE001 - 需要保留线程原始异常类型
                errors.append(error)
            finally:
                close_old_connections()

        threads = [threading.Thread(target=run, args=(target,)) for target in targets]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        return threads, results, errors

    def test_retry_concurrent_requests_only_one_cas_wins(self):
        barrier = threading.Barrier(2)
        original_get = MessageService.get

        def synchronized_get(service, *, message_uid):
            loaded_message = original_get(service, message_uid=message_uid)
            barrier.wait(timeout=5)
            return loaded_message

        def retry_once():
            return MessageService(user=self.user).retry(message_uid=str(self.message.uid))

        with mock.patch.object(
            MessageService,
            "get",
            autospec=True,
            side_effect=synchronized_get,
        ), mock.patch.object(MessageService, "_dispatch") as dispatch:
            threads, results, errors = self.run_threads(retry_once, retry_once)

        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(len(results), 1)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], InvalidMessageState)
        self.assertEqual(dispatch.call_count, 1)

        self.message.refresh_from_db()
        self.assertEqual(self.message.status, ExecutionStatus.PROCESSING)
        self.assertEqual(self.message.task_id, results[0].task_id)
        self.assertNotEqual(self.message.task_id, "task-old")
