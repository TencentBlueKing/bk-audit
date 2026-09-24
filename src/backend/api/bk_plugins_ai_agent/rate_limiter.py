import logging
import math
import time
from uuid import uuid4

from client_throttler import Throttler, ThrottlerConfig
from client_throttler.exceptions import RetryTimeout, TooManyRequests, TooManyRetries
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from api.bk_plugins_ai_agent.exceptions import AgentRateLimited
from api.constants import AIAgentCode

logger = logging.getLogger(__name__)


class AgentRateLimiter:
    """使用 Redis 对各 ``AIAgentCode`` 实施跨进程全局限流。"""

    key_prefix = "bk_audit:ai_agent"

    @staticmethod
    def _get_config(agent_code: AIAgentCode) -> dict:
        """读取单个 Agent 的配置；缺失或空 rate 表示禁用。"""

        configs = getattr(settings, "AI_AGENT_RATE_LIMITS", {})
        return configs.get(agent_code.value, {})

    def acquire(self, agent_code: AIAgentCode) -> float:
        """在 HTTP 请求前取得配额，返回本次有界等待耗时（秒）。

        Raises:
            AgentRateLimited: 等待超过该 Agent 配置的预算或明确拒绝请求。
        """

        agent_code = AIAgentCode(agent_code)
        config = self._get_config(agent_code)
        rate = str(config.get("rate") or "").strip()
        if not rate:
            logger.info(
                "AI agent rate limit disabled",
                extra={"agent_code": agent_code.value, "allowed": True, "throttled": False, "wait_ms": 0},
            )
            return 0.0

        try:
            max_wait_seconds = float(config.get("max_wait_seconds", 0))
        except (TypeError, ValueError) as error:
            raise ImproperlyConfigured(
                f"AI agent {agent_code.value} rate limit max_wait_seconds must be a number greater than 0"
            ) from error
        if not math.isfinite(max_wait_seconds) or max_wait_seconds <= 0:
            raise ImproperlyConfigured(
                f"AI agent {agent_code.value} rate limit max_wait_seconds must be greater than 0"
            )

        started_at = time.monotonic()
        throttler = Throttler(
            ThrottlerConfig(
                rate=rate,
                key_prefix=self.key_prefix,
                key=agent_code.value,
                enable_sleep_wait=True,
                max_retry_duration=max_wait_seconds,
                redis_client=settings.AI_AGENT_RATE_LIMIT_REDIS_CLIENT,
            )
        )
        try:
            throttler.wait(uuid4().hex)
        except (TooManyRequests, TooManyRetries, RetryTimeout) as error:
            wait_ms = int((time.monotonic() - started_at) * 1000)
            logger.warning(
                "AI agent rate limited",
                extra={
                    "agent_code": agent_code.value,
                    "allowed": False,
                    "throttled": True,
                    "wait_ms": wait_ms,
                    "limit_error": error.__class__.__name__,
                },
            )
            raise AgentRateLimited(agent_code=agent_code) from error

        waited = time.monotonic() - started_at
        logger.info(
            "AI agent rate limit allowed",
            extra={
                "agent_code": agent_code.value,
                "allowed": True,
                "throttled": waited >= 0.001,
                "wait_ms": int(waited * 1000),
            },
        )
        return waited


agent_rate_limiter = AgentRateLimiter()
