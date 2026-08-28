"""日志工具共享的 Pydantic 协议。"""

import re
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from apps.meta.utils.fields import EXTEND_DATA
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
