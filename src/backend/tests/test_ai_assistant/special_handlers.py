"""专项测试 Handler：跨进程通过 Redis 控制 key 观测重投与 execution 切换。"""

import os
import threading
import time

from django.conf import settings
from django.db import connections
from django_redis import get_redis_connection

from services.web.ai_assistant.constants import AttachmentType, ExecutionMode
from services.web.ai_assistant.handlers import (
    AttachmentPreparation,
    AttachmentTypeHandler,
    attachment_handler_registry,
)
from services.web.ai_assistant.models import Message
from services.web.ai_assistant.schemas import MessageSchema
from services.web.ai_assistant.streaming import UIStreamRuntime
from services.web.ai_assistant.tasks import attachment_execution_task
from tests.test_ai_assistant.integration_handlers import (
    IntegrationContext,
    IntegrationInput,
    IntegrationOutput,
    RetryableIntegrationError,
)

SPECIAL_QUEUE_ENV = "BKAPP_AI_ASSISTANT_SPECIAL_QUEUE"
SPECIAL_HANDLERS_ENV = "BKAPP_AI_ASSISTANT_SPECIAL_HANDLERS"
TEST_DATABASE_ENV = "BKAPP_TEST_DATABASE_NAME"
SPECIAL_REDELIVERY_QUEUE = os.environ.get(
    SPECIAL_QUEUE_ENV,
    f"{settings.CELERY_TEST_QUEUE_PREFIX}_{os.getpid()}_redelivery",
)

_CONTROL_FIELDS = ("attempt", "started", "execution_ids", "redis_keys")


def _bind_test_database() -> None:
    """Worker 子进程改连 Django 测试库，避免读写业务库。"""

    database_name = os.environ.get(TEST_DATABASE_ENV)
    if not database_name:
        return
    settings.DATABASES["default"]["NAME"] = database_name
    connections.close_all()


def redelivery_control_key(task_id: str, field: str) -> str:
    return f"{settings.CELERY_TEST_QUEUE_PREFIX}:{task_id}:{field}"


def _decode(value) -> str:
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


def wait_for_redelivery_started(*, task_id: str, timeout: float | None = None) -> None:
    deadline = time.monotonic() + (timeout or settings.CELERY_TEST_TASK_TIMEOUT)
    client = get_redis_connection("redis")
    key = redelivery_control_key(task_id, "started")
    while time.monotonic() < deadline:
        if client.get(key):
            return
        time.sleep(0.05)
    raise AssertionError(f"等待重投 started 超时: task_id={task_id}")


def read_redelivery_execution_ids(task_id: str) -> list[str]:
    client = get_redis_connection("redis")
    return [_decode(item) for item in client.lrange(redelivery_control_key(task_id, "execution_ids"), 0, -1)]


def read_redelivery_redis_keys(task_id: str) -> list[str]:
    client = get_redis_connection("redis")
    return [_decode(item) for item in client.lrange(redelivery_control_key(task_id, "redis_keys"), 0, -1)]


def clear_redelivery_control(task_id: str) -> None:
    client = get_redis_connection("redis")
    keys = [redelivery_control_key(task_id, field) for field in _CONTROL_FIELDS]
    if keys:
        client.delete(*keys)


@attachment_execution_task(
    name="tests.ai_assistant.special.attachment_redelivery",
    queue=SPECIAL_REDELIVERY_QUEUE,
    acks_late=True,
)
def execute_special_redelivery(self, execution):
    client = get_redis_connection("redis")
    task_id = execution.attachment.task_id
    attempt = int(client.incr(redelivery_control_key(task_id, "attempt")))
    client.rpush(redelivery_control_key(task_id, "execution_ids"), str(execution.stream.binding.config.execution_id))
    client.rpush(redelivery_control_key(task_id, "redis_keys"), execution.stream.binding.config.redis_key)
    execution.stream.send({"attempt": attempt})
    if attempt == 1:
        client.set(redelivery_control_key(task_id, "started"), "1")
        time.sleep(settings.CELERY_TEST_TASK_TIMEOUT * 2)
        raise TimeoutError("special redelivery task was not killed")
    return IntegrationOutput(content="redelivery:success")


class SpecialRedeliveryHandler(AttachmentTypeHandler[IntegrationInput, IntegrationContext, IntegrationOutput]):
    attachment_type = AttachmentType.AI_ANALYSIS
    execution_mode = ExecutionMode.ASYNC
    is_stream = True
    input_model = IntegrationInput
    context_model = IntegrationContext
    output_model = IntegrationOutput
    async_task = execute_special_redelivery

    def prepare(
        self,
        *,
        user: str,
        source_message: Message,
        input_data: IntegrationInput,
    ) -> AttachmentPreparation[IntegrationContext]:
        return AttachmentPreparation(
            title="专项重投附件",
            context_data=IntegrationContext(prefix="redelivery"),
        )


SPECIAL_FAILURE_QUEUE = f"{settings.CELERY_TEST_QUEUE_PREFIX}_{os.getpid()}_failures"

checkpoint_pending_after_send = 0
checkpoint_pending_lock = threading.Lock()
competition_deliveries = 0
competition_lock = threading.Lock()
competition_hold = threading.Event()
competition_release = threading.Event()
competition_execution_ids: list[str] = []
competition_task_ids: list[str] = []


def reset_checkpoint_observations() -> None:
    global checkpoint_pending_after_send
    with checkpoint_pending_lock:
        checkpoint_pending_after_send = 0


def release_competition_observations() -> None:
    competition_release.set()


def reset_competition_observations() -> None:
    global competition_deliveries
    competition_hold.clear()
    competition_release.clear()
    with competition_lock:
        competition_deliveries = 0
        competition_execution_ids.clear()
        competition_task_ids.clear()


@attachment_execution_task(
    name="tests.ai_assistant.special.attachment_redis_degraded",
    queue=SPECIAL_FAILURE_QUEUE,
    acks_late=True,
)
def execute_special_redis_degraded(self, execution):
    execution.stream.send({"step": 1})
    return IntegrationOutput(content="redis-degraded:success")


class SpecialRedisDegradedHandler(AttachmentTypeHandler[IntegrationInput, IntegrationContext, IntegrationOutput]):
    attachment_type = AttachmentType.AI_ANALYSIS
    execution_mode = ExecutionMode.ASYNC
    is_stream = True
    input_model = IntegrationInput
    context_model = IntegrationContext
    output_model = IntegrationOutput
    async_task = execute_special_redis_degraded

    def prepare(self, *, user: str, source_message: Message, input_data: IntegrationInput):
        return AttachmentPreparation(title="专项 Redis 降级", context_data=IntegrationContext(prefix="redis"))


@attachment_execution_task(
    name="tests.ai_assistant.special.attachment_checkpoint_fail_once",
    queue=SPECIAL_FAILURE_QUEUE,
    acks_late=True,
)
def execute_special_checkpoint_fail_once(self, execution):
    global checkpoint_pending_after_send

    for index in range(UIStreamRuntime.CHECKPOINT_EVENT_COUNT):
        execution.stream.send({"index": index})
    with checkpoint_pending_lock:
        checkpoint_pending_after_send = execution.stream.pending_count
    return IntegrationOutput(content="checkpoint:success")


class SpecialCheckpointFailOnceHandler(SpecialRedisDegradedHandler):
    async_task = execute_special_checkpoint_fail_once


@attachment_execution_task(
    name="tests.ai_assistant.special.attachment_finalize_fail_once",
    queue=SPECIAL_FAILURE_QUEUE,
    acks_late=True,
    max_retries=1,
    default_retry_delay=0,
)
def execute_special_finalize_fail_once(self, execution):
    with competition_lock:
        competition_execution_ids.append(str(execution.stream.binding.config.execution_id))
        competition_task_ids.append(execution.stream.binding.config.redis_key)
    execution.stream.send({"attempt": self.request.retries})
    return IntegrationOutput(content="finalize:success")


class SpecialFinalizeFailOnceHandler(SpecialRedisDegradedHandler):
    async_task = execute_special_finalize_fail_once


@attachment_execution_task(
    name="tests.ai_assistant.special.attachment_retry_race",
    queue=SPECIAL_FAILURE_QUEUE,
    acks_late=True,
)
def execute_special_retry_race(self, execution):
    global competition_deliveries
    with competition_lock:
        competition_deliveries += 1
        delivery = competition_deliveries
        competition_execution_ids.append(str(execution.stream.binding.config.execution_id))
        competition_task_ids.append(execution.attachment.task_id)
    execution.stream.send({"delivery": delivery})
    if delivery == 1:
        competition_hold.set()
        if not competition_release.wait(settings.CELERY_TEST_TASK_TIMEOUT):
            raise TimeoutError("competition release timeout")
        return IntegrationOutput(content="race:old")
    if delivery == 2:
        raise RuntimeError("competition fail")
    return IntegrationOutput(content="race:new")


class SpecialRetryRaceHandler(SpecialRedisDegradedHandler):
    async_task = execute_special_retry_race


SPECIAL_CONCURRENCY_QUEUE = f"{settings.CELERY_TEST_QUEUE_PREFIX}_{os.getpid()}_concurrency"
SPECIAL_CAPACITY_QUEUE = f"{settings.CELERY_TEST_QUEUE_PREFIX}_{os.getpid()}_capacity"

# 并发量只用于制造执行重叠，不是性能 SLA。
CONCURRENT_ATTACHMENT_COUNT = 3
CONCURRENT_SEQUENCE = [{"step": 1}, {"step": 2}, {"step": 3}]

sequence_started = threading.Event()
sequence_release = threading.Event()
delete_hold = threading.Event()
delete_release = threading.Event()
idle_started = threading.Event()
idle_release = threading.Event()
isolation_overlap_started = threading.Event()
isolation_release = threading.Event()
isolation_started_count = 0
isolation_lock = threading.Lock()


def release_concurrency_observations() -> None:
    sequence_release.set()
    delete_release.set()
    idle_release.set()
    isolation_release.set()


def reset_concurrency_observations() -> None:
    global isolation_started_count

    sequence_started.clear()
    sequence_release.clear()
    delete_hold.clear()
    delete_release.clear()
    idle_started.clear()
    idle_release.clear()
    isolation_overlap_started.clear()
    isolation_release.clear()
    with isolation_lock:
        isolation_started_count = 0


@attachment_execution_task(
    name="tests.ai_assistant.special.attachment_sequence",
    queue=SPECIAL_CONCURRENCY_QUEUE,
    acks_late=True,
)
def execute_special_sequence(self, execution):
    for item in CONCURRENT_SEQUENCE:
        execution.stream.send(item)
    sequence_started.set()
    if not sequence_release.wait(settings.CELERY_TEST_TASK_TIMEOUT):
        raise TimeoutError("sequence release timeout")
    return IntegrationOutput(content="sequence:done")


class SpecialSequenceHandler(SpecialRedisDegradedHandler):
    async_task = execute_special_sequence


@attachment_execution_task(
    name="tests.ai_assistant.special.attachment_isolation",
    queue=SPECIAL_CONCURRENCY_QUEUE,
    acks_late=True,
)
def execute_special_isolation(self, execution):
    global isolation_started_count

    token = execution.input_data.text
    execution.stream.send({"token": token})
    with isolation_lock:
        isolation_started_count += 1
        if isolation_started_count >= 2:
            isolation_overlap_started.set()
    if not isolation_release.wait(settings.CELERY_TEST_TASK_TIMEOUT):
        raise TimeoutError("isolation release timeout")
    if token.endswith(":fail"):
        raise RuntimeError("isolation fail")
    return IntegrationOutput(content=f"iso:{token}")


class SpecialIsolationHandler(SpecialRedisDegradedHandler):
    async_task = execute_special_isolation


@attachment_execution_task(
    name="tests.ai_assistant.special.attachment_delete_hold",
    queue=SPECIAL_CONCURRENCY_QUEUE,
    acks_late=True,
)
def execute_special_delete_hold(self, execution):
    execution.stream.send({"phase": "before-delete"})
    delete_hold.set()
    if not delete_release.wait(settings.CELERY_TEST_TASK_TIMEOUT):
        raise TimeoutError("delete release timeout")
    return IntegrationOutput(content="delete:done")


class SpecialDeleteHoldHandler(SpecialRedisDegradedHandler):
    async_task = execute_special_delete_hold


@attachment_execution_task(
    name="tests.ai_assistant.special.attachment_idle_hold",
    queue=SPECIAL_CONCURRENCY_QUEUE,
    acks_late=True,
)
def execute_special_idle_hold(self, execution):
    idle_started.set()
    if not idle_release.wait(settings.CELERY_TEST_TASK_TIMEOUT):
        raise TimeoutError("idle release timeout")
    return IntegrationOutput(content="idle:done")


class SpecialIdleHoldHandler(SpecialRedisDegradedHandler):
    async_task = execute_special_idle_hold


class SpecialCapacityInput(MessageSchema):
    events: list


@attachment_execution_task(
    name="tests.ai_assistant.special.attachment_capacity",
    queue=SPECIAL_CAPACITY_QUEUE,
    acks_late=True,
)
def execute_special_capacity(self, execution):
    for item in execution.input_data.events:
        execution.stream.send(item)
    return IntegrationOutput(content="capacity:done")


class SpecialCapacityHandler(SpecialRedisDegradedHandler):
    input_model = SpecialCapacityInput
    async_task = execute_special_capacity


SPECIAL_SSE_QUEUE = f"{settings.CELERY_TEST_QUEUE_PREFIX}_{os.getpid()}_sse_e2e"

realtime_sse_first_sent = threading.Event()
realtime_sse_release = threading.Event()
realtime_sse_second_sent = threading.Event()
realtime_sse_finish = threading.Event()


def release_realtime_sse_observations() -> None:
    """释放实时 SSE 测试任务，异常清理路径也可安全重复调用。"""

    realtime_sse_release.set()


def finish_realtime_sse_observations() -> None:
    """允许第二帧写入后的任务进入终态。"""

    realtime_sse_finish.set()


def reset_realtime_sse_observations() -> None:
    """清空实时 SSE 屏障，隔离同一测试类中的连续场景。"""

    realtime_sse_first_sent.clear()
    realtime_sse_release.clear()
    realtime_sse_second_sent.clear()
    realtime_sse_finish.clear()


@attachment_execution_task(
    name="tests.ai_assistant.special.attachment_sse_realtime",
    queue=SPECIAL_SSE_QUEUE,
    acks_late=True,
)
def execute_special_sse_realtime(self, execution):
    """写入首帧后阻塞，证明 Web 可在任务终态前实时下发事件。"""

    execution.stream.send({"step": 1})
    realtime_sse_first_sent.set()
    if not realtime_sse_release.wait(settings.CELERY_TEST_TASK_TIMEOUT):
        raise TimeoutError("realtime SSE release timeout")
    execution.stream.send({"step": 2})
    realtime_sse_second_sent.set()
    if not realtime_sse_finish.wait(settings.CELERY_TEST_TASK_TIMEOUT):
        raise TimeoutError("realtime SSE finish timeout")
    return IntegrationOutput(content="sse-e2e:success")


class SpecialRealtimeSSEHandler(SpecialRedisDegradedHandler):
    """使用独立专项队列的实时 SSE Attachment Handler。"""

    async_task = execute_special_sse_realtime


retry_sse_first_sent = threading.Event()
retry_sse_release = threading.Event()
retry_sse_second_sent = threading.Event()
retry_sse_finish = threading.Event()


def release_retry_sse_observations() -> None:
    """允许第一次执行触发 Celery 原生重试。"""

    retry_sse_release.set()


def finish_retry_sse_observations() -> None:
    """允许重试执行写入最终成功终态。"""

    retry_sse_finish.set()


def reset_retry_sse_observations() -> None:
    """清空自动重试场景的执行屏障。"""

    retry_sse_first_sent.clear()
    retry_sse_release.clear()
    retry_sse_second_sent.clear()
    retry_sse_finish.clear()


@attachment_execution_task(
    name="tests.ai_assistant.special.attachment_sse_realtime_retry",
    queue=SPECIAL_SSE_QUEUE,
    acks_late=True,
    max_retries=1,
    default_retry_delay=0,
)
def execute_special_sse_realtime_retry(self, execution):
    """首次执行主动重试，第二次执行停在终态前供客户端切换新流。"""

    attempt = self.request.retries + 1
    execution.stream.send({"attempt": attempt})
    if attempt == 1:
        retry_sse_first_sent.set()
        if not retry_sse_release.wait(settings.CELERY_TEST_TASK_TIMEOUT):
            raise TimeoutError("retry SSE release timeout")
        raise self.retry(exc=RetryableIntegrationError("sse e2e retry"), countdown=0)

    retry_sse_second_sent.set()
    if not retry_sse_finish.wait(settings.CELERY_TEST_TASK_TIMEOUT):
        raise TimeoutError("retry SSE finish timeout")
    return IntegrationOutput(content="sse-e2e-retry:success")


class SpecialRealtimeSSERetryHandler(SpecialRedisDegradedHandler):
    """验证 Celery 自动重试切换 execution 的流式 Handler。"""

    async_task = execute_special_sse_realtime_retry


if os.environ.get(SPECIAL_HANDLERS_ENV) == "1":
    from blueapps.core.celery import celery_app

    _bind_test_database()
    celery_app.conf.task_always_eager = False
    celery_app.conf.broker_url = settings.CELERY_TEST_BROKER_URL
    attachment_handler_registry.unregister(AttachmentType.AI_ANALYSIS)
    attachment_handler_registry.register(SpecialRedeliveryHandler())
