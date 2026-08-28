"""日志分析报告的业务 Celery Task。

平台 Task 基类负责 fencing、Retry 刷盘和终态收敛；本模块只构造紧凑 Agent
请求、透传 AG-UI 事件，并返回最终 Markdown 类型化产物。
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from bk_resource import api
from blueapps.core.celery import celery_app
from django.conf import settings
from django.utils import timezone
from gevent import Timeout

from api.constants import AIAgentCode
from services.web.ai_assistant.constants import (
    DEFAULT_AI_ANALYSIS_TITLE,
    AttachmentType,
    ExecutionStatus,
)
from services.web.ai_assistant.exceptions import (
    AttachmentOutputValidationError,
    AttachmentSnapshotValidationError,
    LogAnalysisTimeout,
)
from services.web.ai_assistant.models import Attachment
from services.web.ai_assistant.schemas import SnapshotInput, parse_snapshot
from services.web.ai_assistant.schemas.audit_analysis import (
    AIAnalysisContextSchema,
    AIAnalysisOutputSchema,
)
from services.web.ai_assistant.tasks.attachment import AttachmentExecutionTask

if TYPE_CHECKING:
    from services.web.ai_assistant.services.attachment_execution import (
        AttachmentExecution,
    )

logger = logging.getLogger(__name__)


@celery_app.task(name="ai_assistant.generate_log_analysis_title", ignore_result=True)
def generate_log_analysis_title(attachment_id: int) -> dict:
    """为默认标题的日志分析附件生成标题，失败时静默保留原值。

    标题是报告旁路元信息。本任务不读取或修改执行状态和产物，只以默认标题作为
    CAS 条件，保证迟到或重复任务不会覆盖用户编辑及已生成标题。
    """

    attachment = (
        Attachment.objects.filter(
            id=attachment_id,
            attachment_type=AttachmentType.AI_ANALYSIS,
            status=ExecutionStatus.SUCCESS,
            title=DEFAULT_AI_ANALYSIS_TITLE,
        )
        .only("id", "created_by", "context_data")
        .first()
    )
    if attachment is None:
        return {"updated": False, "skipped": True}

    try:
        context = parse_snapshot(
            AIAnalysisContextSchema,
            attachment.context_data,
            field_name="context_data",
            error_type=AttachmentSnapshotValidationError,
        )
        # services 包初始化会经 Handler 回到本 Task 模块，必须在模块完成加载后再导入。
        from services.web.ai_assistant.services.title_agent import TitleAgentService

        title = TitleAgentService.generate_title(
            module="log_analysis_attachment",
            input_text=context.effective_instruction,
            username=attachment.created_by,
        )
    except Exception as error:
        # 严禁记录上下文正文；用户分析要求可能包含敏感业务信息。
        logger.warning(
            "日志分析报告标题生成失败",
            extra={"attachment_id": attachment_id, "error_type": type(error).__name__},
        )
        return {"updated": False, "skipped": False}

    if not title:
        logger.warning(
            "日志分析报告标题生成结果为空",
            extra={"attachment_id": attachment_id},
        )
        return {"updated": False, "skipped": False}

    updated = Attachment.objects.filter(
        id=attachment_id,
        attachment_type=AttachmentType.AI_ANALYSIS,
        status=ExecutionStatus.SUCCESS,
        title=DEFAULT_AI_ANALYSIS_TITLE,
    ).update(title=title, updated_at=timezone.now())
    return {"updated": bool(updated), "skipped": False}


def _dispatch_log_analysis_title(*, attachment_id: int) -> None:
    """投递标题旁路；Broker 异常不得反向破坏已生成的报告正文。"""

    try:
        generate_log_analysis_title.delay(attachment_id=attachment_id)
    except Exception as error:
        logger.warning(
            "日志分析报告标题任务投递失败",
            extra={"attachment_id": attachment_id, "error_type": type(error).__name__},
        )


def build_agent_input(context: AIAnalysisContextSchema) -> str:
    """序列化 Agent 最小输入；不携带预览日志、SQL、namespace 或内部 ID。"""

    payload = {
        "instruction": context.effective_instruction,
        "context": {
            "search_condition": context.search_condition.model_dump(mode="json"),
            "query_summary": context.query_summary.model_dump(mode="json"),
            "user": {
                "username": context.username,
                "timezone": context.timezone,
                "language": context.language,
            },
        },
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class LogAnalysisExecutionTask(AttachmentExecutionTask):
    """日志分析任务基类：报告成功落库后再异步补充标题。"""

    def _finish_success(
        self,
        *,
        execution: AttachmentExecution,
        task_id: str,
        output_data: SnapshotInput,
    ) -> dict[str, Any]:
        # 标题是旁路元信息，必须在报告终态提交后派发，Broker 异常不能阻塞正文可用。
        super()._finish_success(
            execution=execution,
            task_id=task_id,
            output_data=output_data,
        )
        _dispatch_log_analysis_title(attachment_id=execution.attachment.id)
        # Celery task-succeeded 事件会携带返回值；正文只允许保存在 Attachment 快照。
        return {"status": ExecutionStatus.SUCCESS}


@celery_app.task(
    bind=True,
    base=LogAnalysisExecutionTask,
    name="ai_assistant.execute_log_analysis",
    queue="ai_assistant_log_analysis",
    ignore_result=True,
    acks_late=True,
    rate_limit=settings.AI_ASSISTANT_LOG_ANALYSIS_TASK_RATE_LIMIT,
    time_limit=settings.AI_ASSISTANT_LOG_ANALYSIS_TASK_TIMEOUT,
)
def execute_log_analysis(
    self,
    execution: AttachmentExecution,
) -> AIAnalysisOutputSchema:  # noqa: N805
    """调用日志分析 Agent，过程事件实时写入平台 UI 流。"""

    # gevent Timeout 抛出普通业务异常，先于 Celery hard limit 收敛失败终态与流。
    with Timeout(settings.AI_ASSISTANT_LOG_ANALYSIS_BUSINESS_TIMEOUT, LogAnalysisTimeout()):
        response = api.bk_plugins_ai_agent.agui_chat_completion(
            agent_code=AIAgentCode.AUDIT_LOG_ANALYSIS,
            user=execution.context_data.username,
            input=build_agent_input(execution.context_data),
            chat_history=[],
            execute_kwargs={"stream": True},
            on_event=execution.stream.send,
        )
    # final_result 是 Agent 自定义终态负载，一期只将完整 assistant Markdown 作为业务事实。
    # 必须经快照解析边界清洗 Pydantic input_value，避免 Agent 正文进入任务异常日志。
    try:
        output = parse_snapshot(
            AIAnalysisOutputSchema,
            {"markdown": response.final_content},
            field_name="output_data",
            error_type=AttachmentSnapshotValidationError,
        )
    except AttachmentSnapshotValidationError as error:
        raise AttachmentOutputValidationError() from error

    return output
