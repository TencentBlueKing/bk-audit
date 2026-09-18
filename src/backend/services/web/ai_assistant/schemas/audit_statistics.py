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

    field: Annotated[LogFieldRef, serializers.DictField()] = Field(
        description='待统计的通用字段或 JSON 子路径；field_type 仅为提示，实际类型由服务端确定。'
    )
    top_n: int = Field(
        default=10,
        strict=True,
        ge=1,
        le=AGGREGATION_MAX_TOP_N,
        description='非缺失类别上限，默认 10、协议最大 500，部署配置可收紧；OTHER/MISSING 不占名额。',
    )
    interval: AggregationTimeInterval = Field(
        default=AggregationTimeInterval.AUTO, description='时间桶粒度，默认 AUTO，由服务端按检索范围及预算选择。'
    )

    @model_validator(mode="before")
    @classmethod
    def apply_default_top_n(cls, data):
        """仅新输入缺省时读取共享配置；显式值及持久化快照保持不变。"""
        if isinstance(data, dict) and "top_n" not in data:
            return {**data, "top_n": settings.AI_LOG_AGGREGATION_DEFAULT_TOP_N}
        return data

    @model_validator(mode="after")
    def validate_budget(self):
        """创建时即拒绝超出部署预算的请求，不产生无效附件。"""
        if not 1 <= self.top_n <= min(settings.AI_LOG_AGGREGATION_MAX_TOP_N, AGGREGATION_MAX_TOP_N):
            raise ValueError("statistics top_n exceeds maximum")
        return self


class FieldStatisticsAttachmentContext(MessageSchema):
    """服务端固化的可重放查询上下文，不存预览样例和客户端类型声明。"""

    search_condition: Annotated[AgentSearchCondition, serializers.DictField()] = Field(
        description='来源成功检索的条件快照；程序统计严格复用该范围。'
    )
    field: Annotated[StatisticsField, serializers.DictField()] = Field(description='服务端解析并固化的字段标识和展示名。')
    top_n: int = Field(ge=1, le=AGGREGATION_MAX_TOP_N, description='创建时确认的非缺失类别上限；执行时仍校验运行预算。')
    interval: AggregationTimeInterval = Field(description='创建时固化的请求时间粒度，允许 AUTO。')
    username: str = Field(min_length=1, description='服务端固化的执行用户；执行时仍按该用户重新鉴权，不接受客户端覆盖。')
    namespace: str = Field(min_length=1, description='服务端固化的租户命名空间。')
    timezone: str = Field(min_length=1, description='服务端固化的用户时区，用于解释时间条件与划分时间桶。')


class FieldStatisticsAttachmentOutput(MessageSchema, FieldStatisticsResult):
    """保存程序统计固定包；OpenAPI 直接引用 Pydantic 模型以保留嵌套协议。"""

    field: Annotated[StatisticsField, serializers.DictField()] = Field(description='服务端解析的字段标识与展示名。')
    overview: Annotated[FieldStatisticsOverview, serializers.DictField()] = Field(description='完整检索范围的存在性概览。')
    distribution: Annotated[FieldDistribution, serializers.DictField()] = Field(
        description='全范围 TopN 类别及实际存在的 OTHER/MISSING。'
    )
    time_series: Annotated[FieldTimeSeries, serializers.DictField()] = Field(description='与分布共享类别的完整时间序列，空桶计数为 0。')
    numeric_summary: Annotated[FieldNumericSummary | None, serializers.DictField(allow_null=True)] = Field(
        description='NUMERIC 包的全范围原生数值摘要；CATEGORICAL 为 null。'
    )
    query_summary: Annotated[AggregationQuerySummary, serializers.DictField()] = Field(
        description='实际执行范围、时间和预算信息，不代表分页。'
    )

    @field_validator("distribution", mode="before")
    @classmethod
    def restore_distribution(cls, value):
        """以 JSON 协议恢复严格 typed 类别，避免数据库回读把合法枚举字符串拒绝。"""
        if isinstance(value, dict):
            return FieldDistribution.model_validate_json(json.dumps(value))
        return value


class AIStatisticsAttachmentInput(MessageSchema):
    """用户统计指令；来源和身份只能由后端填充。"""

    instruction: str = Field(
        min_length=1,
        max_length=settings.AI_ASSISTANT_AI_STATISTICS_INSTRUCTION_MAX_LENGTH,
        description='用户自定义统计需求，禁止纯空白；原文传给统计 Agent，长度受部署配置限制。',
    )

    @field_validator("instruction")
    @classmethod
    def validate_instruction(cls, value: str) -> str:
        """拒绝纯空白指令，保留有效用户输入。"""
        if not value.strip():
            raise ValueError("statistics instruction must not be blank")
        return value


class AIStatisticsQuerySummary(MessageSchema):
    """仅描述原检索的轻量概览，不代表 Agent 调整后的统计范围。"""

    total: int = Field(ge=0, description='来源检索命中的日志总数；不代表 Agent 最终统计范围或数量。')
    executed_at: str = Field(description='来源检索的执行时间，ISO 8601 时间字符串。')


class AIStatisticsAttachmentContext(MessageSchema):
    """创建时固化最小初始上下文；Agent 可以按需求调整实际工具查询范围。"""

    system_prompt: str = Field(min_length=1, description='服务端固化的统计 Agent 系统提示词，约束工具使用与权限边界。')
    instruction: str = Field(min_length=1, description='创建时固化的用户统计需求原文。')
    initial_search_condition: Annotated[AgentSearchCondition, serializers.DictField()] = Field(
        description='来源检索的初始上下文；Agent 可按需求调整范围，工具每次调用仍独立鉴权。'
    )
    query_summary: AIStatisticsQuerySummary = Field(description='来源检索的轻量概览，不含日志样本。')
    username: str = Field(min_length=1, description='服务端固化的执行用户；执行时仍按该用户重新鉴权，不接受客户端覆盖。')
    namespace: str = Field(min_length=1, description='服务端固化的租户命名空间。')
    timezone: str = Field(min_length=1, description='服务端固化的用户时区，用于解释时间条件与划分时间桶。')
    language: str = Field(min_length=1, description='用户语言偏好，作为 Agent 输出语言上下文。')


class AIStatisticsAttachmentOutput(MessageSchema):
    """Agent 最后闭合消息全文；后端不解释格式或前端渲染协议。"""

    content: str = Field(min_length=1, description='Agent 最后闭合消息的完整原文；后端不解析图表标识或 ECharts 协议。非空且 UTF-8 字节数受部署配置限制。')

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        """仅检查非空与独立 UTF-8 预算，逐字返回原文。"""
        if not value.strip():
            raise ValueError("statistics content must not be blank")
        if len(value.encode("utf-8")) > settings.AI_ASSISTANT_AI_STATISTICS_CONTENT_MAX_BYTES:
            raise ValueError("statistics content exceeds maximum")
        return value
