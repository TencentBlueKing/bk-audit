"""业务 Task 的流式出口：封装实时推送、归档缓冲与终态收敛。

核心设计
--------
业务只需调用 ``send(data)``，Runtime 内部自动完成：
1. 编码校验 → 非法 data 立即抛出，属于接入错误。
2. Redis 实时推送 → 连接故障或超限时降级，不阻塞业务。
3. 归档缓冲 → 达到批阈值（条数/字节）时自动 checkpoint 到 MySQL。
4. 终态收敛 → finish_success/finish_failure 原子落库归档 + 终态。

降级策略
--------
- Redis 故障：标记 DEGRADED，停止实时推送，归档继续。
- MySQL checkpoint 故障：标记 DEGRADED，保留缓冲等待后续自动 checkpoint 或终态收敛重试。
- 归档容量耗尽：标记 TRUNCATED，停止缓冲新事件，Redis 推送继续。
- Fencing 失效：抛出 StaleAttachmentTask，由业务 Task 的异常策略决定忽略或重试。

线程安全
--------
业务 Task 可能在线程池中并发 send()，Runtime 内部通过 RLock 串行化缓冲操作。
"""

import logging
import threading
import time
from typing import Any

from django.conf import settings
from django.db import DatabaseError
from redis.exceptions import RedisError

from services.web.ai_assistant.constants import (
    ExecutionStatus,
    PlatformStreamEvent,
    StreamArchiveStatus,
)
from services.web.ai_assistant.exceptions import (
    StaleAttachmentTask,
    StreamRuntimeClosed,
)
from services.web.ai_assistant.observability import (
    StreamMetricSnapshot,
    report_stream_execution,
    start_stream_span,
)
from services.web.ai_assistant.schemas import (
    AttachmentStreamConfig,
    UIStreamEvent,
    serialize_stream_event,
)
from services.web.ai_assistant.streaming.archive import (
    AttachmentArchiveStore,
    merge_archive_status,
)
from services.web.ai_assistant.streaming.redis import RedisLiveStore
from services.web.ai_assistant.streaming.types import StreamExecutionBinding

logger = logging.getLogger(__name__)


class UIStreamRuntime:
    """业务 Task 唯一的流式出口；封装实时推送、归档缓冲与终态收敛。

    Handler 只调用 ``send()``，成功、失败和 Retry 收敛由平台 Task/Service 调用
    ``finish_*`` 生命周期方法；两者都不感知 Redis 与归档细节。
    Redis 连接故障与 MySQL checkpoint 故障降级为 ``DEGRADED``/``TRUNCATED``；
    接入错误、实现错误、MySQL fencing 判定执行失效和终态事务失败向业务抛出。
    """

    # ── 批归档阈值 ──
    # 设计权衡：阈值过小 → 频繁锁行增加 MySQL 压力；阈值过大 → Redis 故障时丢失窗口增大。
    # 当前按 20 条或 256KB 触发，以控制缓冲窗口和单次归档体积。
    CHECKPOINT_EVENT_COUNT = 20
    CHECKPOINT_BYTES = 256 * 1024

    def __init__(
        self,
        *,
        binding: StreamExecutionBinding,
        redis_store: RedisLiveStore,
        archive_store: AttachmentArchiveStore,
        archive_status: StreamArchiveStatus,
    ):
        self._binding = binding
        self._redis_store = redis_store
        self._archive_store = archive_store
        self._archive_status = archive_status
        # 业务 Task 可能在自己的线程池里 send，进程内串行化保证缓冲顺序。
        self._lock = threading.RLock()
        self._pending: list[UIStreamEvent] = []
        self._pending_bytes = 0
        self._closed = False
        # 业务事件计数与字节量用于容量降级判断。
        self._business_event_count = 0
        self._business_event_bytes = 0
        self._redis_business_bytes = 0
        self._degraded = False
        self._truncated = False
        self._summary_reported = False
        self._archive_stopped = False
        self._redis_stopped = False
        # 只在实际落库成功后推进，数据库故障时下一条事件会继续尝试。
        self._last_activity_checkpoint_at = time.monotonic()

    @classmethod
    def start(
        cls,
        *,
        attachment_id: int,
        task_id: str,
        redis_store: RedisLiveStore | None = None,
        archive_store: AttachmentArchiveStore | None = None,
    ) -> "UIStreamRuntime":
        """轮换执行，并在存在旧执行时向旧 Redis Stream 补发 reset。"""

        archive_store = archive_store or AttachmentArchiveStore()
        rotation = archive_store.start_execution(attachment_id=attachment_id, task_id=task_id)
        redis_store = redis_store or RedisLiveStore()
        runtime = cls(
            binding=rotation.binding,
            redis_store=redis_store,
            archive_store=archive_store,
            archive_status=rotation.binding.config.archive_status,
        )
        runtime._reset_previous_stream(previous_config=rotation.previous_config)
        return runtime

    @property
    def binding(self) -> StreamExecutionBinding:
        """当前执行的运行绑定；平台内部与测试用于定位流 key。"""

        return self._binding

    @property
    def pending_count(self) -> int:
        """尚未归档的缓冲事件条数。"""

        with self._lock:
            return len(self._pending)

    @property
    def archive_status(self) -> StreamArchiveStatus:
        """当前执行的归档完整性；只会单向升级。"""

        with self._lock:
            return self._archive_status

    @property
    def closed(self) -> bool:
        """Runtime 是否已在终态或 Retry 后关闭。"""

        with self._lock:
            return self._closed

    def send(self, data: Any) -> UIStreamEvent | None:
        """发送一条协议无关业务 UI 数据；事件名称由平台独占。"""

        with self._lock:
            self._require_open()
            ui_event = UIStreamEvent(data=data)
            # 先编码：非法 data 属于接入错误，必须在任何降级判断前暴露。
            live_payload_size = len(serialize_stream_event(ui_event, include_stream_id=False))
            if not self._accept_business_event(payload_size=live_payload_size):
                return None
            self._business_event_count += 1
            self._business_event_bytes += live_payload_size
            ui_event = self._write_live(ui_event, payload_size=live_payload_size)
            # MySQL 保存的是带 stream_id（实时写入失败时为 null）的完整事件，
            # pending 内存边界必须使用同一编码口径，不能复用 Redis entry 大小。
            archive_payload_size = len(serialize_stream_event(ui_event))
            self._buffer(ui_event, payload_size=archive_payload_size)
            return ui_event

    def finish_retry(self) -> None:
        """Celery Retry 退出前强制刷盘并关闭，不写任何终态。"""

        with start_stream_span(
            attachment_uid=str(self._binding.attachment_uid),
            business_type=self._binding.business_type,
            execution_id=str(self._binding.config.execution_id),
            status="RETRY",
        ):
            with self._lock:
                if self._closed:
                    return
                try:
                    self._checkpoint()
                except DatabaseError:
                    # 数据库基础设施故障不改变已有 Celery Retry 语义。
                    self._degrade("AI 助手附件流式重试前归档失败", status=StreamArchiveStatus.DEGRADED)
                self._closed = True
                self._report_summary(status="RETRY", error_code="")

    def finish_success(self, *, output_data: dict[str, Any], updated_by: str) -> None:
        """在最终事务内写入剩余事件与成功终态，随后补发 stream_end 事件。"""

        self._finish(
            status=ExecutionStatus.SUCCESS,
            output_data=output_data,
            error_code="",
            error_message="",
            updated_by=updated_by,
        )

    def finish_failure(self, *, error_code: str, error_message: str, updated_by: str) -> bool:
        """写入失败终态；执行已失效时返回 False 而不抛出。"""

        try:
            self._finish(
                status=ExecutionStatus.FAILED,
                output_data=None,
                error_code=error_code,
                error_message=error_message,
                updated_by=updated_by,
            )
        except StaleAttachmentTask:
            # 另一个执行已经写入终态，失败路径只需如实返回未更新。
            return False
        return True

    def _finish(
        self,
        *,
        status: ExecutionStatus,
        output_data: dict[str, Any] | None,
        error_code: str,
        error_message: str,
        updated_by: str,
    ) -> None:
        """终态统一入口：先落库，成功后再关闭并最佳努力补发终止事件。

        关键顺序：MySQL finalize → 清缓冲 → 标记关闭 → Redis 补发。
        若 finalize 失败则保留缓冲和未关闭状态，由 Task 的异常策略决定是否重试；
        若 Redis 补发失败则仅降级（MySQL 终态已提交，不可回滚）。
        """

        with start_stream_span(
            attachment_uid=str(self._binding.attachment_uid),
            business_type=self._binding.business_type,
            execution_id=str(self._binding.config.execution_id),
            status=str(status),
        ):
            with self._lock:
                self._require_open()
                pending = list(self._pending)
                terminal_event = UIStreamEvent(event=PlatformStreamEvent.STREAM_END, data={"status": status})
                # 终态事务失败必须保留缓冲并保持未关闭，由 Task 的异常策略收敛。
                persisted_status = self._archive_store.finalize(
                    binding=self._binding,
                    events=pending,
                    terminal_event=terminal_event,
                    archive_status=self._archive_status,
                    status=status,
                    output_data=output_data,
                    error_code=error_code,
                    error_message=error_message,
                    updated_by=updated_by,
                )
                self._observe_archive_status(persisted_status)
                self._pending.clear()
                self._pending_bytes = 0
                self._closed = True
                self._publish_terminal(terminal_event)
                self._report_summary(status=str(status), error_code=error_code)

    def _reset_previous_stream(self, *, previous_config: AttachmentStreamConfig | None) -> None:
        """向旧 execution 的 Redis Stream 尝试补发 reset。"""

        if previous_config is None:
            return
        reset_data = {"reason": "execution_replaced"}
        try:
            self._redis_store.append(
                redis_key=previous_config.redis_key,
                event=UIStreamEvent(event=PlatformStreamEvent.STREAM_RESET, data=reset_data),
            )
        except Exception:
            # MySQL execution 已切换；reset 是提交后的通知，失败不能回滚新执行。
            self._degrade("AI 助手附件旧流重置事件发布失败", status=StreamArchiveStatus.DEGRADED)

    def _publish_terminal(self, terminal_event: UIStreamEvent) -> None:
        """MySQL 终态已提交后，向当前 Redis Stream 最佳努力补发同一事件。"""

        try:
            self._redis_store.append(redis_key=self._binding.config.redis_key, event=terminal_event)
        except Exception:
            # MySQL 终态已提交；Redis terminal 是提交后通知，失败不能回滚最终产物。
            self._degrade("AI 助手附件终止事件实时发布失败", status=StreamArchiveStatus.DEGRADED)

    def _accept_business_event(self, *, payload_size: int) -> bool:
        """按单事件与总条数上限判断是否接收；超限只截断不失败。"""

        if payload_size > settings.AI_ASSISTANT_STREAM_MAX_EVENT_BYTES:
            self._degrade(
                "AI 助手附件流式事件超过单条上限",
                status=StreamArchiveStatus.TRUNCATED,
                extra={"payload_size": payload_size},
            )
            return False
        if self._business_event_count >= settings.AI_ASSISTANT_STREAM_MAX_EVENTS:
            if not self._archive_stopped:
                self._archive_stopped = True
                self._degrade(
                    "AI 助手附件流式事件超过条数上限",
                    status=StreamArchiveStatus.TRUNCATED,
                )
        return True

    def _write_live(self, event: UIStreamEvent, *, payload_size: int) -> UIStreamEvent:
        """写实时流；连接故障或超限降级，其他异常向调用方传播。"""

        if self._redis_stopped:
            return event
        if self._redis_business_bytes + payload_size > settings.AI_ASSISTANT_STREAM_REDIS_MAX_BYTES:
            self._redis_stopped = True
            self._degrade("AI 助手附件流式实时字节超过上限", status=StreamArchiveStatus.DEGRADED)
            return event
        try:
            published = self._redis_store.append(redis_key=self._binding.config.redis_key, event=event)
        except (RedisError, OSError):
            self._degrade("AI 助手附件流式实时写入失败", status=StreamArchiveStatus.DEGRADED)
            return event
        self._redis_business_bytes += payload_size
        return published

    def _buffer(self, event: UIStreamEvent, *, payload_size: int) -> None:
        """事件进入归档缓冲，达到批阈值时仅对数据库故障降级。"""

        if self._archive_stopped:
            self._touch_activity_if_due()
            return
        # MySQL 持续故障时 checkpoint 无法清空 pending。进程内缓冲仍必须受与
        # 持久归档相同的字节上限约束，避免单任务把 Worker 内存无限吃满。
        if self._pending_bytes + payload_size > settings.AI_ASSISTANT_STREAM_ARCHIVE_MAX_BYTES:
            # 缓冲触顶可能只是数据库短暂故障。先用现有 pending 做最后一次恢复性
            # checkpoint；成功后继续接收当前事件，失败或持久归档已耗尽才截断。
            try:
                self._checkpoint()
            except DatabaseError:
                self._degrade(
                    "AI 助手附件流式缓冲触顶前归档失败",
                    status=StreamArchiveStatus.DEGRADED,
                )
        if self._archive_stopped or self._pending_bytes + payload_size > settings.AI_ASSISTANT_STREAM_ARCHIVE_MAX_BYTES:
            self._archive_stopped = True
            self._degrade(
                "AI 助手附件流式待归档缓冲超过上限",
                status=StreamArchiveStatus.TRUNCATED,
            )
            self._touch_activity_if_due()
            return
        self._pending.append(event)
        self._pending_bytes += payload_size
        if (
            len(self._pending) >= self.CHECKPOINT_EVENT_COUNT
            or self._pending_bytes >= self.CHECKPOINT_BYTES
            or self._activity_checkpoint_due()
        ):
            try:
                self._checkpoint()
            except DatabaseError:
                self._degrade("AI 助手附件流式自动归档失败", status=StreamArchiveStatus.DEGRADED)

    def _checkpoint(self) -> None:
        """归档当前缓冲；只有写入成功才清空，降低进程内事件丢失风险。

        当前归档不提供事件级去重，也不宣称 exactly-once；行锁和 fencing 只负责
        串行写入并隔离旧执行，不能把重复事件自动合并。
        """

        if not self._pending:
            return
        result = self._archive_store.checkpoint(
            binding=self._binding,
            events=self._pending,
            archive_status=self._archive_status,
        )
        self._pending.clear()
        self._pending_bytes = 0
        self._archive_status = merge_archive_status(self._archive_status, result.archive_status)
        self._last_activity_checkpoint_at = time.monotonic()
        self._observe_archive_status(result.archive_status)
        # 容量截断后 Redis 实时流仍继续，但不再缓冲业务事件，
        # 避免每批都锁行重新解析已接近上限的大 JSON。
        if result.capacity_exhausted:
            self._archive_stopped = True

    def _activity_checkpoint_due(self) -> bool:
        """低频事件按时间触发 checkpoint，避免真实长任务被巡检误判失活。"""

        return (
            time.monotonic() - self._last_activity_checkpoint_at
            >= settings.AI_ASSISTANT_STREAM_ACTIVITY_INTERVAL_SECONDS
        )

    def _touch_activity_if_due(self) -> None:
        """归档停止后仍按时间刷新 execution 活动；数据库故障沿用流降级语义。"""

        if not self._activity_checkpoint_due():
            return
        try:
            self._archive_store.touch_activity(binding=self._binding)
        except DatabaseError:
            self._degrade("AI 助手附件流式活动刷新失败", status=StreamArchiveStatus.DEGRADED)
            return
        self._last_activity_checkpoint_at = time.monotonic()

    def _degrade(
        self,
        message: str,
        *,
        status: StreamArchiveStatus,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """统一降级入口：提升归档状态并记录不含事件正文的告警。"""

        self._archive_status = merge_archive_status(self._archive_status, status)
        self._observe_archive_status(status)
        logger.warning(
            message,
            extra={
                "attachment_uid": str(self._binding.attachment_uid),
                "task_id": self._binding.task_id,
                "execution_id": str(self._binding.config.execution_id),
                "archive_status": str(self._archive_status),
                **(extra or {}),
            },
        )

    def _observe_archive_status(self, status: StreamArchiveStatus) -> None:
        """记录本次 execution 曾发生的降级类型，终态汇总不读取事件正文。"""

        if status == StreamArchiveStatus.DEGRADED:
            self._degraded = True
        elif status == StreamArchiveStatus.TRUNCATED:
            self._truncated = True

    def _report_summary(self, *, status: str, error_code: str) -> None:
        """一次 Runtime 只上报一条汇总，避免事件和 checkpoint 形成指标洪峰。"""

        if self._summary_reported:
            return
        self._summary_reported = True
        report_stream_execution(
            StreamMetricSnapshot(
                business_type=self._binding.business_type,
                status=status,
                error_code=error_code,
                degraded=self._degraded,
                truncated=self._truncated,
                event_count=self._business_event_count,
                event_bytes=self._business_event_bytes,
            )
        )

    def _require_open(self) -> None:
        """终态或 Retry 后继续使用 Runtime 属于业务接入错误。"""

        if self._closed:
            raise StreamRuntimeClosed()
