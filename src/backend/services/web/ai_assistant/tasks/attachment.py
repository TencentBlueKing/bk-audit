import logging

from celery import Task
from celery.exceptions import Ignore, Retry
from django.core.exceptions import ImproperlyConfigured

from services.web.ai_assistant.constants import AttachmentErrorCode
from services.web.ai_assistant.exceptions import (
    AttachmentOutputValidationError,
    StaleAttachmentTask,
)
from services.web.ai_assistant.services import AttachmentExecutor

logger = logging.getLogger(__name__)


class AttachmentExecutionTask(Task):
    """将队列中的附件 ID 转为执行上下文，并统一管理附件终态。

    业务 Task 仍使用 Celery 原生配置。`max_retries` 只限制重试次数，
    普通异常需配置 `autoretry_for` 或由业务使用 `raise self.retry(...)`
    发起重试。Celery `Retry` 只表示已重投，平台保持 PROCESSING；重试
    耗尽后的原异常或 MaxRetriesExceededError 才会写入 FAILED。调用
    `retry()` 时不得覆盖 `args/kwargs`，否则会丢失平台投递的附件 ID；
    也不得使用 `throw=False`，否则当前调用可能正常返回并被误判为成功。
    """

    abstract = True
    # 业务 run() 接收 Worker 内构造的 AttachmentExecution，而生产端只投递 ID。
    # 因此关闭 Celery 对 run() 签名的生产端校验，并由本基类校验 ID。
    typing = False

    def __call__(self, *args, **kwargs):
        """注入执行上下文；已终态或 task_id 不匹配的投递直接忽略。"""

        attachment_id, task_id = self._extract_attachment_arguments(kwargs)
        try:
            return self._execute_attachment(attachment_id=attachment_id, task_id=task_id)
        except StaleAttachmentTask as error:
            logger.info(
                "忽略已失效或重复投递的 AI 助手附件任务",
                extra={"attachment_id": attachment_id, "task_id": task_id},
            )
            raise Ignore() from error

    def _execute_attachment(self, *, attachment_id: int, task_id: str):
        """加载类型化快照后执行业务，Retry 不收敛状态。"""

        try:
            execution = AttachmentExecutor.load_execution(
                attachment_id=attachment_id,
                task_id=task_id,
                celery_task_id=self.request.id,
            )
            # 直接调用 run() 避免用 AttachmentExecution 覆盖 Celery request 中的原始 ID；
            # self.retry() 因此仍会使用 attachment_id/task_id 生成下一次投递。
            result = self.run(execution)
        except (Retry, StaleAttachmentTask):
            raise
        except Exception as error:
            logger.exception(
                "AI 助手附件任务执行失败",
                extra={"attachment_id": attachment_id, "task_id": task_id, "task_name": self.name},
            )
            AttachmentExecutor.mark_failed(
                attachment_id=attachment_id,
                task_id=task_id,
                exception=error,
            )
            raise

        try:
            return AttachmentExecutor.mark_success(
                execution=execution,
                task_id=task_id,
                output_data=result,
            )
        except StaleAttachmentTask:
            raise
        except AttachmentOutputValidationError as error:
            logger.exception(
                "AI 助手附件任务结果写入失败",
                extra={"attachment_id": attachment_id, "task_id": task_id, "task_name": self.name},
            )
            AttachmentExecutor.mark_failed(
                attachment_id=attachment_id,
                task_id=task_id,
                exception=error,
                error_code=AttachmentErrorCode.OUTPUT_VALIDATION_FAILED,
            )
            raise
        except Exception as error:
            logger.exception(
                "AI 助手附件任务结果写入失败",
                extra={"attachment_id": attachment_id, "task_id": task_id, "task_name": self.name},
            )
            AttachmentExecutor.mark_failed(
                attachment_id=attachment_id,
                task_id=task_id,
                exception=error,
            )
            raise

    @staticmethod
    def _extract_attachment_arguments(kwargs) -> tuple[int, str]:
        """提取平台必需参数，错误的 Task 定义在执行前直接暴露。"""

        attachment_id = kwargs.get("attachment_id")
        task_id = kwargs.get("task_id")
        if attachment_id is None or not task_id:
            raise ImproperlyConfigured("附件 Task 必须提供 attachment_id 和 task_id")
        return attachment_id, task_id
