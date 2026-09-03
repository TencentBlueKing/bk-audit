from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from services.web.ai_assistant.constants import (
    AttachmentType,
    ExecutionMode,
    MessageType,
)
from services.web.ai_assistant.handlers import (
    AttachmentHandlerRegistry,
    AttachmentPreparation,
    AttachmentTypeHandler,
    HandlerRegistry,
    MessageHandlerRegistry,
    MessagePreparation,
    MessageTypeHandler,
)
from services.web.ai_assistant.schemas import MessageSchema
from services.web.ai_assistant.services import AttachmentExecution, MessageExecution
from services.web.ai_assistant.tasks import (
    AttachmentAsyncTask,
    AttachmentExecutionTask,
    MessageAsyncTask,
    MessageExecutionTask,
    attachment_execution_task,
    message_execution_task,
)


class DecoratorInput(MessageSchema):
    text: str


class DecoratorContext(MessageSchema):
    prefix: str


class DecoratorOutput(MessageSchema):
    content: str


@message_execution_task(
    name="tests.ai_assistant.decorated_message",
    queue="tests_ai_assistant",
    acks_late=True,
    max_retries=3,
    time_limit=30,
    autoretry_for=(ValueError,),
)
def execute_decorated_message(
    self: MessageExecutionTask,
    execution: MessageExecution[DecoratorInput, DecoratorContext],
) -> DecoratorOutput:
    return DecoratorOutput(content=f"{execution.context_data.prefix}:{execution.input_data.text}")


@attachment_execution_task(
    name="tests.ai_assistant.decorated_attachment",
    queue="tests_ai_assistant",
    acks_late=True,
    max_retries=4,
    time_limit=60,
    autoretry_for=(RuntimeError,),
)
def execute_decorated_attachment(
    self: AttachmentExecutionTask,
    execution: AttachmentExecution[DecoratorInput, DecoratorContext],
) -> DecoratorOutput:
    return DecoratorOutput(content=f"{execution.context_data.prefix}:{execution.input_data.text}")


# 该显式声明用于 IDE 和代码审查验证装饰器能保留输入、上下文和输出泛型。
typed_message_task: MessageAsyncTask[DecoratorInput, DecoratorContext, DecoratorOutput] = execute_decorated_message
typed_attachment_task: AttachmentAsyncTask[
    DecoratorInput, DecoratorContext, DecoratorOutput
] = execute_decorated_attachment


class SyncMessageHandler(MessageTypeHandler[DecoratorInput, DecoratorContext, DecoratorOutput]):
    message_type = MessageType.SYSTEM_SELECTION
    execution_mode = ExecutionMode.SYNC
    input_model = DecoratorInput
    context_model = DecoratorContext
    output_model = DecoratorOutput

    def prepare(self, **kwargs):
        return MessagePreparation(parent_message=None, context_data=DecoratorContext(prefix="sync"))

    def execute(self, **kwargs):
        return DecoratorOutput(content="sync")


class AsyncMessageHandler(SyncMessageHandler):
    message_type = MessageType.NATURAL_LANGUAGE_SEARCH
    execution_mode = ExecutionMode.ASYNC
    async_task = execute_decorated_message


class SyncAttachmentHandler(AttachmentTypeHandler[DecoratorInput, DecoratorContext, DecoratorOutput]):
    attachment_type = AttachmentType.FIELD_STATISTICS
    execution_mode = ExecutionMode.SYNC
    input_model = DecoratorInput
    context_model = DecoratorContext
    output_model = DecoratorOutput

    def prepare(self, **kwargs):
        return AttachmentPreparation(title="统计", context_data=DecoratorContext(prefix="sync"))

    def execute(self, **kwargs):
        return DecoratorOutput(content="sync")


class AsyncAttachmentHandler(SyncAttachmentHandler):
    attachment_type = AttachmentType.AI_ANALYSIS
    execution_mode = ExecutionMode.ASYNC
    async_task = execute_decorated_attachment


class MessageHandlerWithAttachmentTask(AsyncMessageHandler):
    """模拟把附件 Task 错绑到消息 Handler 的非法声明。"""

    async_task = execute_decorated_attachment


class AttachmentHandlerWithMessageTask(AsyncAttachmentHandler):
    """模拟把消息 Task 错绑到附件 Handler 的非法声明。"""

    async_task = execute_decorated_message


class TaskDecoratorTest(SimpleTestCase):
    def test_message_decorator_preserves_task_type_and_celery_options(self):
        self.assertIsInstance(execute_decorated_message, MessageExecutionTask)
        self.assertEqual(execute_decorated_message.name, "tests.ai_assistant.decorated_message")
        self.assertEqual(execute_decorated_message.queue, "tests_ai_assistant")
        self.assertTrue(execute_decorated_message.acks_late)
        self.assertEqual(execute_decorated_message.max_retries, 3)
        self.assertEqual(execute_decorated_message.time_limit, 30)
        self.assertEqual(execute_decorated_message.autoretry_for, (ValueError,))
        self.assertTrue(callable(execute_decorated_message.run))
        self.assertTrue(callable(execute_decorated_message.apply_async))

    def test_attachment_decorator_preserves_task_type_and_celery_options(self):
        self.assertIsInstance(execute_decorated_attachment, AttachmentExecutionTask)
        self.assertEqual(execute_decorated_attachment.name, "tests.ai_assistant.decorated_attachment")
        self.assertEqual(execute_decorated_attachment.queue, "tests_ai_assistant")
        self.assertTrue(execute_decorated_attachment.acks_late)
        self.assertEqual(execute_decorated_attachment.max_retries, 4)
        self.assertEqual(execute_decorated_attachment.time_limit, 60)
        self.assertEqual(execute_decorated_attachment.autoretry_for, (RuntimeError,))
        self.assertTrue(callable(execute_decorated_attachment.run))
        self.assertTrue(callable(execute_decorated_attachment.apply_async))

    def test_decorator_rejects_platform_owned_celery_options(self):
        for decorator, option in (
            (message_execution_task, {"bind": False}),
            (message_execution_task, {"base": object}),
            (attachment_execution_task, {"bind": False}),
            (attachment_execution_task, {"base": object}),
        ):
            with self.subTest(decorator=decorator.__name__, option=option), self.assertRaises(TypeError):
                decorator(**option)

    def test_handler_uses_task_class_attribute_and_sync_defaults_to_none(self):
        self.assertIsNone(SyncMessageHandler().async_task)
        self.assertIsNone(SyncAttachmentHandler().async_task)
        self.assertIs(AsyncMessageHandler().async_task, execute_decorated_message)
        self.assertIs(AsyncAttachmentHandler().async_task, execute_decorated_attachment)

    def test_domain_tasks_implement_template_hooks_without_executor(self):
        for task_class in (MessageExecutionTask, AttachmentExecutionTask):
            with self.subTest(task_class=task_class.__name__):
                self.assertNotIn("executor", task_class.__dict__)
                for method_name in ("_load_execution", "_finish_success", "_finish_failure"):
                    self.assertIn(method_name, task_class.__dict__)
                    self.assertTrue(callable(getattr(task_class, method_name)))


class CommonHandlerRegistryTest(SimpleTestCase):
    def test_domain_registries_share_common_implementation(self):
        self.assertTrue(issubclass(MessageHandlerRegistry, HandlerRegistry))
        self.assertTrue(issubclass(AttachmentHandlerRegistry, HandlerRegistry))

    def test_registry_rejects_cross_domain_task(self):
        with self.assertRaises(ImproperlyConfigured):
            MessageHandlerRegistry().register(MessageHandlerWithAttachmentTask())
        with self.assertRaises(ImproperlyConfigured):
            AttachmentHandlerRegistry().register(AttachmentHandlerWithMessageTask())
