# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the specific language governing
permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

# AI 助手组件异常定义：error_code 与平台错误码对齐；error_message 只承载
# 用户可读的脱敏摘要，prompt / 字段上下文 / AI 原始输出一律不进入 message。

from django.utils.translation import gettext_lazy

from apps.exceptions import CoreException


class AIAssistantError(Exception):
    """AI 助手业务异常基类"""

    error_code = "AI_SERVICE_ERROR"
    error_message = "AI 服务异常，请稍后重试"

    def __init__(self, message: str = None, error_code: str = None, extra: dict = None):
        self.message = message or self.error_message
        if error_code:
            self.error_code = error_code
        self.extra = extra or {}
        super().__init__(self.message)

    def __str__(self):
        return f"[{self.error_code}] {self.message}"


class QueryNotRecognizedError(AIAssistantError):
    """无法从输入中识别出有效的检索条件"""

    error_code = "QUERY_NOT_RECOGNIZED"
    error_message = "未能理解检索需求，请换一种描述或补充关键信息"


class AIOutputParseFailedError(AIAssistantError):
    """AI 返回内容不是合法 JSON 或契约结构"""

    error_code = "AI_OUTPUT_PARSE_FAILED"
    error_message = "AI 返回内容解析失败"


class AIOutputInvalidError(AIAssistantError):
    """AI 输出通过基础解析但不符合当前业务协议。"""

    error_code = "AI_OUTPUT_INVALID"
    error_message = "AI 生成的内容不合法"


class InvalidConditionError(AIAssistantError):
    """Agent 条件结构或确定性条件规则不合法。"""

    error_code = "INVALID_CONDITION"
    error_message = "检索条件暂不支持，请调整字段、操作符或条件值"


class AIServiceError(AIAssistantError):
    """AIDev 调用返回错误（5xx / 网络错误）；error_code 沿用基类默认 AI_SERVICE_ERROR"""

    error_message = "AI 服务调用失败，请稍后重试"


class AITimeoutError(AIAssistantError):
    """AIDev 调用超时"""

    error_code = "AI_TIMEOUT"
    error_message = "AI 服务响应超时，请稍后重试"


class AIPermissionDeniedError(AIAssistantError):
    """无对应系统的日志检索权限"""

    error_code = "PERMISSION_DENIED"
    error_message = "无目标系统的日志检索权限"


class LogToolException(CoreException):
    """Agent/MCP 日志工具异常基类，公开消息不能由底层异常覆盖。"""

    MODULE_CODE = "26"

    def __init__(self, *args, **kwargs):
        # 查询条件和底层服务异常只允许留在日志上下文，不能进入对外响应。
        super().__init__(message=self.MESSAGE)


class InvalidLogCondition(LogToolException):
    """日志工具请求条件不合法。"""

    ERROR_CODE = "001"
    STATUS_CODE = 400
    MESSAGE = gettext_lazy("日志查询条件不合法")


class UnsupportedLogField(LogToolException):
    """日志工具不支持请求的字段。"""

    ERROR_CODE = "002"
    STATUS_CODE = 400
    MESSAGE = gettext_lazy("不支持的日志字段")


class UnsupportedAggregation(LogToolException):
    """日志工具不支持请求的聚合方式。"""

    ERROR_CODE = "003"
    STATUS_CODE = 400
    MESSAGE = gettext_lazy("不支持的日志聚合方式")


class InvalidAggregationColumnId(UnsupportedAggregation):
    """保留或重复列 ID 的固定修正提示，沿用聚合参数错误码。"""

    MESSAGE = gettext_lazy(
        "维度和指标 id 必须全局唯一，不能使用 group_id、group_kind、log_count、log_ratio、bucket_start；" "计数指标请使用 cnt 或 events 作为 id"
    )


class UnsupportedLogFieldOperator(UnsupportedLogField):
    """操作符错误与字段不存在分开提示，不回显用户条件。"""

    MESSAGE = gettext_lazy("该字段不支持此 operator；请使用字段目录 allow_operators 中的值，" "不要假定 eq 对所有字段可用；修正操作符后重试，无需重复获取已有字段目录")


class InvalidDistinctOptions(UnsupportedAggregation):
    """去重不接受数值转换参数，提示移除而非反复尝试字段类型。"""

    MESSAGE = gettext_lazy("DISTINCT_COUNT 只需 id、type、field；请省略 value_type 和 percentile")


class InvalidAggregationRanking(UnsupportedAggregation):
    """类别排名与时间排序分离，沿用聚合参数错误码。"""

    MESSAGE = gettext_lazy("order_by 仅控制类别 TopN 排名，不能引用 TIME_BUCKET；时间桶自动升序。" "无 FIELD 类别时必须省略 top_n 和 order_by")


class SensitiveFieldPermissionDenied(LogToolException):
    """当前用户无敏感字段查询权限。"""

    ERROR_CODE = "004"
    STATUS_CODE = 403
    MESSAGE = gettext_lazy("无敏感字段查询权限")


class LogQueryTimeout(LogToolException):
    """日志工具查询超时。"""

    ERROR_CODE = "005"
    STATUS_CODE = 504
    MESSAGE = gettext_lazy("日志查询超时，请稍后重试")


class LogQueryFailed(LogToolException):
    """日志工具查询失败。"""

    ERROR_CODE = "006"
    STATUS_CODE = 502
    MESSAGE = gettext_lazy("日志查询失败，请稍后重试")


class LogQueryResponseTooLarge(LogToolException):
    """日志工具响应超过协议字节预算。"""

    ERROR_CODE = "007"
    STATUS_CODE = 413
    MESSAGE = gettext_lazy("日志查询结果过大，请缩小字段或 page_size 后重试")


class UnsupportedFieldType(LogToolException):
    """全范围字段类型不支持请求的统计操作。"""

    ERROR_CODE = "008"
    STATUS_CODE = 400
    DOMAIN_CODE = "UNSUPPORTED_FIELD_TYPE"
    MESSAGE = gettext_lazy("字段类型不支持当前统计操作")


class StatisticsBudgetExceeded(LogToolException):
    """完整统计超出桶数或单元格预算，只返回受控调整建议。"""

    ERROR_CODE = "009"
    STATUS_CODE = 400
    DOMAIN_CODE = "STATISTICS_BUDGET_EXCEEDED"
    MESSAGE = gettext_lazy("统计结果超出预算，请调整查询范围、类别数量或指标")

    def __init__(self, *args, suggested_interval=None, **kwargs):
        """接收可用实际粒度；任意底层消息与自定义 data 不进入公开响应。"""
        super().__init__()
        self.data = {
            "suggested_interval": suggested_interval if suggested_interval in {"MINUTE", "HOUR", "DAY"} else None,
            "adjustments": ["缩短查询时间范围", "降低 top_n", "减少指标数量"],
        }


class StatisticsResponseTooLarge(LogToolException):
    """完整统计结构化 JSON 超出统一响应字节预算。"""

    ERROR_CODE = "010"
    STATUS_CODE = 413
    DOMAIN_CODE = "STATISTICS_RESPONSE_TOO_LARGE"
    MESSAGE = gettext_lazy("统计结果过大，请缩短查询范围或降低 top_n")
