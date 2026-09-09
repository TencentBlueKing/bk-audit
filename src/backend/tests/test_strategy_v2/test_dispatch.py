# -*- coding: utf-8 -*-
"""
分派规则匹配引擎单元测试

覆盖 dispatch.py 中的核心逻辑：
- resolve_field: 字段解析（select 字段按 display_name 取 event_data / 直连字段按 raw_name 取 ctx）
- evaluate: 条件树递归求值
- apply_condition: 原子条件求值
- 操作符实现: EQ/NEQ/GT/GTE/LT/LTE/INCLUDE/EXCLUDE/LIKE/NOT_LIKE/ISNULL/NOTNULL/BETWEEN/MATCH_ANY/MATCH_ALL/JSON_CONTAINS
- match_dispatch_rule: 核心匹配函数
- to_condition_tree: 条件树转换
- evaluate_is_empty: 空条件树判定

条件树结构：与发现规则 where 一致（core.sql.model.WhereCondition，field 为字段对象）
"""

from unittest import TestCase

import pytest

from core.sql.constants import FilterConnector, Operator
from core.sql.model import Condition
from core.sql.model import Field as ConditionField
from core.sql.model import WhereCondition
from services.web.strategy_v2.constants import DispatchMode
from services.web.strategy_v2.handlers.dispatch import (
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


def make_field(raw_name, display_name=None, table="event", field_type="string") -> ConditionField:
    """构造条件字段对象（结构同发现规则 where 的 field）"""
    return ConditionField(
        table=table,
        raw_name=raw_name,
        display_name=display_name or raw_name,
        field_type=field_type,
    )


def make_field_dict(raw_name, display_name=None, table="event", field_type="string") -> dict:
    """构造条件字段对象 dict（请求/存储形态）"""
    return {
        "table": table,
        "raw_name": raw_name,
        "display_name": display_name or raw_name,
        "field_type": field_type,
        "keys": [],
    }


def make_condition_dict(field_name, operator="eq", filters=None, filter_val="", display_name=None) -> dict:
    """构造条件叶子 dict（请求/存储形态）"""
    return {
        "field": make_field_dict(field_name, display_name=display_name),
        "operator": operator,
        "filters": filters or [],
        "filter": filter_val,
    }


@pytest.mark.django_db
class TestResolveField(TestCase):
    """resolve_field: 字段解析测试"""

    def test_resolve_direct_field(self):
        """直连字段：raw_name 直接从 ctx 取值"""
        ctx = {"risk_level": "HIGH", "operator": "admin"}
        self.assertEqual(resolve_field(make_field("risk_level"), ctx), "HIGH")
        self.assertEqual(resolve_field(make_field("operator"), ctx), "admin")

    def test_resolve_select_field_from_event_data(self):
        """select 字段：display_name 命中 event_data 键时取值"""
        ctx = {"event_data": {"资源类型": "host"}, "operator": "admin"}
        field = make_field("resource_type", display_name="资源类型")
        self.assertEqual(resolve_field(field, ctx), "host")

    def test_resolve_select_field_takes_precedence(self):
        """display_name 命中 event_data 时优先于 raw_name 直连取值"""
        ctx = {"risk_level": "HIGH", "event_data": {"risk_level": "MIDDLE"}}
        field = make_field("risk_level", display_name="risk_level")
        self.assertEqual(resolve_field(field, ctx), "MIDDLE")

    def test_resolve_missing_field_returns_none(self):
        """字段不存在时返回 None"""
        ctx = {"risk_level": "HIGH"}
        self.assertIsNone(resolve_field(make_field("operator"), ctx))

    def test_resolve_select_field_missing_key_returns_none(self):
        """select 字段的 display_name 不在 event_data 中且 raw_name 不在 ctx 中"""
        ctx = {"event_data": {"resource_type": "host"}}
        self.assertIsNone(resolve_field(make_field("risk_type", display_name="风险类型"), ctx))

    def test_resolve_none_field_returns_none(self):
        """空字段对象返回 None"""
        ctx = {"risk_level": "HIGH"}
        self.assertIsNone(resolve_field(None, ctx))

    def test_resolve_event_data_not_dict(self):
        """event_data 不是 dict 时按直连字段处理"""
        ctx = {"event_data": "not_a_dict"}
        self.assertIsNone(resolve_field(make_field("risk_level"), ctx))

    def test_resolve_event_data_none(self):
        """event_data 为 None 时按直连字段处理"""
        ctx = {"event_data": None}
        self.assertIsNone(resolve_field(make_field("risk_level"), ctx))


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

    def _make_condition(self, field_name, operator, filters=None, filter_val=""):
        return Condition(field=make_field(field_name), operator=operator, filters=filters or [], filter=filter_val)

    def _eval_condition(self, field_name, operator, ctx, filters=None, filter_val=""):
        cond = self._make_condition(field_name, operator, filters, filter_val)
        return apply_condition(cond, ctx)

    def test_eq(self):
        ctx = {"status": "active"}
        self.assertTrue(self._eval_condition("status", Operator.EQ, ctx, filter_val="active"))
        self.assertFalse(self._eval_condition("status", Operator.EQ, ctx, filter_val="inactive"))

    def test_eq_on_select_field(self):
        """select 字段条件：按 display_name 从 event_data 取值"""
        ctx = {"event_data": {"资源类型": "host"}}
        cond = Condition(
            field=make_field("resource_type", display_name="资源类型"),
            operator=Operator.EQ,
            filters=[],
            filter="host",
        )
        self.assertTrue(apply_condition(cond, ctx))

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

        cond = Condition(field=make_field("field"), operator=Operator.EQ, filters=[], filter="value")
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
        node = WhereCondition(connector=FilterConnector.AND, conditions=[])
        self.assertTrue(evaluate(node, {}))

    def test_single_leaf_condition(self):
        """单个叶子条件"""
        cond = Condition(field=make_field("status"), operator=Operator.EQ, filter="active")
        node = WhereCondition(condition=cond)
        ctx = {"status": "active"}
        self.assertTrue(evaluate(node, ctx))
        ctx2 = {"status": "inactive"}
        self.assertFalse(evaluate(node, ctx2))

    def test_and_connector(self):
        """AND 连接器：所有子节点都为真"""
        cond1 = Condition(field=make_field("status"), operator=Operator.EQ, filter="active")
        cond2 = Condition(field=make_field("level"), operator=Operator.EQ, filter="HIGH")
        node = WhereCondition(
            connector=FilterConnector.AND,
            conditions=[
                WhereCondition(condition=cond1),
                WhereCondition(condition=cond2),
            ],
        )
        self.assertTrue(evaluate(node, {"status": "active", "level": "HIGH"}))
        self.assertFalse(evaluate(node, {"status": "active", "level": "LOW"}))
        self.assertFalse(evaluate(node, {"status": "inactive", "level": "HIGH"}))

    def test_or_connector(self):
        """OR 连接器：任一子节点为真"""
        cond1 = Condition(field=make_field("status"), operator=Operator.EQ, filter="active")
        cond2 = Condition(field=make_field("level"), operator=Operator.EQ, filter="HIGH")
        node = WhereCondition(
            connector=FilterConnector.OR,
            conditions=[
                WhereCondition(condition=cond1),
                WhereCondition(condition=cond2),
            ],
        )
        self.assertTrue(evaluate(node, {"status": "active", "level": "LOW"}))
        self.assertTrue(evaluate(node, {"status": "inactive", "level": "HIGH"}))
        self.assertFalse(evaluate(node, {"status": "inactive", "level": "LOW"}))

    def test_nested_conditions(self):
        """嵌套条件树：(status=active AND level=HIGH) OR operator=admin"""
        cond_status = Condition(field=make_field("status"), operator=Operator.EQ, filter="active")
        cond_level = Condition(field=make_field("level"), operator=Operator.EQ, filter="HIGH")
        cond_operator = Condition(field=make_field("operator"), operator=Operator.EQ, filter="admin")
        node = WhereCondition(
            connector=FilterConnector.OR,
            conditions=[
                WhereCondition(
                    connector=FilterConnector.AND,
                    conditions=[
                        WhereCondition(condition=cond_status),
                        WhereCondition(condition=cond_level),
                    ],
                ),
                WhereCondition(condition=cond_operator),
            ],
        )
        # 满足 status=active AND level=HIGH
        self.assertTrue(evaluate(node, {"status": "active", "level": "HIGH", "operator": "user"}))
        # 满足 operator=admin
        self.assertTrue(evaluate(node, {"status": "inactive", "level": "LOW", "operator": "admin"}))
        # 都不满足
        self.assertFalse(evaluate(node, {"status": "inactive", "level": "LOW", "operator": "user"}))


@pytest.mark.django_db
class TestFrontendFieldStructure(TestCase):
    """前端真实字段对象结构求值测试（携带 isEdit/selectedValue/children 等扩展属性）"""

    FRONTEND_SELECT_FIELD = {
        "keys": [],
        "table": "47_bklog_bkaudit_plugin_20250926_2ac1656e73",
        "isEdit": False,
        "remark": "",
        "children": [],
        "property": {},
        "raw_name": "action_id",
        "aggregate": None,
        "field_type": "string",
        "display_name": "操作ID(action_id)",
        "selectedValue": "操作ID(action_id)",
        "spec_field_type": "string",
    }

    FRONTEND_RISK_FIELD = {
        "keys": [],
        "table": "risk",
        "isEdit": False,
        "remark": "",
        "children": [],
        "property": {},
        "raw_name": "risk_level",
        "aggregate": None,
        "field_type": "string",
        "display_name": "风险等级",
        "selectedValue": "风险等级",
        "spec_field_type": "string",
    }

    def test_select_field_condition_with_extras(self):
        """select 字段（含扩展属性）：按 display_name 从 event_data 取值"""
        conditions = {
            "connector": "and",
            "conditions": [
                {"condition": {"field": self.FRONTEND_SELECT_FIELD, "operator": "eq", "filter": "list_risk_v2"}}
            ],
        }
        tree = to_condition_tree(conditions)
        leaf = tree.conditions[0].condition
        self.assertEqual(leaf.field.raw_name, "action_id")
        self.assertEqual(leaf.field.display_name, "操作ID(action_id)")
        # 事件输出以 display_name 作为 select 输出列名
        ctx = {"event_data": {"操作ID(action_id)": "list_risk_v2"}}
        self.assertTrue(evaluate(tree, ctx))
        ctx_miss = {"event_data": {"操作ID(action_id)": "create_strategy"}}
        self.assertFalse(evaluate(tree, ctx_miss))

    def test_passthrough_field_condition_with_extras(self):
        """直连字段（含扩展属性）：按 raw_name 从分派上下文取值"""
        conditions = {
            "connector": "and",
            "conditions": [{"condition": {"field": self.FRONTEND_RISK_FIELD, "operator": "eq", "filter": "HIGH"}}],
        }
        tree = to_condition_tree(conditions)
        self.assertTrue(evaluate(tree, {"risk_level": "HIGH"}))
        self.assertFalse(evaluate(tree, {"risk_level": "LOW"}))

    def test_mixed_fields_match_dispatch_rule(self):
        """混合词表（select 字段 + 直连字段）首匹配"""
        from types import SimpleNamespace

        from services.web.strategy_v2.constants import DispatchMode

        rule = SimpleNamespace(
            rule_id=1,
            conditions={
                "connector": "and",
                "conditions": [
                    {"condition": {"field": self.FRONTEND_SELECT_FIELD, "operator": "eq", "filter": "list_risk_v2"}},
                    {
                        "connector": "or",
                        "conditions": [
                            {"condition": {"field": self.FRONTEND_RISK_FIELD, "operator": "eq", "filters": ["HIGH"]}},
                            {"condition": {"field": self.FRONTEND_RISK_FIELD, "operator": "eq", "filters": ["MIDDLE"]}},
                        ],
                    },
                ],
            },
            is_default=False,
            target_scene_id=1,
            dispatch_mode=DispatchMode.DIRECT,
            processor=[1001],
            follower=[1002],
            confirmer=[1003],
        )
        rule_default = SimpleNamespace(
            rule_id=2,
            conditions={},
            is_default=True,
            target_scene_id=1,
            dispatch_mode=DispatchMode.DIRECT,
            processor=[1001],
            follower=[1002],
            confirmer=[1003],
        )
        # 命中规则1：action=list_risk_v2 且 risk_level=HIGH
        result = match_dispatch_rule(
            ctx={"event_data": {"操作ID(action_id)": "list_risk_v2"}, "risk_level": "HIGH"},
            rules=[rule, rule_default],
            rule_order=[1, 2],
        )
        self.assertTrue(result.matched)
        self.assertEqual(result.rule.rule_id, 1)
        # action 不匹配 -> 兜底
        result = match_dispatch_rule(
            ctx={"event_data": {"操作ID(action_id)": "create_strategy"}, "risk_level": "HIGH"},
            rules=[rule, rule_default],
            rule_order=[1, 2],
        )
        self.assertTrue(result.matched)
        self.assertEqual(result.rule.rule_id, 2)


@pytest.mark.django_db
class TestToConditionTree(TestCase):
    """to_condition_tree: 条件树转换测试"""

    def test_convert_simple_dict(self):
        """简单 dict 转换为 WhereCondition"""
        cond_dict = {
            "condition": make_condition_dict("status", filters=["active"]),
        }
        node = to_condition_tree(cond_dict)
        self.assertIsNotNone(node.condition)
        self.assertEqual(node.condition.field.raw_name, "status")
        self.assertEqual(node.condition.operator, Operator.EQ)

    def test_convert_nested_dict(self):
        """嵌套 dict 转换"""
        cond_dict = {
            "connector": "and",
            "conditions": [
                {"condition": make_condition_dict("status", filters=["active"])},
                {"condition": make_condition_dict("level", filters=["HIGH"])},
            ],
        }
        node = to_condition_tree(cond_dict)
        self.assertIsNone(node.condition)
        self.assertEqual(len(node.conditions), 2)
        self.assertEqual(node.connector, FilterConnector.AND)

    def test_convert_empty_dict(self):
        """空 dict 转换为空条件树"""
        node = to_condition_tree({})
        self.assertIsNone(node.condition)
        self.assertEqual(node.conditions, [])

    def test_convert_none(self):
        """None 转换为空条件树"""
        node = to_condition_tree(None)
        self.assertIsNone(node.condition)
        self.assertEqual(node.conditions, [])

    def test_convert_already_node(self):
        """已经是 WhereCondition 时直接返回"""
        cond = Condition(field=make_field("status"), operator=Operator.EQ, filter="active")
        node = WhereCondition(condition=cond)
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
        cond = make_condition_dict("status", filters=["active"])
        self.assertFalse(evaluate_is_empty({"condition": cond}))

    def test_dict_with_nested_empty_conditions_is_empty(self):
        self.assertTrue(evaluate_is_empty({"conditions": [{"conditions": []}]}))

    def test_node_with_condition_is_not_empty(self):
        cond = Condition(field=make_field("status"), operator=Operator.EQ, filter="active")
        node = WhereCondition(condition=cond)
        self.assertFalse(evaluate_is_empty(node))

    def test_node_with_empty_conditions_is_empty(self):
        node = WhereCondition(conditions=[])
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
        rule1 = self._make_rule(1, conditions={"condition": make_condition_dict("level", filters=["HIGH"])})
        rule2 = self._make_rule(2, conditions={"condition": make_condition_dict("level", filters=["LOW"])})
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
        rule1 = self._make_rule(1, conditions={"condition": make_condition_dict("level", filters=["HIGH"])})
        rule2 = self._make_rule(2, conditions={"condition": make_condition_dict("level", filters=["HIGH"])})
        result = match_dispatch_rule(
            ctx={"level": "HIGH"},
            rules=[rule1, rule2],
            rule_order=[1, 2],
        )
        self.assertTrue(result.matched)
        self.assertEqual(result.rule.rule_id, 1)

    def test_non_default_rule_miss_falls_to_default(self):
        """非默认规则未命中时降级到默认规则"""
        rule_cond = self._make_rule(1, conditions={"condition": make_condition_dict("level", filters=["HIGH"])})
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
        """复杂条件匹配：select 字段 + 直连字段 + AND/OR"""
        rule = self._make_rule(
            1,
            conditions={
                "connector": "and",
                "conditions": [
                    # select 字段：display_name 命中 event_data 键
                    {"condition": make_condition_dict("resource_type", filters=["host"], display_name="资源类型")},
                    {
                        "connector": "or",
                        "conditions": [
                            {"condition": make_condition_dict("risk_level", filters=["HIGH"])},
                            {"condition": make_condition_dict("risk_level", filters=["MEDIUM"])},
                        ],
                    },
                ],
            },
        )
        rule_default = self._make_rule(2, is_default=True)
        # 匹配：资源类型=host 且 risk_level=HIGH
        result = match_dispatch_rule(
            ctx={"event_data": {"资源类型": "host"}, "risk_level": "HIGH"},
            rules=[rule, rule_default],
            rule_order=[1, 2],
        )
        self.assertTrue(result.matched)
        self.assertEqual(result.rule.rule_id, 1)

        # 不匹配：资源类型=vm（第一个条件不满足）
        result = match_dispatch_rule(
            ctx={"event_data": {"资源类型": "vm"}, "risk_level": "HIGH"},
            rules=[rule, rule_default],
            rule_order=[1, 2],
        )
        self.assertTrue(result.matched)
        self.assertEqual(result.rule.rule_id, 2)  # 降级到默认规则

    def test_rule_order_not_in_list(self):
        """rule_id 不在 rule_order 中时排到最后"""
        rule1 = self._make_rule(1, is_default=True)
        rule2 = self._make_rule(2, conditions={"condition": make_condition_dict("level", filters=["HIGH"])})
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
