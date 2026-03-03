# -*- coding: utf-8 -*-
"""
多字段排序纯单元测试：Serializer、build_preserved_order_queryset、BKBase Resolver/Assembler。
ListRisk 各子类的排序集成测试见 test_retrieve_risk.py 对应的 TestCase。
"""

from sqlglot import exp

from services.web.risk.converter.bkbase import BkBaseFieldResolver, FinalSelectAssembler
from services.web.risk.serializers import ListRiskRequestSerializer
from tests.base import TestCase


class TestListRiskRequestSerializerSort(TestCase):
    def test_sort_param_produces_order_fields(self):
        data = {"sort": ["-event_time", "-risk_id"]}
        s = ListRiskRequestSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data["order_fields"], ["-event_time", "-risk_id"])

    def test_sort_risk_level_converted(self):
        data = {"sort": ["-risk_level", "-event_time"]}
        s = ListRiskRequestSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(
            s.validated_data["order_fields"],
            ["-strategy__risk_level", "-event_time"],
        )

    def test_no_sort_defaults_to_empty(self):
        data = {}
        s = ListRiskRequestSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertIn("order_fields", s.validated_data)
        self.assertEqual(s.validated_data["order_fields"], [])

    def test_sort_empty_list_produces_empty_order_fields(self):
        data = {"sort": []}
        s = ListRiskRequestSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data["order_fields"], [])

    def test_sort_event_data_without_filters_rejected(self):
        data = {"sort": ["-event_data.ip"]}
        s = ListRiskRequestSerializer(data=data)
        self.assertFalse(s.is_valid())

    def test_sort_event_data_with_matching_filter_accepted(self):
        data = {
            "sort": ["-event_data.ip"],
            "event_filters": [{"field": "ip", "display_name": "IP", "operator": "=", "value": "1.2.3.4"}],
        }
        s = ListRiskRequestSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_sort_event_data_with_unmatched_filter_rejected(self):
        data = {
            "sort": ["-event_data.ip"],
            "event_filters": [{"field": "host", "display_name": "Host", "operator": "=", "value": "abc"}],
        }
        s = ListRiskRequestSerializer(data=data)
        self.assertFalse(s.is_valid())

    def test_sort_multiple_event_data_fields_accepted(self):
        data = {
            "sort": ["-event_data.ip", "-event_data.amount"],
            "event_filters": [
                {"field": "ip", "display_name": "IP", "operator": "=", "value": "1.2.3.4"},
                {"field": "amount", "display_name": "Amount", "operator": "=", "value": "100"},
            ],
        }
        s = ListRiskRequestSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)


class TestBkBaseFieldResolverMultiSort(TestCase):
    def test_resolve_value_fields_multi_order(self):
        resolver = BkBaseFieldResolver(
            order_fields=["-event_time", "-risk_id", "-last_operate_time"],
            event_filters=[],
            duplicate_field_map={},
        )
        fields = resolver.resolve_value_fields(["risk_id", "strategy_id", "event_time"])
        self.assertIn("last_operate_time", fields)

    def test_resolve_value_fields_skips_event_data(self):
        resolver = BkBaseFieldResolver(
            order_fields=["-event_data.amount"],
            event_filters=[],
            duplicate_field_map={},
        )
        fields = resolver.resolve_value_fields(["risk_id"])
        self.assertNotIn("event_data.amount", fields)
        self.assertNotIn("amount", fields)

    def test_resolve_value_fields_risk_level_adds_event_time(self):
        resolver = BkBaseFieldResolver(
            order_fields=["-strategy__risk_level"],
            event_filters=[],
            duplicate_field_map={},
        )
        fields = resolver.resolve_value_fields(["risk_id", "strategy_id"])
        self.assertIn("strategy__risk_level", fields)
        self.assertIn("event_time", fields)


class TestFinalSelectAssemblerMultiSort(TestCase):
    def test_build_order_expressions_multi_fields(self):
        resolver = BkBaseFieldResolver(
            order_fields=["-strategy__risk_level", "-event_time", "-risk_id"],
            event_filters=[],
            duplicate_field_map={},
        )
        assembler = FinalSelectAssembler(resolver)
        expressions = assembler._build_order_expressions(resolver.order_fields, has_event_join=False)
        self.assertEqual(len(expressions), 3)
        self.assertTrue(all(isinstance(e, exp.Ordered) for e in expressions))

    def test_build_order_expressions_single_field_backward_compat(self):
        resolver = BkBaseFieldResolver(
            order_fields=["-event_time"],
            event_filters=[],
            duplicate_field_map={},
        )
        assembler = FinalSelectAssembler(resolver)
        expressions = assembler._build_order_expressions(resolver.order_fields, has_event_join=False)
        self.assertEqual(len(expressions), 1)
        self.assertIsInstance(expressions[0], exp.Ordered)

    def test_build_order_expressions_event_data_returns_event_sort_only(self):
        """有 event_data 排序时，直接返回 __order_event_field + dteventtimestamp DESC，忽略其他字段"""
        resolver = BkBaseFieldResolver(
            order_fields=["-event_data.ip", "-risk_id"],
            event_filters=[],
            duplicate_field_map={},
        )
        assembler = FinalSelectAssembler(resolver)
        expressions = assembler._build_order_expressions(resolver.order_fields, has_event_join=True)
        self.assertEqual(len(expressions), 2)
        sql_parts = [e.sql() for e in expressions]
        combined = "".join(sql_parts).lower()
        self.assertIn("__order_event_field", combined)
        self.assertIn("dteventtimestamp", combined)
