"""统计附件的持久化协议。

程序统计只接收字段与预算；查询范围和显示信息由成功检索来源重建。
输出复用查询领域固定包，不在附件层引入图表结构。
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
