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

# isort: off
# 导入业务处理器模块以触发注册（注册表与任务基类已就绪，模块内完成绑定）。
# 注意：audit_search 会经 tasks -> services -> services.attachment 触发对
# handlers 包的回环导入，此处必须保持在 registry 导入之后，否则循环导入。
from services.web.ai_assistant.handlers.audit_search import (
    LogSearchHandler,
    NaturalLanguageSearchHandler,
    SystemSelectionHandler,
)

# isort: on

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
