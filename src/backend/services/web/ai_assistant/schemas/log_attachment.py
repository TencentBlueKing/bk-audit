"""日志衍生附件共用的完整查询条件输入，不允许局部合并或显式 null。"""
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_serializer
from rest_framework import serializers

from services.web.ai_assistant.schemas.message import MessageSchema
from services.web.query.ai_assistant.log_tools.schemas import (
    LOG_TOOL_MAX_CONDITIONS,
    AgentCondition,
    AgentSearchCondition,
    _omit_null_request_schema,
)


class LogAttachmentCondition(AgentSearchCondition):
    """附件覆盖条件必须显式完整；MCP 条件原有默认值保持不变。"""

    scope_type: Literal["system"] = Field(description=AgentSearchCondition.model_fields["scope_type"].description)
    conditions: list[AgentCondition] = Field(
        max_length=LOG_TOOL_MAX_CONDITIONS,
        description=AgentSearchCondition.model_fields["conditions"].description,
    )


class LogAttachmentInput(MessageSchema):
    """省略 condition 使用当前来源条件；prepare 后保存完整有效条件。"""

    condition: Annotated[
        LogAttachmentCondition | None, serializers.DictField(required=False, allow_null=False)
    ] = Field(
        default=None,
        json_schema_extra=_omit_null_request_schema,
        description="可选完整检索条件；省略使用当前成功来源，传入则整体替换，仅影响此附件；不接受 null 或局部条件。",
    )

    @field_validator("condition", mode="before")
    @classmethod
    def reject_null_condition(cls, value):
        """区分省略与显式空值，避免误将错误输入解释为来源范围。"""
        if value is None:
            raise ValueError("condition must be a complete object")
        return value.model_dump(mode="json") if isinstance(value, AgentSearchCondition) else value

    @model_serializer(mode="wrap")
    def serialize_condition(self, handler):
        """尚未 prepare 的输入可省略 condition；有效输入始终包含完整条件。"""
        data = handler(self)
        if self.condition is None:
            data.pop("condition", None)
        return data
