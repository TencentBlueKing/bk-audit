"""审计日志检索三类消息的平台协议模型。

稳定键与《开发设计方案（总）》§7.2 对齐；字段上下文、检索条件和检索快照
的内部结构直接复用 query 模块的类型化模型（协议「零转换」原则）。

嵌套 query 模型含 ``Any`` 字段，drf_pydantic 无法自动转换 DRF serializer，
统一用 ``Annotated[类型, DRF字段]`` 显式声明宽松 DRF 表达：运行时校验仍由
Pydantic 嵌套模型完整执行，Swagger 只展示宽松对象结构。
"""

from typing import Annotated, Any, Literal

from pydantic import Field, model_validator
from rest_framework import serializers

from services.web.ai_assistant.schemas.message import MessageSchema
from services.web.query.ai_assistant.schemas import (
    LogSearchOutput,
    QuerySummary,
    ResultColumn,
    SearchCondition,
    SelectionSystem,
    SystemSelectionOutput,
)

__all__ = [
    "CommonQuerySchema",
    "LogSearchContextSchema",
    "LogSearchInputSchema",
    "LogSearchOutputSchema",
    "NLSearchContextSchema",
    "NLSearchErrorSchema",
    "NLSearchInputSchema",
    "NLSearchOutputSchema",
    "SystemSelectionContextSchema",
    "SystemSelectionInputSchema",
    "SystemSelectionOutputSchema",
]

# 嵌套 query 模型 / 宽松集合的统一 DRF 表达（运行时校验仍走 Pydantic 嵌套模型）
_NestedListField = serializers.ListField(child=serializers.DictField())
_NestedObjectField = serializers.DictField()
_NestedObjectOrNullField = serializers.DictField(allow_null=True)


class CommonQuerySchema(MessageSchema):
    """常见/历史操作条目：自然语言检索样例（D3 方案）。"""

    query_text: str = Field(min_length=1, max_length=2048)


class SystemSelectionInputSchema(MessageSchema):
    """系统选择输入：协议按集合表达，一期限定单系统。"""

    system_ids: list[str] = Field(min_length=1, max_length=1)


class SystemSelectionContextSchema(MessageSchema):
    """系统选择服务端上下文。"""

    username: str
    namespace: str


class SystemSelectionOutputSchema(MessageSchema):
    """系统选择输出：字段上下文与操作上下文的完整快照。"""

    systems: Annotated[list[SelectionSystem], _NestedListField] = Field(default_factory=list)
    common_operations: list[CommonQuerySchema] = Field(default_factory=list)
    historical_operations: list[CommonQuerySchema] = Field(default_factory=list)


class NLSearchInputSchema(MessageSchema):
    """自然语言检索输入。"""

    query_text: str = Field(min_length=1, max_length=2048)
    auto_execute: bool = True


class NLSearchContextSchema(MessageSchema):
    """自然语言检索上下文：从父系统选择消息复制的最小充分字段上下文。"""

    username: str
    namespace: str
    scope_id: str
    system_selection: Annotated[SystemSelectionOutput, _NestedObjectField]


class NLSearchErrorSchema(MessageSchema):
    """自然语言识别失败的结构化协议（消息任务成功、识别业务失败）。"""

    error_code: str
    error_message: str


class NLSearchOutputSchema(MessageSchema):
    """自然语言检索输出：成功携带受控检索条件；预期内识别失败携带结构化错误协议。"""

    condition: Annotated[SearchCondition | None, _NestedObjectOrNullField] = None
    error: NLSearchErrorSchema | None = None

    @model_validator(mode="after")
    def _validate_payload_exclusive(self) -> "NLSearchOutputSchema":
        """condition 与 error 互斥：识别成功带条件，识别失败带错误协议。"""

        if (self.condition is None) == (self.error is None):
            raise ValueError("NL 检索输出必须且只能携带 condition 或 error 之一")
        return self


class LogSearchInputSchema(MessageSchema):
    """日志检索输入：结构化条件，字段条件检索与 NL 续链共用同一结构。"""

    condition: Annotated[SearchCondition, _NestedObjectField]


class LogSearchContextSchema(MessageSchema):
    """日志检索上下文：来源、目标系统与执行身份。"""

    username: str
    namespace: str
    system_id: str
    source: Literal["natural_language", "field_condition"] = "field_condition"


class LogSearchOutputSchema(MessageSchema):
    """日志检索输出：命中概览与最多 100 条样例快照（协议稳定键）。"""

    total: int = 0
    columns: Annotated[list[ResultColumn], _NestedListField] = Field(default_factory=list)
    samples: Annotated[list[dict[str, Any]], _NestedListField] = Field(default_factory=list)
    query_summary: Annotated[QuerySummary, _NestedObjectField]

    @classmethod
    def from_query_output(cls, output: LogSearchOutput) -> "LogSearchOutputSchema":
        """从 query 模块输出零转换构造平台快照。"""

        return cls(
            total=output.total,
            columns=output.columns,
            samples=output.samples,
            query_summary=output.query_summary,
        )
