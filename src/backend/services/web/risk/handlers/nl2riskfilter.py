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
from datetime import datetime
from typing import Any, List, Optional, Tuple

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
