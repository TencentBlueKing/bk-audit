# -*- coding: utf-8 -*-
"""
Tests for sorting risk list by strategy.risk_level using order_field/order_type
"""

import datetime
from unittest import mock

from apps.meta.constants import OrderTypeChoices
from services.web.risk.constants import RiskStatus
from services.web.risk.models import Risk
from services.web.risk.resources import ListMineRisk, ListNoticingRisk, ListRisk
from services.web.strategy_v2.constants import RiskLevel
from services.web.strategy_v2.models import Strategy
from tests.base import TestCase
from tests.utils.request import call_resource_with_request


class TestListRiskOrderByStrategyLevel(TestCase):
    def setUp(self):
        super().setUp()
        # Strategies with different risk levels
        self.strategy_low = Strategy.objects.create(
            strategy_id=201,
            strategy_name="S-LOW",
            risk_level=RiskLevel.LOW,
        )
        self.strategy_mid = Strategy.objects.create(
            strategy_id=202,
            strategy_name="S-MID",
            risk_level=RiskLevel.MIDDLE,
        )
        self.strategy_high = Strategy.objects.create(
            strategy_id=203,
            strategy_name="S-HIGH",
            risk_level=RiskLevel.HIGH,
        )

        # Create risks
        self.risk_low = Risk.objects.create(
            risk_id="RL-2",
            title="low",
            strategy=self.strategy_low,
            status=RiskStatus.NEW,
            event_time=datetime.datetime(2023, 1, 1, 10, 0, 0),
            current_operator=["admin"],
            notice_users=["guest"],
        )
        self.risk_mid = Risk.objects.create(
            risk_id="RM-2",
            title="mid",
            strategy=self.strategy_mid,
            status=RiskStatus.NEW,
            event_time=datetime.datetime(2023, 1, 2, 10, 0, 0),
            current_operator=["someone"],
            notice_users=["admin"],
        )
        self.risk_high = Risk.objects.create(
            risk_id="RH-2",
            title="high",
            strategy=self.strategy_high,
            status=RiskStatus.NEW,
            event_time=datetime.datetime(2023, 1, 3, 10, 0, 0),
            current_operator=["admin"],
            notice_users=["admin"],
        )

    @mock.patch("services.web.risk.models.Risk.load_iam_authed_risks")
    def test_list_risk_sort_by_strategy_level_desc(self, mock_load_iam_authed_risks):
        mock_load_iam_authed_risks.return_value = Risk.objects.all()

        resp = call_resource_with_request(ListRisk().request, {"order_field": "risk_level", "order_type": "desc"})
        # Desc custom order: HIGH > MIDDLE > LOW
        ids = [i["risk_id"] for i in resp["results"]]
        self.assertEqual(ids, ["RH-2", "RM-2", "RL-2"])

    @mock.patch("services.web.risk.models.Risk.load_iam_authed_risks")
    def test_list_risk_sort_by_strategy_level_asc(self, mock_load_iam_authed_risks):
        mock_load_iam_authed_risks.return_value = Risk.objects.all()

        resp = call_resource_with_request(
            ListRisk().request, {"order_field": "risk_level", "order_type": OrderTypeChoices.ASC}
        )
        # Asc custom order: LOW < MIDDLE < HIGH
        ids = [i["risk_id"] for i in resp["results"]]
        self.assertEqual(ids, ["RL-2", "RM-2", "RH-2"])

    @mock.patch("services.web.risk.models.Risk.load_iam_authed_risks")
    def test_list_risk_uses_iam_only(self, mock_load_iam_authed_risks):
        mock_load_iam_authed_risks.return_value = Risk.objects.all()

        call_resource_with_request(ListRisk().request, {"order_field": "-event_time"})
        mock_load_iam_authed_risks.assert_called_once()

    def test_list_mine_risk_sort_by_strategy_level_desc(self):
        resp = call_resource_with_request(ListMineRisk().request, {"order_field": "risk_level", "order_type": "desc"})
        # mine has RH-2 and RL-2 -> order: RH-2 then RL-2 (HIGH > LOW in desc custom)
        ids = [i["risk_id"] for i in resp["results"]]
        self.assertEqual(ids, ["RH-2", "RL-2"])

    def test_list_noticing_risk_sort_by_strategy_level_desc(self):
        resp = call_resource_with_request(
            ListNoticingRisk().request, {"order_field": "risk_level", "order_type": "desc"}
        )
        # noticing has RH-2 and RM-2 -> order: RH-2 then RM-2 (HIGH > MIDDLE in desc custom)
        ids = [i["risk_id"] for i in resp["results"]]
        self.assertEqual(ids, ["RH-2", "RM-2"])
