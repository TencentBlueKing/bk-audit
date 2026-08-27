# -*- coding: utf-8 -*-
"""
分派规则匹配引擎单元测试

覆盖 dispatch.py 中的核心逻辑：
- resolve_field: 字段解析（event_data 路径下钻）
- evaluate: 条件树递归求值
- apply_condition: 原子条件求值
- 操作符实现: EQ/NEQ/GT/GTE/LT/LTE/INCLUDE/EXCLUDE/LIKE/NOT_LIKE/ISNULL/NOTNULL/BETWEEN/MATCH_ANY/MATCH_ALL/JSON_CONTAINS
- match_dispatch_rule: 核心匹配函数
- to_condition_tree: 条件树转换
- evaluate_is_empty: 空条件树判定
"""

from unittest import TestCase

import pytest

from core.sql.constants import FilterConnector, Operator
from services.web.strategy_v2.constants import DispatchMode
from services.web.strategy_v2.handlers.dispatch import (
    DispatchCondition,
    DispatchConditionNode,
    DispatchResult,
    _compare,
    _stringify,
    apply_condition,
    evaluate,
    evaluate_is_empty,
    match_dispatch_rule,
    resolve_field,
    to_condition_tree,
)


@pytest.mark.django_db
class TestResolveField(TestCase):
    """resolve_field: 字段解析测试"""

    def test_resolve_simple_field(self):
        """普通字段直接从 ctx 取值"""
        ctx = {"risk_level": "HIGH", "operator": "admin"}
        self.assertEqual(resolve_field("risk_level", ctx), "HIGH")
        self.assertEqual(resolve_field("operator", ctx), "admin")

    def test_resolve_missing_field_returns_none(self):
        """字段不存在时返回 None"""
        ctx = {"risk_level": "HIGH"}
        self.assertIsNone(resolve_field("operator", ctx))

    def test_resolve_empty_field_returns_none(self):
        """空字段表达式返回 None"""
        ctx = {"risk_level": "HIGH"}
        self.assertIsNone(resolve_field("", ctx))

    def test_resolve_event_data_nested(self):
        """event_data.xxx.yyy 路径下钻"""
        ctx = {"event_data": {"resource_type": "host", "detail": {"ip": "127.0.0.1"}}}
        self.assertEqual(resolve_field("event_data.resource_type", ctx), "host")
        self.assertEqual(resolve_field("event_data.detail.ip", ctx), "127.0.0.1")

    def test_resolve_event_data_missing_key(self):
        """event_data 路径中某个 key 不存在"""
        ctx = {"event_data": {"resource_type": "host"}}
        self.assertIsNone(resolve_field("event_data.missing_key", ctx))

    def test_resolve_event_data_not_dict(self):
        """event_data 不是 dict 时返回 None"""
        ctx = {"event_data": "not_a_dict"}
        self.assertIsNone(resolve_field("event_data.key", ctx))

    def test_resolve_event_data_none(self):
        """event_data 为 None 时返回 None"""
        ctx = {"event_data": None}
        self.assertIsNone(resolve_field("event_data.key", ctx))


@pytest.mark.django_db
class TestStringify(TestCase):
    """_stringify: 类型转换辅助测试"""

    def test_stringify_none(self):
        self.assertIsNone(_stringify(None))

    def test_stringify_bool(self):
        self.assertEqual(_stringify(True), "true")
        self.assertEqual(_stringify(False), "false")

    def test_stringify_int(self):
        self.assertEqual(_stringify(42), "42")

    def test_stringify_float(self):
        self.assertEqual(_stringify(3.14), "3.14")

    def test_stringify_list(self):
        self.assertEqual(_stringify([1, 2, 3]), "1,2,3")

    def test_stringify_tuple(self):
        self.assertEqual(_stringify((1, 2)), "1,2")

    def test_stringify_str(self):
        self.assertEqual(_stringify("hello"), "hello")


@pytest.mark.django_db
class TestCompare(TestCase):
    """_compare: 宽松相等比较测试"""

    def test_compare_same_type(self):
        self.assertTrue(_compare(42, 42))
        self.assertFalse(_compare(42, 43))

    def test_compare_int_vs_str(self):
        """类型不匹配时退化为字符串比较"""
        self.assertTrue(_compare(42, "42"))
        self.assertFalse(_compare(42, "43"))

    def test_compare_bool_vs_str(self):
        self.assertTrue(_compare(True, "true"))
        self.assertFalse(_compare(True, "false"))

    def test_compare_none(self):
        self.assertTrue(_compare(None, None))
        self.assertFalse(_compare(None, "None"))

    def test_compare_list_vs_str(self):
        self.assertTrue(_compare([1, 2], "1,2"))


@pytest.mark.django_db
class TestOperators(TestCase):
    """操作符实现测试"""

    def _make_condition(self, field, operator, filters=None, filter_val=""):
        return DispatchCondition(field=field, operator=operator, filters=filters or [], filter=filter_val)

    def _eval_condition(self, field, operator, ctx, filters=None, filter_val=""):
        cond = self._make_condition(field, operator, filters, filter_val)
        return apply_condition(cond, ctx)

    def test_eq(self):
        ctx = {"status": "active"}
        self.assertTrue(self._eval_condition("status", Operator.EQ, ctx, filter_val="active"))
        self.assertFalse(self._eval_condition("status", Operator.EQ, ctx, filter_val="inactive"))

    def test_neq(self):
        ctx = {"status": "active"}
        self.assertTrue(self._eval_condition("status", Operator.NEQ, ctx, filter_val="inactive"))
        self.assertFalse(self._eval_condition("status", Operator.NEQ, ctx, filter_val="active"))

    def test_gt(self):
        ctx = {"count": 10}
        self.assertTrue(self._eval_condition("count", Operator.GT, ctx, filter_val="5"))
        self.assertFalse(self._eval_condition("count", Operator.GT, ctx, filter_val="10"))
        self.assertFalse(self._eval_condition("count", Operator.GT, ctx, filter_val="15"))

    def test_gte(self):
        ctx = {"count": 10}
        self.assertTrue(self._eval_condition("count", Operator.GTE, ctx, filter_val="10"))
        self.assertTrue(self._eval_condition("count", Operator.GTE, ctx, filter_val="5"))
        self.assertFalse(self._eval_condition("count", Operator.GTE, ctx, filter_val="15"))

    def test_lt(self):
        ctx = {"count": 10}
        self.assertTrue(self._eval_condition("count", Operator.LT, ctx, filter_val="15"))
        self.assertFalse(self._eval_condition("count", Operator.LT, ctx, filter_val="10"))
        self.assertFalse(self._eval_condition("count", Operator.LT, ctx, filter_val="5"))

    def test_lte(self):
        ctx = {"count": 10}
        self.assertTrue(self._eval_condition("count", Operator.LTE, ctx, filter_val="10"))
        self.assertTrue(self._eval_condition("count", Operator.LTE, ctx, filter_val="15"))
        self.assertFalse(self._eval_condition("count", Operator.LTE, ctx, filter_val="5"))

    def test_include(self):
        ctx = {"operator": "admin"}
        self.assertTrue(self._eval_condition("operator", Operator.INCLUDE, ctx, filters=["admin", "user"]))
        self.assertFalse(self._eval_condition("operator", Operator.INCLUDE, ctx, filters=["user", "guest"]))

    def test_exclude(self):
        ctx = {"operator": "admin"}
        self.assertTrue(self._eval_condition("operator", Operator.EXCLUDE, ctx, filters=["user", "guest"]))
        self.assertFalse(self._eval_condition("operator", Operator.EXCLUDE, ctx, filters=["admin", "user"]))

    def test_like(self):
        ctx = {"name": "test_resource_001"}
        self.assertTrue(self._eval_condition("name", Operator.LIKE, ctx, filter_val="test_%"))
        self.assertFalse(self._eval_condition("name", Operator.LIKE, ctx, filter_val="prod_%"))

    def test_not_like(self):
        ctx = {"name": "test_resource_001"}
        self.assertTrue(self._eval_condition("name", Operator.NOT_LIKE, ctx, filter_val="prod_%"))
        self.assertFalse(self._eval_condition("name", Operator.NOT_LIKE, ctx, filter_val="test_%"))

    def test_isnull(self):
        ctx = {"value": None}
        self.assertTrue(self._eval_condition("value", Operator.ISNULL, ctx))
        ctx2 = {"value": "not_none"}
        self.assertFalse(self._eval_condition("value", Operator.ISNULL, ctx2))

    def test_notnull(self):
        ctx = {"value": "not_none"}
        self.assertTrue(self._eval_condition("value", Operator.NOTNULL, ctx))
        ctx2 = {"value": None}
        self.assertFalse(self._eval_condition("value", Operator.NOTNULL, ctx2))

    def test_between(self):
        ctx = {"count": 10}
        self.assertTrue(self._eval_condition("count", Operator.BETWEEN, ctx, filters=[5, 15]))
        self.assertTrue(self._eval_condition("count", Operator.BETWEEN, ctx, filters=[10, 10]))
        self.assertFalse(self._eval_condition("count", Operator.BETWEEN, ctx, filters=[11, 20]))

    def test_between_invalid_filters(self):
        """BETWEEN 需要恰好 2 个 filter 值"""
        ctx = {"count": 10}
        self.assertFalse(self._eval_condition("count", Operator.BETWEEN, ctx, filters=[5]))
        self.assertFalse(self._eval_condition("count", Operator.BETWEEN, ctx, filters=[1, 2, 3]))

    def test_match_any(self):
        ctx = {"level": "HIGH"}
        self.assertTrue(self._eval_condition("level", Operator.MATCH_ANY, ctx, filters=["HIGH", "MEDIUM"]))
        self.assertFalse(self._eval_condition("level", Operator.MATCH_ANY, ctx, filters=["LOW", "MEDIUM"]))

    def test_match_all(self):
        """MATCH_ALL 要求值与所有 filter 都匹配（通常用于多值字段）"""
        ctx = {"tags": "tag1"}
        self.assertTrue(self._eval_condition("tags", Operator.MATCH_ALL, ctx, filters=["tag1"]))
        self.assertFalse(self._eval_condition("tags", Operator.MATCH_ALL, ctx, filters=["tag1", "tag2"]))

    def test_json_contains(self):
        ctx = {"data": "admin"}
        self.assertTrue(self._eval_condition("data", Operator.JSON_CONTAINS, ctx, filters=["admin"]))
        self.assertFalse(self._eval_condition("data", Operator.JSON_CONTAINS, ctx, filters=["user"]))

    def test_unknown_operator_in_py_operators_returns_false(self):
        """PY_OPERATORS 中不存在的操作符返回 False"""
        ctx = {"field": "value"}
        # 使用一个合法的 Operator 值，但手动构造一个不在 PY_OPERATORS 中的情况
        # 通过 mock 来模拟操作符不在 PY_OPERATORS 中的场景
        from unittest import mock as mock_module

        cond = DispatchCondition(field="field", operator=Operator.EQ, filters=[], filter="value")
        with mock_module.patch.dict("services.web.strategy_v2.handlers.dispatch.PY_OPERATORS", clear=True):
            self.assertFalse(apply_condition(cond, ctx))


@pytest.mark.django_db
class TestEvaluate(TestCase):
    """evaluate: 条件树递归求值测试"""

    def test_none_node_returns_true(self):
        """None 节点视为无条件匹配"""
        self.assertTrue(evaluate(None, {}))

    def test_empty_conditions_returns_true(self):
        """空条件列表视为无条件匹配"""
        node = DispatchConditionNode(connector=FilterConnector.AND, conditions=[])
        self.assertTrue(evaluate(node, {}))

    def test_single_leaf_condition(self):
        """单个叶子条件"""
        cond = DispatchCondition(field="status", operator=Operator.EQ, filter="active")
        node = DispatchConditionNode(condition=cond)
        ctx = {"status": "active"}
        self.assertTrue(evaluate(node, ctx))
        ctx2 = {"status": "inactive"}
        self.assertFalse(evaluate(node, ctx2))

    def test_and_connector(self):
        """AND 连接器：所有子节点都为真"""
        cond1 = DispatchCondition(field="status", operator=Operator.EQ, filter="active")
        cond2 = DispatchCondition(field="level", operator=Operator.EQ, filter="HIGH")
        node = DispatchConditionNode(
            connector=FilterConnector.AND,
            conditions=[
                DispatchConditionNode(condition=cond1),
                DispatchConditionNode(condition=cond2),
            ],
        )
        self.assertTrue(evaluate(node, {"status": "active", "level": "HIGH"}))
        self.assertFalse(evaluate(node, {"status": "active", "level": "LOW"}))
        self.assertFalse(evaluate(node, {"status": "inactive", "level": "HIGH"}))

    def test_or_connector(self):
        """OR 连接器：任一子节点为真"""
        cond1 = DispatchCondition(field="status", operator=Operator.EQ, filter="active")
        cond2 = DispatchCondition(field="level", operator=Operator.EQ, filter="HIGH")
        node = DispatchConditionNode(
            connector=FilterConnector.OR,
            conditions=[
                DispatchConditionNode(condition=cond1),
                DispatchConditionNode(condition=cond2),
            ],
        )
        self.assertTrue(evaluate(node, {"status": "active", "level": "LOW"}))
        self.assertTrue(evaluate(node, {"status": "inactive", "level": "HIGH"}))
        self.assertFalse(evaluate(node, {"status": "inactive", "level": "LOW"}))

    def test_nested_conditions(self):
        """嵌套条件树：(status=active AND level=HIGH) OR operator=admin"""
        cond_status = DispatchCondition(field="status", operator=Operator.EQ, filter="active")
        cond_level = DispatchCondition(field="level", operator=Operator.EQ, filter="HIGH")
        cond_operator = DispatchCondition(field="operator", operator=Operator.EQ, filter="admin")
        node = DispatchConditionNode(
            connector=FilterConnector.OR,
            conditions=[
                DispatchConditionNode(
                    connector=FilterConnector.AND,
                    conditions=[
                        DispatchConditionNode(condition=cond_status),
                        DispatchConditionNode(condition=cond_level),
                    ],
                ),
                DispatchConditionNode(condition=cond_operator),
            ],
        )
        # 满足 status=active AND level=HIGH
        self.assertTrue(evaluate(node, {"status": "active", "level": "HIGH", "operator": "user"}))
        # 满足 operator=admin
        self.assertTrue(evaluate(node, {"status": "inactive", "level": "LOW", "operator": "admin"}))
        # 都不满足
        self.assertFalse(evaluate(node, {"status": "inactive", "level": "LOW", "operator": "user"}))


@pytest.mark.django_db
class TestToConditionTree(TestCase):
    """to_condition_tree: 条件树转换测试"""

    def test_convert_simple_dict(self):
        """简单 dict 转换为 DispatchConditionNode"""
        cond_dict = {
            "condition": {"field": "status", "operator": "eq", "filters": ["active"]},
        }
        node = to_condition_tree(cond_dict)
        self.assertIsNotNone(node.condition)
        self.assertEqual(node.condition.field, "status")
        self.assertEqual(node.condition.operator, Operator.EQ)

    def test_convert_nested_dict(self):
        """嵌套 dict 转换"""
        cond_dict = {
            "connector": "and",
            "conditions": [
                {"condition": {"field": "status", "operator": "eq", "filters": ["active"]}},
                {"condition": {"field": "level", "operator": "eq", "filters": ["HIGH"]}},
            ],
        }
        node = to_condition_tree(cond_dict)
        self.assertIsNone(node.condition)
        self.assertEqual(len(node.conditions), 2)
        self.assertEqual(node.connector, FilterConnector.AND)

    def test_convert_already_node(self):
        """已经是 DispatchConditionNode 时直接返回"""
        cond = DispatchCondition(field="status", operator=Operator.EQ, filter="active")
        node = DispatchConditionNode(condition=cond)
        result = to_condition_tree(node)
        self.assertIs(result, node)


@pytest.mark.django_db
class TestEvaluateIsEmpty(TestCase):
    """evaluate_is_empty: 空条件树判定测试"""

    def test_none_is_empty(self):
        self.assertTrue(evaluate_is_empty(None))

    def test_empty_dict_is_empty(self):
        self.assertTrue(evaluate_is_empty({}))

    def test_dict_with_empty_conditions_is_empty(self):
        self.assertTrue(evaluate_is_empty({"conditions": []}))

    def test_dict_with_condition_is_not_empty(self):
        cond = {"field": "status", "operator": "eq", "filters": ["active"]}
        self.assertFalse(evaluate_is_empty({"condition": cond}))

    def test_dict_with_nested_empty_conditions_is_empty(self):
        self.assertTrue(evaluate_is_empty({"conditions": [{"conditions": []}]}))

    def test_node_with_condition_is_not_empty(self):
        cond = DispatchCondition(field="status", operator=Operator.EQ, filter="active")
        node = DispatchConditionNode(condition=cond)
        self.assertFalse(evaluate_is_empty(node))

    def test_node_with_empty_conditions_is_empty(self):
        node = DispatchConditionNode(conditions=[])
        self.assertTrue(evaluate_is_empty(node))


@pytest.mark.django_db
class TestMatchDispatchRule(TestCase):
    """match_dispatch_rule: 核心匹配函数测试"""

    def _make_rule(self, rule_id, conditions=None, is_default=False, target_scene_id=1):
        """创建模拟的 DispatchRule 对象"""
        from types import SimpleNamespace

        return SimpleNamespace(
            rule_id=rule_id,
            conditions=conditions or {},
            is_default=is_default,
            target_scene_id=target_scene_id,
            dispatch_mode=DispatchMode.DIRECT,
            processor=[1001],
            follower=[1002],
            confirmer=[1003],
        )

    def test_no_rules_returns_miss(self):
        """无规则时返回 miss"""
        result = match_dispatch_rule(ctx={}, rules=[], rule_order=[])
        self.assertFalse(result.matched)

    def test_single_default_rule(self):
        """单条默认规则：直接命中"""
        rule = self._make_rule(1, is_default=True)
        result = match_dispatch_rule(ctx={}, rules=[rule], rule_order=[1])
        self.assertTrue(result.matched)
        self.assertEqual(result.rule.rule_id, 1)
        self.assertEqual(result.target_scene_id, 1)

    def test_default_rule_with_empty_conditions(self):
        """空条件树的规则视为默认规则"""
        rule = self._make_rule(1, conditions={})
        result = match_dispatch_rule(ctx={}, rules=[rule], rule_order=[1])
        self.assertTrue(result.matched)
        self.assertEqual(result.rule.rule_id, 1)

    def test_priority_order(self):
        """按 rule_order 优先级匹配"""
        rule1 = self._make_rule(1, conditions={"condition": {"field": "level", "operator": "eq", "filters": ["HIGH"]}})
        rule2 = self._make_rule(2, conditions={"condition": {"field": "level", "operator": "eq", "filters": ["LOW"]}})
        # rule_order: [2, 1] 表示 rule2 优先级更高
        result = match_dispatch_rule(
            ctx={"level": "LOW"},
            rules=[rule1, rule2],
            rule_order=[2, 1],
        )
        self.assertTrue(result.matched)
        self.assertEqual(result.rule.rule_id, 2)

    def test_first_match_wins(self):
        """首匹配：多个规则都匹配时返回第一个"""
        rule1 = self._make_rule(1, conditions={"condition": {"field": "level", "operator": "eq", "filters": ["HIGH"]}})
        rule2 = self._make_rule(2, conditions={"condition": {"field": "level", "operator": "eq", "filters": ["HIGH"]}})
        result = match_dispatch_rule(
            ctx={"level": "HIGH"},
            rules=[rule1, rule2],
            rule_order=[1, 2],
        )
        self.assertTrue(result.matched)
        self.assertEqual(result.rule.rule_id, 1)

    def test_non_default_rule_miss_falls_to_default(self):
        """非默认规则未命中时降级到默认规则"""
        rule_cond = self._make_rule(
            1, conditions={"condition": {"field": "level", "operator": "eq", "filters": ["HIGH"]}}
        )
        rule_default = self._make_rule(2, is_default=True)
        result = match_dispatch_rule(
            ctx={"level": "LOW"},  # 不匹配 rule_cond
            rules=[rule_cond, rule_default],
            rule_order=[1, 2],
        )
        self.assertTrue(result.matched)
        self.assertEqual(result.rule.rule_id, 2)  # 命中默认规则

    def test_dispatch_result_fields(self):
        """DispatchResult 包含正确的分派信息"""
        rule = self._make_rule(1, is_default=True, target_scene_id=42)
        result = match_dispatch_rule(ctx={}, rules=[rule], rule_order=[1])
        self.assertTrue(result.matched)
        self.assertEqual(result.dispatch_mode, DispatchMode.DIRECT)
        self.assertEqual(result.target_scene_id, 42)
        self.assertEqual(result.processor, [1001])
        self.assertEqual(result.follower, [1002])
        self.assertEqual(result.confirmer, [1003])

    def test_complex_condition_match(self):
        """复杂条件匹配：event_data 字段 + AND/OR"""
        rule = self._make_rule(
            1,
            conditions={
                "connector": "and",
                "conditions": [
                    {"condition": {"field": "event_data.resource_type", "operator": "eq", "filters": ["host"]}},
                    {
                        "connector": "or",
                        "conditions": [
                            {"condition": {"field": "risk_level", "operator": "eq", "filters": ["HIGH"]}},
                            {"condition": {"field": "risk_level", "operator": "eq", "filters": ["MEDIUM"]}},
                        ],
                    },
                ],
            },
        )
        rule_default = self._make_rule(2, is_default=True)
        # 匹配：resource_type=host 且 risk_level=HIGH
        result = match_dispatch_rule(
            ctx={"event_data": {"resource_type": "host"}, "risk_level": "HIGH"},
            rules=[rule, rule_default],
            rule_order=[1, 2],
        )
        self.assertTrue(result.matched)
        self.assertEqual(result.rule.rule_id, 1)

        # 不匹配：resource_type=vm（第一个条件不满足）
        result = match_dispatch_rule(
            ctx={"event_data": {"resource_type": "vm"}, "risk_level": "HIGH"},
            rules=[rule, rule_default],
            rule_order=[1, 2],
        )
        self.assertTrue(result.matched)
        self.assertEqual(result.rule.rule_id, 2)  # 降级到默认规则

    def test_rule_order_not_in_list(self):
        """rule_id 不在 rule_order 中时排到最后"""
        rule1 = self._make_rule(1, is_default=True)
        rule2 = self._make_rule(2, conditions={"condition": {"field": "level", "operator": "eq", "filters": ["HIGH"]}})
        # rule_order 只包含 rule1，rule2 优先级最低
        result = match_dispatch_rule(
            ctx={"level": "HIGH"},
            rules=[rule1, rule2],
            rule_order=[1],
        )
        # rule1 是默认规则，rule2 虽然匹配但优先级低（排在最后）
        # 由于 rule1 是默认规则会跳过条件判定，rule2 会先被评估
        self.assertTrue(result.matched)
        self.assertEqual(result.rule.rule_id, 2)


@pytest.mark.django_db
class TestDispatchResult(TestCase):
    """DispatchResult 数据类测试"""

    def test_miss(self):
        result = DispatchResult.miss()
        self.assertFalse(result.matched)
        self.assertIsNone(result.rule)

    def test_hit(self):
        from types import SimpleNamespace

        rule = SimpleNamespace(
            rule_id=1,
            dispatch_mode=DispatchMode.DIRECT,
            target_scene_id=42,
            processor=[1001],
            follower=[1002],
            confirmer=[1003],
        )
        result = DispatchResult.hit(rule)
        self.assertTrue(result.matched)
        self.assertEqual(result.rule.rule_id, 1)
        self.assertEqual(result.dispatch_mode, DispatchMode.DIRECT)
        self.assertEqual(result.target_scene_id, 42)
        self.assertEqual(result.processor, [1001])
        self.assertEqual(result.follower, [1002])
        self.assertEqual(result.confirmer, [1003])
