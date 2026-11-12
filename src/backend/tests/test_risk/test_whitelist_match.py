# -*- coding: utf-8 -*-
from django.test import SimpleTestCase

from services.web.risk.whitelist.constants import WhitelistType
from services.web.risk.whitelist.match import (
    append_risk_match_fields,
    match_scope,
    validate_match_scope,
)


def _field(name):
    return {"table": "event", "raw_name": name, "display_name": name, "field_type": "string"}


def _leaf(name, value, operator="eq"):
    return {"condition": {"field": _field(name), "operator": operator, "filter": value}}


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
        scope = _scope(_leaf("strategy_id", "1"), _leaf("count", "5", operator="gt"))
        self.assertEqual(validate_match_scope(scope, WhitelistType.RISK_ACCEPTANCE), "")
        self.assertTrue(match_scope(scope, {"strategy_id": "1", "count": 8}))
        self.assertFalse(match_scope(scope, {"strategy_id": "1", "count": 3}))

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

    def test_blank_event_id_is_not_appended(self):
        scope = append_risk_match_fields({}, strategy_id=9, raw_event_id="")
        self.assertNotIn("raw_event_id", _operators(scope))


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
