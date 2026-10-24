"""Attachment 实时增量与持久状态核对。

Redis 只传递过程提示；周期读取当前可见对象，补齐丢失的终态或代际切换通知。
不补偿历史、不回灌 Redis，数据库连接在每次核对后归还。
"""

import time
from collections.abc import Iterator
from functools import partial
from uuid import UUID

from django import db
from django.conf import settings
from redis.exceptions import RedisError
from ui_stream.exceptions import InvalidCursor, LiveUnavailable
from ui_stream.reader import iter_live, normalize_cursor

from apps.permission.handlers.actions.action import ActionEnum
from core.exceptions import PermissionException
from services.web.ai_assistant.constants import ExecutionStatus
from services.web.ai_assistant.exceptions import (
    AttachmentNotFound,
    InvalidStreamCursor,
    StreamNotEnabled,
)
from services.web.ai_assistant.schemas import AttachmentStreamSnapshot, UIStreamEvent
from services.web.ai_assistant.services.attachment import AttachmentService
from services.web.ai_assistant.streaming import AttachmentArchiveStore, RedisLiveStore
from services.web.ai_assistant.streaming.codec import control_codec
from services.web.common.scope_permission import ScopeContext

TERMINAL_STATUSES = frozenset({ExecutionStatus.SUCCESS, ExecutionStatus.FAILED})


class AttachmentStreamService:
    """读取 Redis 增量，并按有界周期核对数据库状态、执行代际及访问权限。"""

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
            self._redis_store = RedisLiveStore(for_read=True)
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

        # 先完成请求校验，再交给长连接迭代器；不在建连后补发历史。
        attachment = self._attachment_service.get_for_stream(attachment_uid=str(attachment_uid))
        cursor = self.normalize_cursor(last_stream_id)
        if attachment.status in TERMINAL_STATUSES:
            return iter((control_codec.terminal(attachment.status),))

        config = self._archive_store.safe_parse_config(attachment)
        if config is None or config.task_id != attachment.task_id:
            return iter(())
        if execution_id is not None and config.execution_id != execution_id:
            # Redis 游标仅在单个 key 内有序；换流后禁止把旧游标用于新 key。
            return iter((control_codec.reset("execution_replaced"),))

        self._release_connection_before_live_stream()
        return self._iterate(
            redis_key=config.redis_key,
            cursor=cursor,
            attachment_uid=str(attachment_uid),
            task_id=config.task_id,
            execution_id=config.execution_id,
        )

    @staticmethod
    def _release_connection_before_live_stream() -> None:
        """归还健康连接，避免 CONN_MAX_AGE 使订阅期间仍占用数据库连接。"""

        connection = db.transaction.get_connection()
        if not connection.in_atomic_block:
            db.close_old_connections()
            connection.close()

    def _current_state_event(self, *, attachment_uid: str, task_id: str, execution_id: UUID, redis_key: str):
        """只回读可见状态与代际；任何结束提示均不携带新代际的过程数据。"""

        try:
            attachment = self._attachment_service.get_for_stream(attachment_uid=attachment_uid)
            conversation = attachment.source_message.conversation
            scope = ScopeContext(scope_type=conversation.scope_type, scope_id=conversation.scope_id)
            action = ActionEnum.VIEW_SCENE if scope.is_scene_scope else ActionEnum.VIEW_SYSTEM
            self._attachment_service.scope_permission.check_scope_entry(scope, action)
            config = self._archive_store.safe_parse_config(attachment)
            if (
                config is None
                or attachment.task_id != task_id
                or config.task_id != task_id
                or config.execution_id != execution_id
                or config.redis_key != redis_key
            ):
                return control_codec.reset("execution_replaced")
            if attachment.status in TERMINAL_STATUSES:
                return control_codec.terminal(attachment.status)
            return None
        finally:
            self._release_connection_before_live_stream()

    def _iterate(
        self, *, redis_key: str, cursor: str, attachment_uid: str, task_id: str, execution_id: UUID
    ) -> Iterator[UIStreamEvent | None]:
        """委托组件读取增量，保留审计可见性异常与数据库连接的生命周期。"""

        try:
            yield from iter_live(
                redis_store=self.redis_store,
                redis_key=redis_key,
                cursor=cursor,
                block_ms=self.BLOCK_MS,
                idle_timeout=settings.AI_ASSISTANT_STREAM_IDLE_TIMEOUT,
                clock=time.monotonic,
                live_errors=(RedisError, OSError, LiveUnavailable),
                state_check=partial(
                    self._current_state_event,
                    attachment_uid=attachment_uid,
                    task_id=task_id,
                    execution_id=execution_id,
                    redis_key=redis_key,
                ),
                state_poll_interval=settings.AI_ASSISTANT_STREAM_STATE_POLL_INTERVAL,
            )
        except (AttachmentNotFound, StreamNotEnabled, PermissionException):
            # 已建连后不能再改 HTTP 状态；权限/可见性变化时关闭，禁止发出排队旧数据。
            return
        finally:
            self._release_connection_before_live_stream()

    @staticmethod
    def normalize_cursor(last_stream_id: str | None) -> str:
        """校验客户端游标；缺省从流首开始读取。"""

        try:
            return normalize_cursor(last_stream_id)
        except InvalidCursor:
            raise InvalidStreamCursor() from None
