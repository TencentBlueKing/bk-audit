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
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

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

时间约定：相对时间（近、最近、N小时内、N天内、一个月内等）额外输出 time_shortcut，格式 now-{{正整数}}{{单位}}（h小时、d天、M月）。
月仅支持 1/3/6/12，窗口最多 365 天。例如近一周 → now-7d，最近3个月 → now-3M，近5小时 → now-5h。
明确日期、上周不要输出 time_shortcut。start_time、end_time 仍按原规则输出。


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


# 与下游 ConditionAssemblyService 校验器（services/web/query/ai_assistant/services/condition.py）
# 及前端 DATETIME_SHORTCUT_LABEL_MAP 白名单对齐：仅支持 h/d/M，月仅 1/3/6/12，窗口 ≤ 365 天。
_TIME_SHORTCUT_PATTERN = re.compile(r"^now-([1-9]\d*)([hdM])$")
_MONTH_SHORTCUT_DAYS = {1: 30, 3: 90, 6: 182, 12: 365}
_TIME_SHORTCUT_MAX_WINDOW_DAYS = 365


def _accepted_time_shortcut(value: Any) -> Optional[str]:
    """校验 NL 模型输出的 time_shortcut 形态与上限，不合法时返回 None 降级。

    直接对模型原始输出做形态校验，避免把未校验字符串传给依赖 Pydantic 前置校验的
    ConditionAssemblyService._normalize_time_shortcut（其会对不匹配输入抛 AttributeError）。
    单位/月数与下游校验器对齐（h/d/M，月仅 1/3/6/12，窗口 ≤ 365 天）；不合法
    （形态不符、月数非白名单、超 365 天，如 now-2M/now-30m/now-13M/today/空串）时
    返回 None，调用方据此保留绝对时间，不让自然语言筛选接口抛出未捕获异常。
    """

    if not isinstance(value, str):
        return None
    match = _TIME_SHORTCUT_PATTERN.match(value)
    if not match:
        return None
    count, unit = match.groups()
    count = int(count)
    if unit == "M":
        if count not in _MONTH_SHORTCUT_DAYS:
            return None
        window_days = _MONTH_SHORTCUT_DAYS[count]
    elif unit == "h":
        window_days = count / 24
    else:  # d
        window_days = count
    if window_days > _TIME_SHORTCUT_MAX_WINDOW_DAYS:
        return None
    return value


def attach_datetime_origin(filter_conditions: Dict[str, Any]) -> Dict[str, Any]:
    """模型给出合法 time_shortcut 时写成 datetime_origin，否则不返回该字段。"""

    shortcut = _accepted_time_shortcut(filter_conditions.pop("time_shortcut", None))
    if shortcut:
        filter_conditions["datetime_origin"] = [shortcut, "now"]
    else:
        filter_conditions.pop("datetime_origin", None)
    return filter_conditions
