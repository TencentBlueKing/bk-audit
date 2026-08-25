from datetime import timedelta
from unittest import mock
from uuid import uuid4

from django.test.utils import override_settings
from django.utils import timezone

from services.web.ai_assistant.constants import (
    AttachmentErrorCode,
    AttachmentType,
    ExecutionStatus,
    MessageErrorCode,
    MessageType,
    PlatformStreamEvent,
    StreamArchiveStatus,
)
from services.web.ai_assistant.models import Attachment, Conversation, Message
from services.web.ai_assistant.services.reconciliation import (
    reconcile_processing_executions,
)
from services.web.ai_assistant.tasks.maintenance import monitor_ai_assistant_executions
from tests.base import TestCase


class ReconciliationTest(TestCase):
    """验证巡检分桶、有界扫描和超时 CAS，不依赖真实等待。"""

    def setUp(self):
        self.now = timezone.now()
        self.user = "alice"
        self.conversation = Conversation.objects.create(created_by=self.user, updated_by=self.user)
        self.source_message = Message.objects.create(
            conversation=self.conversation,
            message_type=MessageType.LOG_SEARCH,
            status=ExecutionStatus.SUCCESS,
            input_data={},
            context_data={},
            output_data={},
            created_by=self.user,
            updated_by=self.user,
        )

    def create_message(self, *, task_id: str, age: timedelta) -> Message:
        message = Message.objects.create(
            conversation=self.conversation,
            message_type=MessageType.NATURAL_LANGUAGE_SEARCH,
            status=ExecutionStatus.PROCESSING,
            task_id=task_id,
            input_data={},
            context_data={},
            created_by=self.user,
            updated_by=self.user,
        )
        activity = self.now - age
        Message.objects.filter(id=message.id).update(queued_at=activity, last_activity_at=activity)
        message.refresh_from_db()
        return message

    def create_attachment(self, *, task_id: str, age: timedelta, is_stream: bool = False) -> Attachment:
        attachment = Attachment.objects.create(
            source_message=self.source_message,
            attachment_type=AttachmentType.AI_ANALYSIS,
            title="AI 分析",
            status=ExecutionStatus.PROCESSING,
            task_id=task_id,
            input_data={},
            context_data={},
            is_stream=is_stream,
            stream_config=(
                {
                    "task_id": task_id,
                    "execution_id": str(uuid4()),
                    "redis_key": f"stream:{task_id}",
                    "archive_status": StreamArchiveStatus.COMPLETE,
                }
                if is_stream
                else {}
            ),
            stream_archive=[{"data": {"content": "snapshot"}}] if is_stream else [],
            created_by=self.user,
            updated_by=self.user,
        )
        activity = self.now - age
        Attachment.objects.filter(id=attachment.id).update(queued_at=activity, last_activity_at=activity)
        attachment.refresh_from_db()
        return attachment

    @override_settings(
        AI_ASSISTANT_MESSAGE_WARNING_SECONDS=300,
        AI_ASSISTANT_MESSAGE_FAILURE_SECONDS=900,
        AI_ASSISTANT_ATTACHMENT_WARNING_SECONDS=3600,
        AI_ASSISTANT_ATTACHMENT_FAILURE_SECONDS=7200,
        AI_ASSISTANT_RECONCILE_BATCH_SIZE=200,
        AI_ASSISTANT_RECONCILE_AUTO_FAIL_ENABLED=True,
    )
    @mock.patch("services.web.ai_assistant.services.reconciliation.report_execution_timeout_events")
    @mock.patch("services.web.ai_assistant.services.reconciliation.report_execution_finished_batch")
    @mock.patch("services.web.ai_assistant.services.reconciliation.report_processing_metrics")
    @mock.patch("services.web.ai_assistant.services.reconciliation.report_reconcile_metric")
    @mock.patch("services.web.ai_assistant.services.reconciliation.RedisLiveStore")
    def test_reconcile_buckets_and_auto_fails_only_expired(
        self,
        redis_store,
        report_reconcile_metric,
        report_processing_metrics,
        report_execution_finished_batch,
        report_execution_timeout_events,
    ):
        healthy = self.create_message(task_id="healthy", age=timedelta(minutes=1))
        warning = self.create_message(task_id="warning", age=timedelta(minutes=6))
        expired = self.create_message(task_id="expired", age=timedelta(minutes=16))
        stream_attachment = self.create_attachment(task_id="attachment-expired", age=timedelta(hours=3), is_stream=True)

        summary = reconcile_processing_executions(now=self.now)

        healthy.refresh_from_db()
        warning.refresh_from_db()
        expired.refresh_from_db()
        stream_attachment.refresh_from_db()
        self.assertEqual(healthy.status, ExecutionStatus.PROCESSING)
        self.assertEqual(warning.status, ExecutionStatus.PROCESSING)
        self.assertEqual(expired.error_code, MessageErrorCode.TASK_EXECUTION_TIMEOUT)
        self.assertEqual(stream_attachment.error_code, AttachmentErrorCode.TASK_EXECUTION_TIMEOUT)
        self.assertEqual(stream_attachment.stream_archive[-1]["event"], PlatformStreamEvent.STREAM_END)
        self.assertEqual(stream_attachment.stream_archive[-1]["data"], {"status": ExecutionStatus.FAILED})
        self.assertEqual(stream_attachment.stream_config["archive_status"], StreamArchiveStatus.DEGRADED)
        redis_store.return_value.append.assert_called_once()
        self.assertEqual(summary.failed_count, 2)
        self.assertEqual(summary.expired_count, 2)
        records = report_processing_metrics.call_args.args[0]
        message_buckets = {record.age_bucket for record in records if record.object_type == "MESSAGE"}
        self.assertEqual(message_buckets, {"HEALTHY", "WARNING", "EXPIRED"})
        timeout_records = [record for call in report_execution_timeout_events.call_args_list for record in call.args[0]]
        self.assertEqual(len(timeout_records), 2)
        snapshots = [snapshot for call in report_execution_finished_batch.call_args_list for snapshot in call.args[0]]
        self.assertEqual(len(snapshots), 2)
        self.assertEqual(report_execution_finished_batch.call_count, 2)
        report_reconcile_metric.assert_called_once()

    @override_settings(
        AI_ASSISTANT_MESSAGE_WARNING_SECONDS=300,
        AI_ASSISTANT_MESSAGE_FAILURE_SECONDS=900,
        AI_ASSISTANT_ATTACHMENT_WARNING_SECONDS=3600,
        AI_ASSISTANT_ATTACHMENT_FAILURE_SECONDS=7200,
        AI_ASSISTANT_RECONCILE_BATCH_SIZE=2,
        AI_ASSISTANT_RECONCILE_AUTO_FAIL_ENABLED=True,
    )
    def test_reconcile_limits_each_model_batch(self):
        messages = [self.create_message(task_id=f"task-{index}", age=timedelta(hours=1)) for index in range(3)]

        summary = reconcile_processing_executions(now=self.now)

        self.assertEqual(summary.scanned_count, 2)
        self.assertEqual(summary.failed_count, 2)
        self.assertEqual(
            Message.objects.filter(
                id__in=[message.id for message in messages], status=ExecutionStatus.PROCESSING
            ).count(),
            1,
        )

    @override_settings(
        AI_ASSISTANT_MESSAGE_WARNING_SECONDS=300,
        AI_ASSISTANT_MESSAGE_FAILURE_SECONDS=900,
        AI_ASSISTANT_ATTACHMENT_WARNING_SECONDS=3600,
        AI_ASSISTANT_ATTACHMENT_FAILURE_SECONDS=7200,
        AI_ASSISTANT_RECONCILE_BATCH_SIZE=200,
        AI_ASSISTANT_RECONCILE_AUTO_FAIL_ENABLED=False,
    )
    def test_auto_fail_switch_keeps_expired_object_processing(self):
        message = self.create_message(task_id="expired", age=timedelta(hours=1))

        summary = reconcile_processing_executions(now=self.now)

        message.refresh_from_db()
        self.assertEqual(message.status, ExecutionStatus.PROCESSING)
        self.assertEqual(summary.expired_count, 1)
        self.assertEqual(summary.failed_count, 0)

    @override_settings(
        AI_ASSISTANT_MESSAGE_WARNING_SECONDS=300,
        AI_ASSISTANT_MESSAGE_FAILURE_SECONDS=900,
        AI_ASSISTANT_ATTACHMENT_WARNING_SECONDS=3600,
        AI_ASSISTANT_ATTACHMENT_FAILURE_SECONDS=7200,
        AI_ASSISTANT_RECONCILE_BATCH_SIZE=200,
        AI_ASSISTANT_RECONCILE_AUTO_FAIL_ENABLED=True,
    )
    @mock.patch.object(Message, "timeout_processing", return_value=False)
    def test_lost_timeout_cas_is_normal_concurrency(self, timeout_processing):
        self.create_message(task_id="expired", age=timedelta(hours=1))

        summary = reconcile_processing_executions(now=self.now)

        timeout_processing.assert_called_once()
        self.assertEqual(summary.scanned_count, 1)
        self.assertEqual(summary.failed_count, 0)

    @override_settings(
        AI_ASSISTANT_MESSAGE_WARNING_SECONDS=300,
        AI_ASSISTANT_MESSAGE_FAILURE_SECONDS=900,
        AI_ASSISTANT_ATTACHMENT_WARNING_SECONDS=3600,
        AI_ASSISTANT_ATTACHMENT_FAILURE_SECONDS=7200,
        AI_ASSISTANT_RECONCILE_BATCH_SIZE=200,
        AI_ASSISTANT_RECONCILE_AUTO_FAIL_ENABLED=True,
    )
    @mock.patch("services.web.ai_assistant.services.reconciliation.report_execution_timeout_events")
    @mock.patch.object(Message, "timeout_processing", side_effect=[True, RuntimeError("database down")])
    def test_partial_timeout_results_are_reported_before_reconcile_failure(self, _timeout_processing, report_timeout):
        self.create_message(task_id="expired-1", age=timedelta(hours=1))
        self.create_message(task_id="expired-2", age=timedelta(hours=1))

        with self.assertRaisesRegex(RuntimeError, "database down"):
            reconcile_processing_executions(now=self.now)

        report_timeout.assert_called_once()
        self.assertEqual(len(report_timeout.call_args.args[0]), 1)

    @override_settings(
        AI_ASSISTANT_MESSAGE_WARNING_SECONDS=300,
        AI_ASSISTANT_MESSAGE_FAILURE_SECONDS=900,
        AI_ASSISTANT_ATTACHMENT_WARNING_SECONDS=3600,
        AI_ASSISTANT_ATTACHMENT_FAILURE_SECONDS=7200,
        AI_ASSISTANT_RECONCILE_BATCH_SIZE=200,
        AI_ASSISTANT_RECONCILE_AUTO_FAIL_ENABLED=True,
    )
    def test_null_activity_row_is_reported_but_not_unsafely_failed(self):
        message = self.create_message(task_id="missing-activity", age=timedelta(hours=1))
        Message.objects.filter(id=message.id).update(last_activity_at=None)

        summary = reconcile_processing_executions(now=self.now)

        message.refresh_from_db()
        self.assertEqual(message.status, ExecutionStatus.PROCESSING)
        self.assertEqual(summary.scanned_count, 1)
        self.assertEqual(summary.failed_count, 0)


class ReconciliationTaskTest(TestCase):
    """周期任务只负责任务开关、短锁和失败事件，业务扫描留在 Service。"""

    @override_settings(AI_ASSISTANT_RECONCILE_ENABLED=False)
    @mock.patch("services.web.ai_assistant.tasks.maintenance.reconcile_processing_executions")
    def test_disabled_task_does_not_scan(self, reconcile):
        self.assertIsNone(monitor_ai_assistant_executions.run())
        reconcile.assert_not_called()

    @override_settings(AI_ASSISTANT_RECONCILE_ENABLED=False)
    @mock.patch("services.web.ai_assistant.tasks.maintenance.cache.set")
    @mock.patch("services.web.ai_assistant.tasks.maintenance.reconcile_processing_executions")
    def test_disabled_task_does_not_access_redis(self, reconcile, cache_set):
        self.assertIsNone(monitor_ai_assistant_executions.run())
        cache_set.assert_not_called()
        reconcile.assert_not_called()

    @override_settings(AI_ASSISTANT_RECONCILE_ENABLED=True)
    @mock.patch("services.web.ai_assistant.tasks.maintenance.cache.set", return_value=False)
    @mock.patch("services.web.ai_assistant.tasks.maintenance.reconcile_processing_executions")
    def test_default_settings_attempt_short_lock_without_extra_switch(self, reconcile, cache_set):
        self.assertIsNone(monitor_ai_assistant_executions.run())
        cache_set.assert_called_once()
        reconcile.assert_not_called()

    @override_settings(AI_ASSISTANT_RECONCILE_ENABLED=True)
    @mock.patch("services.web.ai_assistant.tasks.maintenance.cache.set", return_value=True)
    @mock.patch("services.web.ai_assistant.tasks.maintenance.reconcile_processing_executions")
    def test_success_returns_serializable_summary(self, reconcile, _cache_set):
        reconcile.return_value.as_dict.return_value = {"failed_count": 2}

        self.assertEqual(monitor_ai_assistant_executions.run(), {"failed_count": 2})

    @override_settings(AI_ASSISTANT_RECONCILE_ENABLED=True)
    @mock.patch("services.web.ai_assistant.tasks.maintenance.cache.set", side_effect=RuntimeError("redis down"))
    @mock.patch("services.web.ai_assistant.tasks.maintenance.reconcile_processing_executions")
    def test_redis_lock_failure_runs_reconcile_without_lock(self, reconcile, _cache_set):
        reconcile.return_value.as_dict.return_value = {"failed_count": 1}

        self.assertEqual(monitor_ai_assistant_executions.run(), {"failed_count": 1})

    @override_settings(AI_ASSISTANT_RECONCILE_ENABLED=True)
    @mock.patch("services.web.ai_assistant.tasks.maintenance.cache.set", return_value=True)
    @mock.patch("services.web.ai_assistant.tasks.maintenance.report_reconcile_failed_event")
    @mock.patch("services.web.ai_assistant.tasks.maintenance.reconcile_processing_executions")
    def test_failure_reports_event_and_is_reraised(self, reconcile, report_failed, _cache_set):
        error = RuntimeError("database down")
        reconcile.side_effect = error

        with self.assertRaises(RuntimeError):
            monitor_ai_assistant_executions.run()

        report_failed.assert_called_once_with(error=error)

    @override_settings(AI_ASSISTANT_RECONCILE_ENABLED=True)
    @mock.patch("services.web.ai_assistant.tasks.maintenance.cache.set", return_value=True)
    @mock.patch("services.web.ai_assistant.services.reconciliation.set_span_attributes")
    def test_reconcile_records_summary_on_public_span(self, set_attributes, _cache_set):
        self.assertEqual(monitor_ai_assistant_executions.run()["failed_count"], 0)

        self.assertEqual(
            set_attributes.call_args.args[1],
            {
                "bk_audit.ai_assistant.scanned_count": 0,
                "bk_audit.ai_assistant.expired_count": 0,
                "bk_audit.ai_assistant.failed_count": 0,
            },
        )
