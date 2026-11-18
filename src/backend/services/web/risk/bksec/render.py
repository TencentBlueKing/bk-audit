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
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

# 渲染流程
# ① 装载   build_risk_data  风险对象 → 数据字典（不查库，加工已在手的风险）
#          load_risk_events 查回事件列表（外部查询，供 {{ event.xxx }} 用）
# ② 归一   display_value    任意值 → 文本：列表→"a;b"、dict/list→JSON 串、
#          时间→"YYYY-MM-DD HH:MM:SS"。风险字段在装载时批量预转；
#          事件字段在模板取值时惰性转换（模板不碰的字段不做功）
# ③ 组装   build_render_context → {"risk": {...}, "event": EventNamespace, 扁平变量...}
#          命名空间即抽屉：{{ risk.xxx }} 取风险字段（成品文本），
#          {{ event.xxx }} 取事件字段（现取现磨，默认最后一条事件）；
#          此外平铺裸变量（对齐风险单标题渲染口径）：{{ event_time }} 直接取字段，
#          {{ event_data['xx'] }} 按事件自定义字段下标取值（风险字段优先、事件字段补充）
# ④ 渲染   render_value     jinja 展开 "文字 + {{ 变量 }}" 混排模板 → 终值
#
# 使用方：预览（build_event_payload）/ 测试发送（build_plugin_constants）/ 正式发单（AutoProcess）。
#       build_render_context 每次会触发一次load_risk_events 外部查询，应建一次上下文、多字段渲染共用。


import datetime
import json
import logging
from typing import Any, List, Optional

from django.conf import settings
from django.utils import timezone

from apps.meta.models import GlobalMetaConfig
from apps.meta.utils.saas import get_saas_url
from core.render import jinja2_environment
from services.web.risk.bksec.constants import BKSEC_RENDER_EVENT_LIMIT
from services.web.risk.constants import SECURITY_PERSON_KEY
from services.web.risk.models import Risk

logger = logging.getLogger("celery")

TIME_DISPLAY_FORMAT = "%Y-%m-%d %H:%M:%S"


def render_value(template: str, context: dict) -> str:
    """
    渲染字段值模板（支持字符串和风险变量/事件变量混写）
    - 风险变量：{{ risk.risk_id }}、{{ risk.operator }}
    - 事件变量：{{ event.username }}，取最后一条事件的字段值
    - 扁平变量：{{ event_time }}（风险字段优先、事件字段补充）
    - 事件自定义字段：{{ event_data['username'] }}，event_data 恒在上下文中（缺省空 dict）
    """
    if not isinstance(template, str) or "{{" not in template:
        return template if isinstance(template, str) else ""
    env = jinja2_environment(autoescape=False)
    try:
        return env.from_string(template).render(**context).strip()
    except Exception as err:  # NOCC:broad-except(渲染失败需明确可见)
        logger.exception("[BkSecRender] Render failed, template=%s err=%s", template, err)
        raise


def display_value(value: Any) -> str:
    """
    将列表/事件对象等渲染为字符串：列表用分号拼接、字典转 JSON、时间格式化
    - 列表：分号拼接
    - 字典：转 JSON
    - 时间：格式化为 YYYY-MM-DD HH:MM:SS
    """
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        if isinstance(value, list) and not any(isinstance(v, (dict, list)) for v in value):
            return ";".join(display_value(v) for v in value)
        return json.dumps(value, ensure_ascii=False, default=str)
    if isinstance(value, datetime.datetime):
        return value.astimezone(tz=timezone.get_default_timezone()).strftime(TIME_DISPLAY_FORMAT)
    return str(value)


class EventFieldValues(list):
    """
    事件字段跨事件取值列表

    直接渲染时取最后一条事件的值。
    """

    def __str__(self) -> str:
        return display_value(self[-1]) if self else ""


def _event_field_value(event: dict, name: str) -> Any:
    """
    事件字段取值：优先事件顶层字段，其次 event_data 子字典

    事件自定义字段（event_data_field_configs 定义的字段）在检索结果中位于 event_data，
    且可能为 JSON 字符串（取决于解析阶段），需兼容解析后再取值。
    兼容 display_name 形式的键（如「操作人用户名(username)」）：手动事件或早期策略入库的
    event_data 可能以「展示名(原始字段名)」为键，此时按括号内原始字段名匹配。
    """
    if name in event:
        return event.get(name, "")
    data = event.get("event_data") or {}
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except ValueError:
            return ""
    if isinstance(data, dict):
        if name in data:
            return data.get(name, "")
        suffix = "({})".format(name)
        for key, value in data.items():
            if isinstance(key, str) and key.endswith(suffix):
                return value
    return ""


class EventNamespace:
    """
    事件命名空间：{{ event.字段 }}

    - 直接取（{{ event.username }}）：默认渲染最后一条事件的值
    """

    def __init__(self, events: List[dict]):
        object.__setattr__(self, "_events", events or [])

    def __getattr__(self, name: str) -> EventFieldValues:
        events = object.__getattribute__(self, "_events")
        return EventFieldValues(display_value(_event_field_value(ev, name)) for ev in events)


class _RiskData(dict):
    """风险变量字典：未定义字段取值为空串（链式调用不抛错，如 {{ risk.x.split() }}）"""

    def __missing__(self, key: str) -> str:
        return ""


class _EventData(dict):
    """
    事件自定义字段字典：{{ event_data['xx'] }}

    保留字典结构以支持下标取值（对齐风险单标题渲染口径）；
    整体渲染时输出 JSON 串，与 display_value 对 dict 的处理口径一致。
    """

    def __str__(self) -> str:
        return json.dumps(self, ensure_ascii=False, default=str)


def _normalize_event_data(value: Any) -> Any:
    """event_data 值归一：嵌套字典递归保留可下标结构，其余按 display_value 口径转文本"""
    if isinstance(value, dict):
        return _EventData({str(k): _normalize_event_data(v) for k, v in value.items()})
    return display_value(value)


def parse_event_data(value: Any) -> _EventData:
    """
    解析 event_data（恒返回 _EventData）

    检索结果中的 event_data 可能是 JSON 字符串（取决于解析阶段），需兼容解析；
    缺失或非法时返回空 dict，保证 {{ event_data['xx'] }} 只会渲染为空、不会抛未定义错误。
    """
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return _EventData()
    if isinstance(value, dict):
        return _EventData({str(k): _normalize_event_data(v) for k, v in value.items()})
    return _EventData()


def load_security_person() -> List[str]:
    """
    安全接口人
    """
    persons = GlobalMetaConfig.get(config_key=SECURITY_PERSON_KEY) or []
    return [p for p in persons if p]


def load_risk_events(risk: Risk, limit: int = BKSEC_RENDER_EVENT_LIMIT) -> List[dict]:
    """
    加载事件变量，用于事件变量渲染，查询失败时降级为空列表
    """
    try:
        from services.web.risk.handlers.event import EventHandler

        strategy = getattr(risk, "strategy", None)
        namespace = getattr(strategy, "namespace", "") if strategy else ""
        if not namespace:
            return []
        # 时间窗口按本地时区格式化：检索侧按本地时间解释，直接 strftime 会输出 UTC 数值导致整体偏移
        start_time = timezone.localtime(risk.event_time)
        end_time = timezone.localtime(risk.event_end_time or timezone.now())
        # 零宽窗口兜底：单事件风险 event_end_time == event_time，秒级格式化丢毫秒会把事件自身排除
        if end_time <= start_time:
            end_time = start_time + datetime.timedelta(seconds=1)
        response = EventHandler.search_event(
            namespace=namespace,
            start_time=start_time.strftime(TIME_DISPLAY_FORMAT),
            end_time=end_time.strftime(TIME_DISPLAY_FORMAT),
            page=1,
            page_size=limit,
            raw_event_id=risk.raw_event_id,
            strategy_id=str(risk.strategy_id),
        )
        events = response.get("results", []) if isinstance(response, dict) else []
        # 事件按时间升序，保证 latest/默认取值语义正确（事件无 event_time 字段，用落库时间戳排序）
        return sorted(events, key=lambda ev: str(ev.get("dtEventTimeStamp") or ev.get("dtEventTime") or ""))
    except Exception as err:  # NOCC:broad-except(渲染降级)
        logger.exception("[BkSecRender] Load events failed, risk_id=%s err=%s", getattr(risk, "risk_id", ""), err)
        return []


def build_risk_data(risk: Optional[Risk]) -> _RiskData:
    """
    构建风险变量数据（{{ risk.xxx }} 命名空间），未定义字段取值为空串
    """
    if risk is None:
        return _RiskData()
    strategy = getattr(risk, "strategy", None)
    return _RiskData(
        {
            "risk_id": risk.risk_id,
            "title": risk.title or "",
            "event_content": risk.event_content or "",
            "raw_event_id": risk.raw_event_id or "",
            "strategy_id": risk.strategy_id,
            "strategy_name": getattr(strategy, "strategy_name", "") if strategy else "",
            "strategy_rule_id": getattr(risk, "strategy_rule_id", "") or "",
            "risk_level": risk.risk_level or "",
            "risk_hazard": risk.risk_hazard or "",
            "risk_guidance": risk.risk_guidance or "",
            "risk_tags": display_value(risk.get_tag_names()) if hasattr(risk, "get_tag_names") else "",
            "status": risk.status or "",
            "risk_label": risk.risk_label or "",
            "rule_id": risk.rule_id or "",
            "operator": display_value(risk.operator),
            "current_operator": display_value(risk.current_operator),
            "notice_users": display_value(risk.notice_users),
            "origin_operator": display_value(risk.origin_operator),
            "event_type": display_value(risk.event_type),
            # 保留字典结构：支持 {{ risk.event_data['xx'] }} / {{ event_data['xx'] }} 下标取值
            "event_data": parse_event_data(risk.event_data),
            "event_source": risk.event_source or "",
            "event_time": display_value(risk.event_time),
            "event_end_time": display_value(risk.event_end_time),
            "last_operate_time": display_value(risk.last_operate_time),
            # 无责任人时以安全接口人兜底，模板可写 {{ risk.operator or risk.security_person }}
            "security_person": ";".join(load_security_person()),
            "risk_url": "{}/risk-manage/detail/{}".format(get_saas_url(settings.APP_CODE), risk.risk_id),
        }
    )


def build_event_flat_data(events: List[dict], risk_data: Optional[_RiskData] = None) -> dict:
    """
    构建扁平变量命名空间（对齐风险单标题渲染口径）：不写命名空间，直接取字段

    - {{ event_time }}：风险字段优先、事件字段补充（最后一条事件），事件字段不覆盖风险字段，
      避免事件里恰好同名的字段把风险字段顶掉；
    - {{ event_data['xx'] }}：按事件自定义字段下标取值，事件无 event_data 时回落到风险单的 event_data，
      两者皆无时为空 dict（下标不命中只渲染为空，不会抛未定义错误）。
    """
    flat: dict = dict(risk_data or {})
    latest = events[-1] if events else {}
    for name, value in latest.items():
        if name == "event_data":
            continue
        flat.setdefault(name, display_value(value))
    flat["event_data"] = parse_event_data(latest.get("event_data")) or flat.get("event_data") or _EventData()
    return flat


def build_render_context(risk: Optional[Risk] = None, events: Optional[List[dict]] = None) -> dict:
    """
    构建 BKSEC 字段渲染上下文

    {
      "risk":  build_risk_data(risk),        # 风险字段字典：{"operator": "alice;bob", ...}
      "event": EventNamespace(load_risk_events(risk)),   # 2 条事件，{{ event.username }} → "bob"
      "event_time": "2024-09-24 12:00:00",   # 扁平变量：{{ event_time }} 直接取字段
      "event_data": {"username": "bob"},     # 扁平变量：{{ event_data['username'] }} → "bob"
    }
    """
    if events is None and risk is not None:
        events = load_risk_events(risk)
    events = events or []
    risk_data = build_risk_data(risk)
    flat = build_event_flat_data(events, risk_data)
    # 命名空间优先级高于扁平变量：事件字段恰好叫 risk/event 时不覆盖命名空间
    flat.pop("risk", None)
    flat.pop("event", None)
    return {
        **flat,
        "risk": risk_data,
        "event": EventNamespace(events),
    }
