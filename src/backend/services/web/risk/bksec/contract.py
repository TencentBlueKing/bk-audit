# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import datetime
import json
import logging
from typing import Any, List, Optional

from django.utils import timezone

from services.web.risk.bksec.config import BkSecConfig
from services.web.risk.bksec.constants import (
    BKSEC_FIELD_INITIAL_OWNER,
    BKSEC_INVALID_PERSON_VALUES,
    BKSEC_ONCE_TASK_DEFAULT,
    BKSEC_ONCE_TASK_TEST,
    BKSEC_PARAM_ONCE_TASK,
    BKSEC_PARAM_OPERATOR,
    BKSEC_PARAM_RISK_TYPE_EXTRA,
    BKSEC_PARAM_TARGET,
    BKSEC_PARAM_TARGET_TYPE,
    BKSEC_PLUGIN_STANDARD_FIELDS,
)
from services.web.risk.bksec.render import (
    TIME_DISPLAY_FORMAT,
    build_render_context,
    build_risk_data,
    load_security_person,
    render_value,
)
from services.web.risk.models import Risk

logger = logging.getLogger("celery")


def render_field_values(items, context: dict) -> dict:
    """
    把 (key, 模板) 序列渲染成事件体 fields 字典，并统一应用初始责任人兜底

    BkSecFieldMapping(key="target",     name="风险资产信息", value="云账号 {{ risk.raw_event_id }}", required=True)
    BkSecFieldMapping(key="operator",   name="初始责任人",   value="{{ risk.operator }}",            required=True)
    BkSecFieldMapping(key="description", name="描述",        value="{{ risk.event_content }}")
        转换为
    [("target", "云账号 {{ risk.raw_event_id }}"),
     ("operator", "{{ risk.operator }}"),
     ("description", "{{ risk.event_content }}")]
    """
    fields = {}
    for key, template in items:
        if not key:
            continue
        fields[key] = render_value(template, context)
    if not (fields.get(BKSEC_FIELD_INITIAL_OWNER) or "").strip():
        fields[BKSEC_FIELD_INITIAL_OWNER] = ";".join(load_security_person())
    return fields


def build_event_payload(
    config: BkSecConfig,
    risk: Optional[Risk] = None,
    events: Optional[List[dict]] = None,
) -> dict:
    """
    构建bksec工单预览报文

    {
        # 1. 风险类型（来自配置）
        "risk_type": "159",

        # 2. 字段数据（field_mappings 渲染结果）
        "fields": {
            "target": "云账号 12345678",      # 风险资产信息
            "operator": "admin",              # 责任人
            "username": "admin",              # 扩展字段
            "leader_username": "bob",         # 扩展字段
        },

        # 3. 数据源（固定值）
        "source": "bk-audit",

        # 4. 风险 ID
        "risk_id": "risk-001",

        # 5. 风险属性
        "risk_attribute": {
            "title": "云账号未启用MFA",
            "risk_level": "high",
            "event_content": "风险描述",
            "risk_guidance": "处理指引",
            "event_time": "2024-09-24T12:00:00",
            "event_source": "bk-audit",
            "strategy_id": "150",
            "strategy_name": "策略名称",
            "raw_event_id": "raw-001",
            "operator": "alice",
            "current_operator": ["bob"],
            "notice_users": ["charlie"],
        },
    }
    """
    context = build_render_context(risk=risk, events=events)
    fields = render_field_values(((m.key, m.value) for m in config.field_mappings), context)
    # 事件体字段为 BKSEC 侧契约字段，字段名固定，故直接字面量书写
    payload = {
        "risk_type": config.risk_type_id,
        "fields": fields,
        "source": "bk-audit",
    }
    if risk is not None:
        payload["risk_id"] = risk.risk_id
        # 风险属性
        risk_data = build_risk_data(risk)
        payload["risk_attribute"] = {
            "title": risk_data.get("title", ""),
            "risk_level": risk_data.get("risk_level", ""),
            "event_content": risk_data.get("event_content", ""),
            "risk_guidance": risk_data.get("risk_guidance", ""),
            "event_time": risk_data.get("event_time", ""),
            "event_source": risk_data.get("event_source", ""),
            "strategy_id": risk_data.get("strategy_id", ""),
            "strategy_name": risk_data.get("strategy_name", ""),
            "raw_event_id": risk_data.get("raw_event_id", ""),
            "operator": risk_data.get("operator", ""),
            "current_operator": risk_data.get("current_operator", ""),
            "notice_users": risk_data.get("notice_users", ""),
        }
    return payload


def build_pa_params(config: BkSecConfig) -> dict:
    """
    生成自动创建处理规则的 pa_params（未渲染模板）

    - 标准入参，直接从risk对象获取 → {"field": 风险字段, "value": ""}  9个
    - ${target_type} → 目标资产类型（config.target_type）
    - ${target} → 具体风险对象（config.target）
    - ${operator} → 初始责任人（config.operator）
    - ${once_task} → 插件控制参数（测试 yes / 正式 no）
    - ${action} 由 SOPS 模板节点输入决定
    - ${risk_type_extra} → 全部字段映射序列化的模板串（含 target/target_type/operator，发送时渲染）
    """
    params = {param: {"field": field, "value": ""} for param, field in BKSEC_PLUGIN_STANDARD_FIELDS.items()}
    params[BKSEC_PARAM_TARGET_TYPE] = {"field": "", "value": config.target_type}
    params[BKSEC_PARAM_TARGET] = {"field": "", "value": config.target}
    params[BKSEC_PARAM_OPERATOR] = {"field": "", "value": config.operator}
    params[BKSEC_PARAM_RISK_TYPE_EXTRA] = {
        "field": "",
        "value": json.dumps(
            {m.key: m.value for m in config.field_mappings},
            ensure_ascii=False,
        ),
    }
    params[BKSEC_PARAM_ONCE_TASK] = {"field": "", "value": BKSEC_ONCE_TASK_DEFAULT}
    # 风险类型 ID 作为 pa_params 元数据：不映射为 SOPS 模板常量，仅用于规则版本内容差异判定
    params["risk_type_id"] = config.risk_type_id
    return params


def build_plugin_constants(config: BkSecConfig, risk: Optional[Risk] = None, test_operator: str = "") -> dict:
    """
    测试发单时构造插件的最终入参常量（渲染后的具体值）

    因为测试发单时入参是对象，而正式发单时入参是rule.pa_params中的字符串
    """
    context = build_render_context(risk=risk)
    constants: dict = {}
    # 标准入参：取风险字段值（时间字段与 AutoProcess 一致格式化）
    for param, field in BKSEC_PLUGIN_STANDARD_FIELDS.items():
        value = getattr(risk, field, "") if risk is not None else ""
        if isinstance(value, datetime.datetime):
            value = value.astimezone(tz=timezone.get_default_timezone()).strftime(TIME_DISPLAY_FORMAT)
        elif isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False, default=str)
        constants[param] = value
    # 三个独立入参模板渲染（来源 config.target/target_type/operator）
    constants[BKSEC_PARAM_TARGET_TYPE] = render_value(config.target_type, context)
    constants[BKSEC_PARAM_TARGET] = render_value(config.target, context)
    constants[BKSEC_PARAM_OPERATOR] = coerce_operator_constant(render_value(config.operator, context), risk=risk)
    if test_operator:
        constants[BKSEC_PARAM_OPERATOR] = json.dumps([test_operator], ensure_ascii=False)
    # risk_type_extra 承载全部字段映射（初始责任人兜底与预览同口径）
    constants[BKSEC_PARAM_RISK_TYPE_EXTRA] = json.dumps(
        render_field_values(((m.key, m.value) for m in config.field_mappings), context),
        ensure_ascii=False,
    )
    # 插件控制参数（${action} 由 SOPS 模板节点输入决定，审计侧不传）：
    # 测试发送用 once_task=yes 立即结束、豁免单次去重（样例风险单的 raw_event_id 可能已被正式发送占用）
    constants[BKSEC_PARAM_ONCE_TASK] = BKSEC_ONCE_TASK_TEST if test_operator else BKSEC_ONCE_TASK_DEFAULT
    return constants


def coerce_operator_constant(value: str, risk: Optional[Risk] = None) -> str:
    """
    ${operator} 入参收口：解析 → 清洗 → 兜底 → 序列化，输出恒为插件 json.loads 可接受的 JSON 数组串。

    配置页 operator 是责任人模板（如 {{ risk.operator }}），渲染结果形态不一，统一在此处理：
    1. 解析：
        '["1","2"]' --> '["1","2"]'
        "a;b"  --> '["a","b"]'  分号为分隔符
    2. 清洗：空串/纯空白丢弃，"None"/"null"/"undefined"/"nan" 脏值丢弃
    3. 兜底：解析清洗后无人 → risk.operator（同样清洗）→ 仍无人 → 安全接口人；
    4. 序列化：json.dumps(list)。

    """

    def _clean(items: Any) -> List[str]:
        raw_items = items if isinstance(items, (list, tuple)) else str(items or "").split(";")
        persons: List[str] = []
        for item in raw_items:
            name = str(item or "").strip()
            if name and name.lower() not in BKSEC_INVALID_PERSON_VALUES:
                persons.append(name)
        return persons

    raw = str(value or "").strip()
    persons: List[str] = []
    if raw:
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            persons = _clean(raw)
        else:
            persons = _clean(parsed) if isinstance(parsed, list) else []
    if not persons and risk is not None:
        persons = _clean(risk.operator)
    if not persons:
        persons = [person for person in load_security_person() if person]
    return json.dumps(persons, ensure_ascii=False)


def render_risk_type_extra(template_json: str, context: dict) -> str:
    """
    渲染 risk_type_extra这个sops入参为具体值（用于正式发单）
    """
    try:
        mapping = json.loads(template_json)
    except (ValueError, TypeError):
        return render_value(template_json, context)
    if not isinstance(mapping, dict):
        return render_value(template_json, context)
    # 初始责任人兜底与预览/测试发送同口径（render_field_values）
    return json.dumps(render_field_values(mapping.items(), context), ensure_ascii=False)


def render_bksec_constant(key: str, value: Any, context: dict, risk: Optional[Risk] = None) -> Any:
    """
    BKSEC 自动规则 pa_params 值加工：派单时按当前风险把配方/模板渲染成终值。

    引擎（AutoProcess）只做一次委托，插件契约细节在此收口：
    - 普通标量模板（含 {{ 的文字混排，risk_type_extra 除外）→ render_value；
    - ${risk_type_extra}（字段映射 JSON 模板串）→ 逐字段渲染重组（防值内引号破坏 JSON）；
    - ${operator} → coerce_operator_constant（插件 JSON 数组串契约 + 责任人兜底）。
    """
    if isinstance(value, str) and "{{" in value and key != BKSEC_PARAM_RISK_TYPE_EXTRA:
        value = render_value(value, context)
    if key == BKSEC_PARAM_RISK_TYPE_EXTRA and isinstance(value, str):
        value = render_risk_type_extra(value, context)
    if key == BKSEC_PARAM_OPERATOR:
        value = coerce_operator_constant(value, risk=risk)
    return value
