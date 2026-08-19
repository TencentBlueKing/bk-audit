from celery import Task
from django.core.exceptions import ImproperlyConfigured
from pydantic import ValidationError

from services.web.ai_assistant.constants import (
    AttachmentExportFormat,
    AttachmentType,
    ExecutionMode,
)
from services.web.ai_assistant.exceptions import (
    AttachmentNotEditable,
    UnsupportedAttachmentType,
)
from services.web.ai_assistant.handlers import (
    AttachmentExportResult,
    AttachmentHandlerRegistry,
    AttachmentPreparation,
    AttachmentTypeHandler,
)
from services.web.ai_assistant.schemas import MessageSchema
from services.web.ai_assistant.tasks import attachment_execution_task
from tests.base import TestCase


class AttachmentEchoInput(MessageSchema):
    text: str


class AttachmentEchoContext(MessageSchema):
    prefix: str


class AttachmentEchoOutput(MessageSchema):
    content: str


@attachment_execution_task(
    name="tests.ai_assistant.echo_attachment_registry_success",
    queue="tests_ai_assistant",
    acks_late=True,
    max_retries=2,
    default_retry_delay=1,
    time_limit=30,
)
def execute_attachment_async_success(self, execution):
    raise NotImplementedError


class AttachmentHandlerRegistryTest(TestCase):
    def setUp(self):
        self.registry = AttachmentHandlerRegistry()

    def test_register_require_unregister_handler(self):
        handler = EchoAttachmentSyncHandler()

        registered = self.registry.register(handler)

        self.assertIs(registered, handler)
        self.assertIs(self.registry.require(AttachmentType.FIELD_STATISTICS), handler)
        self.assertIs(self.registry.unregister(AttachmentType.FIELD_STATISTICS), handler)
        self.assertIsNone(self.registry.unregister(AttachmentType.FIELD_STATISTICS))

    def test_handlers_is_read_only_mapping(self):
        self.registry.register(EchoAttachmentSyncHandler())

        with self.assertRaises(TypeError):
            self.registry.handlers[AttachmentType.AI_ANALYSIS] = EchoAttachmentSyncHandler()

    def test_feedback_capability_defaults_to_false_and_allows_explicit_true(self):
        self.assertFalse(EchoAttachmentSyncHandler().supports_feedback)

        handler = FeedbackAttachmentHandler()
        self.assertTrue(handler.supports_feedback)
        self.assertIs(self.registry.register(handler), handler)

    def test_export_capability_requires_immutable_unique_supported_formats_and_export_override(self):
        invalid_handlers = (
            ExportFormatsAsListHandler(),
            DuplicateExportFormatsHandler(),
            InvalidExportFormatHandler(),
            DeclaresFormatWithoutExportHandler(),
            OverridesExportWithoutFormatHandler(),
        )

        for handler in invalid_handlers:
            with self.subTest(handler=type(handler).__name__), self.assertRaises(ImproperlyConfigured):
                self.registry.register(handler)

    def test_export_capability_allows_handler_with_declared_formats_and_export_override(self):
        handler = ExportableAttachmentHandler()

        self.assertIs(self.registry.register(handler), handler)

    def test_export_result_validates_fields_and_is_immutable(self):
        result = AttachmentExportResult(
            filename="report.pdf",
            content_type="application/pdf",
            content=b"%PDF",
        )

        for invalid_data in (
            {"filename": "", "content_type": "application/pdf", "content": b"%PDF"},
            {"filename": "report.pdf", "content_type": "", "content": b"%PDF"},
            {"filename": "report.pdf", "content_type": "application/pdf", "content": "%PDF"},
        ):
            with self.subTest(invalid_data=invalid_data), self.assertRaises(ValidationError):
                AttachmentExportResult(**invalid_data)
        with self.assertRaises(ValidationError):
            result.filename = "changed.pdf"

    def test_duplicate_attachment_type_is_rejected(self):
        self.registry.register(EchoAttachmentSyncHandler())

        with self.assertRaises(ImproperlyConfigured):
            self.registry.register(EchoAttachmentSyncHandler())

    def test_non_handler_instance_is_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            self.registry.register(object())

    def test_invalid_attachment_type_is_rejected(self):
        handler = EchoAttachmentSyncHandler()
        handler.attachment_type = "UNKNOWN"

        with self.assertRaises(ImproperlyConfigured):
            self.registry.register(handler)

    def test_non_message_schema_model_is_rejected(self):
        handler = EchoAttachmentSyncHandler()
        handler.input_model = dict

        with self.assertRaises(ImproperlyConfigured):
            self.registry.register(handler)

    def test_non_boolean_feedback_capability_is_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            self.registry.register(InvalidFeedbackAttachmentHandler())

    def test_sync_handler_cannot_have_async_task(self):
        with self.assertRaises(ImproperlyConfigured):
            self.registry.register(SyncAttachmentHandlerWithAsyncTask())

    def test_sync_handler_requires_execute_implementation(self):
        for handler in (SyncAttachmentHandlerWithoutExecute(), SyncAttachmentHandlerWithNonCallableExecute()):
            with self.subTest(handler=type(handler).__name__):
                with self.assertRaises(ImproperlyConfigured):
                    self.registry.register(handler)

    def test_async_handler_requires_async_task(self):
        with self.assertRaises(ImproperlyConfigured):
            self.registry.register(AsyncAttachmentHandlerWithoutTask())

    def test_async_task_must_inherit_attachment_execution_task(self):
        with self.assertRaises(ImproperlyConfigured):
            self.registry.register(AsyncAttachmentHandlerWithInvalidTask())

    def test_require_unregistered_type_raises_business_exception(self):
        with self.assertRaises(UnsupportedAttachmentType):
            self.registry.require(AttachmentType.AI_ANALYSIS)

    def test_concrete_handler_preserves_generic_schema_contract(self):
        handler: AttachmentTypeHandler[
            AttachmentEchoInput, AttachmentEchoContext, AttachmentEchoOutput
        ] = EchoAttachmentSyncHandler()

        self.assertIs(handler.input_model, AttachmentEchoInput)
        self.assertIs(handler.context_model, AttachmentEchoContext)
        self.assertIs(handler.output_model, AttachmentEchoOutput)

    def test_default_edit_output_is_not_editable(self):
        with self.assertRaises(AttachmentNotEditable):
            EchoAttachmentSyncHandler().edit_output(
                attachment=None,
                current_output=AttachmentEchoOutput(content="current"),
                submitted_output=AttachmentEchoOutput(content="submitted"),
            )

    def test_async_handler_accepts_platform_task(self):
        handler = EchoAttachmentAsyncHandler()

        self.assertIs(self.registry.register(handler), handler)
        self.assertEqual(handler.execution_mode, ExecutionMode.ASYNC)
        self.assertIs(handler.async_task, execute_attachment_async_success)

    def test_async_task_keeps_business_celery_options(self):
        self.assertTrue(execute_attachment_async_success.acks_late)
        self.assertEqual(execute_attachment_async_success.queue, "tests_ai_assistant")
        self.assertEqual(execute_attachment_async_success.max_retries, 2)
        self.assertEqual(execute_attachment_async_success.default_retry_delay, 1)
        self.assertEqual(execute_attachment_async_success.time_limit, 30)


class IncompleteAttachmentHandler(
    AttachmentTypeHandler[AttachmentEchoInput, AttachmentEchoContext, AttachmentEchoOutput]
):
    input_model = AttachmentEchoInput
    context_model = AttachmentEchoContext
    output_model = AttachmentEchoOutput

    def prepare(self, **kwargs):
        raise NotImplementedError

    def execute(self, **kwargs):
        raise NotImplementedError


class MissingAttachmentTypeHandler(IncompleteAttachmentHandler):
    execution_mode = ExecutionMode.SYNC


class MissingAttachmentExecutionModeHandler(IncompleteAttachmentHandler):
    attachment_type = AttachmentType.FIELD_STATISTICS


class MissingAsyncTaskPropertyAttachmentHandler(
    AttachmentTypeHandler[AttachmentEchoInput, AttachmentEchoContext, AttachmentEchoOutput]
):
    attachment_type = AttachmentType.FIELD_STATISTICS
    execution_mode = ExecutionMode.SYNC
    input_model = AttachmentEchoInput
    context_model = AttachmentEchoContext
    output_model = AttachmentEchoOutput

    def prepare(self, **kwargs):
        raise NotImplementedError

    def execute(self, **kwargs):
        raise NotImplementedError


class EchoAttachmentSyncHandler(
    AttachmentTypeHandler[AttachmentEchoInput, AttachmentEchoContext, AttachmentEchoOutput]
):
    attachment_type = AttachmentType.FIELD_STATISTICS
    execution_mode = ExecutionMode.SYNC
    input_model = AttachmentEchoInput
    context_model = AttachmentEchoContext
    output_model = AttachmentEchoOutput

    def prepare(self, **kwargs):
        return AttachmentPreparation(
            title="字段统计",
            context_data=AttachmentEchoContext(prefix="sync"),
        )

    def execute(self, **kwargs):
        return AttachmentEchoOutput(content="sync:done")


class SyncAttachmentHandlerWithAsyncTask(EchoAttachmentSyncHandler):
    async_task = execute_attachment_async_success


class SyncAttachmentHandlerWithoutExecute(
    AttachmentTypeHandler[AttachmentEchoInput, AttachmentEchoContext, AttachmentEchoOutput]
):
    attachment_type = AttachmentType.FIELD_STATISTICS
    execution_mode = ExecutionMode.SYNC
    input_model = AttachmentEchoInput
    context_model = AttachmentEchoContext
    output_model = AttachmentEchoOutput

    def prepare(self, **kwargs):
        return AttachmentPreparation(
            title="字段统计",
            context_data=AttachmentEchoContext(prefix="sync"),
        )


class SyncAttachmentHandlerWithNonCallableExecute(SyncAttachmentHandlerWithoutExecute):
    execute = None


class EchoAttachmentAsyncHandler(EchoAttachmentSyncHandler):
    attachment_type = AttachmentType.AI_ANALYSIS
    execution_mode = ExecutionMode.ASYNC
    async_task = execute_attachment_async_success


class AsyncAttachmentHandlerWithoutTask(EchoAttachmentAsyncHandler):
    async_task = None


class AsyncAttachmentHandlerWithInvalidTask(EchoAttachmentAsyncHandler):
    async_task = Task()


class InvalidAttachmentExecutionModeHandler(EchoAttachmentSyncHandler):
    execution_mode = "BACKGROUND"


class InvalidFeedbackAttachmentHandler(EchoAttachmentSyncHandler):
    supports_feedback = 1


class FeedbackAttachmentHandler(EchoAttachmentSyncHandler):
    supports_feedback = True


class ExportFormatsAsListHandler(EchoAttachmentSyncHandler):
    export_formats = [AttachmentExportFormat.PDF]


class DuplicateExportFormatsHandler(EchoAttachmentSyncHandler):
    export_formats = (AttachmentExportFormat.PDF, AttachmentExportFormat.PDF)


class InvalidExportFormatHandler(EchoAttachmentSyncHandler):
    export_formats = ("HTML",)


class DeclaresFormatWithoutExportHandler(EchoAttachmentSyncHandler):
    export_formats = (AttachmentExportFormat.PDF,)


class OverridesExportWithoutFormatHandler(EchoAttachmentSyncHandler):
    def export(self, *, attachment, output_data, export_format):
        return AttachmentExportResult(
            filename="report.pdf",
            content_type="application/pdf",
            content=b"%PDF",
        )


class ExportableAttachmentHandler(EchoAttachmentSyncHandler):
    export_formats = (AttachmentExportFormat.MARKDOWN, AttachmentExportFormat.PDF)

    def export(self, *, attachment, output_data, export_format):
        return AttachmentExportResult(
            filename="report.pdf",
            content_type="application/pdf",
            content=b"%PDF",
        )


class InvalidAttachmentExecutionModeRegistryTest(TestCase):
    def test_sync_handler_defaults_async_task_to_none(self):
        self.assertIsNone(MissingAsyncTaskPropertyAttachmentHandler().async_task)

    def test_invalid_execution_mode_is_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            AttachmentHandlerRegistry().register(InvalidAttachmentExecutionModeHandler())

    def test_missing_required_handler_definition_is_rejected(self):
        for handler in (MissingAttachmentTypeHandler(), MissingAttachmentExecutionModeHandler()):
            with self.subTest(handler=type(handler).__name__):
                with self.assertRaises(ImproperlyConfigured):
                    AttachmentHandlerRegistry().register(handler)
