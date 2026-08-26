from services.web.ai_assistant.handlers.attachment import (
    AttachmentExecutionContext,
    AttachmentExportResult,
    AttachmentPreparation,
    AttachmentTypeHandler,
)
from services.web.ai_assistant.handlers.message import (
    MessagePreparation,
    MessageTypeHandler,
)
from services.web.ai_assistant.handlers.registry import (
    AttachmentHandlerRegistry,
    HandlerRegistry,
    MessageHandlerRegistry,
    attachment_handler_registry,
    message_handler_registry,
)

# 导入业务处理器模块以触发注册（注册表与任务基类已就绪，模块内完成绑定）
from services.web.ai_assistant.handlers.audit_search import (
    LogSearchHandler,
    NaturalLanguageSearchHandler,
    SystemSelectionHandler,
)

__all__ = [
    "AttachmentExecutionContext",
    "AttachmentExportResult",
    "AttachmentHandlerRegistry",
    "AttachmentPreparation",
    "AttachmentTypeHandler",
    "HandlerRegistry",
    "LogSearchHandler",
    "MessageHandlerRegistry",
    "MessagePreparation",
    "MessageTypeHandler",
    "NaturalLanguageSearchHandler",
    "SystemSelectionHandler",
    "attachment_handler_registry",
    "message_handler_registry",
]
