from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, TypeVar

from django.core.exceptions import ImproperlyConfigured

from services.web.ai_assistant.constants import ExecutionMode, MessageType
from services.web.ai_assistant.models import Conversation, Message
from services.web.ai_assistant.schemas import MessageSchema

if TYPE_CHECKING:
    from services.web.ai_assistant.tasks import MessageAsyncTask

InputT = TypeVar("InputT", bound=MessageSchema)
ContextT = TypeVar("ContextT", bound=MessageSchema)
OutputT = TypeVar("OutputT", bound=MessageSchema)


@dataclass(frozen=True, slots=True)
class MessagePreparation(Generic[ContextT]):
    """Handler 交给平台持久化的最终父消息和独立上下文快照。"""

    parent_message: Message | None
    context_data: ContextT


class MessageTypeHandler(Generic[InputT, ContextT, OutputT], ABC):
    """约束一种消息的快照类型、执行方式和两个业务 Hook。"""

    message_type: MessageType
    execution_mode: ExecutionMode
    input_model: type[InputT]
    context_model: type[ContextT]
    output_model: type[OutputT]
    # 同步 Handler 无需重复声明；异步 Handler 直接绑定平台装饰器生成的 Task。
    async_task: "MessageAsyncTask[InputT, ContextT, OutputT] | None" = None

    @abstractmethod
    def prepare(
        self,
        *,
        user: str,
        conversation: Conversation,
        parent_message: Message | None,
        input_data: InputT,
    ) -> MessagePreparation[ContextT]:
        """选择并校验最终父消息，同时构造独立执行所需的上下文。"""

    def execute(self, *, input_data: InputT, context_data: ContextT) -> OutputT:
        """执行同步消息业务；异步消息直接在绑定的 Celery Task 中实现。"""

        raise ImproperlyConfigured("同步消息 Handler 必须实现 execute")
