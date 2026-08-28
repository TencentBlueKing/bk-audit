"""日志工具共享的 Pydantic 协议。"""

import re
from enum import StrEnum
from typing import Any, Dict, List, Literal, Optional, Tuple

from django.conf import settings
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from apps.meta.utils.fields import EXTEND_DATA, START_TIME
from services.web.query.ai_assistant.schemas import (
    QuerySummary,
    SearchCondition,
    SelectionFieldOption,
)
from services.web.query.constants import COLLECT_SEARCH_CONFIG

FIELD_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
LOG_SEARCH_MAX_FIELDS = 20
LOG_SEARCH_MAX_SORT_FIELDS = 3
LOG_SEARCH_MAX_PAGE = 100
LOG_SEARCH_MAX_PAGE_SIZE = 100
LOG_SEARCH_RESPONSE_MAX_BYTES = 1024 * 1024
# 字段展示元信息可覆盖 WEB 列，但 Agent 投影只能使用条件白名单和默认列必需的 start_time。
LOG_TOOL_ALLOWED_FIELD_NAMES = frozenset((*COLLECT_SEARCH_CONFIG.query_field_map, START_TIME.field_name))
LOG_TOOL_SORTABLE_FIELD_NAMES = frozenset((START_TIME.field_name,))


def _bounded_limit(setting_name: str, hard_limit: int, minimum: int) -> int:
    """运行环境只能收紧冻结协议上限，不能放大 Agent 工具成本。"""

    return min(hard_limit, max(minimum, getattr(settings, setting_name, hard_limit)))


class LogFieldRef(BaseModel):
    """受控日志字段引用，仅允许白名单字段或 extend_data 的安全子路径。

    一期仅支持 JSONPath helper 可无歧义表达的 ASCII 标识符子键；这不是 SQL
    注入的唯一防线。Task 3 字段发现必须复用本模型过滤，不能返回不可消费的子键。
    """

    model_config = ConfigDict(extra="forbid")

    raw_name: str = Field(..., min_length=1)
    keys: List[str] = Field(default_factory=list)
    field_type: Optional[str] = None

    @field_validator("keys")
    @classmethod
    def validate_keys(cls, keys: List[str]) -> List[str]:
        for key in keys:
            if not FIELD_KEY_PATTERN.fullmatch(key):
                raise ValueError("invalid field key")
        return keys

    @model_validator(mode="after")
    def validate_field_reference(self):
        if self.raw_name not in LOG_TOOL_ALLOWED_FIELD_NAMES:
            raise ValueError("unsupported log field")
        # 当前工具只允许动态 extend_data 下钻，避免将任意 JSON 容器暴露给 Agent。
        if self.keys and self.raw_name != EXTEND_DATA.field_name:
            raise ValueError("nested keys are only supported for extend_data")
        return self


class LogFieldScope(StrEnum):
    """字段探索范围；ALL 仅用于请求，返回字段分类只使用 BASIC/EXTENDED。"""

    ALL = "ALL"
    BASIC = "BASIC"
    EXTENDED = "EXTENDED"


class LogFieldMetadataTypeSource(StrEnum):
    """字段类型的来源，避免把采样观察误表述为全量定义。"""

    DECLARED = "DECLARED"
    INFERRED = "INFERRED"


class GetLogFieldMetadataRequest(BaseModel):
    """字段元信息探索请求，父路径复用可消费的 extend_data 路径约束。"""

    condition: SearchCondition
    parent_keys: List[str] = Field(default_factory=list)
    field_scope: LogFieldScope = LogFieldScope.ALL

    @field_validator("parent_keys")
    @classmethod
    def validate_parent_keys(cls, parent_keys: List[str]) -> List[str]:
        LogFieldRef(raw_name=EXTEND_DATA.field_name, keys=parent_keys)
        return parent_keys


class LogFieldMetadataItem(BaseModel):
    """单个可查询字段的声明元信息与当前样本观察。"""

    field: LogFieldRef
    category: LogFieldScope
    display_name: str = ""
    description: str = ""
    type_source: LogFieldMetadataTypeSource
    observed_types: List[str] = Field(default_factory=list)
    allow_operators: List[str] = Field(default_factory=list)
    options: Optional[List[SelectionFieldOption]] = None
    is_expandable: bool = False
    sample_values: List[Any] = Field(default_factory=list)
    sampled_non_null_count: int = 0
    coverage: float = 0.0


class FieldSampleSummary(BaseModel):
    """字段探索的有界采样摘要。"""

    sampled_count: int = 0
    returned_field_count: int = 0
    truncated: bool = False


class GetLogFieldMetadataResponse(BaseModel):
    """字段探索响应，不包含 SQL、物理表或未经脱敏的命中行。"""

    fields: List[LogFieldMetadataItem] = Field(default_factory=list)
    sample_summary: FieldSampleSummary


class LogSortItem(BaseModel):
    """明细查询的受控排序项，仅允许已知标准字段。"""

    model_config = ConfigDict(extra="forbid")

    field: LogFieldRef
    direction: Literal["asc", "desc"] = "desc"

    @model_validator(mode="after")
    def validate_sort_field(self):
        if self.field.raw_name not in LOG_TOOL_SORTABLE_FIELD_NAMES or self.field.keys:
            raise ValueError("sort only supports start_time")
        return self


class SearchLogsRequest(BaseModel):
    """日志明细请求，所有字段和排序均以 LogFieldRef 表达。"""

    model_config = ConfigDict(extra="forbid")

    condition: SearchCondition
    fields: Optional[List[LogFieldRef]] = None
    sort: List[LogSortItem] = Field(default_factory=list)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1)

    @model_validator(mode="after")
    def validate_limits(self):
        if self.fields is not None:
            if not self.fields:
                raise ValueError("at least one field is required")
            field_keys = [(field.raw_name, tuple(field.keys)) for field in self.fields]
            if len(field_keys) != len(set(field_keys)):
                raise ValueError("duplicate fields are not allowed")
            if len(self.fields) > _bounded_limit("AI_LOG_SEARCH_MAX_FIELDS", LOG_SEARCH_MAX_FIELDS, 0):
                raise ValueError("too many fields")

        sort_keys = [(item.field.raw_name, tuple(item.field.keys)) for item in self.sort]
        if len(sort_keys) != len(set(sort_keys)):
            raise ValueError("duplicate sort fields are not allowed")
        if len(self.sort) > _bounded_limit("AI_LOG_SEARCH_MAX_SORT_FIELDS", LOG_SEARCH_MAX_SORT_FIELDS, 0):
            raise ValueError("too many sort fields")
        if self.page > _bounded_limit("AI_LOG_SEARCH_MAX_PAGE", LOG_SEARCH_MAX_PAGE, 1):
            raise ValueError("page exceeds maximum")
        if self.page_size > _bounded_limit("AI_LOG_SEARCH_MAX_PAGE_SIZE", LOG_SEARCH_MAX_PAGE_SIZE, 1):
            raise ValueError("page_size exceeds maximum")
        return self


class LogDetailColumn(BaseModel):
    """返回列元信息；key 是 items 中稳定且无歧义的键。"""

    field: LogFieldRef
    key: str
    display_name: str = ""
    description: str = ""
    options: Optional[List[SelectionFieldOption]] = None


class LogSearchPagination(BaseModel):
    """明细分页结果。"""

    page: int
    page_size: int
    total: int
    returned_count: int
    has_more: bool


class SearchLogsResponse(BaseModel):
    """受控明细响应，不包含 SQL、物理表、条件值或原始命中。"""

    total: int
    columns: List[LogDetailColumn] = Field(default_factory=list)
    items: Tuple[Dict[str, Any], ...] = ()
    pagination: LogSearchPagination
    query_summary: QuerySummary
