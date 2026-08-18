from types import MappingProxyType
from typing import Any

from django.core.exceptions import ImproperlyConfigured

from services.web.ai_assistant.constants import (
    AttachmentType,
    ExecutionMode,
    MessageType,
)
from services.web.ai_assistant.exceptions import (
    UnsupportedAttachmentType,
    UnsupportedMessageType,
)
from services.web.ai_assistant.handlers.attachment import AttachmentTypeHandler
from services.web.ai_assistant.handlers.message import MessageTypeHandler
from services.web.ai_assistant.schemas import MessageSchema


class MessageHandlerRegistry:
    """维护消息类型与 Handler 的唯一映射，并在启动注册阶段尽早发现定义错误。"""

    def __init__(self):
        self._handlers: dict[str, MessageTypeHandler] = {}

    @property
    def handlers(self):
        """返回只读注册视图，供协议生成和运行时排查使用。"""

        return MappingProxyType(self._handlers)

    def register(self, handler: MessageTypeHandler) -> MessageTypeHandler:
        """注册一个 Handler；同一消息类型重复注册属于启动配置错误。"""

        self._validate(handler)
        message_type = str(handler.message_type)
        if message_type in self._handlers:
            raise ImproperlyConfigured(f"消息类型已注册: {message_type}")
        self._handlers[message_type] = handler
        return handler

    def require(self, message_type: str | MessageType) -> MessageTypeHandler:
        """获取必须存在的 Handler，未注册时抛出稳定的业务异常。"""

        message_type_value = str(message_type)
        try:
            return self._handlers[message_type_value]
        except KeyError as error:
            raise UnsupportedMessageType(data={"message_type": message_type_value}) from error

    def unregister(self, message_type: str | MessageType) -> MessageTypeHandler | None:
        """移除指定 Handler；未注册时返回 None，主要用于测试隔离和应用卸载。"""

        return self._handlers.pop(str(message_type), None)

    @staticmethod
    def _validate(handler: Any) -> None:
        """校验 Handler 的枚举、快照模型和执行任务定义。"""

        if not isinstance(handler, MessageTypeHandler):
            raise ImproperlyConfigured("消息 Handler 必须继承 MessageTypeHandler")
        message_type = getattr(handler, "message_type", None)
        execution_mode = getattr(handler, "execution_mode", None)
        if str(message_type) not in MessageType.values:
            raise ImproperlyConfigured(f"无效的消息类型: {message_type}")
        if str(execution_mode) not in ExecutionMode.values:
            raise ImproperlyConfigured(f"无效的执行方式: {execution_mode}")
        for field_name in ("input_model", "context_model", "output_model"):
            schema_type = getattr(handler, field_name, None)
            if not isinstance(schema_type, type) or not issubclass(schema_type, MessageSchema):
                raise ImproperlyConfigured(f"{field_name} 必须是 MessageSchema 子类")

        if handler.execution_mode == ExecutionMode.SYNC:
            if handler.async_task is not None:
                raise ImproperlyConfigured("同步消息不能配置异步 Task")
            if type(handler).execute is MessageTypeHandler.execute or not callable(handler.execute):
                raise ImproperlyConfigured("同步消息 Handler 必须实现 execute")
            return
        if handler.async_task is None:
            raise ImproperlyConfigured("异步消息必须配置异步 Task")

        # 延迟导入用于切断注册表与 Task 基类之间的模块循环依赖。
        from services.web.ai_assistant.tasks import MessageExecutionTask

        if not isinstance(handler.async_task, MessageExecutionTask):
            raise ImproperlyConfigured("异步 Task 必须继承 MessageExecutionTask")


message_handler_registry = MessageHandlerRegistry()


class AttachmentHandlerRegistry:
    """维护附件类型与 Handler 的唯一映射，并在启动注册阶段尽早发现定义错误。"""

    def __init__(self):
        self._handlers: dict[str, AttachmentTypeHandler] = {}

    @property
    def handlers(self):
        """返回只读注册视图，供协议生成和运行时排查使用。"""

        return MappingProxyType(self._handlers)

    def register(self, handler: AttachmentTypeHandler) -> AttachmentTypeHandler:
        """注册一个 Handler；同一附件类型重复注册属于启动配置错误。"""

        self._validate(handler)
        attachment_type = str(handler.attachment_type)
        if attachment_type in self._handlers:
            raise ImproperlyConfigured(f"附件类型已注册: {attachment_type}")
        self._handlers[attachment_type] = handler
        return handler

    def require(self, attachment_type: str | AttachmentType) -> AttachmentTypeHandler:
        """获取必须存在的 Handler，未注册时抛出稳定的业务异常。"""

        attachment_type_value = str(attachment_type)
        try:
            return self._handlers[attachment_type_value]
        except KeyError as error:
            raise UnsupportedAttachmentType(data={"attachment_type": attachment_type_value}) from error

    def unregister(self, attachment_type: str | AttachmentType) -> AttachmentTypeHandler | None:
        """移除指定 Handler；未注册时返回 None，主要用于测试隔离和应用卸载。"""

        return self._handlers.pop(str(attachment_type), None)

    @staticmethod
    def _validate(handler: Any) -> None:
        """校验 Handler 的枚举、快照模型和执行任务定义。"""

        if not isinstance(handler, AttachmentTypeHandler):
            raise ImproperlyConfigured("附件 Handler 必须继承 AttachmentTypeHandler")
        attachment_type = getattr(handler, "attachment_type", None)
        execution_mode = getattr(handler, "execution_mode", None)
        if str(attachment_type) not in AttachmentType.values:
            raise ImproperlyConfigured(f"无效的附件类型: {attachment_type}")
        if str(execution_mode) not in ExecutionMode.values:
            raise ImproperlyConfigured(f"无效的执行方式: {execution_mode}")
        for field_name in ("input_model", "context_model", "output_model"):
            schema_type = getattr(handler, field_name, None)
            if not isinstance(schema_type, type) or not issubclass(schema_type, MessageSchema):
                raise ImproperlyConfigured(f"{field_name} 必须是 MessageSchema 子类")

        if handler.execution_mode == ExecutionMode.SYNC:
            if handler.async_task is not None:
                raise ImproperlyConfigured("同步附件不能配置异步 Task")
            if type(handler).execute is AttachmentTypeHandler.execute or not callable(handler.execute):
                raise ImproperlyConfigured("同步 Attachment Handler 必须实现 execute")
            return
        if handler.async_task is None:
            raise ImproperlyConfigured("异步附件必须配置异步 Task")

        # 延迟导入用于切断注册表与 Task 基类之间的模块循环依赖。
        from services.web.ai_assistant.tasks import AttachmentExecutionTask

        if not isinstance(handler.async_task, AttachmentExecutionTask):
            raise ImproperlyConfigured("异步 Task 必须继承 AttachmentExecutionTask")


attachment_handler_registry = AttachmentHandlerRegistry()
