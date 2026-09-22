"""独立 Celery Worker 子进程：用于 SIGKILL 后验证 RabbitMQ 重投。"""

import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path

from amqp.exceptions import ChannelError
from blueapps.core.celery import celery_app
from celery import signals
from django.conf import settings
from django.db import connections
from django_redis import get_redis_connection

from tests.test_ai_assistant.celery_integration import _reset_broker_pools

BACKEND_DIR = Path(__file__).resolve().parents[3]
SPECIAL_HANDLERS_ENV = "BKAPP_AI_ASSISTANT_SPECIAL_HANDLERS"
SPECIAL_QUEUE_ENV = "BKAPP_AI_ASSISTANT_SPECIAL_QUEUE"
SPECIAL_LOG_DIR_ENV = "BKAPP_AI_ASSISTANT_SPECIAL_LOG_DIR"
TEST_DATABASE_ENV = "BKAPP_TEST_DATABASE_NAME"
SPECIAL_TASK_POSTRUN_ENV = "BKAPP_AI_ASSISTANT_SPECIAL_TASK_POSTRUN"
LOG_ANALYSIS_TASK_NAME = "ai_assistant.execute_log_analysis"


def _bind_test_database() -> None:
    """让独立 Worker 使用 pytest 已创建的 MySQL 测试库。"""

    database_name = os.environ.get(TEST_DATABASE_ENV)
    if not database_name:
        return
    settings.DATABASES["default"]["NAME"] = database_name
    connections.close_all()


_bind_test_database()


def process_task_postrun_key(task_id: str) -> str:
    return f"{settings.CELERY_TEST_QUEUE_PREFIX}:process-task-postrun:{task_id}"


def process_task_postrun_observer_key(task_id: str) -> str:
    return f"{settings.CELERY_TEST_QUEUE_PREFIX}:process-task-postrun-observer:{task_id}"


def observe_process_task_postrun(task_id: str) -> None:
    """显式登记需要跨进程观察的 task，避免普通任务产生测试 Redis key。"""

    get_redis_connection("redis").set(
        process_task_postrun_observer_key(task_id),
        "1",
        ex=int(settings.CELERY_TEST_TASK_TIMEOUT * 2),
    )


def clear_process_task_postrun(task_id: str) -> None:
    get_redis_connection("redis").delete(
        process_task_postrun_key(task_id),
        process_task_postrun_observer_key(task_id),
    )


def wait_for_process_task_postrun(*, task_id: str, expected_count: int) -> list[str]:
    """等待独立 Worker 中同一 task ID 的执行全部退出。"""

    client = get_redis_connection("redis")
    key = process_task_postrun_key(task_id)
    deadline = time.monotonic() + settings.CELERY_TEST_TASK_TIMEOUT
    while time.monotonic() < deadline:
        states = client.lrange(key, 0, -1)
        if len(states) >= expected_count:
            return [value.decode() if isinstance(value, bytes) else str(value) for value in states]
        time.sleep(0.05)
    raise AssertionError(
        f"等待独立 Worker task_postrun 超时: task_id={task_id}, " f"expected={expected_count}, observed={client.llen(key)}"
    )


@signals.task_postrun.connect(weak=False)
def record_process_task_postrun(*, sender=None, task_id=None, state=None, **kwargs) -> None:
    """将生产日志分析 Task 的进程内退出信号写入测试 Redis。"""

    if not os.environ.get(SPECIAL_TASK_POSTRUN_ENV):
        return
    if not task_id or getattr(sender, "name", "") != LOG_ANALYSIS_TASK_NAME:
        return
    client = get_redis_connection("redis")
    if not client.get(process_task_postrun_observer_key(task_id)):
        return
    key = process_task_postrun_key(task_id)
    client.rpush(key, state or "")
    client.expire(key, int(settings.CELERY_TEST_TASK_TIMEOUT * 2))


def sanitize_special_worker_log_lines(lines: list[str]) -> list[str]:
    """丢掉疑似业务事件正文，避免断言和 artifact 泄漏 payload。"""

    return [
        line for line in lines if '"data":' not in line and " data=" not in line and "event data" not in line.lower()
    ]


def write_special_worker_log(*, scene: str, pid: int, lines: list[str]) -> None:
    """把 Worker 进程日志落到夹具目录；文件名含场景和 PID。"""

    log_dir = os.environ.get(SPECIAL_LOG_DIR_ENV)
    if not log_dir:
        return
    target_dir = Path(log_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / f"{scene}-{pid}.log").write_text("".join(sanitize_special_worker_log_lines(lines)), encoding="utf-8")


def delete_worker_queue(queue_name: str) -> None:
    """删除专项队列；队列不存在时忽略。"""

    with celery_app.connection_for_write(url=settings.CELERY_TEST_BROKER_URL) as connection:
        with connection.channel() as channel:
            try:
                channel.queue_delete(queue=queue_name)
            except ChannelError as error:
                if error.reply_code != 404:
                    raise


@contextmanager
def using_test_broker(*, queue_name: str) -> Iterator[None]:
    """把当前进程的 Celery App 切到 RabbitMQ，以便向专项队列真实投递。"""

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
            delete_worker_queue(queue_name)
        except ChannelError as error:
            if error.reply_code != 404:
                raise
        yield
    finally:
        try:
            delete_worker_queue(queue_name)
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


def kill_worker_process(process: subprocess.Popen[str]) -> None:
    """向 Worker 进程组发送 SIGKILL，模拟进程突然丢失。"""

    if process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGKILL)
    process.wait(timeout=settings.CELERY_TEST_TASK_TIMEOUT)


def _reap_worker_process(process: subprocess.Popen[str]) -> None:
    """退出路径：有界 wait，再 terminate，最后 SIGKILL。"""

    if process.poll() is not None:
        return
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=settings.CELERY_TEST_TASK_TIMEOUT)


def _pump_stdout(process: subprocess.Popen[str], logs: list[str], ready: threading.Event) -> None:
    if process.stdout is None:
        return
    for line in process.stdout:
        logs.append(line)
        if "ready." in line:
            ready.set()


def _queue_has_consumer(queue_name: str) -> bool:
    with celery_app.connection_for_write(url=settings.CELERY_TEST_BROKER_URL) as connection:
        with connection.channel() as channel:
            try:
                _, _, consumers = channel.queue_declare(queue=queue_name, passive=True)
            except ChannelError as error:
                if error.reply_code == 404:
                    return False
                raise
            return consumers > 0


def _wait_until_ready(process: subprocess.Popen[str], *, queue_name: str, logs: list[str]) -> None:
    ready = threading.Event()
    pump = threading.Thread(target=_pump_stdout, args=(process, logs, ready), daemon=True)
    pump.start()
    deadline = time.monotonic() + settings.CELERY_TEST_TASK_TIMEOUT
    while time.monotonic() < deadline:
        if ready.is_set() or _queue_has_consumer(queue_name):
            return
        if process.poll() is not None:
            raise AssertionError(
                f"Worker 提前退出: code={process.returncode}\n{''.join(sanitize_special_worker_log_lines(logs))}"
            )
        time.sleep(0.05)
    raise AssertionError(f"等待 Worker ready 超时\n{''.join(sanitize_special_worker_log_lines(logs))}")


@contextmanager
def running_worker_process(
    *,
    queue_name: str,
    include_modules: tuple[str, ...] = ("tests.test_ai_assistant.special_handlers",),
    extra_env: Mapping[str, str] | None = None,
    enable_special_handlers: bool = True,
    pool: str = "solo",
    concurrency: int = 1,
    log_scene: str = "worker-redelivery",
    observe_task_postrun: bool = False,
) -> Iterator[subprocess.Popen[str]]:
    """启动可选择生产或专项 Task 的独立 Worker，并在退出时回收进程组。"""

    env = os.environ.copy()
    env["BKAPP_CELERY_BROKER_URL"] = settings.CELERY_TEST_BROKER_URL
    env[TEST_DATABASE_ENV] = settings.DATABASES["default"]["NAME"]
    if enable_special_handlers:
        env[SPECIAL_HANDLERS_ENV] = "1"
    else:
        env.pop(SPECIAL_HANDLERS_ENV, None)
    env[SPECIAL_QUEUE_ENV] = queue_name
    env["PYTHONUNBUFFERED"] = "1"
    if observe_task_postrun:
        env[SPECIAL_TASK_POSTRUN_ENV] = "1"
    else:
        env.pop(SPECIAL_TASK_POSTRUN_ENV, None)
    env.setdefault("DJANGO_SETTINGS_MODULE", "settings")
    if extra_env:
        env.update(extra_env)
    worker_includes = ("tests.test_ai_assistant.special.process_worker", *include_modules)
    command = [
        sys.executable,
        "-m",
        "celery",
        "-A",
        "blueapps.core.celery:celery_app",
        "-b",
        settings.CELERY_TEST_BROKER_URL,
        "worker",
        f"--pool={pool}",
        f"--concurrency={concurrency}",
        "--without-gossip",
        "--without-mingle",
        "--without-heartbeat",
        "--loglevel=INFO",
        f"--queues={queue_name}",
        f"--include={','.join(worker_includes)}",
    ]
    process = subprocess.Popen(
        command,
        cwd=str(BACKEND_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    logs: list[str] = []
    try:
        _wait_until_ready(process, queue_name=queue_name, logs=logs)
        yield process
    except Exception:
        if logs:
            raise AssertionError(
                f"{sys.exc_info()[1]}\n{''.join(sanitize_special_worker_log_lines(logs))}"
            ) from sys.exc_info()[1]
        raise
    finally:
        write_special_worker_log(scene=log_scene, pid=process.pid, lines=logs)
        _reap_worker_process(process)
