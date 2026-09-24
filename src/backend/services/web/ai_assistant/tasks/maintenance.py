"""AI 助手平台周期维护任务。"""

import logging
from datetime import timedelta

from blueapps.contrib.celery_tools.periodic import periodic_task
from django.conf import settings
from django.core.cache import cache

from services.web.ai_assistant.observability import report_reconcile_failed_event
from services.web.ai_assistant.services.reconciliation import (
    reconcile_processing_executions,
)

logger = logging.getLogger(__name__)
_RECONCILE_LOCK_KEY = "ai_assistant_execution_reconcile"


def _try_acquire_reconcile_lock() -> bool:
    """Redis 正常时避免重复巡检，故障时 fail-open 交由 MySQL CAS 保证正确性。

    短锁只用于降重，获取后由 TTL 自动释放，避免检查锁值再删除产生竞争窗口。
    项目通用 ``@lock`` 会在函数结束时释放且锁异常时跳过执行，与这里用接近一个
    调度周期的固定 TTL 降重、基础设施异常仍继续巡检的语义不同，因此保留显式逻辑。
    """

    ttl = max(1, settings.AI_ASSISTANT_RECONCILE_INTERVAL_SECONDS - 5)
    try:
        return cache.set(_RECONCILE_LOCK_KEY, 1, timeout=ttl, nx=True)
    except Exception:  # NOCC:broad-except(Redis 锁只用于降重，不能阻断状态收敛)
        logger.exception("AI 助手巡检短锁获取失败，将无锁执行")
        return True


@periodic_task(
    run_every=timedelta(seconds=settings.AI_ASSISTANT_RECONCILE_INTERVAL_SECONDS),
    time_limit=settings.AI_ASSISTANT_RECONCILE_TIME_LIMIT_SECONDS,
)
def monitor_ai_assistant_executions():
    """每分钟巡检失活执行；短锁只降重，状态正确性由 MySQL CAS 保证。"""

    if not settings.AI_ASSISTANT_RECONCILE_ENABLED:
        return None
    try:
        if not _try_acquire_reconcile_lock():
            return None
        return reconcile_processing_executions().as_dict()
    except Exception as error:
        # 失败事件用于运维恢复巡检心跳；继续抛出让现有 Celery 监控感知任务失败。
        report_reconcile_failed_event(error=error)
        raise
