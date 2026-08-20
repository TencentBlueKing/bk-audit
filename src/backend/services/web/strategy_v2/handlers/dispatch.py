# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
from dataclasses import dataclass, field
from typing import Any, List, Optional, Union

from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field as PydanticField

from core.sql.constants import FilterConnector, Operator
from services.web.strategy_v2.constants import DispatchMode
from services.web.strategy_v2.models import DispatchRule, Strategy

"""
分派规则匹配器: Python 内存求值

字段词表（可引用字段，"分派规则字段词表"契约的具体内容）：
- 事件输出字段：EventMappingFields 定义的全部字段（strategy_id/strategy_rule_id/event_data/event_type/event_time/event_source/operator/raw_event_id/event_content...）
- 规则实例化字段：risk_level、risk_hazard / risk_guidance 
- event_data.* JSON 路径：覆盖策略级 select 的维度/聚合字段（如 event_data.resource_type），resolve_field 按 '.' 分层下钻取值
- 排除流转态字段：status / current_operator / rule_id（处置规则）等——分派先于流转
"""


class DispatchCondition(PydanticBaseModel):
    """
    一条规则的一个条件：字段表达式 + 操作符 + 筛选值。
    """

    field: str = PydanticField(description="字段表达式：事件输出字段 / risk_level / event_data.xxx")
    operator: Operator
    filters: List[Union[str, int, float]] = PydanticField(default_factory=list) # 多值
    filter: Union[str, int, float] = PydanticField(default="")  # 单值


class DispatchConditionNode(PydanticBaseModel):
    """
    一个条件树，多个DispatchCondition和connector的组合
    """

    connector: FilterConnector = FilterConnector.AND
    condition: Optional[DispatchCondition] = None
    conditions: List["DispatchConditionNode"] = PydanticField(default_factory=list)


DispatchConditionNode.model_rebuild()


@dataclass
class DispatchResult:
    """
    分派结果，match=False 时其余字段无效
    """

    matched: bool = False
    rule: Optional[DispatchRule] = None
    # 以下字段为实例化快照（分派时一次性固化，后续规则编辑不影响已产生单据）
    dispatch_mode: str = DispatchMode.DIRECT
    target_scene_id: Optional[int] = None
    processor: List[int] = field(default_factory=list)  # 处理人通知组 ID 列表
    follower: List[int] = field(default_factory=list)  # 关注人通知组 ID 列表
    confirmer: List[str] = field(default_factory=list)  # 确认人用户名列表

    @classmethod
    def miss(cls) -> "DispatchResult":
        return cls(matched=False)

    @classmethod
    def hit(cls, rule: DispatchRule) -> "DispatchResult":
        return cls(
            matched=True,
            rule=rule,
            dispatch_mode=rule.dispatch_mode,
            target_scene_id=rule.target_scene_id,
            processor=list(rule.processor or []),
            follower=list(rule.follower or []),
            confirmer=list(rule.confirmer or []),
        )

# event_data 前缀：前缀命中后按 '.' 下钻
EVENT_DATA_PREFIX = "event_data."


def resolve_field(field_expr: str, ctx: dict) -> Any:
    """
    解析字段表达式的值。
    - event_data.xxx.yyy：从 ctx 的 event_data dict 逐层下钻（覆盖策略级 select 字段）
    - 其他：直接读取
    """
    if not field_expr:
        return None
    if field_expr.startswith(EVENT_DATA_PREFIX):
        node: Any = ctx.get("event_data")
        for key in field_expr[len(EVENT_DATA_PREFIX) :].split("."):
            if isinstance(node, dict):
                node = node.get(key)
            else:
                return None
        return node
    return ctx.get(field_expr)


def _stringify(value: Any) -> Optional[str]:
    """比较辅助：数值与字符串比较时统一转 str"""
    if value is None:
        return None
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, tuple)):
        return ",".join(str(v) for v in value)
    return str(value)


def _compare(actual: Any, expected: Any) -> bool:
    """宽松相等：先严格比较，类型不匹配时退化为字符串比较"""
    if actual == expected:
        return True
    a, e = _stringify(actual), _stringify(expected)
    return a is not None and e is not None and a == e


# 操作符实现函数

def _op_include(actual: Any, values: List[Any]) -> bool:
    return any(_compare(actual, v) for v in values)


def _op_like(actual: Any, pattern: Any) -> bool:
    a, p = _stringify(actual), _stringify(pattern)
    if a is None or p is None:
        return False
    # SQL LIKE 语义：% 任意串、_ 单字符；转 regex
    import re

    regex = "^" + "".join(".*" if ch == "%" else "." if ch == "_" else re.escape(ch) for ch in p) + "$"
    return re.match(regex, a, re.IGNORECASE) is not None


def _numeric_pair(a: Any, b: Any) -> Optional[tuple]:
    """数值比较辅助：可转数值则转，否则退化为字符串比较标记 None"""
    try:
        return float(a), float(b)
    except (TypeError, ValueError):
        return None


def _op_gt(a, b):
    pair = _numeric_pair(a, b)
    return pair is not None and pair[0] > pair[1]


def _op_gte(a, b):
    pair = _numeric_pair(a, b)
    return pair is not None and pair[0] >= pair[1]


def _op_lt(a, b):
    pair = _numeric_pair(a, b)
    return pair is not None and pair[0] < pair[1]


def _op_lte(a, b):
    pair = _numeric_pair(a, b)
    return pair is not None and pair[0] <= pair[1]


def _first_value(v: Any, vs: List[Any]) -> Any:
    """
    单值/多值取值： filter 有值优先，否则取 filters 第一个
    """
    if v is not None and v != "":
        return v
    if vs:
        return vs[0]
    return v  # None 或 ""（保持原值参与语义，如 isnull）

# sql操作符的python等价实现
PY_OPERATORS = {
    Operator.EQ: lambda a, v, vs: _compare(a, _first_value(v, vs)),
    Operator.NEQ: lambda a, v, vs: not _compare(a, _first_value(v, vs)),
    Operator.GT: lambda a, v, vs: _op_gt(a, _first_value(v, vs)),
    Operator.GTE: lambda a, v, vs: _op_gte(a, _first_value(v, vs)),
    Operator.LT: lambda a, v, vs: _op_lt(a, _first_value(v, vs)),
    Operator.LTE: lambda a, v, vs: _op_lte(a, _first_value(v, vs)),
    Operator.INCLUDE: lambda a, v, vs: _op_include(a, vs if vs else ([v] if v is not None and v != "" else [])),
    Operator.EXCLUDE: lambda a, v, vs: not _op_include(a, vs if vs else ([v] if v is not None and v != "" else [])),
    Operator.LIKE: lambda a, v, vs: _op_like(a, _first_value(v, vs)),
    Operator.NOT_LIKE: lambda a, v, vs: not _op_like(a, _first_value(v, vs)),
    Operator.ISNULL: lambda a, v, vs: a is None,
    Operator.NOTNULL: lambda a, v, vs: a is not None,
    Operator.BETWEEN: lambda a, v, vs: _op_gte(a, vs[0]) and _op_lte(a, vs[1]) if len(vs) == 2 else False,
    Operator.MATCH_ANY: lambda a, v, vs: _op_include(a, vs if vs else ([v] if v is not None and v != "" else [])),
    Operator.MATCH_ALL: lambda a, v, vs: all(
        _compare(a, x) for x in (vs if vs else ([v] if v is not None and v != "" else []))
    ),
    Operator.JSON_CONTAINS: lambda a, v, vs: _op_include(a, vs if vs else ([v] if v is not None and v != "" else [])),
}


def apply_condition(condition: DispatchCondition, ctx: dict) -> bool:
    """
    原子条件求值：字段解析 + 操作符比较。
    字段表达式直接取 condition.field（词表标准名或 event_data.xxx 路径）。
    """
    op_func = PY_OPERATORS.get(condition.operator)
    if op_func is None:
        # 未知操作符：视为不匹配
        return False
    actual = resolve_field(condition.field, ctx)
    return op_func(actual, condition.filter, condition.filters)


def evaluate(node: Optional[DispatchConditionNode], ctx: dict) -> bool:
    """
    条件树求值（递归），返回最终布尔结果：
    - None / 空树 -> True（无条件匹配）
    - 叶子 -> apply_condition
    - 分支 -> 子节点按 connector（and/or）聚合
    """
    if node is None:
        return True
    if node.condition:
        return apply_condition(node.condition, ctx)
    if node.conditions:
        results = [evaluate(sub, ctx) for sub in node.conditions]
        if not results:
            return True
        return all(results) if node.connector == FilterConnector.AND else any(results)
    return True


def match_dispatch_rule(
    ctx: dict,
    rules: Optional[List[DispatchRule]] = None,
    strategy: Optional[Strategy] = None,
    rule_order: Optional[List[int]] = None,
) -> DispatchResult:
    """
    按分派规则首匹配（dispatch_rule_order 顺序）。

    :param ctx: 分派上下文（创建 Risk 时的数据 + 分派前实例化的规则字段）
    :param rules: 候选分派规则（默认从 strategy.dispatch_rules 取）
    :param strategy: 全局策略
    :param rule_order: 分派规则优先级（默认 strategy.dispatch_rule_order）
    :return: DispatchResult；未命中且无默认规则 -> matched=False（调用方兜底策略级）

    匹配语义：
    - 非默认规则：evaluate(conditions) 为真 -> 命中
    - 默认规则（is_default / 空条件树）：跳过条件判定直接兜底
    """
    if strategy is not None:
        rules = rules if rules is not None else list(strategy.dispatch_rules.filter(is_deleted=False))
        rule_order = rule_order if rule_order is not None else strategy.dispatch_rule_order or []
    if not rules:
        return DispatchResult.miss()
    # 分派规则按优先级排序
    order_index = {rid: idx for idx, rid in enumerate(rule_order or [])}
    ordered = sorted(rules, key=lambda r: order_index.get(r.rule_id, len(order_index)))

    default_result: Optional[DispatchResult] = None
    for rule in ordered:
        conditions = rule.conditions
        if rule.is_default or evaluate_is_empty(conditions):
            if default_result is None:
                default_result = DispatchResult.hit(rule)
            continue
        if evaluate(to_condition_tree(conditions), ctx):
            return DispatchResult.hit(rule)
    return default_result if default_result is not None else DispatchResult.miss()


def to_condition_tree(conditions: Union[dict, DispatchConditionNode]) -> DispatchConditionNode:
    """
    DispatchRule.conditions（JSON dict）-> DispatchConditionNode（pydantic 对象）
    """
    if isinstance(conditions, DispatchConditionNode):
        return conditions
    subs = [to_condition_tree(sub) for sub in conditions.get("conditions") or []]
    return DispatchConditionNode(
        connector=conditions.get("connector") or FilterConnector.AND,
        conditions=subs,
        condition=conditions.get("condition"),
    )


def evaluate_is_empty(conditions: Union[dict, DispatchConditionNode, None]) -> bool:
    """条件树是否为空树（无叶子且无有效子树）"""
    if conditions is None:
        return True
    if isinstance(conditions, dict):
        # 无 condition 且 conditions 列表为空（或子树全空）
        if conditions.get("condition"):
            return False
        return all(evaluate_is_empty(sub) for sub in conditions.get("conditions") or [])
    if isinstance(conditions, DispatchConditionNode):
        if conditions.condition:
            return False
        return all(evaluate_is_empty(sub) for sub in conditions.conditions)
    return False