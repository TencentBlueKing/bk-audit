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

通用消息规划服务：自然语言 + 会话/权限/字段上下文 → MessagePlan。

意图识别默认调用专属智能体（AIAgentCode.USER_INTENT = bp-ai-user-intent；
2026-09-15 统一切换新智能体，旧网关 bp-audit-log-search / bp-ai-nlls 退役）。
环境地址差异由 get_agent_base_url 优先级链解决：
- 生产（上云）：BK_API_URL_TMPL 独立域名模板默认链路直接跑通（零额外配置）
- bkop：统一域名模板下该网关未注册（404），配置 BKAPP_AI_USER_INTENT_API_URL
  直连独立域名（第 1 层优先级）
settings.AI_USER_INTENT_AGENT_CODE 可按环境覆盖路由到其他智能体（应急等）。

新链路以 MessagePlan 为 single source of truth，一次生成 SYSTEM_SELECTION、LOG_SEARCH
或二者组合；候选系统和完整字段上下文按前端 scope 收窄。
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import islice
from typing import Any
from uuid import uuid4

from bk_resource import api, resource
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.template import Context, Template
from pydantic import ValidationError
from requests.exceptions import Timeout

from api.constants import AIAgentCode
from apps.meta.constants import SystemAuditStatusEnum
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
    MessagePlanningSystemSummary,
    SelectionFieldMeta,
    SelectionSystem,
)
from services.web.query.ai_assistant.services.condition import ConditionAssemblyService

logger = logging.getLogger(__name__)

# AI 输出原文在日志/异常 extra 中的最大保留长度（对齐 NL2JSON）
INTENT_RAW_OUTPUT_KEEP_LENGTH = 2048

PLANNING_SYSTEM_DESCRIPTION_MAX_LENGTH = 256
PLANNING_SAMPLE_STRING_MAX_LENGTH = 128
PLANNING_SAMPLE_MAX_DEPTH = 2
PLANNING_SAMPLE_COLLECTION_MAX_ITEMS = 20


@dataclass(frozen=True, slots=True)
class PlanningRetryFeedback:
    """下一次 Agent 调用所需的上一轮输出和安全校验反馈。"""

    previous_output: str
    validation_errors: tuple[dict[str, str], ...]


def _sample_type(value: Any) -> str:
    """返回上下文元数据使用的稳定样例类型名。"""

    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    return type(value).__name__


def _summarize_sample_value(value: Any, *, depth: int = 0) -> tuple[Any, bool]:
    """对字段样例执行确定性裁剪，返回裁剪后的值与是否发生裁剪。

    设计意图：保留原始查询值形态供模型参考，同时防止大字符串或深层 JSON
    无界增长 Prompt。深度超限时使用带统计信息的占位对象，不让模型误以为原值完整。
    """

    if isinstance(value, str):
        if len(value) <= PLANNING_SAMPLE_STRING_MAX_LENGTH:
            return value, False
        return value[:PLANNING_SAMPLE_STRING_MAX_LENGTH], True
    if isinstance(value, dict):
        if depth >= PLANNING_SAMPLE_MAX_DEPTH:
            return {
                "truncated": True,
                "original_type": "object",
                "item_count": len(value),
            }, True
        summarized = {}
        truncated = len(value) > PLANNING_SAMPLE_COLLECTION_MAX_ITEMS
        for key, item in islice(value.items(), PLANNING_SAMPLE_COLLECTION_MAX_ITEMS):
            summarized_item, item_truncated = _summarize_sample_value(item, depth=depth + 1)
            summarized[str(key)] = summarized_item
            truncated = truncated or item_truncated
        if len(value) > PLANNING_SAMPLE_COLLECTION_MAX_ITEMS:
            summarized["__truncation__"] = {
                "truncated": True,
                "original_type": "object",
                "item_count": len(value),
                "retained_item_count": PLANNING_SAMPLE_COLLECTION_MAX_ITEMS,
            }
        return summarized, truncated
    if isinstance(value, list):
        if depth >= PLANNING_SAMPLE_MAX_DEPTH:
            return {
                "truncated": True,
                "original_type": "array",
                "item_count": len(value),
            }, True
        summarized_items = []
        truncated = len(value) > PLANNING_SAMPLE_COLLECTION_MAX_ITEMS
        for item in value[:PLANNING_SAMPLE_COLLECTION_MAX_ITEMS]:
            summarized_item, item_truncated = _summarize_sample_value(item, depth=depth + 1)
            summarized_items.append(summarized_item)
            truncated = truncated or item_truncated
        if len(value) > PLANNING_SAMPLE_COLLECTION_MAX_ITEMS:
            summarized_items.append(
                {
                    "truncated": True,
                    "original_type": "array",
                    "item_count": len(value),
                    "retained_item_count": PLANNING_SAMPLE_COLLECTION_MAX_ITEMS,
                }
            )
        return summarized_items, truncated
    return value, False


def _serialize_planning_field(field) -> dict:
    """序列化 Agent 可见字段，排除展示值并限制样例体积。"""

    payload = field.model_dump(exclude_none=True, exclude={"sample_value_display"})
    if "sample_value" not in payload:
        return payload
    original = payload["sample_value"]
    summarized, truncated = _summarize_sample_value(original)
    payload["sample_value"] = summarized
    if truncated:
        metadata = {"truncated": True, "original_type": _sample_type(original)}
        if isinstance(original, str):
            metadata["original_length"] = len(original)
        elif isinstance(original, (dict, list)):
            metadata["item_count"] = len(original)
        payload["sample_value_meta"] = metadata
    return payload


def _field_definition(field: SelectionFieldMeta) -> dict:
    """返回不含样例的 Agent 字段定义，用于公共字段与系统差异比较。"""

    return {
        key: value
        for key, value in _serialize_planning_field(field).items()
        if key not in {"sample_value", "sample_value_meta"}
    }


def _serialize_current_system_detail(
    current_system: SelectionSystem | None,
    common_fields: list[SelectionFieldMeta],
) -> dict | None:
    """只表达当前系统相对公共字段的差异，以及路径探索需要的拓展字段样例。"""

    if current_system is None:
        return None
    common_definitions = {field.raw_name: _field_definition(field) for field in common_fields}
    field_overrides = []
    for field in current_system.standard_fields:
        definition = _field_definition(field)
        if common_definitions.get(field.raw_name) != definition:
            field_overrides.append(definition)
    return {
        "system_id": current_system.system_id,
        "name": current_system.name,
        "description": current_system.description[:PLANNING_SYSTEM_DESCRIPTION_MAX_LENGTH],
        "field_overrides": field_overrides,
        "extension_fields": [_serialize_planning_field(field) for field in current_system.extension_fields],
    }


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
        message_plan_schema=json.dumps(MessagePlan.model_json_schema(), ensure_ascii=False, indent=2),
    )

    _PHASE_DECISION_RULES = {
        "SYSTEM_UNSELECTED": "当前会话没有有效系统；用户未提供可匹配系统时返回 SYSTEM_REQUIRED",
        "SYSTEM_SELECTED": "用户未点名其他系统的检索默认使用 current_system_id",
    }

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

        from apps.meta.permissions import SearchLogPermission

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
        common_fields: list[SelectionFieldMeta],
        current_system: SelectionSystem | None,
        username: str,
        reference_time: datetime,
    ) -> MessagePlanningContext:
        """由后端可信事实构造强类型的单次规划上下文。"""

        current_system_id = current_system.system_id if current_system is not None else ""
        phase = "SYSTEM_SELECTED" if current_system_id else "SYSTEM_UNSELECTED"
        current_week_start = reference_time.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
            days=reference_time.weekday()
        )
        return MessagePlanningContext(
            user_query=query_text,
            conversation=MessagePlanningConversation(
                username=username,
                phase=phase,
                phase_decision_rule=cls._PHASE_DECISION_RULES[phase],
                has_selected_system=bool(current_system_id),
                current_system_id=current_system_id,
            ),
            authorized_systems=[
                MessagePlanningSystemSummary(
                    system_id=str(candidate["system_id"]),
                    name=str(candidate.get("name") or candidate["system_id"]),
                    description=str(candidate.get("description") or "")[:PLANNING_SYSTEM_DESCRIPTION_MAX_LENGTH],
                )
                for candidate in candidates
            ],
            common_standard_fields=common_fields,
            current_system_detail=current_system,
            clock=MessagePlanningClock(
                current_time=reference_time.isoformat(),
                timezone=str(reference_time.tzinfo),
                default_start_time=(reference_time - timedelta(days=1)).isoformat(),
                current_week_start=current_week_start.isoformat(),
                previous_week_start=(current_week_start - timedelta(days=7)).isoformat(),
                previous_week_end=current_week_start.isoformat(),
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
        """按固定层级序列化本轮动态事实，不重复稳定规则和输出契约。"""

        common_fields = [_field_definition(field) for field in context.common_standard_fields]
        current_system_detail = _serialize_current_system_detail(
            context.current_system_detail,
            context.common_standard_fields,
        )
        return _render_prompt(
            USER_PROMPT_TEMPLATE,
            user_query=context.user_query,
            conversation_json=json.dumps(context.conversation.model_dump(mode="json"), ensure_ascii=False, indent=2),
            authorized_systems_json=json.dumps(
                [item.model_dump(mode="json") for item in context.authorized_systems],
                ensure_ascii=False,
                indent=2,
            ),
            common_standard_fields_json=json.dumps(common_fields, ensure_ascii=False, indent=2),
            current_system_detail_json=json.dumps(current_system_detail, ensure_ascii=False, indent=2),
            clock_json=json.dumps(context.clock.model_dump(mode="json"), ensure_ascii=False, indent=2),
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
        candidate_ids = {system.system_id for system in context.authorized_systems}
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
