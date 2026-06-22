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

    @mock.patch("services.web.risk.tasks.export_risks_to_mail.update_state")
    @mock.patch("services.web.risk.tasks.RiskExportService")
    def test_export_risks_to_mail_success(self, mock_service_cls, mock_update_state):
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

    @mock.patch("services.web.risk.tasks.RiskExportFailedEvent.report")
    @mock.patch("services.web.risk.tasks.export_risks_to_mail.update_state")
    @mock.patch("services.web.risk.tasks.RiskExportService")
    def test_export_risks_to_mail_apply_returns_failure_state_after_max_retry(
        self, mock_service_cls, mock_update_state, mock_report_event
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
        mock_report_event.assert_called_once()

    @mock.patch("services.web.risk.tasks.RiskExportFailedEvent.report")
    @mock.patch("services.web.risk.tasks.export_risks_to_mail.retry")
    @mock.patch("services.web.risk.tasks.export_risks_to_mail.update_state")
    @mock.patch("services.web.risk.tasks.RiskExportService")
    def test_export_risks_to_mail_retries_when_send_mail_failed(
        self, mock_service_cls, mock_update_state, mock_retry, mock_report_event
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
        mock_report_event.assert_not_called()

    @mock.patch("services.web.risk.tasks.RiskExportFailedEvent.report")
    @mock.patch("services.web.risk.tasks.export_risks_to_mail.retry")
    @mock.patch("services.web.risk.tasks.export_risks_to_mail.update_state")
    @mock.patch("services.web.risk.tasks.RiskExportService")
    def test_export_risks_to_mail_retries_before_max_retry(
        self, mock_service_cls, mock_update_state, mock_retry, mock_report_event
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
        mock_report_event.assert_not_called()

    @mock.patch("services.web.risk.tasks.RiskExportFailedEvent.report")
    @mock.patch("services.web.risk.tasks.export_risks_to_mail.retry")
    @mock.patch("services.web.risk.tasks.export_risks_to_mail.update_state")
    @mock.patch("services.web.risk.tasks.RiskExportService")
    def test_export_risks_to_mail_reports_alert_after_max_retry(
        self, mock_service_cls, mock_update_state, mock_retry, mock_report_event
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

        mock_report_event.assert_called_once()
        mock_retry.assert_called_once_with(countdown=settings.RISK_EXPORT_TASK_RETRY_DELAY)

    @mock.patch("services.web.risk.tasks.RiskExportFailedEvent.report")
    @mock.patch("services.web.risk.tasks.export_risks_to_mail.retry")
    @mock.patch("services.web.risk.tasks.export_risks_to_mail.update_state")
    @mock.patch("services.web.risk.tasks.RiskExportService")
    def test_export_risks_to_mail_keeps_original_error_when_report_failed(
        self, mock_service_cls, mock_update_state, mock_retry, mock_report_event
    ):
        mock_retry.side_effect = MaxRetriesExceededError()
        mock_report_event.side_effect = RuntimeError("report failed")
        service = mock_service_cls.return_value
        service.build_export_file.side_effect = RuntimeError("export failed")

        with self.assertRaisesRegex(RuntimeError, "export failed"):
            export_risks_to_mail(
                username="admin",
                risk_ids=["risk001", "risk002"],
                risk_view_type="all",
                requested_at="2026-06-22 19:33:36",
            )

        mock_report_event.assert_called_once()
        mock_retry.assert_called_once_with(countdown=settings.RISK_EXPORT_TASK_RETRY_DELAY)
