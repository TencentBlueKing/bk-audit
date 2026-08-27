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
either express or implied. See the License for the specific language governing
permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.

F2 NL2JSON 服务（NATURAL_LANGUAGE_SEARCH 消息核心组件）

薄代理原则：业务逻辑（字段语义/操作符规则/few-shot）全在 AIDev System Prompt，
本服务只做四件事：组 User Message → 调 chat_completion → 三层校验 → 组装 condition。

信任边界：
- scope 不信任 AI 输出，一律取调用方传入值（用户选择的系统）；
- 时间由 AI 按注入的 current_time 推算，缺省/非法时后端补默认窗口（D2）；
- AI 输出中偷带的时间字段条件（thedate/dtEventTimeStamp）后端剔除并告警。
"""

import json
import re
from datetime import timedelta
from typing import List, Optional

from bk_resource import api
from bk_resource.exceptions import APIRequestError
from blueapps.utils.logger import logger
from django.template import Context, Template
from django.utils import timezone
from opentelemetry import trace
from pydantic import ValidationError
from requests.exceptions import Timeout

from api.constants import AIAgentCode
from core.sql.constants import FieldType
from core.utils.data import unique_id
from core.utils.time import parse_datetime
from services.web.query.ai_assistant.constants import (
    AI_FORBIDDEN_TIME_FIELDS,
    AI_NL2JSON_THREAD_ID_PREFIX,
    DEFAULT_SEARCH_WINDOW_DAYS,
)
from services.web.query.ai_assistant.exceptions import (
    AIOutputInvalidError,
    AIOutputParseFailedError,
    AIServiceError,
    AITimeoutError,
    QueryNotRecognizedError,
)
from services.web.query.ai_assistant.schemas import (
    NO_VALUE_OPERATORS,
    AIConditionItem,
    AIConditionPayload,
    Condition,
    ConditionField,
    SearchCondition,
    SystemSelectionOutput,
)
from services.web.query.constants import COLLECT_SEARCH_CONFIG
from services.web.query.utils.search_config import QueryConditionOperator

NL2JSON_USER_MESSAGE_TEMPLATE = """# 审计日志检索条件提取任务

## 用户问题
{{ query_text }}

## 当前时间
{{ current_time }}

## 目标系统
{{ scope_id }}

## 字段上下文（含通用字段与拓展字段，拓展字段 nl_name 带 extend. 前缀）
{{ field_context_json }}

## 输出要求
1. 只输出一个 JSON 对象，不要输出其他任何内容：
{
  "conditions": [
    {"raw_name": "字段名", "keys": [], "field_type": "string", "operator": "操作符", "filters": ["值"]}
  ],
  "start_time": "...",
  "end_time": "..."
}
2. raw_name 必须来自字段上下文；keys 照抄字段上下文（通用字段为 []，拓展字段为下钻路径）
3. operator 必须在该字段 allow_operators 内；filters 形态匹配操作符（isnull/notnull 为 []，between 恰好 2 个值，like 只传子串不带 %）
4. 值必须是原始查询值（如 result_code 用 0 而不是 "成功(0)"），形态参照字段上下文 sample_value
5. 时间按当前时间推算，ISO8601 带时区；用户未提时间时输出 null，由后端补默认窗口
6. 关键词全文检索用 match_all/match_any 操作符表达
7. 用户提到的字段若不在字段上下文中，忽略该字段（禁止编造字段名或 keys），继续用字段上下文中已有的字段组装其余可识别的检索条件（如时间范围、操作人等）
8. 仅当所有检索需求都无法映射到字段上下文时，才返回：{"conditions":[],"start_time":null,"end_time":null}"""

# 数值比较操作符（仅数值类型字段可用）
NUMERIC_OPERATORS = {
    QueryConditionOperator.GT.value,
    QueryConditionOperator.GTE.value,
    QueryConditionOperator.LT.value,
    QueryConditionOperator.LTE.value,
    QueryConditionOperator.BETWEEN.value,
}
NUMERIC_FIELD_TYPES = {
    FieldType.INT.value,
    FieldType.LONG.value,
    FieldType.DOUBLE.value,
    FieldType.FLOAT.value,
    FieldType.TIMESTAMP.value,
}
# 花括号提取兜底（AI 输出前后带散文时）
JSON_BRACE_PATTERN = re.compile(r"\{.*\}", re.DOTALL)
JSON_FENCE_PATTERN = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)

# AI 输出原文在日志/异常 extra 中的最大保留长度
RAW_OUTPUT_KEEP_LENGTH = 2048


class NL2JSONService:
    """自然语言 → condition（NL 输出 = LOG_SEARCH 输入，零转换）"""

    agent_code = AIAgentCode.AUDIT_LOG_SEARCH

    @classmethod
    def convert(
        cls,
        query_text: str,
        selection: SystemSelectionOutput,
        scope_id: str,
        username: str,
    ) -> SearchCondition:
        """
        :param query_text: 用户自然语言
        :param selection: F1 产出（SYSTEM_SELECTION output_data），字段上下文同源
        :param scope_id: 目标系统（取自上下文，不信任 AI）
        :param username: 操作人（显式传入，不依赖请求上下文）
        :return: SearchCondition
        :raises QueryNotRecognizedError: 空识别
        :raises AIOutputParseFailedError: AI 返回非合法 JSON
        :raises AIOutputInvalidError: 字段/操作符/取值形态非法
        :raises AIServiceError: AIDev 调用错误
        :raises AITimeoutError: AIDev 调用超时
        """
        span = trace.get_current_span()
        span.set_attribute("ai.nl2json.query_length", len(query_text))
        span.set_attribute("ai.nl2json.scope_id", scope_id)

        user_message = cls._build_user_message(query_text, selection, scope_id)
        content = cls._call_agent(user_message, username)
        payload = cls._parse_and_validate(content, selection)
        return cls._assemble(payload, scope_id)

    # ------------------------------------------------------------------
    # ① User Message 组装
    # ------------------------------------------------------------------

    @classmethod
    def _build_user_message(cls, query_text: str, selection: SystemSelectionOutput, scope_id: str) -> str:
        # autoescape=False：Context 默认开启 HTML 转义，会把用户输入与字段上下文 JSON 中的
        # & < > " ' 转成 &amp; 等实体注入 prompt，扭曲检索语义
        return Template(NL2JSON_USER_MESSAGE_TEMPLATE).render(
            Context(
                {
                    "query_text": query_text,
                    "current_time": timezone.localtime().isoformat(),
                    "scope_id": scope_id,
                    "field_context_json": cls._serialize_field_context(selection),
                },
                autoescape=False,
            )
        )

    @staticmethod
    def _serialize_field_context(selection: SystemSelectionOutput) -> str:
        """字段上下文序列化注入（与前端字段行同源，含 nl_name）"""
        systems = []
        for system in selection.systems:
            systems.append(
                {
                    "system_id": system.system_id,
                    "name": system.name,
                    "standard_fields": [field.model_dump(exclude_none=True) for field in system.standard_fields],
                    "extension_fields": [field.model_dump(exclude_none=True) for field in system.extension_fields],
                }
            )
        return json.dumps(systems, ensure_ascii=False)

    # ------------------------------------------------------------------
    # ② AIDev 调用（非流式，复用 NL2RiskFilter 同链路）
    # ------------------------------------------------------------------

    @classmethod
    def _call_agent(cls, user_message: str, username: str) -> str:
        """
        调 chat_completion 返回 content 字符串。

        超时控制：资源类默认 TIMEOUT=300s（AIAgentBase），不在调用参数透传；
        requests 超时异常统一映射为 AITimeoutError。
        """
        try:
            resp = api.bk_plugins_ai_agent.chat_completion(
                agent_code=cls.agent_code,
                user=username,
                input=user_message,
                chat_history=[],
                execute_kwargs={
                    "stream": False,
                    "thread_id": f"{AI_NL2JSON_THREAD_ID_PREFIX}-{username}-{unique_id()}",
                },
            )
        except Timeout as err:
            raise AITimeoutError(extra={"error": str(err)})
        except APIRequestError as err:
            logger.error(f"[NL2JSONService] chat_completion failed: {err}")
            raise AIServiceError(extra={"error": str(err)})
        except Exception as err:  # noqa: BLE001
            logger.exception("[NL2JSONService] chat_completion unexpected error")
            raise AIServiceError(extra={"error": str(err)})
        if not isinstance(resp, str):
            raise AIOutputParseFailedError(
                extra={"raw_type": type(resp).__name__, "raw_output": str(resp)[:RAW_OUTPUT_KEEP_LENGTH]},
            )
        return resp

    # ------------------------------------------------------------------
    # ③ 三层校验：JSON 提取 → Pydantic 形态 → 语义
    # ------------------------------------------------------------------

    @classmethod
    def _parse_and_validate(cls, content: str, selection: SystemSelectionOutput) -> AIConditionPayload:
        payload = cls._extract_json(content)
        if payload is None:
            raise AIOutputParseFailedError(extra={"raw_output": content[:RAW_OUTPUT_KEEP_LENGTH]})
        try:
            parsed = AIConditionPayload.model_validate(payload)
        except ValidationError as err:
            raise AIOutputParseFailedError(
                extra={"raw_output": content[:RAW_OUTPUT_KEEP_LENGTH], "validation_error": str(err)},
            )
        cls._validate_semantics(parsed, selection)
        return parsed

    @staticmethod
    def _try_parse_json(text: Optional[str]) -> Optional[dict]:
        """json.loads + dict 形态检查，失败/非 dict 返回 None"""
        if not text:
            return None
        try:
            result = json.loads(text)
            return result if isinstance(result, dict) else None
        except (json.JSONDecodeError, TypeError):
            return None

    @classmethod
    def _extract_json(cls, content: str) -> Optional[dict]:
        """递进提取：直解析 → ```json``` 代码块 → 花括号正则"""
        text = (content or "").strip()
        # 直解析
        result = cls._try_parse_json(text)
        if result is not None:
            return result
        # 代码块
        fence_match = JSON_FENCE_PATTERN.search(text)
        if fence_match:
            result = cls._try_parse_json(fence_match.group(1))
            if result is not None:
                return result
        # 花括号兜底
        brace_match = JSON_BRACE_PATTERN.search(text)
        if brace_match:
            result = cls._try_parse_json(brace_match.group(0))
            if result is not None:
                return result
        return None

    @classmethod
    def _validate_semantics(cls, payload: AIConditionPayload, selection: SystemSelectionOutput) -> None:
        """
        语义校验（AIOutputInvalidError 抛出点）。

        规则与 QuerySearchConditionSerializer.validate 同源：
        - raw_name 白名单（通用字段清单 = COLLECT_SEARCH_CONFIG 同源）
        - 下钻条件必须是字段清单中的拓展字段（容器 is_json + keys 照抄）
        - operator ∈ 该字段 allow_operators（下钻条件按 judge_operator 语义放行自定义操作符，
          但仍需在拓展字段自身 allow_operators 内）
        - 数值比较操作符仅数值类型字段可用（拓展字段一期恒 string 不支持）
        """
        standard_map = {f.raw_name: f for s in selection.systems for f in s.standard_fields}
        extension_map = {(f.raw_name, tuple(f.keys)): f for s in selection.systems for f in s.extension_fields}
        json_containers = {cfg.field.field_name for cfg in COLLECT_SEARCH_CONFIG.field_configs if cfg.field.is_json}
        valid_operators = {choice[0] for choice in QueryConditionOperator.choices}

        valid_conditions: List[AIConditionItem] = []
        for cond in payload.conditions:
            # 防御：AI 偷带时间字段条件 → 剔除并告警（时间由后端统一管理）
            if cond.raw_name in AI_FORBIDDEN_TIME_FIELDS:
                logger.warning(f"[NL2JSONService] drop time field condition from AI output: {cond.raw_name}")
                continue
            cls._validate_operator_shape(cond, valid_operators)
            if cond.keys:
                cls._validate_extension_condition(cond, extension_map, json_containers)
            else:
                cls._validate_standard_condition(cond, standard_map)
            valid_conditions.append(cond)

        if not valid_conditions:
            raise QueryNotRecognizedError(extra={"payload": payload.model_dump()})
        payload.conditions = valid_conditions

    @classmethod
    def _validate_operator_shape(cls, cond: AIConditionItem, valid_operators: set) -> None:
        if cond.operator not in valid_operators:
            raise AIOutputInvalidError(extra={"condition": cond.model_dump(), "reason": "unknown operator"})
        if cond.operator in NO_VALUE_OPERATORS:
            # isnull/notnull 不需要值，容错归一为空数组
            cond.filters = []
        elif not cond.filters:
            raise AIOutputInvalidError(extra={"condition": cond.model_dump(), "reason": "filters required"})
        if cond.operator == QueryConditionOperator.BETWEEN.value and len(cond.filters) != 2:
            raise AIOutputInvalidError(extra={"condition": cond.model_dump(), "reason": "between needs 2 filters"})

    @classmethod
    def _validate_extension_condition(cls, cond: AIConditionItem, extension_map: dict, json_containers: set) -> None:
        meta = extension_map.get((cond.raw_name, tuple(cond.keys)))
        if meta is None:
            raise AIOutputInvalidError(
                extra={"condition": cond.model_dump(), "reason": "extension field not in field context"}
            )
        if cond.raw_name not in json_containers:
            raise AIOutputInvalidError(extra={"condition": cond.model_dump(), "reason": "keys on non-json field"})
        if cond.operator not in meta.allow_operators:
            raise AIOutputInvalidError(
                extra={"condition": cond.model_dump(), "reason": "operator not allowed for extension field"}
            )
        # 拓展字段一期恒 string：数值比较不支持
        if cond.operator in NUMERIC_OPERATORS:
            raise AIOutputInvalidError(
                extra={"condition": cond.model_dump(), "reason": "numeric operator on string extension field"}
            )

    @classmethod
    def _validate_standard_condition(cls, cond: AIConditionItem, standard_map: dict) -> None:
        meta = standard_map.get(cond.raw_name)
        if meta is None:
            raise AIOutputInvalidError(extra={"condition": cond.model_dump(), "reason": "field not in field context"})
        if cond.operator not in meta.allow_operators:
            raise AIOutputInvalidError(
                extra={"condition": cond.model_dump(), "reason": "operator not allowed for field"}
            )
        field_cfg = COLLECT_SEARCH_CONFIG.query_field_map.get(cond.raw_name)
        field_type = field_cfg.field.field_type if field_cfg else None
        if cond.operator in NUMERIC_OPERATORS and field_type not in NUMERIC_FIELD_TYPES:
            raise AIOutputInvalidError(
                extra={"condition": cond.model_dump(), "reason": "numeric operator on non-numeric field"}
            )
        # field_type 缺省补全（协议：服务端按字段元数据补全）
        if not cond.field_type and field_cfg:
            cond.field_type = field_cfg.field.field_type

    # ------------------------------------------------------------------
    # ④ 组装 condition
    # ------------------------------------------------------------------

    @classmethod
    def _assemble(cls, payload: AIConditionPayload, scope_id: str) -> SearchCondition:
        """scope 取入参（不信任 AI）；时间 AI 优先，缺省/非法补默认窗口（D2）"""
        end_time = cls._safe_parse_time(payload.end_time) or timezone.now()
        start_time = cls._safe_parse_time(payload.start_time) or (end_time - timedelta(days=DEFAULT_SEARCH_WINDOW_DAYS))
        return SearchCondition(
            scope_type="system",
            scope_id=scope_id,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            conditions=[
                Condition(
                    field=ConditionField(raw_name=cond.raw_name, field_type=cond.field_type, keys=cond.keys),
                    operator=cond.operator,
                    filters=cond.filters,
                )
                for cond in payload.conditions
            ],
        )

    @staticmethod
    def _safe_parse_time(value: Optional[str]):
        if not value:
            return None
        try:
            return parse_datetime(value)
        except Exception:  # noqa: BLE001
            logger.warning(f"[NL2JSONService] invalid time from AI output: {value}")
            return None
