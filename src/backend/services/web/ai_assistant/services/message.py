import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, TypeVar
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone

from services.web.ai_assistant.constants import (
    ExecutionMode,
    ExecutionStatus,
    FeedbackSourceType,
    MessageErrorCode,
    MessageHistoryDirection,
    MessageType,
)
from services.web.ai_assistant.exceptions import (
    ConversationNotFound,
    InvalidInitialMessage,
    InvalidMessageAnchor,
    InvalidMessageState,
    InvalidParentMessage,
    MessageNotFound,
)
from services.web.ai_assistant.handlers import (
    MessageTypeHandler,
    message_handler_registry,
)
from services.web.ai_assistant.models import Attachment, Conversation, Message
from services.web.ai_assistant.schemas import (
    MessageSchema,
    dump_snapshot,
    parse_snapshot,
)
from services.web.ai_assistant.services.feedback import FeedbackService
from services.web.ai_assistant.services.message_execution import finish_message_failure

logger = logging.getLogger(__name__)

InputT = TypeVar("InputT", bound=MessageSchema)
ContextT = TypeVar("ContextT", bound=MessageSchema)
OutputT = TypeVar("OutputT", bound=MessageSchema)


@dataclass(frozen=True, slots=True)
class PreparedMessage:
    """Handler 已完成请求准备、可直接按执行方式持久化的标准快照。"""

    message_type: MessageType
    execution_mode: ExecutionMode
    parent_message: Message | None
    input_data: dict[str, Any]
    context_data: dict[str, Any]
    output_data: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class MessageWindow:
    """前端可直接向上或向下拼接的正序消息窗口。"""

    results: list[Message]
    first_uid: str | None
    last_uid: str | None
    has_before: bool
    has_after: bool
    include_content: bool


class MessageService:
    """在绑定用户边界内统一创建和准备消息，业务差异由 Handler 提供。"""

    def __init__(self, *, user: str):
        self.user = user

    def create(
        self,
        *,
        conversation: Conversation,
        message_type: str | MessageType,
        input_data: Mapping[str, Any],
        parent_message_uid: str | None = None,
    ) -> Message:
        """校验请求和业务上下文，并按 Handler 的执行方式创建消息。"""

        self._validate_conversation(conversation=conversation)
        parent_message = self._resolve_parent(
            conversation=conversation,
            parent_message_uid=parent_message_uid,
        )
        handler = message_handler_registry.require(message_type)

        prepared = self._prepare(
            conversation=conversation,
            handler=handler,
            input_data=input_data,
            parent_message=parent_message,
        )
        message = self.create_prepared(conversation=conversation, prepared=prepared)
        logger.info(
            "AI 助手消息创建完成",
            extra={
                "message_id": message.id,
                "message_type": str(handler.message_type),
                "execution_mode": str(handler.execution_mode),
                "status": message.status,
            },
        )
        return message

    def prepare_initial(
        self,
        *,
        conversation: Conversation,
        message_type: str | MessageType,
        input_data: Mapping[str, Any],
    ) -> PreparedMessage:
        """事务外准备会话初始化消息，并返回尚未落库的完整快照。"""

        if (
            conversation.pk is not None
            or conversation.created_by != self.user
            or message_type != MessageType.SYSTEM_SELECTION
        ):
            raise InvalidInitialMessage()
        handler = message_handler_registry.require(message_type)
        prepared = self._prepare(
            conversation=conversation,
            handler=handler,
            input_data=input_data,
            parent_message=None,
        )
        if prepared.parent_message is not None:
            raise InvalidInitialMessage(message="初始化消息不能引用父消息")
        return prepared

    def create_prepared(self, *, conversation: Conversation, prepared: PreparedMessage) -> Message:
        """持久化已准备的消息；异步消息在事务提交后投递业务 Task。"""

        self._validate_conversation(conversation=conversation)
        if prepared.execution_mode == ExecutionMode.ASYNC:
            handler = message_handler_registry.require(prepared.message_type)
            return self._create_async(
                conversation=conversation,
                handler=handler,
                parent_message=prepared.parent_message,
                input_snapshot=prepared.input_data,
                context_snapshot=prepared.context_data,
            )
        now = timezone.now()
        return Message.objects.create(
            conversation=conversation,
            parent_message=prepared.parent_message,
            message_type=prepared.message_type,
            status=ExecutionStatus.SUCCESS,
            input_data=prepared.input_data,
            context_data=prepared.context_data,
            output_data=prepared.output_data,
            last_activity_at=now,
            finished_at=now,
            created_by=self.user,
            updated_by=self.user,
        )

    def get(self, *, message_uid: str) -> Message:
        """按外部 UID 获取当前用户有效会话中的一条消息。"""

        try:
            message = self._visible_messages().filter(uid=message_uid).first()
        except DjangoValidationError as error:
            raise MessageNotFound() from error
        if message is None:
            raise MessageNotFound()
        FeedbackService(user=self.user).bind_current_feedback(sources=[message], source_type=FeedbackSourceType.MESSAGE)
        return message

    def list(
        self,
        *,
        conversation_uid: str,
        anchor_uid: str | None = None,
        direction: str | MessageHistoryDirection | None = None,
        limit: int | None = None,
        include_content: bool = True,
    ) -> MessageWindow:
        """按 UID 锚点读取一段消息；无锚点时从最新消息开始加载。"""

        if bool(anchor_uid) != bool(direction):
            raise InvalidMessageAnchor(message="anchor_uid 和 direction 必须同时传入")
        try:
            normalized_direction = MessageHistoryDirection(direction) if direction else None
        except ValueError as error:
            raise InvalidMessageAnchor() from error
        # Service 也约束窗口，防止内部业务绕过 HTTP Serializer 形成无界查询。
        limit = limit or settings.AI_ASSISTANT_MESSAGE_HISTORY_DEFAULT_LIMIT
        limit = min(max(limit, 1), settings.AI_ASSISTANT_MESSAGE_HISTORY_MAX_LIMIT)

        conversation = self._get_conversation(conversation_uid=conversation_uid)
        conversation_messages = self._visible_messages(conversation=conversation)
        anchor = None
        if anchor_uid is not None:
            try:
                # 锚点只用于获取内部递增 ID，不预取其附件，避免额外查询。
                anchor = conversation_messages.prefetch_related(None).filter(uid=anchor_uid).first()
            except DjangoValidationError as error:
                raise InvalidMessageAnchor() from error
            if anchor is None:
                raise InvalidMessageAnchor()

        if anchor is None:
            results = list(conversation_messages.order_by("-id")[:limit])
            results.reverse()
        elif normalized_direction == MessageHistoryDirection.BEFORE:
            results = list(conversation_messages.filter(id__lt=anchor.id).order_by("-id")[:limit])
            results.reverse()
        else:
            results = list(conversation_messages.filter(id__gt=anchor.id).order_by("id")[:limit])

        if results:
            first_id = results[0].id
            last_id = results[-1].id
            first_uid = str(results[0].uid)
            last_uid = str(results[-1].uid)
        elif anchor is not None:
            first_id = last_id = anchor.id
            first_uid = last_uid = None
        else:
            return MessageWindow(
                results=[],
                first_uid=None,
                last_uid=None,
                has_before=False,
                has_after=False,
                include_content=include_content,
            )

        FeedbackService(user=self.user).bind_current_feedback(sources=results, source_type=FeedbackSourceType.MESSAGE)

        return MessageWindow(
            results=results,
            first_uid=first_uid,
            last_uid=last_uid,
            has_before=conversation_messages.filter(id__lt=first_id).exists(),
            has_after=conversation_messages.filter(id__gt=last_id).exists(),
            include_content=include_content,
        )

    def retry(self, *, message_uid: str) -> Message:
        """复用失败异步消息的原快照，并以旧 task_id 原子抢占一次重试。"""

        message = self.get(message_uid=message_uid)
        handler = message_handler_registry.require(message.message_type)
        if (
            message.status != ExecutionStatus.FAILED
            or handler.execution_mode != ExecutionMode.ASYNC
            or not message.task_id
        ):
            raise InvalidMessageState()

        old_task_id = message.task_id
        new_task_id = str(uuid4())
        now = timezone.now()
        with transaction.atomic():
            updated = Message.restart_failed(
                instance_id=message.id,
                old_task_id=old_task_id,
                new_task_id=new_task_id,
                extra_updates={
                    "updated_by": self.user,
                    "updated_at": now,
                },
                now=now,
            )
            if not updated:
                raise InvalidMessageState()
            # 刷新后的同一实例既用于任务投递，也作为接口响应，避免暴露旧 task 状态。
            message.refresh_from_db()
            transaction.on_commit(lambda: self._dispatch(handler=handler, message=message))
        return message

    def _get_conversation(self, *, conversation_uid: str) -> Conversation:
        """独立校验会话归属，使不存在与空消息列表保持不同语义。"""

        try:
            conversation = Conversation.objects.filter(
                uid=conversation_uid,
                created_by=self.user,
                is_deleted=False,
            ).first()
        except DjangoValidationError as error:
            raise ConversationNotFound() from error
        if conversation is None:
            raise ConversationNotFound()
        return conversation

    def _visible_messages(self, *, conversation: Conversation | None = None):
        """构造统一用户边界的消息查询，并预取列表展示所需附件。"""

        # 消息接口只展示附件摘要，避免把 A2UI 结果和完整流归档读入历史列表内存。
        attachment_summaries = Attachment.objects.only(
            "id",
            "source_message_id",
            "uid",
            "attachment_type",
            "status",
            "title",
            "content_updated_at",
            "created_at",
        ).order_by("-id")
        filters: dict[str, Any] = {
            "created_by": self.user,
            "conversation__created_by": self.user,
            "conversation__is_deleted": False,
        }
        if conversation is not None:
            filters["conversation"] = conversation
        return (
            Message.objects.filter(**filters)
            .select_related("conversation", "parent_message")
            .prefetch_related(Prefetch("attachments", queryset=attachment_summaries))
        )

    def _validate_conversation(self, *, conversation: Conversation) -> None:
        """防御性校验会话存在、未删除且归属于当前用户。"""

        if (
            not self.user
            or conversation.created_by != self.user
            or conversation.is_deleted
            or not Conversation.objects.filter(id=conversation.id, created_by=self.user).exists()
        ):
            raise InvalidParentMessage(message="会话无效")

    def _resolve_parent(
        self,
        *,
        conversation: Conversation,
        parent_message_uid: str | None,
    ) -> Message | None:
        """解析前端显式传入的父消息，并完成用户和会话归属校验。"""

        if not parent_message_uid:
            return None
        try:
            parent_message = Message.objects.filter(
                uid=parent_message_uid,
                conversation=conversation,
                created_by=self.user,
            ).first()
        except DjangoValidationError as error:
            raise InvalidParentMessage() from error
        if parent_message is None:
            raise InvalidParentMessage()
        return parent_message

    def _prepare(
        self,
        *,
        conversation: Conversation,
        handler: MessageTypeHandler[InputT, ContextT, OutputT],
        input_data: Mapping[str, Any] | MessageSchema,
        parent_message: Message | None,
    ) -> PreparedMessage:
        """统一构造输入和上下文快照；同步 Handler 在此直接生成输出。"""

        parsed_input = parse_snapshot(handler.input_model, input_data, field_name="input_data")
        preparation = handler.prepare(
            user=self.user,
            conversation=conversation,
            parent_message=parent_message,
            input_data=parsed_input,
        )
        parsed_context = parse_snapshot(
            handler.context_model,
            preparation.context_data,
            field_name="context_data",
        )
        output_snapshot = None
        if handler.execution_mode == ExecutionMode.SYNC:
            output_data = handler.execute(input_data=parsed_input, context_data=parsed_context)
            output_snapshot = dump_snapshot(handler.output_model, output_data, field_name="output_data")
        return PreparedMessage(
            message_type=handler.message_type,
            execution_mode=handler.execution_mode,
            parent_message=preparation.parent_message,
            input_data=parsed_input.model_dump(mode="json"),
            context_data=parsed_context.model_dump(mode="json"),
            output_data=output_snapshot,
        )

    def _create_async(
        self,
        *,
        conversation: Conversation,
        handler: MessageTypeHandler,
        parent_message: Message | None,
        input_snapshot: dict[str, Any],
        context_snapshot: dict[str, Any],
    ) -> Message:
        """先持久化 PROCESSING 消息，并在事务提交后投递绑定的业务任务。"""

        task_id = str(uuid4())
        now = timezone.now()
        with transaction.atomic():
            message = Message.objects.create(
                conversation=conversation,
                parent_message=parent_message,
                message_type=handler.message_type,
                status=ExecutionStatus.PROCESSING,
                task_id=task_id,
                input_data=input_snapshot,
                context_data=context_snapshot,
                output_data=None,
                queued_at=now,
                last_activity_at=now,
                created_by=self.user,
                updated_by=self.user,
            )
            transaction.on_commit(lambda: self._dispatch(handler=handler, message=message))
        return message

    @staticmethod
    def _dispatch(*, handler: MessageTypeHandler, message: Message) -> None:
        """使用数据库 task_id 投递业务任务，投递失败则收敛消息为 FAILED。"""

        try:
            handler.async_task.apply_async(
                kwargs={"message_id": message.id, "task_id": message.task_id},
                task_id=message.task_id,
            )
            logger.info(
                "AI 助手消息任务已投递",
                extra={
                    "message_id": message.id,
                    "message_type": str(handler.message_type),
                    "task_id": message.task_id,
                    "task_name": handler.async_task.name,
                },
            )
        except Exception as error:
            logger.exception(
                "AI 助手消息任务投递失败",
                extra={
                    "message_id": message.id,
                    "message_type": str(handler.message_type),
                    "task_id": message.task_id,
                },
            )
            finish_message_failure(
                message_id=message.id,
                task_id=message.task_id,
                exception=error,
                error_code=MessageErrorCode.TASK_DISPATCH_FAILED,
            )
            # 投递失败后刷新同一个实例，避免 create() 首次返回值仍停留在 PROCESSING。
            message.refresh_from_db()
