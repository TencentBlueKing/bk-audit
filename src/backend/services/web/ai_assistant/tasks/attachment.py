from typing import Any

from django.db import DatabaseError

from services.web.ai_assistant.exceptions import StaleAttachmentTask
from services.web.ai_assistant.schemas import SnapshotInput
from services.web.ai_assistant.services.attachment_execution import (
    AttachmentExecution,
    finish_attachment_failure,
    finish_attachment_success,
    load_attachment_execution,
)
from services.web.ai_assistant.tasks.base import BaseExecutionTask


class AttachmentExecutionTask(BaseExecutionTask[AttachmentExecution]):
    """为业务附件 Task 注入 AttachmentExecution，并由平台收敛执行终态。"""

    abstract = True
    id_argument = "attachment_id"
    object_label = "附件"
    stale_exception = StaleAttachmentTask

    def _load_execution(
        self,
        *,
        instance_id: int,
        task_id: str,
        celery_task_id: str,
    ) -> AttachmentExecution:
        """将平台通用对象参数适配为附件领域加载函数。"""

        return load_attachment_execution(
            attachment_id=instance_id,
            task_id=task_id,
            celery_task_id=celery_task_id,
        )

    def _finish_success(
        self,
        *,
        execution: AttachmentExecution,
        task_id: str,
        output_data: SnapshotInput,
    ) -> dict[str, Any]:
        """将附件业务输出交给附件领域函数校验并收敛。"""

        try:
            return finish_attachment_success(execution=execution, task_id=task_id, output_data=output_data)
        except DatabaseError as error:
            # 流式最终事务失败属于基础设施故障；重试才能重新生成流并保留业务产物。
            if execution.has_stream:
                raise self.retry(exc=error) from error
            raise

    def _finish_failure(
        self,
        *,
        execution: AttachmentExecution | None,
        instance_id: int,
        task_id: str,
        exception: Exception,
    ) -> bool:
        """将 Worker 异常交给附件领域函数映射为公开失败快照。"""

        try:
            return finish_attachment_failure(
                attachment_id=instance_id,
                task_id=task_id,
                exception=exception,
                execution=execution,
            )
        except DatabaseError as error:
            if execution is not None and execution.has_stream:
                raise self.retry(exc=error) from error
            raise

    def _handle_retry(self, *, execution: AttachmentExecution | None) -> None:
        """Retry 退出前强制刷盘，避免本次执行已产生的事件丢失。"""

        if execution is not None and execution.has_stream:
            execution.stream.finish_retry()
