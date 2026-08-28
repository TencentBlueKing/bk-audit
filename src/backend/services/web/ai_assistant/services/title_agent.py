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
AI 标题生成服务（共用智能体）。

与风险分析报告标题（risk/tasks.py generate_analyse_report_title）共用同一智能体
ALS_TITLE_SUM（System Prompt 平台侧统一配置，后端只发 User Message）；
User Prompt 走统一结构化模板（constants.AI_TITLE_USER_PROMPT_TEMPLATE），
新模块接入只需在 AI_TITLE_MODULE_CONFIGS 加一个条目。
"""

import logging
from typing import Any

from bk_resource import api
from django.conf import settings

from api.constants import AIAgentCode
from services.web.ai_assistant.constants import (
    AI_CONVERSATION_TITLE_MAX_LENGTH,
    AI_TITLE_MODULE_CONFIGS,
    AI_TITLE_USER_PROMPT_TEMPLATE,
)

logger = logging.getLogger(__name__)


class TitleAgentService:
    """共用智能体标题生成（当前服务 AI 日志检索会话标题）。"""

    @classmethod
    def generate_title(cls, *, module: str, input_text: str, username: str, max_length: int = None) -> str:
        """渲染统一模板 → 调共用智能体 → 清洗截断，返回标题文本（空串表示无可用标题）。

        :param module: AI_TITLE_MODULE_CONFIGS 中注册的模块标识
        :param input_text: 用户输入（已组装好的自然语言文本）
        :param username: 调用者（透传智能体鉴权与审计）
        :param max_length: 标题最大长度（缺省取会话标题配置）
        """

        module_config = AI_TITLE_MODULE_CONFIGS[module]
        max_length = max_length if max_length is not None else getattr(
            settings, "AI_CONVERSATION_TITLE_MAX_LENGTH", AI_CONVERSATION_TITLE_MAX_LENGTH
        )
        prompt = cls.render_user_prompt(module_config=module_config, input_text=input_text, max_length=max_length)
        result = api.bk_plugins_ai_agent.chat_completion(
            agent_code=AIAgentCode.ALS_TITLE_SUM,
            user=username,
            input=prompt,
            chat_history=[],
            execute_kwargs={"stream": False},
        )
        return cls.normalize_title(result, max_length)

    @staticmethod
    def render_user_prompt(*, module_config: dict, input_text: str, max_length: int) -> str:
        """按统一三段式模板（场景/任务/输入）渲染 User Message。"""

        template = getattr(settings, "AI_TITLE_USER_PROMPT_TEMPLATE", "") or AI_TITLE_USER_PROMPT_TEMPLATE
        return template.format(
            module_name=module_config["module_name"],
            module_description=module_config["module_description"],
            module_object=module_config["module_object"],
            max_length=max_length,
            input_text=input_text,
        )

    @staticmethod
    def normalize_title(raw_title: Any, max_length: int) -> str:
        """清洗智能体返回：去 markdown 代码块/引号/空白折叠/截断（规则与 risk 标题清洗一致）。"""

        title = str(raw_title or "").strip()
        title = title.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        title = title.strip("\"'“”‘’")
        title = " ".join(title.split())
        title = title[:max_length]
        return title
