"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.

风险批量处理 · 字段插入工具

- `{{operator}}` / `{{event_data.xxx}}` 占位符插值（工单字段 + event_data 点路径）
- 人员字段引用 PersonnelRef：{type: user|field, value}
- $OPERATOR / $OPERATOR_LEADER 人员槽（沿用 apps.notice.parser）

约定：
- 单条操作场景 event_data.* 始终可用；批量场景由调用方通过 allow_event_data 控制
- 缺字段 / 未定义变量替换为空串
- list 值在字符串插值中用英文逗号拼接；人员解析场景 list 拆成多用户
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from apps.notice.constants import MemberVariable
from apps.notice.parser import MemberVariableParser

_PLACEHOLDER_RE = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")

# ------------------------------------------------------------------
# 变量取值
# ------------------------------------------------------------------


def _stringify(value: Any) -> str:
    """把插值结果统一转为字符串：list → 英文逗号拼接，dict → JSON。"""

    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple, set)):
        return ",".join(str(item) for item in value if item is not None)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _resolve_token(risk: Any, token: str) -> Any:
    """解析工单字段 / event_data 点路径。缺字段返回 None。"""

    if not token:
        return None
    parts = token.split(".")
    root = parts[0]
    value: Any = getattr(risk, root, None) if risk is not None else None
    for attr in parts[1:]:
        if isinstance(value, dict):
            value = value.get(attr)
        elif value is None:
            return None
        else:
            value = getattr(value, attr, None)
        if value is None:
            return None
    return value


# ------------------------------------------------------------------
# Description / 字符串模板
# ------------------------------------------------------------------


def render_string(
    template: str | None,
    risk: Any = None,
    operator: str | None = None,
    allow_event_data: bool = True,
) -> str:
    """渲染 `{{operator}}` / `{{event_data.xxx}}` / `{{<risk_field>}}`。

    - 空模板直接返回空串
    - allow_event_data=False 时，`event_data.*` 替换为空串（批量场景策略不唯一）
    - 缺字段替换为空串
    """

    if template is None:
        return ""
    if not isinstance(template, str):
        return _stringify(template)
    if "{{" not in template:
        return template

    def _replace(raw: str) -> str:
        expr = raw.strip()
        # `operator` 语义固定为「当前操作用户」，与 Risk.operator（通知人列表）区分
        if expr == "operator":
            return operator or ""
        if not allow_event_data and (expr == "event_data" or expr.startswith("event_data.")):
            return ""
        return _stringify(_resolve_token(risk, expr))

    # 只替换 {{name}} / {{a.b}}，不走 Jinja2，避免模板里的表达式被执行
    return _PLACEHOLDER_RE.sub(lambda m: _replace(m.group(1)), template)


def render_payload(
    payload: Any,
    risk: Any = None,
    operator: str | None = None,
    allow_event_data: bool = True,
) -> Any:
    """递归渲染 pa_params 结构中的字符串模板。

    - `{value, field}` 结构（字段映射 vs 直接输入互斥）：
      - 有 `field`：跳过 value（走原字段映射路径，不做模板插值）
      - 无 `field`：仅渲染 `value` 字符串
    - 其他 dict / list：递归
    """

    if isinstance(payload, str):
        return render_string(payload, risk=risk, operator=operator, allow_event_data=allow_event_data)
    if isinstance(payload, dict):
        if "value" in payload and "field" in payload and payload.get("field"):
            # 字段映射：由 AutoProcess.process 用 field 从 risk 上取值，这里保持原样
            return {
                k: (
                    v
                    if k == "value"
                    else render_payload(v, risk=risk, operator=operator, allow_event_data=allow_event_data)
                )
                for k, v in payload.items()
            }
        return {
            k: render_payload(v, risk=risk, operator=operator, allow_event_data=allow_event_data)
            for k, v in payload.items()
        }
    if isinstance(payload, list):
        return [render_payload(v, risk=risk, operator=operator, allow_event_data=allow_event_data) for v in payload]
    return payload


# ------------------------------------------------------------------
# 人员字段引用 & 人员槽
# ------------------------------------------------------------------


@dataclass
class PersonnelRef:
    """转单人员字段引用。

    - type=user：`value` 即用户名，可直接是 `$OPERATOR` / `$OPERATOR_LEADER` 人员槽
    - type=field：`value` 是工单字段或 `event_data.xxx` 点路径，运行时从 risk 取值
    """

    type: str
    value: str

    USER = "user"
    FIELD = "field"


def normalize_personnel_ref(item: Any) -> PersonnelRef:

    if isinstance(item, PersonnelRef):
        return item
    if isinstance(item, str):
        return PersonnelRef(type=PersonnelRef.USER, value=item)
    if isinstance(item, dict):
        ptype = item.get("type") or PersonnelRef.USER
        value = item.get("value") or ""
        if not isinstance(value, str):
            value = _stringify(value)
        return PersonnelRef(type=ptype, value=value)
    raise ValueError(f"unsupported personnel ref: {item!r}")


def normalize_personnel_refs(items: Iterable[Any]) -> list[PersonnelRef]:
    return [normalize_personnel_ref(item) for item in items or []]


class _RiskOperatorParser(MemberVariableParser):
    """展开 $OPERATOR / $OPERATOR_LEADER 人员槽。"""

    def is_skip(self, member: str) -> bool:
        return False


def _expand_variable(raw: str, parser: _RiskOperatorParser) -> list[str]:
    """值若命中 $OPERATOR / $OPERATOR_LEADER 变量，展开为具体用户名。"""

    matched = MemberVariable.match(raw)
    if matched is None:
        return [raw]
    expanded = parser.parse_member(matched) or []
    return [u for u in expanded if u]


def resolve_personnel_refs(
    refs: Iterable[Any],
    risk: Any,
    allow_event_data: bool = True,
) -> list[str]:
    """把 PersonnelRef 列表解析成实际用户名列表。

    - 保持顺序去重
    - type=field 解析后 list 拆成多用户，dict / 标量按字符串处理
    - 命中 $OPERATOR / $OPERATOR_LEADER 时展开人员槽（依赖 risk.operator）
    - 空值 / 无法解析 → 忽略该项；若最终结果为空由调用方判定为失败
    """

    parser = _RiskOperatorParser(operators=list(getattr(risk, "operator", None) or []))
    resolved: list[str] = []
    seen: set = set()

    def _push(name: str) -> None:
        if not name or name in seen:
            return
        seen.add(name)
        resolved.append(name)

    for ref in normalize_personnel_refs(refs):
        raw = (ref.value or "").strip()
        if not raw:
            continue
        if ref.type == PersonnelRef.FIELD:
            if not allow_event_data and (raw == "event_data" or raw.startswith("event_data.")):
                continue
            value = _resolve_token(risk, raw)
            candidates: list[str] = []
            if isinstance(value, (list, tuple, set)):
                candidates = [str(v) for v in value if v]
            elif isinstance(value, dict) or value is None:
                candidates = []
            else:
                candidates = [str(value)]
            for cand in candidates:
                for name in _expand_variable(cand, parser):
                    _push(name)
            continue
        # type=user
        for name in _expand_variable(raw, parser):
            _push(name)
    return resolved


__all__ = [
    "PersonnelRef",
    "normalize_personnel_ref",
    "normalize_personnel_refs",
    "render_payload",
    "render_string",
    "resolve_personnel_refs",
]
