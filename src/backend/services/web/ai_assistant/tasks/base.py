import logging
from typing import Any, Generic, TypeVar

from celery import Task
from celery.exceptions import Ignore, Retry
from django.core.exceptions import ImproperlyConfigured

from services.web.ai_assistant.constants import ExecutionObjectType
from services.web.ai_assistant.observability import start_execution_span
from services.web.ai_assistant.schemas import SnapshotInput

logger = logging.getLogger(__name__)
ExecutionT = TypeVar("ExecutionT")


class BaseExecutionTask(Task, Generic[ExecutionT]):
    """为消息和附件 Task 注入类型化快照，并统一收敛执行终态。

    业务 Task 继续使用 Celery 原生重试配置。调用 ``self.retry()`` 时不要覆盖
    ``args/kwargs``，否则会丢失平台投递的对象 ID；也不要使用 ``throw=False``，
    否则当前执行可能正常返回并被平台误判为成功。Celery ``Retry`` 仅表示任务
    已重投，平台会保持 PROCESSING，直到后续执行成功或重试耗尽抛出最终异常。
    Handler 配置的 countdown/ETA 必须短于对象硬失效阈值；一期不持久化待重试
    ETA，超过阈值的排队会被巡检视为失活执行。
    """

    abstract = True
    # 业务 run() 接收 Worker 内构造的执行快照，生产端只投递对象 ID 和 task_id。
    typing = False

    # 两个领域 Task 声明自己的投递参数、陈旧任务异常和日志对象名称。
    id_argument: str
    object_label: str
    object_type: ExecutionObjectType
    stale_exception: type[Exception]

    def _load_execution(
        self,
        *,
        instance_id: int,
        task_id: str,
        celery_task_id: str,
    ) -> ExecutionT:
        """由领域 Task 加载类型化执行上下文。"""

        raise NotImplementedError

    def _finish_success(
        self,
        *,
        execution: ExecutionT,
        task_id: str,
        output_data: SnapshotInput,
    ) -> dict[str, Any]:
        """由领域 Task 校验输出并写入成功终态。"""

        raise NotImplementedError

    def _finish_failure(
        self,
        *,
        execution: ExecutionT | None,
        instance_id: int,
        task_id: str,
        exception: Exception,
    ) -> bool:
        """由领域 Task 映射异常并写入失败终态。"""

        raise NotImplementedError

    def _handle_retry(self, *, execution: ExecutionT | None) -> None:
        """领域 Task 可在 Celery Retry 退出前强制持久化执行过程。"""

    def __call__(self, *args, **kwargs):
        """注入执行上下文；已终态或 task_id 不匹配的投递直接忽略。"""

        instance_id, task_id = self._extract_arguments(kwargs)
        stale_error = None
        delivery_info = self.request.delivery_info or {}
        with start_execution_span(
            object_type=self.object_type,
            object_id=instance_id,
            task_id=task_id,
            task_name=self.name,
            retries=self.request.retries,
            redelivered=bool(delivery_info.get("redelivered")),
        ):
            try:
                return self._execute(instance_id=instance_id, task_id=task_id)
            except self.stale_exception as error:
                # fencing 是预期控制流，在 Span 内吞掉后再转为 Celery Ignore，
                # 避免重复投递被 OTel 误标为业务 ERROR。
                stale_error = error
        logger.info(
            "忽略已失效或重复投递的 AI 助手任务",
            extra={
                "object_label": self.object_label,
                self.id_argument: instance_id,
                "task_id": task_id,
                "task_name": self.name,
            },
        )
        raise Ignore() from stale_error

    def _execute(self, *, instance_id: int, task_id: str):
        """执行业务 Task，并让领域 Hook 负责快照校验和终态写入。"""

        execution: ExecutionT | None = None
        try:
            execution = self._load_execution(
                instance_id=instance_id,
                task_id=task_id,
                celery_task_id=self.request.id,
            )
            # 保留 Celery request 的原始 kwargs，保证 self.retry() 能重投相同平台参数。
            result = self.run(execution)
        except Retry:
            # Retry 已由 Celery 完成重投；收尾观测失败不能覆盖该控制异常。
            self._handle_retry_best_effort(execution=execution)
            raise
        except self.stale_exception:
            raise
        except Exception as error:
            self._log_failure(
                "AI 助手任务执行失败",
                instance_id=instance_id,
                task_id=task_id,
            )
            self._fail_or_retry(execution=execution, instance_id=instance_id, task_id=task_id, exception=error)
            raise

        try:
            return self._finish_success(
                execution=execution,
                task_id=task_id,
                output_data=result,
            )
        except Retry:
            self._handle_retry_best_effort(execution=execution)
            raise
        except self.stale_exception:
            raise
        except Exception as error:
            self._log_failure(
                "AI 助手任务结果写入失败",
                instance_id=instance_id,
                task_id=task_id,
            )
            self._fail_or_retry(execution=execution, instance_id=instance_id, task_id=task_id, exception=error)
            raise

    def _fail_or_retry(
        self,
        *,
        execution: ExecutionT | None,
        instance_id: int,
        task_id: str,
        exception: Exception,
    ) -> None:
        """写失败终态；若领域 Hook 判定需要基础设施重试则改走 Retry。"""

        try:
            self._finish_failure(
                execution=execution,
                instance_id=instance_id,
                task_id=task_id,
                exception=exception,
            )
        except Retry:
            self._handle_retry_best_effort(execution=execution)
            raise

    def _handle_retry_best_effort(self, *, execution: ExecutionT | None) -> None:
        """尽力刷新 Retry 过程，始终保留 Celery 已建立的重投语义。"""

        try:
            self._handle_retry(execution=execution)
        except Exception:  # NOCC:broad-except(Retry 收尾失败不能覆盖 Celery 控制异常)
            logger.exception(
                "AI 助手任务 Retry 收尾失败",
                extra={"object_label": self.object_label, "task_name": self.name},
            )

    def _extract_arguments(self, kwargs) -> tuple[int, str]:
        """提取平台必需参数，错误的 Task 声明或投递在业务执行前直接暴露。"""

        instance_id = kwargs.get(self.id_argument)
        task_id = kwargs.get("task_id")
        if instance_id is None or not task_id:
            raise ImproperlyConfigured(f"{self.object_label} Task 必须提供 {self.id_argument} 和 task_id")
        return instance_id, task_id

    def _log_failure(
        self,
        message: str,
        *,
        instance_id: int,
        task_id: str,
    ) -> None:
        """记录可定位执行对象的结构化日志，不写入业务快照或异常正文。"""

        logger.exception(
            message,
            extra={
                "object_label": self.object_label,
                self.id_argument: instance_id,
                "task_id": task_id,
                "task_name": self.name,
            },
        )
