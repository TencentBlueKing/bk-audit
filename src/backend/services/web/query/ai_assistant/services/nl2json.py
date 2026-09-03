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
    AI_FORBIDDEN_CONDITION_FIELDS,
    AI_NL2JSON_THREAD_ID_PREFIX,
    DEFAULT_SEARCH_WINDOW_DAYS,
    EXTENSION_FIELD_DEFAULT_OPERATORS,
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
2. 通用字段：raw_name 必须来自字段上下文，keys 为 []；拓展字段（下钻）：raw_name 取字段上下文中的 JSON 容器字段（如 extend_data），keys 为下钻子键——字段上下文已列出的照抄，未列出但用户明确指定的按用户描述的子键名生成；检索范围由「目标系统」唯一指定，禁止输出 system_id 字段条件，用户提及系统名或其他系统时不映射该字段
3. operator 必须在该字段 allow_operators 内（拓展字段允许 eq/neq/include/exclude/like）；filters 形态匹配操作符（isnull/notnull 为 []，between 恰好 2 个值，like 只传子串不带 %）
4. 同一字段的多个取值（如多个操作人、多个资源类型）输出为单个条件：filters 放全部值、operator 用 include（排除语义用 exclude）；禁止拆成多个同字段条件，也禁止把多个值塞进 eq
5. 值必须是原始查询值（如 result_code 用 0 而不是 "成功(0)"），形态参照字段上下文 sample_value
6. 时间按「当前时间」推算为 ISO8601 带时区的绝对时间：
   - 相对表述（最近N天/近N天/最近N小时/近一小时/最近一周等）→ 滚动窗口：start_time=当前时间前推N天（或N小时），end_time=当前时间
   - 自然单位（昨天/前天/上周/上个月）→ 按自然边界换算（如昨天=昨日00:00:00至昨日23:59:59，上周=上周一00:00:00至上周日23:59:59）；本周/本月 → 起点为自然边界，end_time 取当前时间
   - 时段表述（今天上午/昨天下午等）→ 该时段起点至该时段终点
   - 具体日期区间（如"8月1日到8月15日"）→ 按给出的起止边界换算
   - 用户有检索意图（想查日志）但未提任何时间 → 输出最近 30 天（一个月）滚动窗口
   - 仅当用户输入与日志检索完全无关（寒暄/闲聊）时才输出 null
7. 关键词全文检索用 log 字段的 match_all/match_any 操作符表达：多个关键词需同时满足用 match_all，任一满足用 match_any；当用户以中文或口语描述操作类型、资源类型等，而字段上下文的 options 与 sample_value 均无法确定该字段确切取值时，禁止猜测字段值，改用 log 的 match_any 表达该关键词需求
8. 用户明确指定某个下钻子键时，即使字段上下文未列出该子键也必须按用户要求生成对应拓展字段条件（禁止因字段上下文没有该子键就拒绝或忽略）；仅通用字段不在字段上下文中时才忽略该字段，继续组装其余可识别的检索条件
9. 时间范围本身就是有效检索需求：仅含时间的查询（如"帮我查下最近七天的日志"）必须输出空 conditions 与换算后的 start_time/end_time；仅当输入与日志检索完全无关（寒暄/闲聊）时，才返回：{"conditions":[],"start_time":null,"end_time":null}"""

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
        - 下钻条件的容器字段必须在 is_json 白名单内；子键采样发现或用户显式指定均放行
        - operator ∈ 该字段 allow_operators（未采样发现的子键按拓展字段默认操作符集合校验）
        - 数值比较操作符仅数值类型字段可用（拓展字段一期恒 string 不支持）
        """
        standard_map = {f.raw_name: f for s in selection.systems for f in s.standard_fields}
        extension_map = {(f.raw_name, tuple(f.keys)): f for s in selection.systems for f in s.extension_fields}
        json_containers = {cfg.field.field_name for cfg in COLLECT_SEARCH_CONFIG.field_configs if cfg.field.is_json}
        valid_operators = {choice[0] for choice in QueryConditionOperator.choices}

        valid_conditions: List[AIConditionItem] = []
        for cond in payload.conditions:
            # 防御：AI 偷带时间/系统字段条件 → 剔除并告警（时间由后端统一管理；
            # 系统范围由 scope_id 唯一决定，偷带 system_id 会与权限注入条件冲突致零命中）
            if cond.raw_name in AI_FORBIDDEN_CONDITION_FIELDS:
                logger.warning(f"[NL2JSONService] drop forbidden field condition from AI output: {cond.raw_name}")
                continue
            cls._validate_operator_shape(cond, valid_operators)
            if cond.keys:
                cls._validate_extension_condition(cond, extension_map, json_containers)
            else:
                cls._validate_standard_condition(cond, standard_map)
            valid_conditions.append(cond)

        if not valid_conditions:
            # 纯时间窗口检索（如"帮我查下最近七天的日志"）：AI 已识别出有效时间即视为
            # 合法检索意图，放行空条件（时间由 _assemble 统一组装，检索侧支持零条件）；
            # 仅当时间同样无效（寒暄/无关输入）才判未识别
            if not cls._payload_has_valid_time(payload):
                raise QueryNotRecognizedError(extra={"payload": payload.model_dump()})
            payload.conditions = []
            return
        payload.conditions = valid_conditions

    @classmethod
    def _payload_has_valid_time(cls, payload: AIConditionPayload) -> bool:
        """AI 输出是否携带可解析的有效时间（检索意图成立的信号，与 _assemble 同解析口径）"""

        return any(cls._safe_parse_time(value) is not None for value in (payload.start_time, payload.end_time))

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
        """拓展子键信任边界：容器字段必须在白名单（防编造容器），子键采样发现或用户显式指定均放行。

        采样覆盖率有限（单系统子键集合远大于 N 条样本），用户显式指定的下钻子键
        不因「字段上下文未列出」被拒绝；用户指定的子键限单层（一期下钻协议），
        多层路径仅字段上下文精确匹配（L1 人工配置）时放行；未发现子键的操作符按拓展字段默认集合校验。
        """
        if cond.raw_name not in json_containers:
            raise AIOutputInvalidError(extra={"condition": cond.model_dump(), "reason": "keys on non-json field"})
        meta = extension_map.get((cond.raw_name, tuple(cond.keys)))
        if meta is None and len(cond.keys) != 1:
            raise AIOutputInvalidError(
                extra={"condition": cond.model_dump(), "reason": "extension keys depth not supported"}
            )
        allowed_operators = meta.allow_operators if meta is not None else EXTENSION_FIELD_DEFAULT_OPERATORS
        if cond.operator not in allowed_operators:
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
        if start_time > end_time:
            # 防御：AI 时间换算倒置（LLM 常见笔误），Doris 链路无倒置校验、SQL 恒假零命中，交换保窗口有效
            logger.warning(
                f"[NL2JSONService] swapped reversed time window from AI output: {start_time} ~ {end_time}"
            )
            start_time, end_time = end_time, start_time
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
