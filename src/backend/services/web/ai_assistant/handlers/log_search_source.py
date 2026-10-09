"""成功日志检索附件的共用来源边界。

校验归属、状态和三份快照一致性，返回完整条件而不是预览记录。
不注册 Handler，不依赖统计或分析任务，创建与执行均可复验。
"""

from services.web.ai_assistant.constants import ExecutionStatus, MessageType
from services.web.ai_assistant.exceptions import (
    AttachmentSnapshotValidationError,
    InvalidAttachmentSource,
)
from services.web.ai_assistant.models import Message
from services.web.ai_assistant.schemas import parse_snapshot
from services.web.ai_assistant.schemas.audit_search import (
    LogSearchContextSchema,
    LogSearchInputSchema,
    LogSearchOutputSchema,
)


def parse_log_search_source(*, user: str, source_message: Message):
    """验证来源并返回 input/context/output；不满足来源或快照条件时抛领域异常。"""
    validate_log_search_source(user=user, source_message=source_message)
    log_input = parse_snapshot(
        LogSearchInputSchema,
        source_message.input_data,
        field_name="source_message.input_data",
        error_type=AttachmentSnapshotValidationError,
    )
    log_context = parse_snapshot(
        LogSearchContextSchema,
        source_message.context_data,
        field_name="source_message.context_data",
        error_type=AttachmentSnapshotValidationError,
    )
    log_output = parse_snapshot(
        LogSearchOutputSchema,
        source_message.output_data,
        field_name="source_message.output_data",
        error_type=AttachmentSnapshotValidationError,
    )
    if log_context.username != user or log_context.system_id != log_input.condition.scope_id:
        raise InvalidAttachmentSource()
    validate_log_search_consistency(
        log_input=log_input,
        log_context=log_context,
        log_output=log_output,
    )
    return log_input, log_context, log_output


def validate_log_search_source(*, user: str, source_message: Message) -> None:
    """防御性校验来源业务类型与可见边界；Service 仍是公开创建入口的第一道校验。"""

    conversation = source_message.conversation
    if (
        source_message.message_type != MessageType.LOG_SEARCH
        or source_message.status != ExecutionStatus.SUCCESS
        or source_message.created_by != user
        or conversation.created_by != user
        or conversation.is_deleted
    ):
        raise InvalidAttachmentSource()


def validate_log_search_consistency(
    *,
    log_input: LogSearchInputSchema,
    log_context: LogSearchContextSchema,
    log_output: LogSearchOutputSchema,
) -> None:
    """校验三份快照来自同一次检索，避免拼接不相干的分析范围。

    日志检索会合并可归一的重复条件，因此输出条件数只校验合法区间，
    不依赖 ``LogSearchService`` 的私有归一实现。
    """

    condition = log_input.condition
    summary = log_output.query_summary
    expected_time_range = {
        "start_time": condition.start_time,
        "end_time": condition.end_time,
    }
    is_consistent = (
        summary.scope_type == condition.scope_type
        and summary.scope_id == condition.scope_id == log_context.system_id
        and summary.time_range == expected_time_range
        and summary.source == log_context.source
        and 0 <= summary.condition_count <= len(condition.conditions)
    )
    if not is_consistent:
        raise AttachmentSnapshotValidationError(data={"field_name": "source_message", "errors": []})
