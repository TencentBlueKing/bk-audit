from io import StringIO
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, override_settings


@override_settings(
    LOG_EXPORT_STATUS_DATA_ID=1001,
    LOG_EXPORT_STATUS_ACCESS_TOKEN="metric-token",
    ALERT_DATA_ID=1002,
    ALERT_ACCESS_TOKEN="event-token",
)
class ReportObservabilitySamplesCommandTest(SimpleTestCase):
    """样例命令应显式覆盖平台约定的全部 Metric 和 Event 类型。"""

    @mock.patch(
        "services.web.ai_assistant.management.commands.report_ai_assistant_observability_samples."
        "report_stream_execution"
    )
    @mock.patch(
        "services.web.ai_assistant.management.commands.report_ai_assistant_observability_samples."
        "report_reconcile_metric"
    )
    @mock.patch(
        "services.web.ai_assistant.management.commands.report_ai_assistant_observability_samples."
        "report_processing_metrics"
    )
    @mock.patch(
        "services.web.ai_assistant.management.commands.report_ai_assistant_observability_samples."
        "report_execution_finished"
    )
    @mock.patch(
        "services.web.ai_assistant.management.commands.report_ai_assistant_observability_samples."
        "AIAssistantInvariantViolationEvent"
    )
    @mock.patch(
        "services.web.ai_assistant.management.commands.report_ai_assistant_observability_samples."
        "AIAssistantReconcileFailedEvent"
    )
    @mock.patch(
        "services.web.ai_assistant.management.commands.report_ai_assistant_observability_samples."
        "AIAssistantExecutionTimeoutEvent"
    )
    def test_command_reports_all_metric_groups_and_event_types(
        self,
        timeout_event,
        reconcile_failed_event,
        invariant_violation_event,
        report_execution_finished,
        report_processing_metrics,
        report_reconcile_metric,
        report_stream_execution,
    ):
        stdout = StringIO()

        call_command("report_ai_assistant_observability_samples", stdout=stdout)

        report_execution_finished.assert_called_once()
        report_processing_metrics.assert_called_once()
        report_reconcile_metric.assert_called_once()
        report_stream_execution.assert_called_once()
        self.assertEqual(report_execution_finished.call_args.args[0].status, "SAMPLE")
        self.assertEqual(report_reconcile_metric.call_args.args[0].status, "SAMPLE")
        self.assertEqual(report_stream_execution.call_args.args[0].status, "SAMPLE")
        self.assertEqual(timeout_event.call_args.kwargs["context"]["error_code"], "OBSERVABILITY_SAMPLE")
        self.assertEqual(reconcile_failed_event.call_args.kwargs["context"]["error_code"], "OBSERVABILITY_SAMPLE")
        self.assertEqual(invariant_violation_event.call_args.kwargs["context"]["error_code"], "OBSERVABILITY_SAMPLE")
        timeout_event.return_value.async_report.assert_called_once_with()
        reconcile_failed_event.return_value.async_report.assert_called_once_with()
        invariant_violation_event.return_value.async_report.assert_called_once_with()
        self.assertIn("4 组 Metric 和 3 类 Event", stdout.getvalue())

    @override_settings(LOG_EXPORT_STATUS_DATA_ID=0, ALERT_DATA_ID=0)
    def test_command_rejects_missing_monitor_configuration(self):
        with self.assertRaisesRegex(CommandError, "监控上报配置不完整"):
            call_command("report_ai_assistant_observability_samples")
