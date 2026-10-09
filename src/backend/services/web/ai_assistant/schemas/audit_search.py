"""审计日志检索三类消息的平台协议模型。

稳定键与《开发设计方案（总）》§7.2 对齐；字段上下文、检索条件和检索快照
的内部结构直接复用 query 模块的类型化模型（协议「零转换」原则）。

嵌套 query 模型含 ``Any`` 字段，drf_pydantic 无法自动转换 DRF serializer。
检索条件用显式嵌套 Serializer 展开 OpenAPI；其余嵌套对象仍用宽松 DictField。
运行时校验一律走 Pydantic，不把 OpenAPI 枚举当成请求校验。
"""

from typing import Annotated, Any, Literal

from pydantic import Field, model_validator
from rest_framework import serializers

from core.sql.constants import FieldType
from services.web.ai_assistant.schemas.message import MessageSchema
from services.web.query.ai_assistant.schemas import (
    LogSearchOutput,
    MessagePlan,
    QuerySummary,
    ResultColumn,
    SearchCondition,
    SelectionFieldMeta,
    SelectionSystem,
)
from services.web.query.utils.search_config import QueryConditionOperator

__all__ = [
    "CommonQuerySchema",
    "DerivedMessageSummarySchema",
    "LogSearchContextSchema",
    "LogSearchInputSchema",
    "LogSearchOutputSchema",
    "SystemSelectionContextSchema",
    "SystemSelectionInputSchema",
    "SystemSelectionOutputSchema",
    "UserIntentContextSchema",
    "UserIntentAgentTraceSchema",
    "UserIntentErrorSchema",
    "UserIntentInputSchema",
    "UserIntentOutputSchema",
]

# 嵌套 query 模型 / 宽松集合的统一 DRF 表达（运行时校验仍走 Pydantic 嵌套模型）
_NestedListField = serializers.ListField(child=serializers.DictField())
_NestedObjectField = serializers.DictField()
_NestedObjectOrNullField = serializers.DictField(allow_null=True)

_OPERATOR_HELP = "查询执行层全局操作符。各字段实际可用集合是动态 allow_operators，" "本枚举不是字段白名单。"
_FILTERS_HELP = "isnull/notnull 的 filters 必须为空数组；between 必须恰好 2 个值；其余操作符至少一个值。"
_TIME_HELP = "手工创建 LOG_SEARCH 时必填；ISO8601 带时区，或 YYYY-MM-DD HH:mm:ss。"


class _ConditionFieldSerializer(serializers.Serializer):
    raw_name = serializers.CharField()
    field_type = serializers.ChoiceField(choices=FieldType.choices, required=False)
    keys = serializers.ListField(child=serializers.CharField(), required=False)


class _ConditionItemSerializer(serializers.Serializer):
    field = _ConditionFieldSerializer()
    operator = serializers.ChoiceField(choices=QueryConditionOperator.choices, help_text=_OPERATOR_HELP)
    filters = serializers.ListField(child=serializers.JSONField(), required=False, help_text=_FILTERS_HELP)


class _SearchConditionSerializer(serializers.Serializer):
    scope_type = serializers.ChoiceField(choices=[("system", "系统")], default="system")
    scope_id = serializers.CharField()
    start_time = serializers.CharField(help_text=_TIME_HELP)
    end_time = serializers.CharField(help_text=_TIME_HELP)
    conditions = _ConditionItemSerializer(many=True, required=False)


_SearchConditionField = _SearchConditionSerializer()
_SearchConditionOrNullField = _SearchConditionSerializer(allow_null=True)
_USER_INTENT_CANDIDATES_DESCRIPTION = (
    "当前范围内可选系统列表，元素为 {system_id, name}；SYSTEM_REQUIRED 和 SYSTEM_UNAVAILABLE 时可用于选择引导，" "其他错误通常为空数组。"
)
_UserIntentCandidatesField = serializers.ListField(
    child=serializers.DictField(),
    help_text=_USER_INTENT_CANDIDATES_DESCRIPTION,
)


class CommonQuerySchema(MessageSchema):
    """常见/历史操作条目：自然语言检索样例（D3 方案）。"""

    query_text: str = Field(min_length=1, max_length=2048)


class SystemSelectionInputSchema(MessageSchema):
    """系统选择输入：协议按集合表达，一期限定单系统；会话 scope 从 Conversation 获取。"""

    system_ids: list[str] = Field(min_length=1, max_length=1)


class SystemSelectionContextSchema(MessageSchema):
    """系统选择服务端上下文；scope 固化自所属 Conversation。"""

    username: str
    namespace: str
    # 服务端快照供执行链路使用，创建/编辑时始终从所属 Conversation 重建。
    scope_type: str = ""
    scope_id: str = ""


class SystemSelectionOutputSchema(MessageSchema):
    """系统选择输出：字段上下文与操作上下文的完整快照。"""

    systems: Annotated[list[SelectionSystem], _NestedListField] = Field(default_factory=list)
    common_operations: list[CommonQuerySchema] = Field(default_factory=list)
    historical_operations: list[CommonQuerySchema] = Field(default_factory=list)


class UserIntentInputSchema(MessageSchema):
    """USER_INTENT 输入：只描述用户意图，会话 scope 从所属 Conversation 获取。"""

    query_text: str = Field(min_length=1, max_length=2048)
    auto_execute: bool = True


class UserIntentAgentTraceSchema(MessageSchema):
    """一次意图规划调用的可复现诊断快照，不参与消息执行或重投决策。"""

    status: Literal["processing", "success", "failed"] = Field(description="Agent 调用状态")
    agent_code: str = Field(description="实际调用的 Agent 标识")
    system_prompt: str = Field(description="通过 role 消息注入的完整系统提示词")
    user_prompt: str = Field(description="发送给 Agent 的完整动态用户提示词")
    reference_time: str = Field(description="规划相对时间使用的带时区基准时间")
    plan: Annotated[MessagePlan | None, _NestedObjectOrNullField] = Field(
        default=None,
        description="通过输出协议校验后的消息计划；失败时为空",
    )
    attempt_count: int = Field(default=0, ge=0, description="本次任务已发起的 Agent 调用次数")
    duration_ms: int = Field(default=0, ge=0, description="从首次调用到结束的总耗时（毫秒）")
    error_code: str = Field(default="", description="失败时的稳定错误码")
    error_message: str = Field(default="", description="失败时的受控错误信息")
    reason: str = Field(default="", description="后端确定性校验失败原因")
    raw_output: str = Field(default="", description="无法解析时保留的 Agent 原始输出")


class UserIntentContextSchema(MessageSchema):
    """USER_INTENT 服务端上下文与 Agent 诊断快照；scope 固化自所属 Conversation。"""

    username: str
    namespace: str
    # 服务端执行上下文，创建/编辑时从 Conversation 读取并重新固化。
    scope_type: str = ""
    scope_id: str = ""
    agent_trace: Annotated[UserIntentAgentTraceSchema | None, _NestedObjectOrNullField] = None


class UserIntentErrorSchema(MessageSchema):
    """USER_INTENT 成功终态的业务错误协议，前端按 error_code 分支并展示安全文案。"""

    error_code: str = Field(
        description=(
            "稳定业务错误码：UNRECOGNIZED_INTENT、SYSTEM_REQUIRED、SYSTEM_UNAVAILABLE、INVALID_CONDITION、"
            "AI_OUTPUT_INVALID、PERMISSION_DENIED。"
            "前端必须按错误码选择交互，不得解析错误文案。"
        )
    )
    error_message: str = Field(description="经过后端控制和脱敏、适合向当前用户直接展示的业务提示；前端可直接展示，但不得据此判断错误类型。")
    candidates: Annotated[list, _UserIntentCandidatesField] = Field(
        default_factory=list,
        description=_USER_INTENT_CANDIDATES_DESCRIPTION,
    )


class DerivedMessageSummarySchema(MessageSchema):
    """USER_INTENT 按计划顺序生成的业务消息摘要。"""

    message_uid: str = Field(description="派生业务消息 UID")
    message_type: Literal["SYSTEM_SELECTION", "LOG_SEARCH"] = Field(description="派生业务消息类型")
    status: str = Field(description="派生业务消息执行状态")
    visible: bool = Field(description="前端是否展示该消息卡片")


class UserIntentOutputSchema(MessageSchema):
    """USER_INTENT 输出：新链路以派生消息摘要为主，旧字段保留用于历史快照和条件预览。"""

    intent: str = ""
    system_id: str = ""
    message: str = ""
    condition: Annotated[SearchCondition | None, _SearchConditionOrNullField] = None
    # 相对时间窗快捷标记（条件预览的动态标签）：与 condition 平级，语义见 LogSearchInputSchema
    time_shortcut: str | None = None
    error: UserIntentErrorSchema | None = None
    selection_message_uid: str = ""
    log_search_message_uid: str = ""
    derived_messages: list[DerivedMessageSummarySchema] = Field(
        default_factory=list,
        description="按消息计划顺序排列的派生业务消息；历史输出缺失时为空数组",
    )

    @model_validator(mode="after")
    def _validate_payload_exclusive(self) -> "UserIntentOutputSchema":
        """condition 与 error 互斥；condition 仅用于 auto_execute=false 的条件预览。"""

        if self.condition is not None and self.error is not None:
            raise ValueError("USER_INTENT 输出不能同时携带 condition 和 error")
        return self


class LogSearchInputSchema(MessageSchema):
    """日志检索输入：结构化条件，字段条件检索与 NL 续链共用同一结构。"""

    condition: Annotated[SearchCondition, _SearchConditionField]
    # 相对时间窗快捷标记（如 "now-1d"，与前端 datetime_origin 快捷项语法同源）：
    # 仅 NL 链路携带——用户时间语义为相对表述（近N小时/近N天）或未提及时间（默认窗口）
    # 时由消息规划层写入，明确时间段为 None；字段条件检索不传。condition 里的
    # start_time/end_time 恒为换算后的绝对时间（查询/导出/报告依赖），本标记仅供
    # 前端渲染「近N天」标签并按执行时刻动态换算，不参与查询（故不放 SearchCondition——
    # 其子类 AgentSearchCondition 是 MCP 工具契约，definition.yaml 静态快照不包含该字段）
    time_shortcut: str | None = None


class LogSearchContextSchema(MessageSchema):
    """日志检索上下文：来源、目标系统与执行身份。"""

    username: str
    namespace: str
    system_id: str
    source: Literal["natural_language", "field_condition"] = "field_condition"
    # session scope 从所属 Conversation 获取并固化，供 LogSearchService 过滤 system_id。
    session_scope_type: str = ""
    session_scope_id: str = ""
    extension_fields: Annotated[list[SelectionFieldMeta], _NestedListField] = Field(
        default_factory=list,
        description="目标系统的拓展字段快照，供当前消息的标题和导出使用",
    )


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
