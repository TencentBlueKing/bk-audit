import unittest
from collections.abc import Mapping
from dataclasses import dataclass

from django.utils.module_loading import import_string

from services.web.ai_assistant.constants import ExecutionMode
from services.web.ai_assistant.handlers import AttachmentTypeHandler, MessageTypeHandler

SYNC_METHODS = frozenset({"test_success_contract", "test_invalid_output_contract"})
ASYNC_METHODS = frozenset(
    {"test_success_contract", "test_failure_contract", "test_retry_contract", "test_stale_task_contract"}
)
STREAM_METHODS = frozenset({"test_stream_success_contract", "test_stream_retry_contract"})


@dataclass(frozen=True, slots=True)
class HandlerContractSpec:
    test_case_path: str


def _required_methods(handler: MessageTypeHandler | AttachmentTypeHandler) -> frozenset[str]:
    required_methods = ASYNC_METHODS if handler.execution_mode == ExecutionMode.ASYNC else SYNC_METHODS
    if getattr(handler, "is_stream", False):
        required_methods |= STREAM_METHODS
    return required_methods


def validate_handler_contracts(
    *,
    handlers: Mapping[str, MessageTypeHandler | AttachmentTypeHandler],
    contracts: Mapping[str, HandlerContractSpec],
    handler_kind: str,
) -> None:
    """比较注册类型与契约清单，并按同步/异步/流式声明检查测试方法定义。"""

    indexed_handlers = {str(handler_type): handler for handler_type, handler in handlers.items()}
    indexed_contracts = {str(handler_type): spec for handler_type, spec in contracts.items()}
    missing_contracts = sorted(set(indexed_handlers) - set(indexed_contracts))
    if missing_contracts:
        raise AssertionError(f"{handler_kind} Handler 缺少行为契约: {', '.join(missing_contracts)}")
    extra_contracts = sorted(set(indexed_contracts) - set(indexed_handlers))
    if extra_contracts:
        raise AssertionError(f"{handler_kind} 契约缺少对应 Handler: {', '.join(extra_contracts)}")

    for handler_type, handler in indexed_handlers.items():
        test_case = import_string(indexed_contracts[handler_type].test_case_path)
        if not isinstance(test_case, type) or not issubclass(test_case, unittest.TestCase):
            raise AssertionError(
                f"{type(handler).__name__} 的契约目标必须继承 unittest.TestCase: "
                f"{indexed_contracts[handler_type].test_case_path}"
            )
        loadable_methods = set(unittest.defaultTestLoader.getTestCaseNames(test_case))
        missing_methods = sorted(
            method_name for method_name in _required_methods(handler) if method_name not in loadable_methods
        )
        if missing_methods:
            raise AssertionError(f"{type(handler).__name__} 缺少契约方法: {', '.join(missing_methods)}")
