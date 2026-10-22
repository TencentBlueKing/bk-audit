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

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy

from apps.meta.models import GlobalMetaConfig
from apps.meta.utils.saas import get_saas_url
from services.web.risk.bksec.constants import (
    BKSEC_RENDER_EVENT_LIMIT,
    BKSEC_REQUIRED_FIELD_KEYS,
)
from services.web.risk.constants import SECURITY_PERSON_KEY
from services.web.risk.models import Risk

logger = logging.getLogger("celery")

TIME_DISPLAY_FORMAT = "%Y-%m-%d %H:%M:%S"


def display_value(value: Any) -> str:
    """
    渲染为字符串：列表用分号拼接、字典转 JSON、时间格式化
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


def _match_display_name_key(data: dict, name: str) -> Any:
    """
    兼容 display_name 形式的键（如「操作人用户名(username)」）

    手动事件或早期策略入库的 event_data 可能以「展示名(原始字段名)」为键，
    此时按原始字段名（括号内）匹配，保证 {{ event.username }} 仍可取到值。
    """
    suffix = "({})".format(name)
    for key, value in data.items():
        if isinstance(key, str) and key.endswith(suffix):
            return value
    return ""


def _event_field_value(event: dict, name: str) -> Any:
    """
    事件字段取值：优先事件顶层字段，其次 event_data 子字典

    事件自定义字段（event_data_field_configs 定义的字段）在检索结果中位于 event_data，
    且可能为 JSON 字符串（取决于解析阶段），需兼容解析后再取值。
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
        return _match_display_name_key(data, name)
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


class RiskNamespace:
    """
    风险命名空间：{{ risk.xxx }}，未定义字段渲染为空串
    """

    def __init__(self, data: dict):
        object.__setattr__(self, "_data", data or {})

    def __getattr__(self, name: str) -> Any:
        data = object.__getattribute__(self, "_data")
        return data.get(name, "")


def load_security_person() -> List[str]:
    """
    安全接口人（无责任人风险的发单兜底，决策 D4）
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


# 风险变量展示元数据，定义所有可用的风险变量
RISK_VARIABLE_META = {
    "risk_id": (gettext_lazy("风险ID"), "R-20260101-0001"),
    "title": (gettext_lazy("风险标题"), "异常登录风险"),
    "event_content": (gettext_lazy("风险描述"), "检测到异常登录行为"),
    "risk_level": (gettext_lazy("风险等级"), "high"),
    "risk_hazard": (gettext_lazy("风险危害"), "可能导致数据泄露"),
    "risk_guidance": (gettext_lazy("处理指引"), "请及时修改密码"),
    "risk_tags": (gettext_lazy("风险标签"), "高危"),
    "risk_label": (gettext_lazy("风险标记"), "normal"),
    "status": (gettext_lazy("处理状态"), "NEW"),
    "rule_id": (gettext_lazy("处理规则"), "100"),
    "strategy_id": (gettext_lazy("策略ID"), "1001"),
    "strategy_name": (gettext_lazy("策略名称"), "离线策略审计"),
    "strategy_rule_id": (gettext_lazy("发现规则ID"), "200"),
    "raw_event_id": (gettext_lazy("原始事件ID"), "evt-001"),
    "origin_operator": (gettext_lazy("原始责任人"), "admin"),
    "operator": (gettext_lazy("责任人"), "admin"),
    "current_operator": (gettext_lazy("当前处理人"), "admin"),
    "notice_users": (gettext_lazy("关注人"), "follower"),
    "event_type": (gettext_lazy("风险类型"), "账号安全"),
    "event_source": (gettext_lazy("风险数据源"), "bkm"),
    "event_time": (gettext_lazy("首次发现时间"), "2026-01-01 00:00:00"),
    "event_end_time": (gettext_lazy("最后发现时间"), "2026-01-01 00:10:00"),
    "last_operate_time": (gettext_lazy("最后一次处理时间"), "2026-01-02 00:00:00"),
    "security_person": (gettext_lazy("安全接口人"), "sec_admin"),
    "risk_url": (gettext_lazy("风险单链接"), "https://audit.example.com/risk-manage/detail/R-001"),
}


def build_risk_data(risk: Optional[Risk]) -> dict:
    """
    构建风险变量数据，用于风险变量渲染
    """
    if risk is None:
        return {}
    strategy = getattr(risk, "strategy", None)
    return {
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
        "event_source": risk.event_source or "",
        "event_time": display_value(risk.event_time),
        "event_end_time": display_value(risk.event_end_time),
        "last_operate_time": display_value(risk.last_operate_time),
        # 无责任人时以安全接口人兜底，模板可写 {{ risk.operator or risk.security_person }}
        "security_person": ";".join(load_security_person()),
        "risk_url": "{}/risk-manage/detail/{}".format(get_saas_url(settings.APP_CODE), risk.risk_id),
    }


def build_render_context(risk: Optional[Risk] = None, events: Optional[List[dict]] = None) -> dict:
    """
    构建 BKSEC 字段渲染上下文：risk / event 命名空间

    预览、测试发送、正式发送共用，保证三处渲染结果一致。
    """
    if events is None and risk is not None:
        events = load_risk_events(risk)
    context = {
        "risk": RiskNamespace(build_risk_data(risk)),
        "event": EventNamespace(events or []),
    }
    return context


def _normalize_field_type(value: Any) -> str:
    """
    归一化 BKSEC 字段类型

    接口返回的是 storage_type，且大小写不统一（同时存在 STRING / string），统一转小写后输出为 type。
    已知取值：string / int / object / timestamp；未知取值原样小写返回，不丢弃信息。
    接口未返回类型时保持为空串，由前端自行决定缺省渲染方式。
    """
    return str(value or "").strip().lower()


def _extract_risk_access_fields(item: dict) -> list:
    """
    从风险类型对象中抽取工单字段 schema（risk_access_fields）
    入参示例（来自 BKSEC risk_access_list API）：
    {
        "id": 159,
        "name": "云账号未启用MFA",
        "is_formal": True,
        "risk_access_fields": [
            {"id": 9, "key": "submitter", "name": "提单人", "sequence": 0, "storage_type": "STRING",
             "source_type": "CUSTOM", "unique": False},
        ]
    }
    required 由审计中心按白名单 BKSEC_REQUIRED_FIELD_KEYS 判定（BKSEC 不返回该字段）：
    target / target_type / operator 为必填，其余一律非必填。
    type 取自接口的 storage_type 并归一化小写（string / int / object / timestamp）。

    返回值示例：
    [
        {"key": "target", "name": "风险资产信息", "required": True, "type": "string"},
        {"key": "submitter", "name": "提单人", "required": False, "type": "string"},
    ]
    """
    if not isinstance(item, dict):
        return []
    raw_fields = item.get("risk_access_fields") or item.get("fields") or []
    fields = []
    if isinstance(raw_fields, list):
        for f in raw_fields:
            if not isinstance(f, dict):
                continue
            key = f.get("key", "")
            fields.append(
                {
                    "key": key,
                    "name": f.get("name", "") or f.get("label", ""),
                    "required": key in BKSEC_REQUIRED_FIELD_KEYS,
                    "type": _normalize_field_type(f.get("type") or f.get("storage_type", "")),
                }
            )
    return fields


def _normalize_risk_type(item: dict) -> dict:
    """
    归一化 BKSEC 风险类型列表项

    入参示例（来自 BKSEC risk_access_list API）：
    {
        "id": 159,
        "name": "云账号未启用MFA",
        "is_formal": True,
        "risk_access_fields": [
            {"id": 9, "key": "submitter", "name": "提单人", "sequence": 0,
             "storage_type": "STRING", "source_type": "CUSTOM", "unique": False},
        ]
    }

    返回值示例：
    {
        "risk_type_id": "159",
        "risk_type_name": "云账号未启用MFA",
        "is_formal": True,
        "fields": [
            {"key": "submitter", "name": "提单人", "required": False, "type": "string"},
        ]
    }
    """
    if not isinstance(item, dict):
        return {}
    return {
        "risk_type_id": str(item.get("id", "")),
        "risk_type_name": item.get("name", "") or item.get("risk_type_name", ""),
        "is_formal": bool(item.get("is_formal", False)),
        "fields": _extract_risk_access_fields(item),
    }
