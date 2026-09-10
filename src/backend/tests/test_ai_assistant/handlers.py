from services.web.ai_assistant.constants import (
    AttachmentExportFormat,
    AttachmentType,
    ExecutionMode,
    MessageType,
)
from services.web.ai_assistant.exceptions import (
    AttachmentExecutionFailed,
    InvalidAttachmentState,
)
from services.web.ai_assistant.exporters import MarkdownDocumentExporter
from services.web.ai_assistant.handlers import (
    AttachmentPreparation,
    AttachmentTypeHandler,
    MessagePreparation,
    MessageTypeHandler,
    attachment_handler_registry,
    message_handler_registry,
)
from services.web.ai_assistant.models import Attachment, Conversation, Message
from services.web.ai_assistant.schemas import MessageSchema
from services.web.ai_assistant.services import AttachmentExecution, MessageExecution
from services.web.ai_assistant.tasks import (
    attachment_execution_task,
    message_execution_task,
)


def register_test_message_handler(handler):
    """注册测试用消息 Handler；同类型已有业务 Handler 时先移除再注册。

    业务 Handler（audit_search）常驻注册表后，平台机制测试需要用 Echo Handler
    临时替换真实消息类型；tearDown 的 unregister 语义保持不变。
    """

    message_handler_registry.unregister(str(handler.message_type))
    return message_handler_registry.register(handler)


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


class FeedbackEchoSyncHandler(EchoSyncHandler):
    """显式开放反馈的消息 Handler，用于反馈能力测试。"""

    supports_feedback = True


@message_execution_task(
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


class EchoAsyncHandler(MessageTypeHandler[EchoInput, EchoContext, EchoOutput]):
    """示例异步消息 Handler：在类体中直接绑定业务 Task。"""

    message_type = MessageType.NATURAL_LANGUAGE_SEARCH
    execution_mode = ExecutionMode.ASYNC
    input_model = EchoInput
    context_model = EchoContext
    output_model = EchoOutput
    async_task = execute_async_success

    def prepare(
        self,
        *,
        user: str,
        conversation: Conversation,
        parent_message: Message | None,
        input_data: EchoInput,
    ) -> MessagePreparation[EchoContext]:
        return MessagePreparation(parent_message=parent_message, context_data=EchoContext(prefix="async"))


class SystemSelectionAsyncHandler(EchoAsyncHandler):
    """验证初始化消息可复用平台异步创建链路。"""

    message_type = MessageType.SYSTEM_SELECTION


@message_execution_task(
    name="tests.ai_assistant.echo_async_failure",
    queue="tests_ai_assistant",
    acks_late=True,
    max_retries=2,
    default_retry_delay=1,
    time_limit=30,
)
def execute_async_failure(self, execution: MessageExecution[EchoInput, EchoContext]):
    raise RuntimeError("private detail")


@message_execution_task(
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


@message_execution_task(
    name="tests.ai_assistant.echo_async_retry_exhausted",
    queue="tests_ai_assistant",
    max_retries=2,
)
def execute_async_retry_exhausted(self, execution: MessageExecution[EchoInput, EchoContext]):
    """始终携带原异常重试，用于验证耗尽后由平台写入失败终态。"""

    raise self.retry(exc=RuntimeError("retry exhausted private detail"))


@message_execution_task(
    name="tests.ai_assistant.echo_async_retry_without_exc",
    queue="tests_ai_assistant",
    max_retries=2,
)
def execute_async_retry_without_exc(self, execution: MessageExecution[EchoInput, EchoContext]):
    """不携带原异常重试，耗尽后 Celery 抛出 MaxRetriesExceededError。"""

    raise self.retry()


class RetryableEchoError(RuntimeError):
    pass


@message_execution_task(
    name="tests.ai_assistant.echo_async_autoretry",
    queue="tests_ai_assistant",
    autoretry_for=(RetryableEchoError,),
    max_retries=2,
)
def execute_async_autoretry(self, execution: MessageExecution[EchoInput, EchoContext]):
    """普通业务异常由 Celery autoretry_for 转换成 Retry。"""

    raise RetryableEchoError("autoretry private detail")


class AttachmentEchoInput(MessageSchema):
    text: str


class AttachmentEchoContext(MessageSchema):
    prefix: str


class AttachmentEchoOutput(MessageSchema):
    content: str


class EditableAttachmentEchoHandler(
    AttachmentTypeHandler[AttachmentEchoInput, AttachmentEchoContext, AttachmentEchoOutput]
):
    attachment_type = AttachmentType.FIELD_STATISTICS
    execution_mode = ExecutionMode.SYNC
    input_model = AttachmentEchoInput
    context_model = AttachmentEchoContext
    output_model = AttachmentEchoOutput

    def prepare(
        self,
        *,
        user: str,
        source_message: Message,
        input_data: AttachmentEchoInput,
    ) -> AttachmentPreparation[AttachmentEchoContext]:
        return AttachmentPreparation(
            title="字段统计",
            context_data=AttachmentEchoContext(prefix="editable"),
        )

    def execute(
        self,
        *,
        execution,
    ) -> AttachmentEchoOutput:
        return AttachmentEchoOutput(content=f"{execution.context_data.prefix}:{execution.input_data.text}")

    def edit_output(
        self,
        *,
        attachment: Attachment,
        current_output: AttachmentEchoOutput,
        submitted_output: AttachmentEchoOutput,
    ) -> AttachmentEchoOutput:
        return submitted_output


class EchoAttachmentSyncHandler(
    AttachmentTypeHandler[AttachmentEchoInput, AttachmentEchoContext, AttachmentEchoOutput]
):
    attachment_type = AttachmentType.FIELD_STATISTICS
    execution_mode = ExecutionMode.SYNC
    input_model = AttachmentEchoInput
    context_model = AttachmentEchoContext
    output_model = AttachmentEchoOutput

    def prepare(
        self,
        *,
        user: str,
        source_message: Message,
        input_data: AttachmentEchoInput,
    ) -> AttachmentPreparation[AttachmentEchoContext]:
        return AttachmentPreparation(
            title="字段统计",
            context_data=AttachmentEchoContext(prefix="sync"),
        )

    def execute(
        self,
        *,
        execution: AttachmentExecution[AttachmentEchoInput, AttachmentEchoContext],
    ) -> AttachmentEchoOutput:
        return AttachmentEchoOutput(content=f"{execution.context_data.prefix}:{execution.input_data.text}")


class FeedbackAttachmentEchoHandler(EchoAttachmentSyncHandler):
    """显式开放反馈的附件 Handler，用于反馈能力测试。"""

    supports_feedback = True


class ExportableAnalysisAttachmentHandler(EditableAttachmentEchoHandler):
    """仅用于测试 Attachment 导出协议，不属于生产 AI 分析 Handler。"""

    attachment_type = AttachmentType.AI_ANALYSIS
    export_formats = (
        AttachmentExportFormat.MARKDOWN,
        AttachmentExportFormat.PDF,
    )

    def export(self, *, attachment, output_data, export_format):
        return MarkdownDocumentExporter(title=attachment.title, markdown=output_data.content).export(export_format)


@attachment_execution_task(
    name="tests.ai_assistant.echo_attachment_async_success",
    queue="tests_ai_assistant",
    acks_late=True,
    max_retries=2,
    default_retry_delay=1,
    time_limit=30,
)
def execute_attachment_async_success(
    self,
    execution: AttachmentExecution[AttachmentEchoInput, AttachmentEchoContext],
):
    return AttachmentEchoOutput(content=f"{execution.context_data.prefix}:{execution.input_data.text}")


class EchoAttachmentAsyncHandler(EchoAttachmentSyncHandler):
    """示例异步附件 Handler：在类体中直接绑定业务 Task。"""

    attachment_type = AttachmentType.AI_ANALYSIS
    execution_mode = ExecutionMode.ASYNC
    async_task = execute_attachment_async_success

    def prepare(
        self,
        *,
        user: str,
        source_message: Message,
        input_data: AttachmentEchoInput,
    ) -> AttachmentPreparation[AttachmentEchoContext]:
        return AttachmentPreparation(
            title="AI 分析",
            context_data=AttachmentEchoContext(prefix="async"),
        )


@attachment_execution_task(
    name="tests.ai_assistant.echo_attachment_async_failure",
    queue="tests_ai_assistant",
    acks_late=True,
    max_retries=2,
    default_retry_delay=1,
    time_limit=30,
)
def execute_attachment_async_failure(
    self,
    execution: AttachmentExecution[AttachmentEchoInput, AttachmentEchoContext],
):
    raise RuntimeError("private detail")


@attachment_execution_task(
    name="tests.ai_assistant.echo_attachment_async_retry",
    queue="tests_ai_assistant",
    acks_late=True,
    max_retries=2,
    default_retry_delay=1,
    time_limit=30,
)
def execute_attachment_async_retry(
    self,
    execution: AttachmentExecution[AttachmentEchoInput, AttachmentEchoContext],
):
    if self.request.retries == 0:
        raise self.retry(exc=RuntimeError("temporary private detail"))
    return AttachmentEchoOutput(content=f"{execution.context_data.prefix}:{execution.input_data.text}")


@attachment_execution_task(
    name="tests.ai_assistant.echo_attachment_async_retry_exhausted",
    queue="tests_ai_assistant",
    max_retries=2,
)
def execute_attachment_async_retry_exhausted(
    self,
    execution: AttachmentExecution[AttachmentEchoInput, AttachmentEchoContext],
):
    raise self.retry(exc=RuntimeError("retry exhausted private detail"))


@attachment_execution_task(
    name="tests.ai_assistant.echo_attachment_async_retry_without_exc",
    queue="tests_ai_assistant",
    max_retries=2,
)
def execute_attachment_async_retry_without_exc(
    self,
    execution: AttachmentExecution[AttachmentEchoInput, AttachmentEchoContext],
):
    raise self.retry()


class RetryableAttachmentError(RuntimeError):
    pass


@attachment_execution_task(
    name="tests.ai_assistant.echo_attachment_async_autoretry",
    queue="tests_ai_assistant",
    autoretry_for=(RetryableAttachmentError,),
    max_retries=2,
)
def execute_attachment_async_autoretry(
    self,
    execution: AttachmentExecution[AttachmentEchoInput, AttachmentEchoContext],
):
    raise RetryableAttachmentError("autoretry private detail")


@attachment_execution_task(
    name="tests.ai_assistant.echo_attachment_async_update_title",
    queue="tests_ai_assistant",
    acks_late=True,
    max_retries=2,
    default_retry_delay=1,
    time_limit=30,
)
def execute_attachment_async_update_title(
    self,
    execution: AttachmentExecution[AttachmentEchoInput, AttachmentEchoContext],
):
    execution.attachment.title = "任务内更新标题"
    execution.attachment.save(update_fields=["title", "updated_by", "updated_at"])
    return AttachmentEchoOutput(content=f"{execution.context_data.prefix}:{execution.input_data.text}")


@attachment_execution_task(
    name="tests.ai_assistant.echo_attachment_async_platform_error",
    queue="tests_ai_assistant",
    acks_late=True,
    max_retries=2,
    default_retry_delay=1,
    time_limit=30,
)
def execute_attachment_async_platform_error(
    self,
    execution: AttachmentExecution[AttachmentEchoInput, AttachmentEchoContext],
):
    raise InvalidAttachmentState(message="可公开的附件错误")


@attachment_execution_task(
    name="tests.ai_assistant.echo_attachment_async_execution_failed",
    queue="tests_ai_assistant",
    acks_late=True,
    max_retries=2,
    default_retry_delay=1,
    time_limit=30,
)
def execute_attachment_async_execution_failed(
    self,
    execution: AttachmentExecution[AttachmentEchoInput, AttachmentEchoContext],
):
    raise AttachmentExecutionFailed(message="可公开的执行失败")


@attachment_execution_task(
    name="tests.ai_assistant.echo_attachment_stream_success",
    queue="tests_ai_assistant",
    acks_late=True,
    max_retries=2,
    default_retry_delay=1,
    time_limit=30,
)
def execute_attachment_stream_success(
    self,
    execution: AttachmentExecution[AttachmentEchoInput, AttachmentEchoContext],
):
    """流式业务 Task 只通过平台注入的 Runtime 写 UI 事件，并返回最终类型化产物。"""

    execution.stream.send({"content": execution.input_data.text})
    return AttachmentEchoOutput(content=f"{execution.context_data.prefix}:{execution.input_data.text}")


@attachment_execution_task(
    name="tests.ai_assistant.echo_attachment_stream_retry",
    queue="tests_ai_assistant",
    acks_late=True,
    max_retries=2,
    default_retry_delay=1,
    time_limit=30,
)
def execute_attachment_stream_retry(
    self,
    execution: AttachmentExecution[AttachmentEchoInput, AttachmentEchoContext],
):
    """首次投递发布事件后重试，用于验证 Retry 前平台强制刷盘。"""

    execution.stream.send({"content": "before retry"})
    if self.request.retries == 0:
        raise self.retry()
    return AttachmentEchoOutput(content=f"{execution.context_data.prefix}:{execution.input_data.text}")


@attachment_execution_task(
    name="tests.ai_assistant.echo_attachment_stream_autoretry",
    queue="tests_ai_assistant",
    autoretry_for=(RetryableAttachmentError,),
    max_retries=2,
)
def execute_attachment_stream_autoretry(
    self,
    execution: AttachmentExecution[AttachmentEchoInput, AttachmentEchoContext],
):
    """通过 autoretry_for 触发重试，验证平台无需业务显式调用 retry。"""

    execution.stream.send({"content": "before autoretry"})
    raise RetryableAttachmentError("stream autoretry private detail")


@attachment_execution_task(
    name="tests.ai_assistant.echo_attachment_stream_failure",
    queue="tests_ai_assistant",
    acks_late=True,
    max_retries=2,
    default_retry_delay=1,
    time_limit=30,
)
def execute_attachment_stream_failure(
    self,
    execution: AttachmentExecution[AttachmentEchoInput, AttachmentEchoContext],
):
    """流式业务执行失败，用于验证失败终态同样经由 Runtime 收敛。"""

    execution.stream.send({"content": "partial"})
    raise AttachmentExecutionFailed(message="可公开的执行失败")


class EchoAttachmentStreamHandler(EchoAttachmentAsyncHandler):
    """示例流式附件 Handler：异步执行且开启 UI 实时流。"""

    is_stream = True
    async_task = execute_attachment_stream_success


def use_attachment_handler(test_case, handler: AttachmentTypeHandler) -> AttachmentTypeHandler:
    """在用例内独占注册某个附件 Handler。

    Handler 注册表是进程级单例，直接 ``register()`` 会因同类型已存在而抛出
    ``ImproperlyConfigured``。这里先卸载同类型再注册，并交由
    ``AttachmentHandlerRegistryMixin`` 在用例结束时统一清空注册表。
    """

    attachment_handler_registry.unregister(handler.attachment_type)
    return attachment_handler_registry.register(handler)


class AttachmentHandlerRegistryMixin:
    """为用例提供隔离的附件 Handler 注册表。

    注册表是进程级单例，任何用例遗留的 Handler 都会让后续用例注册失败或读到
    错误协议。这里在每个用例结束时清空全部类型，保证下一个用例从干净状态开始。
    """

    def tearDown(self):
        for attachment_type in AttachmentType.values:
            attachment_handler_registry.unregister(attachment_type)
        super().tearDown()
