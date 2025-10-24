import ctypes
import os
import signal
from itertools import count
from threading import Timer

from celery.signals import task_postrun
from django.conf import settings

task_counter = count()


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
    libc = ctypes.CDLL("libc.so.6")
    libc.malloc_trim(0)
    Timer(120, trim_memory).start()


# 启动第一个定时器
Timer(120, trim_memory).start()
