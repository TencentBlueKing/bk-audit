"""统计附件的非流式业务任务。

平台基类负责任务 fencing、重投和持久化；程序统计只复验来源并调用共享统计服务。
Celery 成功事件仅携带状态，统计数据保留在附件输出快照。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from bk_resource.exceptions import APIRequestError
from blueapps.core.celery import celery_app
from celery.utils.time import get_exponential_backoff_interval
from django.conf import settings
from gevent import Timeout
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout as RequestsTimeout

from services.web.ai_assistant.constants import ExecutionStatus
from services.web.ai_assistant.exceptions import InvalidAttachmentSource
from services.web.ai_assistant.schemas import SnapshotInput
from services.web.ai_assistant.schemas.audit_statistics import (
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


class FieldStatisticsExecutionTask(AttachmentExecutionTask):
    """先完成平台 CAS 持久化，再收敛 Celery 返回值。"""

    def _finish_success(self, *, execution: AttachmentExecution, task_id: str, output_data: SnapshotInput) -> dict:
        """CAS 失败继续抛陈旧任务异常，不将未持久化结果宣告成功。"""
        super()._finish_success(execution=execution, task_id=task_id, output_data=output_data)
        return {"status": ExecutionStatus.SUCCESS}


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
    base=FieldStatisticsExecutionTask,
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
