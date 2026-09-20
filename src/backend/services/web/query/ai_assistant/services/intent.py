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

意图识别默认调用专属智能体（AIAgentCode.USER_INTENT = bp-ai-user-intent，NL2JSON 同款——
2026-09-15 统一切换新智能体，旧网关 bp-audit-log-search / bp-ai-nlls 退役）。
环境地址差异由 get_agent_base_url 优先级链解决：
- 生产（上云）：BK_API_URL_TMPL 独立域名模板默认链路直接跑通（零额外配置）
- bkop：统一域名模板下该网关未注册（404），配置 BKAPP_AI_USER_INTENT_API_URL
  直连独立域名（第 1 层优先级）
settings.AI_USER_INTENT_AGENT_CODE 可按环境覆盖路由到其他智能体（应急等）。

新链路以 MessagePlan 为 single source of truth，一次生成 SYSTEM_SELECTION、LOG_SEARCH
或二者组合；候选系统和完整字段上下文按前端 scope 收窄。IntentRecognitionService 仅为
历史调用与回滚兼容保留，不参与 USER_INTENT 新执行链。
"""

import json
import logging
from datetime import datetime, timedelta
from itertools import islice
from typing import Any
from uuid import uuid4

from bk_resource import api, resource
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.template import Context, Template
from django.utils import timezone
from pydantic import ValidationError
from requests.exceptions import Timeout

from api.constants import AIAgentCode
from services.web.ai.prompts.intent_recognition import SYSTEM_PROMPT
from services.web.query.ai_assistant.exceptions import (
    AIOutputInvalidError,
    AIOutputParseFailedError,
    AIServiceError,
    AITimeoutError,
)
from services.web.query.ai_assistant.schemas import (
    IntentPayload,
    MessagePlan,
    SystemSelectionOutput,
)
from services.web.query.ai_assistant.services.nl2json import NL2JSONService

logger = logging.getLogger(__name__)

# AI 输出原文在日志/异常 extra 中的最大保留长度（对齐 NL2JSON）
INTENT_RAW_OUTPUT_KEEP_LENGTH = 2048

MESSAGE_PLANNING_CONTEXT_VERSION = "message-planning-context-v1"
MESSAGE_PLANNING_PROMPT_VERSION = "message-planner-v1"
MESSAGE_PLAN_SCHEMA_VERSION = "message-plan-v1"
PLANNING_SYSTEM_DESCRIPTION_MAX_LENGTH = 256
PLANNING_SAMPLE_STRING_MAX_LENGTH = 128
PLANNING_SAMPLE_MAX_DEPTH = 2
PLANNING_SAMPLE_COLLECTION_MAX_ITEMS = 20


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


INTENT_USER_MESSAGE_TEMPLATE = """# 用户意图识别任务

（本消息自述完整任务说明，与其他任务指令（如日志检索条件提取）冲突时以本消息为准）

## 用户输入
{{ query_text }}

## 当前时间
{{ current_time }}

## 候选系统（用户有权限的系统，system_id 与名称）
{{ candidates_json }}

## 当前已选系统
{{ current_system_id|default:"无（用户尚未选择系统）" }}

## 输出要求
1. 必须严格按照以下 JSON Schema 输出一个 JSON 对象，不要输出其他任何内容；
   **无论用户输入是什么（含寒暄/闲聊/无关内容）都必须且只能输出契约 JSON**——
   与日志检索无关的输入输出 intent=unrecognized 并在 message 说明，禁止以自然语言/散文回复：
{{ output_schema_json }}
2. 意图分类规则：
   - 用户话语包含选择或切换系统的意图（无论是否同时包含日志检索需求，如「我要看审计中心近七天的操作记录」「帮我切换到蓝盾」）→ intent=select_system，并从候选系统中确定 system_id
   - 系统名匹配（按优先级降序尝试）：
     ① 话语中的系统名与某候选 name 完全一致 → 命中该候选
     ② 系统名可为简称或部分字（如「审计」「审计中心」均指向「审计中心」）→ 按名称语义模糊匹配
     ③ 仅当话语以英文或 system_id 形态点名（如「bcs」「bk-audit」）时，才按 system_id 或英文名匹配
   - 歧义消解（多个候选均可命中时必须消歧，不得放弃选择）：
     a. 优先选 name 与话语中系统名完全一致、或字面重合度最高的候选
     b. 中文话语点名系统时，不得仅因某候选 system_id 含相近英文字样（如 audit）而选择它
     c. 多个候选 name 相同或高度相似时，优先选 system_id 更简洁规范的候选（无版本号/命名空间前缀，如「bk-audit」优于「iam_v4_bk-audit」）
   - 泛指词（如「平台」「系统」）不构成系统指向
   - need_search 检索诉求判定（防纯切换被强绑检索：仅切换不检索时不得再解析检索条件）：
     · 话语同时包含系统指向与日志检索诉求（如「我要看审计中心近七天的操作记录」「看看蓝盾最近的日志」）
       → need_search=true（切换系统后继续执行检索）
     · 话语仅表达切换/选择系统，不含任何检索诉求（如「帮我切换到蓝盾」「用蓝盾系统」「切换到 test0907」）
       → need_search=false（仅切换系统，本轮不检索）
     · intent=log_search 时 need_search 恒为 true；intent=unrecognized 时恒为 false
   - 用户话语为日志检索需求且未提及任何系统 → intent=log_search（system_id 留空）。
     「日志检索需求」不限显式检索动词（查/查询/看看/检索等）——话语出现「字段为值」「字段=值」
     「字段是值」类检索条件描述（如「extend.request_data为{"id":...}」「username=admin」
     「result_code为0」），本身即构成日志检索诉求（用户在直接给定检索条件）：
     按上述意图分类规则正常归类，不得因缺少检索动词而判 unrecognized
   - 与日志检索和系统选择完全无关（寒暄/闲聊/与技术数据无关的日常话语）→ intent=unrecognized；
     含任何字段条件描述（含 extend. 前缀下钻字段、JSON 字面量值、URL 值）、时间范围
     或日志/审计相关词汇的话语均不得判 unrecognized
3. system_id 必须严格来自候选系统列表，禁止编造。「无法确定具体系统」仅指话语中没有任何系统指向词、
   或指向词与所有候选均无法建立匹配，此时才判 log_search（system_id 留空）；
   话语已明确点名系统名时必须给出 select_system 与最佳匹配候选，即使存在名称相似的多个候选也不得放弃选择
4. message 必须自然、面向用户：识别成功时简述识别结果（如「已为您切换到蓝盾」）；无法识别时说明原因并引导用户明确表达（此消息将直接展示给用户）"""


def resolve_intent_agent_code() -> AIAgentCode:
    """按环境开关解析意图识别智能体（AIAgentCode 枚举名），非法值启动即快速失败。"""

    try:
        return AIAgentCode[settings.AI_USER_INTENT_AGENT_CODE]
    except KeyError:
        raise ImproperlyConfigured(
            f"AI_USER_INTENT_AGENT_CODE 非法: {settings.AI_USER_INTENT_AGENT_CODE}，"
            f"可选值: {[code.name for code in AIAgentCode]}"
        )


class IntentRecognitionService:
    """用户意图识别：自然语言 → IntentPayload（select_system / log_search / unrecognized）。

    单次识别（非法输出的预算重试由调用方任务层控制，对齐 NL2JSON 模式）：
    - 解析失败（非合法 JSON / 形态不合 schema）→ AIOutputParseFailedError（触发重试）
    - select_system 的 system_id 越权（不在候选内）→ AIOutputInvalidError（触发重试）
    - AI 调用超时 / 服务异常 → AITimeoutError / AIServiceError（触发重试）
    """

    # 默认专属智能体（bp-ai-user-intent）；bkop 经 BKAPP_AI_USER_INTENT_API_URL 直连，
    # 生产默认链路（见模块 docstring）；AI_USER_INTENT_AGENT_CODE 可应急覆盖路由
    agent_code = resolve_intent_agent_code()

    @classmethod
    def recognize(
        cls,
        *,
        query_text: str,
        candidates: list[dict],
        current_system_id: str,
        username: str,
    ) -> IntentPayload:
        """
        :param query_text: 用户自然语言原话
        :param candidates: 候选系统清单 [{system_id, name}]（权限内，调用方组装）
        :param current_system_id: 会话当前已选系统（空串表示未选）
        :param username: 操作人（显式传入，不依赖请求上下文）
        :return: IntentPayload
        """

        user_message = cls._build_user_message(query_text, candidates, current_system_id)
        content = cls._call_agent(user_message, username)
        payload = cls._parse_and_validate(content)
        cls._validate_system_in_candidates(payload, candidates)
        return payload

    @classmethod
    def _build_user_message(cls, query_text: str, candidates: list[dict], current_system_id: str) -> str:
        # autoescape=False：防止用户输入与候选 JSON 中的引号被 HTML 转义扭曲语义（对齐 NL2JSON）
        return Template(INTENT_USER_MESSAGE_TEMPLATE).render(
            Context(
                {
                    "query_text": query_text,
                    "current_time": timezone.localtime().isoformat(),
                    "candidates_json": json.dumps(candidates, ensure_ascii=False),
                    "current_system_id": current_system_id or "",
                    "output_schema_json": json.dumps(IntentPayload.model_json_schema(), ensure_ascii=False),
                },
                autoescape=False,
            )
        )

    @classmethod
    def _call_agent(cls, user_message: str, username: str) -> str:
        """调 chat_completion 返回 content 字符串（异常映射与 NL2JSON 同构）。"""

        try:
            resp = api.bk_plugins_ai_agent.chat_completion(
                agent_code=cls.agent_code,
                user=username,
                input=user_message,
                chat_history=[],
                execute_kwargs={"stream": False},
            )
        except Timeout as err:
            raise AITimeoutError(extra={"error": str(err)})
        except Exception as err:  # noqa: BLE001
            logger.exception("[IntentRecognitionService] chat_completion failed")
            raise AIServiceError(extra={"error": str(err)})
        if not isinstance(resp, str):
            raise AIOutputParseFailedError(
                extra={"raw_type": type(resp).__name__, "raw_output": str(resp)[:INTENT_RAW_OUTPUT_KEEP_LENGTH]},
            )
        return resp

    @classmethod
    def _parse_and_validate(cls, content: str) -> IntentPayload:
        """JSON 提取（复用 NL2JSON 三级递进闸门）→ IntentPayload 形态校验。"""

        payload = NL2JSONService._extract_json(content)
        if payload is None:
            raise AIOutputParseFailedError(extra={"raw_output": content[:INTENT_RAW_OUTPUT_KEEP_LENGTH]})
        try:
            return IntentPayload.model_validate(payload)
        except ValidationError as err:
            raise AIOutputParseFailedError(
                extra={
                    "raw_output": content[:INTENT_RAW_OUTPUT_KEEP_LENGTH],
                    "validation_error": str(err),
                },
            )

    @staticmethod
    def _validate_system_in_candidates(payload: IntentPayload, candidates: list[dict]) -> None:
        """select_system 的 system_id 必须在候选内（防幻觉越权；不合法触发调用方预算重试）。"""

        if payload.intent != "select_system":
            return
        candidate_ids = {str(candidate.get("system_id") or "") for candidate in candidates}
        if not payload.system_id or payload.system_id not in candidate_ids:
            raise AIOutputInvalidError(
                extra={
                    "intent": payload.intent,
                    "system_id": payload.system_id,
                    "reason": "system_id not in candidates",
                },
            )

    @staticmethod
    def load_candidates(namespace: str, username: str, scope_type: str = "", scope_id: str = "") -> list[dict]:
        """组装候选系统清单：全量系统 ∩ 用户检索权限（无权限系统不进候选，AI 无法越权）。

        传 scope_type 时与检索页场景过滤同源（SearchLogPermission.get_scope_auth_systems，
        即 ``_build_system_conditions`` 同一权限口径）：候选限定为该场景/scope 下授权的系统，
        意图识别无法路由到场景外系统；未传时保持既有行为（系统方向 ∪ 场景方向权限并集，
        旧前端兼容）。

        供 Celery 任务等无请求上下文场景使用（权限组件依赖请求上下文取用户名，
        此处走显式 username 的参数化版本）。
        """

        from apps.meta.permissions import SearchLogPermission

        if scope_type:
            # get_scope_auth_systems 无权限时返回 [""]（ES filter 兜底语义），候选清单置空
            allowed_ids = set(SearchLogPermission.get_scope_auth_systems(scope_type, scope_id, username))
            allowed_ids.discard("")
            systems = resource.meta.system_list_all(namespace=namespace)
        else:
            systems, authorized_system_ids = SearchLogPermission.get_auth_systems_by_username(namespace, username)
            allowed_ids = set(authorized_system_ids)
        return [
            {"system_id": str(system["id"]), "name": str(system.get("name") or system["id"])}
            for system in systems
            if str(system["id"]) in allowed_ids
        ]


class MessagePlanningService:
    """通用消息规划：一次调用生成系统选择、日志检索或二者组合。"""

    agent_code = resolve_intent_agent_code()
    system_prompt = SYSTEM_PROMPT

    @classmethod
    def plan(
        cls,
        *,
        query_text: str,
        system_context: SystemSelectionOutput,
        current_system_id: str,
        username: str,
        scope_type: str,
        scope_id: str,
        reference_time: datetime,
        user_message: str | None = None,
    ) -> MessagePlan:
        """构造完整规划上下文并返回通过候选范围校验的消息计划。"""

        if user_message is None:
            user_message = cls.build_user_message(
                query_text=query_text,
                system_context=system_context,
                current_system_id=current_system_id,
                username=username,
                scope_type=scope_type,
                scope_id=scope_id,
                reference_time=reference_time,
            )
        content = cls._call_agent(user_message, username)
        plan = cls._parse_and_validate(content)
        plan = cls._normalize_redundant_selection(plan, current_system_id)
        cls._validate_system_scope(plan, system_context, current_system_id)
        return plan

    @classmethod
    def build_user_message(
        cls,
        *,
        query_text: str,
        system_context: SystemSelectionOutput,
        current_system_id: str,
        username: str,
        scope_type: str,
        scope_id: str,
        reference_time: datetime,
    ) -> str:
        """以分层文本组织动态上下文，输出契约只注入一次 MessagePlan schema。"""

        systems = []
        for system in system_context.systems:
            description = system.description
            description_truncated = len(description) > PLANNING_SYSTEM_DESCRIPTION_MAX_LENGTH
            systems.append(
                {
                    "system_id": system.system_id,
                    "name": system.name,
                    "description": description[:PLANNING_SYSTEM_DESCRIPTION_MAX_LENGTH],
                    **(
                        {
                            "description_meta": {
                                "truncated": True,
                                "original_length": len(description),
                            }
                        }
                        if description_truncated
                        else {}
                    ),
                    "standard_fields": [_serialize_planning_field(field) for field in system.standard_fields],
                    "extension_fields": [_serialize_planning_field(field) for field in system.extension_fields],
                }
            )
        current_week_start = reference_time.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
            days=reference_time.weekday()
        )
        conversation_context = {
            "username": username,
            "phase": "SYSTEM_SELECTED" if current_system_id else "SYSTEM_UNSELECTED",
            "scope_type": scope_type,
            "scope_id": scope_id,
            "current_system_id": current_system_id,
        }
        clock = {
            "current_time": reference_time.isoformat(),
            "timezone": str(reference_time.tzinfo),
            "default_start_time": (reference_time - timedelta(days=1)).isoformat(),
            "current_week_start": current_week_start.isoformat(),
            "previous_week_start": (current_week_start - timedelta(days=7)).isoformat(),
            "previous_week_end": current_week_start.isoformat(),
        }
        rules = (
            "- 当前系统 ID 必须存在于授权系统列表中才算有效；否则按当前无有效系统处理。\n"
            "- 仅切换系统时生成 SYSTEM_SELECTION。\n"
            "- 已有有效系统且用户未明确点名另一个系统时，只生成 LOG_SEARCH。\n"
            "- 指定新系统并检索时，依次生成 SYSTEM_SELECTION、LOG_SEARCH。\n"
            "- 未指定系统且当前无有效系统时返回 SYSTEM_REQUIRED。\n"
            "- 不得因授权系统只有一个或位于列表首位就自动选择；SYSTEM_SELECTION 必须有用户点名系统的依据。\n"
            "- 用户明确点名的系统不在授权系统中时返回 SYSTEM_UNAVAILABLE，不得映射到当前系统。\n"
            "- 错误分支先判断用户是否点名系统：授权列表无匹配（包括授权列表为空）时优先返回 SYSTEM_UNAVAILABLE；只有未点名且无有效当前系统时才返回 SYSTEM_REQUIRED。\n"
            "- 寒暄、闲聊及无关请求返回 UNRECOGNIZED_INTENT；即使已有系统，也不得据此生成 LOG_SEARCH。\n"
            "- 未指定时间时默认最近一天；相对时间只以 clock.current_time 和 timezone 为基准。\n"
            "- 近 N 天表示 current_time 前 N×24 小时；上周直接使用 previous_week_start/previous_week_end。\n"
            "- 用户已表达日志检索但未给字段和时间时仍生成 LOG_SEARCH，空 condition 由后端补齐。"
        )
        return (
            "# 任务\n"
            "根据当前会话、授权系统与用户请求，生成下一批业务消息。\n\n"
            "# 当前会话\n"
            "<conversation>\n"
            f"{json.dumps(conversation_context, ensure_ascii=False, indent=2)}\n"
            "</conversation>\n\n"
            "# 当前时间\n"
            "<clock>\n"
            f"{json.dumps(clock, ensure_ascii=False, indent=2)}\n"
            "</clock>\n\n"
            "# 授权系统与字段\n"
            "以下列表已经过权限过滤，SYSTEM_SELECTION 的 system_id 只能取自此处。\n"
            "<authorized_systems>\n"
            f"{json.dumps(systems, ensure_ascii=False, indent=2)}\n"
            "</authorized_systems>\n\n"
            "# 支持的消息\n"
            "- SYSTEM_SELECTION：选择或切换一个授权系统；scope 与 visible 由后端补齐。\n"
            "- LOG_SEARCH：在目标系统中检索日志；scope 与 visible 由后端补齐。\n\n"
            "# 业务规则\n"
            f"{rules}\n\n"
            "# 用户请求\n"
            "<user_query>\n"
            f"{query_text}\n"
            "</user_query>\n\n"
            "# 输出 JSON Schema\n"
            "只输出一个符合以下 schema 的 JSON 对象，不要输出解释或 Markdown。\n"
            "<message_plan_schema>\n"
            f"{json.dumps(MessagePlan.model_json_schema(), ensure_ascii=False, indent=2)}\n"
            "</message_plan_schema>"
        )

    @classmethod
    def _call_agent(cls, user_message: str, username: str) -> str:
        """调用通用 Agent 并统一映射基础设施异常。"""

        try:
            response = api.bk_plugins_ai_agent.chat_completion(
                agent_code=cls.agent_code,
                user=username,
                chat_history=[
                    {"role": "role", "content": cls.system_prompt},
                    {"role": "user", "content": user_message},
                ],
                execute_kwargs={"stream": False, "thread_id": f"intent-planning-{uuid4().hex}"},
            )
        except Timeout as error:
            raise AITimeoutError(extra={"error": str(error)})
        except Exception as error:  # noqa: BLE001
            logger.exception("[MessagePlanningService] chat_completion failed")
            raise AIServiceError(extra={"error": str(error)})
        if not isinstance(response, str):
            raise AIOutputParseFailedError(
                extra={
                    "raw_type": type(response).__name__,
                    "raw_output": str(response)[:INTENT_RAW_OUTPUT_KEEP_LENGTH],
                },
            )
        return response

    @classmethod
    def _parse_and_validate(cls, content: str) -> MessagePlan:
        """提取 JSON 并按 MessagePlan 契约校验。"""

        raw_plan = NL2JSONService._extract_json(content)
        if raw_plan is None:
            raise AIOutputParseFailedError(extra={"raw_output": content[:INTENT_RAW_OUTPUT_KEEP_LENGTH]})
        try:
            return MessagePlan.model_validate(raw_plan)
        except ValidationError as error:
            raise AIOutputParseFailedError(
                extra={"raw_output": content[:INTENT_RAW_OUTPUT_KEEP_LENGTH], "validation_error": str(error)},
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
        system_context: SystemSelectionOutput,
        current_system_id: str,
    ) -> None:
        """拒绝候选外系统及缺失有效系统的检索计划。"""

        if plan.outcome == "error":
            return
        candidate_ids = {system.system_id for system in system_context.systems}
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
