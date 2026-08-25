from contextlib import nullcontext
from unittest import mock

from celery.exceptions import Ignore, MaxRetriesExceededError, Retry
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError

from core.exceptions import ValidationError as CoreValidationError
from services.web.ai_assistant.constants import (
    ExecutionStatus,
    MessageErrorCode,
    MessageType,
)
from services.web.ai_assistant.exceptions import (
    InvalidParentMessage,
    MessageExecutionFailed,
    MessageSnapshotValidationError,
    StaleMessageTask,
)
from services.web.ai_assistant.handlers import message_handler_registry
from services.web.ai_assistant.models import Conversation, Message
from services.web.ai_assistant.services.message_execution import (
    finish_message_failure,
    finish_message_success,
    load_message_execution,
)
from services.web.ai_assistant.tasks import BaseExecutionTask, MessageExecutionTask
from tests.base import TestCase
from tests.test_ai_assistant.handlers import (
    EchoAsyncHandler,
    EchoContext,
    EchoInput,
    EchoOutput,
    RetryableEchoError,
    execute_async_autoretry,
    execute_async_failure,
    execute_async_retry,
    execute_async_retry_exhausted,
    execute_async_retry_without_exc,
    execute_async_success,
)


class MessageTaskTest(TestCase):
    def setUp(self):
        self.user = "alice"
        self.conversation = Conversation.objects.create(created_by=self.user, updated_by=self.user)
        self.handler = EchoAsyncHandler()
        message_handler_registry.register(self.handler)

    def tearDown(self):
        message_handler_registry.unregister(MessageType.NATURAL_LANGUAGE_SEARCH)

    def create_message(self, *, task_id: str = "task-current") -> Message:
        return Message.objects.create(
            conversation=self.conversation,
            message_type=MessageType.NATURAL_LANGUAGE_SEARCH,
            status=ExecutionStatus.PROCESSING,
            task_id=task_id,
            input_data={"text": "hello"},
            context_data={"prefix": "async"},
            output_data=None,
            created_by=self.user,
            updated_by=self.user,
        )

    def test_message_task_declares_execution_protocol(self):
        self.assertTrue(issubclass(MessageExecutionTask, BaseExecutionTask))
        self.assertEqual(MessageExecutionTask.id_argument, "message_id")
        self.assertIs(MessageExecutionTask.stale_exception, StaleMessageTask)
        self.assertEqual(MessageExecutionTask.object_label, "消息")
        self.assertNotIn("executor", MessageExecutionTask.__dict__)
        for method_name in ("_load_execution", "_finish_success", "_finish_failure"):
            self.assertIn(method_name, MessageExecutionTask.__dict__)

    def test_task_marks_worker_start_and_refreshes_activity_on_retry(self):
        message = self.create_message()

        with self.assertRaises(Retry):
            self.invoke(execute_async_retry, message=message)

        message.refresh_from_db()
        self.assertIsNotNone(message.started_at)
        self.assertIsNotNone(message.last_activity_at)
        self.assertGreaterEqual(message.last_activity_at, message.started_at)
        self.assertIsNone(message.finished_at)

    @mock.patch("services.web.ai_assistant.services.message_execution.report_execution_finished")
    def test_terminal_metric_is_reported_only_by_cas_winner(self, report_execution_finished):
        message = self.create_message()

        self.invoke(execute_async_success, message=message)
        with self.assertRaises(Ignore):
            self.invoke(execute_async_success, message=message)

        report_execution_finished.assert_called_once()
        self.assertEqual(report_execution_finished.call_args.args[0].status, ExecutionStatus.SUCCESS)

    @mock.patch("services.web.ai_assistant.services.message_execution.report_invariant_violation")
    def test_invalid_output_reports_invariant_violation(self, report_invariant_violation):
        message = self.create_message()

        with mock.patch.object(execute_async_success, "run", return_value={"invalid": True}):
            with self.assertRaises(MessageExecutionFailed):
                self.invoke(execute_async_success, message=message)

        report_invariant_violation.assert_called_once()

    @mock.patch("services.web.ai_assistant.services.message_execution.report_invariant_violation")
    def test_invalid_output_invariant_is_reported_only_by_failure_cas_winner(self, report_invariant_violation):
        message = self.create_message()
        validation_error = MessageSnapshotValidationError()
        execution_error = MessageExecutionFailed(message="任务执行结果格式错误")
        execution_error.__cause__ = validation_error

        self.assertTrue(
            finish_message_failure(
                message_id=message.id,
                task_id=message.task_id,
                exception=execution_error,
            )
        )
        self.assertFalse(
            finish_message_failure(
                message_id=message.id,
                task_id=message.task_id,
                exception=execution_error,
            )
        )
        report_invariant_violation.assert_called_once()

    @mock.patch("services.web.ai_assistant.tasks.base.start_execution_span")
    def test_task_wraps_execution_with_platform_span(self, start_execution_span):
        message = self.create_message()
        start_execution_span.return_value = nullcontext()

        self.invoke(execute_async_success, message=message)

        start_execution_span.assert_called_once()
        self.assertEqual(start_execution_span.call_args.kwargs["object_type"], "MESSAGE")
        self.assertEqual(start_execution_span.call_args.kwargs["task_id"], message.task_id)

    @staticmethod
    def invoke(task, *, message: Message, celery_task_id: str | None = None, retries: int = 0):
        """在进程内模拟 Celery 投递，并允许显式推进重试次数。"""

        task_kwargs = {"message_id": message.id, "task_id": message.task_id}
        task.push_request(
            id=celery_task_id or message.task_id,
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
        for return_value in ({"content": "done"}, EchoOutput(content="done")):
            with self.subTest(return_value=return_value):
                message = self.create_message(task_id=f"task-{Message.objects.count()}")
                with mock.patch.object(execute_async_success, "run", return_value=return_value):
                    result = self.invoke(execute_async_success, message=message)

                message.refresh_from_db()
                self.assertEqual(result, {"content": "done"})
                self.assertEqual(message.status, ExecutionStatus.SUCCESS)
                self.assertEqual(message.output_data, {"content": "done"})

    def test_invalid_output_marks_failed_without_partial_output(self):
        message = self.create_message()

        with mock.patch.object(execute_async_success, "run", return_value={"invalid": True}):
            with self.assertRaises(MessageExecutionFailed):
                self.invoke(execute_async_success, message=message)

        message.refresh_from_db()
        self.assertEqual(message.status, ExecutionStatus.FAILED)
        self.assertIsNone(message.output_data)
        self.assertEqual(message.error_code, MessageErrorCode.TASK_EXECUTION_FAILED)
        self.assertEqual(message.error_message, "任务执行结果格式错误")

    def test_invalid_stored_snapshot_marks_failed_before_business_execution(self):
        message = self.create_message()
        Message.objects.filter(id=message.id).update(context_data={"invalid": True})

        with self.assertRaises(MessageSnapshotValidationError):
            self.invoke(execute_async_success, message=message)

        message.refresh_from_db()
        self.assertEqual(message.status, ExecutionStatus.FAILED)
        self.assertEqual(message.error_code, MessageSnapshotValidationError().code)
        self.assertEqual(message.error_message, "消息数据格式错误")

    def test_unknown_exception_marks_failed_without_private_detail(self):
        message = self.create_message()

        with self.assertRaises(RuntimeError):
            self.invoke(execute_async_failure, message=message)

        message.refresh_from_db()
        self.assertEqual(message.status, ExecutionStatus.FAILED)
        self.assertEqual(message.error_code, MessageErrorCode.TASK_EXECUTION_FAILED)
        self.assertEqual(message.error_message, "消息执行失败，请稍后重试")
        self.assertNotIn("private detail", message.error_message)

    def test_platform_exception_keeps_public_code_and_message(self):
        message = self.create_message()
        error = InvalidParentMessage(message="可公开的任务错误")

        updated = finish_message_failure(message_id=message.id, task_id=message.task_id, exception=error)

        message.refresh_from_db()
        self.assertTrue(updated)
        self.assertEqual(message.error_code, error.code)
        self.assertEqual(message.error_message, "可公开的任务错误")

    def test_non_platform_blue_exception_is_sanitized(self):
        message = self.create_message()
        error = CoreValidationError(message="upstream private detail")

        finish_message_failure(message_id=message.id, task_id=message.task_id, exception=error)

        message.refresh_from_db()
        self.assertEqual(message.error_code, MessageErrorCode.TASK_EXECUTION_FAILED)
        self.assertEqual(message.error_message, "消息执行失败，请稍后重试")

    def test_retry_keeps_processing_then_next_execution_succeeds(self):
        message = self.create_message()

        # 第一轮执行真实业务 Task 的 self.retry()，平台只向上抛出 Retry。
        with self.assertRaises(Retry) as caught:
            self.invoke(execute_async_retry, message=message)
        message.refresh_from_db()
        self.assertEqual(message.status, ExecutionStatus.PROCESSING)
        self.assertEqual(message.task_id, "task-current")
        self.assertEqual(
            caught.exception.sig.kwargs,
            {"message_id": message.id, "task_id": message.task_id},
        )

        # Celery 使用相同 task ID 重投，并通过 request.retries 暴露当前轮次。
        result = self.invoke(execute_async_retry, message=message, retries=1)

        message.refresh_from_db()
        self.assertEqual(result, {"content": "async:hello"})
        self.assertEqual(message.status, ExecutionStatus.SUCCESS)

    @mock.patch.object(Message, "touch_processing", side_effect=DatabaseError("database unavailable"))
    def test_retry_activity_failure_does_not_replace_retry(self, _touch_processing):
        message = self.create_message()

        with self.assertRaises(Retry):
            self.invoke(execute_async_retry, message=message)

    def test_retry_with_exception_marks_failed_after_max_retries(self):
        message = self.create_message()

        with self.assertRaisesRegex(RuntimeError, "retry exhausted private detail"):
            self.invoke(execute_async_retry_exhausted, message=message, retries=2)

        message.refresh_from_db()
        self.assertEqual(message.status, ExecutionStatus.FAILED)
        self.assertEqual(message.error_code, MessageErrorCode.TASK_EXECUTION_FAILED)
        self.assertEqual(message.error_message, "消息执行失败，请稍后重试")

    def test_retry_without_exception_marks_failed_after_max_retries(self):
        message = self.create_message()

        with self.assertRaises(MaxRetriesExceededError):
            self.invoke(execute_async_retry_without_exc, message=message, retries=2)

        message.refresh_from_db()
        self.assertEqual(message.status, ExecutionStatus.FAILED)
        self.assertEqual(message.error_code, MessageErrorCode.TASK_EXECUTION_FAILED)

    def test_autoretry_keeps_processing_and_marks_failed_after_max_retries(self):
        message = self.create_message()

        with self.assertRaises(Retry):
            self.invoke(execute_async_autoretry, message=message)
        message.refresh_from_db()
        self.assertEqual(message.status, ExecutionStatus.PROCESSING)

        with self.assertRaises(RetryableEchoError):
            self.invoke(execute_async_autoretry, message=message, retries=2)
        message.refresh_from_db()
        self.assertEqual(message.status, ExecutionStatus.FAILED)
        self.assertEqual(message.error_code, MessageErrorCode.TASK_EXECUTION_FAILED)

    def test_mismatched_celery_task_id_does_not_execute_or_update(self):
        message = self.create_message()

        with mock.patch.object(execute_async_success, "run") as run:
            with self.assertRaises(Ignore):
                self.invoke(execute_async_success, message=message, celery_task_id="task-old")

        message.refresh_from_db()
        run.assert_not_called()
        self.assertEqual(message.status, ExecutionStatus.PROCESSING)

    def test_terminal_message_duplicate_delivery_is_ignored(self):
        for status in (ExecutionStatus.SUCCESS, ExecutionStatus.FAILED):
            with self.subTest(status=status):
                message = self.create_message(task_id=f"task-{status}")
                Message.objects.filter(id=message.id).update(status=status)
                with mock.patch.object(execute_async_success, "run") as run:
                    with self.assertRaises(Ignore):
                        self.invoke(execute_async_success, message=message)
                run.assert_not_called()

    def test_first_terminal_update_wins_when_workers_execute_concurrently(self):
        message = self.create_message()

        # 两个 Worker 可以同时加载同一个 PROCESSING 快照并完成各自的业务计算。
        first_execution = load_message_execution(
            message_id=message.id,
            task_id=message.task_id,
            celery_task_id=message.task_id,
        )
        load_message_execution(
            message_id=message.id,
            task_id=message.task_id,
            celery_task_id=message.task_id,
        )
        finish_message_success(
            execution=first_execution,
            task_id=message.task_id,
            output_data={"content": "first"},
        )
        updated = finish_message_failure(
            message_id=message.id,
            task_id=message.task_id,
            exception=RuntimeError("second worker failed"),
        )

        message.refresh_from_db()
        self.assertFalse(updated)
        self.assertEqual(message.status, ExecutionStatus.SUCCESS)
        self.assertEqual(message.output_data, {"content": "first"})

    def test_success_cannot_overwrite_failure_written_by_another_worker(self):
        message = self.create_message()
        execution = load_message_execution(
            message_id=message.id,
            task_id=message.task_id,
            celery_task_id=message.task_id,
        )

        updated = finish_message_failure(
            message_id=message.id,
            task_id=message.task_id,
            exception=RuntimeError("first worker failed"),
        )
        with self.assertRaises(StaleMessageTask):
            finish_message_success(
                execution=execution,
                task_id=message.task_id,
                output_data={"content": "second"},
            )

        message.refresh_from_db()
        self.assertTrue(updated)
        self.assertEqual(message.status, ExecutionStatus.FAILED)
        self.assertIsNone(message.output_data)

    def test_only_current_task_id_can_write_terminal_state(self):
        message = self.create_message(task_id="task-current")

        with self.assertRaises(StaleMessageTask):
            load_message_execution(
                message_id=message.id,
                task_id="task-old",
                celery_task_id="task-old",
            )
        execution = load_message_execution(
            message_id=message.id,
            task_id="task-current",
            celery_task_id="task-current",
        )
        current_output = finish_message_success(
            execution=execution,
            task_id="task-current",
            output_data={"content": "current"},
        )

        message.refresh_from_db()
        self.assertEqual(current_output, {"content": "current"})
        self.assertEqual(message.output_data, {"content": "current"})

    def test_task_can_finish_after_conversation_soft_delete(self):
        message = self.create_message()
        self.conversation.delete()

        self.invoke(execute_async_success, message=message)

        message.refresh_from_db()
        self.assertEqual(message.status, ExecutionStatus.SUCCESS)

    def test_load_execution_returns_concrete_snapshot_types(self):
        message = self.create_message()

        execution = load_message_execution(
            message_id=message.id,
            task_id=message.task_id,
            celery_task_id=message.task_id,
        )

        self.assertIsInstance(execution.input_data, EchoInput)
        self.assertIsInstance(execution.context_data, EchoContext)

    def test_missing_task_arguments_are_configuration_error(self):
        execute_async_success.push_request(id="task-current", retries=0)
        try:
            with self.assertRaises(ImproperlyConfigured):
                execute_async_success(message_id=1)
        finally:
            execute_async_success.pop_request()
