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

通用消息规划：用户目标、可信会话和授权边界 → MessagePlan。
动态系统/字段/操作元数据由专用MCP按需提供，后端独立校验授权范围与检索条件。
Agent路由由AI_USER_INTENT_AGENT_CODE及api.domains中的环境配置决定。
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from bk_resource import api, resource
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.template import Context, Template
from pydantic import ValidationError
from requests.exceptions import Timeout

from api.bk_plugins_ai_agent.exceptions import AgentRateLimited
from api.constants import AIAgentCode
from apps.meta.constants import SystemAuditStatusEnum
from apps.meta.permissions import SearchLogPermission
from services.web.ai.prompts.intent_recognition import (
    RETRY_PROMPT_TEMPLATE,
    SYSTEM_PROMPT_TEMPLATE,
    USER_PROMPT_TEMPLATE,
)
from services.web.query.ai_assistant.exceptions import (
    AIAssistantError,
    AIOutputInvalidError,
    AIServiceError,
    AITimeoutError,
    InvalidConditionError,
)
from services.web.query.ai_assistant.schemas import (
    MessagePlan,
    MessagePlanningClock,
    MessagePlanningContext,
    MessagePlanningConversation,
)
from services.web.query.ai_assistant.services.condition import ConditionAssemblyService

logger = logging.getLogger(__name__)

# AI 输出原文在日志/异常 extra 中的最大保留长度（对齐 NL2JSON）
INTENT_RAW_OUTPUT_KEEP_LENGTH = 2048


@dataclass(frozen=True, slots=True)
class PlanningRetryFeedback:
    """下一次 Agent 调用所需的上一轮输出和安全校验反馈。"""

    previous_output: str
    validation_errors: tuple[dict[str, str], ...]


def _compact_json(data: Any) -> str:
    """Prompt 注入用紧凑 JSON：无缩进、中文原样，体积最小且模型解析无差异。"""

    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _render_prompt(template: str, **variables: str) -> str:
    """关闭 HTML 转义后渲染提示词模板，保持 JSON 和用户原话不失真。"""

    return Template(template).render(Context(variables, autoescape=False)).strip()


def resolve_intent_agent_code() -> AIAgentCode:
    """按环境开关解析意图识别智能体（AIAgentCode 枚举名），非法值启动即快速失败。"""

    try:
        return AIAgentCode[settings.AI_USER_INTENT_AGENT_CODE]
    except KeyError:
        raise ImproperlyConfigured(
            f"AI_USER_INTENT_AGENT_CODE 非法: {settings.AI_USER_INTENT_AGENT_CODE}，"
            f"可选值: {[code.name for code in AIAgentCode]}"
        )


class MessagePlanningService:
    """通用消息规划：一次调用生成系统选择、日志检索或二者组合。"""

    agent_code = resolve_intent_agent_code()
    system_prompt = _render_prompt(
        SYSTEM_PROMPT_TEMPLATE,
        message_plan_schema=_compact_json(MessagePlan.model_json_schema()),
    )

    @staticmethod
    def load_candidates(namespace: str, username: str, scope_type: str = "", scope_id: str = "") -> list[dict]:
        """组装候选系统：当前场景授权范围 ∩ 已接入审计系统。

        传 scope_type 时与检索页场景过滤同源（SearchLogPermission.get_scope_auth_systems，
        即 ``_build_system_conditions`` 同一权限口径）：候选限定为该场景/scope 下授权的系统，
        意图识别无法路由到场景外系统；未传时沿用系统方向 ∪ 场景方向权限并集，
        两种入口最终都剔除尚未接入审计的系统。

        供 Celery 任务等无请求上下文场景使用（权限组件依赖请求上下文取用户名，
        此处走显式 username 的参数化版本）。
        """

        if scope_type:
            # get_scope_auth_systems 无权限时返回 [""]（ES filter 兜底语义），候选清单置空
            allowed_ids = set(SearchLogPermission.get_scope_auth_systems(scope_type, scope_id, username))
            allowed_ids.discard("")
            systems = resource.meta.system_list_all(
                namespace=namespace,
                audit_status__in=SystemAuditStatusEnum.ACCESSED.value,
            )
        else:
            systems, authorized_system_ids = SearchLogPermission.get_auth_systems_by_username(namespace, username)
            allowed_ids = set(authorized_system_ids)
        return [
            {
                "system_id": str(system["id"]),
                "name": str(system.get("name") or system["id"]),
                "description": str(system.get("description") or ""),
            }
            for system in systems
            if str(system["id"]) in allowed_ids
            and str(system.get("audit_status") or "") == SystemAuditStatusEnum.ACCESSED.value
        ]

    @classmethod
    def build_context(
        cls,
        *,
        query_text: str,
        candidates: list[dict],
        current_system_id: str,
        username: str,
        reference_time: datetime,
    ) -> MessagePlanningContext:
        """只构造可信决策事实，不预加载工具可查询的字段、样例或系统详情。"""
        current_week_start = reference_time.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
            days=reference_time.weekday()
        )
        return MessagePlanningContext(
            user_query=query_text,
            conversation=MessagePlanningConversation(
                username=username,
                phase="SYSTEM_SELECTED" if current_system_id else "SYSTEM_UNSELECTED",
                current_system_id=current_system_id,
            ),
            authorized_system_ids=list(dict.fromkeys(str(candidate["system_id"]) for candidate in candidates)),
            clock=MessagePlanningClock(
                current_time=reference_time.isoformat(),
                timezone=str(reference_time.tzinfo),
                default_start_time=(reference_time - timedelta(days=1)).isoformat(),
                current_week_start=current_week_start.isoformat(),
                previous_week_start=(current_week_start - timedelta(days=7)).isoformat(),
            ),
        )

    @classmethod
    def plan(
        cls,
        *,
        context: MessagePlanningContext,
        user_message: str | None = None,
        agent_user: str | None = None,
        retry_feedback: PlanningRetryFeedback | None = None,
    ) -> MessagePlan:
        """调用 Agent 并返回通过授权候选范围校验的消息计划。"""

        if user_message is None:
            user_message = cls.build_user_message(context)
        content = cls._call_agent(
            user_message,
            agent_user or context.conversation.username,
            retry_feedback=retry_feedback,
        )
        try:
            plan = cls._parse_and_validate(content)
            plan = cls._normalize_redundant_selection(plan, context.conversation.current_system_id)
            cls._validate_system_scope(plan, context)
        except AIAssistantError as error:
            # plan() 内部的范围校验发生在赋值返回前，调用方拿不到 plan；把原始输出
            # 固化到异常中，保证下一轮仍能看到需要修正的完整 MessagePlan。
            error.extra.setdefault("raw_output", content[:INTENT_RAW_OUTPUT_KEEP_LENGTH])
            error.retry_raw_output = content
            raise
        return plan

    @staticmethod
    def build_user_message(context: MessagePlanningContext) -> str:
        """序列化本轮目标、授权ID与时间，动态业务元数据仅通过专用MCP进入上下文。"""
        return _render_prompt(
            USER_PROMPT_TEMPLATE,
            user_query_json=_compact_json(context.user_query),
            conversation_json=_compact_json(context.conversation.model_dump(mode="json")),
            authorized_system_ids_json=_compact_json(context.authorized_system_ids),
            clock_json=_compact_json(context.clock.model_dump(mode="json")),
        )

    @classmethod
    def _call_agent(
        cls,
        user_message: str,
        username: str,
        *,
        retry_feedback: PlanningRetryFeedback | None = None,
    ) -> str:
        """调用通用 Agent 并统一映射基础设施异常。"""

        chat_history = [
            {"role": "role", "content": cls.system_prompt},
            {"role": "user", "content": user_message},
        ]
        if retry_feedback is not None:
            retry_message = _render_prompt(
                RETRY_PROMPT_TEMPLATE,
                validation_errors_json=json.dumps(
                    retry_feedback.validation_errors,
                    ensure_ascii=False,
                    indent=2,
                ),
            )
            chat_history.extend(
                [
                    {"role": "assistant", "content": retry_feedback.previous_output},
                    {"role": "user", "content": retry_message},
                ]
            )

        try:
            response = api.bk_plugins_ai_agent.chat_completion(
                agent_code=cls.agent_code,
                user=username,
                chat_history=chat_history,
                execute_kwargs={"stream": False, "thread_id": f"intent-planning-{uuid4().hex}"},
            )
        except Timeout as error:
            raise AITimeoutError(extra={"error": str(error)})
        except AgentRateLimited:
            raise
        except Exception as error:  # noqa: BLE001
            logger.exception("[MessagePlanningService] chat_completion failed")
            raise AIServiceError(extra={"error": str(error)})
        if not isinstance(response, str):
            raise AIOutputInvalidError(
                extra={
                    "raw_type": type(response).__name__,
                    "raw_output": str(response)[:INTENT_RAW_OUTPUT_KEEP_LENGTH],
                    "validation_errors": [
                        {
                            "path": "$",
                            "code": "invalid_response_type",
                            "message": "Agent response must be a JSON string",
                        }
                    ],
                },
            )
        return response

    @classmethod
    def _parse_and_validate(cls, content: str) -> MessagePlan:
        """提取 JSON 并按 MessagePlan 契约校验。"""

        raw_plan = ConditionAssemblyService.extract_json(content)
        if raw_plan is None:
            raise AIOutputInvalidError(
                retry_raw_output=content,
                extra={
                    "raw_output": content[:INTENT_RAW_OUTPUT_KEEP_LENGTH],
                    "validation_errors": [{"path": "$", "code": "invalid_json", "message": "输出必须是完整 JSON 对象"}],
                },
            )
        try:
            return MessagePlan.model_validate(raw_plan)
        except ValidationError as error:
            validation_errors = cls._normalize_validation_errors(error)
            exception_class = (
                InvalidConditionError
                if all(cls._is_condition_error(item["path"]) for item in validation_errors)
                else AIOutputInvalidError
            )
            raise exception_class(
                retry_raw_output=content,
                extra={
                    "raw_output": content[:INTENT_RAW_OUTPUT_KEEP_LENGTH],
                    "validation_error": str(error),
                    "validation_errors": validation_errors,
                },
            ) from error

    @staticmethod
    def _normalize_validation_errors(error: ValidationError) -> list[dict[str, str]]:
        """把 Pydantic 错误压缩为可安全回传给 Agent 的稳定结构。"""

        return [
            {
                "path": ".".join(str(part) for part in item["loc"]) or "$",
                "code": str(item["type"]),
                "message": str(item["msg"]),
            }
            for item in error.errors(include_input=False, include_url=False)
        ]

    @staticmethod
    def _is_condition_error(path: str) -> bool:
        """判断 MessagePlan 校验错误是否位于 LOG_SEARCH 条件载荷。"""

        parts = set(path.split("."))
        return "condition" in parts or "conditions" in parts

    @staticmethod
    def build_retry_feedback(
        *,
        error: AIAssistantError,
        plan: MessagePlan | None,
    ) -> PlanningRetryFeedback:
        """从本轮失败构造下一轮完整纠错上下文。"""

        previous_output = error.retry_raw_output or str(error.extra.get("raw_output") or "")
        if not previous_output and plan is not None:
            previous_output = plan.model_dump_json()
        validation_errors = error.extra.get("validation_errors")
        if not isinstance(validation_errors, list) or not validation_errors:
            validation_errors = [
                {
                    "path": "messages.LOG_SEARCH.message_input.condition",
                    "code": str(error.extra.get("reason") or error.error_code),
                    "message": str(error.message),
                }
            ]
        normalized = tuple(
            {
                "path": str(item.get("path") or "$"),
                "code": str(item.get("code") or error.error_code),
                "message": str(item.get("message") or error.message),
            }
            for item in validation_errors
        )
        return PlanningRetryFeedback(
            previous_output=previous_output or "{}",
            validation_errors=normalized,
        )

    @staticmethod
    def _normalize_redundant_selection(plan: MessagePlan, current_system_id: str) -> MessagePlan:
        """复合计划重复选择当前系统时，仅保留检索消息。"""

        if plan.outcome != "dispatch" or len(plan.messages) != 2 or not current_system_id:
            return plan
        selection, log_search = plan.messages
        if (
            selection.message_type == "SYSTEM_SELECTION"
            and log_search.message_type == "LOG_SEARCH"
            and selection.message_input.system_ids == [current_system_id]
        ):
            return MessagePlan(outcome="dispatch", messages=[log_search])
        return plan

    @staticmethod
    def _validate_system_scope(
        plan: MessagePlan,
        context: MessagePlanningContext,
    ) -> None:
        """拒绝候选外系统及缺失有效系统的检索计划。"""

        if plan.outcome == "error":
            return
        candidate_ids = set(context.authorized_system_ids)
        current_system_id = context.conversation.current_system_id
        selection = next(
            (message for message in plan.messages if message.message_type == "SYSTEM_SELECTION"),
            None,
        )
        if selection is not None:
            selected_system_id = selection.message_input.system_ids[0]
            if selected_system_id not in candidate_ids:
                raise AIOutputInvalidError(
                    extra={"system_id": selected_system_id, "reason": "system_id not in candidates"}
                )
            return
        if any(message.message_type == "LOG_SEARCH" for message in plan.messages):
            if not current_system_id or current_system_id not in candidate_ids:
                raise AIOutputInvalidError(
                    extra={"system_id": current_system_id, "reason": "current system not in candidates"}
                )
