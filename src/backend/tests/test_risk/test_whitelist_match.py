# -*- coding: utf-8 -*-
from django.test import SimpleTestCase

from services.web.risk.whitelist.constants import WhitelistType
from services.web.risk.whitelist.match import (
    append_risk_match_fields,
    as_where_scope,
    match_scope,
    scope_field_names,
    validate_match_scope,
)


def _field(name, field_type="string"):
    return {"table": "event", "raw_name": name, "display_name": name, "field_type": field_type}


def _leaf(name, value, operator="eq", field_type="string"):
    return {"condition": {"field": _field(name, field_type), "operator": operator, "filter": value}}


def _scope(*nodes, connector="and"):
    return {"connector": connector, "conditions": list(nodes)}


class WhitelistMatchTests(SimpleTestCase):
    def test_and_group_requires_every_condition(self):
        scope = _scope(_leaf("strategy_id", "9"), _leaf("operator", "alice"))
        event = {"strategy_id": 9, "operator": "alice"}
        self.assertTrue(match_scope(scope, event))
        event["operator"] = "bob"
        self.assertFalse(match_scope(scope, event))

    def test_neq_and_or_across_groups(self):
        scope = _scope(
            _scope(_leaf("strategy_id", "1")),
            _scope(_leaf("raw_event_id", "keep", operator="neq")),
            connector="or",
        )
        self.assertTrue(match_scope(scope, {"strategy_id": "2", "raw_event_id": "other"}))
        self.assertFalse(match_scope(scope, {"strategy_id": "2", "raw_event_id": "keep"}))

    def test_false_positive_rejects_strategy_only(self):
        scope = _scope(_leaf("strategy_id", "1"))
        self.assertEqual(
            validate_match_scope(scope, WhitelistType.FALSE_POSITIVE),
            "只有命中策略条件时不允许误报加白",
        )
        self.assertEqual(validate_match_scope(scope, WhitelistType.RISK_ACCEPTANCE), "")

    def test_compare_operator_is_not_limited_to_eq(self):
        # count 是数值字段，比较类运算符可用（口径同审计策略）
        scope = _scope(_leaf("strategy_id", "1"), _leaf("count", "5", operator="gt", field_type="long"))
        self.assertEqual(validate_match_scope(scope, WhitelistType.RISK_ACCEPTANCE), "")
        self.assertTrue(match_scope(scope, {"strategy_id": "1", "count": 8}))
        self.assertFalse(match_scope(scope, {"strategy_id": "1", "count": 3}))

    def test_validate_requires_strategy_eq_with_value(self):
        # 其它条件依赖命中策略取值：策略条件固定等于且不能为空
        neq = _scope(_leaf("strategy_id", "1", operator="neq"), _leaf("operator", "alice"))
        self.assertEqual(validate_match_scope(neq, WhitelistType.RISK_ACCEPTANCE), "命中策略条件的操作符只能为等于")
        empty = _scope(_leaf("strategy_id", ""), _leaf("operator", "alice"))
        self.assertEqual(validate_match_scope(empty, WhitelistType.RISK_ACCEPTANCE), "命中策略条件不能为空")

    def test_validate_operator_matches_field_type(self):
        # 字符串字段不允许比较类运算符；数值字段不允许模糊匹配（与审计策略类型口径一致）
        gt_text = _scope(_leaf("strategy_id", "1"), _leaf("operator", "a", operator="gt"))
        self.assertEqual(validate_match_scope(gt_text, WhitelistType.RISK_ACCEPTANCE), "条件操作符不支持当前字段类型")
        like_number = _scope(
            _leaf("strategy_id", "1"),
            _leaf("count", "5", operator="like", field_type="long"),
        )
        self.assertEqual(validate_match_scope(like_number, WhitelistType.RISK_ACCEPTANCE), "条件操作符不支持当前字段类型")
        in_text = _scope(_leaf("strategy_id", "1"), _leaf("operator", "a", operator="include"))
        self.assertEqual(validate_match_scope(in_text, WhitelistType.RISK_ACCEPTANCE), "")

    def test_validate_operator_within_rule_audit_scope(self):
        # match_all 不在审计策略条件操作符（RuleAuditConditionOperator）范围内
        scope = _scope(_leaf("strategy_id", "1"), _leaf("operator", "a", operator="match_all"))
        self.assertEqual(validate_match_scope(scope, WhitelistType.RISK_ACCEPTANCE), "条件操作符不支持当前字段类型")

    def test_single_risk_appends_strategy_and_event(self):
        scope = append_risk_match_fields(_scope(_leaf("operator", "alice")), strategy_id=9, raw_event_id="evt-1")
        event = {"strategy_id": 9, "raw_event_id": "evt-1", "operator": "alice"}
        self.assertTrue(match_scope(scope, event))
        event["raw_event_id"] = "evt-2"
        self.assertFalse(match_scope(scope, event))
        self.assertNotIn("risk_id", _operators(scope))

    def test_appended_risk_fields_use_eq(self):
        scope = append_risk_match_fields({}, strategy_id=9, raw_event_id="evt-1")
        operators = _operators(scope)
        self.assertEqual(operators["strategy_id"], "eq")
        self.assertEqual(operators["raw_event_id"], "eq")
        self.assertNotIn("risk_id", operators)

    def test_existing_operator_is_kept(self):
        scope = append_risk_match_fields(
            _scope(_leaf("strategy_id", "9", operator="neq")),
            strategy_id=9,
            raw_event_id="evt-1",
        )
        operators = _operators(scope)
        self.assertEqual(operators["strategy_id"], "neq")
        self.assertEqual(operators["raw_event_id"], "eq")
        self.assertEqual(_field_count(scope, "strategy_id"), 1)

    def test_frontend_groups_are_a_complete_scope(self):
        scope = {
            "groups": [
                {
                    "connector": "and",
                    "conditions": [
                        {"field": "strategy_id", "operator": "eq", "value": "312"},
                        {"field": "event_id", "operator": "eq", "value": "11"},
                    ],
                }
            ]
        }
        self.assertEqual(validate_match_scope(scope, WhitelistType.FALSE_POSITIVE), "")
        self.assertTrue(match_scope(scope, {"strategy_id": "312", "event_id": "11"}))
        self.assertFalse(match_scope(scope, {"strategy_id": "312", "event_id": "12"}))

    def test_field_label_still_matches_raw_name(self):
        scope = {
            "connector": "and",
            "groups": [
                {
                    "connector": "and",
                    "conditions": [
                        {
                            "field": "strategy_id",
                            "field_name": "命中策略(ID)",
                            "operator": "eq",
                            "value": "359",
                        }
                    ],
                }
            ],
        }
        event = {"strategy_id": 359, "raw_event_id": "abc", "event_data": {"事件ID": "x"}}
        self.assertTrue(match_scope(scope, event))
        self.assertFalse(match_scope(scope, {**event, "strategy_id": 1}))

    def test_event_data_display_name_matches(self):
        scope = {
            "connector": "and",
            "groups": [
                {
                    "connector": "and",
                    "conditions": [
                        {"field": "strategy_id", "field_name": "命中策略(ID)", "operator": "eq", "value": "359"},
                        {"field": "username", "field_name": "操作人用户名", "operator": "eq", "value": "alice"},
                    ],
                }
            ],
        }
        event = {"strategy_id": 359, "event_data": {"操作人用户名": "alice", "事件ID": "e-1"}}
        self.assertTrue(match_scope(scope, event))
        self.assertFalse(match_scope(scope, {**event, "event_data": {"操作人用户名": "bob"}}))

    def test_blank_event_id_is_not_appended(self):
        scope = append_risk_match_fields({}, strategy_id=9, raw_event_id="")
        self.assertNotIn("raw_event_id", _operators(scope))

    def test_mixed_connector_within_group(self):
        # 组 connector=or 聚合各段，叶子 connector 表达组内线性连接：
        # a(strategy=9) or b(operator=alice) and c(operator=bob)
        # 切段为 [a](or)、[b and c](and) -> a or (b and c)。
        # 旧实现统一按组 connector(or) 求值，会把 b and c 错当成 b or c。
        scope = {
            "connector": "and",
            "groups": [
                {
                    "connector": "or",
                    "conditions": [
                        {"field": "strategy_id", "operator": "eq", "value": "9", "connector": "or"},
                        {"field": "operator", "operator": "eq", "value": "alice", "connector": "and"},
                        {"field": "operator", "operator": "eq", "value": "bob", "connector": "and"},
                    ],
                }
            ],
        }
        # a 命中 -> 整组命中
        self.assertTrue(match_scope(scope, {"strategy_id": "9", "operator": "carol"}))
        # b 单独不成立（and 段需 b、c 同时满足，c 不同字段无法同时满足）
        self.assertFalse(match_scope(scope, {"strategy_id": "1", "operator": "alice"}))
        # 既不满足 a，也不满足 (b and c)
        self.assertFalse(match_scope(scope, {"strategy_id": "1", "operator": "carol"}))

    def test_append_risk_fields_into_every_or_group(self):
        # 组间 OR：strategy_id 必须注入每个可命中分支，否则未注入分支脱离策略约束
        scope = {
            "connector": "or",
            "groups": [
                {"connector": "and", "conditions": [{"field": "operator", "operator": "eq", "value": "alice"}]},
                {"connector": "and", "conditions": [{"field": "operator", "operator": "eq", "value": "bob"}]},
            ],
        }
        scope = append_risk_match_fields(scope, strategy_id=9)
        # 注入后每个分支带 strategy_id，转成条件树后各分支都必须含策略约束
        tree_scope = as_where_scope(scope)
        self.assertGreaterEqual(_field_count(tree_scope, "strategy_id"), 2)
        self.assertIn("strategy_id", scope_field_names(scope))
        # 正确策略下两个分支都可命中
        self.assertTrue(match_scope(scope, {"strategy_id": "9", "operator": "bob"}))
        # 策略不匹配时，未注入的 OR 分支不得单独命中
        self.assertFalse(match_scope(scope, {"strategy_id": "1", "operator": "bob"}))


def _operators(scope):
    found = {}

    def walk(node):
        condition = node.get("condition")
        if condition:
            found[condition["field"]["raw_name"]] = condition["operator"]
        for child in node.get("conditions") or []:
            walk(child)

    walk(scope)
    return found


def _field_count(scope, raw_name):
    count = 0

    def walk(node):
        nonlocal count
        condition = node.get("condition")
        if condition and condition["field"]["raw_name"] == raw_name:
            count += 1
        for child in node.get("conditions") or []:
            walk(child)

    walk(scope)
    return count
