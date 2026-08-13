import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Generic, TypeVar
from uuid import uuid4

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone

from services.web.ai_assistant.constants import (
    ExecutionMode,
    ExecutionStatus,
    MessageErrorCode,
    MessageType,
)
from services.web.ai_assistant.exceptions import (
    AIAssistantException,
    InvalidParentMessage,
    MessageExecutionFailed,
    MessageSnapshotValidationError,
    StaleMessageTask,
)
from services.web.ai_assistant.handlers import (
    MessageTypeHandler,
    message_handler_registry,
)
from services.web.ai_assistant.models import Conversation, Message
from services.web.ai_assistant.schemas import (
    MessageSchema,
    SnapshotInput,
    dump_snapshot,
    parse_snapshot,
)

logger = logging.getLogger(__name__)

InputT = TypeVar("InputT", bound=MessageSchema)
ContextT = TypeVar("ContextT", bound=MessageSchema)
OutputT = TypeVar("OutputT", bound=MessageSchema)


@dataclass(frozen=True, slots=True)
class MessageExecution(Generic[InputT, ContextT]):
    """业务 Task 执行时读取到的消息和类型化快照。"""

    message: Message
    input_data: InputT
    context_data: ContextT


class MessageService:
    """统一消息创建顺序，业务差异由注册 Handler 提供。"""

    @classmethod
    def create(
        cls,
        *,
        user: str,
        conversation: Conversation,
        message_type: str | MessageType,
        input_data: Mapping[str, Any],
        parent_message_uid: str | None = None,
    ) -> Message:
        """校验请求和业务上下文，并按 Handler 的执行方式创建消息。"""

        cls._validate_conversation(user=user, conversation=conversation)
        parent_message = cls._resolve_parent(
            user=user,
            conversation=conversation,
            parent_message_uid=parent_message_uid,
        )
        handler = message_handler_registry.require(message_type)
        parsed_input = parse_snapshot(handler.input_model, input_data, field_name="input_data")
        preparation = handler.prepare(
            user=user,
            conversation=conversation,
            parent_message=parent_message,
            input_data=parsed_input,
        )
        parsed_context = parse_snapshot(
            handler.context_model,
            preparation.context_data,
            field_name="context_data",
        )
        input_snapshot = parsed_input.model_dump(mode="json")
        context_snapshot = parsed_context.model_dump(mode="json")

        if handler.execution_mode == ExecutionMode.SYNC:
            message = cls._create_sync(
                user=user,
                conversation=conversation,
                handler=handler,
                parent_message=preparation.parent_message,
                input_data=parsed_input,
                context_data=parsed_context,
                input_snapshot=input_snapshot,
                context_snapshot=context_snapshot,
            )
        else:
            message = cls._create_async(
                user=user,
                conversation=conversation,
                handler=handler,
                parent_message=preparation.parent_message,
                input_snapshot=input_snapshot,
                context_snapshot=context_snapshot,
            )
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

    @staticmethod
    def _validate_conversation(*, user: str, conversation: Conversation) -> None:
        """防御性校验会话存在、未删除且归属于当前用户。"""

        if (
            not user
            or conversation.created_by != user
            or conversation.is_deleted
            or not Conversation.objects.filter(id=conversation.id, created_by=user).exists()
        ):
            raise InvalidParentMessage(message="会话无效")

    @classmethod
    def _resolve_parent(
        cls,
        *,
        user: str,
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
                created_by=user,
            ).first()
        except DjangoValidationError as error:
            raise InvalidParentMessage() from error
        if parent_message is None:
            raise InvalidParentMessage()
        return parent_message

    @staticmethod
    def _create_sync(
        *,
        user: str,
        conversation: Conversation,
        handler: MessageTypeHandler[InputT, ContextT, OutputT],
        parent_message: Message | None,
        input_data: InputT,
        context_data: ContextT,
        input_snapshot: dict[str, Any],
        context_snapshot: dict[str, Any],
    ) -> Message:
        """同步执行业务，输出校验成功后直接创建 SUCCESS 消息。"""

        output_data = handler.execute(input_data=input_data, context_data=context_data)
        output_snapshot = dump_snapshot(handler.output_model, output_data, field_name="output_data")
        return Message.objects.create(
            conversation=conversation,
            parent_message=parent_message,
            message_type=handler.message_type,
            status=ExecutionStatus.SUCCESS,
            input_data=input_snapshot,
            context_data=context_snapshot,
            output_data=output_snapshot,
            created_by=user,
            updated_by=user,
        )

    @classmethod
    def _create_async(
        cls,
        *,
        user: str,
        conversation: Conversation,
        handler: MessageTypeHandler,
        parent_message: Message | None,
        input_snapshot: dict[str, Any],
        context_snapshot: dict[str, Any],
    ) -> Message:
        """先持久化 PROCESSING 消息，并在事务提交后投递绑定的业务任务。"""

        task_id = str(uuid4())
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
                created_by=user,
                updated_by=user,
            )
            transaction.on_commit(lambda: cls._dispatch(handler=handler, message=message))
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
            MessageExecutor.mark_failed(
                message_id=message.id,
                task_id=message.task_id,
                exception=error,
                error_code=MessageErrorCode.TASK_DISPATCH_FAILED,
            )


class MessageExecutor:
    """提供异步消息 fencing、类型化快照加载和数据库终态幂等更新。"""

    @staticmethod
    def assert_executable(*, message_id: int, task_id: str, celery_task_id: str) -> None:
        """外部调用前校验数据库任务与当前 Celery 投递完全一致。"""

        if celery_task_id != task_id:
            raise StaleMessageTask()
        MessageExecutor._require_processing_message(message_id=message_id, task_id=task_id)

    @classmethod
    def load_processing_execution(
        cls,
        *,
        message_id: int,
        task_id: str,
    ) -> MessageExecution[InputT, ContextT]:
        """加载当前任务的消息，并按已注册 Handler Schema 解析执行快照。"""

        message = cls._require_processing_message(message_id=message_id, task_id=task_id)
        handler = message_handler_registry.require(message.message_type)
        return MessageExecution(
            message=message,
            input_data=parse_snapshot(handler.input_model, message.input_data, field_name="input_data"),
            context_data=parse_snapshot(handler.context_model, message.context_data, field_name="context_data"),
        )

    @staticmethod
    def mark_success(*, message_id: int, task_id: str, output_data: SnapshotInput) -> dict[str, Any]:
        """校验输出并原子写入成功终态；并发任务只有第一个更新成功。"""

        message = MessageExecutor._require_processing_message(message_id=message_id, task_id=task_id)
        handler = message_handler_registry.require(message.message_type)
        try:
            output_snapshot = dump_snapshot(handler.output_model, output_data, field_name="output_data")
        except MessageSnapshotValidationError as error:
            raise MessageExecutionFailed(message="任务执行结果格式错误") from error
        processing_message = Message.objects.filter(
            id=message_id,
            task_id=task_id,
            status=ExecutionStatus.PROCESSING,
        )
        # PROCESSING 是终态写入的 CAS 条件，防止并发 Worker 相互覆盖结果。
        updated = processing_message.update(
            output_data=output_snapshot,
            status=ExecutionStatus.SUCCESS,
            error_code="",
            error_message="",
            updated_by=message.created_by,
            updated_at=timezone.now(),
        )
        if updated != 1:
            raise StaleMessageTask()
        return output_snapshot

    @staticmethod
    def mark_failed(
        *,
        message_id: int,
        task_id: str,
        exception: Exception,
        error_code: str | MessageErrorCode = MessageErrorCode.TASK_EXECUTION_FAILED,
    ) -> bool:
        """提取可公开错误，并以相同 CAS 条件尝试写入失败终态。"""

        message = Message.objects.filter(
            id=message_id,
            task_id=task_id,
            status=ExecutionStatus.PROCESSING,
        ).first()
        if message is None:
            return False
        if error_code == MessageErrorCode.TASK_DISPATCH_FAILED:
            public_message = "任务投递失败，请稍后重试"
        elif isinstance(exception, MessageExecutionFailed):
            public_message = exception.message
        elif isinstance(exception, AIAssistantException):
            public_message = exception.message
            error_code = exception.code
        else:
            public_message = "消息执行失败，请稍后重试"
        processing_message = Message.objects.filter(
            id=message_id,
            task_id=task_id,
            status=ExecutionStatus.PROCESSING,
        )
        # 失败与成功竞争同一 PROCESSING 条件，首个终态写入者获胜。
        updated = processing_message.update(
            output_data=None,
            status=ExecutionStatus.FAILED,
            error_code=error_code,
            error_message=public_message,
            updated_by=message.created_by,
            updated_at=timezone.now(),
        )
        return updated == 1

    @staticmethod
    def _require_processing_message(*, message_id: int, task_id: str) -> Message:
        """要求消息仍绑定当前任务且处于 PROCESSING，否则视为陈旧任务。"""

        message = Message.objects.filter(id=message_id).first()
        if message is None or message.status != ExecutionStatus.PROCESSING or message.task_id != task_id:
            raise StaleMessageTask()
        return message
