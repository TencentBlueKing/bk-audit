"""审计日志检索三类消息的业务处理器。

设计约定：
- LOG_SEARCH 为 SYNC（成功才创建消息，失败抛异常不落库）；
- 前端不传 parent 时，后端绑定当前会话最新成功 SYSTEM_SELECTION；
- SYSTEM_SELECTION 输出组装常见/历史操作上下文。
"""

from django.conf import settings
from pydantic import ValidationError

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
    NLSearchContextSchema,
    NLSearchInputSchema,
    NLSearchOutputSchema,
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
    execute_natural_language_search,
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

    if message.message_type == MessageType.NATURAL_LANGUAGE_SEARCH:
        context_data = message.context_data if isinstance(message.context_data, dict) else {}
        systems = (context_data.get("system_selection") or {}).get("systems") or []
    elif message.message_type == MessageType.USER_INTENT:
        # 意图识别消息：路由结果系统在 output_data.system_id（条件识别即按该系统组装）
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

    一期全异步化：对外创建即返回 PROCESSING（前端轮询终态）；
    任务内编排（意图识别子链）经 MessageService.create_executed 同步执行保证时序。
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
            raise InvalidParentMessage(message="系统选择是根消息，不能引用父消息")
        return MessagePreparation(
            parent_message=None,
            context_data=SystemSelectionContextSchema(username=user, namespace=settings.DEFAULT_NAMESPACE),
        )

    def execute(self, *, input_data: SystemSelectionInputSchema, context_data: SystemSelectionContextSchema):
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

    任务内完成意图识别（选系统 / 日志检索 / 无法识别）→ 按需建/复用系统选择 →
    条件识别 → 续链日志检索；上下文不含 system_selection（意图识别前系统未定，
    任务内按路由结果加载，详见 execute_user_intent）。
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
            context_data=UserIntentContextSchema(username=user, namespace=settings.DEFAULT_NAMESPACE),
        )


class NaturalLanguageSearchHandler(
    MessageTypeHandler[NLSearchInputSchema, NLSearchContextSchema, NLSearchOutputSchema]
):
    """自然语言检索消息：异步识别条件；上下文从父系统选择消息复制。"""

    message_type = MessageType.NATURAL_LANGUAGE_SEARCH
    execution_mode = ExecutionMode.ASYNC
    input_model = NLSearchInputSchema
    context_model = NLSearchContextSchema
    output_model = NLSearchOutputSchema
    # 仅成功的自然语言消息支持反馈
    supports_feedback = True
    async_task = execute_natural_language_search

    def prepare(
        self,
        *,
        user: str,
        conversation: Conversation,
        parent_message: Message | None,
        input_data: NLSearchInputSchema,
    ) -> MessagePreparation[NLSearchContextSchema]:
        parent = resolve_selection_parent(user=user, conversation=conversation, parent_message=parent_message)
        selection = load_selection_snapshot(parent)
        system_ids = [system.system_id for system in selection.systems]
        if not system_ids:
            raise InvalidMessageSnapshot()
        return MessagePreparation(
            parent_message=parent,
            context_data=NLSearchContextSchema(
                username=user,
                namespace=settings.DEFAULT_NAMESPACE,
                scope_id=system_ids[0],
                system_selection=selection,
            ),
        )


class LogSearchHandler(MessageTypeHandler[LogSearchInputSchema, LogSearchContextSchema, LogSearchOutputSchema]):
    """日志检索消息：父消息为系统选择、自然语言或用户意图消息。

    一期全异步化：对外创建即返回 PROCESSING（前端轮询终态）；
    任务内编排（NL / 意图识别续链）经 MessageService.create_executed 同步执行保证时序。
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
        # 自然语言来源 = NL 或意图识别消息续链（条件由 AI 识别，非用户手选条件表单）；
        # field_condition 仅用户直接发起的条件检索（其标题走条件摘要派发）
        source = (
            "natural_language"
            if parent.message_type in (MessageType.NATURAL_LANGUAGE_SEARCH, MessageType.USER_INTENT)
            else "field_condition"
        )
        return MessagePreparation(
            parent_message=parent,
            context_data=LogSearchContextSchema(
                username=user,
                namespace=settings.DEFAULT_NAMESPACE,
                system_id=input_data.condition.scope_id,
                source=source,
            ),
        )

    def execute(self, *, input_data: LogSearchInputSchema, context_data: LogSearchContextSchema):
        """同步执行检索；执行失败直接抛出异常，消息不创建。"""

        output = LogSearchService.search(
            condition=input_data.condition,
            namespace=context_data.namespace,
            username=context_data.username,
            source=context_data.source,
            # 展示列按用户偏好注入（九列固定 + 自选列，跨设备同步）
            column_fields=ColumnPreferenceService(username=context_data.username).get_selected_fields(),
        )
        return LogSearchOutputSchema.from_query_output(output)

    def _resolve_parent(self, *, user: str, conversation: Conversation, parent_message: Message | None) -> Message:
        """显式父消息须为成功的系统选择、自然语言或用户意图消息；省略时兜底解析最新成功选择。"""

        if parent_message is not None:
            if parent_message.message_type not in (
                MessageType.SYSTEM_SELECTION,
                MessageType.NATURAL_LANGUAGE_SEARCH,
                MessageType.USER_INTENT,
            ):
                raise InvalidParentMessage(message="日志检索的父消息必须是系统选择、自然语言或用户意图消息")
            if parent_message.status != ExecutionStatus.SUCCESS:
                raise InvalidParentMessage(message="父消息必须执行成功")
            return parent_message
        return resolve_selection_parent(user=user, conversation=conversation, parent_message=None)

    @staticmethod
    def _validate_scope(*, parent: Message, condition: SearchCondition) -> None:
        """检索系统必须来自父消息绑定的系统选择，防止构造未选择系统的条件。"""

        selection_system_ids = extract_selection_system_ids(parent)
        if condition.scope_id not in selection_system_ids:
            raise InvalidParentMessage(message="检索系统与当前选择的系统不一致")


message_handler_registry.register(SystemSelectionHandler())
message_handler_registry.register(UserIntentHandler())
message_handler_registry.register(NaturalLanguageSearchHandler())
message_handler_registry.register(LogSearchHandler())
