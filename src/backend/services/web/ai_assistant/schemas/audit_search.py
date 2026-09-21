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
    MessagePlan,
    QuerySummary,
    ResultColumn,
    SearchCondition,
    SelectionFieldMeta,
    SelectionSystem,
    SystemSelectionOutput,
)

__all__ = [
    "CommonQuerySchema",
    "DerivedMessageSummarySchema",
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
    """系统选择输入：协议按集合表达，一期限定单系统。

    scope 双层校验：schema 层 scope_type 可选（宽松解析历史消息快照——协议
    升级前落库的 input_data 无该字段，消息列表/详情/重试不能因协议升级报错）；
    创建/编辑路径在 Handler.prepare 强制必填（AI 助手必须和前端左上角场景
    过滤器保持一致，scope 随消息快照固化后 NL/LOG_SEARCH 链路继承同一 session scope）。
    """

    system_ids: list[str] = Field(min_length=1, max_length=1)
    scope_type: Literal["cross_scene", "cross_system", "scene", "system"] | None = None
    scope_id: str = Field(default="", max_length=64)

    @model_validator(mode="after")
    def _validate_scope(self) -> "SystemSelectionInputSchema":
        """scope 协议约束：scene/system 必填 scope_id（与 ScopeContext 同源；None 跳过）。"""

        if self.scope_type in ("scene", "system") and not self.scope_id:
            raise ValueError("scope_type=scene/system 时 scope_id 为必传参数")
        return self


class SystemSelectionContextSchema(MessageSchema):
    """系统选择服务端上下文。"""

    username: str
    namespace: str
    # session scope 随消息快照固化（重试/编辑复用）；后续 NL/LOG_SEARCH 继承
    scope_type: str = ""
    scope_id: str = ""


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
    # session scope（从父 SELECTION 继承）固化到上下文：LOG_SEARCH 续链按此过滤
    session_scope_type: str = ""
    session_scope_id: str = ""


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


class UserIntentInputSchema(MessageSchema):
    """USER_INTENT 输入：与 NL 输入同构（前端提交参数零变化，仅 message_type 不同）。

    scope 双层校验：schema 层 scope_type 可选（宽松解析历史消息快照——协议
    升级前落库的 input_data 无该字段）；创建/编辑路径在 Handler.prepare 强制
    必填（不传 400），与前端左上角场景过滤器当前选择保持一致——AI 助手是
    场景内工具，必须明确场景才能工作。
    """

    query_text: str = Field(min_length=1, max_length=2048)
    auto_execute: bool = True
    scope_type: Literal["cross_scene", "cross_system", "scene", "system"] | None = None
    scope_id: str = Field(default="", max_length=64)

    @model_validator(mode="after")
    def _validate_scope(self) -> "UserIntentInputSchema":
        """scope 协议约束：scene/system 必填 scope_id（None 跳过，历史快照兼容）。"""

        if self.scope_type in ("scene", "system") and not self.scope_id:
            raise ValueError("scope_type=scene/system 时 scope_id 为必传参数")
        return self


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
    """USER_INTENT 自身执行所需上下文，以及不参与续链决策的 Agent 诊断快照。"""

    username: str
    namespace: str
    # session scope（前端左上角场景过滤器当前选择）随消息快照固化：
    # 任务内 SYSTEM_REQUIRED 引导、select_system 路由校验、按需建 SYSTEM_SELECTION
    # 都按此 scope 收窄，与前端 UI 可见系统保持一致
    scope_type: str = ""
    scope_id: str = ""
    agent_trace: Annotated[UserIntentAgentTraceSchema | None, _NestedObjectOrNullField] = None


class UserIntentErrorSchema(MessageSchema):
    """USER_INTENT 成功终态的业务错误协议，前端按 error_code 分支并展示安全文案。"""

    error_code: str = Field(
        description=(
            "稳定业务错误码。编排类：UNRECOGNIZED_INTENT、SYSTEM_REQUIRED、SYSTEM_UNAVAILABLE；"
            "条件识别类：QUERY_NOT_RECOGNIZED、AI_OUTPUT_PARSE_FAILED、AI_OUTPUT_INVALID、PERMISSION_DENIED。"
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
    condition: Annotated[SearchCondition | None, _NestedObjectOrNullField] = None
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

    condition: Annotated[SearchCondition, _NestedObjectField]


class LogSearchContextSchema(MessageSchema):
    """日志检索上下文：来源、目标系统与执行身份。"""

    username: str
    namespace: str
    system_id: str
    source: Literal["natural_language", "field_condition"] = "field_condition"
    # session scope（从父消息继承）固化到上下文：LogSearchService 按此过滤 system_id
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
