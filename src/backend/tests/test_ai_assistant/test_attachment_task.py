from unittest import mock

from celery.exceptions import Ignore, MaxRetriesExceededError, Retry
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connection
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext

from services.web.ai_assistant.constants import (
    AttachmentErrorCode,
    AttachmentType,
    ExecutionStatus,
    MessageType,
    PlatformStreamEvent,
)
from services.web.ai_assistant.exceptions import (
    AttachmentExecutionFailed,
    AttachmentOutputValidationError,
    AttachmentSnapshotValidationError,
    InvalidAttachmentState,
    StaleAttachmentTask,
    StreamNotEnabled,
)
from services.web.ai_assistant.handlers import attachment_handler_registry
from services.web.ai_assistant.models import Attachment, Conversation, Message
from services.web.ai_assistant.schemas import parse_stream_config
from services.web.ai_assistant.services.attachment_execution import (
    finish_attachment_failure,
    finish_attachment_success,
    load_attachment_execution,
)
from services.web.ai_assistant.streaming import (
    AttachmentArchiveStore,
    RedisLiveStore,
    UIStreamRuntime,
)
from services.web.ai_assistant.tasks import AttachmentExecutionTask, BaseExecutionTask
from tests.base import TestCase
from tests.test_ai_assistant.handlers import (
    AttachmentEchoContext,
    AttachmentEchoInput,
    AttachmentEchoOutput,
    AttachmentHandlerRegistryMixin,
    EchoAttachmentAsyncHandler,
    EchoAttachmentStreamHandler,
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
    execute_attachment_stream_autoretry,
    execute_attachment_stream_failure,
    execute_attachment_stream_retry,
    execute_attachment_stream_success,
    use_attachment_handler,
)


def invoke_task(task, *, attachment: Attachment, celery_task_id: str | None = None, retries: int = 0):
    """按平台约定投递参数直接触发 Task，模拟 Worker 内的一次实际执行。"""

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
        return invoke_task(task, attachment=attachment, celery_task_id=celery_task_id, retries=retries)

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

    def test_non_stream_execution_has_no_runtime_and_rejects_stream_access(self):
        attachment = self.create_attachment()

        execution = load_attachment_execution(
            attachment_id=attachment.id,
            task_id=attachment.task_id,
            celery_task_id=attachment.task_id,
        )

        self.assertFalse(execution.has_stream)
        with self.assertRaises(StreamNotEnabled):
            execution.stream


class StreamAttachmentTaskTest(AttachmentHandlerRegistryMixin, TransactionTestCase):
    """流式附件 Task 的生命周期：Runtime 注入、Retry 刷盘与终态收敛。"""

    # Task 生命周期测试仅读写 AI 助手模型，避免 flush 污染全量测试数据库。
    available_apps = ["services.web.ai_assistant"]

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
        use_attachment_handler(self, EchoAttachmentStreamHandler())
        self.attachment = self.create_attachment()

    def tearDown(self):
        redis_store = RedisLiveStore()
        keys = []
        for attachment_uid in Attachment.objects.values_list("uid", flat=True):
            pattern = redis_store.physical_key(f"ai_assistant:attachment_stream:{attachment_uid}:*")
            keys.extend(redis_store._client.scan_iter(match=pattern))
        if keys:
            redis_store._client.delete(*keys)
        super().tearDown()

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
            is_stream=True,
            created_by=self.user,
            updated_by=self.user,
        )

    invoke = staticmethod(invoke_task)

    @staticmethod
    def redis_events(redis_key: str):
        return RedisLiveStore().read(redis_key=redis_key, after_id="0-0", block_ms=1).events

    def test_stream_task_receives_runtime_and_persists_events_with_success(self):
        result = self.invoke(execute_attachment_stream_success, attachment=self.attachment)

        self.attachment.refresh_from_db()
        self.assertEqual(result, {"content": "async:hello"})
        self.assertEqual(self.attachment.status, ExecutionStatus.SUCCESS)
        self.assertEqual(self.attachment.output_data, {"content": "async:hello"})
        events = self.attachment.stream_archive
        self.assertEqual(events[0]["data"], {"content": "hello"})
        self.assertEqual(events[-1]["event"], PlatformStreamEvent.STREAM_END)

    def test_stream_task_failure_persists_partial_events_and_failed_terminal(self):
        with self.assertRaises(AttachmentExecutionFailed):
            self.invoke(execute_attachment_stream_failure, attachment=self.attachment)

        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.status, ExecutionStatus.FAILED)
        self.assertIsNone(self.attachment.output_data)
        self.assertEqual(self.attachment.error_message, "可公开的执行失败")
        events = self.attachment.stream_archive
        self.assertEqual(events[0]["data"], {"content": "partial"})
        self.assertEqual(events[-1]["event"], PlatformStreamEvent.STREAM_END)

    def test_business_retry_flushes_pending_events_and_keeps_processing(self):
        with mock.patch.object(
            UIStreamRuntime, "finish_retry", autospec=True, side_effect=UIStreamRuntime.finish_retry
        ) as finish_retry:
            with self.assertRaises(Retry):
                self.invoke(execute_attachment_stream_retry, attachment=self.attachment)

        self.assertEqual(finish_retry.call_count, 1)
        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.status, ExecutionStatus.PROCESSING)
        self.assertIsNone(self.attachment.output_data)
        # Retry 前必须强制刷盘，否则重投前的事件会永久丢失。
        self.assertEqual(self.attachment.stream_archive[-1]["data"], {"content": "before retry"})
        config = parse_stream_config(self.attachment.stream_config)
        self.assertIsNone(self.redis_events(config.redis_key)[-1].event)

    def test_next_execution_after_retry_starts_new_stream_and_clears_archive(self):
        first_config = None
        with self.assertRaises(Retry):
            self.invoke(execute_attachment_stream_retry, attachment=self.attachment)
        self.attachment.refresh_from_db()
        first_config = parse_stream_config(self.attachment.stream_config)

        result = self.invoke(execute_attachment_stream_retry, attachment=self.attachment, retries=1)

        self.attachment.refresh_from_db()
        second_config = parse_stream_config(self.attachment.stream_config)
        self.assertEqual(result, {"content": "async:hello"})
        self.assertNotEqual(second_config.execution_id, first_config.execution_id)
        self.assertEqual(self.attachment.status, ExecutionStatus.SUCCESS)
        # reset 只通知旧 Redis reader；新 archive 从本次业务事件开始。
        self.assertEqual(self.redis_events(first_config.redis_key)[-1].event, PlatformStreamEvent.STREAM_RESET)
        events = self.attachment.stream_archive
        self.assertIsNone(events[0]["event"])
        self.assertEqual(events[0]["data"], {"content": "before retry"})
        self.assertEqual(events[-1]["event"], PlatformStreamEvent.STREAM_END)

    def test_stale_automatic_checkpoint_is_ignored_without_writing_terminal_state(self):
        with mock.patch.object(UIStreamRuntime, "CHECKPOINT_EVENT_COUNT", 1):
            with mock.patch.object(AttachmentArchiveStore, "checkpoint", side_effect=StaleAttachmentTask()):
                with self.assertRaises(Ignore):
                    self.invoke(execute_attachment_stream_success, attachment=self.attachment)

        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.status, ExecutionStatus.PROCESSING)
        self.assertIsNone(self.attachment.output_data)
        self.assertEqual(self.attachment.stream_archive, [])

    def test_autoretry_also_flushes_pending_events(self):
        with self.assertRaises(Retry):
            self.invoke(execute_attachment_stream_autoretry, attachment=self.attachment)

        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.status, ExecutionStatus.PROCESSING)
        self.assertEqual(self.attachment.stream_archive[-1]["data"], {"content": "before autoretry"})

    def test_final_transaction_failure_triggers_retry_and_keeps_processing(self):
        with mock.patch.object(AttachmentArchiveStore, "finalize", side_effect=DatabaseError("db down")):
            with self.assertRaises(Retry):
                self.invoke(execute_attachment_stream_success, attachment=self.attachment)

        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.status, ExecutionStatus.PROCESSING)
        self.assertIsNone(self.attachment.output_data)

    def test_output_validation_error_does_not_retry_and_marks_failed(self):
        with mock.patch.object(execute_attachment_stream_success, "run", return_value={"invalid": True}):
            with self.assertRaises(AttachmentOutputValidationError):
                self.invoke(execute_attachment_stream_success, attachment=self.attachment)

        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.status, ExecutionStatus.FAILED)
        self.assertEqual(self.attachment.error_code, AttachmentErrorCode.OUTPUT_VALIDATION_FAILED)
        self.assertEqual(self.attachment.stream_archive[-1]["event"], PlatformStreamEvent.STREAM_END)

    def test_stale_delivery_does_not_start_stream_execution(self):
        Attachment.objects.filter(id=self.attachment.id).update(task_id="task-new")

        with mock.patch.object(UIStreamRuntime, "start") as start:
            with self.assertRaises(Ignore):
                self.invoke(execute_attachment_stream_success, attachment=self.attachment)

        start.assert_not_called()
        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.stream_config, {})

    def test_invalid_snapshot_does_not_start_stream_execution(self):
        Attachment.objects.filter(id=self.attachment.id).update(input_data={"invalid": True})

        with mock.patch.object(UIStreamRuntime, "start") as start:
            with self.assertRaises(AttachmentSnapshotValidationError):
                self.invoke(execute_attachment_stream_success, attachment=self.attachment)

        start.assert_not_called()
        self.attachment.refresh_from_db()
        self.assertEqual(self.attachment.status, ExecutionStatus.FAILED)
        self.assertEqual(self.attachment.stream_config, {})
