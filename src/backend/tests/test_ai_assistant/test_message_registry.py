from celery import Task
from django.core.exceptions import ImproperlyConfigured

from services.web.ai_assistant.constants import ExecutionMode, MessageType
from services.web.ai_assistant.exceptions import UnsupportedMessageType
from services.web.ai_assistant.handlers import (
    MessageHandlerRegistry,
    MessageTypeHandler,
)
from tests.base import TestCase
from tests.test_ai_assistant.handlers import (
    EchoAsyncHandler,
    EchoContext,
    EchoInput,
    EchoOutput,
    EchoSyncHandler,
    execute_async_success,
)


class MessageHandlerRegistryTest(TestCase):
    def setUp(self):
        self.registry = MessageHandlerRegistry()

    def test_register_require_unregister_handler(self):
        handler = EchoSyncHandler()

        registered = self.registry.register(handler)

        self.assertIs(registered, handler)
        self.assertIs(self.registry.require(MessageType.SYSTEM_SELECTION), handler)
        self.assertIs(self.registry.unregister(MessageType.SYSTEM_SELECTION), handler)
        self.assertIsNone(self.registry.unregister(MessageType.SYSTEM_SELECTION))

    def test_handlers_is_read_only_mapping(self):
        self.registry.register(EchoSyncHandler())

        with self.assertRaises(TypeError):
            self.registry.handlers[MessageType.LOG_SEARCH] = EchoSyncHandler()

    def test_feedback_capability_defaults_to_false_and_allows_explicit_true(self):
        self.assertFalse(EchoSyncHandler().supports_feedback)

        handler = FeedbackMessageHandler()
        self.assertTrue(handler.supports_feedback)
        self.assertIs(self.registry.register(handler), handler)

    def test_duplicate_message_type_is_rejected(self):
        self.registry.register(EchoSyncHandler())

        with self.assertRaises(ImproperlyConfigured):
            self.registry.register(EchoSyncHandler())

    def test_non_handler_instance_is_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            self.registry.register(object())

    def test_invalid_message_type_is_rejected(self):
        handler = EchoSyncHandler()
        handler.message_type = "UNKNOWN"

        with self.assertRaises(ImproperlyConfigured):
            self.registry.register(handler)

    def test_non_message_schema_model_is_rejected(self):
        handler = EchoSyncHandler()
        handler.input_model = dict

        with self.assertRaises(ImproperlyConfigured):
            self.registry.register(handler)

    def test_non_boolean_feedback_capability_is_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            self.registry.register(InvalidFeedbackMessageHandler())

    def test_sync_handler_cannot_have_async_task(self):
        with self.assertRaises(ImproperlyConfigured):
            self.registry.register(SyncHandlerWithAsyncTask())

    def test_sync_handler_requires_execute_implementation(self):
        for handler in (SyncHandlerWithoutExecute(), SyncHandlerWithNonCallableExecute()):
            with self.subTest(handler=type(handler).__name__):
                with self.assertRaises(ImproperlyConfigured):
                    self.registry.register(handler)

    def test_async_handler_requires_async_task(self):
        with self.assertRaises(ImproperlyConfigured):
            self.registry.register(AsyncHandlerWithoutTask())

    def test_async_task_must_inherit_message_execution_task(self):
        with self.assertRaises(ImproperlyConfigured):
            self.registry.register(AsyncHandlerWithInvalidTask())

    def test_require_unregistered_type_raises_business_exception(self):
        with self.assertRaises(UnsupportedMessageType):
            self.registry.require(MessageType.LOG_SEARCH)

    def test_concrete_handler_preserves_generic_schema_contract(self):
        handler: MessageTypeHandler[EchoInput, EchoContext, EchoOutput] = EchoSyncHandler()

        self.assertIs(handler.input_model, EchoInput)
        self.assertIs(handler.context_model, EchoContext)
        self.assertIs(handler.output_model, EchoOutput)

    def test_async_handler_accepts_platform_task(self):
        handler = EchoAsyncHandler()

        self.assertIs(self.registry.register(handler), handler)
        self.assertEqual(handler.execution_mode, ExecutionMode.ASYNC)
        self.assertIs(handler.async_task, execute_async_success)

    def test_async_task_keeps_business_celery_options(self):
        self.assertTrue(execute_async_success.acks_late)
        self.assertEqual(execute_async_success.queue, "tests_ai_assistant")
        self.assertEqual(execute_async_success.max_retries, 2)
        self.assertEqual(execute_async_success.default_retry_delay, 1)
        self.assertEqual(execute_async_success.time_limit, 30)


class InvalidExecutionModeHandler(EchoSyncHandler):
    execution_mode = "BACKGROUND"


class InvalidFeedbackMessageHandler(EchoSyncHandler):
    supports_feedback = "yes"


class FeedbackMessageHandler(EchoSyncHandler):
    supports_feedback = True


class IncompleteHandler(MessageTypeHandler[EchoInput, EchoContext, EchoOutput]):
    input_model = EchoInput
    context_model = EchoContext
    output_model = EchoOutput

    def prepare(self, **kwargs):
        raise NotImplementedError

    def execute(self, **kwargs):
        raise NotImplementedError


class MissingMessageTypeHandler(IncompleteHandler):
    execution_mode = ExecutionMode.SYNC


class MissingExecutionModeHandler(IncompleteHandler):
    message_type = MessageType.SYSTEM_SELECTION


class MissingAsyncTaskPropertyHandler(MessageTypeHandler[EchoInput, EchoContext, EchoOutput]):
    message_type = MessageType.SYSTEM_SELECTION
    execution_mode = ExecutionMode.SYNC
    input_model = EchoInput
    context_model = EchoContext
    output_model = EchoOutput

    def prepare(self, **kwargs):
        raise NotImplementedError

    def execute(self, **kwargs):
        raise NotImplementedError


class SyncHandlerWithAsyncTask(EchoSyncHandler):
    async_task = execute_async_success


class SyncHandlerWithoutExecute(MessageTypeHandler[EchoInput, EchoContext, EchoOutput]):
    message_type = MessageType.SYSTEM_SELECTION
    execution_mode = ExecutionMode.SYNC
    input_model = EchoInput
    context_model = EchoContext
    output_model = EchoOutput

    def prepare(self, **kwargs):
        raise NotImplementedError


class SyncHandlerWithNonCallableExecute(SyncHandlerWithoutExecute):
    execute = None


class AsyncHandlerWithoutTask(EchoAsyncHandler):
    async_task = None


class AsyncHandlerWithInvalidTask(EchoAsyncHandler):
    async_task = Task()


class InvalidExecutionModeRegistryTest(TestCase):
    def test_sync_handler_defaults_async_task_to_none(self):
        self.assertIsNone(MissingAsyncTaskPropertyHandler().async_task)

    def test_invalid_execution_mode_is_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            MessageHandlerRegistry().register(InvalidExecutionModeHandler())

    def test_missing_required_handler_definition_is_rejected(self):
        for handler in (MissingMessageTypeHandler(), MissingExecutionModeHandler()):
            with self.subTest(handler=type(handler).__name__):
                with self.assertRaises(ImproperlyConfigured):
                    MessageHandlerRegistry().register(handler)
