from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from django.utils import timezone

from services.web.ai_assistant.constants import (
    ExecutionMode,
    ExecutionObjectType,
    ExecutionStatus,
    MessageErrorCode,
)
from services.web.ai_assistant.exceptions import (
    AIAssistantException,
    MessageExecutionFailed,
    MessageSnapshotValidationError,
    StaleMessageTask,
)
from services.web.ai_assistant.handlers import message_handler_registry
from services.web.ai_assistant.models import Message
from services.web.ai_assistant.observability import (
    ExecutionMetricSnapshot,
    report_execution_finished,
    report_invariant_violation,
    set_execution_span_context,
)
from services.web.ai_assistant.schemas import (
    MessageSchema,
    SnapshotInput,
    dump_snapshot,
    parse_snapshot,
)

InputT = TypeVar("InputT", bound=MessageSchema)
ContextT = TypeVar("ContextT", bound=MessageSchema)


@dataclass(frozen=True, slots=True)
class MessageExecution(Generic[InputT, ContextT]):
    """异步业务 Task 使用的消息实例和类型化执行快照。"""

    message: Message
    input_data: InputT
    context_data: ContextT


def load_message_execution(
    *,
    message_id: int,
    task_id: str,
    celery_task_id: str,
) -> MessageExecution:
    """校验当前投递并加载消息的类型化输入、上下文快照。"""

    if celery_task_id != task_id:
        raise StaleMessageTask()
    if not Message.mark_processing_started(instance_id=message_id, task_id=task_id):
        raise StaleMessageTask()
    message = Message.objects.filter(
        id=message_id,
        task_id=task_id,
        status=ExecutionStatus.PROCESSING,
    ).first()
    if message is None:
        raise StaleMessageTask()
    handler = message_handler_registry.require(message.message_type)
    set_execution_span_context(
        object_uid=str(message.uid),
        business_type=message.message_type,
        is_stream=False,
    )
    return MessageExecution(
        message=message,
        input_data=parse_snapshot(handler.input_model, message.input_data, field_name="input_data"),
        context_data=parse_snapshot(handler.context_model, message.context_data, field_name="context_data"),
    )


def finish_message_success(
    *,
    execution: MessageExecution,
    task_id: str,
    output_data: SnapshotInput,
) -> dict[str, Any]:
    """校验消息输出并通过 PROCESSING CAS 竞争写入 SUCCESS。"""

    message = execution.message
    handler = message_handler_registry.require(message.message_type)
    try:
        output_snapshot = dump_snapshot(handler.output_model, output_data, field_name="output_data")
    except MessageSnapshotValidationError as error:
        raise MessageExecutionFailed(message="任务执行结果格式错误") from error
    now = timezone.now()
    updated = Message.finish_processing(
        instance_id=message.id,
        task_id=task_id,
        status=ExecutionStatus.SUCCESS,
        output_data=output_snapshot,
        error_code="",
        error_message="",
        extra_updates={
            "updated_by": message.created_by,
            "updated_at": now,
        },
        now=now,
    )
    if not updated:
        raise StaleMessageTask()
    report_execution_finished(
        ExecutionMetricSnapshot(
            object_type=ExecutionObjectType.MESSAGE,
            business_type=message.message_type,
            execution_mode=ExecutionMode.ASYNC,
            is_stream=False,
            status=ExecutionStatus.SUCCESS,
            error_code="",
            created_at=message.created_at,
            queued_at=message.queued_at,
            started_at=message.started_at,
            finished_at=now,
        )
    )
    return output_snapshot


def finish_message_failure(
    *,
    message_id: int,
    task_id: str,
    exception: Exception,
    error_code: str | MessageErrorCode = MessageErrorCode.TASK_EXECUTION_FAILED,
) -> bool:
    """映射消息错误并通过 PROCESSING CAS 尝试写入 FAILED。"""

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
    now = timezone.now()
    updated = Message.finish_processing(
        instance_id=message_id,
        task_id=task_id,
        status=ExecutionStatus.FAILED,
        output_data=None,
        error_code=str(error_code),
        error_message=public_message,
        extra_updates={
            "updated_by": message.created_by,
            "updated_at": now,
        },
        now=now,
    )
    if updated:
        if isinstance(exception, MessageExecutionFailed) and isinstance(
            exception.__cause__, MessageSnapshotValidationError
        ):
            report_invariant_violation(
                object_type=ExecutionObjectType.MESSAGE,
                business_type=message.message_type,
                object_uid=str(message.uid),
                task_id=task_id,
                error_code=str(exception.__cause__.code),
            )
        report_execution_finished(
            ExecutionMetricSnapshot(
                object_type=ExecutionObjectType.MESSAGE,
                business_type=message.message_type,
                execution_mode=ExecutionMode.ASYNC,
                is_stream=False,
                status=ExecutionStatus.FAILED,
                error_code=str(error_code),
                created_at=message.created_at,
                queued_at=message.queued_at,
                started_at=message.started_at,
                finished_at=now,
            )
        )
    return updated
