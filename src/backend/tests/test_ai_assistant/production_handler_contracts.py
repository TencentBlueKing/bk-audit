from services.web.ai_assistant.handlers import (
    AttachmentTypeHandler,
    MessageTypeHandler,
    attachment_handler_registry,
    message_handler_registry,
)
from tests.test_ai_assistant.handler_contracts import HandlerContractSpec

MESSAGE_HANDLER_CONTRACTS: dict[str, HandlerContractSpec] = {}
ATTACHMENT_HANDLER_CONTRACTS: dict[str, HandlerContractSpec] = {}

_CAPTURED_MESSAGE_HANDLERS: dict[str, MessageTypeHandler] | None = None
_CAPTURED_ATTACHMENT_HANDLERS: dict[str, AttachmentTypeHandler] | None = None


def capture_production_registries() -> None:
    """只在首次调用时冻结当前 registry，避免后续用例 unregister 污染契约门禁。"""

    global _CAPTURED_MESSAGE_HANDLERS, _CAPTURED_ATTACHMENT_HANDLERS
    if _CAPTURED_MESSAGE_HANDLERS is None:
        _CAPTURED_MESSAGE_HANDLERS = dict(message_handler_registry.handlers)
    if _CAPTURED_ATTACHMENT_HANDLERS is None:
        _CAPTURED_ATTACHMENT_HANDLERS = dict(attachment_handler_registry.handlers)


def captured_message_handlers() -> dict[str, MessageTypeHandler]:
    capture_production_registries()
    return dict(_CAPTURED_MESSAGE_HANDLERS)


def captured_attachment_handlers() -> dict[str, AttachmentTypeHandler]:
    capture_production_registries()
    return dict(_CAPTURED_ATTACHMENT_HANDLERS)


# unittest 和 pytest 都会在执行测试方法前导入本模块。这里立即冻结生产注册表，
# 避免后续用例注册的测试 Handler 被惰性快照误判为生产 Handler。
capture_production_registries()
