"""流式传输的不可变值对象与跨模块数据契约。

设计原则：
- 所有类型均为 frozen dataclass，构造后不可修改，避免运行期意外篡改绑定信息。
- slots=True 减少内存开销，适合高频创建的短生命周期对象。
- 类型只承载数据与派生属性，不包含业务逻辑，逻辑由 Runtime/Archive 层负责。
"""

from dataclasses import dataclass
from uuid import UUID

from services.web.ai_assistant.constants import StreamArchiveStatus
from services.web.ai_assistant.schemas import AttachmentStreamConfig, UIStreamEvent


@dataclass(frozen=True, slots=True)
class StreamExecutionBinding:
    """单次 Celery 实际执行的不可变运行绑定。

    Redis 使用独立 execution key 隔离 reader，MySQL 用 ``task_id + execution_id``
    做唯一 fencing。同一个 Celery ``task_id`` 因 Retry 或重复投递可以对应多个
    execution，因此运行期不允许修改绑定，只能重新 ``start_execution()``。
    """

    attachment_id: int
    attachment_uid: UUID
    config: AttachmentStreamConfig

    @property
    def task_id(self) -> str:
        """任务归属由持久化流配置唯一提供，避免构造不一致绑定。"""

        return self.config.task_id


@dataclass(frozen=True, slots=True)
class StreamRotation:
    """一次执行切换结果；``previous_config`` 用于向旧流补发 reset。"""

    binding: StreamExecutionBinding
    previous_config: AttachmentStreamConfig | None


@dataclass(frozen=True, slots=True)
class StreamReadResult:
    """一次 Redis XREAD 的结果，游标包含被跳过的脏 entry。"""

    events: list[UIStreamEvent]
    last_seen_stream_id: str | None


@dataclass(frozen=True, slots=True)
class StreamCheckpointResult:
    """一次 MySQL checkpoint 的结果，显式告知 Runtime 是否停止后续归档。"""

    archive_status: StreamArchiveStatus
    capacity_exhausted: bool = False
