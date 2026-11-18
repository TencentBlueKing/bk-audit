"""审计附件的执行轮换、持久快照与终态事务。

行锁与 task/execution 双重 fencing 隔离旧 Worker，archive_id 只用于同执行归档重试去重。
组件提供容量裁剪和完整性合并算法；本层负责真实字节计量及 MySQL 原子提交。
旧流重置和终态通知在相应数据库事务返回后发布，避免外层回滚留下错误的 UI 提示。
"""

import logging
import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from ui_stream.archive import append_archive_events
from ui_stream.archive import merge_archive_status as component_merge_archive_status

from services.web.ai_assistant.constants import (
    ExecutionMode,
    ExecutionObjectType,
    ExecutionStatus,
    StreamArchiveStatus,
)
from services.web.ai_assistant.exceptions import StaleAttachmentTask
from services.web.ai_assistant.models import Attachment
from services.web.ai_assistant.observability import (
    ExecutionMetricSnapshot,
    report_execution_finished,
)
from services.web.ai_assistant.schemas import (
    AttachmentStreamConfig,
    AttachmentStreamSnapshot,
    UIStreamEvent,
    parse_stream_archive,
    parse_stream_config,
)
from services.web.ai_assistant.schemas.stream import (
    dump_stream_archive_event,
    serialize_stream_archive_event,
)
from services.web.ai_assistant.streaming.codec import control_codec
from services.web.ai_assistant.streaming.redis import build_stream_key
from services.web.ai_assistant.streaming.types import (
    AttachmentCompletion,
    StreamCheckpointResult,
    StreamExecutionBinding,
    StreamRotation,
    StreamTimeoutResult,
)

logger = logging.getLogger(__name__)


def _encoded_event_bytes(event: UIStreamEvent) -> int:
    """按含内部 archive_id 的持久化格式计量，避免用公开 DTO 低估归档容量。"""

    return len(serialize_stream_archive_event(event))


def merge_archive_status(current: StreamArchiveStatus, incoming: StreamArchiveStatus) -> StreamArchiveStatus:
    """按组件的单向升级规则合并完整性，并保留审计枚举作为返回类型。"""

    return StreamArchiveStatus(component_merge_archive_status(current, incoming))


class AttachmentArchiveStore:
    """Attachment 流式事件的 MySQL 归档与终态事务管理器。

    职责：持久化 Runtime 同步缓冲的 UI 事件，并在执行结束时原子写入归档与终态。

    并发安全设计：
    - 所有写入操作通过 SELECT ... FOR UPDATE 按主键加行锁串行化。
    - 双重 fencing（task_id + execution_id）防止旧 Worker 的延迟写入覆盖新执行数据。

    生命周期：start_execution → checkpoint（0~N 次） → finalize。
    """

    @property
    def max_archive_bytes(self) -> int:
        """归档 JSON 字节上限（来自 settings）。

        超限时事件会被截断，但不影响最终产物（output_data）的完整性，
        仅影响前端流式回放的展示完整度。
        """

        return settings.AI_ASSISTANT_STREAM_ARCHIVE_MAX_BYTES

    def start_execution(self, *, attachment_id: int, task_id: str) -> StreamRotation:
        """启动新的流式执行：锁行校验、轮换 execution、清空旧归档。

        设计意图：
        - 每次执行生成唯一 execution_id，配合 task_id 构成双重 fencing 令牌。
        - 清空旧归档而非追加，因为新执行的事件序列与旧执行无关；旧 Redis 流
          保留到 TTL 自然过期，Runtime 会根据 previous_config 向其发送 reset。
        - 返回 previous_config 供调用方通知仍订阅旧流的客户端切换执行。

        Args:
            attachment_id: 附件主键 ID。
            task_id: 当前 Celery 任务 ID，用于 fencing 校验。

        Returns:
            StreamRotation，包含：
            - binding: 新执行的绑定信息（后续 checkpoint/finalize 必须携带）。
            - previous_config: 上一次执行的配置（可能为 None），供发送旧流 reset。

        Raises:
            StaleAttachmentTask: 附件不存在、task_id 不匹配、非 PROCESSING 状态或非流式附件。
        """

        # 返回后 Runtime 会发布实时数据，禁止外层事务随后回滚这次轮换。
        with transaction.atomic(durable=True):
            attachment = self._lock_attachment(attachment_id=attachment_id)
            if (
                attachment is None
                or attachment.task_id != task_id
                or attachment.status != ExecutionStatus.PROCESSING
                or not attachment.is_stream
            ):
                raise StaleAttachmentTask()

            previous_config = self.safe_parse_config(attachment)
            execution_id = uuid.uuid4()
            config = AttachmentStreamConfig(
                task_id=task_id,
                execution_id=execution_id,
                redis_key=build_stream_key(attachment_uid=attachment.uid, execution_id=execution_id),
                archive_status=StreamArchiveStatus.COMPLETE,
            )
            attachment.stream_config = config.model_dump(mode="json")
            # 新执行从空归档开始；旧事件只保留在旧 Redis 流中直到 TTL 过期。
            attachment.stream_archive = []
            now = timezone.now()
            attachment.last_activity_at = now
            attachment.updated_at = now
            # Celery Worker 无请求态用户，必须跳过自动操作人覆写。
            attachment.save(
                update_record=False,
                update_fields=["stream_config", "stream_archive", "last_activity_at", "updated_at"],
            )

        binding = StreamExecutionBinding(
            attachment_id=attachment.id,
            attachment_uid=attachment.uid,
            business_type=attachment.attachment_type,
            config=config,
        )
        logger.info(
            "AI 助手附件流式执行已启动",
            extra={
                "attachment_uid": str(attachment.uid),
                "task_id": task_id,
                "execution_id": str(execution_id),
                "previous_execution_id": (None if previous_config is None else str(previous_config.execution_id)),
            },
        )
        return StreamRotation(binding=binding, previous_config=previous_config)

    def is_current(self, *, binding: StreamExecutionBinding, require_processing: bool = True) -> bool:
        """轻量判断绑定是否仍是该附件的当前有效执行（不加行锁）。

        设计意图：供调用方在非关键路径快速检测自身是否已被新执行取代，
        避免无谓的后续业务处理和 checkpoint 尝试。因为不加锁，结果可能有瞬时不一致，
        但后续 checkpoint/finalize 会通过行锁做最终校验。

        Args:
            binding: 当前 Worker 持有的执行绑定。
            require_processing: 是否要求附件仍处于 PROCESSING 状态（默认 True）。

        Returns:
            True 表示绑定仍有效，False 表示已过期应停止工作。
        """

        attachment = (
            Attachment.objects.filter(id=binding.attachment_id).only("task_id", "status", "stream_config").first()
        )
        return self._matches_binding(attachment=attachment, binding=binding, require_processing=require_processing)

    def checkpoint(
        self,
        *,
        binding: StreamExecutionBinding,
        events: Sequence[UIStreamEvent],
        archive_status: StreamArchiveStatus,
    ) -> StreamCheckpointResult:
        """中间持久化：将缓冲的流式事件追加到 MySQL 归档。

        设计意图：
        - 定期将 Runtime 缓冲的事件批量落库，缩小进程异常时尚未归档的数据窗口。
        - 受容量限制（max_archive_bytes），超限后标记 TRUNCATED 并通知调用方停止归档。
        - 行锁 + fencing 校验保证并发安全，旧 Worker 的延迟 checkpoint 会被拒绝。

        Args:
            binding: 当前执行绑定（含 task_id + execution_id 双重 fencing）。
            events: 本次待追加的 Runtime 缓冲事件。
            archive_status: 调用方观察到的归档状态（如 Redis 读取异常时传 DEGRADED）。

        Returns:
            StreamCheckpointResult，包含：
            - archive_status: 合并后的最终归档状态。
            - capacity_exhausted: 是否已耗尽容量（True 时调用方应停止后续归档）。

        Raises:
            StaleAttachmentTask: 绑定已过期（task_id/execution_id 不匹配或非 PROCESSING）。
        """

        with transaction.atomic(durable=True):
            attachment = self._require_current_attachment(binding=binding, require_processing=True)
            persisted_status, update_fields, capacity_exhausted = self._apply_events(
                attachment=attachment,
                binding=binding,
                events=list(events),
                incoming_status=archive_status,
                enforce_capacity=True,
            )
            if update_fields or events:
                now = timezone.now()
                update_fields.extend(["last_activity_at", "updated_at"])
                attachment.last_activity_at = now
                attachment.updated_at = now
                attachment.save(update_record=False, update_fields=update_fields)
        return StreamCheckpointResult(
            archive_status=persisted_status,
            capacity_exhausted=capacity_exhausted,
        )

    def touch_activity(self, *, binding: StreamExecutionBinding) -> None:
        """为仍有实时输出但已停止归档的 execution 刷新活动时间。

        使用与 checkpoint 相同的 task_id + execution_id fencing。该方法只由
        Runtime 按固定时间间隔调用，不会为每条 UI 事件产生数据库写入。
        """

        with transaction.atomic():
            attachment = self._require_current_attachment(binding=binding, require_processing=True)
            now = timezone.now()
            attachment.last_activity_at = now
            attachment.updated_at = now
            attachment.save(update_record=False, update_fields=["last_activity_at", "updated_at"])

    def commit(
        self,
        *,
        binding: StreamExecutionBinding,
        events: Sequence[UIStreamEvent],
        terminal_event: UIStreamEvent,
        archive_status: StreamArchiveStatus,
        completion: AttachmentCompletion,
    ) -> StreamArchiveStatus:
        """将组件的终态载荷转交审计事务，返回已持久化的完整性状态。

        业务状态取自 terminal_event；completion 提供结果、错误及操作人。
        finalize 负责行锁、fencing 和真实外层提交，不能在此提前确认或异步保存。
        """

        return self.finalize(
            binding=binding,
            events=list(events),
            terminal_event=terminal_event,
            archive_status=archive_status,
            status=terminal_event.data["status"],
            output_data=completion.output_data,
            error_code=completion.error_code,
            error_message=completion.error_message,
            updated_by=completion.updated_by,
        )

    def finalize(
        self,
        *,
        binding: StreamExecutionBinding,
        events: list[UIStreamEvent],
        terminal_event: UIStreamEvent,
        archive_status: StreamArchiveStatus = StreamArchiveStatus.COMPLETE,
        status: ExecutionStatus,
        output_data: dict[str, Any] | None,
        error_code: str,
        error_message: str,
        updated_by: str,
    ) -> StreamArchiveStatus:
        """终态写入：在一次锁行事务内原子落库业务尾部事件、终止标记与执行结果。

        设计意图：
        - 业务尾部事件（events）受容量限制，可能被截断；但 terminal_event 不受限制，
          终态事务成功时确保终止标记与最终结果一并落库。
        - 归档字段与终态字段（status/output_data/error_*）在同一条 UPDATE 中落库，
          避免出现"有终态但缺尾部事件"的中间态，保证前端读取的一致性。

        Args:
            binding: 当前执行绑定（含双重 fencing 令牌）。
            events: 业务尾部事件列表（受容量限制，可能被截断）。
            terminal_event: 终止标记事件（不受业务容量限制）。
            archive_status: 调用方观察到的归档状态（默认 COMPLETE）。
            status: 执行终态（SUCCESS / FAILED 等）。
            output_data: 最终产物数据（如生成的报告内容）。
            error_code: 错误码（成功时为空字符串）。
            error_message: 错误描述（成功时为空字符串）。
            updated_by: 操作人标识。

        Returns:
            当前执行最终持久化的归档状态，供 Runtime 汇总降级和截断情况。

        Raises:
            StaleAttachmentTask: 绑定已过期。
        """

        # commit 返回即代表最终结果可见，不能在外层 savepoint 中提前发布终态。
        with transaction.atomic(durable=True):
            attachment = self._require_current_attachment(binding=binding, require_processing=True)
            _, business_update_fields, _ = self._apply_events(
                attachment=attachment,
                binding=binding,
                events=events,
                incoming_status=archive_status,
                enforce_capacity=True,
            )
            # terminal 是终态快照的一部分，不受业务归档容量限制，且不携带 Redis 游标。
            persisted_status, terminal_update_fields, _ = self._apply_events(
                attachment=attachment,
                binding=binding,
                events=[terminal_event],
                incoming_status=archive_status,
                enforce_capacity=False,
            )
            now = timezone.now()
            attachment.status = str(status)
            attachment.output_data = output_data
            attachment.error_code = error_code
            attachment.error_message = error_message
            attachment.content_updated_at = now
            attachment.updated_by = updated_by
            attachment.updated_at = now
            attachment.last_activity_at = now
            attachment.finished_at = now
            # 归档与终态必须同一条 UPDATE 落库，避免出现终态但缺尾部事件的中间态。
            attachment.save(
                update_record=False,
                update_fields=sorted(
                    set(business_update_fields + terminal_update_fields)
                    | {
                        "status",
                        "output_data",
                        "error_code",
                        "error_message",
                        "content_updated_at",
                        "updated_by",
                        "updated_at",
                        "last_activity_at",
                        "finished_at",
                    }
                ),
            )
            metric_snapshot = ExecutionMetricSnapshot(
                object_type=ExecutionObjectType.ATTACHMENT,
                business_type=attachment.attachment_type,
                execution_mode=ExecutionMode.ASYNC,
                is_stream=True,
                status=str(status),
                error_code=error_code,
                created_at=attachment.created_at,
                queued_at=attachment.queued_at,
                started_at=attachment.started_at,
                finished_at=now,
            )
            # 监控必须在终态事务提交后投递，避免回滚对象产生虚假成功指标。
            transaction.on_commit(lambda: report_execution_finished(metric_snapshot))
        logger.info(
            "AI 助手附件流式执行已结束",
            extra={
                "attachment_uid": str(binding.attachment_uid),
                "task_id": binding.task_id,
                "execution_id": str(binding.config.execution_id),
                "status": str(status),
                "final_batch_event_count": len(events) + 1,
            },
        )
        return persisted_status

    def timeout_processing(
        self,
        *,
        attachment_id: int,
        task_id: str,
        cutoff: datetime,
        error_code: str,
        error_message: str,
        now: datetime,
    ) -> StreamTimeoutResult:
        """巡检原子收敛失活流，并为已启动 execution 持久化终止事件。

        Worker 异常退出时进程内尾部事件可能尚未 checkpoint，因此当前归档只能标记
        DEGRADED。若任务尚未建立有效 stream_config，则没有可关闭的实时流，仍按普通
        Attachment 超时 CAS 收敛状态。
        """

        with transaction.atomic():
            attachment = self._lock_attachment(attachment_id=attachment_id)
            if (
                attachment is None
                or attachment.status != ExecutionStatus.PROCESSING
                or attachment.task_id != task_id
                or attachment.last_activity_at is None
                or attachment.last_activity_at > cutoff
            ):
                return StreamTimeoutResult(updated=False)

            config = self.safe_parse_config(attachment)
            terminal_event = None
            redis_key = None
            extra_updates: dict[str, Any] = {
                "content_updated_at": now,
                "updated_at": now,
            }
            if config is not None and config.task_id == task_id:
                binding = StreamExecutionBinding(
                    attachment_id=attachment.id,
                    attachment_uid=attachment.uid,
                    business_type=attachment.attachment_type,
                    config=config,
                )
                terminal_event = control_codec.terminal(ExecutionStatus.FAILED)
                self._apply_events(
                    attachment=attachment,
                    binding=binding,
                    events=[terminal_event],
                    incoming_status=StreamArchiveStatus.DEGRADED,
                    enforce_capacity=False,
                )
                extra_updates.update(
                    stream_archive=attachment.stream_archive,
                    stream_config=attachment.stream_config,
                )
                redis_key = config.redis_key

            updated = Attachment.timeout_processing(
                instance_id=attachment.id,
                task_id=task_id,
                cutoff=cutoff,
                error_code=error_code,
                error_message=error_message,
                now=now,
                extra_updates=extra_updates,
            )
        return StreamTimeoutResult(
            updated=updated,
            redis_key=redis_key if updated else None,
            terminal_event=terminal_event if updated else None,
        )

    def snapshot(self, *, attachment: Attachment) -> AttachmentStreamSnapshot:
        """构建当前附件的流式归档快照（供 API 读取端使用）。

        设计意图：
        - 合并 stream_config 中记录的状态与实际解析 stream_archive 时发现的状态，
          取更严重者作为最终展示状态。
        - 手动重试排队期间保留旧 config 仅为后续切流，此时不继承旧 config 的降级状态，
          而是重置为 COMPLETE（因为新任务尚未产生任何归档）。

        Args:
            attachment: 已加载的附件实例（需包含 stream_archive 和 stream_config 字段）。

        Returns:
            AttachmentStreamSnapshot，包含：
            - events: 已持久化的有效事件列表。
            - execution_id: 当前执行 ID（task_id 不匹配时为 None）。
            - latest_stream_id: 最后一个带 Redis 游标的事件 ID（供断线续传）。
            - archive_status: 合并后的最终归档状态。
        """

        events, parse_status = parse_stream_archive(attachment.stream_archive)
        config = self.safe_parse_config(attachment)
        # 手动重试排队期保留旧 config 仅为后续切流，其降级状态
        # 不属于已换 task_id 的新任务。
        config_status = (
            config.archive_status
            if config is not None and config.task_id == attachment.task_id
            else StreamArchiveStatus.COMPLETE
        )
        execution_id = config.execution_id if config is not None and config.task_id == attachment.task_id else None
        return AttachmentStreamSnapshot(
            events=events,
            execution_id=execution_id,
            latest_stream_id=self._latest_stream_id(events),
            archive_status=merge_archive_status(config_status, parse_status),
        )

    def _apply_events(
        self,
        *,
        attachment: Attachment,
        binding: StreamExecutionBinding,
        events: list[UIStreamEvent],
        incoming_status: StreamArchiveStatus,
        enforce_capacity: bool,
    ) -> tuple[StreamArchiveStatus, list[str], bool]:
        """核心归档合并逻辑：就地修改 attachment 字段，返回合并结果元信息。

        执行步骤：
        1. 解析现有归档 → 得到有效事件列表和解析状态（脏数据会标记 DEGRADED）。
        2. 三方状态合并 → base_status(config) ∪ parse_status ∪ incoming_status，取最严重。
        3. 事件追加 → 根据 enforce_capacity 决定是否受字节上限约束：
           - True: 按内部身份去重后追加可容纳前缀，超限标记 TRUNCATED。
           - False: 无限制直接拼接（用于 terminal_event，与终态事务一起提交）。
        4. 脏数据清理 → 即使无新事件，若解析发现脏数据也重写归档字段，避免后续重复解析。
        5. 状态持久化 → 仅在状态实际变化时更新 stream_config，减少不必要写入。

        设计意图：
        - 该方法只修改 attachment 的内存字段并收集 update_fields，不执行 save()。
          由调用方（checkpoint/finalize）统一决定何时落库，支持 finalize 中多次调用后
          合并为一条 UPDATE。
        - enforce_capacity=False 专为 terminal_event 设计，避免流结束标记因业务容量
          限制被截断；是否落库仍取决于整个终态事务是否提交成功。

        Args:
            attachment: 已加行锁的附件实例（会被就地修改）。
            binding: 当前执行绑定（用于日志上下文）。
            events: 待追加的事件列表（可为空）。
            incoming_status: 调用方传入的状态（如 Redis 异常时为 DEGRADED）。
            enforce_capacity: 是否启用字节容量限制。

        Returns:
            三元组 (persisted_status, update_fields, capacity_exhausted):
            - persisted_status: 合并后的最终归档状态。
            - update_fields: 本次需要落库的字段名列表（可能为空）。
            - capacity_exhausted: 是否因容量不足而截断（仅 enforce_capacity=True 时可能为 True）。
        """

        existing, parse_status = parse_stream_archive(attachment.stream_archive)
        config = self.safe_parse_config(attachment)
        base_status = StreamArchiveStatus.COMPLETE if config is None else config.archive_status
        persisted_status = merge_archive_status(merge_archive_status(base_status, parse_status), incoming_status)

        update_fields: list[str] = []
        capacity_exhausted = False
        merged = existing
        accepted = 0
        if events:
            if enforce_capacity:
                # COMMIT 确认丢失后的重试按身份去重，容量按真实落库格式计量。
                result = append_archive_events(
                    existing,
                    events,
                    max_bytes=self.max_archive_bytes,
                    identity=lambda event: event.archive_id,
                    event_size=_encoded_event_bytes,
                )
                merged, accepted = result.events, result.appended_count
                capacity_exhausted = result.truncated
                if capacity_exhausted:
                    persisted_status = merge_archive_status(persisted_status, StreamArchiveStatus.TRUNCATED)
                    logger.warning(
                        "AI 助手附件流式归档已截断",
                        extra={
                            "attachment_uid": str(binding.attachment_uid),
                            "task_id": binding.task_id,
                            "execution_id": str(binding.config.execution_id),
                            "accepted_count": accepted,
                            "duplicate_count": result.duplicate_count,
                            "dropped_count": result.dropped_count,
                        },
                    )
            else:
                # 仅终态事务/CAS 路径使用；当前代际至多提交一次，并豁免业务容量。
                merged, accepted = existing + events, len(events)
        if accepted or parse_status != StreamArchiveStatus.COMPLETE:
            attachment.stream_archive = [dump_stream_archive_event(event) for event in merged]
            update_fields.append("stream_archive")

        if config is not None and config.archive_status != persisted_status:
            attachment.stream_config = config.model_copy(update={"archive_status": persisted_status}).model_dump(
                mode="json"
            )
            update_fields.append("stream_config")
        return persisted_status, update_fields, capacity_exhausted

    def _require_current_attachment(self, *, binding: StreamExecutionBinding, require_processing: bool) -> Attachment:
        """锁行读取附件并校验绑定有效性，不匹配立即抛出异常。

        Args:
            binding: 当前执行绑定。
            require_processing: 是否要求附件仍处于 PROCESSING 状态。

        Returns:
            已加行锁的 Attachment 实例。

        Raises:
            StaleAttachmentTask: 附件不存在或绑定已过期。
        """

        attachment = self._lock_attachment(attachment_id=binding.attachment_id)
        if not self._matches_binding(attachment=attachment, binding=binding, require_processing=require_processing):
            raise StaleAttachmentTask()
        return attachment

    @staticmethod
    def _lock_attachment(*, attachment_id: int) -> Attachment | None:
        """按主键加行锁读取附件（SELECT ... FOR UPDATE）。

        设计意图：仅按主键命中单行，避免扫描其他用户或会话数据，
        锁粒度最小化以减少并发阻塞。

        Args:
            attachment_id: 附件主键 ID。

        Returns:
            加锁后的 Attachment 实例，不存在时返回 None。
        """

        return Attachment.objects.select_for_update().filter(id=attachment_id).first()

    def _matches_binding(
        self,
        *,
        attachment: Attachment | None,
        binding: StreamExecutionBinding,
        require_processing: bool,
    ) -> bool:
        """双重 fencing 校验：task_id + execution_id 必须同时匹配。

        设计意图：
        - task_id 防止旧 Celery 任务的延迟回调写入新任务的数据。
        - execution_id 防止同一 task 内的旧 execution（如重试前的）覆盖新 execution。
        - 两者结合构成完整的 fencing token，任一不匹配即视为过期。

        Args:
            attachment: 待校验的附件实例（可能为 None）。
            binding: 当前 Worker 持有的执行绑定。
            require_processing: 是否要求附件仍处于 PROCESSING 状态。

        Returns:
            True 表示绑定有效，False 表示已过期。
        """

        if attachment is None or attachment.task_id != binding.task_id:
            return False
        if require_processing and attachment.status != ExecutionStatus.PROCESSING:
            return False
        config = self.safe_parse_config(attachment)
        return (
            config is not None
            and config.task_id == binding.task_id
            and config.execution_id == binding.config.execution_id
        )

    @staticmethod
    def safe_parse_config(attachment: Attachment) -> AttachmentStreamConfig | None:
        """安全解析附件的流式配置，异常时降级为 None 而非抛出。

        设计意图：
        - stream_config 字段可能因手动修改等原因损坏，此方法只把解析失败降级为
          无配置；是否允许后续操作由调用方的 fencing 语义决定。
        - 告警日志只使用主键与 task_id：因为 is_current() 会用 only() 裁剪字段，
          在异常路径上访问 uid 等延迟字段会额外触发一次数据库查询。

        Args:
            attachment: 附件实例。

        Returns:
            解析成功返回 AttachmentStreamConfig，失败返回 None。
        """

        try:
            return parse_stream_config(attachment.stream_config)
        except Exception:
            logger.warning(
                "AI 助手附件流式配置解析失败",
                extra={"attachment_id": attachment.pk, "task_id": attachment.task_id},
            )
            return None

    @staticmethod
    def _latest_stream_id(events: list[UIStreamEvent]) -> str | None:
        """从事件列表尾部向前查找最后一个带 Redis Stream ID 的事件。

        设计意图：并非所有事件都有 stream_id（如实时写入 Redis 失败的事件），
        需要从尾部逆序查找第一个有效游标，供前端断线续传时作为 XREAD 的起始 ID。

        Args:
            events: 已持久化的事件列表。

        Returns:
            最后一个有效的 Redis Stream ID，全部无游标时返回 None。
        """

        for event in reversed(events):
            if event.stream_id:
                return event.stream_id
        return None
