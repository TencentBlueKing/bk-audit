"""Attachment SSE 服务：一次鉴权定位后，仅通过 Redis 订阅实时事件。"""

import logging
import re
import time
from collections.abc import Iterator
from uuid import UUID

from django import db
from django.conf import settings
from redis.exceptions import RedisError

from services.web.ai_assistant.constants import ExecutionStatus, PlatformStreamEvent
from services.web.ai_assistant.exceptions import InvalidStreamCursor
from services.web.ai_assistant.schemas import AttachmentStreamSnapshot, UIStreamEvent
from services.web.ai_assistant.services.attachment import AttachmentService
from services.web.ai_assistant.streaming import AttachmentArchiveStore, RedisLiveStore

logger = logging.getLogger(__name__)

# Redis Stream 游标格式：毫秒时间戳 + 序号。
STREAM_CURSOR_PATTERN = re.compile(r"^\d+-\d+$")
# 流起始游标；表示从当前流的第一条事件开始读取。
STREAM_START_CURSOR = "0-0"
# 平台终止事件；读到后连接必须关闭，由前端决定是否重连或拉取快照。
CLOSING_EVENTS = frozenset({PlatformStreamEvent.STREAM_RESET, PlatformStreamEvent.STREAM_END})
TERMINAL_STATUSES = frozenset({ExecutionStatus.SUCCESS, ExecutionStatus.FAILED})


class AttachmentStreamService:
    """附件流式读取入口：一次鉴权定位后只订阅 Redis 增量。

    服务不承担 MySQL 补偿、Redis 回灌或业务协议解析；前端收到连接关闭后自行
    拉取详情和快照，再根据当前状态决定是否重连。
    """

    # 无新事件时的阻塞时长；到时返回心跳以探测连接存活。
    BLOCK_MS = 15_000

    def __init__(
        self,
        *,
        user: str,
        redis_store: RedisLiveStore | None = None,
        archive_store: AttachmentArchiveStore | None = None,
    ):
        self.user = user
        self._attachment_service = AttachmentService(user=user)
        self._redis_store = redis_store
        self._archive_store = archive_store or AttachmentArchiveStore()

    @property
    def redis_store(self) -> RedisLiveStore:
        """延迟建连：快照接口不需要 Redis，避免无谓的连接开销。"""

        if self._redis_store is None:
            self._redis_store = RedisLiveStore()
        return self._redis_store

    def get_snapshot(self, *, attachment_uid: str | UUID) -> AttachmentStreamSnapshot:
        """返回当前执行已持久化的事件快照，供首次进入或 reset 后恢复。"""

        attachment = self._attachment_service.get_for_stream(
            attachment_uid=str(attachment_uid),
            include_archive=True,
        )
        return self._archive_store.snapshot(attachment=attachment)

    def iter_events(
        self,
        *,
        attachment_uid: str | UUID,
        execution_id: UUID | None = None,
        last_stream_id: str | None = None,
    ) -> Iterator[UIStreamEvent | None]:
        """迭代实时增量事件；``None`` 表示心跳，迭代结束表示连接应关闭。"""

        # 建连时一次性读取用户可见附件、执行状态与流配置；进入 Redis 循环后不再查 MySQL。
        attachment = self._attachment_service.get_for_stream(attachment_uid=str(attachment_uid))
        cursor = self.normalize_cursor(last_stream_id)
        if attachment.status in TERMINAL_STATUSES:
            return iter((self._synthesize_terminal(attachment.status),))

        config = self._archive_store.safe_parse_config(attachment)
        if config is None or config.task_id != attachment.task_id:
            return iter(())
        if execution_id is not None and config.execution_id != execution_id:
            # Redis 游标仅在单个 key 内有序；换流后禁止把旧游标用于新 key。
            return iter((self._synthesize(PlatformStreamEvent.STREAM_RESET, data={"reason": "execution_replaced"}),))

        self._release_connection_before_live_stream()
        return self._iterate(redis_key=config.redis_key, cursor=cursor, attachment_id=attachment.id)

    @staticmethod
    def _release_connection_before_live_stream() -> None:
        """长时 Redis 订阅前归还 DB 连接；事务中保持当前连接不变。"""

        if not db.transaction.get_connection().in_atomic_block:
            db.close_old_connections()

    def _iterate(self, *, redis_key: str, cursor: str, attachment_id: int) -> Iterator[UIStreamEvent | None]:
        """SSE 主循环：固定 XREAD 阻塞时间，业务事件驱动滑动空闲窗口。"""

        last_business_event_at = time.monotonic()
        while True:
            try:
                read_result = self.redis_store.read(
                    redis_key=redis_key,
                    after_id=cursor,
                    block_ms=self.BLOCK_MS,
                )
            except (RedisError, OSError):
                # Redis 故障只终止本次 SSE；前端会重新读取详情和快照。
                logger.warning(
                    "AI 助手附件流实时读取失败",
                    extra={"attachment_id": attachment_id},
                )
                return
            # 每轮只取一次时钟，避免测试及超时边界因分支额外调用而漂移。
            now = time.monotonic()

            # XREAD 可能只读到被丢弃的脏 entry；即使无有效事件也要
            # 推进游标，否则下一轮会立即重读同一批数据。
            if read_result.last_seen_stream_id:
                cursor = read_result.last_seen_stream_id

            has_business_event = False
            for event in read_result.events:
                yield event
                if event.event in CLOSING_EVENTS:
                    # 终止事件已下发，后续 entry 属于旧流残留，不再推送。
                    return
                if event.event is None:
                    # UIStreamEvent.event 为空表示默认 SSE message，即业务事件；
                    # heartbeat 是迭代器返回的 Python None，不会进入此分支。
                    has_business_event = True
                    last_business_event_at = now

            # heartbeat、脏 entry 和平台事件都不刷新窗口；平台事件批次也必须超时。
            if not has_business_event and now - last_business_event_at >= settings.AI_ASSISTANT_STREAM_IDLE_TIMEOUT:
                return
            if not read_result.events:
                yield None

    @staticmethod
    def _synthesize(event: PlatformStreamEvent, *, data: dict | None = None) -> UIStreamEvent:
        """合成平台事件；无 Redis 游标，客户端不得用它续传。"""

        return UIStreamEvent(event=event, stream_id=None, data=data or {})

    @classmethod
    def _synthesize_terminal(cls, status: str) -> UIStreamEvent:
        """按数据库终态合成统一的 stream_end 事件。"""

        return cls._synthesize(PlatformStreamEvent.STREAM_END, data={"status": status})

    @staticmethod
    def normalize_cursor(last_stream_id: str | None) -> str:
        """校验客户端游标；缺省从流首开始读取。"""

        if not last_stream_id:
            return STREAM_START_CURSOR
        if not STREAM_CURSOR_PATTERN.fullmatch(last_stream_id):
            raise InvalidStreamCursor()
        return last_stream_id
