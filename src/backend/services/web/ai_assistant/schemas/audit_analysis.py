"""日志分析报告的 Input / Context / Output 快照协议。

Context 只保存重放 Agent 请求所需的最小充分信息，不保存预览日志、
SQL 或数据库内部 ID。历史附件的有效指令固化在 Context，不跟随全局配置变化。
"""

from typing import Annotated

from django.conf import settings
from pydantic import (
    Field,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)
from rest_framework import serializers

from services.web.ai_assistant.constants import AnalysisMode
from services.web.ai_assistant.schemas.message import MessageSchema
from services.web.query.ai_assistant.log_tools.schemas import AgentSearchCondition
from services.web.query.ai_assistant.schemas import SearchCondition

_NestedObjectField = serializers.DictField()


class AIAnalysisInputSchema(MessageSchema):
    """前端提交的分析模式与可选自定义指令。"""

    analysis_mode: AnalysisMode
    instruction: str | None = Field(
        default=None,
        max_length=settings.AI_ASSISTANT_LOG_ANALYSIS_PROMPT_MAX_LENGTH,
        description="CUSTOM 模式必填的分析要求；DEFAULT 模式不允许提交。",
    )

    @field_validator("instruction")
    @classmethod
    def _strip_instruction(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def _validate_instruction_mode(self) -> "AIAnalysisInputSchema":
        if self.analysis_mode == AnalysisMode.CUSTOM and not self.instruction:
            raise ValueError("CUSTOM 模式必须提供非空 instruction")
        # DEFAULT 的指令只能由服务端配置生成；显式 null/空串也属于客户端越权指定。
        if self.analysis_mode == AnalysisMode.DEFAULT and "instruction" in self.model_fields_set:
            raise ValueError("DEFAULT 模式不允许提供 instruction")
        return self

    @model_serializer(mode="wrap")
    def serialize_input(self, handler: SerializerFunctionWrapHandler):
        """默认模式不写入 instruction，保证快照回读遵守与创建相同的协议。

        不声明新的返回 schema，避免 Pydantic 将原有字段协议替换为任意字典。
        """

        data = handler(self)
        if self.analysis_mode == AnalysisMode.DEFAULT:
            data.pop("instruction", None)
        return data


class AIAnalysisQuerySummary(MessageSchema):
    """Agent 可用的轻量检索摘要，不包含任何日志样例。"""

    total: int = Field(ge=0, description="检索命中日志总数。")
    took_ms: int = Field(ge=0, description="原始检索耗时，单位毫秒。")
    executed_at: str = Field(description="原始检索完成时间。")


class AIAnalysisContextSchema(MessageSchema):
    """Worker 使用的不对外执行快照。"""

    effective_instruction: str = Field(min_length=1, description="创建时已固化的有效分析指令。")
    search_condition: Annotated[AgentSearchCondition, _NestedObjectField]
    query_summary: AIAnalysisQuerySummary
    username: str = Field(min_length=1, description="Agent 及工具调用使用的用户身份。")
    namespace: str = Field(min_length=1, description="检索消息固化的 namespace，不由前端提交。")
    timezone: str = Field(min_length=1, description="创建报告时固化的部署默认时区。")
    language: str = Field(min_length=1, description="创建报告时固化的部署默认语言。")

    @field_validator("search_condition", mode="before")
    @classmethod
    def normalize_search_condition(cls, value):
        """兼容平台内部传入公共条件实例，并统一固化为 Agent 工具条件。"""

        if isinstance(value, SearchCondition):
            return value.model_dump(mode="json")
        return value


class AIAnalysisOutputSchema(MessageSchema):
    """可编辑、可导出的最终 Markdown 报告。"""

    markdown: str = Field(min_length=1, description="Agent 返回的完整 Markdown 正文。")

    @field_validator("markdown")
    @classmethod
    def _validate_markdown(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Markdown 正文不能为空")
        if len(value.encode("utf-8")) > settings.AI_ASSISTANT_ATTACHMENT_MARKDOWN_MAX_BYTES:
            raise ValueError("Markdown 正文超过大小上限")
        return value


__all__ = [
    "AIAnalysisContextSchema",
    "AIAnalysisInputSchema",
    "AIAnalysisOutputSchema",
    "AIAnalysisQuerySummary",
]
