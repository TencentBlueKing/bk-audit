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

用户意图识别服务（一期 v6）：自然语言 → IntentPayload。

复用现有 AUDIT_LOG_SEARCH agent（意图识别任务指令在 User Message 完整自述）；
输出契约 IntentPayload 为 single source of truth（schema 注入与校验同模型）；
候选系统 = 用户权限内系统（无权限系统不进候选，AI 无法越权），
前端传场景过滤 scope 时与检索页同口径收窄候选（防意图识别绕过场景过滤）。
"""

import json
import logging

from bk_resource import api, resource
from django.template import Context, Template
from django.utils import timezone
from pydantic import ValidationError
from requests.exceptions import Timeout

from api.constants import AIAgentCode
from services.web.query.ai_assistant.exceptions import (
    AIOutputInvalidError,
    AIOutputParseFailedError,
    AIServiceError,
    AITimeoutError,
)
from services.web.query.ai_assistant.schemas import IntentPayload
from services.web.query.ai_assistant.services.nl2json import NL2JSONService

logger = logging.getLogger(__name__)

# AI 输出原文在日志/异常 extra 中的最大保留长度（对齐 NL2JSON）
INTENT_RAW_OUTPUT_KEEP_LENGTH = 2048

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
1. 必须严格按照以下 JSON Schema 输出一个 JSON 对象，不要输出其他任何内容：
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
   - 用户话语为日志检索需求且未提及任何系统 → intent=log_search（system_id 留空）
   - 与日志检索和系统选择完全无关（寒暄/闲聊）→ intent=unrecognized
3. system_id 必须严格来自候选系统列表，禁止编造。「无法确定具体系统」仅指话语中没有任何系统指向词、
   或指向词与所有候选均无法建立匹配，此时才判 log_search（system_id 留空）；
   话语已明确点名系统名时必须给出 select_system 与最佳匹配候选，即使存在名称相似的多个候选也不得放弃选择
4. message 必须自然、面向用户：识别成功时简述识别结果（如「已为您切换到蓝盾」）；无法识别时说明原因并引导用户明确表达（此消息将直接展示给用户）"""


class IntentRecognitionService:
    """用户意图识别：自然语言 → IntentPayload（select_system / log_search / unrecognized）。

    单次识别（非法输出的预算重试由调用方任务层控制，对齐 NL2JSON 模式）：
    - 解析失败（非合法 JSON / 形态不合 schema）→ AIOutputParseFailedError（触发重试）
    - select_system 的 system_id 越权（不在候选内）→ AIOutputInvalidError（触发重试）
    - AI 调用超时 / 服务异常 → AITimeoutError / AIServiceError（触发重试）
    """

    agent_code = AIAgentCode.AUDIT_LOG_SEARCH

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
