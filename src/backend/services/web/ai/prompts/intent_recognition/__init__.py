# -*- coding: utf-8 -*-
"""意图识别 Agent 提示词模板的稳定导出入口。"""

from services.web.ai.prompts.intent_recognition.templates import (
    RETRY_PROMPT_TEMPLATE,
    SYSTEM_PROMPT_TEMPLATE,
    USER_PROMPT_TEMPLATE,
)

__all__ = ["RETRY_PROMPT_TEMPLATE", "SYSTEM_PROMPT_TEMPLATE", "USER_PROMPT_TEMPLATE"]
