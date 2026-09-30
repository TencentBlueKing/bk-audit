from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from django.utils import timezone

from services.web.ai_assistant.constants import (
    AttachmentErrorCode,
    ExecutionMode,
    ExecutionObjectType,
    ExecutionStatus,
)
from services.web.ai_assistant.exceptions import (
    AIAssistantException,
    AttachmentOutputValidationError,
    AttachmentSnapshotValidationError,
    StaleAttachmentTask,
    StreamNotEnabled,
)
from services.web.ai_assistant.handlers import attachment_handler_registry
from services.web.ai_assistant.models import Attachment, Message
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
from services.web.ai_assistant.streaming import UIStreamRuntime

InputT = TypeVar("InputT", bound=MessageSchema)
ContextT = TypeVar("ContextT", bound=MessageSchema)


@dataclass(frozen=True, slots=True)
class AttachmentExecution(Generic[InputT, ContextT]):
    """异步业务 Task 使用的附件实例和类型化执行快照。"""

    attachment: Attachment
    input_data: InputT
    context_data: ContextT
    # 仅流式附件由平台注入；业务统一通过 stream 属性访问，避免误判 None。
    _stream: UIStreamRuntime | None = field(default=None, repr=False)

    @property
    def source_message(self) -> Message:
        """保留业务 Task 读取来源消息的便捷入口。"""

        return self.attachment.source_message

    @property
    def stream(self) -> UIStreamRuntime:
        """非流式附件访问流出口属于接入错误，直接暴露平台异常。"""

        if self._stream is None:
            raise StreamNotEnabled()
        return self._stream

    @property
    def has_stream(self) -> bool:
        """平台内部据此决定是否走 Runtime 终态与 Retry 刷盘。"""

        return self._stream is not None


def load_attachment_execution(
    *,
    attachment_id: int,
    task_id: str,
    celery_task_id: str,
) -> AttachmentExecution:
    """校验当前投递并加载附件的类型化输入、上下文快照。"""

    if celery_task_id != task_id:
        raise StaleAttachmentTask()
    if not Attachment.mark_processing_started(instance_id=attachment_id, task_id=task_id):
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
    set_execution_span_context(
        object_uid=str(attachment.uid),
        business_type=attachment.attachment_type,
        is_stream=attachment.is_stream,
    )
    input_data = parse_snapshot(
        handler.input_model,
        attachment.input_data,
        field_name="input_data",
        error_type=AttachmentSnapshotValidationError,
    )
    context_data = parse_snapshot(
        handler.context_model,
        attachment.context_data,
        field_name="context_data",
        error_type=AttachmentSnapshotValidationError,
    )
    # 流能力以模型字段为准；Handler 声明只在创建时固化，避免运行期改动影响历史执行。
    stream = UIStreamRuntime.start(attachment_id=attachment.id, task_id=task_id) if attachment.is_stream else None
    return AttachmentExecution(
        attachment=attachment,
        input_data=input_data,
        context_data=context_data,
        _stream=stream,
    )


def finish_attachment_success(
    *,
    execution: AttachmentExecution,
    task_id: str,
    output_data: SnapshotInput,
) -> dict[str, Any]:
    """校验附件输出后写入 SUCCESS；流式经 Runtime 终态事务收敛。"""

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
    if execution.has_stream:
        # 流式必须让剩余事件与终态落在同一事务，避免终态先可见、尾部事件丢失。
        execution.stream.finish_success(output_data=output_snapshot, updated_by=execution.attachment.created_by)
        return output_snapshot
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
        now=now,
    )
    if not updated:
        raise StaleAttachmentTask()
    report_execution_finished(
        ExecutionMetricSnapshot(
            object_type=ExecutionObjectType.ATTACHMENT,
            business_type=execution.attachment.attachment_type,
            execution_mode=ExecutionMode.ASYNC,
            is_stream=False,
            status=ExecutionStatus.SUCCESS,
            error_code="",
            created_at=execution.attachment.created_at,
            queued_at=execution.attachment.queued_at,
            started_at=execution.attachment.started_at,
            finished_at=now,
        )
    )
    return output_snapshot


def finish_attachment_failure(
    *,
    attachment_id: int,
    task_id: str,
    exception: Exception,
    error_code: str | AttachmentErrorCode = AttachmentErrorCode.TASK_EXECUTION_FAILED,
    execution: AttachmentExecution | None = None,
) -> bool:
    """映射附件错误并写入 FAILED；流式复用 Runtime 保留已产生的事件。"""

    processing_attachment = Attachment.objects.filter(
        id=attachment_id,
        task_id=task_id,
        status=ExecutionStatus.PROCESSING,
    )
    attachment = processing_attachment.first()
    if attachment is None:
        return False
    created_by = attachment.created_by

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
    if execution is not None and execution.has_stream:
        is_stream_execution = True
        # 流式 Runtime 在同一事务内收敛归档与终态，并返回当前任务是否赢得竞争。
        updated = execution.stream.finish_failure(
            error_code=resolved_error_code,
            error_message=public_message,
            updated_by=created_by,
        )
    else:
        is_stream_execution = False
        # 投递失败等未进入 Worker 的场景没有 Runtime，直接通过任务 fencing 写终态。
        now = timezone.now()
        updated = Attachment.finish_processing(
            instance_id=attachment_id,
            task_id=task_id,
            status=ExecutionStatus.FAILED,
            output_data=None,
            error_code=resolved_error_code,
            error_message=public_message,
            extra_updates={
                "updated_by": created_by,
                "updated_at": now,
            },
            now=now,
        )
    if updated:
        if isinstance(exception, AttachmentOutputValidationError) and isinstance(
            exception.__cause__, AttachmentSnapshotValidationError
        ):
            report_invariant_violation(
                object_type=ExecutionObjectType.ATTACHMENT,
                business_type=attachment.attachment_type,
                object_uid=str(attachment.uid),
                task_id=task_id,
                error_code=AttachmentErrorCode.OUTPUT_VALIDATION_FAILED,
            )
        # 流式 Runtime 已在最终事务提交后上报 Execution Metric，避免重复计数。
        if not is_stream_execution:
            report_execution_finished(
                ExecutionMetricSnapshot(
                    object_type=ExecutionObjectType.ATTACHMENT,
                    business_type=attachment.attachment_type,
                    execution_mode=ExecutionMode.ASYNC,
                    is_stream=attachment.is_stream,
                    status=ExecutionStatus.FAILED,
                    error_code=resolved_error_code,
                    created_at=attachment.created_at,
                    queued_at=attachment.queued_at,
                    started_at=attachment.started_at,
                    finished_at=now,
                )
            )
    return updated
