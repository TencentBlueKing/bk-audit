import threading
from datetime import timedelta
from unittest import mock
from uuid import uuid4

from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from services.web.ai_assistant import services as ai_assistant_services
from services.web.ai_assistant.constants import (
    AttachmentErrorCode,
    AttachmentType,
    ExecutionStatus,
    MessageType,
)
from services.web.ai_assistant.exceptions import (
    AttachmentNotEditable,
    AttachmentNotFound,
    AttachmentOutputValidationError,
    AttachmentSnapshotValidationError,
    InvalidAttachmentPreparation,
    InvalidAttachmentSource,
    InvalidAttachmentState,
)
from services.web.ai_assistant.handlers import (
    AttachmentExecutionContext,
    AttachmentPreparation,
    attachment_handler_registry,
)
from services.web.ai_assistant.models import Attachment, Conversation, Message
from services.web.ai_assistant.schemas import MessageSchema
from services.web.ai_assistant.serializers.attachment import (
    AttachmentListItemSerializer,
)
from services.web.ai_assistant.services.attachment import AttachmentService
from services.web.ai_assistant.services.attachment_execution import (
    finish_attachment_failure,
)
from tests.base import TestCase
from tests.test_ai_assistant.handlers import (
    AttachmentEchoContext,
    AttachmentEchoInput,
    AttachmentEchoOutput,
    EchoAttachmentAsyncHandler,
    EchoAttachmentSyncHandler,
    EditableAttachmentEchoHandler,
)

UNSET = object()


class RecordingAttachmentSyncHandler(EchoAttachmentSyncHandler):
    def __init__(self, *, title: str = "字段统计"):
        self.title = title
        self.prepared_input = None
        self.prepare_atomic_depth = None
        self.execution_context = None

    def prepare(
        self,
        *,
        user: str,
        source_message: Message,
        input_data: AttachmentEchoInput,
    ) -> AttachmentPreparation[AttachmentEchoContext]:
        self.prepared_input = input_data
        self.prepare_atomic_depth = len(connection.atomic_blocks)
        return AttachmentPreparation(
            title=self.title,
            context_data=AttachmentEchoContext(prefix=f"{user}:sync"),
        )

    def execute(
        self,
        *,
        execution: AttachmentExecutionContext[AttachmentEchoInput, AttachmentEchoContext],
    ) -> AttachmentEchoOutput:
        self.execution_context = execution
        return AttachmentEchoOutput(content=f"{execution.context_data.prefix}:{execution.input_data.text}")


class RecordingAttachmentAsyncHandler(EchoAttachmentAsyncHandler):
    def __init__(self, *, title: str = "AI 分析"):
        self.title = title
        self.prepare_calls = 0
        self.prepare_atomic_depth = None

    def prepare(
        self,
        *,
        user: str,
        source_message: Message,
        input_data: AttachmentEchoInput,
    ) -> AttachmentPreparation[AttachmentEchoContext]:
        self.prepare_calls += 1
        self.prepare_atomic_depth = len(connection.atomic_blocks)
        return AttachmentPreparation(
            title=self.title,
            context_data=AttachmentEchoContext(prefix=f"{user}:async"),
        )


class FailingAttachmentSyncHandler(RecordingAttachmentSyncHandler):
    def execute(
        self,
        *,
        execution: AttachmentExecutionContext[AttachmentEchoInput, AttachmentEchoContext],
    ) -> AttachmentEchoOutput:
        raise RuntimeError("private detail")


class InvalidOutputAttachmentSyncHandler(RecordingAttachmentSyncHandler):
    def execute(
        self,
        *,
        execution: AttachmentExecutionContext[AttachmentEchoInput, AttachmentEchoContext],
    ):
        return {"invalid": True}


class InvalidReturnEditableAttachmentHandler(EditableAttachmentEchoHandler):
    def edit_output(
        self,
        *,
        attachment: Attachment,
        current_output: AttachmentEchoOutput,
        submitted_output: AttachmentEchoOutput,
    ):
        return {"invalid": True}


class EmptyEditableOutput(MessageSchema):
    pass


class EmptyObjectEditableAttachmentHandler(EditableAttachmentEchoHandler):
    output_model = EmptyEditableOutput

    def __init__(self):
        self.edit_calls = 0

    def edit_output(
        self,
        *,
        attachment: Attachment,
        current_output: EmptyEditableOutput,
        submitted_output: EmptyEditableOutput,
    ) -> EmptyEditableOutput:
        self.edit_calls += 1
        return submitted_output


class AttachmentServiceTest(TestCase):
    def setUp(self):
        self.user = "alice"
        self.other_user = "bob"
        self.service = AttachmentService(user=self.user)
        self.conversation = Conversation.objects.create(created_by=self.user, updated_by=self.user)
        self.source_message = self.create_source_message()
        self.atomic_depth = len(connection.atomic_blocks)

    def tearDown(self):
        for attachment_type in AttachmentType.values:
            attachment_handler_registry.unregister(attachment_type)

    def register_sync_handler(self, handler=None):
        handler = handler or RecordingAttachmentSyncHandler()
        attachment_handler_registry.register(handler)
        return handler

    def register_async_handler(self, handler=None):
        handler = handler or RecordingAttachmentAsyncHandler()
        attachment_handler_registry.register(handler)
        return handler

    def create_source_message(
        self,
        *,
        conversation: Conversation | None = None,
        user: str | None = None,
        status: str = ExecutionStatus.SUCCESS,
    ) -> Message:
        owner = user or self.user
        return Message.objects.create(
            conversation=conversation or self.conversation,
            message_type=MessageType.LOG_SEARCH,
            status=status,
            task_id=f"message-{Message.objects.count() + 1}",
            input_data={"text": "query"},
            context_data={"prefix": "source"},
            output_data={"content": "source"} if status == ExecutionStatus.SUCCESS else None,
            created_by=owner,
            updated_by=owner,
        )

    def create_attachment(
        self,
        *,
        attachment_type: str = AttachmentType.FIELD_STATISTICS,
        source_message: Message | None = None,
        status: str = ExecutionStatus.SUCCESS,
        task_id: str | None = None,
        title: str = "原始标题",
        content_updated_at=None,
        output_data=UNSET,
        stream_config=UNSET,
        stream_archive=UNSET,
        created_by: str | None = None,
    ) -> Attachment:
        return Attachment.objects.create(
            source_message=source_message or self.source_message,
            attachment_type=attachment_type,
            title=title,
            status=status,
            task_id=task_id,
            input_data={"text": "hello"},
            context_data={"prefix": "ctx"},
            output_data={"content": "old"} if output_data is UNSET else output_data,
            error_code="OLD_CODE" if status == ExecutionStatus.FAILED else "",
            error_message="old error" if status == ExecutionStatus.FAILED else "",
            stream_config={"mode": "stream"} if stream_config is UNSET else stream_config,
            stream_archive=[{"delta": "old"}] if stream_archive is UNSET else stream_archive,
            content_updated_at=content_updated_at or timezone.now(),
            created_by=created_by or self.user,
            updated_by=created_by or self.user,
        )

    def test_create_requires_visible_success_source_message(self):
        self.register_sync_handler()
        foreign_conversation = Conversation.objects.create(created_by=self.other_user, updated_by=self.other_user)
        invalid_source_uids = [
            str(uuid4()),
            str(self.create_source_message(conversation=foreign_conversation, user=self.other_user).uid),
        ]
        deleted_conversation = Conversation.objects.create(created_by=self.user, updated_by=self.user)
        deleted_source = self.create_source_message(conversation=deleted_conversation)
        deleted_conversation.delete()
        invalid_source_uids.append(str(deleted_source.uid))
        invalid_source_uids.extend(
            [
                str(self.create_source_message(status=ExecutionStatus.PROCESSING).uid),
                str(self.create_source_message(status=ExecutionStatus.FAILED).uid),
            ]
        )

        for source_message_uid in invalid_source_uids:
            with self.subTest(source_message_uid=source_message_uid), self.assertRaises(InvalidAttachmentSource):
                self.service.create(
                    source_message_uid=source_message_uid,
                    attachment_type=AttachmentType.FIELD_STATISTICS,
                    input_data={"text": "hello"},
                )

    def test_create_invalid_input_raises_attachment_snapshot_validation_error(self):
        self.register_sync_handler()

        with self.assertRaises(AttachmentSnapshotValidationError):
            self.service.create(
                source_message_uid=str(self.source_message.uid),
                attachment_type=AttachmentType.FIELD_STATISTICS,
                input_data={},
            )

    def test_create_prepare_receives_typed_input_outside_transaction_and_validates_title(self):
        handler = self.register_sync_handler()

        attachment = self.service.create(
            source_message_uid=str(self.source_message.uid),
            attachment_type=AttachmentType.FIELD_STATISTICS,
            input_data={"text": "hello"},
        )

        self.assertEqual(attachment.status, ExecutionStatus.SUCCESS)
        self.assertEqual(attachment.title, "字段统计")
        self.assertEqual(attachment.context_data, {"prefix": "alice:sync"})
        self.assertEqual(attachment.output_data, {"content": "alice:sync:hello"})
        self.assertIsInstance(handler.prepared_input, AttachmentEchoInput)
        self.assertEqual(handler.prepare_atomic_depth, self.atomic_depth)
        self.assertEqual(handler.execution_context.source_message, self.source_message)
        self.assertIsInstance(handler.execution_context.input_data, AttachmentEchoInput)
        self.assertIsInstance(handler.execution_context.context_data, AttachmentEchoContext)

        for invalid_title in ("   ", "x" * 256):
            attachment_handler_registry.unregister(AttachmentType.FIELD_STATISTICS)
            self.register_sync_handler(RecordingAttachmentSyncHandler(title=invalid_title))
            with self.subTest(invalid_title=invalid_title), self.assertRaises(InvalidAttachmentPreparation):
                self.service.create(
                    source_message_uid=str(self.source_message.uid),
                    attachment_type=AttachmentType.FIELD_STATISTICS,
                    input_data={"text": "hello"},
                )

    def test_sync_create_calls_create_once_and_persists_success(self):
        self.register_sync_handler()

        with mock.patch.object(Attachment.objects, "create", wraps=Attachment.objects.create) as create_attachment:
            attachment = self.service.create(
                source_message_uid=str(self.source_message.uid),
                attachment_type=AttachmentType.FIELD_STATISTICS,
                input_data={"text": "hello"},
            )

        self.assertEqual(create_attachment.call_count, 1)
        self.assertEqual(Attachment.objects.count(), 1)
        self.assertEqual(attachment.status, ExecutionStatus.SUCCESS)

    def test_sync_create_failure_or_output_validation_does_not_persist_attachment(self):
        for handler, expected_exception in (
            (FailingAttachmentSyncHandler(), RuntimeError),
            (InvalidOutputAttachmentSyncHandler(), AttachmentOutputValidationError),
        ):
            with self.subTest(handler=handler.__class__.__name__):
                attachment_handler_registry.unregister(AttachmentType.FIELD_STATISTICS)
                self.register_sync_handler(handler)

                with self.assertRaises(expected_exception):
                    self.service.create(
                        source_message_uid=str(self.source_message.uid),
                        attachment_type=AttachmentType.FIELD_STATISTICS,
                        input_data={"text": "hello"},
                    )

                self.assertFalse(Attachment.objects.exists())

    def test_async_create_persists_processing_attachment_and_dispatches_after_commit(self):
        handler = self.register_async_handler()

        with mock.patch.object(handler.async_task, "apply_async") as apply_async:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                attachment = self.service.create(
                    source_message_uid=str(self.source_message.uid),
                    attachment_type=AttachmentType.AI_ANALYSIS,
                    input_data={"text": "hello"},
                )

            apply_async.assert_not_called()
            self.assertEqual(len(callbacks), 1)
            callbacks[0]()

        attachment.refresh_from_db()
        self.assertEqual(attachment.status, ExecutionStatus.PROCESSING)
        self.assertEqual(attachment.title, "AI 分析")
        self.assertEqual(attachment.input_data, {"text": "hello"})
        self.assertEqual(attachment.context_data, {"prefix": "alice:async"})
        self.assertIsNone(attachment.output_data)
        self.assertIsNotNone(attachment.task_id)
        self.assertEqual(handler.prepare_atomic_depth, self.atomic_depth)
        apply_async.assert_called_once_with(
            kwargs={"attachment_id": attachment.id, "task_id": attachment.task_id},
            task_id=attachment.task_id,
        )

    def test_async_dispatch_failure_marks_database_and_returned_instance_failed(self):
        handler = self.register_async_handler()

        with mock.patch.object(handler.async_task, "apply_async", side_effect=RuntimeError("broker secret")):
            with self.captureOnCommitCallbacks(execute=True):
                attachment = self.service.create(
                    source_message_uid=str(self.source_message.uid),
                    attachment_type=AttachmentType.AI_ANALYSIS,
                    input_data={"text": "hello"},
                )

        self.assertEqual(attachment.status, ExecutionStatus.FAILED)
        self.assertEqual(attachment.error_code, AttachmentErrorCode.TASK_DISPATCH_FAILED)
        self.assertEqual(attachment.error_message, "附件任务投递失败，请稍后重试")
        self.assertNotIn("broker secret", attachment.error_message)
        db_attachment = Attachment.objects.get(id=attachment.id)
        self.assertEqual(db_attachment.status, ExecutionStatus.FAILED)
        self.assertEqual(db_attachment.error_code, AttachmentErrorCode.TASK_DISPATCH_FAILED)

    def test_get_only_returns_visible_attachment(self):
        self.register_sync_handler()
        visible = self.create_attachment()
        foreign_conversation = Conversation.objects.create(created_by=self.other_user, updated_by=self.other_user)
        foreign_source = self.create_source_message(conversation=foreign_conversation, user=self.other_user)
        foreign_attachment = self.create_attachment(source_message=foreign_source, created_by=self.other_user)
        deleted_conversation = Conversation.objects.create(created_by=self.user, updated_by=self.user)
        deleted_source = self.create_source_message(conversation=deleted_conversation)
        deleted_attachment = self.create_attachment(source_message=deleted_source)
        deleted_conversation.delete()

        self.assertEqual(self.service.get(attachment_uid=str(visible.uid)).id, visible.id)
        for attachment_uid in ("not-a-uuid", str(uuid4()), str(foreign_attachment.uid), str(deleted_attachment.uid)):
            with self.subTest(attachment_uid=attachment_uid), self.assertRaises(AttachmentNotFound):
                self.service.get(attachment_uid=attachment_uid)

    def test_list_filters_visible_attachments_and_orders_by_content_updated_at_then_id(self):
        self.register_sync_handler()
        now = timezone.now()
        first = self.create_attachment(
            attachment_type=AttachmentType.FIELD_STATISTICS,
            status=ExecutionStatus.SUCCESS,
            title="字段统计 Alpha",
            content_updated_at=now - timedelta(minutes=5),
        )
        second = self.create_attachment(
            attachment_type=AttachmentType.AI_ANALYSIS,
            status=ExecutionStatus.FAILED,
            title="AI Alpha",
            content_updated_at=now,
        )
        third = self.create_attachment(
            attachment_type=AttachmentType.AI_ANALYSIS,
            status=ExecutionStatus.SUCCESS,
            title="AI Beta",
            content_updated_at=now,
        )
        foreign_conversation = Conversation.objects.create(created_by=self.other_user, updated_by=self.other_user)
        foreign_source = self.create_source_message(conversation=foreign_conversation, user=self.other_user)
        self.create_attachment(source_message=foreign_source, created_by=self.other_user)
        deleted_conversation = Conversation.objects.create(created_by=self.user, updated_by=self.user)
        deleted_source = self.create_source_message(conversation=deleted_conversation)
        self.create_attachment(source_message=deleted_source)
        deleted_conversation.delete()

        self.assertEqual(
            [attachment.id for attachment in self.service.list()],
            [third.id, second.id, first.id],
        )
        self.assertEqual(
            [attachment.id for attachment in self.service.list(keyword="alpha")],
            [second.id, first.id],
        )
        self.assertEqual(
            [attachment.id for attachment in self.service.list(attachment_types=[AttachmentType.AI_ANALYSIS])],
            [third.id, second.id],
        )
        self.assertEqual(
            [attachment.id for attachment in self.service.list(statuses=[ExecutionStatus.FAILED])],
            [second.id],
        )
        self.assertEqual(
            [
                attachment.id
                for attachment in self.service.list(
                    attachment_types=[AttachmentType.AI_ANALYSIS, AttachmentType.FIELD_STATISTICS],
                    statuses=[ExecutionStatus.SUCCESS, ExecutionStatus.FAILED],
                    keyword="AI",
                    conversation_uid=str(self.conversation.uid),
                    source_message_uid=str(self.source_message.uid),
                )
            ],
            [third.id, second.id],
        )

    def test_list_prefetches_relations_and_defers_large_fields_in_constant_queries(self):
        self.register_sync_handler()
        self.register_async_handler()
        for index in range(20):
            source_message = self.create_source_message()
            self.create_attachment(
                source_message=source_message,
                attachment_type=AttachmentType.FIELD_STATISTICS if index % 2 == 0 else AttachmentType.AI_ANALYSIS,
                title=f"attachment-{index}",
                content_updated_at=timezone.now() + timedelta(seconds=index),
            )

        with self.assertNumQueries(1):
            attachments = list(self.service.list())
            serialized_attachments = AttachmentListItemSerializer(attachments, many=True).data
            conversation_ids = [attachment.source_message.conversation.id for attachment in attachments]

        self.assertEqual(len(attachments), 20)
        self.assertEqual(len(serialized_attachments), 20)
        self.assertEqual(len(conversation_ids), 20)
        required_deferred_fields = {
            "input_data",
            "context_data",
            "output_data",
            "stream_config",
            "stream_archive",
        }
        for attachment in attachments:
            self.assertTrue(required_deferred_fields.issubset(attachment.get_deferred_fields()))

    def test_update_title_only_allows_all_statuses_and_rejects_invalid_title(self):
        self.register_async_handler()
        for status in (ExecutionStatus.PROCESSING, ExecutionStatus.SUCCESS, ExecutionStatus.FAILED):
            with self.subTest(status=status):
                attachment = self.create_attachment(
                    attachment_type=AttachmentType.AI_ANALYSIS,
                    status=status,
                    task_id="task-current" if status != ExecutionStatus.SUCCESS else None,
                    title="旧标题",
                )
                before_updated_at = attachment.content_updated_at

                updated = self.service.update(attachment_uid=str(attachment.uid), title="  新标题  ")

                self.assertEqual(updated.title, "新标题")
                self.assertGreaterEqual(updated.content_updated_at, before_updated_at)

        attachment = self.create_attachment(attachment_type=AttachmentType.AI_ANALYSIS)
        for invalid_title in ("   ", "x" * 256):
            with self.subTest(invalid_title=invalid_title), self.assertRaises(InvalidAttachmentPreparation):
                self.service.update(attachment_uid=str(attachment.uid), title=invalid_title)

    def test_update_output_requires_success_editable_handler_and_valid_payload(self):
        attachment = self.create_attachment(
            attachment_type=AttachmentType.FIELD_STATISTICS,
            status=ExecutionStatus.SUCCESS,
            output_data={"content": "old"},
        )
        self.register_sync_handler()
        with self.assertRaises(AttachmentNotEditable):
            self.service.update(
                attachment_uid=str(attachment.uid),
                output_data={"content": "submitted"},
            )

        attachment_handler_registry.unregister(AttachmentType.FIELD_STATISTICS)
        attachment_handler_registry.register(EditableAttachmentEchoHandler())
        for status in (ExecutionStatus.PROCESSING, ExecutionStatus.FAILED):
            with self.subTest(status=status):
                invalid_attachment = self.create_attachment(
                    attachment_type=AttachmentType.FIELD_STATISTICS,
                    status=status,
                    task_id="task-processing" if status == ExecutionStatus.PROCESSING else "task-failed",
                    output_data=None if status == ExecutionStatus.PROCESSING else {"content": "failed"},
                )
                with self.assertRaises(InvalidAttachmentState):
                    self.service.update(
                        attachment_uid=str(invalid_attachment.uid),
                        output_data={"content": "submitted"},
                    )

        with self.assertRaises(AttachmentSnapshotValidationError):
            self.service.update(
                attachment_uid=str(attachment.uid),
                output_data={"invalid": True},
            )

        attachment_handler_registry.unregister(AttachmentType.FIELD_STATISTICS)
        attachment_handler_registry.register(InvalidReturnEditableAttachmentHandler())
        with self.assertRaises(AttachmentOutputValidationError):
            self.service.update(
                attachment_uid=str(attachment.uid),
                output_data={"content": "submitted"},
            )

    def test_attachment_service_is_exported_from_services_package(self):
        self.assertIs(ai_assistant_services.AttachmentService, AttachmentService)

    def test_update_distinguishes_null_output_from_valid_empty_object(self):
        handler = EmptyObjectEditableAttachmentHandler()
        attachment_handler_registry.register(handler)
        null_output_attachment = self.create_attachment(
            attachment_type=AttachmentType.FIELD_STATISTICS,
            status=ExecutionStatus.SUCCESS,
            output_data=None,
        )

        with self.assertRaises(AttachmentOutputValidationError):
            self.service.update(
                attachment_uid=str(null_output_attachment.uid),
                output_data={},
            )

        self.assertEqual(handler.edit_calls, 0)
        empty_object_attachment = self.create_attachment(
            attachment_type=AttachmentType.FIELD_STATISTICS,
            status=ExecutionStatus.SUCCESS,
            output_data={},
        )

        updated = self.service.update(
            attachment_uid=str(empty_object_attachment.uid),
            output_data={},
        )

        self.assertEqual(handler.edit_calls, 1)
        self.assertEqual(updated.output_data, {})

    def test_update_combines_title_and_output_in_one_update_without_touching_internal_fields(self):
        attachment = self.create_attachment(
            attachment_type=AttachmentType.FIELD_STATISTICS,
            status=ExecutionStatus.SUCCESS,
            task_id=None,
            title="旧标题",
            output_data={"content": "old"},
        )
        attachment_handler_registry.register(EditableAttachmentEchoHandler())
        before_content_updated_at = attachment.content_updated_at
        original_input = attachment.input_data
        original_context = attachment.context_data
        original_status = attachment.status
        original_task_id = attachment.task_id

        with CaptureQueriesContext(connection) as captured:
            updated = self.service.update(
                attachment_uid=str(attachment.uid),
                title="新标题",
                output_data={"content": "new"},
            )

        update_queries = [
            query["sql"] for query in captured.captured_queries if query["sql"].strip().upper().startswith("UPDATE ")
        ]
        self.assertEqual(len(update_queries), 1)
        self.assertEqual(updated.title, "新标题")
        self.assertEqual(updated.output_data, {"content": "new"})
        self.assertEqual(updated.input_data, original_input)
        self.assertEqual(updated.context_data, original_context)
        self.assertEqual(updated.status, original_status)
        self.assertEqual(updated.task_id, original_task_id)
        self.assertGreater(updated.content_updated_at, before_content_updated_at)

    def test_update_last_write_wins_without_row_lock(self):
        attachment = self.create_attachment(
            attachment_type=AttachmentType.FIELD_STATISTICS,
            status=ExecutionStatus.SUCCESS,
            title="第一次",
            output_data={"content": "old"},
        )
        attachment_handler_registry.register(EditableAttachmentEchoHandler())

        with CaptureQueriesContext(connection) as captured:
            self.service.update(attachment_uid=str(attachment.uid), title="第二次")
            updated = self.service.update(
                attachment_uid=str(attachment.uid),
                title="第三次",
                output_data={"content": "latest"},
            )

        lock_queries = [query["sql"] for query in captured.captured_queries if "FOR UPDATE" in query["sql"].upper()]
        self.assertEqual(lock_queries, [])
        self.assertEqual(updated.title, "第三次")
        self.assertEqual(updated.output_data, {"content": "latest"})

    def test_retry_only_allows_failed_async_and_preserves_snapshots_without_prepare(self):
        handler = self.register_async_handler()
        self.register_sync_handler()
        for attachment in (
            self.create_attachment(
                attachment_type=AttachmentType.AI_ANALYSIS,
                status=ExecutionStatus.PROCESSING,
                task_id="task-processing",
                output_data=None,
            ),
            self.create_attachment(
                attachment_type=AttachmentType.AI_ANALYSIS,
                status=ExecutionStatus.SUCCESS,
                task_id=None,
                output_data={"content": "done"},
            ),
            self.create_attachment(
                attachment_type=AttachmentType.FIELD_STATISTICS,
                status=ExecutionStatus.FAILED,
                task_id="task-sync",
            ),
        ):
            with self.subTest(status=attachment.status, mode=attachment.attachment_type), self.assertRaises(
                InvalidAttachmentState
            ):
                self.service.retry(attachment_uid=str(attachment.uid))

        failed_attachment = self.create_attachment(
            attachment_type=AttachmentType.AI_ANALYSIS,
            status=ExecutionStatus.FAILED,
            task_id="task-old",
            title="旧标题",
            output_data={"content": "failed"},
            stream_config={"step": 1},
            stream_archive=[{"delta": "old"}],
        )
        old_created_at = failed_attachment.created_at
        old_source_message_id = failed_attachment.source_message_id
        old_input_data = failed_attachment.input_data
        old_context_data = failed_attachment.context_data
        old_task_id = failed_attachment.task_id
        old_content_updated_at = failed_attachment.content_updated_at

        with mock.patch.object(handler.async_task, "apply_async") as apply_async:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                retried = self.service.retry(attachment_uid=str(failed_attachment.uid))

            apply_async.assert_not_called()
            self.assertEqual(len(callbacks), 1)
            callbacks[0]()

        self.assertEqual(handler.prepare_calls, 0)
        self.assertEqual(retried.status, ExecutionStatus.PROCESSING)
        self.assertEqual(retried.source_message_id, old_source_message_id)
        self.assertEqual(retried.input_data, old_input_data)
        self.assertEqual(retried.context_data, old_context_data)
        self.assertEqual(retried.title, "旧标题")
        self.assertEqual(retried.created_at, old_created_at)
        self.assertNotEqual(retried.task_id, old_task_id)
        self.assertIsNone(retried.output_data)
        self.assertEqual(retried.error_code, "")
        self.assertEqual(retried.error_message, "")
        self.assertEqual(retried.stream_config, {})
        self.assertEqual(retried.stream_archive, [])
        self.assertGreater(retried.content_updated_at, old_content_updated_at)
        apply_async.assert_called_once_with(
            kwargs={"attachment_id": retried.id, "task_id": retried.task_id},
            task_id=retried.task_id,
        )

    def test_retry_does_not_use_for_update(self):
        self.register_async_handler()
        attachment = self.create_attachment(
            attachment_type=AttachmentType.AI_ANALYSIS,
            status=ExecutionStatus.FAILED,
            task_id="task-old",
            output_data={"content": "failed"},
        )

        with CaptureQueriesContext(connection) as captured, mock.patch(
            "services.web.ai_assistant.services.attachment.transaction.on_commit"
        ):
            self.service.retry(attachment_uid=str(attachment.uid))

        lock_queries = [query["sql"] for query in captured.captured_queries if "FOR UPDATE" in query["sql"].upper()]
        self.assertEqual(lock_queries, [])

    def test_old_task_id_cannot_overwrite_new_retry_task(self):
        self.register_async_handler()
        attachment = self.create_attachment(
            attachment_type=AttachmentType.AI_ANALYSIS,
            status=ExecutionStatus.FAILED,
            task_id="task-old",
            output_data={"content": "failed"},
        )
        old_task_id = attachment.task_id

        with mock.patch("services.web.ai_assistant.services.attachment.transaction.on_commit"):
            retried = self.service.retry(attachment_uid=str(attachment.uid))
        new_task_id = retried.task_id

        updated = finish_attachment_failure(
            attachment_id=retried.id,
            task_id=old_task_id,
            exception=RuntimeError("old task"),
        )

        retried.refresh_from_db()
        self.assertFalse(updated)
        self.assertEqual(retried.status, ExecutionStatus.PROCESSING)
        self.assertEqual(retried.task_id, new_task_id)
        self.assertNotEqual(retried.task_id, old_task_id)

    def test_retry_dispatch_failure_returns_failed_instance_and_can_retry_again(self):
        handler = self.register_async_handler()
        attachment = self.create_attachment(
            attachment_type=AttachmentType.AI_ANALYSIS,
            status=ExecutionStatus.FAILED,
            task_id="task-old",
            output_data={"content": "failed"},
        )

        with mock.patch.object(handler.async_task, "apply_async", side_effect=RuntimeError("broker secret")):
            with self.captureOnCommitCallbacks(execute=True):
                failed = self.service.retry(attachment_uid=str(attachment.uid))

        self.assertEqual(failed.status, ExecutionStatus.FAILED)
        self.assertEqual(failed.error_code, AttachmentErrorCode.TASK_DISPATCH_FAILED)
        failed_task_id = failed.task_id

        with mock.patch.object(handler.async_task, "apply_async") as apply_async:
            with self.captureOnCommitCallbacks(execute=True):
                retried = self.service.retry(attachment_uid=str(attachment.uid))

        self.assertEqual(retried.status, ExecutionStatus.PROCESSING)
        self.assertNotEqual(retried.task_id, failed_task_id)
        apply_async.assert_called_once_with(
            kwargs={"attachment_id": retried.id, "task_id": retried.task_id},
            task_id=retried.task_id,
        )


class AttachmentServiceConcurrencyTest(TransactionTestCase):
    """使用独立连接验证两个请求都读到旧快照时，只有一个 CAS 更新成功。"""

    available_apps = ["services.web.ai_assistant"]
    reset_sequences = True

    def setUp(self):
        self.user = "alice"
        self.service = AttachmentService(user=self.user)
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
        attachment_handler_registry.register(RecordingAttachmentAsyncHandler())

    def tearDown(self):
        for attachment_type in AttachmentType.values:
            attachment_handler_registry.unregister(attachment_type)

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

    def test_retry_concurrent_requests_only_one_cas_wins_after_shared_old_snapshot(self):
        attachment = Attachment.objects.create(
            source_message=self.source_message,
            attachment_type=AttachmentType.AI_ANALYSIS,
            title="原始标题",
            status=ExecutionStatus.FAILED,
            task_id="task-old",
            input_data={"text": "hello"},
            context_data={"prefix": "ctx"},
            output_data={"content": "failed"},
            error_code="OLD_CODE",
            error_message="old error",
            content_updated_at=timezone.now(),
            created_by=self.user,
            updated_by=self.user,
        )
        barrier = threading.Barrier(2)
        original_get = AttachmentService.get

        def synchronized_get(service, *, attachment_uid):
            loaded_attachment = original_get(service, attachment_uid=attachment_uid)
            barrier.wait(timeout=5)
            return loaded_attachment

        def retry_once():
            return AttachmentService(user=self.user).retry(attachment_uid=str(attachment.uid))

        with mock.patch.object(
            AttachmentService, "get", autospec=True, side_effect=synchronized_get
        ), mock.patch.object(AttachmentService, "_dispatch") as dispatch:
            threads, results, errors = self.run_threads(retry_once, retry_once)

        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(len(results), 1)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], InvalidAttachmentState)
        self.assertEqual(dispatch.call_count, 1)

        attachment.refresh_from_db()
        self.assertEqual(attachment.status, ExecutionStatus.PROCESSING)
        self.assertEqual(attachment.task_id, results[0].task_id)
        self.assertNotEqual(attachment.task_id, "task-old")
