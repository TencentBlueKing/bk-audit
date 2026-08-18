from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from django.utils import timezone

from services.web.ai_assistant.constants import AttachmentErrorCode, ExecutionStatus
from services.web.ai_assistant.exceptions import (
    AIAssistantException,
    AttachmentOutputValidationError,
    AttachmentSnapshotValidationError,
    StaleAttachmentTask,
)
from services.web.ai_assistant.handlers import attachment_handler_registry
from services.web.ai_assistant.models import Attachment, Message
from services.web.ai_assistant.schemas import (
    MessageSchema,
    SnapshotInput,
    dump_snapshot,
    parse_snapshot,
)

InputT = TypeVar("InputT", bound=MessageSchema)
ContextT = TypeVar("ContextT", bound=MessageSchema)


@dataclass(frozen=True, slots=True)
class AttachmentExecution(Generic[InputT, ContextT]):
    """异步业务 Task 使用的附件实例和类型化执行快照。"""

    attachment: Attachment
    input_data: InputT
    context_data: ContextT

    @property
    def source_message(self) -> Message:
        """保留业务 Task 读取来源消息的便捷入口。"""

        return self.attachment.source_message


def load_attachment_execution(
    *,
    attachment_id: int,
    task_id: str,
    celery_task_id: str,
) -> AttachmentExecution:
    """校验当前投递并加载附件的类型化输入、上下文快照。"""

    if celery_task_id != task_id:
        raise StaleAttachmentTask()
    attachment = (
        Attachment.objects.select_related("source_message__conversation")
        .filter(
            id=attachment_id,
            task_id=task_id,
            status=ExecutionStatus.PROCESSING,
        )
        .first()
    )
    if attachment is None:
        raise StaleAttachmentTask()
    handler = attachment_handler_registry.require(attachment.attachment_type)
    return AttachmentExecution(
        attachment=attachment,
        input_data=parse_snapshot(
            handler.input_model,
            attachment.input_data,
            field_name="input_data",
            error_type=AttachmentSnapshotValidationError,
        ),
        context_data=parse_snapshot(
            handler.context_model,
            attachment.context_data,
            field_name="context_data",
            error_type=AttachmentSnapshotValidationError,
        ),
    )


def finish_attachment_success(
    *,
    execution: AttachmentExecution,
    task_id: str,
    output_data: SnapshotInput,
) -> dict[str, Any]:
    """校验附件输出并通过 PROCESSING CAS 竞争写入 SUCCESS。"""

    handler = attachment_handler_registry.require(execution.attachment.attachment_type)
    try:
        output_snapshot = dump_snapshot(
            handler.output_model,
            output_data,
            field_name="output_data",
            error_type=AttachmentSnapshotValidationError,
        )
    except AttachmentSnapshotValidationError as error:
        raise AttachmentOutputValidationError() from error
    now = timezone.now()
    updated = Attachment.finish_processing(
        instance_id=execution.attachment.id,
        task_id=task_id,
        status=ExecutionStatus.SUCCESS,
        output_data=output_snapshot,
        error_code="",
        error_message="",
        extra_updates={
            "content_updated_at": now,
            "updated_by": execution.attachment.created_by,
            "updated_at": now,
        },
    )
    if not updated:
        raise StaleAttachmentTask()
    return output_snapshot


def finish_attachment_failure(
    *,
    attachment_id: int,
    task_id: str,
    exception: Exception,
    error_code: str | AttachmentErrorCode = AttachmentErrorCode.TASK_EXECUTION_FAILED,
) -> bool:
    """映射附件错误并通过 PROCESSING CAS 尝试写入 FAILED。"""

    processing_attachment = Attachment.objects.filter(
        id=attachment_id,
        task_id=task_id,
        status=ExecutionStatus.PROCESSING,
    )
    created_by = processing_attachment.values_list("created_by", flat=True).first()
    if created_by is None:
        return False

    resolved_error_code = str(error_code)
    if resolved_error_code == AttachmentErrorCode.TASK_DISPATCH_FAILED:
        public_message = "附件任务投递失败，请稍后重试"
    elif isinstance(exception, AttachmentOutputValidationError):
        public_message = exception.message
        resolved_error_code = AttachmentErrorCode.OUTPUT_VALIDATION_FAILED
    elif isinstance(exception, AIAssistantException):
        public_message = exception.message
        if resolved_error_code == AttachmentErrorCode.TASK_EXECUTION_FAILED:
            resolved_error_code = exception.code
    else:
        public_message = "附件执行失败，请稍后重试"
    return Attachment.finish_processing(
        instance_id=attachment_id,
        task_id=task_id,
        status=ExecutionStatus.FAILED,
        output_data=None,
        error_code=resolved_error_code,
        error_message=public_message,
        extra_updates={
            "updated_by": created_by,
            "updated_at": timezone.now(),
        },
    )
