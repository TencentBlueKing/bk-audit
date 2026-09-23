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

检索条件的 JSON 提取、语义校验与组装。

消息规划和评测都先得到 Agent 的条件载荷，再交给本服务补齐服务端范围与默认时间。
本服务不调用 Agent，也不感知消息类型。
"""

import json
import re
from datetime import datetime, timedelta
from typing import List, Optional

from blueapps.utils.logger import logger
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from pydantic import ValidationError

from core.sql.constants import FieldType
from services.web.query.ai_assistant.constants import (
    AI_FORBIDDEN_CONDITION_FIELDS,
    DEFAULT_SEARCH_WINDOW_DAYS,
)
from services.web.query.ai_assistant.exceptions import (
    AIOutputParseFailedError,
    InvalidConditionError,
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

# 语义校验拒绝原因 → 用户可读文案（extra.reason 保留机器码供日志排障；message 直达用户）
INVALID_REASON_MESSAGES = {
    "field not in field context": "字段不在当前系统的可检索字段内",
    "operator not allowed for field": "该字段不支持此筛选方式",
    "operator not allowed for extension field": "拓展字段不支持此筛选方式",
    "keys on non-json field": "该字段不支持下钻筛选",
    "numeric operator on string extension field": "拓展字段为文本类型，不支持数值比较",
    "numeric operator on non-numeric field": "该字段为非数值类型，不支持数值比较",
    "unknown operator": "不支持的操作符",
    "filters required": "筛选条件缺少比较值",
    "between needs 2 filters": "区间筛选需要恰好 2 个值",
    "field type does not match field context": "字段类型与当前系统字段定义不一致",
}


def _invalid_condition_error(cond: "AIConditionItem", reason: str) -> InvalidConditionError:
    """语义校验失败统一构造：message 面向用户可读（前端错误卡直显），extra 保留机器 reason。"""

    return InvalidConditionError(
        message=INVALID_REASON_MESSAGES.get(reason, InvalidConditionError.error_message),
        extra={"condition": cond.model_dump(), "reason": reason},
    )


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


class ConditionAssemblyService:
    """校验并组装检索条件：范围取调用方，时间缺省时按同一锚点补齐。"""

    @classmethod
    def parse_condition_text(
        cls,
        content: str,
        selection: SystemSelectionOutput,
        scope_id: str,
        reference_time: datetime,
        allow_empty: bool = False,
    ) -> SearchCondition:
        """从 Agent 原文提取条件 JSON，校验后组装。不调用 Agent。"""

        payload = cls.parse_payload(content)
        return cls.validate_and_assemble(
            payload=payload,
            selection=selection,
            scope_id=scope_id,
            reference_time=reference_time,
            allow_empty=allow_empty,
        )

    @classmethod
    def parse_payload(cls, content: str) -> AIConditionPayload:
        """提取并做形态校验，语义校验留给 validate_and_assemble。"""

        payload = cls.extract_json(content)
        if payload is None:
            raise AIOutputParseFailedError(extra={"raw_output": content[:RAW_OUTPUT_KEEP_LENGTH]})
        try:
            return AIConditionPayload.model_validate(payload)
        except ValidationError as err:
            raise InvalidConditionError(
                extra={
                    "raw_output": content[:RAW_OUTPUT_KEEP_LENGTH],
                    "validation_error": str(err),
                    "validation_errors": [
                        {
                            "path": ".".join(str(part) for part in item["loc"]),
                            "code": str(item["type"]),
                            "message": str(item["msg"]),
                        }
                        for item in err.errors(include_input=False, include_url=False)
                    ],
                },
            )

    @classmethod
    def validate_and_assemble(
        cls,
        payload: AIConditionPayload,
        selection: SystemSelectionOutput,
        scope_id: str,
        reference_time: datetime,
        allow_empty: bool = False,
    ) -> SearchCondition:
        """校验 Agent 已生成的条件并补齐服务端范围与默认时间，不再次调用 Agent。

        Args:
            allow_empty: 上游已通过消息计划确认检索意图时，允许空条件并采用默认时间窗。
        """

        normalized = payload.model_copy(deep=True)
        if allow_empty and not normalized.conditions and not cls._payload_has_valid_time(normalized):
            return cls._assemble(normalized, scope_id, reference_time)
        cls._validate_semantics(normalized, selection)
        return cls._assemble(normalized, scope_id, reference_time)

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
    def extract_json(cls, content: str) -> Optional[dict]:
        """递进提取：直解析 → ```json``` 代码块 → 花括号正则"""
        text = (content or "").strip()
        result = cls._try_parse_json(text)
        if result is not None:
            return result
        fence_match = JSON_FENCE_PATTERN.search(text)
        if fence_match:
            result = cls._try_parse_json(fence_match.group(1))
            if result is not None:
                return result
        brace_match = JSON_BRACE_PATTERN.search(text)
        if brace_match:
            result = cls._try_parse_json(brace_match.group(0))
            if result is not None:
                return result
        return None

    @classmethod
    def _validate_semantics(cls, payload: AIConditionPayload, selection: SystemSelectionOutput) -> None:
        """
        语义校验（InvalidConditionError 抛出点）。

        规则与 QuerySearchConditionSerializer.validate 同源：
        - raw_name 白名单（通用字段清单 = COLLECT_SEARCH_CONFIG 同源）
        - 下钻条件的容器字段必须在 is_json 白名单内；子键采样发现或用户显式指定均放行
        - 标准字段 operator 遵循字段上下文；拓展字段 operator 使用查询层全局枚举
        - 标准字段按元数据校验类型和操作符；拓展叶子字段允许 Agent 在查询契约内推断
        """
        standard_map = {f.raw_name: f for s in selection.systems for f in s.standard_fields}
        json_containers = {cfg.field.field_name for cfg in COLLECT_SEARCH_CONFIG.field_configs if cfg.field.is_json}
        valid_operators = {choice[0] for choice in QueryConditionOperator.choices}

        valid_conditions: List[AIConditionItem] = []
        for cond in payload.conditions:
            # 防御：AI 偷带时间/系统字段条件 → 剔除并告警（时间由后端统一管理；
            # 系统范围由 scope_id 唯一决定，偷带 system_id 会与权限注入条件冲突致零命中）
            if cond.raw_name in AI_FORBIDDEN_CONDITION_FIELDS:
                logger.warning(
                    "[ConditionAssemblyService] drop forbidden field condition from AI output: %s",
                    cond.raw_name,
                )
                continue
            cls._validate_operator_shape(cond, valid_operators)
            if cond.keys:
                cls._validate_extension_condition(cond, json_containers)
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
            raise _invalid_condition_error(cond, "unknown operator")
        if cond.operator in NO_VALUE_OPERATORS:
            # isnull/notnull 不需要值，容错归一为空数组
            cond.filters = []
        elif not cond.filters:
            raise _invalid_condition_error(cond, "filters required")
        if cond.operator == QueryConditionOperator.BETWEEN.value and len(cond.filters) != 2:
            raise _invalid_condition_error(cond, "between needs 2 filters")

    @classmethod
    def _validate_extension_condition(cls, cond: AIConditionItem, json_containers: set) -> None:
        """拓展子键信任边界：容器字段必须在白名单（防编造容器），子键路径采样发现或用户显式指定均放行。

        采样覆盖率有限（单系统子键集合远大于 N 条样本），用户显式指定的下钻路径
        不因「字段上下文未列出」被拒绝；下钻路径支持多层（产品确认不做层级限制——
        Doris SQL 层 variant 逐级拼接 / JSON Path 均天然支持任意深度，见
        core/sql/builder/terms.py::DorisVariantField.format_keys_quote）；未发现
        子键路径的类型与操作符由 Agent 在查询层 Schema 范围内结合用户表达推断。
        """
        if cond.raw_name not in json_containers:
            raise _invalid_condition_error(cond, "keys on non-json field")

    @classmethod
    def _validate_standard_condition(cls, cond: AIConditionItem, standard_map: dict) -> None:
        meta = standard_map.get(cond.raw_name)
        if meta is None:
            raise _invalid_condition_error(cond, "field not in field context")
        if cond.operator not in meta.allow_operators:
            raise _invalid_condition_error(cond, "operator not allowed for field")
        field_cfg = COLLECT_SEARCH_CONFIG.query_field_map.get(cond.raw_name)
        field_type = field_cfg.field.field_type if field_cfg else None
        if cond.operator in NUMERIC_OPERATORS and field_type not in NUMERIC_FIELD_TYPES:
            raise _invalid_condition_error(cond, "numeric operator on non-numeric field")
        if field_type in FieldType.values:
            if "field_type" not in cond.model_fields_set:
                # 兼容旧输出未携带类型；标准字段元数据是权威来源。
                cond.field_type = field_type
            elif cond.field_type != field_type:
                raise _invalid_condition_error(cond, "field type does not match field context")

    @classmethod
    def _assemble(cls, payload: AIConditionPayload, scope_id: str, reference_time: datetime) -> SearchCondition:
        """scope 取入参；AI 时间优先，缺省时间基于本次转换的同一锚点补齐。"""

        end_time = cls._safe_parse_time(payload.end_time) or reference_time
        start_time = cls._safe_parse_time(payload.start_time) or (end_time - timedelta(days=DEFAULT_SEARCH_WINDOW_DAYS))
        if start_time > end_time:
            # 防御：AI 时间换算倒置（LLM 常见笔误），Doris 链路无倒置校验、SQL 恒假零命中，交换保窗口有效
            logger.warning(
                "[ConditionAssemblyService] swapped reversed time window from AI output: %s ~ %s",
                start_time,
                end_time,
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
        """解析 Agent 输出的 ISO 时间并保留绝对时刻；无时区值按当前服务时区解释。"""

        if not value:
            return None
        try:
            parsed = parse_datetime(value)
            if parsed is None:
                return None
            if timezone.is_naive(parsed):
                return timezone.make_aware(parsed, timezone.get_current_timezone())
            return parsed
        except Exception:  # noqa: BLE001
            logger.warning("[ConditionAssemblyService] invalid time from AI output: %s", value)
            return None
