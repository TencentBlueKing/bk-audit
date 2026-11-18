"""将通用流运行时接入审计附件的执行生命周期。

AttachmentArchiveStore 负责执行轮换、fencing 和结果事务；组件负责缓冲与传输协调。
本层装配当前 Django 配置、公开事件与内部归档编码，保留业务异常及审计监控边界。
旧流 reset 在轮换提交后发布，终态通知在结果提交后发布，实时故障不回滚持久结果。
"""

from typing import Any

from django.conf import settings
from django.db import DatabaseError
from redis.exceptions import RedisError
from ui_stream import StreamPolicy, StreamRuntime
from ui_stream.exceptions import LiveUnavailable
from ui_stream.redis import BoundRedisPublisher
from ui_stream.types import Summary

from services.web.ai_assistant.constants import ExecutionStatus, StreamArchiveStatus
from services.web.ai_assistant.exceptions import (
    StaleAttachmentTask,
    StreamRuntimeClosed,
)
from services.web.ai_assistant.observability import (
    StreamMetricSnapshot,
    report_stream_execution,
    start_stream_span,
)
from services.web.ai_assistant.streaming.archive import AttachmentArchiveStore
from services.web.ai_assistant.streaming.codec import archive_codec
from services.web.ai_assistant.streaming.redis import RedisLiveStore
from services.web.ai_assistant.streaming.types import (
    AttachmentCompletion,
    StreamExecutionBinding,
)


class UIStreamRuntime(StreamRuntime):
    """为附件提供稳定的发送与收敛入口，复用组件的缓冲和故障语义。

    每个实例只绑定一次 execution；start 先完成持久轮换，再通知旧流并装配新发布器。
    业务结果通过 AttachmentCompletion 交给归档事务，关闭摘要只用于审计聚合监控。
    """

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
        """绑定当前执行的存储端口与编解码，不在构造中轮换或发布事件。

        binding 和 archive_status 必须来自已提交的执行轮换；替换通知在构造后通过组件发布。
        """

        super().__init__(
            binding=binding,
            publisher=BoundRedisPublisher(redis_store, binding.config.redis_key),
            archive_store=archive_store,
            archive_status=archive_status,
            policy=self._build_policy,
            codec=archive_codec,
            after_close=self._report_summary,
            archive_errors=(DatabaseError,),
            live_errors=(RedisError, OSError, LiveUnavailable),
            closed_error=StreamRuntimeClosed,
        )

    @property
    def archive_status(self) -> StreamArchiveStatus:
        """把组件的中立完整性状态映射回审计枚举，保持现有调用契约。"""

        return StreamArchiveStatus(super().archive_status)

    def _build_policy(self) -> StreamPolicy:
        """由当前进程 settings 和批量阈值生成策略，不捕获构造时的配置值。

        容量或活动间隔的进程内调整对后续发送生效；连接池配置由 Redis 适配器独立缓存。
        工厂只读取配置，不执行外部 I/O 或重入发送/关闭；每次 send 的快照由组件统一管理。
        """

        return StreamPolicy(
            max_event_bytes=settings.AI_ASSISTANT_STREAM_MAX_EVENT_BYTES,
            max_events=settings.AI_ASSISTANT_STREAM_MAX_EVENTS,
            max_live_bytes=settings.AI_ASSISTANT_STREAM_REDIS_MAX_BYTES,
            max_archive_bytes=settings.AI_ASSISTANT_STREAM_ARCHIVE_MAX_BYTES,
            activity_interval_seconds=settings.AI_ASSISTANT_STREAM_ACTIVITY_INTERVAL_SECONDS,
            checkpoint_event_count=self.CHECKPOINT_EVENT_COUNT,
            checkpoint_bytes=self.CHECKPOINT_BYTES,
        )

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
        binding = rotation.binding
        runtime = cls(
            binding=binding,
            redis_store=redis_store,
            archive_store=archive_store,
            archive_status=binding.config.archive_status,
        )
        if rotation.previous_config is not None:
            runtime.announce_replacement(BoundRedisPublisher(redis_store, rotation.previous_config.redis_key))
        return runtime

    def finish_success(self, *, output_data: dict[str, Any], updated_by: str) -> None:
        """原子保存剩余事件与成功结果，再尽力发布实时 stream_end 通知。"""

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
        """只封装审计结果字段；事务提交和终态发布顺序由组件与归档端口协作保证。"""

        completion = AttachmentCompletion(
            output_data=output_data,
            error_code=error_code,
            error_message=error_message,
            updated_by=updated_by,
        )
        self.finish(status=status, completion=completion, error_code=error_code)

    def _convergence_span(self, *, status: str):
        """以不可变执行标识关联收敛 Trace，不把事件正文或最终产物放入属性。"""

        return start_stream_span(
            attachment_uid=str(self.binding.attachment_uid),
            business_type=self.binding.business_type,
            execution_id=str(self.binding.execution_id),
            status=status,
        )

    def finish(self, *, status: str, completion: Any, error_code: str = "") -> None:
        """在审计 Trace 内提交结果；提交异常继续向平台任务传播以决定重试。"""

        with self._convergence_span(status=str(status)):
            super().finish(status=status, completion=completion, error_code=error_code)

    def close_for_retry(self) -> None:
        """重试前尽力归档并关闭当前实例，不写业务终态或发布结束事件。"""

        with self._convergence_span(status="RETRY"):
            super().close_for_retry()

    def _report_summary(self, summary: Summary) -> None:
        """将组件的只读关闭摘要映射为审计聚合指标，不重新查询业务结果。"""

        report_stream_execution(
            StreamMetricSnapshot(
                business_type=self.binding.business_type,
                status=summary.status,
                error_code=summary.error_code,
                degraded=summary.degraded,
                truncated=summary.truncated,
                event_count=summary.event_count,
                event_bytes=summary.event_bytes,
            )
        )
