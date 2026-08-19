from unittest import mock
from uuid import UUID, uuid4

import yaml
from django.http import QueryDict
from django.test import TransactionTestCase, override_settings
from django.urls import resolve
from drf_spectacular.drainage import get_override
from drf_spectacular.views import SpectacularAPIView
from rest_framework.test import APIRequestFactory

from core.utils.spectacular import BKResourceAutoSchema
from services.web.ai_assistant.constants import (
    AttachmentType,
    ExecutionStatus,
    FeedbackSourceType,
    FeedbackType,
    MessageType,
)
from services.web.ai_assistant.exceptions import (
    AttachmentNotFound,
    AttachmentSnapshotValidationError,
    InvalidAttachmentSource,
)
from services.web.ai_assistant.handlers import attachment_handler_registry
from services.web.ai_assistant.models import Attachment, Conversation, Feedback, Message
from services.web.ai_assistant.resources.attachment import (
    CreateAttachment,
    GetAttachment,
    ListAttachments,
    RetryAttachment,
    UpdateAttachment,
)
from services.web.ai_assistant.serializers.attachment import (
    AttachmentCreateRequestSerializer,
    AttachmentDetailRequestSerializer,
    AttachmentInputDataField,
    AttachmentListItemSerializer,
    AttachmentListRequestSerializer,
    AttachmentOutputDataField,
    AttachmentResponseSerializer,
    AttachmentUpdateRequestSerializer,
    EditableAttachmentOutputDataField,
    _attachment_schema_mapping,
    _editable_attachment_output_schema_mapping,
)
from services.web.ai_assistant.serializers.feedback import FeedbackResponseSerializer
from services.web.ai_assistant.services.attachment_execution import (
    finish_attachment_success,
    load_attachment_execution,
)
from services.web.ai_assistant.views import AttachmentsViewSet
from tests.base import TestCase
from tests.test_ai_assistant.handlers import (
    AttachmentEchoInput,
    AttachmentEchoOutput,
    EchoAttachmentAsyncHandler,
    EchoAttachmentSyncHandler,
    EditableAttachmentEchoHandler,
    FeedbackAttachmentEchoHandler,
)


def _override_serializers(field_class):
    override = get_override(field_class, "field")
    serializers = override.serializers
    return serializers() if callable(serializers) else serializers


class AttachmentRequestSerializerTest(TestCase):
    def setUp(self):
        self.message_uid = str(uuid4())
        self.attachment_uid = str(uuid4())
        attachment_handler_registry.register(EditableAttachmentEchoHandler())
        attachment_handler_registry.register(EchoAttachmentAsyncHandler())

    def tearDown(self):
        for attachment_type in AttachmentType.values:
            attachment_handler_registry.unregister(attachment_type)

    def test_create_request_requires_typed_business_input(self):
        serializer = AttachmentCreateRequestSerializer(
            data={
                "message_uid": self.message_uid,
                "attachment_type": AttachmentType.FIELD_STATISTICS,
                "input_data": {"text": "hello"},
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["message_uid"], UUID(self.message_uid))

    def test_create_request_rejects_missing_input_and_ignores_internal_fields(self):
        missing_input = AttachmentCreateRequestSerializer(
            data={
                "message_uid": self.message_uid,
                "attachment_type": AttachmentType.FIELD_STATISTICS,
            }
        )
        internal_fields = AttachmentCreateRequestSerializer(
            data={
                "message_uid": self.message_uid,
                "attachment_type": AttachmentType.FIELD_STATISTICS,
                "input_data": {"text": "hello"},
                "status": ExecutionStatus.SUCCESS,
                "output_data": {"content": "forged"},
                "context_data": {"private": True},
                "task_id": "task-1",
                "is_stream": True,
                "stream_config": {"mode": "stream"},
                "stream_archive": [{"delta": "x"}],
            }
        )

        self.assertFalse(missing_input.is_valid())
        self.assertTrue(internal_fields.is_valid(), internal_fields.errors)
        for field_name in (
            "status",
            "output_data",
            "context_data",
            "task_id",
            "is_stream",
            "stream_config",
            "stream_archive",
        ):
            self.assertNotIn(field_name, internal_fields.validated_data)

    def test_all_attachment_api_fields_have_swagger_descriptions(self):
        serializer_classes = (
            AttachmentCreateRequestSerializer,
            AttachmentDetailRequestSerializer,
            AttachmentListRequestSerializer,
            AttachmentUpdateRequestSerializer,
            AttachmentResponseSerializer,
            AttachmentListItemSerializer,
            FeedbackResponseSerializer,
        )

        for serializer_class in serializer_classes:
            for field_name, field in serializer_class().fields.items():
                with self.subTest(serializer=serializer_class.__name__, field=field_name):
                    self.assertTrue(field.help_text)

    def test_swagger_snapshot_schema_mapping_uses_registered_handler_models(self):
        input_schemas = _attachment_schema_mapping("input_model")
        output_schemas = _attachment_schema_mapping("output_model")
        input_override_serializers = _override_serializers(AttachmentInputDataField)
        output_override_serializers = _override_serializers(AttachmentOutputDataField)

        self.assertIs(input_schemas[AttachmentType.FIELD_STATISTICS], AttachmentEchoInput)
        self.assertIs(input_schemas[AttachmentType.AI_ANALYSIS], AttachmentEchoInput)
        self.assertIs(output_schemas[AttachmentType.FIELD_STATISTICS], AttachmentEchoOutput)
        self.assertIs(output_schemas[AttachmentType.AI_ANALYSIS], AttachmentEchoOutput)
        self.assertEqual(input_override_serializers, [AttachmentEchoInput])
        self.assertEqual(output_override_serializers, [AttachmentEchoOutput])

    def test_editable_output_swagger_only_exposes_handlers_that_override_edit_output(self):
        attachment_handler_registry.unregister(AttachmentType.FIELD_STATISTICS)
        attachment_handler_registry.register(EchoAttachmentSyncHandler())

        self.assertEqual(_editable_attachment_output_schema_mapping(), {})

        attachment_handler_registry.unregister(AttachmentType.FIELD_STATISTICS)
        attachment_handler_registry.register(EditableAttachmentEchoHandler())
        editable_schemas = _editable_attachment_output_schema_mapping()
        editable_override_serializers = _override_serializers(EditableAttachmentOutputDataField)

        self.assertEqual(set(editable_schemas), {AttachmentType.FIELD_STATISTICS})
        self.assertIs(editable_schemas[AttachmentType.FIELD_STATISTICS], AttachmentEchoOutput)
        self.assertEqual(editable_override_serializers, [AttachmentEchoOutput])
        self.assertNotIn(AttachmentType.AI_ANALYSIS, editable_schemas)

    def test_update_request_requires_title_or_output_data(self):
        invalid = AttachmentUpdateRequestSerializer(data={"attachment_uid": self.attachment_uid})
        title_only = AttachmentUpdateRequestSerializer(data={"attachment_uid": self.attachment_uid, "title": "新的标题"})
        output_only = AttachmentUpdateRequestSerializer(
            data={
                "attachment_uid": self.attachment_uid,
                "output_data": {"content": "新的产物"},
            }
        )

        self.assertFalse(invalid.is_valid())
        self.assertTrue(title_only.is_valid(), title_only.errors)
        self.assertTrue(output_only.is_valid(), output_only.errors)
        self.assertNotIn("attachment_type", AttachmentUpdateRequestSerializer().fields)

    def test_list_request_accepts_single_csv_array_and_repeated_query_params(self):
        serializer_cases = (
            {
                "attachment_type": AttachmentType.FIELD_STATISTICS,
                "status": ExecutionStatus.SUCCESS,
            },
            {
                "attachment_type": "FIELD_STATISTICS,AI_ANALYSIS",
                "status": "SUCCESS,FAILED",
            },
            {
                "attachment_type": [AttachmentType.FIELD_STATISTICS, AttachmentType.AI_ANALYSIS],
                "status": [ExecutionStatus.SUCCESS, ExecutionStatus.FAILED],
            },
            QueryDict(
                "attachment_type=FIELD_STATISTICS&attachment_type=AI_ANALYSIS"
                "&status=SUCCESS&status=FAILED"
                f"&conversation_uid={uuid4()}&source_message_uid={uuid4()}&keyword=分析"
            ),
        )

        for data in serializer_cases:
            with self.subTest(data=data):
                serializer = AttachmentListRequestSerializer(data=data)
                self.assertTrue(serializer.is_valid(), serializer.errors)
                self.assertTrue(serializer.validated_data["attachment_type"])
                self.assertTrue(serializer.validated_data["status"])

        fields = AttachmentListRequestSerializer().fields
        self.assertIn("attachment_type", fields)
        self.assertIn("status", fields)
        self.assertIn("keyword", fields)
        self.assertIn("conversation_uid", fields)
        self.assertIn("source_message_uid", fields)
        self.assertNotIn("attachment_types", fields)
        self.assertNotIn("statuses", fields)
        self.assertNotIn("page", fields)
        self.assertNotIn("page_size", fields)

    def test_detail_and_list_response_only_expose_public_fields(self):
        detail_fields = set(AttachmentResponseSerializer().fields)
        list_fields = set(AttachmentListItemSerializer().fields)

        self.assertEqual(
            detail_fields,
            {
                "uid",
                "source_message_uid",
                "attachment_type",
                "status",
                "title",
                "content_updated_at",
                "input_data",
                "output_data",
                "error_code",
                "error_message",
                "created_at",
                "updated_at",
                "supports_feedback",
                "feedback",
            },
        )
        self.assertEqual(
            list_fields,
            {
                "uid",
                "attachment_type",
                "status",
                "title",
                "created_at",
                "content_updated_at",
                "source_message",
                "conversation",
                "supports_feedback",
            },
        )
        for field_name in ("id", "context_data", "task_id", "is_stream", "stream_config", "stream_archive"):
            self.assertNotIn(field_name, detail_fields)
            self.assertNotIn(field_name, list_fields)

    @override_settings(ROOT_URLCONF="urls")
    def test_real_openapi_endpoint_exposes_attachment_list_response_as_array(self):
        request = APIRequestFactory().get("/api/schema/")
        request.user = mock.Mock(is_staff=True, is_authenticated=True)

        response = SpectacularAPIView.as_view()(request)
        response.render()
        schema = yaml.safe_load(response.content)
        list_response_schema = schema["paths"]["/api/v1/ai_assistant/attachments/"]["get"]["responses"]["200"][
            "content"
        ]["application/json"]["schema"]

        self.assertEqual(list_response_schema.get("type"), "array")
        self.assertEqual(list_response_schema.get("items"), {"$ref": "#/components/schemas/AttachmentListItem"})

        parameters = {
            parameter["name"]: parameter
            for parameter in schema["paths"]["/api/v1/ai_assistant/attachments/"]["get"]["parameters"]
        }
        expected_enums = {
            "attachment_type": set(AttachmentType.values),
            "status": set(ExecutionStatus.values),
        }
        for parameter_name, expected_enum in expected_enums.items():
            with self.subTest(parameter=parameter_name):
                parameter = parameters[parameter_name]
                self.assertEqual(parameter["schema"]["type"], "array")
                self.assertEqual(set(parameter["schema"]["items"]["enum"]), expected_enum)
                self.assertEqual(parameter["style"], "form")
                self.assertTrue(parameter["explode"])

    @override_settings(ROOT_URLCONF="urls")
    def test_common_auto_schema_recognizes_flexible_list_query_parameters(self):
        request = APIRequestFactory().get("/api/schema/")
        request.user = mock.Mock(is_staff=True, is_authenticated=True)

        # 使用公共 AutoSchema 生成参数，避免附件专属适配掩盖通用 ListField 推导问题。
        with mock.patch.object(AttachmentsViewSet, "schema", BKResourceAutoSchema()):
            response = SpectacularAPIView.as_view()(request)
            response.render()
        schema = yaml.safe_load(response.content)
        parameters = {
            parameter["name"]: parameter
            for parameter in schema["paths"]["/api/v1/ai_assistant/attachments/"]["get"]["parameters"]
        }

        for parameter_name in ("attachment_type", "status"):
            with self.subTest(parameter=parameter_name):
                self.assertEqual(parameters[parameter_name]["schema"]["type"], "array")

    @override_settings(ROOT_URLCONF="urls")
    def test_real_openapi_attachment_snapshot_one_of_has_no_false_discriminator(self):
        request = APIRequestFactory().get("/api/schema/")
        request.user = mock.Mock(is_staff=True, is_authenticated=True)

        response = SpectacularAPIView.as_view()(request)
        response.render()
        components = yaml.safe_load(response.content)["components"]["schemas"]
        expected_one_of = {
            "AIAttachmentInputDataRequest": [{"$ref": "#/components/schemas/AttachmentEchoInputRequest"}],
            "AIAttachmentOutputData": [{"$ref": "#/components/schemas/AttachmentEchoOutput"}],
            "EditableAIAttachmentOutputDataRequest": [{"$ref": "#/components/schemas/AttachmentEchoOutputRequest"}],
        }

        for component_name, expected_refs in expected_one_of.items():
            with self.subTest(component=component_name):
                component = components[component_name]
                self.assertEqual(component["oneOf"], expected_refs)
                self.assertNotIn("discriminator", component)

    @override_settings(ROOT_URLCONF="urls")
    def test_real_openapi_attachment_snapshot_schema_is_valid_without_registered_handler(self):
        for attachment_type in AttachmentType.values:
            attachment_handler_registry.unregister(attachment_type)

        request = APIRequestFactory().get("/api/schema/")
        request.user = mock.Mock(is_staff=True, is_authenticated=True)

        response = SpectacularAPIView.as_view()(request)
        response.render()
        components = yaml.safe_load(response.content)["components"]["schemas"]

        for component_name in (
            "AIAttachmentInputDataRequest",
            "AIAttachmentOutputData",
            "EditableAIAttachmentOutputDataRequest",
        ):
            with self.subTest(component=component_name):
                self.assertTrue(components[component_name]["oneOf"])


class EditableAnalysisAttachmentHandler(EditableAttachmentEchoHandler):
    attachment_type = AttachmentType.AI_ANALYSIS


@mock.patch("services.web.ai_assistant.resources.attachment.get_request_username", return_value="alice")
class AttachmentResourceTest(TestCase):
    def setUp(self):
        self.conversation = Conversation.objects.create(
            title="查询用户登录日志",
            created_by="alice",
            updated_by="alice",
        )
        self.source_message = Message.objects.create(
            conversation=self.conversation,
            message_type=MessageType.LOG_SEARCH,
            status=ExecutionStatus.SUCCESS,
            task_id="message-task",
            input_data={"text": "query"},
            context_data={"prefix": "source"},
            output_data={"content": "source"},
            created_by="alice",
            updated_by="alice",
        )
        self.sync_handler = FeedbackAttachmentEchoHandler()
        self.async_handler = EchoAttachmentAsyncHandler()
        attachment_handler_registry.register(self.sync_handler)
        attachment_handler_registry.register(self.async_handler)

    def tearDown(self):
        for attachment_type in AttachmentType.values:
            attachment_handler_registry.unregister(attachment_type)

    def create_attachment(
        self,
        *,
        source_message=None,
        attachment_type=AttachmentType.FIELD_STATISTICS,
        status=ExecutionStatus.SUCCESS,
        task_id=None,
        title="原始标题",
        input_data=None,
        output_data=None,
        created_by="alice",
    ):
        return Attachment.objects.create(
            source_message=source_message or self.source_message,
            attachment_type=attachment_type,
            title=title,
            status=status,
            task_id=task_id,
            input_data=input_data or {"text": "hello"},
            context_data={"prefix": "ctx"},
            output_data=output_data,
            error_code="OLD_CODE" if status == ExecutionStatus.FAILED else "",
            error_message="old error" if status == ExecutionStatus.FAILED else "",
            created_by=created_by,
            updated_by=created_by,
        )

    def test_create_sync_attachment_returns_success_without_internal_fields(self, _username):
        response = CreateAttachment().request(
            {
                "message_uid": str(self.source_message.uid),
                "attachment_type": AttachmentType.FIELD_STATISTICS,
                "input_data": {"text": "hello"},
            }
        )

        self.assertEqual(response["status"], ExecutionStatus.SUCCESS)
        self.assertEqual(response["source_message_uid"], str(self.source_message.uid))
        self.assertEqual(response["input_data"], {"text": "hello"})
        self.assertEqual(response["output_data"], {"content": "sync:hello"})
        self.assertTrue(response["supports_feedback"])
        self.assertIsNone(response["feedback"])
        for internal_field in ("id", "context_data", "task_id", "is_stream", "stream_config", "stream_archive"):
            self.assertNotIn(internal_field, response)

    def test_create_async_attachment_supports_polling_to_final_state(self, _username):
        with mock.patch.object(self.async_handler.async_task, "apply_async"):
            with self.captureOnCommitCallbacks(execute=True):
                created = CreateAttachment().request(
                    {
                        "message_uid": str(self.source_message.uid),
                        "attachment_type": AttachmentType.AI_ANALYSIS,
                        "input_data": {"text": "search"},
                    }
                )

        self.assertEqual(created["status"], ExecutionStatus.PROCESSING)
        self.assertIsNone(created["output_data"])

        attachment = Attachment.objects.get(uid=created["uid"])
        execution = load_attachment_execution(
            attachment_id=attachment.id,
            task_id=attachment.task_id,
            celery_task_id=attachment.task_id,
        )
        finish_attachment_success(
            execution=execution,
            task_id=attachment.task_id,
            output_data={"content": "async:search"},
        )

        detail = GetAttachment().request({"attachment_uid": created["uid"]})
        self.assertEqual(detail["status"], ExecutionStatus.SUCCESS)
        self.assertEqual(detail["output_data"], {"content": "async:search"})

    def test_create_async_dispatch_failure_returns_failed_attachment(self, _username):
        with mock.patch.object(self.async_handler.async_task, "apply_async", side_effect=RuntimeError("broker secret")):
            with self.captureOnCommitCallbacks(execute=True):
                created = CreateAttachment().request(
                    {
                        "message_uid": str(self.source_message.uid),
                        "attachment_type": AttachmentType.AI_ANALYSIS,
                        "input_data": {"text": "search"},
                    }
                )

        detail = GetAttachment().request({"attachment_uid": created["uid"]})
        self.assertEqual(detail["status"], ExecutionStatus.FAILED)
        self.assertEqual(detail["error_code"], "TASK_DISPATCH_FAILED")
        self.assertNotIn("task_id", detail)

    def test_list_filters_by_type_status_keyword_conversation_and_source(self, _username):
        other_conversation = Conversation.objects.create(
            title="其他会话",
            created_by="alice",
            updated_by="alice",
        )
        other_source_message = Message.objects.create(
            conversation=other_conversation,
            message_type=MessageType.LOG_SEARCH,
            status=ExecutionStatus.SUCCESS,
            task_id="other-message-task",
            input_data={"text": "query"},
            context_data={"prefix": "source"},
            output_data={"content": "source"},
            created_by="alice",
            updated_by="alice",
        )
        first = self.create_attachment(
            attachment_type=AttachmentType.FIELD_STATISTICS,
            status=ExecutionStatus.SUCCESS,
            title="字段统计 Alpha",
            output_data={"content": "one"},
        )
        second = self.create_attachment(
            attachment_type=AttachmentType.AI_ANALYSIS,
            status=ExecutionStatus.FAILED,
            title="AI 分析 Alpha",
            output_data=None,
        )
        self.create_attachment(
            source_message=other_source_message,
            attachment_type=AttachmentType.AI_ANALYSIS,
            status=ExecutionStatus.SUCCESS,
            title="AI 分析 Beta",
            output_data={"content": "three"},
        )

        response = ListAttachments().request(
            {
                "attachment_type": "FIELD_STATISTICS,AI_ANALYSIS",
                "status": [ExecutionStatus.SUCCESS, ExecutionStatus.FAILED],
                "keyword": "Alpha",
                "conversation_uid": str(self.conversation.uid),
                "source_message_uid": str(self.source_message.uid),
            }
        )

        self.assertEqual([item["uid"] for item in response], [str(second.uid), str(first.uid)])
        self.assertEqual(
            set(response[0]),
            {
                "uid",
                "attachment_type",
                "status",
                "title",
                "created_at",
                "content_updated_at",
                "source_message",
                "conversation",
                "supports_feedback",
            },
        )
        self.assertNotIn("input_data", response[0])
        self.assertNotIn("output_data", response[0])
        self.assertEqual(response[0]["source_message"]["uid"], str(self.source_message.uid))
        self.assertEqual(response[0]["conversation"]["uid"], str(self.conversation.uid))

    def test_attachment_detail_exposes_current_feedback_but_list_only_exposes_capability(self, _username):
        attachment = self.create_attachment(output_data={"content": "feedback"})
        Feedback.objects.create(
            source_type=FeedbackSourceType.ATTACHMENT,
            source_id=attachment.id,
            feedback_type=FeedbackType.DISLIKE,
            comment="不准确",
            created_by="alice",
            updated_by="alice",
        )

        detail = GetAttachment().request({"attachment_uid": str(attachment.uid)})
        listed = ListAttachments().request({})

        self.assertTrue(detail["supports_feedback"])
        self.assertEqual(detail["feedback"]["source_uid"], str(attachment.uid))
        self.assertTrue(listed[0]["supports_feedback"])
        self.assertNotIn("feedback", listed[0])

    def test_update_supports_title_and_editable_ai_analysis_output(self, _username):
        title_attachment = self.create_attachment(
            attachment_type=AttachmentType.FIELD_STATISTICS,
            status=ExecutionStatus.SUCCESS,
            title="旧标题",
            output_data={"content": "old"},
        )
        updated_title = UpdateAttachment().request({"attachment_uid": str(title_attachment.uid), "title": "  新标题  "})
        self.assertEqual(updated_title["title"], "新标题")

        analysis_attachment = self.create_attachment(
            attachment_type=AttachmentType.AI_ANALYSIS,
            status=ExecutionStatus.SUCCESS,
            title="AI 分析",
            output_data={"content": "old"},
        )
        attachment_handler_registry.unregister(AttachmentType.AI_ANALYSIS)
        attachment_handler_registry.register(EditableAnalysisAttachmentHandler())

        updated_output = UpdateAttachment().request(
            {
                "attachment_uid": str(analysis_attachment.uid),
                "output_data": {"content": "new"},
            }
        )

        self.assertEqual(updated_output["output_data"], {"content": "new"})

    def test_update_invalid_output_raises_public_request_validation_error(self, _username):
        attachment = self.create_attachment(
            attachment_type=AttachmentType.AI_ANALYSIS,
            status=ExecutionStatus.SUCCESS,
            output_data={"content": "old"},
        )
        attachment_handler_registry.unregister(AttachmentType.AI_ANALYSIS)
        attachment_handler_registry.register(EditableAnalysisAttachmentHandler())

        with self.assertRaises(AttachmentSnapshotValidationError) as context:
            UpdateAttachment().request(
                {
                    "attachment_uid": str(attachment.uid),
                    "output_data": {"invalid": True},
                }
            )

        self.assertEqual(context.exception.STATUS_CODE, 400)

    def test_retry_failed_async_attachment_returns_processing_snapshot(self, _username):
        attachment = self.create_attachment(
            attachment_type=AttachmentType.AI_ANALYSIS,
            status=ExecutionStatus.FAILED,
            task_id="task-old",
            title="AI 分析",
            output_data={"content": "old"},
        )

        with mock.patch.object(self.async_handler.async_task, "apply_async"):
            with self.captureOnCommitCallbacks(execute=True):
                retried = RetryAttachment().request({"attachment_uid": str(attachment.uid)})

        attachment.refresh_from_db()
        self.assertEqual(retried["status"], ExecutionStatus.PROCESSING)
        self.assertIsNone(retried["output_data"])
        self.assertEqual(attachment.status, ExecutionStatus.PROCESSING)
        self.assertNotEqual(attachment.task_id, "task-old")
        self.assertNotIn("task_id", retried)

    def test_cross_user_soft_deleted_and_corrupted_snapshots_are_rejected(self, _username):
        foreign_conversation = Conversation.objects.create(
            title="foreign",
            created_by="bob",
            updated_by="bob",
        )
        foreign_source_message = Message.objects.create(
            conversation=foreign_conversation,
            message_type=MessageType.LOG_SEARCH,
            status=ExecutionStatus.SUCCESS,
            task_id="foreign-message-task",
            input_data={"text": "query"},
            context_data={"prefix": "source"},
            output_data={"content": "source"},
            created_by="bob",
            updated_by="bob",
        )
        foreign_attachment = self.create_attachment(
            source_message=foreign_source_message,
            attachment_type=AttachmentType.FIELD_STATISTICS,
            created_by="bob",
            output_data={"content": "foreign"},
        )
        deleted_conversation = Conversation.objects.create(
            title="deleted",
            created_by="alice",
            updated_by="alice",
        )
        deleted_source_message = Message.objects.create(
            conversation=deleted_conversation,
            message_type=MessageType.LOG_SEARCH,
            status=ExecutionStatus.SUCCESS,
            task_id="deleted-message-task",
            input_data={"text": "query"},
            context_data={"prefix": "source"},
            output_data={"content": "source"},
            created_by="alice",
            updated_by="alice",
        )
        deleted_attachment = self.create_attachment(
            source_message=deleted_source_message,
            attachment_type=AttachmentType.FIELD_STATISTICS,
            output_data={"content": "deleted"},
        )
        deleted_conversation.delete()
        corrupted_attachment = self.create_attachment(
            attachment_type=AttachmentType.FIELD_STATISTICS,
            status=ExecutionStatus.SUCCESS,
            input_data={"invalid": True},
            output_data={"content": "ok"},
        )

        with self.assertRaises(InvalidAttachmentSource):
            CreateAttachment().request(
                {
                    "message_uid": str(foreign_source_message.uid),
                    "attachment_type": AttachmentType.FIELD_STATISTICS,
                    "input_data": {"text": "hello"},
                }
            )
        with self.assertRaises(InvalidAttachmentSource):
            CreateAttachment().request(
                {
                    "message_uid": str(deleted_source_message.uid),
                    "attachment_type": AttachmentType.FIELD_STATISTICS,
                    "input_data": {"text": "hello"},
                }
            )
        for attachment_uid in (str(foreign_attachment.uid), str(deleted_attachment.uid)):
            with self.subTest(attachment_uid=attachment_uid):
                with self.assertRaises(AttachmentNotFound):
                    GetAttachment().request({"attachment_uid": attachment_uid})
                with self.assertRaises(AttachmentNotFound):
                    UpdateAttachment().request({"attachment_uid": attachment_uid, "title": "新标题"})
                with self.assertRaises(AttachmentNotFound):
                    RetryAttachment().request({"attachment_uid": attachment_uid})
        with self.assertRaises(AttachmentSnapshotValidationError):
            GetAttachment().request({"attachment_uid": str(corrupted_attachment.uid)})


@override_settings(ROOT_URLCONF="services.web.urls")
class AttachmentResourceRoutingTest(TestCase):
    def test_attachment_routes_use_external_uid(self):
        message_uid = str(uuid4())
        attachment_uid = str(uuid4())

        self.assertEqual(resolve("/api/v1/ai_assistant/attachments/").url_name, "attachments-list")
        nested_create = resolve(f"/api/v1/ai_assistant/messages/{message_uid}/attachments/")
        self.assertEqual(nested_create.kwargs, {"message_uid": message_uid})
        detail = resolve(f"/api/v1/ai_assistant/attachments/{attachment_uid}/")
        retry = resolve(f"/api/v1/ai_assistant/attachments/{attachment_uid}/retry/")
        self.assertEqual(detail.kwargs, {"attachment_uid": attachment_uid})
        self.assertEqual(retry.kwargs, {"attachment_uid": attachment_uid})


class AttachmentResourceTransactionTest(TransactionTestCase):
    available_apps = ["services.web.ai_assistant"]
    reset_sequences = True

    def setUp(self):
        self.conversation = Conversation.objects.create(
            title="查询用户登录日志",
            created_by="alice",
            updated_by="alice",
        )
        self.source_message = Message.objects.create(
            conversation=self.conversation,
            message_type=MessageType.LOG_SEARCH,
            status=ExecutionStatus.SUCCESS,
            task_id="message-task",
            input_data={"text": "query"},
            context_data={"prefix": "source"},
            output_data={"content": "source"},
            created_by="alice",
            updated_by="alice",
        )
        self.async_handler = EchoAttachmentAsyncHandler()
        attachment_handler_registry.register(self.async_handler)

    def tearDown(self):
        for attachment_type in AttachmentType.values:
            attachment_handler_registry.unregister(attachment_type)

    @mock.patch("services.web.ai_assistant.resources.attachment.get_request_username", return_value="alice")
    def test_create_async_dispatch_failure_returns_failed_response_without_task_id(self, _username):
        with mock.patch.object(self.async_handler.async_task, "apply_async", side_effect=RuntimeError("broker secret")):
            created = CreateAttachment().request(
                {
                    "message_uid": str(self.source_message.uid),
                    "attachment_type": AttachmentType.AI_ANALYSIS,
                    "input_data": {"text": "search"},
                }
            )

        self.assertEqual(created["status"], ExecutionStatus.FAILED)
        self.assertEqual(created["error_code"], "TASK_DISPATCH_FAILED")
        self.assertNotIn("task_id", created)
