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

AI 助手日志检索消息协议模型

与《W0 消息业务载荷协议》1:1：
- condition 与现有 collector_query/search 请求完全同构
  （field{raw_name, field_type, keys} + filters + 顶层 start_time/end_time），
  无 namespace / 分页 / 排序（后端注入 / 固化）；
- Pydantic 只做形态校验（类型/必填/格式），语义校验（字段白名单/操作符）在服务层。

快照样例字典键规则（samples 内）：标准列为 raw_name；拓展列为
full_key（raw_name 与 keys 以 LOG_FIELD_KEY_JOIN_CHAR 连接），与导出链路一致。
"""

import re
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from core.utils.time import parse_datetime
from services.web.query.constants import LOG_FIELD_KEY_JOIN_CHAR
from services.web.query.utils.search_config import QueryConditionOperator

NO_VALUE_OPERATORS = (
    QueryConditionOperator.ISNULL.value,
    QueryConditionOperator.NOTNULL.value,
)

# 协议 §2.1：时间仅两种格式——ISO8601 带时区（推荐）或 'YYYY-MM-DD HH:mm:ss'（无时区按本地时区）
ISO8601_TZ_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})$")
NAIVE_DATETIME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")


# ---------------------------------------------------------------------------
# 统一条件结构（协议 §2）
# ---------------------------------------------------------------------------


class ConditionField(BaseModel):
    """条件字段（协议 §2.1 field；与 QuerySearchFieldSerializer 同构）"""

    raw_name: str = Field(..., min_length=1)
    field_type: Optional[str] = None
    keys: List[str] = Field(default_factory=list)


class Condition(BaseModel):
    """单条检索条件（协议 §2.1；与 QuerySearchConditionSerializer 同构）"""

    field: ConditionField
    operator: str = Field(..., min_length=1)
    filters: List[Any] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_filters_shape(self):
        if self.operator in NO_VALUE_OPERATORS and self.filters:
            raise ValueError("isnull/notnull operator requires empty filters")
        if self.operator not in NO_VALUE_OPERATORS and not self.filters:
            raise ValueError("filters is required")
        if self.operator == QueryConditionOperator.BETWEEN.value and len(self.filters) != 2:
            raise ValueError("between operator requires exactly 2 filters")
        return self


class SearchCondition(BaseModel):
    """
    统一条件结构（协议 §2）：NL 输出 = LOG_SEARCH 输入。

    与 collector_query/search 请求同构平铺，缺 namespace/分页/排序（后端注入/固化）。
    model_dump() 输出补 namespace/page/page_size/sort_list 后可直接喂
    CollectorSearchAllReqSerializer 校验。
    """

    scope_type: Literal["system"] = "system"
    scope_id: str = Field(..., min_length=1)
    start_time: str = Field(..., min_length=1)
    end_time: str = Field(..., min_length=1)
    conditions: List[Condition] = Field(default_factory=list)

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        if not (ISO8601_TZ_PATTERN.match(v) or NAIVE_DATETIME_PATTERN.match(v)):
            raise ValueError("time must be ISO8601 with timezone or 'YYYY-MM-DD HH:mm:ss'")
        try:
            parse_datetime(v)
        except Exception as err:
            raise ValueError("invalid datetime value") from err
        return v


# ---------------------------------------------------------------------------
# SYSTEM_SELECTION（协议 §3）
# ---------------------------------------------------------------------------


class SystemSelectionInput(BaseModel):
    """SYSTEM_SELECTION 输入（协议 §3.1，一期限 1 个系统，结构按集合设计）"""

    system_ids: List[str] = Field(..., min_length=1, max_length=1)


class SelectionFieldOption(BaseModel):
    """枚举字段可选值（与日志检索页 es_query/field_map 返回同构 [{id, name}]）"""

    id: str
    name: str


class SelectionFieldMeta(BaseModel):
    """字段元数据（协议 §3.2，standard_fields / extension_fields 共用结构）"""

    raw_name: str
    keys: List[str] = Field(default_factory=list)
    # 字段值类型（FieldType.value，如 string/integer/long；拓展字段一期恒 string）
    field_type: Optional[str] = None
    display_name: str = ""
    nl_name: str = ""
    description: str = ""
    allow_operators: List[str] = Field(default_factory=list)
    # 原始查询值（如 0/-1，非展示值"成功(0)"），无数据为 None
    sample_value: Optional[Any] = None
    # 枚举字段可选值（如 result_code 的 成功0/其他-1），非枚举字段为 None；前端 options 非空时渲染下拉
    options: Optional[List[SelectionFieldOption]] = None
    # 仅拓展字段返回
    system_id: Optional[str] = None


class SelectionSystem(BaseModel):
    """单系统的字段上下文（协议 §3.2 systems[] 元素）"""

    system_id: str
    name: str = ""
    standard_fields: List[SelectionFieldMeta] = Field(default_factory=list)
    extension_fields: List[SelectionFieldMeta] = Field(default_factory=list)


class SystemSelectionOutput(BaseModel):
    """SYSTEM_SELECTION 输出（协议 §3.2）；常见/历史操作由平台层消息协议组装。"""

    systems: List[SelectionSystem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# NATURAL_LANGUAGE_SEARCH（协议 §4）
# ---------------------------------------------------------------------------


class NLSearchInput(BaseModel):
    """NL 输入（协议 §4.1）"""

    query_text: str = Field(..., min_length=1)
    auto_execute: bool = True


class NLSearchOutput(BaseModel):
    """NL 输出（协议 §4.2，官方稳定键为 condition 单键）"""

    condition: SearchCondition


class AIConditionItem(BaseModel):
    """AI 生成的单条条件（AIDev 返回契约，不进 output_data）"""

    raw_name: str = Field(..., min_length=1)
    keys: List[str] = Field(default_factory=list)
    field_type: Optional[str] = None
    operator: str = Field(..., min_length=1)
    filters: List[Any] = Field(default_factory=list)


class AIConditionPayload(BaseModel):
    """AIDev 返回的 JSON 契约：条件 + 时间（scope 不生成，取自上下文）"""

    conditions: List[AIConditionItem] = Field(default_factory=list)
    start_time: Optional[str] = None
    end_time: Optional[str] = None


# ---------------------------------------------------------------------------
# LOG_SEARCH（协议 §5）
# ---------------------------------------------------------------------------


class LogSearchInput(BaseModel):
    """LOG_SEARCH 输入（协议 §5.1）"""

    condition: SearchCondition


class ResultColumn(BaseModel):
    """结果列定义（协议 §5.2 columns；首列固定 start_time）"""

    raw_name: str
    keys: List[str] = Field(default_factory=list)
    display_name: str = ""
    description: str = ""

    @property
    def full_key(self) -> str:
        """列唯一键（samples 字典键）：标准列 = raw_name，拓展列 = raw_name/key/..."""
        return LOG_FIELD_KEY_JOIN_CHAR.join([self.raw_name, *self.keys])


class QuerySummary(BaseModel):
    """检索摘要（协议 §5.2 query_summary）"""

    scope_type: str
    scope_id: str
    time_range: Dict[str, str]
    condition_count: int = 0
    source: Literal["natural_language", "field_condition"] = "field_condition"
    took_ms: int = 0
    executed_at: str = ""


class LogSearchOutput(BaseModel):
    """LOG_SEARCH 输出（协议 §5.2，四键：total/columns/samples/query_summary，无 SQL）"""

    total: int = 0
    columns: List[ResultColumn] = Field(default_factory=list)
    samples: List[Dict[str, Any]] = Field(default_factory=list)
    query_summary: QuerySummary
