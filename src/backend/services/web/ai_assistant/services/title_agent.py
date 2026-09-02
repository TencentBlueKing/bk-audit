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

# AI 会话标题生成服务（一期：完全复刻 risk generate_analyse_report_title 的调用方式）。
#
# 与风险分析报告标题共用同一智能体 ALS_TITLE_SUM（System Prompt 平台侧统一配置）；
# User Message 为单行 label 前缀格式（与 risk 的「用户自定义分析描述: "..."」同构，
# label 区分模块），清洗规则与 risk _normalize_analyse_report_ai_title 一致。

import logging
from typing import Any, Mapping, Sequence

from bk_resource import api

from api.constants import AIAgentCode
from services.web.query.utils.field import LOG_SEARCH_ALL_FIELDS_MAP

logger = logging.getLogger(__name__)

# 统一 User Prompt 格式：单行 label 前缀 + 引号包裹输入（与 risk 报告标题同构）
AI_TITLE_INPUT_TEMPLATE = '用户自然语言检索描述: "{input_text}"'
# 条件检索（非自然语言）来源的标题素材：label 区分来源，仍保持单行 label 前缀格式
AI_TITLE_CONDITION_INPUT_TEMPLATE = '用户条件检索描述: "{input_text}"'

# 条件检索标题素材：操作符中文描述（Operator 元数据为 SQL 符号，标题素材用中文更利于智能体概括；
# 覆盖 core.sql.constants.Operator 全部取值，未知操作符回退原文）
CONDITION_OPERATOR_LABELS = {
    "eq": "等于",
    "neq": "不等于",
    "gt": "大于",
    "lt": "小于",
    "gte": "大于等于",
    "lte": "小于等于",
    "include": "包含",
    "exclude": "不包含",
    "like": "模糊匹配",
    "not_like": "排除模糊匹配",
    "isnull": "为空",
    "notnull": "不为空",
    "match_all": "全部包含",
    "match_any": "任一包含",
    "json_contains": "JSON包含",
    "between": "介于",
}
# 标题素材长度上限（防止超长条件撑爆 Prompt）
CONDITION_TITLE_INPUT_MAX_LENGTH = 200


def build_condition_title_input(
    input_data: Mapping[str, Any],
    extension_fields: Sequence[Mapping[str, Any]] | None = None,
    max_length: int = CONDITION_TITLE_INPUT_MAX_LENGTH,
) -> str:
    """把条件检索消息的 input_data.condition 快照拼为单行中文摘要（标题生成素材）。

    摘要 = 系统 + 时间范围 + 逐条件「字段 操作符 值」，字段名动态适配：
    - 标准/系统/快照字段：中文名取 LOG_SEARCH_ALL_FIELDS_MAP 的 Field.description，
      与条件筛选回传前端的字段描述同源（field_context 构建逻辑一致），新增字段自动适配；
    - 拓展子键：展示名取父消息系统选择快照的 extension_fields[].display_name，
      缺元数据回退子键名；操作符中文见 CONDITION_OPERATOR_LABELS；
    - 未知字段/操作符回退原文；空条件仅保留系统与时间；整体截断到 max_length。
    """

    condition = (input_data or {}).get("condition") or {}
    # 拓展子键 → 展示名（一期下钻协议限单层，仅取第一层子键）
    extension_display_names: dict[str, str] = {}
    for field in extension_fields or []:
        if not isinstance(field, Mapping) or field.get("raw_name") != "extend_data":
            continue
        field_keys = field.get("keys") or []
        key = field_keys[0] if field_keys else ""
        if isinstance(key, str) and key:
            extension_display_names[key] = str(field.get("display_name") or key)
    parts: list[str] = []
    if condition.get("scope_id"):
        parts.append(f"系统 {condition['scope_id']}")
    start_time, end_time = condition.get("start_time"), condition.get("end_time")
    if start_time and end_time:
        parts.append(f"时间 {start_time} 至 {end_time}")
    for cond in condition.get("conditions") or []:
        field_meta = (cond or {}).get("field") or {}
        raw_name = field_meta.get("raw_name") or ""
        if not raw_name:
            continue
        field_keys = field_meta.get("keys") or []
        if raw_name == "extend_data" and field_keys:
            # 拓展子键条件：展示名来自父消息快照，缺元数据回退子键名
            field_label = extension_display_names.get(field_keys[0], field_keys[0])
        else:
            # 标准/系统/快照字段：与条件筛选回传前端的字段描述同源
            meta = LOG_SEARCH_ALL_FIELDS_MAP.get(raw_name)
            field_label = str(meta.description) if meta is not None else raw_name
        operator = (cond or {}).get("operator") or ""
        operator_label = CONDITION_OPERATOR_LABELS.get(operator, operator)
        filters = ",".join(str(value) for value in (cond or {}).get("filters") or [] if value not in (None, ""))
        if filters:
            parts.append(f"{field_label} {operator_label} {filters}")
    return "，".join(parts)[:max_length]


class TitleAgentService:
    """共用智能体标题生成（复刻 risk 调用方式，服务 AI 日志检索会话标题）。"""

    @classmethod
    def generate_title(
        cls, *, input_text: str, username: str, max_length: int, source: str = "natural_language"
    ) -> str:
        """拼 input → 调共用智能体 → 清洗截断，返回标题文本（空串表示无可用标题）。

        :param source: 素材来源（natural_language=自然语言原文 / field_condition=条件摘要），
            决定 User Message 的 label 前缀，格式仍为与 risk 同构的单行 label。
        """

        template = AI_TITLE_CONDITION_INPUT_TEMPLATE if source == "field_condition" else AI_TITLE_INPUT_TEMPLATE
        prompt = template.format(input_text=input_text)
        result = api.bk_plugins_ai_agent.chat_completion(
            agent_code=AIAgentCode.ALS_TITLE_SUM,
            user=username,
            input=prompt,
            chat_history=[],
            execute_kwargs={"stream": False},
        )
        return cls.normalize_title(result, max_length)

    @staticmethod
    def normalize_title(raw_title: Any, max_length: int) -> str:
        """清洗智能体返回：去 markdown 代码块/引号/空白折叠/截断（规则与 risk 标题清洗一致）。

        适配 bk_resource chat_completion 返回 RequestContext 的场景（payload 字段为响应字符串化的内容）：
        - payload 内含 error_code（非 0 / 存在 error 字段）→ 退回空串（上层判空跳过）
        - 正常响应 → 走原有清洗截断
        - 任何非预期输入 → 退回空串，绝不污染标题
        """

        # 1) RequestContext → payload 字符串
        if not isinstance(raw_title, str):
            payload = getattr(raw_title, "payload", None) or ""
            candidate = str(payload).strip()
        else:
            candidate = raw_title.strip()

        # 2) payload 形如 Python repr 的 tuple/list 字符串，解析后取首项内容
        #    典型形态：'[{"error_code": 1, "message": "bad request", "data": {}}, {...}]'
        extracted = candidate
        if candidate.startswith(("[", "(")):
            import ast

            try:
                parsed = ast.literal_eval(candidate)
            except (ValueError, SyntaxError):
                # 解析失败（payload 形态异常 / 含错误信息等）→ 空串，绝不污染标题
                return ""
            if not isinstance(parsed, (list, tuple)) or not parsed:
                return ""
            first = parsed[0]
            if isinstance(first, dict):
                if first.get("error_code") or "error" in first:
                    # 错误响应：直接空串让上层跳过
                    return ""
                # 正常响应：取 content / message / data / text 等字符串字段
                for key in ("content", "message", "data", "text"):
                    value = first.get(key)
                    if isinstance(value, str) and value:
                        extracted = value
                        break
                    if isinstance(value, dict):
                        for sub_key in ("content", "message", "text"):
                            sub = value.get(sub_key)
                            if isinstance(sub, str) and sub:
                                extracted = sub
                                break
                        if extracted != first:
                            break
                else:
                    # 没找到已知字段，整个 dict 序列化兜底
                    extracted = str(first)
            else:
                extracted = str(first)

        title = str(extracted or "").strip()
        title = title.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        title = title.strip("\"'“”‘’")
        title = " ".join(title.split())
        title = title[:max_length]
        return title
