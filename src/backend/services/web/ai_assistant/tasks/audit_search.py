"""审计日志检索的业务 Celery 任务。

自然语言检索为异步消息（调 AIDev 耗时长）；
常见操作缓存刷新为声明式周期任务（对齐上游 periodic_task 惯例，beat 自动调度）。
"""

import logging

from blueapps.contrib.celery_tools.periodic import periodic_task
from blueapps.core.celery import celery_app
from celery.schedules import crontab

from services.web.ai_assistant.constants import MessageType
from services.web.ai_assistant.schemas.audit_search import NLSearchErrorSchema, NLSearchOutputSchema
from services.web.ai_assistant.services.message import MessageService
from services.web.ai_assistant.services.message_execution import MessageExecution
from services.web.ai_assistant.services.operation import OperationContextService
from services.web.ai_assistant.tasks.message import MessageExecutionTask
from services.web.query.ai_assistant.exceptions import AIAssistantError
from services.web.query.ai_assistant.services.nl2json import NL2JSONService

logger = logging.getLogger(__name__)


class NLSearchExecutionTask(MessageExecutionTask):
    """自然语言检索任务：消息成功后按 auto_execute 续链同步执行 LOG_SEARCH。

    预期内识别失败时消息同样收敛 SUCCESS（output_data 携带结构化 error 协议），
    无 condition 不续链；续链的日志检索为同步消息——在 Worker 线程内直接执行，
    成功即创建 SUCCESS 子消息；失败则子消息不创建，自然语言消息本身
    保留 SUCCESS 和 condition，前端可基于该消息重新发起检索。
    """

    abstract = True

    def _finish_success(self, *, execution: MessageExecution, task_id: str, output_data: NLSearchOutputSchema) -> dict:
        result = super()._finish_success(execution=execution, task_id=task_id, output_data=output_data)
        try:
            self._create_auto_log_search(execution=execution, output_data=output_data)
        except Exception:
            # 续链失败不回滚自然语言消息终态（识别成功保留 condition，子消息不创建）
            logger.exception(
                "[NLSearchExecutionTask] auto log search failed, message_id=%s, task_id=%s",
                execution.message.id,
                task_id,
            )
        return result

    @staticmethod
    def _create_auto_log_search(*, execution: MessageExecution, output_data: NLSearchOutputSchema) -> None:
        """以自然语言消息为父消息同步创建日志检索子消息（失败不创建）。"""

        message = execution.message
        if not execution.input_data.auto_execute:
            return
        if output_data.condition is None:
            # 识别失败（结构化 error 协议）无检索条件，不续链
            return
        MessageService(user=message.created_by).create(
            conversation=message.conversation,
            message_type=MessageType.LOG_SEARCH,
            input_data={"condition": output_data.condition.model_dump(mode="json")},
            parent_message_uid=str(message.uid),
        )
        logger.info(
            "[NLSearchExecutionTask] auto log search created, parent_message_id=%s",
            message.id,
        )


@celery_app.task(bind=True, base=NLSearchExecutionTask)
def execute_natural_language_search(self, execution: MessageExecution) -> NLSearchOutputSchema:  # noqa: N805
    """识别自然语言并产出受控检索条件（薄代理：调用 query 模块 NL2JSON 服务）。

    预期内识别失败（AI 未识别 / 输出非法 / 服务异常 / 超时）不抛出：
    消息任务收敛 SUCCESS 并携带结构化 error 协议供前端展示；
    仅非预期异常继续冒泡，由平台收敛为 FAILED。
    """

    context_data = execution.context_data
    try:
        condition = NL2JSONService.convert(
            query_text=execution.input_data.query_text,
            selection=context_data.system_selection,
            scope_id=context_data.scope_id,
            username=context_data.username,
        )
    except AIAssistantError as error:
        # query 侧业务异常自带稳定 error_code 与脱敏 message，属预期内失败
        logger.warning(
            "[execute_natural_language_search] nl2json recognized failure, message_id=%s, error_code=%s",
            execution.message.id,
            error.error_code,
        )
        return NLSearchOutputSchema(
            error=NLSearchErrorSchema(error_code=error.error_code, error_message=error.message),
        )
    return NLSearchOutputSchema(condition=condition)


@periodic_task(run_every=crontab(hour="*/1"))
def refresh_common_queries() -> dict:
    """每小时聚合最近成功自然语言消息，按系统刷新常见操作 Redis 缓存。

    周期随代码声明（blueapps periodic_task，对齐上游 query/tasks.py 惯例），
    由 beat 自动调度，无需在 django_celery_beat 后台手动配置；
    任务幂等，重复执行只会覆盖为相同数据。
    """

    return OperationContextService.refresh_common_queries()
