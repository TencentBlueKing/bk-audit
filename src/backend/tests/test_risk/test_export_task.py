# -*- coding: utf-8 -*-
from unittest import mock

from celery.exceptions import MaxRetriesExceededError
from django.conf import settings
from django.test import TestCase

from core.monitor import report_event_to_bk_monitor
from services.web.risk.tasks import export_risks_to_mail


class TestRiskExportTask(TestCase):
    def test_export_risks_to_mail_uses_default_queue(self):
        task = export_risks_to_mail._get_current_object()

        self.assertIsNone(task._get_exec_options()["queue"])
        self.assertEqual(task.max_retries, settings.RISK_EXPORT_TASK_MAX_RETRY)
        self.assertEqual(task.time_limit, settings.RISK_EXPORT_TASK_TIME_LIMIT)

    def test_report_event_to_bk_monitor_uses_monitor_timeout(self):
        task = report_event_to_bk_monitor._get_current_object()

        self.assertEqual(task.time_limit, settings.MONITOR_EVENT_TASK_TIMEOUT)

    @mock.patch("services.web.risk.tasks.logger_celery.info")
    @mock.patch("services.web.risk.tasks.export_risks_to_mail.update_state")
    @mock.patch("services.web.risk.tasks.RiskExportService")
    def test_export_risks_to_mail_success(self, mock_service_cls, mock_update_state, mock_logger_info):
        service = mock_service_cls.return_value
        export_file = mock.Mock()
        export_file.total = 2
        export_file.filename = "审计风险_所有风险_20260622_193336.xlsx"
        service.build_export_file.return_value = export_file
        service.send_mail.return_value = {"result": True}

        result = export_risks_to_mail(
            username="admin",
            risk_ids=["risk001", "risk002"],
            risk_view_type="all",
            requested_at="2026-06-22 19:33:36",
        )

        self.assertEqual(result["total"], 2)
        self.assertEqual(result["filename"], "审计风险_所有风险_20260622_193336.xlsx")
        mock_service_cls.assert_called_once_with(
            username="admin",
            risk_ids=["risk001", "risk002"],
            risk_view_type="all",
        )
        service.build_export_file.assert_called_once()
        service.send_mail.assert_called_once_with(
            export_file=export_file,
            requested_at="2026-06-22 19:33:36",
        )
        mock_update_state.assert_any_call(state="RUNNING", meta={"current": 0, "total": 2})
        mock_update_state.assert_any_call(state="PROGRESS", meta={"current": 2, "total": 2})
        log_messages = [call.args[0] for call in mock_logger_info.call_args_list]
        self.assertIn(
            "[RiskExportTask] start username=%s total=%s risk_view_type=%s requested_at=%s",
            log_messages,
        )
        self.assertIn(
            "[RiskExportTask] export file built username=%s total=%s filename=%s",
            log_messages,
        )
        self.assertIn("[RiskExportTask] mail sent username=%s total=%s filename=%s", log_messages)

    @mock.patch("services.web.risk.tasks.export_risks_to_mail.update_state")
    @mock.patch("services.web.risk.tasks.RiskExportService")
    def test_export_risks_to_mail_uses_resolved_ids(self, mock_service_cls, mock_update_state):
        export_file = mock.Mock()
        export_file.total = 1
        export_file.filename = "审计风险_全部风险_20260623_100000.xlsx"
        service = mock_service_cls.return_value
        service.build_export_file.return_value = export_file

        result = export_risks_to_mail(
            username="admin",
            risk_ids=["risk001"],
            risk_view_type="all",
            requested_at="2026-06-23 10:00:00",
        )

        self.assertEqual(result["total"], 1)
        mock_service_cls.assert_called_once_with(
            username="admin",
            risk_ids=["risk001"],
            risk_view_type="all",
        )

    @mock.patch("services.web.risk.tasks.export_risks_to_mail.update_state")
    @mock.patch("services.web.risk.tasks.RiskExportService")
    def test_export_risks_to_mail_apply_returns_success_state(self, mock_service_cls, mock_update_state):
        service = mock_service_cls.return_value
        export_file = mock.Mock()
        export_file.total = 2
        export_file.filename = "审计风险_所有风险_20260622_193336.xlsx"
        service.build_export_file.return_value = export_file
        service.send_mail.return_value = {"result": True}

        result = export_risks_to_mail.apply(
            kwargs={
                "username": "admin",
                "risk_ids": ["risk001", "risk002"],
                "risk_view_type": "all",
                "requested_at": "2026-06-22 19:33:36",
            }
        )

        self.assertEqual(result.state, "SUCCESS")
        self.assertEqual(result.result["total"], 2)
        mock_update_state.assert_any_call(state="RUNNING", meta={"current": 0, "total": 2})
        mock_update_state.assert_any_call(state="PROGRESS", meta={"current": 2, "total": 2})

    @mock.patch("services.web.risk.tasks.RiskExportFailedEvent.async_report")
    @mock.patch("services.web.risk.tasks.export_risks_to_mail.update_state")
    @mock.patch("services.web.risk.tasks.RiskExportService")
    def test_export_risks_to_mail_apply_returns_failure_state_after_max_retry(
        self, mock_service_cls, mock_update_state, mock_async_report_event
    ):
        service = mock_service_cls.return_value
        service.build_export_file.side_effect = RuntimeError("export failed")

        result = export_risks_to_mail.apply(
            kwargs={
                "username": "admin",
                "risk_ids": ["risk001"],
                "risk_view_type": "all",
                "requested_at": "2026-06-22 19:33:36",
            },
            retries=export_risks_to_mail.max_retries,
            throw=False,
        )

        self.assertEqual(result.state, "FAILURE")
        self.assertIsInstance(result.result, RuntimeError)
        self.assertIn("export failed", str(result.result))
        mock_async_report_event.assert_called_once()

    @mock.patch("services.web.risk.tasks.RiskExportFailedEvent.async_report")
    @mock.patch("services.web.risk.tasks.export_risks_to_mail.retry")
    @mock.patch("services.web.risk.tasks.export_risks_to_mail.update_state")
    @mock.patch("services.web.risk.tasks.RiskExportService")
    def test_export_risks_to_mail_retries_when_send_mail_failed(
        self, mock_service_cls, mock_update_state, mock_retry, mock_async_report_event
    ):
        mock_retry.side_effect = RuntimeError("retry called")
        service = mock_service_cls.return_value
        export_file = mock.Mock()
        export_file.total = 1
        export_file.filename = "审计风险_所有风险_20260622_193336.xlsx"
        service.build_export_file.return_value = export_file
        service.send_mail.side_effect = RuntimeError("mail failed")

        with self.assertRaisesRegex(RuntimeError, "retry called"):
            export_risks_to_mail(
                username="admin",
                risk_ids=["risk001"],
                risk_view_type="all",
                requested_at="2026-06-22 19:33:36",
            )

        service.build_export_file.assert_called_once()
        service.send_mail.assert_called_once_with(
            export_file=export_file,
            requested_at="2026-06-22 19:33:36",
        )
        mock_retry.assert_called_once_with(countdown=settings.RISK_EXPORT_TASK_RETRY_DELAY)
        mock_async_report_event.assert_not_called()

    @mock.patch("services.web.risk.tasks.logger_celery.error")
    @mock.patch("services.web.risk.tasks.logger_celery.warning")
    @mock.patch("services.web.risk.tasks.report_observation_metric")
    @mock.patch("services.web.risk.tasks.RiskExportFailedEvent.async_report")
    @mock.patch("services.web.risk.tasks.export_risks_to_mail.retry")
    @mock.patch("services.web.risk.tasks.export_risks_to_mail.update_state")
    @mock.patch("services.web.risk.tasks.RiskExportService")
    def test_export_risks_to_mail_retries_before_max_retry(
        self,
        mock_service_cls,
        mock_update_state,
        mock_retry,
        mock_async_report_event,
        mock_report_metric,
        mock_logger_warning,
        mock_logger_error,
    ):
        mock_retry.side_effect = RuntimeError("retry called")
        service = mock_service_cls.return_value
        service.build_export_file.side_effect = RuntimeError("export failed")

        original_retries = export_risks_to_mail.request.retries
        export_risks_to_mail.request.retries = 0
        try:
            with self.assertRaisesRegex(RuntimeError, "retry called"):
                export_risks_to_mail(
                    username="admin",
                    risk_ids=["risk001"],
                    risk_view_type="all",
                    requested_at="2026-06-22 19:33:36",
                )
        finally:
            export_risks_to_mail.request.retries = original_retries

        mock_retry.assert_called_once_with(countdown=settings.RISK_EXPORT_TASK_RETRY_DELAY)
        mock_async_report_event.assert_not_called()
        mock_report_metric.assert_not_called()
        warning_messages = [call.args[0] for call in mock_logger_warning.call_args_list]
        error_messages = [call.args[0] for call in mock_logger_error.call_args_list]
        self.assertIn(
            "[RiskExportTaskRetrying] username=%s total=%s retries=%s max_retries=%s countdown=%s error=%s",
            warning_messages,
        )
        self.assertNotIn("[RiskExportTaskFailed] username=%s total=%s retries=%s max_retries=%s", error_messages)

    @mock.patch("services.web.risk.tasks.RiskExportFailedEvent.async_report")
    @mock.patch("services.web.risk.tasks.logger_celery.error")
    @mock.patch("services.web.risk.tasks.export_risks_to_mail.retry")
    @mock.patch("services.web.risk.tasks.export_risks_to_mail.update_state")
    @mock.patch("services.web.risk.tasks.RiskExportService")
    def test_export_risks_to_mail_reports_alert_after_max_retry(
        self, mock_service_cls, mock_update_state, mock_retry, mock_logger_error, mock_async_report_event
    ):
        mock_retry.side_effect = MaxRetriesExceededError()
        service = mock_service_cls.return_value
        service.build_export_file.side_effect = RuntimeError("export failed")

        with self.assertRaisesRegex(RuntimeError, "export failed"):
            export_risks_to_mail(
                username="admin",
                risk_ids=["risk001", "risk002"],
                risk_view_type="all",
                requested_at="2026-06-22 19:33:36",
            )

        mock_async_report_event.assert_called_once()
        mock_retry.assert_called_once_with(countdown=settings.RISK_EXPORT_TASK_RETRY_DELAY)
        error_messages = [call.args[0] for call in mock_logger_error.call_args_list]
        self.assertIn(
            "[RiskExportTaskFailed] username=%s total=%s retries=%s max_retries=%s",
            error_messages,
        )

    @mock.patch("services.web.risk.tasks.report_observation_metric")
    @mock.patch("services.web.risk.tasks.RiskExportFailedEvent.async_report")
    @mock.patch("services.web.risk.tasks.export_risks_to_mail.retry")
    @mock.patch("services.web.risk.tasks.export_risks_to_mail.update_state")
    @mock.patch("services.web.risk.tasks.RiskExportService")
    def test_export_risks_to_mail_reports_event_and_keeps_original_error(
        self, mock_service_cls, mock_update_state, mock_retry, mock_async_report_event, mock_report_metric
    ):
        mock_retry.side_effect = MaxRetriesExceededError()
        service = mock_service_cls.return_value
        service.build_export_file.side_effect = RuntimeError("export failed")

        with self.assertRaisesRegex(RuntimeError, "export failed"):
            export_risks_to_mail(
                username="admin",
                risk_ids=["risk001", "risk002"],
                risk_view_type="all",
                requested_at="2026-06-22 19:33:36",
            )

        mock_async_report_event.assert_called_once()
        mock_retry.assert_called_once_with(countdown=settings.RISK_EXPORT_TASK_RETRY_DELAY)
        mock_report_metric.assert_called_once()
        metric_kwargs = mock_report_metric.call_args.kwargs
        self.assertEqual(metric_kwargs["name"], "risk.export_risks_to_mail")
        self.assertEqual(metric_kwargs["status"], "error")
        self.assertEqual(metric_kwargs["error_type"], "RuntimeError")
        self.assertEqual(metric_kwargs["dimensions"]["operation"], "export_risks_to_mail")
        self.assertEqual(metric_kwargs["dimensions"]["business_status"], "failed")
