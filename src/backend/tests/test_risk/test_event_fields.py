# -*- coding: utf-8 -*-
"""
ListEventFieldsByStrategy 接口单测
"""

from bk_resource import resource

from services.web.strategy_v2.models import Strategy
from tests.base import TestCase


class TestListEventFieldsByStrategy(TestCase):
    def setUp(self):
        super().setUp()
        # 创建若干策略，包含基础字段配置
        self.s1 = Strategy.objects.create(
            strategy_id=101,
            strategy_name="Strategy One",
            event_basic_field_configs=[
                {"field_name": "raw_event_id", "display_name": "Raw Event ID"},
                {"field_name": "operator", "display_name": "Operator"},
            ],
        )
        self.s2 = Strategy.objects.create(
            strategy_id=102,
            strategy_name="Strategy Two",
            event_basic_field_configs=[
                {"field_name": "operator", "display_name": "Operator"},
                {"field_name": "event_time", "display_name": "Event Time"},
            ],
        )
        self.s3 = Strategy.objects.create(
            strategy_id=103,
            strategy_name="Strategy Three",
            event_basic_field_configs=[],
        )

    def _sorted(self, items):
        return sorted(items, key=lambda x: (x["strategy_id"], x["field_name"]))

    def test_list_event_fields_by_specific_strategies(self):
        # 仅查询 s1、s2
        result = resource.risk.list_event_fields_by_strategy(strategy_ids=[self.s1.strategy_id, self.s2.strategy_id])

        expected = [
            {
                "strategy_id": self.s1.strategy_id,
                "strategy_name": self.s1.strategy_name,
                "field_name": "raw_event_id",
                "display_name": "Raw Event ID",
            },
            {
                "strategy_id": self.s1.strategy_id,
                "strategy_name": self.s1.strategy_name,
                "field_name": "operator",
                "display_name": "Operator",
            },
            {
                "strategy_id": self.s2.strategy_id,
                "strategy_name": self.s2.strategy_name,
                "field_name": "operator",
                "display_name": "Operator",
            },
            {
                "strategy_id": self.s2.strategy_id,
                "strategy_name": self.s2.strategy_name,
                "field_name": "event_time",
                "display_name": "Event Time",
            },
        ]

        self.assertEqual(self._sorted(result), self._sorted(expected))

    def test_list_event_fields_all_strategies_when_none(self):
        # 不传 strategy_ids，返回全部策略
        result = resource.risk.list_event_fields_by_strategy()

        # 预期包含 s1、s2 的基础字段，s3 无字段
        expected = [
            {
                "strategy_id": self.s1.strategy_id,
                "strategy_name": self.s1.strategy_name,
                "field_name": "raw_event_id",
                "display_name": "Raw Event ID",
            },
            {
                "strategy_id": self.s1.strategy_id,
                "strategy_name": self.s1.strategy_name,
                "field_name": "operator",
                "display_name": "Operator",
            },
            {
                "strategy_id": self.s2.strategy_id,
                "strategy_name": self.s2.strategy_name,
                "field_name": "operator",
                "display_name": "Operator",
            },
            {
                "strategy_id": self.s2.strategy_id,
                "strategy_name": self.s2.strategy_name,
                "field_name": "event_time",
                "display_name": "Event Time",
            },
        ]

        self.assertEqual(self._sorted(result), self._sorted(expected))
