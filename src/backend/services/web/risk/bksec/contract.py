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


def build_event_payload(
    config: BkSecConfig,
    risk: Optional[Risk] = None,
    events: Optional[List[dict]] = None,
) -> dict:
    """
    构建bksec发单报文

    build_event_payload 响应结构：
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
    fields = {}
    for mapping in config.field_mappings:
        if mapping.key:
            fields[mapping.key] = render_value(mapping.value, context)
    # 初始责任人为空时以安全接口人兜底
    if not fields.get(BKSEC_FIELD_INITIAL_OWNER):
        fields[BKSEC_FIELD_INITIAL_OWNER] = ";".join(load_security_person())
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
    构造插件的最终入参常量（渲染后的具体值）
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
    # risk_type_extra 承载全部字段映射
    constants[BKSEC_PARAM_RISK_TYPE_EXTRA] = json.dumps(
        {m.key: render_value(m.value, context) for m in config.field_mappings},
        ensure_ascii=False,
    )
    # 插件控制参数（${action} 由 SOPS 模板节点输入决定，审计侧不传）：
    # 测试发送用 once_task=yes 立即结束、豁免单次去重（样例风险单的 raw_event_id 可能已被正式发送占用）
    constants[BKSEC_PARAM_ONCE_TASK] = BKSEC_ONCE_TASK_TEST if test_operator else BKSEC_ONCE_TASK_DEFAULT
    return constants


def split_persons(value: Any) -> List[str]:
    """把人名数据归一化为列表：列表原样、字符串按分号切分；过滤空值与 "None"/"null" 脏值"""
    if not value:
        return []
    items = value if isinstance(value, (list, tuple)) else str(value).split(";")
    persons: List[str] = []
    for item in items:
        name = str(item or "").strip()
        if not name or name.lower() in BKSEC_INVALID_PERSON_VALUES:
            continue
        persons.append(name)
    return persons


def load_fallback_persons(risk: Optional[Risk] = None) -> List[str]:
    """责任人兜底：风险责任人 → 当前处理人 → 安全接口人"""
    if risk is not None:
        for value in (risk.operator, risk.current_operator):
            persons = split_persons(value)
            if persons:
                return persons
    return [person for person in load_security_person() if person]


def coerce_operator_constant(value: str, risk: Optional[Risk] = None) -> str:
    """
    operator 入参规范化：保证为插件 json.loads 可接受的 JSON 数组串。

    配置页的 operator 是「责任人模板」，用户按语义书写即可（如 {{ risk.operator }}）；
    渲染结果是人名文本（多人以分号分隔，源自 display_value / security_person 的拼接形态）。
    分号切分与 JSON 序列化属于与插件之间的传输层契约，由本函数统一处理，
    不要求用户在模板里写 split | tojson。

    - 已是合法 JSON 数组串 → 解析后重新序列化，保证格式统一
    - 分号分隔的人名文本 → 切分后序列化
    - 取不到任何人名 → 回退到风险责任人 / 安全接口人
    """
    raw = str(value or "").strip()
    persons: List[str] = []
    if raw:
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            persons = split_persons(raw)
        else:
            # 非数组的合法 JSON（对象/数字/布尔）不是人名，视为无效走兜底
            persons = split_persons(parsed) if isinstance(parsed, list) else []
    if not persons:
        persons = load_fallback_persons(risk)
    return json.dumps(persons, ensure_ascii=False)


def render_event_constant(template_json: str, risk: Optional[Risk] = None) -> str:
    """
    渲染字符串和模板混写
    """
    return render_value(template_json, build_render_context(risk=risk))


def render_risk_type_extra(template_json: str, risk: Optional[Risk] = None) -> str:
    """
    渲染 risk_type_extra（字段映射序列化串）

    必须逐字段渲染后重新序列化：整体按字符串渲染时，字段值自带的引号
    （如 operator 的 tojson 输出 ["v_dryidong"]）会破坏 JSON 结构，
    导致插件 json.loads 失败（Expecting ',' delimiter）。
    """
    context = build_render_context(risk=risk)
    try:
        mapping = json.loads(template_json)
    except (ValueError, TypeError):
        return render_value(template_json, context)
    if not isinstance(mapping, dict):
        return render_value(template_json, context)
    return json.dumps(
        {key: render_value(value, context) for key, value in mapping.items()},
        ensure_ascii=False,
    )
