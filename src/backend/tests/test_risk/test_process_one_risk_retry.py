# -*- coding: utf-8 -*-
"""自动流转失败次数：先落缓存，离开自动流转后再删除。"""

import datetime
from unittest import mock

from django.conf import settings

from services.web.risk.constants import RiskStatus
from services.web.risk.models import Risk
from services.web.risk.tasks import process_one_risk
from services.web.strategy_v2.models import Strategy
from tests.base import TestCase


class DictCache:
    def __init__(self):
        self.store = {}

    def get(self, key, default=None):
        return self.store.get(key, default)

    def set(self, key, value, timeout=None):
        self.store[key] = value

    def delete(self, key):
        self.store.pop(key, None)


class TestProcessOneRiskRetryCount(TestCase):
    def setUp(self):
        super().setUp()
        strategy = Strategy.objects.create(
            namespace=settings.DEFAULT_NAMESPACE, strategy_name="formal-retry", is_formal=True
        )
        self.risk = Risk.objects.create(
            strategy=strategy,
            raw_event_id="raw-retry",
            event_time=datetime.datetime.now(),
            event_data={},
            event_type=[],
            status=RiskStatus.AUTO_PROCESS,
        )
        self.cache_key = f"process_one_risk:fail:{self.risk.risk_id}"
        self.cache = DictCache()
        self.cache_patch = mock.patch("services.web.risk.tasks.cache", self.cache)
        self.cache_patch.start()
        self.notify_patch = mock.patch("services.web.risk.tasks.ErrorMsgHandler")
        self.notify_patch.start()
        self.addCleanup(self.cache_patch.stop)
        self.addCleanup(self.notify_patch.stop)

    def _run(self, run_side_effect=None, handoff_side_effect=None):
        effect = run_side_effect

        class AutoProcess:
            def __init__(self, *args, **kwargs):
                pass

            def run(self, *args, **kwargs):
                if isinstance(effect, BaseException):
                    raise effect
                if callable(effect):
                    return effect(*args, **kwargs)

        with (
            mock.patch("services.web.risk.tasks.AutoProcess", AutoProcess),
            mock.patch("services.web.risk.tasks.TransOperator") as trans_cls,
        ):
            trans_cls.load_security_person.return_value = ["security"]
            trans_cls.return_value.run.side_effect = handoff_side_effect
            process_one_risk(risk_id=self.risk.risk_id)
            return trans_cls

    def test_failure_below_cap_keeps_count_and_status(self):
        self._run(run_side_effect=RuntimeError("gateway 50000"))

        self.risk.refresh_from_db()
        self.assertEqual(self.cache.get(self.cache_key), 1)
        self.assertEqual(self.risk.status, RiskStatus.AUTO_PROCESS)

    def test_successful_poll_does_not_clear_count(self):
        self.cache.set(self.cache_key, 2)

        trans_cls = self._run(run_side_effect=None)

        self.assertEqual(self.cache.get(self.cache_key), 2)
        trans_cls.return_value.run.assert_not_called()

    def test_leaving_auto_flow_clears_count(self):
        self.cache.set(self.cache_key, 2)

        def close_risk(*args, **kwargs):
            Risk.objects.filter(risk_id=self.risk.risk_id).update(status=RiskStatus.AWAIT_PROCESS)

        self._run(run_side_effect=close_risk)

        self.assertIsNone(self.cache.get(self.cache_key))

    def test_third_failure_hands_off_then_clears_count(self):
        self.cache.set(self.cache_key, settings.PROCESS_RISK_MAX_RETRY - 1)

        def handoff(*args, **kwargs):
            Risk.objects.filter(risk_id=self.risk.risk_id).update(status=RiskStatus.AWAIT_PROCESS)

        trans_cls = self._run(run_side_effect=RuntimeError("gateway 50000"), handoff_side_effect=handoff)

        trans_cls.return_value.run.assert_called_once()
        self.assertIsNone(self.cache.get(self.cache_key))
        self.risk.refresh_from_db()
        self.assertEqual(self.risk.status, RiskStatus.AWAIT_PROCESS)

    def test_failed_handoff_keeps_count(self):
        self.cache.set(self.cache_key, settings.PROCESS_RISK_MAX_RETRY - 1)

        with self.assertRaises(RuntimeError):
            self._run(
                run_side_effect=RuntimeError("gateway 50000"),
                handoff_side_effect=RuntimeError("transfer failed"),
            )

        self.assertEqual(self.cache.get(self.cache_key), settings.PROCESS_RISK_MAX_RETRY)
        self.risk.refresh_from_db()
        self.assertEqual(self.risk.status, RiskStatus.AUTO_PROCESS)

    def test_cap_already_reached_hands_off_even_if_poll_succeeds(self):
        self.cache.set(self.cache_key, settings.PROCESS_RISK_MAX_RETRY)

        def handoff(*args, **kwargs):
            Risk.objects.filter(risk_id=self.risk.risk_id).update(status=RiskStatus.AWAIT_PROCESS)

        trans_cls = self._run(run_side_effect=None, handoff_side_effect=handoff)

        trans_cls.return_value.run.assert_called_once()
        self.assertIsNone(self.cache.get(self.cache_key))
