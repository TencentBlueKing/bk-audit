import os
import threading

from django.conf import settings

from services.web.ai_assistant.constants import (
    AttachmentType,
    ExecutionMode,
    MessageType,
)
from services.web.ai_assistant.handlers import (
    AttachmentPreparation,
    AttachmentTypeHandler,
    MessagePreparation,
    MessageTypeHandler,
)
from services.web.ai_assistant.models import Conversation, Message
from services.web.ai_assistant.schemas import MessageSchema
from services.web.ai_assistant.services import AttachmentExecution, MessageExecution
from services.web.ai_assistant.tasks import (
    attachment_execution_task,
    message_execution_task,
)

# 队列名带进程 pid，确保并行/重复运行的真实 Worker 各自独占队列，互不串消息。
INTEGRATION_QUEUE = f"{settings.CELERY_TEST_QUEUE_PREFIX}_{os.getpid()}_ai_assistant"


class IntegrationInput(MessageSchema):
    text: str


class IntegrationContext(MessageSchema):
    prefix: str


class IntegrationOutput(MessageSchema):
    content: str


@message_execution_task(
    name="tests.ai_assistant.integration.message_success",
    queue=INTEGRATION_QUEUE,
    acks_late=True,
)
def execute_real_message_success(
    self,
    execution: MessageExecution[IntegrationInput, IntegrationContext],
) -> IntegrationOutput:
    return IntegrationOutput(content=f"{execution.context_data.prefix}:{execution.input_data.text}")


class RealMessageSuccessHandler(MessageTypeHandler[IntegrationInput, IntegrationContext, IntegrationOutput]):
    message_type = MessageType.NATURAL_LANGUAGE_SEARCH
    execution_mode = ExecutionMode.ASYNC
    input_model = IntegrationInput
    context_model = IntegrationContext
    output_model = IntegrationOutput
    async_task = execute_real_message_success

    def prepare(
        self,
        *,
        user: str,
        conversation: Conversation,
        parent_message: Message | None,
        input_data: IntegrationInput,
    ) -> MessagePreparation[IntegrationContext]:
        return MessagePreparation(
            parent_message=parent_message,
            context_data=IntegrationContext(prefix="real"),
        )


@attachment_execution_task(
    name="tests.ai_assistant.integration.attachment_success",
    queue=INTEGRATION_QUEUE,
    acks_late=True,
)
def execute_real_attachment_success(
    self,
    execution: AttachmentExecution[IntegrationInput, IntegrationContext],
) -> IntegrationOutput:
    return IntegrationOutput(content=f"{execution.context_data.prefix}:{execution.input_data.text}")


class RealAttachmentSuccessHandler(AttachmentTypeHandler[IntegrationInput, IntegrationContext, IntegrationOutput]):
    attachment_type = AttachmentType.AI_ANALYSIS
    execution_mode = ExecutionMode.ASYNC
    input_model = IntegrationInput
    context_model = IntegrationContext
    output_model = IntegrationOutput
    async_task = execute_real_attachment_success

    def prepare(
        self,
        *,
        user: str,
        source_message: Message,
        input_data: IntegrationInput,
    ) -> AttachmentPreparation[IntegrationContext]:
        return AttachmentPreparation(
            title="真实 Celery 附件",
            context_data=IntegrationContext(prefix="real"),
        )


@attachment_execution_task(
    name="tests.ai_assistant.integration.attachment_stream_success",
    queue=INTEGRATION_QUEUE,
    acks_late=True,
)
def execute_real_attachment_stream_success(
    self,
    execution: AttachmentExecution[IntegrationInput, IntegrationContext],
) -> IntegrationOutput:
    execution.stream.send({"content": execution.input_data.text})
    return IntegrationOutput(content=f"{execution.context_data.prefix}:{execution.input_data.text}")


class RealAttachmentStreamSuccessHandler(RealAttachmentSuccessHandler):
    """通过真实 Worker 执行的平台流式附件。"""

    is_stream = True
    async_task = execute_real_attachment_stream_success


# ── 重试与并发观测器 ──────────────────────────────────────
# 观测器只保存计数和线程同步原语，绝不持有 Django Model 实例或数据库连接，
# 避免跨线程复用连接；业务断言仍以数据库快照为准。

retry_statuses: list[str] = []
retry_statuses_lock = threading.Lock()
autoretry_attempts = 0
autoretry_lock = threading.Lock()
duplicate_barrier: threading.Barrier | None = None
duplicate_executions = 0
duplicate_lock = threading.Lock()
old_task_execution_ids: list[str] = []
old_task_lock = threading.Lock()
stream_execution_ids: list[str] = []
stream_redis_keys: list[str] = []
stream_execution_lock = threading.Lock()
stream_duplicate_barrier: threading.Barrier | None = None
stream_duplicate_executions = 0
stream_duplicate_lock = threading.Lock()


class RetryableIntegrationError(RuntimeError):
    pass


def _record_stream_execution(execution: AttachmentExecution) -> None:
    """记录真实 Worker 创建的 execution，供集成测试验证换流与清理 Redis。"""

    with stream_execution_lock:
        stream_execution_ids.append(str(execution.stream.binding.config.execution_id))
        stream_redis_keys.append(execution.stream.binding.config.redis_key)


@attachment_execution_task(
    name="tests.ai_assistant.integration.attachment_stream_retry",
    queue=INTEGRATION_QUEUE,
    acks_late=True,
    max_retries=1,
    default_retry_delay=0,
)
def execute_real_attachment_stream_retry(
    self,
    execution: AttachmentExecution[IntegrationInput, IntegrationContext],
) -> IntegrationOutput:
    _record_stream_execution(execution)
    execution.stream.send({"attempt": self.request.retries})
    if self.request.retries == 0:
        raise self.retry(exc=RetryableIntegrationError("temporary stream error"), countdown=0)
    return IntegrationOutput(content="stream:success")


class RealAttachmentStreamRetryHandler(RealAttachmentStreamSuccessHandler):
    async_task = execute_real_attachment_stream_retry


@attachment_execution_task(
    name="tests.ai_assistant.integration.attachment_stream_duplicate",
    queue=INTEGRATION_QUEUE,
    acks_late=True,
)
def execute_real_attachment_stream_duplicate(
    self,
    execution: AttachmentExecution[IntegrationInput, IntegrationContext],
) -> IntegrationOutput:
    global stream_duplicate_executions
    _record_stream_execution(execution)
    execution.stream.send({"execution_id": str(execution.stream.binding.config.execution_id)})
    with stream_duplicate_lock:
        stream_duplicate_executions += 1
    barrier = stream_duplicate_barrier
    if barrier is not None:
        barrier.wait(timeout=settings.CELERY_TEST_TASK_TIMEOUT)
    return IntegrationOutput(content="duplicate:success")


class RealAttachmentStreamDuplicateHandler(RealAttachmentStreamSuccessHandler):
    async_task = execute_real_attachment_stream_duplicate


@attachment_execution_task(
    name="tests.ai_assistant.integration.attachment_stream_finalize_retry",
    queue=INTEGRATION_QUEUE,
    acks_late=True,
    max_retries=1,
    default_retry_delay=0,
)
def execute_real_attachment_stream_finalize_retry(
    self,
    execution: AttachmentExecution[IntegrationInput, IntegrationContext],
) -> IntegrationOutput:
    _record_stream_execution(execution)
    execution.stream.send({"content": execution.input_data.text})
    return IntegrationOutput(content="finalize:success")


class RealAttachmentStreamFinalizeRetryHandler(RealAttachmentStreamSuccessHandler):
    async_task = execute_real_attachment_stream_finalize_retry


@message_execution_task(
    name="tests.ai_assistant.integration.message_self_retry",
    queue=INTEGRATION_QUEUE,
    acks_late=True,
    max_retries=1,
    default_retry_delay=0,
)
def execute_real_message_self_retry(
    self,
    execution: MessageExecution[IntegrationInput, IntegrationContext],
) -> IntegrationOutput:
    execution.message.refresh_from_db(fields=["status"])
    with retry_statuses_lock:
        retry_statuses.append(execution.message.status)
    if self.request.retries == 0:
        raise self.retry(exc=RetryableIntegrationError("temporary private detail"), countdown=0)
    return IntegrationOutput(content="retry:success")


@message_execution_task(
    name="tests.ai_assistant.integration.message_autoretry_exhausted",
    queue=INTEGRATION_QUEUE,
    autoretry_for=(RetryableIntegrationError,),
    max_retries=1,
    default_retry_delay=0,
)
def execute_real_message_autoretry_exhausted(
    self,
    execution: MessageExecution[IntegrationInput, IntegrationContext],
) -> IntegrationOutput:
    global autoretry_attempts
    with autoretry_lock:
        autoretry_attempts += 1
    raise RetryableIntegrationError("autoretry private detail")


@message_execution_task(
    name="tests.ai_assistant.integration.message_duplicate",
    queue=INTEGRATION_QUEUE,
    acks_late=True,
)
def execute_real_message_duplicate(
    self,
    execution: MessageExecution[IntegrationInput, IntegrationContext],
) -> IntegrationOutput:
    global duplicate_executions
    with duplicate_lock:
        duplicate_executions += 1
    barrier = duplicate_barrier
    if barrier is not None:
        barrier.wait(timeout=settings.CELERY_TEST_TASK_TIMEOUT)
    return IntegrationOutput(content="duplicate:success")


@message_execution_task(
    name="tests.ai_assistant.integration.message_old_task",
    queue=INTEGRATION_QUEUE,
    acks_late=True,
)
def execute_real_message_old_task(
    self,
    execution: MessageExecution[IntegrationInput, IntegrationContext],
) -> IntegrationOutput:
    with old_task_lock:
        old_task_execution_ids.append(self.request.id)
    return IntegrationOutput(content="old:must-not-win")


class RealMessageSelfRetryHandler(RealMessageSuccessHandler):
    async_task = execute_real_message_self_retry


class RealMessageAutoretryFailureHandler(RealMessageSuccessHandler):
    async_task = execute_real_message_autoretry_exhausted


class RealMessageDuplicateHandler(RealMessageSuccessHandler):
    async_task = execute_real_message_duplicate


class RealMessageOldTaskHandler(RealMessageSuccessHandler):
    async_task = execute_real_message_old_task


def reset_retry_observations() -> None:
    global autoretry_attempts
    with retry_statuses_lock:
        retry_statuses.clear()
    with autoretry_lock:
        autoretry_attempts = 0


def reset_duplicate_observations(*, parties: int = 2) -> None:
    global duplicate_barrier, duplicate_executions
    duplicate_barrier = threading.Barrier(parties)
    with duplicate_lock:
        duplicate_executions = 0


def clear_duplicate_observations() -> None:
    global duplicate_barrier
    duplicate_barrier = None


def reset_old_task_observations() -> None:
    """清空业务执行 task ID，用于证明 fencing 发生在业务调用之前。"""

    with old_task_lock:
        old_task_execution_ids.clear()


def reset_stream_observations() -> None:
    """清空流式重试执行记录，避免集成用例之间共享进程状态。"""

    with stream_execution_lock:
        stream_execution_ids.clear()
        stream_redis_keys.clear()


http_stream_started = threading.Event()
http_stream_release = threading.Event()
http_attachment_fail_once = True


@attachment_execution_task(
    name="tests.ai_assistant.integration.attachment_http_stream",
    queue=INTEGRATION_QUEUE,
    acks_late=True,
)
def execute_real_attachment_http_stream(self, execution):
    execution.stream.send({"step": 1})
    http_stream_started.set()
    if not http_stream_release.wait(settings.CELERY_TEST_TASK_TIMEOUT):
        raise TimeoutError("HTTP stream test release timeout")
    execution.stream.send({"step": 2})
    return IntegrationOutput(content="http-stream:success")


class RealAttachmentHttpStreamHandler(RealAttachmentStreamSuccessHandler):
    async_task = execute_real_attachment_http_stream


@attachment_execution_task(
    name="tests.ai_assistant.integration.attachment_http_stream_retry",
    queue=INTEGRATION_QUEUE,
    acks_late=True,
    max_retries=1,
    default_retry_delay=0,
)
def execute_real_attachment_http_stream_retry(self, execution):
    execution.stream.send({"step": 1})
    http_stream_started.set()
    if not http_stream_release.wait(settings.CELERY_TEST_TASK_TIMEOUT):
        raise TimeoutError("HTTP stream test release timeout")
    if self.request.retries == 0:
        raise self.retry(exc=RetryableIntegrationError("http stream retry"), countdown=0)
    execution.stream.send({"step": 2})
    return IntegrationOutput(content="http-stream:success")


class RealAttachmentHttpStreamRetryHandler(RealAttachmentStreamSuccessHandler):
    async_task = execute_real_attachment_http_stream_retry


@attachment_execution_task(
    name="tests.ai_assistant.integration.attachment_http_fail_once",
    queue=INTEGRATION_QUEUE,
    acks_late=True,
)
def execute_real_attachment_http_fail_once(self, execution):
    global http_attachment_fail_once
    if http_attachment_fail_once:
        http_attachment_fail_once = False
        raise RuntimeError("http attachment fail")
    return IntegrationOutput(content="http-retry:success")


class RealAttachmentHttpFailOnceHandler(RealAttachmentSuccessHandler):
    async_task = execute_real_attachment_http_fail_once


def release_http_stream_events() -> None:
    """先唤醒仍卡在 wait() 上的 Worker，再交给 reset 清旗。"""

    http_stream_release.set()


def reset_http_stream_events() -> None:
    http_stream_started.clear()
    http_stream_release.clear()


def reset_http_attachment_fail_once() -> None:
    global http_attachment_fail_once
    http_attachment_fail_once = True


def reset_stream_duplicate_observations(*, parties: int = 2) -> None:
    """为同 task ID 的两次真实投递建立同步栅栏。"""

    global stream_duplicate_barrier, stream_duplicate_executions
    stream_duplicate_barrier = threading.Barrier(parties)
    with stream_duplicate_lock:
        stream_duplicate_executions = 0


def clear_stream_duplicate_observations() -> None:
    global stream_duplicate_barrier
    stream_duplicate_barrier = None
