from blueapps.core.celery import celery_app

from services.web.ai_assistant.constants import ExecutionMode, MessageType
from services.web.ai_assistant.handlers import MessagePreparation, MessageTypeHandler
from services.web.ai_assistant.models import Conversation, Message
from services.web.ai_assistant.schemas import MessageSchema
from services.web.ai_assistant.services import MessageExecution
from services.web.ai_assistant.tasks import MessageExecutionTask


class EchoInput(MessageSchema):
    text: str


class EchoContext(MessageSchema):
    prefix: str


class EchoOutput(MessageSchema):
    content: str


class EchoSyncHandler(MessageTypeHandler[EchoInput, EchoContext, EchoOutput]):
    message_type = MessageType.SYSTEM_SELECTION
    execution_mode = ExecutionMode.SYNC
    input_model = EchoInput
    context_model = EchoContext
    output_model = EchoOutput

    @property
    def async_task(self) -> None:
        return None

    def prepare(
        self,
        *,
        user: str,
        conversation: Conversation,
        parent_message: Message | None,
        input_data: EchoInput,
    ) -> MessagePreparation[EchoContext]:
        return MessagePreparation(parent_message=parent_message, context_data=EchoContext(prefix="system"))

    def execute(self, *, input_data: EchoInput, context_data: EchoContext) -> EchoOutput:
        return EchoOutput(content=f"{context_data.prefix}:{input_data.text}")


class EchoAsyncHandler(MessageTypeHandler[EchoInput, EchoContext, EchoOutput]):
    message_type = MessageType.NATURAL_LANGUAGE_SEARCH
    execution_mode = ExecutionMode.ASYNC
    input_model = EchoInput
    context_model = EchoContext
    output_model = EchoOutput

    @property
    def async_task(self) -> MessageExecutionTask:
        return execute_async_success

    def prepare(
        self,
        *,
        user: str,
        conversation: Conversation,
        parent_message: Message | None,
        input_data: EchoInput,
    ) -> MessagePreparation[EchoContext]:
        return MessagePreparation(parent_message=parent_message, context_data=EchoContext(prefix="async"))


class EchoMessageExecutionTask(MessageExecutionTask):
    """测试消息 Task 基类，完整生命周期由生产基类统一提供。"""

    abstract = True


@celery_app.task(
    bind=True,
    base=EchoMessageExecutionTask,
    name="tests.ai_assistant.echo_async_success",
    queue="tests_ai_assistant",
    acks_late=True,
    max_retries=2,
    default_retry_delay=1,
    time_limit=30,
)
def execute_async_success(self, execution: MessageExecution[EchoInput, EchoContext]):
    """模拟业务 Task 直接使用平台注入的消息实例和类型化快照。"""

    execution.message.output_data = {"task_seen_message": True}
    return EchoOutput(content=f"{execution.context_data.prefix}:{execution.input_data.text}")


@celery_app.task(
    bind=True,
    base=EchoMessageExecutionTask,
    name="tests.ai_assistant.echo_async_failure",
    queue="tests_ai_assistant",
    acks_late=True,
    max_retries=2,
    default_retry_delay=1,
    time_limit=30,
)
def execute_async_failure(self, execution: MessageExecution[EchoInput, EchoContext]):
    raise RuntimeError("private detail")


@celery_app.task(
    bind=True,
    base=EchoMessageExecutionTask,
    name="tests.ai_assistant.echo_async_retry",
    queue="tests_ai_assistant",
    acks_late=True,
    max_retries=2,
    default_retry_delay=1,
    time_limit=30,
)
def execute_async_retry(self, execution: MessageExecution[EchoInput, EchoContext]):
    if self.request.retries == 0:
        # Celery Retry 不写消息终态，下一次投递仍使用同一个业务 task_id。
        raise self.retry(exc=RuntimeError("temporary private detail"))
    return EchoOutput(content=f"{execution.context_data.prefix}:{execution.input_data.text}")


@celery_app.task(
    bind=True,
    base=EchoMessageExecutionTask,
    name="tests.ai_assistant.echo_async_retry_exhausted",
    queue="tests_ai_assistant",
    max_retries=2,
)
def execute_async_retry_exhausted(self, execution: MessageExecution[EchoInput, EchoContext]):
    """始终携带原异常重试，用于验证耗尽后由平台写入失败终态。"""

    raise self.retry(exc=RuntimeError("retry exhausted private detail"))


@celery_app.task(
    bind=True,
    base=EchoMessageExecutionTask,
    name="tests.ai_assistant.echo_async_retry_without_exc",
    queue="tests_ai_assistant",
    max_retries=2,
)
def execute_async_retry_without_exc(self, execution: MessageExecution[EchoInput, EchoContext]):
    """不携带原异常重试，耗尽后 Celery 抛出 MaxRetriesExceededError。"""

    raise self.retry()


class RetryableEchoError(RuntimeError):
    pass


@celery_app.task(
    bind=True,
    base=EchoMessageExecutionTask,
    name="tests.ai_assistant.echo_async_autoretry",
    queue="tests_ai_assistant",
    autoretry_for=(RetryableEchoError,),
    max_retries=2,
)
def execute_async_autoretry(self, execution: MessageExecution[EchoInput, EchoContext]):
    """普通业务异常由 Celery autoretry_for 转换成 Retry。"""

    raise RetryableEchoError("autoretry private detail")
