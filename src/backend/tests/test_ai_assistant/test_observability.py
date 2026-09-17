from datetime import timedelta
from unittest import mock

from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from services.web.ai_assistant.observability import (
    AIAssistantExecutionMetric,
    AIAssistantProcessingMetric,
    AIAssistantReconcileMetric,
    AIAssistantStreamExecutionMetric,
    ExecutionMetricSnapshot,
    ProcessingMetricRecord,
    ReconcileMetricSnapshot,
    StreamMetricSnapshot,
    TimeoutEventRecord,
    report_execution_finished,
    report_execution_finished_batch,
    report_execution_timeout_events,
    report_invariant_violation,
    report_processing_metrics,
    report_reconcile_failed_event,
    report_reconcile_metric,
    report_stream_execution,
    set_execution_span_context,
    start_execution_span,
    start_stream_span,
)


class ObservabilityTest(SimpleTestCase):
    """验证观测协议的统计口径、隐私边界和最佳努力语义。"""

    def setUp(self):
        self.now = timezone.now()

    def test_ai_assistant_metric_declarations_are_complete_and_unique(self):
        metric_types = (
            AIAssistantExecutionMetric,
            AIAssistantProcessingMetric,
            AIAssistantReconcileMetric,
            AIAssistantStreamExecutionMetric,
        )
        metric_names = []
        for metric_type in metric_types:
            self.assertTrue(metric_type.documentation)
            self.assertTrue(metric_type.metric_fields)
            self.assertTrue(metric_type.dimension_fields)
            for name, field in metric_type.metric_fields.items():
                self.assertTrue(name.startswith("ai_assistant_"))
                self.assertTrue(field.documentation)
                self.assertTrue(field.unit)
                metric_names.append(name)
            for dimension in metric_type.dimension_fields.values():
                self.assertTrue(dimension.documentation)

        self.assertEqual(len(metric_names), len(set(metric_names)))

    def assert_metric_call_matches_declaration(self, metric_mock, metric_type):
        """断言固定指标组的上报 payload 与声明协议完全一致。"""

        call = metric_mock.call_args
        records = call.kwargs.get("records") or [call.kwargs]
        for record in records:
            self.assertEqual(set(record["metrics"]), set(metric_type.metric_fields))
            self.assertEqual(set(record["dimension"]), set(metric_type.dimension_fields))

    @mock.patch("services.web.ai_assistant.observability.AIAssistantExecutionMetric")
    def test_execution_metric_has_expected_durations_and_dimensions(self, metric_cls):
        report_execution_finished(
            ExecutionMetricSnapshot(
                object_type="MESSAGE",
                business_type="NATURAL_LANGUAGE_SEARCH",
                execution_mode="ASYNC",
                is_stream=False,
                status="SUCCESS",
                error_code="",
                created_at=self.now - timedelta(seconds=20),
                queued_at=self.now - timedelta(seconds=15),
                started_at=self.now - timedelta(seconds=10),
                finished_at=self.now,
            )
        )

        self.assertEqual(
            metric_cls.call_args.kwargs["metrics"],
            {
                "ai_assistant_execution_count": 1,
                "ai_assistant_execution_queue_duration_ms": 5000,
                "ai_assistant_execution_duration_ms": 10000,
                "ai_assistant_execution_total_duration_ms": 20000,
                "ai_assistant_execution_slo_met_count": 1,
            },
        )
        self.assertEqual(
            metric_cls.call_args.kwargs["dimension"],
            {
                "object_type": "MESSAGE",
                "business_type": "NATURAL_LANGUAGE_SEARCH",
                "execution_mode": "ASYNC",
                "is_stream": "false",
                "stage": "terminal",
                "status": "SUCCESS",
                "error_code": "",
            },
        )
        self.assert_metric_call_matches_declaration(metric_cls, AIAssistantExecutionMetric)
        metric_cls.return_value.async_report.assert_called_once_with()

    @mock.patch("services.web.ai_assistant.observability.AIAssistantExecutionMetric")
    def test_execution_metric_treats_missing_worker_start_as_zero_duration(self, metric_cls):
        report_execution_finished(
            ExecutionMetricSnapshot(
                object_type="MESSAGE",
                business_type="SYNC_EXAMPLE",
                execution_mode="SYNC",
                is_stream=False,
                status="SUCCESS",
                error_code="",
                created_at=self.now - timedelta(seconds=2),
                queued_at=None,
                started_at=None,
                finished_at=self.now,
            )
        )

        metrics = metric_cls.call_args.kwargs["metrics"]
        self.assertEqual(metrics["ai_assistant_execution_queue_duration_ms"], 0)
        self.assertEqual(metrics["ai_assistant_execution_duration_ms"], 0)
        self.assertEqual(metrics["ai_assistant_execution_total_duration_ms"], 2000)

    @mock.patch("services.web.ai_assistant.observability.AIAssistantExecutionMetric")
    def test_execution_metric_counts_queue_until_terminal_when_worker_never_started(self, metric_cls):
        report_execution_finished(
            ExecutionMetricSnapshot(
                object_type="MESSAGE",
                business_type="NATURAL_LANGUAGE_SEARCH",
                execution_mode="ASYNC",
                is_stream=False,
                status="FAILED",
                error_code="TASK_EXECUTION_TIMEOUT",
                created_at=self.now - timedelta(minutes=16),
                queued_at=self.now - timedelta(minutes=15),
                started_at=None,
                finished_at=self.now,
            )
        )

        metrics = metric_cls.call_args.kwargs["metrics"]
        self.assertEqual(metrics["ai_assistant_execution_queue_duration_ms"], 15 * 60 * 1000)
        self.assertEqual(metrics["ai_assistant_execution_duration_ms"], 0)

    @mock.patch("services.web.ai_assistant.observability.AIAssistantExecutionMetric")
    def test_execution_metrics_can_be_batched_into_one_delivery(self, metric_cls):
        snapshots = [
            ExecutionMetricSnapshot(
                object_type="MESSAGE",
                business_type="NATURAL_LANGUAGE_SEARCH",
                execution_mode="ASYNC",
                is_stream=False,
                status="FAILED",
                error_code="TASK_EXECUTION_TIMEOUT",
                created_at=self.now - timedelta(minutes=index + 1),
                queued_at=self.now - timedelta(minutes=index + 1),
                started_at=None,
                finished_at=self.now,
            )
            for index in range(2)
        ]

        report_execution_finished_batch(snapshots)

        self.assertEqual(len(metric_cls.call_args.kwargs["records"]), 2)
        self.assert_metric_call_matches_declaration(metric_cls, AIAssistantExecutionMetric)
        metric_cls.return_value.async_report.assert_called_once_with()

    @mock.patch("services.web.ai_assistant.observability.AIAssistantExecutionMetric")
    def test_execution_metric_uses_object_slo_setting(self, metric_cls):
        snapshot = ExecutionMetricSnapshot(
            object_type="ATTACHMENT",
            business_type="AI_ANALYSIS",
            execution_mode="ASYNC",
            is_stream=True,
            status="SUCCESS",
            error_code="",
            created_at=self.now - timedelta(seconds=31),
            queued_at=self.now - timedelta(seconds=30),
            started_at=self.now - timedelta(seconds=29),
            finished_at=self.now,
        )

        with self.settings(AI_ASSISTANT_ATTACHMENT_SLO_SECONDS=30):
            report_execution_finished(snapshot)

        self.assertEqual(metric_cls.call_args.kwargs["metrics"]["ai_assistant_execution_slo_met_count"], 0)

    @mock.patch("services.web.ai_assistant.observability.AIAssistantProcessingMetric")
    def test_processing_metrics_are_batched_with_fixed_dimensions(self, metric_cls):
        report_processing_metrics(
            [
                ProcessingMetricRecord(
                    object_type="MESSAGE",
                    business_type="NL_SEARCH",
                    age_bucket="WARNING",
                    processing_count=3,
                    warning_count=2,
                    expired_count=1,
                ),
                ProcessingMetricRecord(
                    object_type="ATTACHMENT",
                    business_type="AI_ANALYSIS",
                    age_bucket="HEALTHY",
                    processing_count=4,
                    warning_count=0,
                    expired_count=0,
                ),
            ]
        )

        records = metric_cls.call_args.kwargs["records"]
        self.assertEqual(len(records), 2)
        self.assertEqual(set(records[0]["dimension"]), {"object_type", "business_type", "age_bucket"})
        self.assertEqual(records[0]["metrics"]["ai_assistant_processing_expired_count"], 1)
        self.assert_metric_call_matches_declaration(metric_cls, AIAssistantProcessingMetric)
        metric_cls.return_value.async_report.assert_called_once_with()

    @mock.patch("services.web.ai_assistant.observability.AIAssistantStreamExecutionMetric")
    def test_stream_metric_contains_only_aggregate_values(self, metric_cls):
        report_stream_execution(
            StreamMetricSnapshot(
                business_type="AI_ANALYSIS",
                status="SUCCESS",
                error_code="",
                degraded=True,
                truncated=False,
                event_count=8,
                event_bytes=1024,
            )
        )

        self.assertEqual(
            metric_cls.call_args.kwargs["metrics"],
            {
                "ai_assistant_stream_execution_count": 1,
                "ai_assistant_stream_degraded_count": 1,
                "ai_assistant_stream_truncated_count": 0,
                "ai_assistant_stream_event_count": 8,
                "ai_assistant_stream_event_bytes": 1024,
            },
        )
        self.assertNotIn("data", metric_cls.call_args.kwargs)
        self.assert_metric_call_matches_declaration(metric_cls, AIAssistantStreamExecutionMetric)

    @mock.patch("services.web.ai_assistant.observability.AIAssistantReconcileMetric")
    def test_reconcile_metric_uses_heartbeat_and_counts(self, metric_cls):
        report_reconcile_metric(
            ReconcileMetricSnapshot(
                duration_ms=25,
                scanned_count=10,
                expired_count=3,
                failed_count=2,
                status="SUCCESS",
            )
        )

        self.assertEqual(metric_cls.call_args.kwargs["dimension"], {"stage": "reconcile", "status": "SUCCESS"})
        self.assertEqual(metric_cls.call_args.kwargs["metrics"]["ai_assistant_reconcile_heartbeat"], 1)
        self.assert_metric_call_matches_declaration(metric_cls, AIAssistantReconcileMetric)

    @override_settings(LOG_EXPORT_STATUS_DATA_ID=456, LOG_EXPORT_STATUS_ACCESS_TOKEN="metric-token")
    @mock.patch("core.monitor.report_metric_to_bk_monitor.delay")
    def test_reporters_build_complete_declarative_bkm_payload(self, report_delay):
        """不 mock Metric 子类，验证声明字段与最终 BKM payload 一致。"""

        report_execution_finished(
            ExecutionMetricSnapshot(
                object_type="MESSAGE",
                business_type="NATURAL_LANGUAGE_SEARCH",
                execution_mode="ASYNC",
                is_stream=False,
                status="SUCCESS",
                error_code="",
                created_at=self.now - timedelta(seconds=20),
                queued_at=self.now - timedelta(seconds=15),
                started_at=self.now - timedelta(seconds=10),
                finished_at=self.now,
            )
        )
        report_processing_metrics(
            [
                ProcessingMetricRecord(
                    object_type="MESSAGE",
                    business_type="NATURAL_LANGUAGE_SEARCH",
                    age_bucket="HEALTHY",
                    processing_count=1,
                    warning_count=0,
                    expired_count=0,
                )
            ]
        )
        report_reconcile_metric(
            ReconcileMetricSnapshot(
                duration_ms=10,
                scanned_count=1,
                expired_count=0,
                failed_count=0,
                status="SUCCESS",
            )
        )
        report_stream_execution(
            StreamMetricSnapshot(
                business_type="AI_ANALYSIS",
                status="SUCCESS",
                error_code="",
                degraded=False,
                truncated=False,
                event_count=1,
                event_bytes=10,
            )
        )

        metric_types = (
            AIAssistantExecutionMetric,
            AIAssistantProcessingMetric,
            AIAssistantReconcileMetric,
            AIAssistantStreamExecutionMetric,
        )
        self.assertEqual(report_delay.call_count, len(metric_types))
        for call, metric_type in zip(report_delay.call_args_list, metric_types):
            payload = call.args[0]
            self.assertEqual(payload["data_id"], 456)
            self.assertEqual(payload["access_token"], "metric-token")
            for record in payload["data"]:
                self.assertEqual(set(record["metrics"]), set(metric_type.metric_fields))
                self.assertEqual(set(record["dimension"]), set(metric_type.dimension_fields) | {"job"})
                self.assertTrue(record["dimension"]["job"])

    @mock.patch("services.web.ai_assistant.observability.AIAssistantExecutionTimeoutEvent")
    def test_timeout_events_batch_identifiers_outside_dimensions(self, event_cls):
        report_execution_timeout_events(
            [
                TimeoutEventRecord(
                    object_type="MESSAGE",
                    business_type="NL_SEARCH",
                    object_uid="message-uid",
                    task_id="task-id",
                    error_code="TASK_EXECUTION_TIMEOUT",
                )
            ]
        )

        records = event_cls.call_args.kwargs["records"]
        self.assertEqual(records[0]["target"], "message-uid")
        self.assertEqual(records[0]["extra"], {"task_id": "task-id"})
        self.assertEqual(
            records[0]["context"],
            {
                "object_type": "MESSAGE",
                "business_type": "NL_SEARCH",
                "error_code": "TASK_EXECUTION_TIMEOUT",
            },
        )
        event_cls.return_value.async_report.assert_called_once_with()

    def test_common_monitor_reporters_isolate_delivery_failures(self):
        execution = ExecutionMetricSnapshot(
            object_type="MESSAGE",
            business_type="NL_SEARCH",
            execution_mode="ASYNC",
            is_stream=False,
            status="FAILED",
            error_code="FAILED",
            created_at=self.now,
            queued_at=self.now,
            started_at=self.now,
            finished_at=self.now,
        )
        with self.settings(LOG_EXPORT_STATUS_DATA_ID=1, LOG_EXPORT_STATUS_ACCESS_TOKEN="token"):
            with mock.patch("core.monitor.report_metric_to_bk_monitor.delay", side_effect=RuntimeError("monitor down")):
                report_execution_finished(execution)
                report_processing_metrics([ProcessingMetricRecord("MESSAGE", "NL_SEARCH", "HEALTHY", 1, 0, 0)])
                report_reconcile_metric(ReconcileMetricSnapshot(0, 0, 0, 0, "FAILED"))
                report_stream_execution(StreamMetricSnapshot("AI_ANALYSIS", "FAILED", "FAILED", True, False, 0, 0))

        with mock.patch("core.monitor.report_event_to_bk_monitor.delay", side_effect=RuntimeError("monitor down")):
            report_execution_timeout_events(
                [TimeoutEventRecord("MESSAGE", "NL_SEARCH", "uid", "task", "TASK_EXECUTION_TIMEOUT")]
            )
            report_reconcile_failed_event(RuntimeError("database down"))
            report_invariant_violation("MESSAGE", "NL_SEARCH", "uid", "task", "INVALID_OUTPUT")

    @mock.patch("services.web.ai_assistant.observability.set_span_attributes")
    @mock.patch("services.web.ai_assistant.observability.trace.get_current_span")
    def test_set_execution_span_context_uses_trace_not_metric_dimensions(self, get_current_span, set_attributes):
        set_execution_span_context(object_uid="uid", business_type="AI_ANALYSIS", is_stream=True)
        set_attributes.assert_called_once_with(
            get_current_span.return_value,
            {
                "bk_audit.ai_assistant.object_uid": "uid",
                "bk_audit.ai_assistant.business_type": "AI_ANALYSIS",
                "bk_audit.ai_assistant.is_stream": True,
            },
        )

    @mock.patch("services.web.ai_assistant.observability.start_observation_span")
    def test_start_execution_span_uses_stable_name_and_context(self, start_span):
        with start_execution_span(
            object_type="MESSAGE",
            object_id=12,
            task_id="task-id",
            task_name="task.name",
            retries=2,
            redelivered=True,
        ):
            pass
        start_span.assert_called_once_with(
            "ai_assistant.message.execute",
            {
                "bk_audit.ai_assistant.object_type": "MESSAGE",
                "bk_audit.ai_assistant.object_id": 12,
                "bk_audit.ai_assistant.task_id": "task-id",
                "bk_audit.ai_assistant.task_name": "task.name",
                "bk_audit.ai_assistant.retries": 2,
                "bk_audit.ai_assistant.redelivered": True,
            },
        )

    @mock.patch("services.web.ai_assistant.observability.start_observation_span")
    def test_start_stream_span_uses_stable_name_and_context(self, start_span):
        with start_stream_span(
            attachment_uid="attachment-uid",
            business_type="AI_ANALYSIS",
            execution_id="execution-id",
            status="SUCCESS",
        ):
            pass

        start_span.assert_called_once_with(
            "ai_assistant.attachment.stream",
            {
                "bk_audit.ai_assistant.object_type": "ATTACHMENT",
                "bk_audit.ai_assistant.object_uid": "attachment-uid",
                "bk_audit.ai_assistant.business_type": "AI_ANALYSIS",
                "bk_audit.ai_assistant.execution_id": "execution-id",
                "bk_audit.ai_assistant.status": "SUCCESS",
            },
        )

    def test_public_span_preserves_business_result_and_exception(self):
        with start_stream_span("uid", "AI_ANALYSIS", "execution", "SUCCESS"):
            result = "success"
        self.assertEqual(result, "success")

        with self.assertRaisesRegex(ValueError, "business failed"):
            with start_stream_span("uid", "AI_ANALYSIS", "execution", "FAILED"):
                raise ValueError("business failed")
