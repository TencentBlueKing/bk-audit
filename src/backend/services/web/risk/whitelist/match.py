# -*- coding: utf-8 -*-
"""白名单匹配。条件树和运算符复用分派规则的内存求值。"""

from services.web.risk.whitelist.constants import STRATEGY_FIELDS
from services.web.strategy_v2.handlers.dispatch import (
    evaluate,
    evaluate_is_empty,
    to_condition_tree,
)


def _leaves(node):
    if node is None:
        return
    if node.condition:
        yield node.condition
        return
    for child in node.conditions or []:
        yield from _leaves(child)


def _condition(raw_name: str, value) -> dict:
    return {
        "condition": {
            "field": {
                "table": "event",
                "raw_name": raw_name,
                "display_name": raw_name,
                "field_type": "string",
            },
            "operator": "eq",
            "filter": str(value),
        }
    }


def append_risk_match_fields(scope: dict, *, strategy_id, raw_event_id=None) -> dict:
    """补上策略。单条再补原始事件。空值不写入。"""

    scope = dict(scope or {})
    try:
        existing = {
            condition.field.raw_name
            for condition in _leaves(to_condition_tree(scope))
            if condition.field and condition.field.raw_name
        }
    except Exception:
        existing = set()
    additions = []
    for raw_name, value in (
        ("strategy_id", strategy_id),
        ("raw_event_id", raw_event_id),
    ):
        if value in (None, "") or raw_name in existing:
            continue
        additions.append(_condition(raw_name, value))
    if not additions:
        return scope
    if scope.get("condition") and not scope.get("conditions"):
        conditions = [{"condition": scope["condition"]}]
        scope = {"connector": scope.get("connector") or "and"}
    else:
        conditions = list(scope.get("conditions") or [])
    conditions.extend(additions)
    scope["conditions"] = conditions
    scope["connector"] = scope.get("connector") or "and"
    scope.pop("condition", None)
    return scope


def match_scope(scope: dict, event: dict) -> bool:
    try:
        node = to_condition_tree(scope)
    except Exception:
        return False
    if evaluate_is_empty(node):
        return False
    return evaluate(node, {"event_data": event or {}})


def validate_match_scope(scope: dict, whitelist_type: str) -> str:
    """返回错误文案。通过时返回空字符串。"""

    from services.web.risk.whitelist.constants import WhitelistType

    try:
        node = to_condition_tree(scope)
    except Exception:
        return "匹配范围未完善"
    if evaluate_is_empty(node):
        return "匹配范围未完善"
    conditions = list(_leaves(node))
    if not conditions:
        return "匹配范围未完善"
    has_strategy = False
    only_strategy = True
    for condition in conditions:
        field = condition.field.raw_name if condition.field else ""
        if field in STRATEGY_FIELDS:
            has_strategy = True
        else:
            only_strategy = False
    if not has_strategy:
        return "匹配范围必须包含命中策略"
    if whitelist_type == WhitelistType.FALSE_POSITIVE and only_strategy:
        return "只有命中策略条件时不允许误报加白"
    return ""
