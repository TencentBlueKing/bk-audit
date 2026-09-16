"""程序与 AI 统计附件的独立业务任务。

平台负责任务 fencing、重投和持久化；程序统计调用共享统计服务，AI 统计透传 Agent 原文。
Celery 成功事件仅携带状态，统计数据保留在附件输出快照。
"""

from __future__ import annotations

import json
from http import HTTPStatus
from typing import TYPE_CHECKING

from bk_resource import api
from bk_resource.exceptions import APIRequestError
from blueapps.core.celery import celery_app
from celery.utils.time import get_exponential_backoff_interval
from django.conf import settings
from gevent import Timeout
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError, RequestException
from requests.exceptions import Timeout as RequestsTimeout

from api.bk_plugins_ai_agent.exceptions import AGUIStreamProtocolError
from api.constants import AIAgentCode
from services.web.ai_assistant.exceptions import (
    AIStatisticsTimeout,
    AttachmentOutputValidationError,
    AttachmentSnapshotValidationError,
    InvalidAttachmentSource,
)
from services.web.ai_assistant.log_analysis_artifact import LogAnalysisArtifactExtractor
from services.web.ai_assistant.schemas import parse_snapshot
from services.web.ai_assistant.schemas.audit_statistics import (
    AIStatisticsAttachmentContext,
    AIStatisticsAttachmentOutput,
    FieldStatisticsAttachmentOutput,
)
from services.web.ai_assistant.tasks.attachment import AttachmentExecutionTask
from services.web.query.ai_assistant.exceptions import (
    LogQueryFailed,
    LogQueryTimeout,
    LogToolException,
)
from services.web.query.ai_assistant.log_tools.schemas import LogFieldRef
from services.web.query.ai_assistant.log_tools.statistics import FieldStatisticsService

if TYPE_CHECKING:
    from services.web.ai_assistant.services.attachment_execution import (
        AttachmentExecution,
    )


def is_temporary_statistics_error(error: Exception) -> bool:
    """只识别受控传输错误；LogQueryFailed 包装的参数或坏帧不自动重试。"""
    current = error
    visited = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        if isinstance(current, (RequestsTimeout, RequestsConnectionError, TimeoutError)):
            return True
        if isinstance(current, APIRequestError):
            return current.status_code in {408, 429} or (
                current.status_code is not None and 500 <= current.status_code < 600
            )
        if isinstance(current, LogQueryTimeout) and current.__cause__ is None:
            return True
        current = current.__cause__
    return False


@celery_app.task(
    bind=True,
    base=AttachmentExecutionTask,
    name="ai_assistant.generate_field_statistics",
    queue="ai_assistant_statistics",
    ignore_result=True,
    acks_late=True,
    max_retries=settings.AI_ASSISTANT_FIELD_STATISTICS_MAX_RETRIES,
    default_retry_delay=settings.AI_ASSISTANT_FIELD_STATISTICS_RETRY_DELAY_SECONDS,
    rate_limit=settings.AI_ASSISTANT_FIELD_STATISTICS_TASK_RATE_LIMIT,
    time_limit=settings.AI_ASSISTANT_FIELD_STATISTICS_TASK_TIMEOUT,
)
def generate_field_statistics(self, execution: AttachmentExecution) -> FieldStatisticsAttachmentOutput:  # noqa: N805
    """复验完整来源和权限后计算固定包；只对临时上游故障作有界自动重试。"""
    # tasks 冷启动经 services 回到 handlers，来源 helper 必须延迟到注册完成后加载。
    from services.web.ai_assistant.handlers.log_search_source import (
        parse_log_search_source,
    )

    context = execution.context_data
    log_input, log_context, _ = parse_log_search_source(
        user=execution.attachment.created_by,
        source_message=execution.source_message,
    )
    if (
        context.username != execution.attachment.created_by
        or context.namespace != log_context.namespace
        or context.search_condition.model_dump(mode="json") != log_input.condition.model_dump(mode="json")
        or context.field.raw_name != execution.input_data.field.raw_name
        or list(context.field.keys) != execution.input_data.field.keys
        or context.top_n != execution.input_data.top_n
        or context.interval != execution.input_data.interval
    ):
        raise InvalidAttachmentSource()
    try:
        with Timeout(settings.AI_ASSISTANT_FIELD_STATISTICS_BUSINESS_TIMEOUT, LogQueryTimeout()):
            result = FieldStatisticsService.analyze(
                username=context.username,
                namespace=context.namespace,
                condition=context.search_condition,
                field=LogFieldRef(raw_name=context.field.raw_name, keys=list(context.field.keys)),
                top_n=context.top_n,
                interval=context.interval,
            )
        return FieldStatisticsAttachmentOutput.model_validate(result.model_dump(mode="python"))
    except (LogToolException, APIRequestError, RequestsTimeout, RequestsConnectionError) as error:
        # 分类依赖原始cause；之后必须离开except再重试，避免Celery重新关联敏感异常链。
        retryable = is_temporary_statistics_error(error)
        public_error = type(error)() if isinstance(error, LogToolException) else LogQueryFailed()
    if not retryable:
        raise public_error from None
    countdown = get_exponential_backoff_interval(
        factor=self.default_retry_delay,
        retries=self.request.retries,
        maximum=settings.AI_ASSISTANT_FIELD_STATISTICS_RETRY_BACKOFF_MAX_SECONDS,
        full_jitter=True,
    )
    raise self.retry(exc=public_error, countdown=countdown) from None


def build_statistics_agent_input(context: AIStatisticsAttachmentContext) -> str:
    """序列化可调整的初始上下文；不暴露 namespace、预览、SQL 或内部 ID。"""
    return json.dumps(
        {
            "instruction": context.instruction,
            "context": {
                "initial_search_condition": context.initial_search_condition.model_dump(mode="json"),
                "query_summary": context.query_summary.model_dump(mode="json"),
                "user": {"username": context.username, "timezone": context.timezone, "language": context.language},
            },
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


@celery_app.task(
    bind=True,
    base=AttachmentExecutionTask,
    name="ai_assistant.generate_ai_statistics",
    queue="ai_assistant_statistics",
    ignore_result=True,
    acks_late=True,
    max_retries=settings.AI_ASSISTANT_AI_STATISTICS_MAX_RETRIES,
    default_retry_delay=settings.AI_ASSISTANT_AI_STATISTICS_RETRY_DELAY_SECONDS,
    rate_limit=settings.AI_ASSISTANT_AI_STATISTICS_TASK_RATE_LIMIT,
    time_limit=settings.AI_ASSISTANT_AI_STATISTICS_TASK_TIMEOUT,
)
def generate_ai_statistics(self, execution: AttachmentExecution) -> AIStatisticsAttachmentOutput:  # noqa: N805
    """调用独立统计 Agent，受控重试传输和最终文本错误；权限及参数错误直接失败。"""
    try:
        return _execute_ai_statistics(execution)
    except (
        APIRequestError,
        RequestException,
        AGUIStreamProtocolError,
        AIStatisticsTimeout,
        AttachmentOutputValidationError,
    ) as error:
        status_code = None
        if isinstance(error, APIRequestError):
            status_code = error.status_code
        elif isinstance(error, HTTPError) and error.response is not None:
            status_code = error.response.status_code
        retryable = not (
            status_code is not None
            and HTTPStatus.BAD_REQUEST <= status_code < HTTPStatus.INTERNAL_SERVER_ERROR
            and status_code not in (HTTPStatus.REQUEST_TIMEOUT, HTTPStatus.TOO_MANY_REQUESTS)
        )
        # API标准错误的message来自上游正文；只保留HTTP状态供诊断及重试。
        public_error = (
            APIRequestError(status_code=status_code, result={"message": "AI 统计服务调用失败，请稍后重试"})
            if isinstance(error, APIRequestError)
            else error
        )
    # 离开原异常上下文，避免Celery.retry耗尽时raise_with_context重新接回正文。
    if not retryable:
        raise public_error from None
    countdown = get_exponential_backoff_interval(
        factor=self.default_retry_delay,
        retries=self.request.retries,
        maximum=settings.AI_ASSISTANT_AI_STATISTICS_RETRY_BACKOFF_MAX_SECONDS,
        full_jitter=True,
    )
    raise self.retry(exc=public_error, countdown=countdown) from None


def _execute_ai_statistics(execution: AttachmentExecution) -> AIStatisticsAttachmentOutput:
    """复验来源后透传事件，仅持久化最后闭合 assistant 消息的原始文本。"""
    # tasks 冷启动经 services 回到 handlers，来源 helper 在注册完成后加载。
    from services.web.ai_assistant.handlers.log_search_source import (
        parse_log_search_source,
    )

    context = execution.context_data
    log_input, log_context, log_output = parse_log_search_source(
        user=execution.attachment.created_by,
        source_message=execution.source_message,
    )
    if (
        context.username != execution.attachment.created_by
        or context.namespace != log_context.namespace
        or context.instruction != execution.input_data.instruction
        or context.initial_search_condition.model_dump(mode="json") != log_input.condition.model_dump(mode="json")
        or context.query_summary.total != log_output.total
        or context.query_summary.executed_at != log_output.query_summary.executed_at
    ):
        raise InvalidAttachmentSource()
    # 以上只验证创建快照未被拼接；Agent 后续工具调用不受初始范围锁定，工具按当前用户重新鉴权。
    extractor = LogAnalysisArtifactExtractor(
        max_content_bytes=settings.AI_ASSISTANT_AI_STATISTICS_CONTENT_MAX_BYTES,
        strict_final_message=True,
    )

    def on_event(event: dict) -> None:
        """先归档原始事件，再更新本次执行独立的最终文本候选。"""
        execution.stream.send(event)
        extractor.consume(event)

    with Timeout(settings.AI_ASSISTANT_AI_STATISTICS_BUSINESS_TIMEOUT, AIStatisticsTimeout()):
        api.bk_plugins_ai_agent.chat_completion(
            agent_code=AIAgentCode.AUDIT_LOG_STATISTICS,
            user=execution.attachment.created_by,
            chat_history=[
                {"role": "role", "content": context.system_prompt},
                {"role": "user", "content": build_statistics_agent_input(context)},
            ],
            execute_kwargs={"stream": True, "thread_id": str(execution.stream.execution_id)},
            on_event=on_event,
        )
    try:
        return parse_snapshot(
            AIStatisticsAttachmentOutput,
            {"content": extractor.final_content},
            field_name="output_data",
            error_type=AttachmentSnapshotValidationError,
        )
    except AttachmentSnapshotValidationError as error:
        raise AttachmentOutputValidationError() from error
