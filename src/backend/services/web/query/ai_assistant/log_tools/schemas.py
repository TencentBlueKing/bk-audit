"""日志工具共享的 Pydantic 协议。"""

import re
from enum import StrEnum
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from apps.meta.utils.fields import EXTEND_DATA
from services.web.query.ai_assistant.schemas import (
    SearchCondition,
    SelectionFieldOption,
)
from services.web.query.constants import COLLECT_SEARCH_CONFIG

FIELD_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


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
        if self.raw_name not in COLLECT_SEARCH_CONFIG.query_field_map:
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
