# -*- coding: utf-8 -*-
"""
Tests for filtering risk processing by Strategy.is_formal.
"""

import datetime
from unittest import mock

from django.conf import settings

from services.web.risk.models import Risk
from services.web.risk.tasks import process_risk_ticket
from services.web.strategy_v2.models import Strategy
from tests.base import TestCase


class TestProcessRiskIsFormalFilter(TestCase):
    def test_only_process_formal_strategies(self):
        # Create strategies
        s_formal = Strategy.objects.create(namespace=settings.DEFAULT_NAMESPACE, strategy_name="formal", is_formal=True)
        s_non_formal = Strategy.objects.create(
            namespace=settings.DEFAULT_NAMESPACE, strategy_name="non-formal", is_formal=False
        )

        now = datetime.datetime.now()
        # Create risks for both strategies in NEW status
        r1 = Risk.objects.create(
            strategy=s_formal,
            raw_event_id="raw-1",
            event_time=now,
            event_data={},
            event_type=[],
        )
        Risk.objects.create(
            strategy=s_non_formal,
            raw_event_id="raw-2",
            event_time=now,
            event_data={},
            event_type=[],
        )

        # Ensure synchronous processing path and intercept process_one_risk
        with (
            mock.patch("services.web.risk.tasks.settings.ENABLE_MULTI_PROCESS_RISK", False),
            mock.patch("services.web.risk.tasks.process_one_risk") as mocked_process,
        ):
            process_risk_ticket()

            # Only the formal strategy risk should be processed
            mocked_process.assert_called_once()
            called_kwargs = mocked_process.call_args.kwargs
            assert called_kwargs["risk_id"] == r1.risk_id
