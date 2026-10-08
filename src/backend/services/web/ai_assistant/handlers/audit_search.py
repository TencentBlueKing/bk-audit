"""审计日志检索三类消息的业务处理器。

设计约定：
- SYSTEM_SELECTION 与 LOG_SEARCH 先持久化为 PROCESSING，再由各自任务独立收敛终态；
- 前端不传 parent 时，后端绑定当前会话最新成功 SYSTEM_SELECTION；
- SYSTEM_SELECTION 输出组装常见/历史操作上下文。
"""

from django.conf import settings
from pydantic import ValidationError

from apps.meta.permissions import SearchLogPermission
from services.web.ai_assistant.constants import (
    ExecutionMode,
    ExecutionStatus,
    MessageType,
)
from services.web.ai_assistant.exceptions import (
    InvalidMessageSnapshot,
    InvalidParentMessage,
    SystemSelectionPermissionDenied,
    SystemSelectionRequired,
)
from services.web.ai_assistant.handlers.message import (
    MessagePreparation,
    MessageTypeHandler,
)
from services.web.ai_assistant.handlers.registry import message_handler_registry
from services.web.ai_assistant.models import Conversation, Message
from services.web.ai_assistant.schemas.audit_search import (
    LogSearchContextSchema,
    LogSearchInputSchema,
    LogSearchOutputSchema,
    SystemSelectionContextSchema,
    SystemSelectionInputSchema,
    SystemSelectionOutputSchema,
    UserIntentContextSchema,
    UserIntentInputSchema,
    UserIntentOutputSchema,
)
from services.web.ai_assistant.services.column_preference import ColumnPreferenceService
from services.web.ai_assistant.services.operation import (
    OperationContextService,
    extract_system_ids,
)
from services.web.ai_assistant.tasks.audit_search import (
    execute_log_search,
    execute_system_selection,
    execute_user_intent,
)
from services.web.query.ai_assistant.exceptions import AIPermissionDeniedError
from services.web.query.ai_assistant.schemas import (
    SearchCondition,
    SystemSelectionOutput,
)
from services.web.query.ai_assistant.services.field_context import FieldContextService
from services.web.query.ai_assistant.services.log_search import LogSearchService


def resolve_selection_parent(*, user: str, conversation: Conversation, parent_message: Message | None) -> Message:
    """统一解析系统选择父消息（前端不传时后端取最新成功选择绑定）。

    显式传入时校验类型与状态；未传入时绑定当前会话内部 ID 最大的成功
    SYSTEM_SELECTION；不存在可绑定选择时返回稳定错误。
    """

    if parent_message is not None:
        if parent_message.message_type != MessageType.SYSTEM_SELECTION:
            raise InvalidParentMessage(message="父消息必须是系统选择消息")
        if parent_message.status != ExecutionStatus.SUCCESS:
            raise InvalidParentMessage(message="父消息必须执行成功")
        return parent_message
    latest_selection = (
        Message.objects.filter(
            conversation=conversation,
            created_by=user,
            message_type=MessageType.SYSTEM_SELECTION,
            status=ExecutionStatus.SUCCESS,
        )
        .order_by("-id")
        .first()
    )
    if latest_selection is None:
        raise SystemSelectionRequired()
    return latest_selection


def load_selection_snapshot(message: Message) -> SystemSelectionOutput:
    """从系统选择消息输出快照恢复字段上下文（最小充分上下文副本来源）。"""

    if not isinstance(message.output_data, dict) or not message.output_data:
        raise InvalidMessageSnapshot()
    try:
        return SystemSelectionOutput.model_validate(message.output_data)
    except ValidationError as error:
        raise InvalidMessageSnapshot() from error


def extract_selection_system_ids(message: Message) -> set[str]:
    """提取父消息绑定的系统集合（日志检索 scope 校验依据）。"""

    if message.message_type == MessageType.USER_INTENT:
        output_data = message.output_data if isinstance(message.output_data, dict) else {}
        system_id = str(output_data.get("system_id") or "")
        return {system_id} if system_id else set()
    else:
        output_data = message.output_data if isinstance(message.output_data, dict) else {}
        systems = output_data.get("systems") or []
    return extract_system_ids(systems)


class SystemSelectionHandler(
    MessageTypeHandler[SystemSelectionInputSchema, SystemSelectionContextSchema, SystemSelectionOutputSchema]
):
    """系统选择消息：构建字段上下文与操作上下文（根消息）。

    创建后返回 PROCESSING，由独立任务构建字段上下文；意图识别只负责创建计划消息。
    """

    message_type = MessageType.SYSTEM_SELECTION
    execution_mode = ExecutionMode.ASYNC
    input_model = SystemSelectionInputSchema
    context_model = SystemSelectionContextSchema
    output_model = SystemSelectionOutputSchema
    async_task = execute_system_selection

    def prepare(
        self,
        *,
        user: str,
        conversation: Conversation,
        parent_message: Message | None,
        input_data: SystemSelectionInputSchema,
    ) -> MessagePreparation[SystemSelectionContextSchema]:
        if parent_message is not None:
            if (
                parent_message.message_type != MessageType.USER_INTENT
                or parent_message.status != ExecutionStatus.SUCCESS
            ):
                raise InvalidParentMessage(message="系统选择只能作为根消息或成功意图识别消息的子消息")
        return MessagePreparation(
            parent_message=parent_message,
            context_data=SystemSelectionContextSchema(
                username=user,
                namespace=settings.DEFAULT_NAMESPACE,
                scope_type=conversation.scope_type,
                scope_id=conversation.scope_id,
            ),
        )

    def execute(self, *, input_data: SystemSelectionInputSchema, context_data: SystemSelectionContextSchema):
        # ① 严格按 session scope 收窄（与前端场景过滤器保持一致）：
        # 即便 has_system_search_permission 在 system 方向任一授权即通过（并集过宽），
        # 也必须校验 system_id 在 session scope 候选内——这是 AI 助手"场景内工具"的语义边界
        if context_data.scope_type:
            scoped_ids = set(
                SearchLogPermission.get_scope_auth_systems(
                    context_data.scope_type, context_data.scope_id, context_data.username
                )
            )
            scoped_ids.discard("")  # ES filter 兜底空串
            if not all(sid in scoped_ids for sid in input_data.system_ids):
                raise SystemSelectionPermissionDenied()
        try:
            selection = FieldContextService.build_selection(
                namespace=context_data.namespace,
                system_ids=input_data.system_ids,
                username=context_data.username,
            )
        except AIPermissionDeniedError as error:
            # 所选系统均无检索权限：转为平台稳定错误（403），不误报为 AI 识别失败
            raise SystemSelectionPermissionDenied() from error
        common_operations, historical_operations = OperationContextService.build(
            scope_type=context_data.scope_type,
            scope_id=context_data.scope_id,
            # 操作榜单按所选系统隔离（验收修复）：场景内多系统时各自系统的常用/历史操作
            # 互不串榜——用户在系统选择卡上看到的是该系统自己的高频与最近检索
            system_ids=input_data.system_ids,
            username=context_data.username,
        )
        return SystemSelectionOutputSchema(
            systems=selection.systems,
            common_operations=common_operations,
            historical_operations=historical_operations,
        )


class UserIntentHandler(MessageTypeHandler[UserIntentInputSchema, UserIntentContextSchema, UserIntentOutputSchema]):
    """用户意图识别消息：统一自然语言入口（新会话/中途均可，无父消息）。

    任务内由通用 Agent 一次生成系统选择、日志检索或二者组合，再由后端校验并按序
    创建派生消息；上下文不含 system_selection，任务运行时从会话读取当前选择。
    """

    message_type = MessageType.USER_INTENT
    execution_mode = ExecutionMode.ASYNC
    input_model = UserIntentInputSchema
    context_model = UserIntentContextSchema
    output_model = UserIntentOutputSchema
    # 与自然语言消息对齐：仅成功消息支持反馈
    supports_feedback = True
    async_task = execute_user_intent

    def prepare(
        self,
        *,
        user: str,
        conversation: Conversation,
        parent_message: Message | None,
        input_data: UserIntentInputSchema,
    ) -> MessagePreparation[UserIntentContextSchema]:
        # 入口消息无父：系统选择由任务内按意图识别结果创建/复用，prepare 阶段不做系统绑定
        if parent_message is not None:
            raise InvalidParentMessage(message="用户意图识别是入口消息，不能引用父消息")
        return MessagePreparation(
            parent_message=None,
            context_data=UserIntentContextSchema(
                username=user,
                namespace=settings.DEFAULT_NAMESPACE,
                scope_type=conversation.scope_type,
                scope_id=conversation.scope_id,
            ),
        )


class LogSearchHandler(MessageTypeHandler[LogSearchInputSchema, LogSearchContextSchema, LogSearchOutputSchema]):
    """日志检索消息：父消息为系统选择或用户意图消息。

    创建后返回 PROCESSING，由独立任务执行检索；意图识别不等待检索结果。
    """

    message_type = MessageType.LOG_SEARCH
    execution_mode = ExecutionMode.ASYNC
    input_model = LogSearchInputSchema
    context_model = LogSearchContextSchema
    output_model = LogSearchOutputSchema
    async_task = execute_log_search

    def prepare(
        self,
        *,
        user: str,
        conversation: Conversation,
        parent_message: Message | None,
        input_data: LogSearchInputSchema,
    ) -> MessagePreparation[LogSearchContextSchema]:
        parent = self._resolve_parent(user=user, conversation=conversation, parent_message=parent_message)
        self._validate_scope(parent=parent, condition=input_data.condition)
        # 父消息仅提供已选择系统，不作为会话范围事实来源。
        session_scope_type = conversation.scope_type
        session_scope_id = conversation.scope_id
        # 用户意图续链的条件由 AI 识别；field_condition 仅用户直接发起的条件检索
        source = "natural_language" if parent.message_type == MessageType.USER_INTENT else "field_condition"
        return MessagePreparation(
            parent_message=parent,
            context_data=LogSearchContextSchema(
                username=user,
                namespace=settings.DEFAULT_NAMESPACE,
                system_id=input_data.condition.scope_id,
                source=source,
                session_scope_type=session_scope_type,
                session_scope_id=session_scope_id,
                extension_fields=self._load_extension_fields(
                    user=user,
                    parent=parent,
                    system_id=input_data.condition.scope_id,
                ),
            ),
        )

    def execute(self, *, input_data: LogSearchInputSchema, context_data: LogSearchContextSchema):
        """在异步任务中执行检索；异常由统一任务基类写入当前消息失败状态。"""

        output = LogSearchService.search(
            condition=input_data.condition,
            namespace=context_data.namespace,
            username=context_data.username,
            source=context_data.source,
            # 展示列按用户偏好注入（九列固定 + 自选列，跨设备同步）
            column_fields=ColumnPreferenceService(username=context_data.username).get_selected_fields(),
            # session scope 透传给 LogSearchService：按此过滤 system_id，
            # 不再以 condition.scope_id 的 system 维度权限为兜底（避免跨场景越权）
            session_scope_type=context_data.session_scope_type,
            session_scope_id=context_data.session_scope_id,
            extension_fields=context_data.extension_fields,
        )
        return LogSearchOutputSchema.from_query_output(output)

    def _resolve_parent(self, *, user: str, conversation: Conversation, parent_message: Message | None) -> Message:
        """显式父消息须为成功的系统选择或用户意图消息；省略时兜底解析最新成功选择。"""

        if parent_message is not None:
            if parent_message.message_type not in (
                MessageType.SYSTEM_SELECTION,
                MessageType.USER_INTENT,
            ):
                raise InvalidParentMessage(message="日志检索的父消息必须是系统选择或用户意图消息")
            if parent_message.status != ExecutionStatus.SUCCESS:
                raise InvalidParentMessage(message="父消息必须执行成功")
            return parent_message
        return resolve_selection_parent(user=user, conversation=conversation, parent_message=None)

    @staticmethod
    def _load_extension_fields(*, user: str, parent: Message, system_id: str):
        """在创建时固化目标系统拓展字段，使 LOG_SEARCH 后续能力只读自身上下文。"""

        if parent.message_type == MessageType.SYSTEM_SELECTION:
            systems = load_selection_snapshot(parent).systems
        else:
            try:
                systems = FieldContextService.build_selection(
                    namespace=settings.DEFAULT_NAMESPACE,
                    system_ids=[system_id],
                    username=user,
                ).systems
            except AIPermissionDeniedError as error:
                raise SystemSelectionPermissionDenied() from error
        target = next((system for system in systems if system.system_id == system_id), None)
        if target is None:
            raise InvalidMessageSnapshot()
        return target.extension_fields

    @staticmethod
    def _validate_scope(*, parent: Message, condition: SearchCondition) -> None:
        """检索系统必须来自父消息绑定的系统选择，防止构造未选择系统的条件。"""

        selection_system_ids = extract_selection_system_ids(parent)
        if condition.scope_id not in selection_system_ids:
            raise InvalidParentMessage(message="检索系统与当前选择的系统不一致")


message_handler_registry.register(SystemSelectionHandler())
message_handler_registry.register(UserIntentHandler())
message_handler_registry.register(LogSearchHandler())
