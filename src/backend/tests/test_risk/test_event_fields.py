# -*- coding: utf-8 -*-
"""
ListEventFieldsByStrategy 接口单测

产品收敛：/api/v1/risks/event_fields/ 在原有返回（策略事件扩展字段 event_data_field_configs）基础上，
新增返回 7 个可检索事件基本信息字段（固定顺序前置，带 type=basic_event_field 标识）。
原有扩展字段返回行为保持不变：裸字段名、set 去重、id 格式为 {display_name}:{field_name}、无 type。
"""

from bk_resource import resource

from services.web.risk.constants import EventBasicField
from services.web.strategy_v2.constants import RiskLevel
from services.web.strategy_v2.models import Strategy
from tests.base import TestCase


class TestListEventFieldsByStrategy(TestCase):
    def setUp(self):
        super().setUp()
        self.strategy_1 = Strategy.objects.create(
            namespace="default",
            strategy_name="strategy-1",
            risk_level=RiskLevel.HIGH.value,
            event_data_field_configs=[
                {"field_name": "ip", "display_name": "Source IP"},
                {"field_name": "操作人用户名", "display_name": "操作人用户名"},
            ],
        )
        self.strategy_2 = Strategy.objects.create(
            namespace="default",
            strategy_name="strategy-2",
            risk_level=RiskLevel.MIDDLE.value,
            event_data_field_configs=[
                {"field_name": "ip", "display_name": "Source IP"},
                {"field_name": "domain", "display_name": "目标域名"},
            ],
        )

    def _basic_results(self, result):
        """前 7 项为固定基本信息字段（order 顺序与 EventBasicField.choices 一致）"""
        self.assertGreaterEqual(len(result), 7)
        expected = [
            {"field_name": field_name, "display_name": str(display_name)}
            for field_name, display_name in EventBasicField.choices
        ]
        basic_items = [{"field_name": item["field_name"], "display_name": item["display_name"]} for item in result[:7]]
        self.assertEqual(basic_items, expected)
        return {item["field_name"] for item in result[:7]}

    def test_basic_fields_first_and_strategy_ids_restrict_strategies(self):
        """传 strategy_ids 时只查指定策略，且 7 个基本信息字段固定顺序前置"""
        result = resource.risk.list_event_fields_by_strategy(strategy_ids=[self.strategy_1.strategy_id])

        basic_field_names = self._basic_results(result)
        self.assertEqual(len(EventBasicField.choices), 7)

        extended_items = result[7:]
        self.assertEqual(
            sorted((item["field_name"], item["display_name"]) for item in extended_items),
            sorted([("ip", "Source IP"), ("操作人用户名", "操作人用户名")]),
        )
        # 扩展字段在基本字段之后，且不与基本字段名冲突
        self.assertFalse(any(item["field_name"] in basic_field_names for item in extended_items))

    def test_without_strategy_ids_returns_all_strategies_extended_fields(self):
        """不传 strategy_ids 返回所有策略扩展字段（跨策略 set 去重）"""
        result = resource.risk.list_event_fields_by_strategy()

        self._basic_results(result)
        extended_names = {item["field_name"] for item in result[7:]}
        # ip 被两个策略重复声明 → 只保留一条
        self.assertEqual(extended_names, {"ip", "操作人用户名", "domain"})

    def test_strategy_ids_with_no_strategy_returns_only_7_basic_fields(self):
        """传入空/不存在的 strategy_ids：无扩展字段，仅 7 个基本信息字段"""
        result = resource.risk.list_event_fields_by_strategy(strategy_ids=[999999])

        self.assertEqual(len(result), 7)
        self._basic_results(result)

    def test_strategy_ids_empty_list_same_as_not_passing(self):
        """strategy_ids=[] 与不传等价：空列表视为"无筛选"，返回所有策略扩展字段（跨策略 set 去重）"""
        result = resource.risk.list_event_fields_by_strategy(strategy_ids=[])

        self._basic_results(result)
        extended_names = {item["field_name"] for item in result[7:]}
        self.assertEqual(extended_names, {"ip", "操作人用户名", "domain"})

    def test_basic_field_id_format(self):
        """基本信息字段 id 为 {display_name}:{field_name}"""
        result = resource.risk.list_event_fields_by_strategy(strategy_ids=[self.strategy_1.strategy_id])

        for item in result[:7]:
            self.assertEqual(item["id"], f"{item['display_name']}:{item['field_name']}")

    def test_extended_field_id_format(self):
        """扩展字段 id 保持原有格式 {display_name}:{field_name}"""
        result = resource.risk.list_event_fields_by_strategy(strategy_ids=[self.strategy_1.strategy_id])

        extended = {item["field_name"]: item for item in result[7:]}
        self.assertEqual(extended["ip"]["id"], "Source IP:ip")
        self.assertEqual(extended["操作人用户名"]["id"], "操作人用户名:操作人用户名")

    def test_display_names_use_product_style(self):
        """基本字段 display_name 为产品指定文案（纯中文，不带英文字段名后缀）"""
        result = resource.risk.list_event_fields_by_strategy(strategy_ids=[self.strategy_1.strategy_id])
        display_map = {item["field_name"]: item["display_name"] for item in result[:7]}

        self.assertEqual(display_map["raw_event_id"], "原始事件ID")
        self.assertEqual(display_map["operator"], "责任人")
        self.assertEqual(display_map["event_time"], "事件时间")

    def test_basic_fields_marked_with_type(self):
        """基本信息字段返回 type=basic_event_field 标识；扩展字段无 type，前端据此区分字段来源"""
        result = resource.risk.list_event_fields_by_strategy(strategy_ids=[self.strategy_1.strategy_id])

        for item in result[:7]:
            self.assertEqual(item["type"], "basic_event_field")
        for item in result[7:]:
            self.assertNotIn("type", item)
