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


def _condition(raw_name: str, value, display_name: "str | None" = None) -> dict:
    return {
        "condition": {
            "field": {
                "table": "event",
                "raw_name": raw_name,
                "display_name": display_name or raw_name,
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
    leaf = {"condition": condition}
    # 保留前端叶子 connector（与下一叶子的连接符），供 _group_subtrees 切段；
    # connector 一致的段折叠后叶子不再携带 connector，避免冗余。
    if item.get("connector"):
        leaf["connector"] = item["connector"]
    return leaf


def _group_subtrees(leaves: list, group_connector: str) -> list:
    """组内叶子按 connector 切段：连续相同 connector 的叶子合并为一个段（子树），
    段 connector 取叶子真实连接符；全段 connector 与组一致时折叠回扁平结构。

    求值（dispatch.evaluate）只读取父节点 connector 作为其子节点间连接符，叶子自身 connector 不参与求值。
    旧实现把组内所有叶子统一按组 connector 连接，导致叶子 connector 与组不一致时语义错误：
    组 connector=and、叶子写 `a or b` 时，旧实现按 `a and b` 求值，把 or 错当成 and。
    这里以段为最小求值单元：段节点带真实 connector 挂到组下，由组 connector 聚合各段。
    单段折叠为“组直挂叶子”且 connector 不变（与旧结构一致，避免改变既有同 connector 语义）。
    """

    segments: list = []
    for leaf in leaves:
        connector = leaf.get("connector") or group_connector
        if segments and segments[-1][0] == connector:
            segments[-1][1].append(leaf)
        else:
            segments.append((connector, [leaf]))
    if len(segments) == 1:
        connector, seg_leaves = segments[0]
        for leaf in seg_leaves:
            leaf.pop("connector", None)
        return [{"connector": connector, "conditions": seg_leaves}]
    subtrees = []
    for connector, seg_leaves in segments:
        if len(seg_leaves) == 1:
            subtrees.append(seg_leaves[0])
        else:
            subtrees.append({"connector": connector, "conditions": seg_leaves})
    return subtrees


def _group_leaves(group: dict) -> list:
    """把前端组内条件转成叶子节点列表（保留各叶子的 connector，供切段使用）。"""

    return [leaf for item in group.get("conditions") or [] if (leaf := _frontend_leaf(item))]


def _group_subtree(group: dict) -> dict:
    """组转成条件树子树：组 connector 聚合各段，段 connector 表达组内线性连接符。"""

    group_connector = group.get("connector") or "and"
    subtrees = _group_subtrees(_group_leaves(group), group_connector)
    return {"connector": group_connector, "conditions": subtrees}


def as_where_scope(scope: dict) -> dict:
    """groups 转成求值用的条件树。已经是条件树的原样返回。"""

    if not _is_group_scope(scope):
        return scope or {}
    groups = [_group_subtree(group) for group in scope.get("groups") or [] if _group_leaves(group)]
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


def scope_field_options(scope: dict) -> "list[tuple[str, str]]":
    """列出实际带值的条件字段的 (field, field_name) 配对，供“包含条件”下拉枚举。

    与 scope_field_names 的带值判定一致（值非空才算），兼容 groups 和条件树两种结构。
    单份 scope 内按 field 去重，field_name 取首次出现的非空展示名，
    展示名缺失时按标准字段中文名兜底，兜底不到回退 field。
    """

    pairs: "list[tuple[str, str]]" = []
    if _is_group_scope(scope):
        fallbacks = _fallback_field_names()
        for group in scope.get("groups") or []:
            for item in group.get("conditions") or []:
                if item.get("field") and item.get("value") not in (None, "", []):
                    field = str(item.get("field"))
                    display = str(item.get("field_name") or "")
                    field_name = display if display and display != field else (fallbacks.get(field) or field)
                    pairs.append((field, field_name))
        return _dedupe_field_options(pairs)
    fallbacks = _fallback_field_names()
    try:
        for condition in _leaves(to_condition_tree(scope)):
            field = condition.field
            if not (field and field.raw_name):
                continue
            if not (getattr(condition, "filter", None) not in (None, "", []) or getattr(condition, "filters", None)):
                continue
            raw_name = field.raw_name
            display = getattr(field, "display_name", "") or ""
            field_name = display if display and display != raw_name else (fallbacks.get(raw_name) or raw_name)
            pairs.append((raw_name, field_name))
    except Exception:
        return []
    return _dedupe_field_options(pairs)


def _dedupe_field_options(pairs: "list[tuple[str, str]]") -> "list[tuple[str, str]]":
    """按 field 去重，保留首次出现的非空 field_name，全空则回退 field。"""

    picked: "dict[str, str]" = {}
    for field, field_name in pairs:
        if field not in picked:
            picked[field] = field_name or field
        elif not picked[field] and field_name:
            picked[field] = field_name
    return list(picked.items())


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
    """匹配范围回显：直接用建单时存进快照的字段中文名（与风险筛选选择器口径一致），缺失回退 raw_name。"""

    raw_name = getattr(field, "raw_name", "") or ""
    display_name = getattr(field, "display_name", "") or ""
    return display_name or raw_name or "未知字段"


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
    joiner = str(getattr(node.connector, "value", None) or node.connector or "and").upper()
    parts = [part for part in (_describe_tree(child, joiner) for child in node.conditions or []) if part]
    if not parts:
        return ""
    text = f" {joiner} ".join(parts)
    return f"({text})" if connector and connector != joiner else text


def _group_leaf_text(item: dict) -> str:
    """groups 条件转 "中文名 = 值"；直接用建单存进快照的 field_name（与风险筛选口径一致），缺失回退 field。"""

    raw_name = str(item.get("field") or "")
    display_name = str(item.get("field_name") or "")
    field = display_name or raw_name
    value = item.get("value")
    if not isinstance(value, list):
        value = [value]
    shown = "、".join(str(v) for v in value if v not in (None, ""))
    return f"{field} {_display_operator(item.get('operator'))} {shown}".strip()


def _describe_group_scope(scope: dict) -> str:
    """groups 结构按原始结构拼接，保留前端的条件中文名。"""

    connector = str(scope.get("connector") or "and").upper()
    parts = []
    for group in scope.get("groups") or []:
        joiner = str(group.get("connector") or "and").upper()
        texts = [_group_leaf_text(item) for item in group.get("conditions") or [] if item.get("field")]
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


def _frontend_condition(raw_name: str, value, display_name: "str | None" = None) -> dict:
    return {
        "field": raw_name,
        "field_name": display_name or raw_name,
        "operator": "eq",
        "value": str(value),
        "connector": "and",
    }


def append_risk_match_fields(scope: dict, *, strategy_id, raw_event_id=None) -> dict:
    """补上策略。单条再补原始事件。空值不写入。"""

    scope = dict(scope or {})
    existing = _field_names(scope)
    # 注入字段（策略 / 原始事件）由后端补充，前端未带中文名；写标准中文名进快照，
    # 否则纯回显快照 field_name 时这些字段会退回英文 raw_name（前端自带字段才直接回显）。
    fallbacks = _fallback_field_names()
    additions = []
    for raw_name, value in (
        ("strategy_id", strategy_id),
        ("raw_event_id", raw_event_id),
    ):
        if value in (None, "") or raw_name in existing:
            continue
        additions.append((raw_name, value, fallbacks.get(raw_name) or raw_name))
    if not additions:
        return scope
    if _is_group_scope(scope):
        groups = [dict(group) for group in scope.get("groups") or []]
        if not groups:
            groups = [{"connector": "and", "conditions": []}]
        # 策略 / 原始事件必须出现在每个可命中子树：组间 connector 可能为 OR，
        # 仅注入 groups[0] 会让其余 OR 分支脱离策略约束，扩大加白命中范围。
        # 仅对叶子条件做去重，子树内缺少 strategy_id / raw_event_id 时补上。
        for group in groups:
            conditions = list(group.get("conditions") or [])
            field_names = {item.get("field") for item in conditions if isinstance(item, dict) and item.get("field")}
            for raw_name, value, display_name in additions:
                if raw_name not in field_names:
                    conditions.append(_frontend_condition(raw_name, value, display_name))
            group["conditions"] = conditions
            group["connector"] = group.get("connector") or "and"
        scope["groups"] = groups
        return scope
    where_additions = [_condition(raw_name, value, display_name) for raw_name, value, display_name in additions]
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
