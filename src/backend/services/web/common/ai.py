"""跨业务 AI 任务的 Celery 执行约定。

集中维护共享队列和限流重试基类，避免风险、AI 助手等业务模块相互依赖。
"""

import logging
import random
import time
from typing import NoReturn

from celery import Task
from django.conf import settings
from django.db.models import TextChoices
from django.utils.translation import gettext_lazy

from api.bk_plugins_ai_agent.exceptions import AgentRateLimited

logger = logging.getLogger(__name__)

AGENT_RETRY_STARTED_AT_HEADER = "ai_agent_retry_started_at"


class AIWorkloadQueue(TextChoices):
    """按执行特征划分的跨业务 AI workload 队列。"""

    DEFAULT = "ai_default", gettext_lazy("默认 AI 任务")
    RISK_SINGLE = "risk_single_analyse", gettext_lazy("单风险分析")


class AIAgentTask(Task):
    """将 Agent 限流统一转换为有界的 Celery 延迟重试。"""

    abstract = True

    def __call__(self, *args, **kwargs):
        """执行任务，并在最外层收敛未被业务消费的限流异常。"""

        try:
            return super().__call__(*args, **kwargs)
        except AgentRateLimited as error:
            try:
                self.retry_agent_rate_limit(error)
            except AgentRateLimited:
                self.on_agent_rate_limit_exhausted(error=error, args=args, kwargs=kwargs)
                raise

    def on_agent_rate_limit_exhausted(self, *, error: AgentRateLimited, args: tuple, kwargs: dict) -> None:
        """总重试预算耗尽后的领域收尾扩展点，默认无需额外状态处理。"""

    def retry_agent_rate_limit(self, error: AgentRateLimited) -> NoReturn:
        """按指数退避、抖动、最大次数和总 deadline 调度下一次执行。"""

        retries = int(getattr(self.request, "retries", 0) or 0)
        max_retries = int(settings.AI_AGENT_TASK_MAX_RETRIES)
        if retries >= max_retries:
            logger.warning(
                "AI agent task rate limit retries exhausted",
                extra={"agent_code": error.agent_code.value, "retry_count": retries},
            )
            raise error

        base = float(settings.AI_AGENT_TASK_RETRY_BASE_SECONDS)
        maximum = float(settings.AI_AGENT_TASK_RETRY_MAX_SECONDS)
        jitter = float(settings.AI_AGENT_TASK_RETRY_JITTER_SECONDS)
        countdown = min(base * (2**retries), maximum) + random.uniform(0, jitter)

        now = time.time()
        headers = dict(getattr(self.request, "headers", None) or {})
        started_at = float(headers.get(AGENT_RETRY_STARTED_AT_HEADER) or now)
        deadline = started_at + float(settings.AI_AGENT_TASK_RETRY_DEADLINE_SECONDS)
        if now + countdown > deadline:
            logger.warning(
                "AI agent task rate limit deadline exhausted",
                extra={"agent_code": error.agent_code.value, "retry_count": retries},
            )
            raise error

        headers[AGENT_RETRY_STARTED_AT_HEADER] = started_at
        logger.warning(
            "AI agent task delayed by rate limit",
            extra={
                "agent_code": error.agent_code.value,
                "retry_count": retries + 1,
                "retry_countdown": countdown,
            },
        )
        raise self.retry(
            exc=error,
            countdown=countdown,
            max_retries=max_retries,
            headers=headers,
        )
