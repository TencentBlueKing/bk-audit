"""流式传输的不可变值对象与跨模块数据契约。

设计原则：
- 值对象冻结字段绑定；事件 data 等嵌套内容仍须按只读契约使用，不能就地修改。
- slots=True 减少内存开销，适合高频创建的短生命周期对象。
- 类型只承载数据与派生属性，不包含业务逻辑，逻辑由 Runtime/Archive 层负责。
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from ui_stream.types import Checkpoint as StreamCheckpointResult

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
    # 固化创建执行时的附件类型，终态汇总无需再查询数据库或依赖 Handler 注册表。
    business_type: str
    config: AttachmentStreamConfig

    @property
    def task_id(self) -> str:
        """任务归属由持久化流配置唯一提供，避免构造不一致绑定。"""

        return self.config.task_id

    @property
    def resource_id(self) -> str:
        """向组件提供业务无关的资源标识，不暴露数据库主键。"""

        return str(self.attachment_uid)

    @property
    def execution_id(self) -> UUID:
        """复用持久配置中的代际标识，与归档 fencing 保持同一来源。"""

        return self.config.execution_id

    @property
    def redis_key(self) -> str:
        """当前 execution 的逻辑 key，物理命名空间由 Redis 适配器补充。"""

        return self.config.redis_key


@dataclass(frozen=True, slots=True)
class StreamRotation:
    """一次执行切换结果；``previous_config`` 用于向旧流补发 reset。"""

    binding: StreamExecutionBinding
    previous_config: AttachmentStreamConfig | None


@dataclass(frozen=True, slots=True)
class StreamTimeoutResult:
    """巡检收敛流式附件的结果；实时通知只在当前 execution 可定位时返回。"""

    updated: bool
    redis_key: str | None = None
    terminal_event: UIStreamEvent | None = None


@dataclass(frozen=True, slots=True)
class AttachmentCompletion:
    """与流尾部共同提交的业务结果及审计字段，不承担事务或状态机逻辑。"""

    output_data: dict[str, Any] | None
    error_code: str
    error_message: str
    updated_by: str


__all__ = [
    "StreamExecutionBinding",
    "StreamRotation",
    "StreamCheckpointResult",
    "StreamTimeoutResult",
    "AttachmentCompletion",
]
