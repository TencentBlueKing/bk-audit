# -*- coding: utf-8 -*-
from jinja2 import Environment, nodes

from tests.base import TestCase


class TestEventProviderMatch(TestCase):
    """测试 EventProvider.match() 方法"""

    def setUp(self):
        from services.web.risk.report.providers import EventProvider

        self.provider = EventProvider(risk_id="test_risk_123")

    def _parse_expr(self, expr: str) -> nodes.Node:
        """解析 Jinja2 表达式为 AST 节点"""
        env = Environment()
        template = env.parse(f"{{{{ {expr} }}}}")
        return template.body[0].nodes[0]

    def test_match_count_event_field(self):
        """测试匹配 count(event.event_id)"""
        node = self._parse_expr("count(event.event_id)")
        result = self.provider.match(node)

        self.assertTrue(result.matched)
        self.assertEqual(result.original_expr, "count(event.event_id)")
        self.assertEqual(result.call_args["function"], "count")
        self.assertEqual(result.call_args["field_name"], "event_id")
        self.assertIs(result.provider, self.provider)

    def test_match_first_event_field(self):
        """测试匹配 first(event.username)"""
        node = self._parse_expr("first(event.username)")
        result = self.provider.match(node)

        self.assertTrue(result.matched)
        self.assertEqual(result.call_args["function"], "first")
        self.assertEqual(result.call_args["field_name"], "username")

    def test_match_latest_event_field(self):
        """测试匹配 latest(event.ip)"""
        node = self._parse_expr("latest(event.ip)")
        result = self.provider.match(node)

        self.assertTrue(result.matched)
        self.assertEqual(result.call_args["function"], "latest")

    def test_match_list_distinct_event_field(self):
        """测试匹配 list_distinct(event.action)"""
        node = self._parse_expr("list_distinct(event.action)")
        result = self.provider.match(node)

        self.assertTrue(result.matched)
        self.assertEqual(result.call_args["function"], "list_distinct")

    def test_match_all_aggregation_functions(self):
        """测试匹配所有支持的聚合函数"""
        from services.web.risk.constants import AggregationFunction

        for func in AggregationFunction.values:
            with self.subTest(function=func):
                node = self._parse_expr(f"{func}(event.field)")
                result = self.provider.match(node)
                self.assertTrue(result.matched, f"函数 {func} 应该被匹配")
                self.assertEqual(result.call_args["function"], func)

    def test_no_match_non_event_field(self):
        """测试不匹配非 event 字段"""
        node = self._parse_expr("count(risk.field)")
        result = self.provider.match(node)

        self.assertFalse(result.matched)

    def test_no_match_simple_variable(self):
        """测试不匹配简单变量"""
        node = self._parse_expr("event.field")
        result = self.provider.match(node)

        self.assertFalse(result.matched)

    def test_no_match_unknown_function(self):
        """测试不匹配未知函数"""
        node = self._parse_expr("unknown_func(event.field)")
        result = self.provider.match(node)

        self.assertFalse(result.matched)

    def test_no_match_no_args(self):
        """测试不匹配无参数的函数调用"""
        node = self._parse_expr("count()")
        result = self.provider.match(node)

        self.assertFalse(result.matched)


class TestEventProviderGet(TestCase):
    """测试 EventProvider.get() 方法（Mock 实现）"""

    def setUp(self):
        from services.web.risk.report.providers import EventProvider

        self.provider = EventProvider(risk_id="test_risk_123")

    def test_get_returns_mock_value(self):
        """测试 get 返回 mock 值"""
        result = self.provider.get(function="count", field_name="event_id")
        self.assertEqual(result, "mock_count_event_id")

    def test_get_first_returns_mock_value(self):
        """测试 first 返回 mock 值"""
        result = self.provider.get(function="first", field_name="username")
        self.assertEqual(result, "mock_first_username")

    def test_get_without_function_returns_none(self):
        """测试无 function 参数返回 None"""
        result = self.provider.get(field_name="event_id")
        self.assertIsNone(result)

    def test_get_without_field_name_returns_none(self):
        """测试无 field_name 参数返回 None"""
        result = self.provider.get(function="count")
        self.assertIsNone(result)

    def test_get_unsupported_function_returns_none(self):
        """测试不支持的函数返回 None"""
        result = self.provider.get(function="unsupported", field_name="event_id")
        self.assertIsNone(result)
