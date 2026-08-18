from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, TypeVar

from django.core.exceptions import ImproperlyConfigured

from services.web.ai_assistant.constants import AttachmentType, ExecutionMode
from services.web.ai_assistant.exceptions import AttachmentNotEditable
from services.web.ai_assistant.models import Attachment, Message
from services.web.ai_assistant.schemas import MessageSchema

if TYPE_CHECKING:
    from services.web.ai_assistant.tasks import AttachmentExecutionTask

InputT = TypeVar("InputT", bound=MessageSchema)
ContextT = TypeVar("ContextT", bound=MessageSchema)
OutputT = TypeVar("OutputT", bound=MessageSchema)


@dataclass(frozen=True, slots=True)
class AttachmentPreparation(Generic[ContextT]):
    """首次创建 Attachment 时由业务 Handler 生成的标题和上下文。"""

    title: str
    context_data: ContextT


@dataclass(frozen=True, slots=True)
class AttachmentExecutionContext(Generic[InputT, ContextT]):
    """同步 Handler 执行时使用的未持久化执行上下文。"""

    source_message: Message
    input_data: InputT
    context_data: ContextT


class AttachmentTypeHandler(Generic[InputT, ContextT, OutputT], ABC):
    """约束一种附件的快照类型、执行方式和最小扩展点。"""

    attachment_type: AttachmentType
    execution_mode: ExecutionMode
    input_model: type[InputT]
    context_model: type[ContextT]
    output_model: type[OutputT]

    @property
    @abstractmethod
    def async_task(self) -> "AttachmentExecutionTask | None":
        """返回该附件绑定的异步任务；同步附件必须显式返回 None。"""

    @abstractmethod
    def prepare(
        self,
        *,
        user: str,
        source_message: Message,
        input_data: InputT,
    ) -> AttachmentPreparation[ContextT]:
        """基于来源消息和输入快照，生成首次持久化所需的标题和上下文。"""

    def execute(self, *, execution: AttachmentExecutionContext[InputT, ContextT]) -> OutputT:
        """执行同步附件业务；异步附件直接在绑定的 Celery Task 中实现。"""

        raise ImproperlyConfigured("同步 Attachment Handler 必须实现 execute")

    def edit_output(
        self,
        *,
        attachment: Attachment,
        current_output: OutputT,
        submitted_output: OutputT,
    ) -> OutputT:
        """默认禁止附件编辑，只有业务显式覆写后才开放。"""

        raise AttachmentNotEditable()

    def supports_output_edit(self) -> bool:
        """通过方法覆写判断编辑能力，避免重复维护布尔标记。"""

        return type(self).edit_output is not AttachmentTypeHandler.edit_output
