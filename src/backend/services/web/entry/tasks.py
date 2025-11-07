import ctypes
import os
import signal
import sys
from itertools import count
from threading import Timer

from celery.signals import task_postrun
from django.conf import settings

task_counter = count()


def _parse_trim_interval() -> int:
    try:
        return int(os.getenv("RISK_TRIM_MEMORY_INTERVAL", "120"))
    except (TypeError, ValueError):
        return 120


TRIM_MEMORY_ENABLED = os.getenv("RISK_ENABLE_TRIM_MEMORY", "1").lower() in {"1", "true", "yes", "on"}
TRIM_MEMORY_INTERVAL = _parse_trim_interval()


@task_postrun.connect
def task_postrun_handler(**other_kwargs):
    """任务后处理函数"""
    current_count = next(task_counter)
    if current_count >= settings.SELF_MANAGED_MAX_TASKS:
        print(f"Processed {current_count} tasks, sending SIGTERM to exit worker...")

        # 向当前进程发送 SIGTERM 信号，Celery会处理退出
        os.kill(os.getpid(), signal.SIGTERM)  # 发送 SIGTERM 信号给当前进程


def trim_memory():
    """定期释放内存"""
    if not TRIM_MEMORY_ENABLED or TRIM_MEMORY_INTERVAL <= 0:
        return
    libc = ctypes.CDLL("libc.so.6")
    libc.malloc_trim(0)
    t = Timer(TRIM_MEMORY_INTERVAL, trim_memory)
    t.daemon = True
    t.start()


if "gevent" in sys.argv and "worker" in sys.argv and TRIM_MEMORY_ENABLED:  # 根据命令行参数判断
    # 启动第一个定时器
    print(f"Starting memory trimming timer (interval={TRIM_MEMORY_INTERVAL}s)...")
    t = Timer(TRIM_MEMORY_INTERVAL, trim_memory)
    t.daemon = True
    t.start()
elif "gevent" in sys.argv and "worker" in sys.argv:
    print("Memory trimming disabled via RISK_ENABLE_TRIM_MEMORY.")
