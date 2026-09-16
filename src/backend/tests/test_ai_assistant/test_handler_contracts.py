from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from services.web.ai_assistant.constants import MessageType
from services.web.ai_assistant.handlers import attachment_handler_registry
from services.web.ai_assistant.handlers.attachment import AttachmentTypeHandler
from services.web.ai_assistant.handlers.audit_analysis import AIAnalysisHandler
from services.web.ai_assistant.handlers.registry import AttachmentHandlerRegistry
from tests.test_ai_assistant.handler_contracts import (
    HandlerContractSpec,
    validate_handler_contracts,
)
from tests.test_ai_assistant.handlers import (
    EchoAsyncHandler,
    EchoAttachmentSyncHandler,
    EchoSyncHandler,
)
from tests.test_ai_assistant.production_handler_contracts import (
    ATTACHMENT_HANDLER_CONTRACTS,
    MESSAGE_HANDLER_CONTRACTS,
    captured_attachment_handlers,
    captured_message_handlers,
)


class HandlerContractValidatorTest(SimpleTestCase):
    def test_registered_handler_without_contract_fails(self):
        with self.assertRaisesRegex(AssertionError, "缺少行为契约"):
            validate_handler_contracts(
                handlers={MessageType.SYSTEM_SELECTION: EchoSyncHandler()},
                contracts={},
                handler_kind="message",
            )

    def test_async_handler_missing_retry_method_fails(self):
        class IncompleteAsyncContract(SimpleTestCase):
            def test_success_contract(self):
                pass

            def test_failure_contract(self):
                pass

            def test_stale_task_contract(self):
                pass

        handler = EchoAsyncHandler()
        with (
            mock.patch(
                "tests.test_ai_assistant.handler_contracts.import_string",
                return_value=IncompleteAsyncContract,
            ),
            self.assertRaisesRegex(AssertionError, rf"{type(handler).__name__}.*test_retry_contract"),
        ):
            self.validate_contract(handler)

    def test_stream_async_handler_also_requires_async_contract(self):
        class StreamOnlyContract(SimpleTestCase):
            def test_stream_success_contract(self):
                pass

            def test_stream_retry_contract(self):
                pass

        handler = EchoAsyncHandler()
        handler.is_stream = True
        with (
            mock.patch(
                "tests.test_ai_assistant.handler_contracts.import_string",
                return_value=StreamOnlyContract,
            ),
            self.assertRaisesRegex(AssertionError, rf"{type(handler).__name__}.*test_failure_contract"),
        ):
            self.validate_contract(handler)

    def test_contract_target_must_be_unittest_test_case(self):
        class CallableContainer:
            def test_success_contract(self):
                pass

            def test_invalid_output_contract(self):
                pass

        handler = EchoSyncHandler()
        with (
            mock.patch(
                "tests.test_ai_assistant.handler_contracts.import_string",
                return_value=CallableContainer,
            ),
            self.assertRaisesRegex(AssertionError, "必须继承 unittest.TestCase"),
        ):
            self.validate_contract(handler)

    def validate_contract(self, handler):
        validate_handler_contracts(
            handlers={handler.message_type: handler},
            contracts={handler.message_type: HandlerContractSpec(test_case_path="unused.Contract")},
            handler_kind="message",
        )


class ProductionMessageHandlerContractTest(SimpleTestCase):
    def test_production_message_registry_matches_contract_manifest(self):
        validate_handler_contracts(
            handlers=captured_message_handlers(),
            contracts=MESSAGE_HANDLER_CONTRACTS,
            handler_kind="message",
        )


class ProductionAttachmentHandlerContractTest(SimpleTestCase):
    def test_production_attachment_registry_matches_contract_manifest(self):
        validate_handler_contracts(
            handlers=captured_attachment_handlers(),
            contracts=ATTACHMENT_HANDLER_CONTRACTS,
            handler_kind="attachment",
        )

    def test_live_registry_pollution_does_not_change_captured_contracts(self):
        handler = EchoAttachmentSyncHandler()
        original = attachment_handler_registry.unregister(handler.attachment_type)
        attachment_handler_registry.register(handler)
        try:
            validate_handler_contracts(
                handlers=captured_attachment_handlers(),
                contracts=ATTACHMENT_HANDLER_CONTRACTS,
                handler_kind="attachment",
            )
        finally:
            attachment_handler_registry.unregister(handler.attachment_type)
            if original is not None:
                attachment_handler_registry.register(original)


class AttachmentRetryCapabilityTest(SimpleTestCase):
    """手动重试必须由附件类型显式声明，错误布尔值在注册阶段失败。"""

    def test_retry_defaults_closed_and_analysis_keeps_retry(self):
        self.assertIs(getattr(AttachmentTypeHandler, "supports_retry", None), False)
        self.assertIs(getattr(AIAnalysisHandler(), "supports_retry", None), True)

    def test_registry_rejects_non_boolean_retry_capability(self):
        for value in (None, 1, "false"):
            with self.subTest(value=value):
                handler = EchoAttachmentSyncHandler()
                handler.supports_retry = value
                with self.assertRaisesRegex(ImproperlyConfigured, "supports_retry"):
                    AttachmentHandlerRegistry().register(handler)
