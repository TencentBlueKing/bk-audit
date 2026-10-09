import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import TypeVar

from amqp.exceptions import ChannelError
from blueapps.core.celery import celery_app
from celery import signals
from celery.contrib.testing.worker import start_worker
from django.conf import settings
from django.db import close_old_connections
from django.db.models import Model
from kombu import pools as kombu_pools

ModelT = TypeVar("ModelT", bound=Model)


def once_then_original(original, *, exc: BaseException):
    """第一次调用抛出指定异常，后续调用回落到原实现。"""

    lock = threading.Lock()
    attempts = {"count": 0}

    def wrapper(*args, **kwargs):
        with lock:
            attempts["count"] += 1
            current = attempts["count"]
        if current == 1:
            raise exc
        return original(*args, **kwargs)

    wrapper.attempts = attempts
    return wrapper


def _reset_broker_pools() -> None:
    """关闭当前 Broker 连接池，但不注销项目唯一 Celery App。

    Celery 会缓存 Producer 和 Broker 连接池；切换 ``broker_url`` 前后必须清理
    两层缓存，否则后续投递可能继续复用上一个 Broker 的连接。这里不能调用
    ``celery_app.close()``，该方法面向动态 App，会把项目单例从全局注册表注销。
    """

    producer_pool = celery_app.amqp._producer_pool
    if producer_pool is not None:
        producer_pool.force_close_all()
        celery_app.amqp._producer_pool = None
    broker_pool = celery_app._pool
    if broker_pool is not None:
        broker_pool.force_close_all()
        celery_app._pool = None
    # kombu 全局 connections/producers 会缓存已关闭的池；只清空 App 引用
    # 时，后续 Worker 仍可能拿到 closed pool。
    kombu_pools.reset()


def _delete_queue(queue_name: str) -> None:
    """清理上次异常退出遗留的测试消息；队列名只能来自测试端生成。"""

    with celery_app.connection_for_write() as connection:
        with connection.channel() as channel:
            channel.queue_delete(queue=queue_name)


@contextmanager
def running_celery_worker(*, queue_name: str) -> Iterator[None]:
    """临时把项目 Celery App 切到 RabbitMQ，并启动两个线程的真实 Worker。

    职责：仅在上下文内把唯一 Celery App 从日常 Redis/eager 切换到与生产一致的
    RabbitMQ 非 eager 模式，退出时无条件恢复原配置；确保集成测试通过真实 Broker
    投递并至少执行一次，不污染其他测试的 App 状态。
    """

    original = {
        "broker_url": celery_app.conf.broker_url,
        "task_always_eager": celery_app.conf.task_always_eager,
        "task_eager_propagates": celery_app.conf.task_eager_propagates,
        "task_default_queue": celery_app.conf.task_default_queue,
    }
    queues = celery_app.amqp.queues
    original_queues = dict(queues)
    original_aliases = dict(queues.aliases)
    original_consume_from = None if queues._consume_from is None else dict(queues._consume_from)
    _reset_broker_pools()
    celery_app.conf.update(
        broker_url=settings.CELERY_TEST_BROKER_URL,
        task_always_eager=False,
        task_eager_propagates=False,
        task_default_queue=queue_name,
    )
    try:
        try:
            _delete_queue(queue_name)
        except ChannelError as error:
            # 只忽略队列不存在（404）；连接失败、认证失败等其他错误必须暴露。
            if error.reply_code != 404:
                raise
        with start_worker(
            celery_app,
            pool="threads",
            concurrency=2,
            queues=[queue_name],
            perform_ping_check=False,
            shutdown_timeout=settings.CELERY_TEST_TASK_TIMEOUT,
        ):
            yield
    finally:
        try:
            _delete_queue(queue_name)
        except ChannelError as error:
            if error.reply_code != 404:
                raise
        finally:
            try:
                _reset_broker_pools()
            finally:
                celery_app.conf.update(**original)
                queues.clear()
                queues.update(original_queues)
                queues.aliases.clear()
                queues.aliases.update(original_aliases)
                queues._consume_from = original_consume_from


def wait_for_snapshot(
    *,
    model: type[ModelT],
    instance_id: int,
    predicate: Callable[[ModelT], bool],
) -> ModelT:
    """轮询 Worker 写入的数据库快照；超时输出最后状态便于定位失败。

    Worker 在独立线程/连接中提交事务，主测试线程需要短间隔轮询而非依赖
    result backend；至少一次执行语义下，断言最终以数据库终态为准。
    """

    deadline = time.monotonic() + settings.CELERY_TEST_TASK_TIMEOUT
    last_value = None
    while time.monotonic() < deadline:
        close_old_connections()
        last_value = model.objects.get(id=instance_id)
        if predicate(last_value):
            return last_value
        time.sleep(0.05)
    status = getattr(last_value, "status", None)
    task_id = getattr(last_value, "task_id", None)
    raise AssertionError(f"等待 {model.__name__}#{instance_id} 超时: status={status}, task_id={task_id}")


# ── 真实 Task 完成信号观察器 ─────────────────────────────
# 仅观察本专项集成 Task 是否退出 Worker，用于等待 stale/Ignore 和相同 task ID
# 重复投递等场景；不作为业务结果来源，业务断言仍以数据库快照为准。

_postrun_condition = threading.Condition()
_postrun_counts: dict[str, int] = {}
_postrun_states: dict[str, list[str]] = {}


@signals.task_postrun.connect(weak=False)
def _record_integration_task_postrun(*, sender=None, task_id=None, state=None, **kwargs) -> None:
    """记录真实集成 Task 已退出 Worker；业务断言仍以数据库快照为准。"""

    task_name = getattr(sender, "name", "")
    if not task_id or not task_name.startswith("tests.ai_assistant."):
        return
    with _postrun_condition:
        _postrun_counts[task_id] = _postrun_counts.get(task_id, 0) + 1
        _postrun_states.setdefault(task_id, []).append(state or "")
        _postrun_condition.notify_all()


def reset_task_postrun(*, task_id: str) -> None:
    """在投递前清理同名测试 task ID 的历史计数。"""

    with _postrun_condition:
        _postrun_counts.pop(task_id, None)
        _postrun_states.pop(task_id, None)


def wait_for_task_postrun(*, task_id: str, expected_count: int = 1) -> list[str]:
    """等待指定真实投递退出 Worker，并返回每次执行的 Celery 终态。"""

    deadline = time.monotonic() + settings.CELERY_TEST_TASK_TIMEOUT
    with _postrun_condition:
        while _postrun_counts.get(task_id, 0) < expected_count:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                observed = _postrun_counts.get(task_id, 0)
                raise AssertionError(
                    f"等待 Celery task_postrun 超时: task_id={task_id}, " f"expected={expected_count}, observed={observed}"
                )
            _postrun_condition.wait(timeout=remaining)
        states = list(_postrun_states.pop(task_id, []))
        _postrun_counts.pop(task_id, None)
        return states
