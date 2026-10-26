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
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from services.web.query.ai_assistant.exceptions import InvalidConditionError
from services.web.query.ai_assistant.services.condition import ConditionAssemblyService

NL2RISK_USER_PROMPT = """\
当前时间：{current_time}
当前请求人：{username}
当前可用场景：
{scenes_text}
当前视角/范围：
{scope_text}

可用标签：
{tags_text}

可用策略：
{strategies_text}

用户查询：{query}"""


def _format_items(items: List[dict], key_id: str = "id", key_name: str = "name") -> str:
    if not items:
        return "无"
    return "\n".join(f"- id={item.get(key_id, '')}, 名称={item.get(key_name, '')}" for item in items)


def _format_scope(scope_type: str = "", scope_id: str = "") -> str:
    if not scope_type:
        return "无"
    if scope_id:
        return f"scope_type={scope_type}, scope_id={scope_id}"
    return f"scope_type={scope_type}"


def build_nl2risk_user_message(
    query: str,
    tags: List[dict],
    strategies: List[dict],
    username: str = "",
    scenes: List[dict] = None,
    scope_type: str = "",
    scope_id: str = "",
) -> str:
    return NL2RISK_USER_PROMPT.format(
        current_time=datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        username=username or "未知",
        scenes_text=_format_items(scenes or []),
        scope_text=_format_scope(scope_type, scope_id),
        tags_text=_format_items(tags),
        strategies_text=_format_items(strategies),
        query=query,
    )


def extract_json_from_text(text: Optional[str]) -> dict:
    if not text or not text.strip():
        return {}
    raw_text = text.strip()
    try:
        result = json.loads(raw_text)
        if isinstance(result, str):
            return extract_json_from_text(result)
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, TypeError):
        pass
    if '\\"' in raw_text:
        try:
            result = json.loads(raw_text.replace('\\"', '"'))
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, TypeError):
            pass
    return {}


def extract_filter_conditions_from_ai_result(result: Any) -> Tuple[dict, str]:
    if isinstance(result, dict):
        filter_conditions = result.get("filter_conditions")
        if isinstance(filter_conditions, dict) and filter_conditions:
            return filter_conditions, ""

        for key in ("message", "content", "output"):
            parsed = extract_json_from_text(result.get(key))
            if parsed:
                return parsed, ""

        message = result.get("message") or result.get("content") or result.get("output") or ""
        return {}, str(message).strip()

    raw_text = str(result)
    filter_conditions = extract_json_from_text(raw_text)
    message = "" if filter_conditions else raw_text.strip()
    return filter_conditions, message


def _accepted_time_shortcut(value: Any) -> Optional[str]:
    """复用日志检索的 time_shortcut 校验。"""

    if not isinstance(value, str) or ConditionAssemblyService.TIME_SHORTCUT_PATTERN.match(value) is None:
        return None
    try:
        return ConditionAssemblyService._normalize_time_shortcut(value)
    except InvalidConditionError:
        return None


_END_TOLERANCE = timedelta(hours=2)


def _parse_filter_time(value: Any) -> Optional[datetime]:
    if not value:
        return None
    parsed = parse_datetime(str(value))
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _span_origin(start: datetime, reference: datetime) -> Optional[str]:
    """按 月/天/小时 取最大可对齐单位，复用 condition 的月粒度白名单。"""

    days = (reference.date() - start.date()).days
    if days < 0:
        return None

    # 月粒度：天数命中 condition 白名单且日对齐（相对窗口结束于 now，不校验时分）
    for count, mapped_days in ConditionAssemblyService.MONTH_SHORTCUT_DAYS.items():
        if days == mapped_days and start.day == reference.day:
            return f"now-{count}M"

    # 天粒度
    if days >= 1:
        return f"now-{days}d"

    # 小时粒度（不足 1 天）
    hours = int((reference - start).total_seconds() // 3600)
    if 1 <= hours < 24:
        return f"now-{hours}h"

    return None


def _derive_shortcut_from_window(start_time: Any, end_time: Any) -> Optional[str]:
    """模型没给 time_shortcut，但给了绝对时间窗时，回推相对标记。"""

    start = _parse_filter_time(start_time)
    end = _parse_filter_time(end_time)
    if start is None or end is None:
        return None

    now = timezone.now()
    if abs((end - now).total_seconds()) > _END_TOLERANCE.total_seconds():
        return None

    span = _span_origin(start, now)
    if span is None:
        return None
    try:
        ConditionAssemblyService._normalize_time_shortcut(span)
    except InvalidConditionError:
        return None
    return span


def attach_datetime_origin(filter_conditions: Dict[str, Any]) -> Dict[str, Any]:

    shortcut = _accepted_time_shortcut(filter_conditions.pop("time_shortcut", None))
    if not shortcut:
        # 模型未直接给出 time_shortcut 时，尝试从「结束于 now 的绝对窗口」反推
        shortcut = _derive_shortcut_from_window(filter_conditions.get("start_time"), filter_conditions.get("end_time"))
    if shortcut:
        filter_conditions["datetime_origin"] = [shortcut, "now"]
    else:
        filter_conditions.pop("datetime_origin", None)
    return filter_conditions
