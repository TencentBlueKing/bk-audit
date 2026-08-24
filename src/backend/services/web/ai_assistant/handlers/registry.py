from types import MappingProxyType
from typing import Any, Callable, Generic, TypeVar

from celery import Task
from django.core.exceptions import ImproperlyConfigured

from services.web.ai_assistant.constants import (
    AttachmentExportFormat,
    AttachmentType,
    ExecutionMode,
    MessageType,
)
from services.web.ai_assistant.exceptions import (
    AIAssistantException,
    UnsupportedAttachmentType,
    UnsupportedMessageType,
)
from services.web.ai_assistant.handlers.attachment import AttachmentTypeHandler
from services.web.ai_assistant.handlers.message import MessageTypeHandler
from services.web.ai_assistant.schemas import MessageSchema

HandlerT = TypeVar("HandlerT", MessageTypeHandler, AttachmentTypeHandler)


class HandlerRegistry(Generic[HandlerT]):
    """复用消息和附件 Handler 的注册、查找及公共定义校验。"""

    def __init__(
        self,
        *,
        handler_class: type[HandlerT],
        type_attribute: str,
        valid_types: list[str] | tuple[str, ...],
        unsupported_exception: type[AIAssistantException],
        task_class_loader: Callable[[], type[Task]],
        label: str,
    ):
        self._handler_class = handler_class
        self._type_attribute = type_attribute
        self._valid_types = valid_types
        self._unsupported_exception = unsupported_exception
        self._task_class_loader = task_class_loader
        self._label = label
        self._handlers: dict[str, HandlerT] = {}

    @property
    def handlers(self):
        """返回只读注册视图，供协议生成和运行时排查使用。"""

        return MappingProxyType(self._handlers)

    def register(self, handler: HandlerT) -> HandlerT:
        """注册一个 Handler；同一类型重复注册属于启动配置错误。"""

        # PolymorphicProxySerializer 会在首次生成 OpenAPI 时固化当前注册表：
        # 此前通过 AppConfig.ready() 注册的全部 Handler 都会被包含，之后热注册不保证刷新。
        self._validate(handler)
        handler_type = str(getattr(handler, self._type_attribute))
        if handler_type in self._handlers:
            raise ImproperlyConfigured(f"{self._label}类型已注册: {handler_type}")
        self._handlers[handler_type] = handler
        return handler

    def require(self, handler_type: str) -> HandlerT:
        """获取必须存在的 Handler，未注册时抛出对应领域的稳定异常。"""

        handler_type_value = str(handler_type)
        try:
            return self._handlers[handler_type_value]
        except KeyError as error:
            raise self._unsupported_exception(data={self._type_attribute: handler_type_value}) from error

    def unregister(self, handler_type: str) -> HandlerT | None:
        """移除指定 Handler；未注册时返回 None，主要用于测试隔离和应用卸载。"""

        return self._handlers.pop(str(handler_type), None)

    def _validate(self, handler: Any) -> None:
        """校验 Handler 的枚举、快照模型、同步实现和异步任务类型。"""

        if not isinstance(handler, self._handler_class):
            raise ImproperlyConfigured(f"{self._label} Handler 必须继承 {self._handler_class.__name__}")
        handler_type = getattr(handler, self._type_attribute, None)
        execution_mode = getattr(handler, "execution_mode", None)
        if str(handler_type) not in self._valid_types:
            raise ImproperlyConfigured(f"无效的{self._label}类型: {handler_type}")
        if str(execution_mode) not in ExecutionMode.values:
            raise ImproperlyConfigured(f"无效的执行方式: {execution_mode}")
        if not isinstance(handler.supports_feedback, bool):
            raise ImproperlyConfigured(f"{self._label} supports_feedback 必须是 bool")
        for field_name in ("input_model", "context_model", "output_model"):
            schema_type = getattr(handler, field_name, None)
            if not isinstance(schema_type, type) or not issubclass(schema_type, MessageSchema):
                raise ImproperlyConfigured(f"{field_name} 必须是 MessageSchema 子类")

        if execution_mode == ExecutionMode.SYNC:
            if handler.async_task is not None:
                raise ImproperlyConfigured(f"同步{self._label}不能配置异步 Task")
            if type(handler).execute is self._handler_class.execute or not callable(handler.execute):
                raise ImproperlyConfigured(f"同步{self._label} Handler 必须实现 execute")
            return

        if handler.async_task is None:
            raise ImproperlyConfigured(f"异步{self._label}必须配置异步 Task")
        # Task 基类按需加载，避免 Handler 注册模块和执行模块在初始化阶段循环导入。
        task_class = self._task_class_loader()
        if not isinstance(handler.async_task, task_class):
            raise ImproperlyConfigured(f"异步 Task 必须继承 {task_class.__name__}")


def _load_message_task_class() -> type[Task]:
    from services.web.ai_assistant.tasks import MessageExecutionTask

    return MessageExecutionTask


def _load_attachment_task_class() -> type[Task]:
    from services.web.ai_assistant.tasks import AttachmentExecutionTask

    return AttachmentExecutionTask


class MessageHandlerRegistry(HandlerRegistry[MessageTypeHandler]):
    """保留消息领域的注册表入口和异常语义。"""

    def __init__(self):
        super().__init__(
            handler_class=MessageTypeHandler,
            type_attribute="message_type",
            valid_types=MessageType.values,
            unsupported_exception=UnsupportedMessageType,
            task_class_loader=_load_message_task_class,
            label="消息",
        )


class AttachmentHandlerRegistry(HandlerRegistry[AttachmentTypeHandler]):
    """保留附件领域的注册表入口和异常语义。"""

    def __init__(self):
        super().__init__(
            handler_class=AttachmentTypeHandler,
            type_attribute="attachment_type",
            valid_types=AttachmentType.values,
            unsupported_exception=UnsupportedAttachmentType,
            task_class_loader=_load_attachment_task_class,
            label="附件",
        )

    def _validate(self, handler: Any) -> None:
        """在通用 Handler 校验后收敛附件导出与流式声明，防止能力与实现不一致。"""

        super()._validate(handler)
        if not isinstance(handler.is_stream, bool):
            raise ImproperlyConfigured("附件 is_stream 必须是 bool")
        if handler.is_stream and handler.execution_mode != ExecutionMode.ASYNC:
            raise ImproperlyConfigured("流式附件必须使用异步执行")
        export_formats = handler.export_formats
        if type(export_formats) is not tuple:
            raise ImproperlyConfigured("附件 export_formats 必须是 tuple")
        try:
            normalized_formats = tuple(AttachmentExportFormat(export_format) for export_format in export_formats)
        except (TypeError, ValueError) as error:
            raise ImproperlyConfigured("附件 export_formats 包含不支持的格式") from error
        if len(normalized_formats) != len(set(normalized_formats)):
            raise ImproperlyConfigured("附件 export_formats 不允许重复")
        if bool(normalized_formats) != (type(handler).export is not AttachmentTypeHandler.export):
            raise ImproperlyConfigured("附件 export_formats 声明必须与 export() 实现一致")


message_handler_registry = MessageHandlerRegistry()
attachment_handler_registry = AttachmentHandlerRegistry()
