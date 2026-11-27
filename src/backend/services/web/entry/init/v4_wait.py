"""为同一次 BKBase V4 初始化提供共享的有界等待。"""

from collections.abc import Callable, Mapping
from time import monotonic, sleep

from bk_resource.exceptions import APIRequestError
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from api.bk_base_v4.default import (
    INIT_DEADLINE,
    InitDeadlineBeforeSend,
    is_init_deadline_before_send,
)

POLL_INTERVAL_SECONDS = 5


class BKBaseV4InitTimeout(Exception):
    """本轮观察超时，不代表远端已进入失败态。"""


class V4InitWait:
    def __init__(self, seconds: int):
        self.started = monotonic()
        self.deadline = self.started + seconds

    @classmethod
    def from_settings(cls) -> "V4InitWait":
        value = str(settings.BKBASE_V4_INIT_TIMEOUT_SECONDS).strip()
        if not value.isascii() or not value.isdecimal() or int(value) <= 0:
            raise ImproperlyConfigured("BKAPP_BKBASE_V4_INIT_TIMEOUT_SECONDS must be a positive integer")
        return cls(int(value))

    def until_ready(self, stage: str, check: Callable[[], Mapping[str, str]]) -> None:
        """只重跑一步推进函数，绝不吞掉明确业务错误。"""
        pending = {}
        token = INIT_DEADLINE.set(self.deadline)
        try:
            while self.deadline > monotonic():
                try:
                    pending = check()
                except (APIRequestError, InitDeadlineBeforeSend) as error:
                    if not is_init_deadline_before_send(error):
                        raise
                    break
                remaining = self.deadline - monotonic()
                if remaining <= 0:
                    break
                if not pending:
                    return
                print(f"[InitBKBaseV4] {stage} pending: {self._describe(pending)}")
                sleep(min(POLL_INTERVAL_SECONDS, remaining))
        finally:
            INIT_DEADLINE.reset(token)
        raise BKBaseV4InitTimeout(
            f"[InitBKBaseV4] {stage} timed out after {monotonic() - self.started:.0f}s: "
            f"{self._describe(pending)}; rerun with the same configuration"
        )

    @staticmethod
    def _describe(pending: Mapping[str, str]) -> str:
        return ", ".join(f"{key}={reason}" for key, reason in pending.items()) or "not confirmed ready in time"
