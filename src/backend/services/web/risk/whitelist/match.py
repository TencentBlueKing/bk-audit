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


def _is_group_scope(scope) -> bool:
    return isinstance(scope, dict) and isinstance(scope.get("groups"), list)


def _frontend_leaf(item: dict) -> dict | None:
    field = item.get("field")
    operator = item.get("operator")
    if not field or not operator:
        return None
    condition = {
        "field": {
            "table": "event",
            "raw_name": str(field),
            "display_name": item.get("field_name") or str(field),
            "field_type": "string",
        },
        "operator": operator,
    }
    value = item.get("value")
    if isinstance(value, list):
        condition["filters"] = value
    elif value not in (None, ""):
        condition["filter"] = value
    return {"condition": condition}


def as_where_scope(scope: dict) -> dict:
    """groups 转成求值用的条件树。已经是条件树的原样返回。"""

    if not _is_group_scope(scope):
        return scope or {}
    groups = []
    for group in scope.get("groups") or []:
        leaves = [leaf for item in group.get("conditions") or [] if (leaf := _frontend_leaf(item))]
        if leaves:
            groups.append({"connector": group.get("connector") or "and", "conditions": leaves})
    return {"connector": scope.get("connector") or "and", "conditions": groups}


def _field_names(scope: dict) -> set:
    if _is_group_scope(scope):
        return {
            item.get("field")
            for group in scope.get("groups") or []
            for item in group.get("conditions") or []
            if item.get("field")
        }
    try:
        return {
            condition.field.raw_name
            for condition in _leaves(to_condition_tree(scope))
            if condition.field and condition.field.raw_name
        }
    except Exception:
        return set()


def _frontend_condition(raw_name: str, value) -> dict:
    return {
        "field": raw_name,
        "field_name": raw_name,
        "operator": "eq",
        "value": str(value),
        "connector": "and",
    }


def append_risk_match_fields(scope: dict, *, strategy_id, raw_event_id=None) -> dict:
    """补上策略。单条再补原始事件。空值不写入。"""

    scope = dict(scope or {})
    existing = _field_names(scope)
    additions = []
    for raw_name, value in (
        ("strategy_id", strategy_id),
        ("raw_event_id", raw_event_id),
    ):
        if value in (None, "") or raw_name in existing:
            continue
        additions.append((raw_name, value))
    if not additions:
        return scope
    if _is_group_scope(scope):
        groups = [dict(group) for group in scope.get("groups") or []]
        if not groups:
            groups = [{"connector": "and", "conditions": []}]
        conditions = list(groups[0].get("conditions") or [])
        conditions.extend(_frontend_condition(raw_name, value) for raw_name, value in additions)
        groups[0]["conditions"] = conditions
        groups[0]["connector"] = groups[0].get("connector") or "and"
        scope["groups"] = groups
        return scope
    where_additions = [_condition(raw_name, value) for raw_name, value in additions]
    if scope.get("condition") and not scope.get("conditions"):
        conditions = [{"condition": scope["condition"]}]
        scope = {"connector": scope.get("connector") or "and"}
    else:
        conditions = list(scope.get("conditions") or [])
    conditions.extend(where_additions)
    scope["conditions"] = conditions
    scope["connector"] = scope.get("connector") or "and"
    scope.pop("condition", None)
    return scope


def match_scope(scope: dict, event: dict) -> bool:
    try:
        node = to_condition_tree(as_where_scope(scope))
    except Exception:
        return False
    if evaluate_is_empty(node):
        return False
    return evaluate(node, {"event_data": event or {}})


def validate_match_scope(scope: dict, whitelist_type: str) -> str:
    """返回错误文案。通过时返回空字符串。"""

    from services.web.risk.whitelist.constants import WhitelistType

    try:
        node = to_condition_tree(as_where_scope(scope))
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
