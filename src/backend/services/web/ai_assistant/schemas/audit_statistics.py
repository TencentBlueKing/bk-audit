"""统计附件的持久化协议。

程序统计接收字段、粒度与可选完整范围；默认范围来自成功检索来源。
程序输出复用查询领域固定包，AI 输出保存原文，不在附件层引入图表结构。
"""

import json
from typing import Annotated

from django.conf import settings
from pydantic import Field, field_validator
from rest_framework import serializers

from services.web.ai_assistant.schemas.log_attachment import LogAttachmentInput
from services.web.ai_assistant.schemas.message import MessageSchema
from services.web.query.ai_assistant.log_tools.field_statistics_schemas import (
    FieldDistribution,
    FieldNumericSummary,
    FieldStatisticsOverview,
    FieldStatisticsQuerySummary,
    FieldStatisticsResult,
    FieldTimeSeries,
    StatisticsField,
)
from services.web.query.ai_assistant.log_tools.schemas import (
    AgentSearchCondition,
    AggregationTimeInterval,
    LogFieldRef,
)


class FieldStatisticsAttachmentInput(LogAttachmentInput):
    """目录字段或用户自定义路径与统计参数；无需先调用字段探索，类型由全范围判定。"""

    field: Annotated[LogFieldRef, serializers.DictField()] = Field(
        description=(
            '待统计的通用字段或自定义JSON对象路径，不要求出现在采样目录中；'
            '例如 {"raw_name":"extend_data","keys":["a","b","c"]}。'
            'raw_name 为已知日志根字段；JSON 子键按层级传 keys，不能传 SQL 表达式或数组下标；'
            'field_type 可省略，实际类型由服务端确定。'
        )
    )
    interval: AggregationTimeInterval = Field(
        default=AggregationTimeInterval.AUTO,
        description='时间桶粒度 MINUTE/HOUR/DAY/MONTH，默认 AUTO 按完整范围从月到分钟选首个达到桶数阈值的粒度（默认12，后端可配置）；容量独立检查。',
    )


class FieldStatisticsAttachmentContext(MessageSchema):
    """服务端固化的可重放查询上下文，不存预览样例和客户端类型声明。"""

    search_condition: Annotated[AgentSearchCondition, serializers.DictField()] = Field(
        description='当前附件有效的独立条件快照；执行时重新鉴权。'
    )
    field: Annotated[StatisticsField, serializers.DictField()] = Field(description='服务端解析并固化的字段标识和展示名。')
    interval: AggregationTimeInterval = Field(description='创建时固化的请求时间粒度，允许 AUTO。')
    username: str = Field(min_length=1, description='服务端固化的执行用户；执行时仍按该用户重新鉴权，不接受客户端覆盖。')
    namespace: str = Field(min_length=1, description='服务端固化的租户命名空间。')
    timezone: str = Field(min_length=1, description='服务端固化的用户时区，用于解释时间条件与划分时间桶。')


class FieldStatisticsAttachmentOutput(MessageSchema, FieldStatisticsResult):
    """保存程序统计固定包；OpenAPI 直接引用 Pydantic 模型以保留嵌套协议。"""

    field: Annotated[StatisticsField, serializers.DictField()] = Field(description='服务端解析的字段标识与展示名。')
    overview: Annotated[FieldStatisticsOverview, serializers.DictField()] = Field(description='完整检索范围的存在性概览。')
    distribution: Annotated[FieldDistribution, serializers.DictField()] = Field(
        description='完整真实类别及实际 MISSING，不合并 OTHER。'
    )
    time_series: Annotated[FieldTimeSeries, serializers.DictField()] = Field(description='与分布共享类别的完整时间序列，空桶计数为 0。')
    numeric_summary: Annotated[FieldNumericSummary | None, serializers.DictField(allow_null=True)] = Field(
        description='NUMERIC 包的全范围原生数值摘要；CATEGORICAL 为 null。'
    )
    query_summary: Annotated[FieldStatisticsQuerySummary, serializers.DictField()] = Field(
        description='实际执行范围、时间和预算信息，不代表分页。'
    )

    @field_validator("distribution", mode="before")
    @classmethod
    def restore_distribution(cls, value):
        """以 JSON 协议恢复严格 typed 类别，避免数据库回读把合法枚举字符串拒绝。"""
        if isinstance(value, dict):
            return FieldDistribution.model_validate_json(json.dumps(value))
        return value


class AIStatisticsAttachmentInput(LogAttachmentInput):
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

    system_prompt: str = Field(min_length=1, description='服务端固化的统计 Agent 角色、能力与工作原则。')
    instruction: str = Field(min_length=1, description='创建时固化的用户统计需求原文。')
    initial_search_condition: Annotated[AgentSearchCondition, serializers.DictField()] = Field(
        description='当前附件有效的初始查询条件；Agent 可按需求调整范围，工具每次调用仍独立鉴权。'
    )
    query_summary: AIStatisticsQuerySummary | None = Field(
        default=None, description="条件与来源一致时的历史概览；覆盖条件不一致时为 null，不冒用来源计数。"
    )
    username: str = Field(min_length=1, description='服务端固化的执行用户；执行时仍按该用户重新鉴权，不接受客户端覆盖。')
    namespace: str = Field(min_length=1, description='服务端固化的租户命名空间。')
    timezone: str = Field(min_length=1, description='服务端固化的用户时区，用于解释时间条件与划分时间桶。')
    language: str = Field(min_length=1, description='用户语言偏好，作为 Agent 输出语言上下文。')


class AIStatisticsAttachmentOutput(MessageSchema):
    """输出 Schema 不解释已提取内容。"""

    content: str = Field(
        min_length=1,
        description=(
            "已提取的图表配置标签内原文；后端不解析图表标识或 ECharts 协议。"
            "任务层 UTF-8 字节预算作用在 Agent 最后闭合消息全文（含起止标签和标签外说明），"
            "超限会丢弃候选并表现为格式异常；本字段仍拒绝超出同一预算的内文。"
        ),
    )

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        """仅检查非空与独立 UTF-8 预算，逐字返回原文。"""
        if not value.strip():
            raise ValueError("statistics content must not be blank")
        if len(value.encode("utf-8")) > settings.AI_ASSISTANT_AI_STATISTICS_CONTENT_MAX_BYTES:
            raise ValueError("statistics content exceeds maximum")
        return value
