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


# 月快捷项与日期组件一致，其余天数走 now-{N}d
_MONTH_ORIGIN_BY_DAYS = {30: "now-1M", 90: "now-3M", 182: "now-6M", 365: "now-12M"}
_END_TOLERANCE = timedelta(hours=2)
_ALIGN_TOLERANCE = timedelta(minutes=10)


def _parse_filter_time(value: Any) -> Optional[datetime]:
    if not value:
        return None
    parsed = parse_datetime(str(value))
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _day_origin(days: int) -> str:
    return _MONTH_ORIGIN_BY_DAYS.get(days, f"now-{days}d")


def _relative_shortcut(start: datetime, reference: datetime) -> Optional[str]:
    """结束于当前时间的窗口 → now-{N}h / now-{N}d / now-{N}M。对不上返回 None。"""

    delta = reference - start
    if delta <= timedelta(0):
        return None

    same_clock = (
        abs(
            timedelta(hours=start.hour, minutes=start.minute, seconds=start.second)
            - timedelta(hours=reference.hour, minutes=reference.minute, seconds=reference.second)
        )
        <= _ALIGN_TOLERANCE
    )
    midnight = start.hour == start.minute == start.second == 0
    days = (reference.date() - start.date()).days
    if days >= 1 and (midnight or same_clock):
        return _day_origin(days)

    hours = round(delta.total_seconds() / 3600)
    if hours >= 1 and abs(delta - timedelta(hours=hours)) <= _ALIGN_TOLERANCE:
        if hours % 24 == 0:
            return _day_origin(hours // 24)
        return f"now-{hours}h"
    return None


def attach_datetime_origin(
    filter_conditions: Dict[str, Any], reference_time: Optional[datetime] = None
) -> Dict[str, Any]:
    """补 datetime_origin。相对到当前时间用 ['now-{N}{unit}', 'now']，其他时间用绝对起止。"""

    raw_start = filter_conditions.get("start_time")
    raw_end = filter_conditions.get("end_time")
    start = _parse_filter_time(raw_start)
    end = _parse_filter_time(raw_end)
    if start is None or end is None:
        filter_conditions.pop("datetime_origin", None)
        return filter_conditions

    tz = timezone.get_current_timezone()
    if reference_time is None:
        reference_time = timezone.localtime(timezone.now())
    start = start.astimezone(tz).replace(microsecond=0)
    end = end.astimezone(tz).replace(microsecond=0)
    reference = reference_time.astimezone(tz).replace(microsecond=0)
    if abs(end - reference) <= _END_TOLERANCE:
        shortcut = _relative_shortcut(start, reference)
        if shortcut:
            filter_conditions["datetime_origin"] = [shortcut, "now"]
            return filter_conditions

    filter_conditions["datetime_origin"] = [str(raw_start), str(raw_end)]
    return filter_conditions
