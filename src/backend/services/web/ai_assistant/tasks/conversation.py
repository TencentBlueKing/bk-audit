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

# 会话侧异步任务：根据检索输入生成会话标题（共用智能体 ALS_TITLE_SUM）。

import logging

from blueapps.core.celery import celery_app
from django.conf import settings
from django.utils import timezone

from services.web.ai_assistant.constants import AI_CONVERSATION_TITLE_MAX_LENGTH
from services.web.ai_assistant.models import Conversation
from services.web.ai_assistant.serializers.conversation import (
    DEFAULT_CONVERSATION_TITLE,
)

logger = logging.getLogger(__name__)


@celery_app.task()
def generate_conversation_title(conversation_id: int, query_text: str, source: str = "natural_language") -> dict:
    """根据检索输入生成会话标题（失败静默降级，标题非关键路径）。

    触发来源与 NL 消息成功链路对齐：自然语言消息（query_text=原文）或
    条件检索消息（query_text=条件中文摘要，source=field_condition）。
    仅当会话标题仍为默认值时写入（首条检索消息生成一次）；
    原子条件写保证用户手动改名永远优先。
    """

    try:
        conversation = Conversation.objects.get(id=conversation_id, title=DEFAULT_CONVERSATION_TITLE)
    except Conversation.DoesNotExist:
        # 会话不存在 / 用户已改名 / 已生成过 → 跳过
        return {"conversation_id": conversation_id, "skipped": True}

    try:
        # 延迟导入：避免 tasks → services 半初始化状态触发循环 import（PR #1716 实踩）
        from services.web.ai_assistant.services.title_agent import TitleAgentService

        title = TitleAgentService.generate_title(
            input_text=query_text or "",
            username=conversation.created_by,
            max_length=getattr(settings, "AI_CONVERSATION_TITLE_MAX_LENGTH", AI_CONVERSATION_TITLE_MAX_LENGTH),
            source=source,
        )
    except Exception:
        logger.exception("[generate_conversation_title] ai agent failed, conversation_id=%s", conversation_id)
        return {"conversation_id": conversation_id, "skipped": True}

    if not title:
        logger.warning("[generate_conversation_title] empty title from agent, conversation_id=%s", conversation_id)
        return {"conversation_id": conversation_id, "skipped": True}

    updated = Conversation.objects.filter(id=conversation_id, title=DEFAULT_CONVERSATION_TITLE).update(
        title=title, updated_at=timezone.now()
    )
    if not updated:
        # 生成期间用户已手动改名 → 不覆盖
        return {"conversation_id": conversation_id, "skipped": True}
    return {"conversation_id": conversation_id, "title": title}
