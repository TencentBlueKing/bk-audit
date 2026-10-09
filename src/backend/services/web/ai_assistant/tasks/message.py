from typing import Any

from services.web.ai_assistant.constants import ExecutionObjectType
from services.web.ai_assistant.exceptions import StaleMessageTask
from services.web.ai_assistant.models import Message
from services.web.ai_assistant.schemas import SnapshotInput
from services.web.ai_assistant.services.message_execution import (
    MessageExecution,
    finish_message_failure,
    finish_message_success,
    load_message_execution,
)
from services.web.ai_assistant.tasks.base import BaseExecutionTask


class MessageExecutionTask(BaseExecutionTask[MessageExecution]):
    """为业务消息 Task 注入 MessageExecution，并由平台收敛执行终态。"""

    abstract = True
    id_argument = "message_id"
    object_label = "消息"
    object_type = ExecutionObjectType.MESSAGE
    stale_exception = StaleMessageTask

    def _load_execution(
        self,
        *,
        instance_id: int,
        task_id: str,
        celery_task_id: str,
    ) -> MessageExecution:
        """将平台通用对象参数适配为消息领域加载函数。"""

        return load_message_execution(
            message_id=instance_id,
            task_id=task_id,
            celery_task_id=celery_task_id,
        )

    def _finish_success(
        self,
        *,
        execution: MessageExecution,
        task_id: str,
        output_data: SnapshotInput,
    ) -> dict[str, Any]:
        """将消息业务输出交给消息领域函数校验并收敛。"""

        return finish_message_success(execution=execution, task_id=task_id, output_data=output_data)

    def _finish_failure(
        self,
        *,
        execution: MessageExecution | None,
        instance_id: int,
        task_id: str,
        exception: Exception,
    ) -> bool:
        """将 Worker 异常交给消息领域函数映射为公开失败快照。"""

        return finish_message_failure(message_id=instance_id, task_id=task_id, exception=exception)

    def _handle_retry(self, *, execution: MessageExecution | None) -> None:
        """Retry 保持消息处理中，并刷新巡检使用的平台活动时间。"""

        if execution is not None:
            Message.touch_processing(instance_id=execution.message.id, task_id=execution.message.task_id)
