import json
import logging
import uuid
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from services.web.ai_assistant.constants import ExecutionStatus, StreamArchiveStatus
from services.web.ai_assistant.exceptions import StaleAttachmentTask
from services.web.ai_assistant.models import Attachment
from services.web.ai_assistant.schemas import (
    AttachmentStreamConfig,
    AttachmentStreamSnapshot,
    UIStreamEvent,
    parse_stream_archive,
    parse_stream_config,
)
from services.web.ai_assistant.streaming.redis import build_stream_key
from services.web.ai_assistant.streaming.types import (
    StreamCheckpointResult,
    StreamExecutionBinding,
    StreamRotation,
)

logger = logging.getLogger(__name__)

# 归档状态严重程度；同一次执行内只允许单向升级，避免前端提示反复抖动。
_ARCHIVE_STATUS_PRIORITY: dict[str, int] = {
    StreamArchiveStatus.COMPLETE: 0,
    StreamArchiveStatus.DEGRADED: 1,
    StreamArchiveStatus.TRUNCATED: 2,
}


def merge_archive_status(current: StreamArchiveStatus, incoming: StreamArchiveStatus) -> StreamArchiveStatus:
    """返回两个归档状态中更严重的一个（单向升级语义）。

    设计意图：归档状态在同一次执行内只允许从 COMPLETE → DEGRADED → TRUNCATED 单向升级，
    避免前端展示的降级提示反复抖动。调用方无需关心合并顺序，结果始终是更严重的那个。

    Args:
        current: 当前已持久化的归档状态。
        incoming: 本次操作产生的新状态。

    Returns:
        两者中严重程度更高的状态值。
    """

    if _ARCHIVE_STATUS_PRIORITY[current] >= _ARCHIVE_STATUS_PRIORITY[incoming]:
        return current
    return incoming


def _encoded_event_bytes(event: UIStreamEvent) -> int:
    """计算单个事件在归档 JSON 数组中占用的 UTF-8 紧凑编码字节数。

    不包含数组分隔符（逗号、方括号），仅计算事件自身序列化后的字节长度。
    用于 fit_archive_events 的增量字节累加，避免每次追加都重新编码整个数组。

    Args:
        event: 待计算的流式事件。

    Returns:
        该事件紧凑 JSON 编码后的 UTF-8 字节数。
    """

    return len(json.dumps(event.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _encoded_archive_bytes(events: list[UIStreamEvent]) -> int:
    """计算事件列表序列化为 JSON 数组后的 UTF-8 紧凑编码总字节数。

    计算公式：2（首尾方括号） + 各元素编码字节之和 + (元素数 - 1)（逗号分隔符）。
    这样无需真正执行 json.dumps(整个列表)，即可精确得到最终落库的字节数。

    Args:
        events: 已有的事件列表。

    Returns:
        该列表序列化为紧凑 JSON 数组后的 UTF-8 字节数（空列表返回 2，即 "[]"）。
    """

    if not events:
        # 空数组仍占用 "[]" 两个字节。
        return 2
    # 数组等于各元素编码之和，加上首尾方括号与元素间逗号，无需再整体编码一次。
    return 2 + sum(_encoded_event_bytes(event) for event in events) + (len(events) - 1)


def fit_archive_events(
    *, existing: list[UIStreamEvent], incoming: list[UIStreamEvent], max_bytes: int
) -> tuple[list[UIStreamEvent], int, bool]:
    """在容量限制内按顺序追加尽可能多的事件，返回合并结果。

    设计意图：
    - 字节数按增量累加（O(n) 对 incoming），而非每追加一条都重新编码整个数组。
      单执行可能累积上万条事件，全量编码会让持有行锁的 checkpoint 退化成 O(n²)。
    - 一旦某条事件放不下即停止，不跳跃保留后续事件，保证前端回放的时序连续性。

    Args:
        existing: 数据库中已有的归档事件列表。
        incoming: 本次待追加的新事件列表。
        max_bytes: 归档 JSON 数组的 UTF-8 字节上限。

    Returns:
        三元组 (merged, accepted_count, truncated):
        - merged: 合并后的完整事件列表（existing + 已接收的 incoming 前缀）。
        - accepted_count: 本次实际接收的 incoming 事件数量。
        - truncated: 是否因容量不足而截断（True 表示有事件被丢弃）。
    """

    if not incoming:
        return list(existing), 0, False

    accepted: list[UIStreamEvent] = list(existing)
    accepted_count = 0
    current_bytes = _encoded_archive_bytes(accepted)
    for event in incoming:
        # 追加一个元素会增加它自身的编码长度，以及非空数组所需的一个逗号。
        candidate_bytes = current_bytes + _encoded_event_bytes(event) + (1 if accepted else 0)
        if candidate_bytes > max_bytes:
            # 单条事件放不下即停止，保持事件顺序连续，不跳跃保留后续事件。
            return accepted, accepted_count, True
        accepted.append(event)
        accepted_count += 1
        current_bytes = candidate_bytes
    return accepted, accepted_count, False


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

        with transaction.atomic():
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
            attachment.updated_at = timezone.now()
            # Celery Worker 无请求态用户，必须跳过自动操作人覆写。
            attachment.save(update_record=False, update_fields=["stream_config", "stream_archive", "updated_at"])

        binding = StreamExecutionBinding(
            attachment_id=attachment.id,
            attachment_uid=attachment.uid,
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
        events: list[UIStreamEvent],
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

        with transaction.atomic():
            attachment = self._require_current_attachment(binding=binding, require_processing=True)
            persisted_status, update_fields, capacity_exhausted = self._apply_events(
                attachment=attachment,
                binding=binding,
                events=events,
                incoming_status=archive_status,
                enforce_capacity=True,
            )
            if update_fields:
                update_fields.append("updated_at")
                attachment.updated_at = timezone.now()
                attachment.save(update_record=False, update_fields=update_fields)
        return StreamCheckpointResult(
            archive_status=persisted_status,
            capacity_exhausted=capacity_exhausted,
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
    ) -> None:
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

        Raises:
            StaleAttachmentTask: 绑定已过期。
        """

        with transaction.atomic():
            attachment = self._require_current_attachment(binding=binding, require_processing=True)
            _, business_update_fields, _ = self._apply_events(
                attachment=attachment,
                binding=binding,
                events=events,
                incoming_status=archive_status,
                enforce_capacity=True,
            )
            # terminal 是终态快照的一部分，不受业务归档容量限制，且不携带 Redis 游标。
            _, terminal_update_fields, _ = self._apply_events(
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
                    }
                ),
            )
        logger.info(
            "AI 助手附件流式执行已结束",
            extra={
                "attachment_uid": str(binding.attachment_uid),
                "task_id": binding.task_id,
                "execution_id": str(binding.config.execution_id),
                "status": str(status),
                "event_count": len(events) + 1,
            },
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
           - True: 调用 fit_archive_events 按顺序追加可容纳前缀，超限标记 TRUNCATED。
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
        if events:
            max_bytes = self.max_archive_bytes if enforce_capacity else None
            if max_bytes is None:
                merged, accepted, truncated = existing + events, len(events), False
            else:
                merged, accepted, truncated = fit_archive_events(
                    existing=existing, incoming=events, max_bytes=max_bytes
                )
            if truncated:
                capacity_exhausted = enforce_capacity
                persisted_status = merge_archive_status(persisted_status, StreamArchiveStatus.TRUNCATED)
                logger.warning(
                    "AI 助手附件流式归档已截断",
                    extra={
                        "attachment_uid": str(binding.attachment_uid),
                        "task_id": binding.task_id,
                        "execution_id": str(binding.config.execution_id),
                        "accepted_count": accepted,
                        "dropped_count": len(events) - accepted,
                    },
                )
            attachment.stream_archive = [event.model_dump(mode="json") for event in merged]
            update_fields.append("stream_archive")
        elif parse_status != StreamArchiveStatus.COMPLETE:
            # 只清理脏数据也需要落库，避免同一批脏项在后续 checkpoint 重复解析。
            attachment.stream_archive = [event.model_dump(mode="json") for event in existing]
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
