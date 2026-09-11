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
    "UserIntentContextSchema",
    "UserIntentErrorSchema",
    "UserIntentInputSchema",
    "UserIntentOutputSchema",
]

# 嵌套 query 模型 / 宽松集合的统一 DRF 表达（运行时校验仍走 Pydantic 嵌套模型）
_NestedListField = serializers.ListField(child=serializers.DictField())
_NestedObjectField = serializers.DictField()
_NestedObjectOrNullField = serializers.DictField(allow_null=True)


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
    # 引导卡显隐（编排链路专用：复合意图「切系统+检索」自动创建的 SELECTION 传 False——
    # 本轮仅展示日志检索消息，设计侧要求；前端手选系统不传，默认 True 展示引导卡。
    # 随 input 快照固化，刷新/重试/编辑后前端仍可按 output.show_guide 恢复显隐）
    show_guide: bool = True

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
    # 引导卡显隐（由 input.show_guide 透传固化；历史快照缺省 True = 展示，兼容不回退）：
    # 前端以此字段控制 retrieval-guide 卡显示/隐藏，替代内存态 hiddenGuideMessageIds
    # （刷新即丢，曾致复合意图刷新后引导卡重现的 bug）
    show_guide: bool = True


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


class UserIntentContextSchema(MessageSchema):
    """USER_INTENT 上下文：意图识别前系统未定，无 system_selection（任务内按路由结果加载）。"""

    username: str
    namespace: str
    # session scope（前端左上角场景过滤器当前选择）随消息快照固化：
    # 任务内 SYSTEM_REQUIRED 引导、select_system 路由校验、按需建 SYSTEM_SELECTION
    # 都按此 scope 收窄，与前端 UI 可见系统保持一致
    scope_type: str = ""
    scope_id: str = ""


class UserIntentErrorSchema(MessageSchema):
    """USER_INTENT 结构化错误协议：与 NL error 同构（error_code + AI 动态 error_message）
    + 候选系统清单（SYSTEM_REQUIRED 引导补系统时携带）。"""

    error_code: str  # UNRECOGNIZED_INTENT / SYSTEM_REQUIRED / QUERY_NOT_RECOGNIZED
    error_message: str
    candidates: Annotated[list, _NestedListField] = Field(default_factory=list)


class UserIntentOutputSchema(MessageSchema):
    """USER_INTENT 输出：condition/error 与 NL 输出同构（前端卡片渲染复用 NL 逻辑），
    附加意图扩展字段（intent/system_id/message/子消息锚点，前端渐进增强）。"""

    intent: str = ""
    system_id: str = ""
    message: str = ""
    condition: Annotated[SearchCondition | None, _NestedObjectOrNullField] = None
    error: UserIntentErrorSchema | None = None
    selection_message_uid: str = ""
    log_search_message_uid: str = ""

    @model_validator(mode="after")
    def _validate_payload_exclusive(self) -> "UserIntentOutputSchema":
        """condition 与 error 互斥且至多其一：均识别成功带 condition；识别失败带错误协议；
        纯切换（select_system 无检索诉求，need_search=false）两者皆空，仅携带
        message 与切换结果（selection_message_uid）。"""

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
