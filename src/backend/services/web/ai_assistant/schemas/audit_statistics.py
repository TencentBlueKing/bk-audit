"""统计附件的持久化协议。

程序统计只接收字段与预算；查询范围和显示信息由成功检索来源重建。
程序输出复用查询领域固定包，AI 输出保存原文，不在附件层引入图表结构。
"""

import json
from typing import Annotated

from django.conf import settings
from pydantic import Field, field_validator, model_validator
from rest_framework import serializers

from services.web.ai_assistant.schemas.message import MessageSchema
from services.web.query.ai_assistant.log_tools.field_statistics_schemas import (
    FieldDistribution,
    FieldNumericSummary,
    FieldStatisticsOverview,
    FieldStatisticsResult,
    FieldTimeSeries,
    StatisticsField,
)
from services.web.query.ai_assistant.log_tools.schemas import (
    AGGREGATION_MAX_TOP_N,
    AgentSearchCondition,
    AggregationQuerySummary,
    AggregationTimeInterval,
    LogFieldRef,
)


class FieldStatisticsAttachmentInput(MessageSchema):
    """前端字段引用与有界统计参数；类型提示由查询内核忽略。"""

    field: Annotated[LogFieldRef, serializers.DictField()]
    top_n: int = Field(default=100, strict=True, ge=1, le=AGGREGATION_MAX_TOP_N)
    interval: AggregationTimeInterval = AggregationTimeInterval.AUTO

    @model_validator(mode="after")
    def validate_budget(self):
        """创建时即拒绝超出部署预算的请求，不产生无效附件。"""
        if self.top_n > min(settings.AI_LOG_AGGREGATION_MAX_TOP_N, AGGREGATION_MAX_TOP_N):
            raise ValueError("statistics top_n exceeds maximum")
        return self


class FieldStatisticsAttachmentContext(MessageSchema):
    """服务端固化的可重放查询上下文，不存预览样例和客户端类型声明。"""

    search_condition: Annotated[AgentSearchCondition, serializers.DictField()]
    field: Annotated[StatisticsField, serializers.DictField()]
    top_n: int = Field(ge=1, le=AGGREGATION_MAX_TOP_N)
    interval: AggregationTimeInterval
    username: str = Field(min_length=1)
    namespace: str = Field(min_length=1)
    timezone: str = Field(min_length=1)


class FieldStatisticsAttachmentOutput(MessageSchema, FieldStatisticsResult):
    """直接保存 Task6 固定包；DRF 仅为嵌套领域 DTO 提供文档字段。"""

    field: Annotated[StatisticsField, serializers.DictField()]
    overview: Annotated[FieldStatisticsOverview, serializers.DictField()]
    distribution: Annotated[FieldDistribution, serializers.DictField()]
    time_series: Annotated[FieldTimeSeries, serializers.DictField()]
    numeric_summary: Annotated[FieldNumericSummary | None, serializers.DictField(allow_null=True)]
    query_summary: Annotated[AggregationQuerySummary, serializers.DictField()]

    @field_validator("distribution", mode="before")
    @classmethod
    def restore_distribution(cls, value):
        """以 JSON 协议恢复严格 typed 类别，避免数据库回读把合法枚举字符串拒绝。"""
        if isinstance(value, dict):
            return FieldDistribution.model_validate_json(json.dumps(value))
        return value


class AIStatisticsAttachmentInput(MessageSchema):
    """用户统计指令；来源和身份只能由后端填充。"""

    instruction: str = Field(min_length=1, max_length=settings.AI_ASSISTANT_AI_STATISTICS_INSTRUCTION_MAX_LENGTH)

    @field_validator("instruction")
    @classmethod
    def validate_instruction(cls, value: str) -> str:
        """拒绝纯空白指令，保留有效用户输入。"""
        if not value.strip():
            raise ValueError("statistics instruction must not be blank")
        return value


class AIStatisticsQuerySummary(MessageSchema):
    """仅描述原检索的轻量概览，不代表 Agent 调整后的统计范围。"""

    total: int = Field(ge=0)
    executed_at: str


class AIStatisticsAttachmentContext(MessageSchema):
    """创建时固化最小初始上下文；Agent 可以按需求调整实际工具查询范围。"""

    system_prompt: str = Field(min_length=1)
    instruction: str = Field(min_length=1)
    initial_search_condition: Annotated[AgentSearchCondition, serializers.DictField()]
    query_summary: AIStatisticsQuerySummary
    username: str = Field(min_length=1)
    namespace: str = Field(min_length=1)
    timezone: str = Field(min_length=1)
    language: str = Field(min_length=1)


class AIStatisticsAttachmentOutput(MessageSchema):
    """Agent 最后闭合消息全文；后端不解释格式或前端渲染协议。"""

    content: str = Field(min_length=1)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        """仅检查非空与独立 UTF-8 预算，逐字返回原文。"""
        if not value.strip():
            raise ValueError("statistics content must not be blank")
        if len(value.encode("utf-8")) > settings.AI_ASSISTANT_AI_STATISTICS_CONTENT_MAX_BYTES:
            raise ValueError("statistics content exceeds maximum")
        return value
