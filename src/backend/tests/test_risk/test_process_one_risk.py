# -*- coding: utf-8 -*-
"""
Tests for process_one_risk retry-counter semantics and the auto-process stuck metric.
"""

import datetime
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from services.web.risk.constants import RiskStatus
from services.web.risk.models import Risk
from services.web.risk.tasks import (
    RISK_AUTO_PROCESS_STUCK_METRIC,
    build_process_risk_fail_cache_key,
    process_one_risk,
    report_auto_process_stuck_risks,
)
from services.web.strategy_v2.models import Strategy
from tests.base import TestCase


class ProcessOneRiskRetryCounterTest(TestCase):
    """失败计数不得因通知/转人工失败而丢失或被清零（历史无限重试根因）。"""

    def setUp(self):
        cache.clear()
        self.strategy = Strategy.objects.create(
            namespace=settings.DEFAULT_NAMESPACE, strategy_name="process_one_risk_strategy", is_formal=True
        )
        self.risk = Risk.objects.create(
            strategy=self.strategy,
            raw_event_id="raw-process-one-risk",
            event_time=datetime.datetime.now(),
            event_data={},
            event_type=[],
        )
        self.cache_key = build_process_risk_fail_cache_key(self.risk.risk_id)

    def tearDown(self):
        cache.clear()

    def test_notice_failure_does_not_lose_retry_counter(self):
        """通知发送失败不得导致计数丢失，下一轮仍从 1 开始（历史"回滚"洞之一）。"""

        with (
            mock.patch("services.web.risk.tasks.NewRisk") as mock_process,
            mock.patch("services.web.risk.tasks.ErrorMsgHandler") as mock_notice,
        ):
            mock_process.return_value.run.side_effect = Exception("process boom")
            mock_notice.return_value.send.side_effect = Exception("notice boom")
            process_one_risk(risk_id=self.risk.risk_id)
            # 首次失败计数 1 -> 落盘为 2，即使通知抛异常
            self.assertEqual(cache.get(self.cache_key), 2)

            mock_notice.return_value.send.side_effect = None
            process_one_risk(risk_id=self.risk.risk_id)
            self.assertEqual(cache.get(self.cache_key), 3)

    def test_transfer_failure_keeps_counter_and_skips_reprocess(self):
        """转人工失败不得清零计数；下一轮跳过自动处理，只继续尝试转人工收敛。"""

        cache.set(self.cache_key, settings.PROCESS_RISK_MAX_RETRY, timeout=60)
        with (
            mock.patch("services.web.risk.tasks.NewRisk") as mock_process,
            mock.patch("services.web.risk.tasks.ErrorMsgHandler"),
            mock.patch("services.web.risk.tasks.TransOperator") as mock_trans,
        ):
            mock_process.return_value.run.side_effect = Exception("process boom")
            mock_trans.return_value.run.side_effect = Exception("transfer boom")

            process_one_risk(risk_id=self.risk.risk_id)
            # 计数推进为"待转人工"标记，而不是被清零
            self.assertEqual(cache.get(self.cache_key), settings.PROCESS_RISK_MAX_RETRY + 1)
            self.assertEqual(mock_process.return_value.run.call_count, 1)

            process_one_risk(risk_id=self.risk.risk_id)
            # 第二轮跳过自动处理（不再重复失败），只重试转人工
            self.assertEqual(mock_process.return_value.run.call_count, 1)
            self.assertEqual(mock_trans.return_value.run.call_count, 2)

    def test_transfer_success_clears_counter(self):
        """转人工成功后清除失败计数。"""

        cache.set(self.cache_key, settings.PROCESS_RISK_MAX_RETRY, timeout=60)
        with (
            mock.patch("services.web.risk.tasks.NewRisk") as mock_process,
            mock.patch("services.web.risk.tasks.ErrorMsgHandler"),
            mock.patch("services.web.risk.tasks.TransOperator") as mock_trans,
        ):
            mock_process.return_value.run.side_effect = Exception("process boom")
            process_one_risk(risk_id=self.risk.risk_id)

            mock_trans.return_value.run.assert_called_once()
            self.assertIsNone(cache.get(self.cache_key))

    def test_success_clears_counter(self):
        """处理成功后清除失败计数。"""

        cache.set(self.cache_key, 2, timeout=60)
        with mock.patch("services.web.risk.tasks.NewRisk") as mock_process:
            process_one_risk(risk_id=self.risk.risk_id)
            mock_process.return_value.run.assert_called_once()
            self.assertIsNone(cache.get(self.cache_key))


class ReportAutoProcessStuckRisksTest(TestCase):
    """自动处理停留 gauge：超阈值计数上报，处理完成后归零自动恢复。"""

    def setUp(self):
        cache.clear()
        self.strategy = Strategy.objects.create(
            namespace=settings.DEFAULT_NAMESPACE, strategy_name="stuck_metric_strategy", is_formal=True
        )

    def tearDown(self):
        cache.clear()

    def _create_risk(self, raw_event_id: str, status: str, minutes_ago: int) -> Risk:
        risk = Risk.objects.create(
            strategy=self.strategy,
            raw_event_id=raw_event_id,
            event_time=datetime.datetime.now(),
            event_data={},
            event_type=[],
            status=status,
        )
        # last_operate_time 是 auto_now 字段，需 queryset.update 回写历史时间
        Risk.objects.filter(risk_id=risk.risk_id).update(
            last_operate_time=timezone.now() - datetime.timedelta(minutes=minutes_ago)
        )
        return risk

    def test_reports_stuck_count(self):
        self._create_risk(
            "stuck-1", RiskStatus.AUTO_PROCESS, minutes_ago=settings.PROCESS_RISK_STUCK_THRESHOLD_MINUTES + 5
        )
        self._create_risk(
            "stuck-2", RiskStatus.AUTO_PROCESS, minutes_ago=settings.PROCESS_RISK_STUCK_THRESHOLD_MINUTES + 10
        )
        # 正常处理中的单不计
        self._create_risk("running-1", RiskStatus.AUTO_PROCESS, minutes_ago=1)
        # 非自动处理状态不计
        self._create_risk(
            "other-1", RiskStatus.AWAIT_PROCESS, minutes_ago=settings.PROCESS_RISK_STUCK_THRESHOLD_MINUTES + 5
        )

        with mock.patch("services.web.risk.tasks.Metric") as mock_metric:
            report_auto_process_stuck_risks()
            mock_metric.assert_called_once_with(metrics={RISK_AUTO_PROCESS_STUCK_METRIC: 2})
            mock_metric.return_value.report.assert_called_once()

    def test_reports_zero_when_no_stuck_risk(self):
        self._create_risk("running-2", RiskStatus.AUTO_PROCESS, minutes_ago=1)

        with mock.patch("services.web.risk.tasks.Metric") as mock_metric:
            report_auto_process_stuck_risks()
            mock_metric.assert_called_once_with(metrics={RISK_AUTO_PROCESS_STUCK_METRIC: 0})
