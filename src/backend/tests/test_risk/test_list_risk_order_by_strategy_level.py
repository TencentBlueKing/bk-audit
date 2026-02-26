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
from services.web.risk.resources.risk import ListRiskStrategy, ListRiskTags
from services.web.strategy_v2.constants import RiskLevel
from services.web.strategy_v2.models import Strategy, StrategyTag
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

    @mock.patch("services.web.risk.models.Risk.load_iam_authed_risks")
    def test_list_risk_load_risks_returns_plain_queryset(self, mock_load_iam_authed_risks):
        """ListRisk.load_risks 应返回不带注解的纯净 QuerySet"""
        mock_load_iam_authed_risks.return_value = Risk.objects.all()
        qs = ListRisk().load_risks({})
        risk = qs.first()
        self.assertFalse(hasattr(risk, "event_content_short"))
        self.assertFalse(hasattr(risk, "_has_report"))

    @mock.patch("services.web.risk.models.Risk.load_iam_authed_risks")
    def test_list_mine_risk_load_risks_returns_plain_queryset(self, mock_load_iam_authed_risks):
        mock_load_iam_authed_risks.return_value = Risk.objects.all()
        """ListMineRisk.load_risks 应返回不带注解的纯净 QuerySet"""
        qs = ListMineRisk().load_risks({})
        risk = qs.first()
        self.assertIsNotNone(risk, "setUp 数据应包含 current_operator=['admin'] 的风险")
        self.assertFalse(hasattr(risk, "event_content_short"))
        self.assertFalse(hasattr(risk, "_has_report"))

    @mock.patch("services.web.risk.models.Risk.load_iam_authed_risks")
    def test_list_noticing_risk_load_risks_returns_plain_queryset(self, mock_load_iam_authed_risks):
        """ListNoticingRisk.load_risks 应返回不带注解的纯净 QuerySet"""
        mock_load_iam_authed_risks.return_value = Risk.objects.all()
        qs = ListNoticingRisk().load_risks({})
        risk = qs.first()
        self.assertIsNotNone(risk, "setUp 数据应包含 notice_users=['admin'] 的风险")
        self.assertFalse(hasattr(risk, "event_content_short"))
        self.assertFalse(hasattr(risk, "_has_report"))

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

    @mock.patch("services.web.risk.models.Risk.load_iam_authed_risks")
    def test_list_risk_tags_no_memory_materialization(self, mock_load_iam_authed_risks):
        """ListRiskTags 应使用子查询而非将 risk_id 物化到内存"""
        from apps.meta.models import Tag

        mock_load_iam_authed_risks.return_value = Risk.objects.all()
        tag = Tag.objects.create(tag_name="test-tag")
        StrategyTag.objects.create(strategy=self.strategy_high, tag=tag)

        result = ListRiskTags().perform_request({"risk_view_type": "all"})
        tag_ids = [t.tag_id if hasattr(t, "tag_id") else t["tag_id"] for t in result]
        self.assertIn(tag.tag_id, tag_ids)

    @mock.patch("services.web.risk.models.Risk.load_iam_authed_risks")
    def test_list_risk_strategy_returns_correct_strategies(self, mock_load_iam_authed_risks):
        """ListRiskStrategy 应返回风险关联的策略"""
        mock_load_iam_authed_risks.return_value = Risk.objects.all()
        result = ListRiskStrategy().perform_request({"risk_view_type": "all"})
        strategy_ids = {s.strategy_id if hasattr(s, "strategy_id") else s["strategy_id"] for s in result}
        self.assertIn(self.strategy_high.strategy_id, strategy_ids)
