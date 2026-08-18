from unittest import mock

from celery.exceptions import Ignore, MaxRetriesExceededError, Retry
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.test.utils import CaptureQueriesContext

from services.web.ai_assistant.constants import (
    AttachmentErrorCode,
    AttachmentType,
    ExecutionStatus,
    MessageType,
)
from services.web.ai_assistant.exceptions import (
    AttachmentExecutionFailed,
    AttachmentOutputValidationError,
    AttachmentSnapshotValidationError,
    InvalidAttachmentState,
    StaleAttachmentTask,
)
from services.web.ai_assistant.handlers import attachment_handler_registry
from services.web.ai_assistant.models import Attachment, Conversation, Message
from services.web.ai_assistant.services.attachment_execution import (
    finish_attachment_failure,
    finish_attachment_success,
    load_attachment_execution,
)
from services.web.ai_assistant.tasks import AttachmentExecutionTask, BaseExecutionTask
from tests.base import TestCase
from tests.test_ai_assistant.handlers import (
    AttachmentEchoContext,
    AttachmentEchoInput,
    AttachmentEchoOutput,
    EchoAttachmentAsyncHandler,
    RetryableAttachmentError,
    execute_attachment_async_autoretry,
    execute_attachment_async_execution_failed,
    execute_attachment_async_failure,
    execute_attachment_async_platform_error,
    execute_attachment_async_retry,
    execute_attachment_async_retry_exhausted,
    execute_attachment_async_retry_without_exc,
    execute_attachment_async_success,
    execute_attachment_async_update_title,
)


class AttachmentTaskTest(TestCase):
    def setUp(self):
        self.user = "alice"
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
        self.handler = EchoAttachmentAsyncHandler()
        attachment_handler_registry.register(self.handler)

    def tearDown(self):
        attachment_handler_registry.unregister(AttachmentType.AI_ANALYSIS)

    def create_attachment(self, *, task_id: str = "task-current") -> Attachment:
        return Attachment.objects.create(
            source_message=self.source_message,
            attachment_type=AttachmentType.AI_ANALYSIS,
            title="AI 分析",
            status=ExecutionStatus.PROCESSING,
            task_id=task_id,
            input_data={"text": "hello"},
            context_data={"prefix": "async"},
            output_data=None,
            created_by=self.user,
            updated_by=self.user,
        )

    def test_attachment_task_declares_execution_protocol(self):
        self.assertTrue(issubclass(AttachmentExecutionTask, BaseExecutionTask))
        self.assertEqual(AttachmentExecutionTask.id_argument, "attachment_id")
        self.assertIs(AttachmentExecutionTask.stale_exception, StaleAttachmentTask)
        self.assertEqual(AttachmentExecutionTask.object_label, "附件")
        self.assertNotIn("executor", AttachmentExecutionTask.__dict__)
        for method_name in ("_load_execution", "_finish_success", "_finish_failure"):
            self.assertIn(method_name, AttachmentExecutionTask.__dict__)

    @staticmethod
    def invoke(task, *, attachment: Attachment, celery_task_id: str | None = None, retries: int = 0):
        task_kwargs = {"attachment_id": attachment.id, "task_id": attachment.task_id}
        task.push_request(
            id=celery_task_id or attachment.task_id,
            retries=retries,
            called_directly=False,
            is_eager=True,
            args=(),
            kwargs=task_kwargs,
        )
        try:
            return task(**task_kwargs)
        finally:
            task.pop_request()

    def test_success_task_accepts_dict_or_output_model_and_marks_success(self):
        for return_value in ({"content": "done"}, AttachmentEchoOutput(content="done")):
            with self.subTest(return_value=return_value):
                attachment = self.create_attachment(task_id=f"task-{Attachment.objects.count()}")
                with mock.patch.object(execute_attachment_async_success, "run", return_value=return_value):
                    result = self.invoke(execute_attachment_async_success, attachment=attachment)

                attachment.refresh_from_db()
                self.assertEqual(result, {"content": "done"})
                self.assertEqual(attachment.status, ExecutionStatus.SUCCESS)
                self.assertEqual(attachment.output_data, {"content": "done"})

    def test_invalid_output_marks_failed_without_partial_output(self):
        attachment = self.create_attachment()

        with mock.patch.object(execute_attachment_async_success, "run", return_value={"invalid": True}):
            with self.assertRaises(AttachmentOutputValidationError):
                self.invoke(execute_attachment_async_success, attachment=attachment)

        attachment.refresh_from_db()
        self.assertEqual(attachment.status, ExecutionStatus.FAILED)
        self.assertIsNone(attachment.output_data)
        self.assertEqual(attachment.error_code, AttachmentErrorCode.OUTPUT_VALIDATION_FAILED)
        self.assertEqual(attachment.error_message, "附件产物格式错误")

    def test_invalid_stored_snapshot_marks_failed_before_business_execution(self):
        attachment = self.create_attachment()
        Attachment.objects.filter(id=attachment.id).update(context_data={"invalid": True})

        with mock.patch.object(execute_attachment_async_success, "run") as run:
            with self.assertRaises(AttachmentSnapshotValidationError):
                self.invoke(execute_attachment_async_success, attachment=attachment)

        attachment.refresh_from_db()
        run.assert_not_called()
        self.assertEqual(attachment.status, ExecutionStatus.FAILED)
        self.assertEqual(attachment.error_code, AttachmentSnapshotValidationError().code)
        self.assertEqual(attachment.error_message, "附件数据格式错误")

    def test_unknown_exception_marks_failed_without_private_detail(self):
        attachment = self.create_attachment()

        with self.assertRaises(RuntimeError):
            self.invoke(execute_attachment_async_failure, attachment=attachment)

        attachment.refresh_from_db()
        self.assertEqual(attachment.status, ExecutionStatus.FAILED)
        self.assertEqual(attachment.error_code, AttachmentErrorCode.TASK_EXECUTION_FAILED)
        self.assertEqual(attachment.error_message, "附件执行失败，请稍后重试")
        self.assertNotIn("private detail", attachment.error_message)

    def test_platform_exception_keeps_public_code_and_message(self):
        attachment = self.create_attachment()

        with self.assertRaises(InvalidAttachmentState):
            self.invoke(execute_attachment_async_platform_error, attachment=attachment)

        attachment.refresh_from_db()
        self.assertEqual(attachment.status, ExecutionStatus.FAILED)
        self.assertEqual(attachment.error_code, InvalidAttachmentState().code)
        self.assertEqual(attachment.error_message, "可公开的附件错误")

    def test_attachment_execution_failed_keeps_public_code_and_message(self):
        attachment = self.create_attachment()

        with self.assertRaises(AttachmentExecutionFailed):
            self.invoke(execute_attachment_async_execution_failed, attachment=attachment)

        attachment.refresh_from_db()
        self.assertEqual(attachment.status, ExecutionStatus.FAILED)
        self.assertEqual(attachment.error_code, AttachmentExecutionFailed().code)
        self.assertEqual(attachment.error_message, "可公开的执行失败")

    def test_retry_keeps_processing_then_next_execution_succeeds(self):
        attachment = self.create_attachment()

        with self.assertRaises(Retry) as caught:
            self.invoke(execute_attachment_async_retry, attachment=attachment)
        attachment.refresh_from_db()
        self.assertEqual(attachment.status, ExecutionStatus.PROCESSING)
        self.assertEqual(
            caught.exception.sig.kwargs,
            {"attachment_id": attachment.id, "task_id": attachment.task_id},
        )

        result = self.invoke(execute_attachment_async_retry, attachment=attachment, retries=1)

        attachment.refresh_from_db()
        self.assertEqual(result, {"content": "async:hello"})
        self.assertEqual(attachment.status, ExecutionStatus.SUCCESS)

    def test_retry_with_exception_marks_failed_after_max_retries(self):
        attachment = self.create_attachment()

        with self.assertRaisesRegex(RuntimeError, "retry exhausted private detail"):
            self.invoke(execute_attachment_async_retry_exhausted, attachment=attachment, retries=2)

        attachment.refresh_from_db()
        self.assertEqual(attachment.status, ExecutionStatus.FAILED)
        self.assertEqual(attachment.error_code, AttachmentErrorCode.TASK_EXECUTION_FAILED)
        self.assertEqual(attachment.error_message, "附件执行失败，请稍后重试")

    def test_retry_without_exception_marks_failed_after_max_retries(self):
        attachment = self.create_attachment()

        with self.assertRaises(MaxRetriesExceededError):
            self.invoke(execute_attachment_async_retry_without_exc, attachment=attachment, retries=2)

        attachment.refresh_from_db()
        self.assertEqual(attachment.status, ExecutionStatus.FAILED)
        self.assertEqual(attachment.error_code, AttachmentErrorCode.TASK_EXECUTION_FAILED)

    def test_autoretry_keeps_processing_and_marks_failed_after_max_retries(self):
        attachment = self.create_attachment()

        with self.assertRaises(Retry):
            self.invoke(execute_attachment_async_autoretry, attachment=attachment)
        attachment.refresh_from_db()
        self.assertEqual(attachment.status, ExecutionStatus.PROCESSING)

        with self.assertRaises(RetryableAttachmentError):
            self.invoke(execute_attachment_async_autoretry, attachment=attachment, retries=2)
        attachment.refresh_from_db()
        self.assertEqual(attachment.status, ExecutionStatus.FAILED)
        self.assertEqual(attachment.error_code, AttachmentErrorCode.TASK_EXECUTION_FAILED)

    def test_mismatched_celery_task_id_does_not_execute_or_update(self):
        attachment = self.create_attachment()

        with mock.patch.object(execute_attachment_async_success, "run") as run:
            with self.assertRaises(Ignore):
                self.invoke(execute_attachment_async_success, attachment=attachment, celery_task_id="task-old")

        attachment.refresh_from_db()
        run.assert_not_called()
        self.assertEqual(attachment.status, ExecutionStatus.PROCESSING)

    def test_old_task_id_delivery_is_ignored(self):
        attachment = self.create_attachment(task_id="task-old")
        Attachment.objects.filter(id=attachment.id).update(task_id="task-new")

        with mock.patch.object(execute_attachment_async_success, "run") as run:
            with self.assertRaises(Ignore):
                self.invoke(execute_attachment_async_success, attachment=attachment)

        attachment.refresh_from_db()
        run.assert_not_called()
        self.assertEqual(attachment.task_id, "task-new")
        self.assertEqual(attachment.status, ExecutionStatus.PROCESSING)

    def test_terminal_attachment_duplicate_delivery_is_ignored(self):
        for status in (ExecutionStatus.SUCCESS, ExecutionStatus.FAILED):
            with self.subTest(status=status):
                attachment = self.create_attachment(task_id=f"task-{status}")
                Attachment.objects.filter(id=attachment.id).update(status=status)
                with mock.patch.object(execute_attachment_async_success, "run") as run:
                    with self.assertRaises(Ignore):
                        self.invoke(execute_attachment_async_success, attachment=attachment)
                run.assert_not_called()

    def test_first_terminal_update_wins_when_workers_execute_concurrently(self):
        attachment = self.create_attachment()

        first_execution = load_attachment_execution(
            attachment_id=attachment.id,
            task_id=attachment.task_id,
            celery_task_id=attachment.task_id,
        )
        load_attachment_execution(
            attachment_id=attachment.id,
            task_id=attachment.task_id,
            celery_task_id=attachment.task_id,
        )
        finish_attachment_success(
            execution=first_execution,
            task_id=attachment.task_id,
            output_data={"content": "first"},
        )
        updated = finish_attachment_failure(
            attachment_id=attachment.id,
            task_id=attachment.task_id,
            exception=RuntimeError("second worker failed"),
        )

        attachment.refresh_from_db()
        self.assertFalse(updated)
        self.assertEqual(attachment.status, ExecutionStatus.SUCCESS)
        self.assertEqual(attachment.output_data, {"content": "first"})

    def test_success_cannot_overwrite_failure_written_by_another_worker(self):
        attachment = self.create_attachment()
        execution = load_attachment_execution(
            attachment_id=attachment.id,
            task_id=attachment.task_id,
            celery_task_id=attachment.task_id,
        )

        updated = finish_attachment_failure(
            attachment_id=attachment.id,
            task_id=attachment.task_id,
            exception=RuntimeError("first worker failed"),
        )
        with self.assertRaises(StaleAttachmentTask):
            finish_attachment_success(
                execution=execution,
                task_id=attachment.task_id,
                output_data={"content": "second"},
            )

        attachment.refresh_from_db()
        self.assertTrue(updated)
        self.assertEqual(attachment.status, ExecutionStatus.FAILED)
        self.assertIsNone(attachment.output_data)

    def test_task_can_save_title_explicitly(self):
        attachment = self.create_attachment()

        result = self.invoke(execute_attachment_async_update_title, attachment=attachment)

        attachment.refresh_from_db()
        self.assertEqual(result, {"content": "async:hello"})
        self.assertEqual(attachment.title, "任务内更新标题")
        self.assertEqual(attachment.status, ExecutionStatus.SUCCESS)

    def test_missing_task_arguments_are_configuration_error(self):
        execute_attachment_async_success.push_request(id="task-current", retries=0)
        try:
            with self.assertRaises(ImproperlyConfigured):
                execute_attachment_async_success(attachment_id=1)
        finally:
            execute_attachment_async_success.pop_request()

    def test_load_execution_uses_one_query_and_preloads_source_message_conversation(self):
        attachment = self.create_attachment()

        with CaptureQueriesContext(connection) as captured:
            execution = load_attachment_execution(
                attachment_id=attachment.id,
                task_id=attachment.task_id,
                celery_task_id=attachment.task_id,
            )
            self.assertEqual(execution.source_message.id, self.source_message.id)
            self.assertEqual(execution.source_message.conversation.id, self.conversation.id)
            self.assertIsInstance(execution.input_data, AttachmentEchoInput)
            self.assertIsInstance(execution.context_data, AttachmentEchoContext)

        self.assertEqual(len(captured), 1)
