# -*- coding: utf-8 -*-
"""白名单匹配。条件树和运算符复用分派规则的内存求值。"""

import json

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


def scope_field_names(scope: dict) -> set:
    """列出实际带值的条件字段名，供列表“包含条件”筛选和展示。

    与 _field_names 的区别：这里要求条件值非空，只登记字段名不算。
    兼容 groups 和条件树两种结构，operator 不参与判定（neq/in 同样算包含）。
    """

    if _is_group_scope(scope):
        return {
            str(item.get("field"))
            for group in scope.get("groups") or []
            for item in group.get("conditions") or []
            if item.get("field") and item.get("value") not in (None, "", [])
        }
    try:
        return {
            condition.field.raw_name
            for condition in _leaves(to_condition_tree(scope))
            if condition.field
            and condition.field.raw_name
            and (getattr(condition, "filter", None) not in (None, "", []) or getattr(condition, "filters", None))
        }
    except Exception:
        return set()


# 工单展示用：core Operator 的 choices 是 SQL 口径（eq 的 label 是 "等于 ="），这里取纯符号
OPERATOR_DISPLAY = {
    "eq": "=",
    "neq": "!=",
    "gt": ">",
    "lt": "<",
    "gte": ">=",
    "lte": "<=",
    "include": "in",
    "exclude": "not in",
    "like": "like",
    "not_like": "not like",
    "isnull": "is null",
    "notnull": "is not null",
    "match_all": "match all",
    "match_any": "match any",
    "json_contains": "json contains",
    "between": "between",
}


def _operator_key(operator) -> str:
    key = getattr(operator, "value", None) or str(operator or "")
    return key


def _display_operator(operator) -> str:
    """运算符转展示符号，未知运算符保留原值便于排查。"""

    return OPERATOR_DISPLAY.get(_operator_key(operator), _operator_key(operator))


def _display_value(condition) -> str:
    if condition.filters:
        return "、".join(str(value) for value in condition.filters)
    return str(condition.filter or "")


def _fallback_field_names() -> dict:
    """事件标准字段的中文名兜底，和前端条件选择器的口径同源。

    EventMappingFields 导入链较重，首次格式化时再取。
    """

    from services.web.risk.constants import EventMappingFields

    return {f.field_name: str(f.description) for f in EventMappingFields().fields}


def _display_field(field) -> str:
    """字段展示名：优先条件自带中文名（append 补的是 raw，会落空），再兜底标准字段。"""

    raw_name = getattr(field, "raw_name", "") or ""
    display_name = getattr(field, "display_name", "") or ""
    if display_name and display_name != raw_name:
        return display_name
    return _fallback_field_names().get(raw_name) or raw_name or "未知字段"


def _describe_tree(node, connector: str = "") -> str:
    """条件树转一行可读文案：字段 运算符 值，组间按连接符拼接。"""

    if node is None:
        return ""
    if node.condition is not None:
        condition = node.condition
        field = _display_field(condition.field)
        value = _display_value(condition)
        operator = _display_operator(condition.operator)
        return f"{field} {operator} {value}".strip()
    joiner = str(getattr(node.connector, "value", None) or node.connector or "and")
    parts = [part for part in (_describe_tree(child, joiner) for child in node.conditions or []) if part]
    if not parts:
        return ""
    text = f" {joiner} ".join(parts)
    return f"({text})" if connector and connector != joiner else text


def _group_leaf_text(item: dict, fallbacks: dict) -> str:
    """groups 条件转 "中文名 = 值"；前端 field_name 缺失或与字段名相同视为无效。"""

    raw_name = str(item.get("field") or "")
    display_name = str(item.get("field_name") or "")
    field = display_name if display_name and display_name != raw_name else (fallbacks.get(raw_name) or raw_name)
    value = item.get("value")
    if not isinstance(value, list):
        value = [value]
    shown = "、".join(str(v) for v in value if v not in (None, ""))
    return f"{field} {_display_operator(item.get('operator'))} {shown}".strip()


def _describe_group_scope(scope: dict) -> str:
    """groups 结构按原始结构拼接，保留前端的条件中文名。"""

    connector = str(scope.get("connector") or "and")
    fallbacks = _fallback_field_names()
    parts = []
    for group in scope.get("groups") or []:
        joiner = str(group.get("connector") or "and")
        texts = [_group_leaf_text(item, fallbacks) for item in group.get("conditions") or [] if item.get("field")]
        texts = [t for t in texts if t]
        if not texts:
            continue
        text = f" {joiner} ".join(texts)
        parts.append(f"({text})" if joiner != connector else text)
    return f" {connector} ".join(parts)


def format_scope_readable(scope: dict) -> str:
    """匹配范围转审批人可读的一行文本；解析失败降级为 JSON，审批信息不能缺失。"""

    try:
        if _is_group_scope(scope):
            text = _describe_group_scope(scope)
            if text:
                return text
        node = to_condition_tree(as_where_scope(scope))
        if not evaluate_is_empty(node):
            text = _describe_tree(node)
            if text:
                return text
    except Exception:
        pass
    return json.dumps(scope or {}, ensure_ascii=False)


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


def _event_data(event: dict) -> dict:
    nested = (event or {}).get("event_data")
    return dict(nested) if isinstance(nested, dict) else {}


def _alias_condition_keys(node, event: dict, data: dict) -> None:
    if node is None:
        return
    condition = getattr(node, "condition", None)
    field = getattr(condition, "field", None)
    if field is not None:
        raw_name = field.raw_name
        display_name = field.display_name
        if display_name and display_name not in data and raw_name and raw_name in event and raw_name != "event_data":
            data[display_name] = event[raw_name]
        if raw_name and raw_name not in data and raw_name in event and raw_name != "event_data":
            data[raw_name] = event[raw_name]
    for child in getattr(node, "conditions", None) or []:
        _alias_condition_keys(child, event, data)


def match_scope(scope: dict, event: dict) -> bool:
    try:
        node = to_condition_tree(as_where_scope(scope))
    except Exception:
        return False
    if evaluate_is_empty(node):
        return False
    event = event or {}
    data = _event_data(event)
    _alias_condition_keys(node, event, data)
    return evaluate(node, {"event_data": data})


# 数值型字段类型。口径对齐审计策略条件表达式：比较类运算符只对数值字段开放，
# 模糊匹配只对字符串类字段开放。EventMappingFields 里策略 ID 声明为 string。
NUMERIC_FIELD_TYPES = {"int", "long", "float", "double", "timestamp"}
STRING_LIKE_FIELD_TYPES = {"string", "text"}


def allowed_operators(field_type) -> set:
    """字段类型可用的运算符集合，与审计策略条件操作符同源（RuleAuditConditionOperator）。"""

    from core.sql.constants import Operator
    from services.web.strategy_v2.constants import RuleAuditConditionOperator

    allowed = set(RuleAuditConditionOperator.values)
    key = getattr(field_type, "value", None) or str(field_type or "")
    if key not in NUMERIC_FIELD_TYPES:
        allowed -= {Operator.GT.value, Operator.LT.value, Operator.GTE.value, Operator.LTE.value}
    if key not in STRING_LIKE_FIELD_TYPES:
        allowed -= {Operator.LIKE.value, Operator.NOT_LIKE.value}
    return allowed


def validate_match_scope(scope: dict, whitelist_type: str) -> str:
    """返回错误文案。通过时返回空字符串。"""

    from core.sql.constants import Operator
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
            # 其它条件依赖命中策略的取值，策略条件必须固定等于且有值
            if condition.operator != Operator.EQ:
                return "命中策略条件的操作符只能为等于"
            if (getattr(condition, "filter", None) in (None, "")) and not getattr(condition, "filters", None):
                return "命中策略条件不能为空"
        else:
            only_strategy = False
            field_type = getattr(condition.field, "field_type", None) if condition.field else None
            if _operator_key(condition.operator) not in allowed_operators(field_type):
                return "条件操作符不支持当前字段类型"
    if not has_strategy:
        return "匹配范围必须包含命中策略"
    if whitelist_type == WhitelistType.FALSE_POSITIVE and only_strategy:
        return "只有命中策略条件时不允许误报加白"
    return ""
