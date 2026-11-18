"""Gunicorn/gevent 专项 Web 进程夹具。

夹具只负责动态端口、就绪探测、日志脱敏和进程组回收；测试场景、数据准备
与 Celery Worker 生命周期仍由具体测试类管理。
"""

import os
import signal
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from http.client import HTTPConnection

from django.conf import settings

from tests.test_ai_assistant.special.process_worker import (
    BACKEND_DIR,
    sanitize_special_worker_log_lines,
    write_special_worker_log,
)

TEST_DATABASE_ENV = "BKAPP_TEST_DATABASE_NAME"
SSE_TEST_USERNAME_ENV = "BKAPP_AI_ASSISTANT_SSE_TEST_USERNAME"


def _allocate_port() -> int:
    """向操作系统申请当前可用的本机端口。"""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _collect_stdout(process: subprocess.Popen[str], logs: list[str]) -> None:
    """持续消费子进程输出，避免 PIPE 写满阻塞 Gunicorn。"""

    if process.stdout is None:
        return
    logs.extend(iter(process.stdout.readline, ""))


def _wait_until_ready(process: subprocess.Popen[str], *, port: int, logs: list[str]) -> None:
    """等待 Gunicorn worker 完成 Django 加载，同时及时暴露启动失败。"""

    deadline = time.monotonic() + settings.CELERY_TEST_TASK_TIMEOUT
    while time.monotonic() < deadline:
        if process.poll() is not None:
            output = "".join(sanitize_special_worker_log_lines(logs))
            raise AssertionError(f"Gunicorn 提前退出: code={process.returncode}\n{output}")
        connection = HTTPConnection("127.0.0.1", port, timeout=0.5)
        try:
            connection.request("GET", "/__ai_assistant_sse_health__")
            if connection.getresponse().status == 204:
                return
        except OSError:
            pass
        finally:
            connection.close()
        time.sleep(0.05)
    output = "".join(sanitize_special_worker_log_lines(logs))
    raise AssertionError(f"等待 Gunicorn ready 超时\n{output}")


def _reap_process_group(process: subprocess.Popen[str]) -> None:
    """先优雅终止 Gunicorn 进程组，超时后强杀兜底。"""

    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=2)
        return
    except subprocess.TimeoutExpired:
        pass

    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    process.wait(timeout=settings.CELERY_TEST_TASK_TIMEOUT)


@contextmanager
def running_gunicorn_web(*, username: str) -> Iterator[str]:
    """启动连接当前测试库的单 Worker Gunicorn/gevent Web 服务。"""

    port = _allocate_port()
    env = os.environ.copy()
    env[TEST_DATABASE_ENV] = settings.DATABASES["default"]["NAME"]
    env[SSE_TEST_USERNAME_ENV] = username
    env["PYTHONUNBUFFERED"] = "1"
    env.setdefault("DJANGO_SETTINGS_MODULE", "settings")
    command = [
        sys.executable,
        "-m",
        "gunicorn",
        "tests.test_ai_assistant.special.sse_wsgi:application",
        "--workers=1",
        "--worker-class=gevent",
        f"--bind=127.0.0.1:{port}",
        "--access-logfile=-",
        "--error-logfile=-",
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
    log_pump = threading.Thread(target=_collect_stdout, args=(process, logs), daemon=True)
    log_pump.start()
    try:
        _wait_until_ready(process, port=port, logs=logs)
        yield f"http://127.0.0.1:{port}"
    finally:
        _reap_process_group(process)
        log_pump.join(timeout=1)
        write_special_worker_log(scene="gunicorn-sse", pid=process.pid, lines=logs)
