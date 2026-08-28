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

"""
AI 会话标题生成服务（一期：完全复刻 risk generate_analyse_report_title 的调用方式）。

与风险分析报告标题共用同一智能体 ALS_TITLE_SUM（System Prompt 平台侧统一配置）；
User Message 为单行 label 前缀格式（与 risk 的「用户自定义分析描述: "..."」同构，
label 区分模块），清洗规则与 risk _normalize_analyse_report_ai_title 一致。
"""

import logging
from typing import Any

from bk_resource import api

from api.constants import AIAgentCode

logger = logging.getLogger(__name__)

# 统一 User Prompt 格式：单行 label 前缀 + 引号包裹输入（与 risk 报告标题同构）
AI_TITLE_INPUT_TEMPLATE = '用户自然语言检索描述: "{input_text}"'


class TitleAgentService:
    """共用智能体标题生成（复刻 risk 调用方式，服务 AI 日志检索会话标题）。"""

    @classmethod
    def generate_title(cls, *, input_text: str, username: str, max_length: int) -> str:
        """拼 input → 调共用智能体 → 清洗截断，返回标题文本（空串表示无可用标题）。"""

        prompt = AI_TITLE_INPUT_TEMPLATE.format(input_text=input_text)
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
