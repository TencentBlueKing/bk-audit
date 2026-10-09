from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Protocol, TypeVar, cast

from blueapps.core.celery import celery_app
from celery import Task

from services.web.ai_assistant.schemas import MessageSchema
from services.web.ai_assistant.tasks.attachment import AttachmentExecutionTask
from services.web.ai_assistant.tasks.message import MessageExecutionTask

if TYPE_CHECKING:
    from services.web.ai_assistant.services import AttachmentExecution, MessageExecution

InputT = TypeVar("InputT", bound=MessageSchema)
ContextT = TypeVar("ContextT", bound=MessageSchema)
OutputT = TypeVar("OutputT", bound=MessageSchema)


class MessageAsyncTask(Protocol[InputT, ContextT, OutputT]):
    """IDE 可识别的消息业务 Task；运行时对象仍是 Celery Task。

    业务函数只需要处理 ``execution`` 并返回类型化输出；平台 Task 会负责
    加载消息、校验 task_id、写入成功或失败终态。业务仍可以通过 ``self.retry()``
    使用 Celery 原生重试，但必须保证外部调用和结果写入具备幂等性。
    """

    name: str

    def run(self, execution: MessageExecution[InputT, ContextT]) -> OutputT:
        ...

    def apply_async(self, args=None, kwargs=None, task_id=None, **options):
        ...


class AttachmentAsyncTask(Protocol[InputT, ContextT, OutputT]):
    """IDE 可识别的附件业务 Task；运行时对象仍是 Celery Task。

    附件 Task 与消息 Task 共享同一套平台生命周期，但外部业务可以自行决定
    队列、重试次数、退避策略和 ``acks_late`` 等 Celery 配置。
    """

    name: str

    def run(self, execution: AttachmentExecution[InputT, ContextT]) -> OutputT:
        ...

    def apply_async(self, args=None, kwargs=None, task_id=None, **options):
        ...


MessageTaskFunction = Callable[
    [MessageExecutionTask, "MessageExecution[InputT, ContextT]"],
    OutputT,
]
AttachmentTaskFunction = Callable[
    [AttachmentExecutionTask, "AttachmentExecution[InputT, ContextT]"],
    OutputT,
]


def message_execution_task(
    **task_options: Any,
) -> Callable[[MessageTaskFunction[InputT, ContextT, OutputT]], MessageAsyncTask[InputT, ContextT, OutputT]]:
    """注册消息业务 Task，并原样透传 Celery 配置。

    ``bind=True`` 和平台基类由框架固定，接入方不需要手动管理消息状态；除这两项
    外的配置（例如 ``queue``、``acks_late``、``autoretry_for``）继续由接入方选择。
    Celery 的至少一次投递语义意味着业务执行逻辑需要自行保证可重复执行。
    """

    return cast(
        Any,
        _execution_task(
            base=MessageExecutionTask,
            decorator_name="message_execution_task",
            task_options=task_options,
        ),
    )


def attachment_execution_task(
    **task_options: Any,
) -> Callable[[AttachmentTaskFunction[InputT, ContextT, OutputT]], AttachmentAsyncTask[InputT, ContextT, OutputT],]:
    """注册附件业务 Task，并原样透传 Celery 的队列、重试和确认配置。"""

    return cast(
        Any,
        _execution_task(
            base=AttachmentExecutionTask,
            decorator_name="attachment_execution_task",
            task_options=task_options,
        ),
    )


def _execution_task(
    *,
    base: type[Task],
    decorator_name: str,
    task_options: dict[str, Any],
) -> Callable:
    """构造领域 Task 装饰器；业务配置原样交给 Celery，平台入口不可覆盖。"""

    owned_options = {"bind", "base"}.intersection(task_options)
    if owned_options:
        option_names = ", ".join(sorted(owned_options))
        raise TypeError(f"{decorator_name} 由平台固定配置: {option_names}")
    # Celery 无法保留业务函数的泛型，两个公开装饰器负责在唯一边界恢复静态类型。
    return celery_app.task(bind=True, base=base, **task_options)
