"""日志分析报告的业务 Celery Task。

平台 Task 基类负责 fencing、Retry 刷盘和终态收敛；本模块只构造紧凑 Agent
请求、透传 AG-UI 事件，并返回最终 Markdown 类型化产物。
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from bk_resource import api
from django.conf import settings
from gevent import Timeout

from api.constants import AIAgentCode
from services.web.ai_assistant.exceptions import (
    AttachmentOutputValidationError,
    AttachmentSnapshotValidationError,
    LogAnalysisTimeout,
)
from services.web.ai_assistant.schemas import parse_snapshot
from services.web.ai_assistant.schemas.audit_analysis import (
    AIAnalysisContextSchema,
    AIAnalysisOutputSchema,
)
from services.web.ai_assistant.tasks.decorators import attachment_execution_task

if TYPE_CHECKING:
    from services.web.ai_assistant.services.attachment_execution import (
        AttachmentExecution,
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


@attachment_execution_task(
    name="ai_assistant.execute_log_analysis",
    queue="ai_assistant_log_analysis",
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
        return parse_snapshot(
            AIAnalysisOutputSchema,
            {"markdown": response.final_content},
            field_name="output_data",
            error_type=AttachmentSnapshotValidationError,
        )
    except AttachmentSnapshotValidationError as error:
        raise AttachmentOutputValidationError() from error
