from unittest import mock
from uuid import UUID, uuid4

from bk_resource.exceptions import ValidateException
from django.db import connection
from django.test import SimpleTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import resolve
from drf_spectacular.openapi import AutoSchema
from drf_spectacular.plumbing import ComponentRegistry
from drf_spectacular.serializers import PolymorphicProxySerializerExtension
from drf_spectacular.utils import PolymorphicProxySerializer
from pydantic import ValidationError
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from core.sql.constants import FieldType
from services.web.ai_assistant.constants import (
    AttachmentType,
    ExecutionStatus,
    FeedbackSourceType,
    FeedbackType,
    MessageHistoryDirection,
    MessageType,
)
from services.web.ai_assistant.exceptions import (
    ConversationNotFound,
    InvalidMessageAnchor,
    InvalidMessageState,
    MessageNotFound,
    MessageSnapshotValidationError,
)
from services.web.ai_assistant.handlers import (
    attachment_handler_registry,
    message_handler_registry,
)
from services.web.ai_assistant.models import Attachment, Conversation, Feedback, Message
from services.web.ai_assistant.resources.message import (
    CreateMessage,
    GetMessage,
    ListMessages,
    RetryMessage,
    UpdateMessage,
)
from services.web.ai_assistant.schemas import MessageSchema
from services.web.ai_assistant.schemas.audit_search import (
    LogSearchInputSchema,
    UserIntentErrorSchema,
    UserIntentOutputSchema,
)
from services.web.ai_assistant.serializers.feedback import FeedbackResponseSerializer
from services.web.ai_assistant.serializers.message import (
    AttachmentSummarySerializer,
    InitialMessageRequestSerializer,
    MessageCreateRequestSerializer,
    MessageDetailRequestSerializer,
    MessageListRequestSerializer,
    MessageResponseSerializer,
    MessageUpdateRequestSerializer,
    MessageWindowResponseSerializer,
    _message_schema_mapping,
    _message_schema_models,
)
from services.web.ai_assistant.services.message import MessageService
from services.web.ai_assistant.services.message_execution import (
    finish_message_success,
    load_message_execution,
)
from services.web.query.utils.search_config import QueryConditionOperator
from tests.base import TestCase
from tests.test_ai_assistant.base import ensure_business_handlers_registered
from tests.test_ai_assistant.handlers import (
    EchoAsyncHandler,
    EchoAttachmentAsyncHandler,
    EchoInput,
    EchoOutput,
    EchoSyncHandler,
    FeedbackAttachmentEchoHandler,
    FeedbackEchoSyncHandler,
    register_test_message_handler,
)


class MessageRequestSerializerTest(TestCase):
    def setUp(self):
        self.conversation_uid = str(uuid4())
        self.message_uid = str(uuid4())

    def test_create_request_requires_typed_business_input(self):
        serializer = MessageCreateRequestSerializer(
            data={
                "conversation_uid": self.conversation_uid,
                "message_type": MessageType.SYSTEM_SELECTION,
                "input_data": {"text": "system-a"},
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["conversation_uid"], UUID(self.conversation_uid))

    def test_update_requires_complete_input_and_ignores_server_owned_fields(self):
        missing = MessageUpdateRequestSerializer(data={"message_uid": self.message_uid})
        self.assertFalse(missing.is_valid())
        serializer = MessageUpdateRequestSerializer(
            data={
                "message_uid": self.message_uid,
                "input_data": {"text": "edited"},
                "conversation_uid": self.conversation_uid,
                "parent_message_uid": str(uuid4()),
                "message_type": MessageType.LOG_SEARCH,
                "context_data": {"forged": True},
                "output_data": {"forged": True},
                "status": ExecutionStatus.SUCCESS,
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data,
            {
                "message_uid": UUID(self.message_uid),
                "input_data": {"text": "edited"},
            },
        )

    def test_create_request_rejects_missing_input_and_ignores_internal_fields(self):
        missing_input = MessageCreateRequestSerializer(
            data={
                "conversation_uid": self.conversation_uid,
                "message_type": MessageType.SYSTEM_SELECTION,
            }
        )
        internal_fields = MessageCreateRequestSerializer(
            data={
                "conversation_uid": self.conversation_uid,
                "message_type": MessageType.SYSTEM_SELECTION,
                "input_data": {"text": "system-a"},
                "status": ExecutionStatus.SUCCESS,
                "output_data": {"content": "forged"},
            }
        )

        self.assertFalse(missing_input.is_valid())
        self.assertTrue(internal_fields.is_valid(), internal_fields.errors)
        self.assertNotIn("status", internal_fields.validated_data)
        self.assertNotIn("output_data", internal_fields.validated_data)

    def test_history_anchor_and_direction_must_be_supplied_together(self):
        for data in (
            {"conversation_uid": self.conversation_uid, "anchor_uid": self.message_uid},
            {"conversation_uid": self.conversation_uid, "direction": MessageHistoryDirection.AFTER},
        ):
            with self.subTest(data=data):
                serializer = MessageListRequestSerializer(data=data)
                self.assertFalse(serializer.is_valid())

    def test_history_rejects_invalid_direction_and_limit(self):
        invalid_requests = (
            {"conversation_uid": self.conversation_uid, "limit": 0},
            {"conversation_uid": self.conversation_uid, "limit": 101},
            {
                "conversation_uid": self.conversation_uid,
                "anchor_uid": self.message_uid,
                "direction": "INVALID",
            },
        )

        for data in invalid_requests:
            with self.subTest(data=data):
                serializer = MessageListRequestSerializer(data=data)
                self.assertFalse(serializer.is_valid())

    def test_post_messages_rejects_retired_natural_language_search(self):
        """POST /messages/ 不再接受旧自然语言检索类型，USER_INTENT 仍是自然语言入口。"""

        with self.assertRaises(ValidateException):
            CreateMessage().request(
                {
                    "conversation_uid": self.conversation_uid,
                    "message_type": "NATURAL_LANGUAGE_SEARCH",
                    "input_data": {"query_text": "查一下最近一天的日志"},
                }
            )

        available = MessageCreateRequestSerializer(
            data={
                "conversation_uid": self.conversation_uid,
                "message_type": MessageType.USER_INTENT,
                "input_data": {"query_text": "查一下最近一天的日志", "scope_type": "cross_system"},
            }
        )
        self.assertTrue(available.is_valid(), available.errors)
        self.assertEqual(available.validated_data["message_type"], MessageType.USER_INTENT)

    def test_initial_message_only_accepts_system_selection(self):
        valid = InitialMessageRequestSerializer(
            data={"message_type": MessageType.SYSTEM_SELECTION, "input_data": {"systems": ["a"]}}
        )
        invalid = InitialMessageRequestSerializer(
            data={"message_type": MessageType.LOG_SEARCH, "input_data": {"query": {}}}
        )

        self.assertTrue(valid.is_valid(), valid.errors)
        self.assertFalse(invalid.is_valid())

    def test_all_message_api_fields_have_swagger_descriptions(self):
        serializer_classes = (
            AttachmentSummarySerializer,
            InitialMessageRequestSerializer,
            MessageCreateRequestSerializer,
            MessageDetailRequestSerializer,
            MessageListRequestSerializer,
            MessageResponseSerializer,
            MessageWindowResponseSerializer,
            FeedbackResponseSerializer,
        )

        for serializer_class in serializer_classes:
            for field_name, field in serializer_class().fields.items():
                with self.subTest(serializer=serializer_class.__name__, field=field_name):
                    self.assertTrue(field.help_text)

    def test_user_intent_business_error_contract_is_documented_for_frontend(self):
        """Swagger 描述稳定业务错误码，并区分 SUCCESS 业务错误与 FAILED 技术错误。"""

        error_schema = UserIntentErrorSchema.model_json_schema()
        error_properties = error_schema["properties"]
        self.assertIn("SYSTEM_UNAVAILABLE", error_properties["error_code"]["description"])
        self.assertIn("直接展示", error_properties["error_message"]["description"])
        self.assertIn("SYSTEM_UNAVAILABLE", error_properties["candidates"]["description"])
        for field_name, field in UserIntentErrorSchema.drf_serializer().fields.items():
            with self.subTest(field=field_name):
                self.assertTrue(field.help_text)

        response_fields = MessageResponseSerializer().fields
        self.assertIn("output_data.error", str(response_fields["output_data"].help_text))
        self.assertIn("FAILED", str(response_fields["error_code"].help_text))

        output_schema = UserIntentOutputSchema.model_json_schema()
        summary_ref = output_schema["properties"]["derived_messages"]["items"]["$ref"]
        summary_schema = output_schema["$defs"][summary_ref.rsplit("/", 1)[-1]]
        self.assertEqual(
            set(summary_schema["properties"]),
            {"message_uid", "message_type", "status", "visible"},
        )
        self.assertIn("计划顺序", output_schema["properties"]["derived_messages"]["description"])
        self.assertIn("复合计划", str(response_fields["visible"].help_text))

    def test_swagger_snapshot_schema_mapping_uses_registered_handler_models(self):
        # 保存常驻业务 Handler，测试结束后恢复，避免污染全局单例影响后续测试。
        saved_sync = message_handler_registry.handlers.get(MessageType.SYSTEM_SELECTION)
        saved_async = message_handler_registry.handlers.get(MessageType.USER_INTENT)
        sync_handler = EchoSyncHandler()
        async_handler = EchoAsyncHandler()
        register_test_message_handler(sync_handler)
        register_test_message_handler(async_handler)
        try:
            input_schemas = _message_schema_mapping("input_model")
            output_schemas = _message_schema_mapping("output_model")
        finally:
            message_handler_registry.unregister(MessageType.SYSTEM_SELECTION)
            message_handler_registry.unregister(MessageType.USER_INTENT)
            if saved_sync is not None:
                message_handler_registry.register(saved_sync)
            if saved_async is not None:
                message_handler_registry.register(saved_async)

        self.assertIs(input_schemas[MessageType.SYSTEM_SELECTION], EchoInput)
        self.assertIs(input_schemas[MessageType.USER_INTENT], EchoInput)
        self.assertIs(output_schemas[MessageType.SYSTEM_SELECTION], EchoOutput)
        self.assertIs(output_schemas[MessageType.USER_INTENT], EchoOutput)


class StartupAlphaMessageInput(MessageSchema):
    alpha: str


class StartupAlphaMessageOutput(MessageSchema):
    content: str


class StartupBetaMessageInput(MessageSchema):
    beta: str


class StartupBetaMessageOutput(MessageSchema):
    content: str


class StartupGammaMessageInput(MessageSchema):
    gamma: str


class StartupGammaMessageOutput(MessageSchema):
    content: str


class StartupAlphaMessageHandler(EchoSyncHandler):
    input_model = StartupAlphaMessageInput
    output_model = StartupAlphaMessageOutput

    def execute(self, *, input_data, context_data):
        return StartupAlphaMessageOutput(content=input_data.alpha)


class StartupBetaMessageHandler(EchoSyncHandler):
    message_type = MessageType.USER_INTENT
    input_model = StartupBetaMessageInput
    output_model = StartupBetaMessageOutput

    def execute(self, *, input_data, context_data):
        return StartupBetaMessageOutput(content=input_data.beta)


class StartupGammaMessageHandler(EchoSyncHandler):
    message_type = MessageType.LOG_SEARCH
    input_model = StartupGammaMessageInput
    output_model = StartupGammaMessageOutput

    def execute(self, *, input_data, context_data):
        return StartupGammaMessageOutput(content=input_data.gamma)


def _component_schema(registry: ComponentRegistry, name: str) -> dict:
    for key, component in registry._components.items():
        component_name = key[0] if isinstance(key, tuple) else getattr(component, "name", None)
        if component_name == name:
            return component.schema
    raise AssertionError(f"OpenAPI 组件不存在: {name}")


def _resolve_schema_refs(node, registry: ComponentRegistry):
    if isinstance(node, list):
        return [_resolve_schema_refs(item, registry) for item in node]
    if not isinstance(node, dict):
        return node
    if set(node) == {"$ref"}:
        name = node["$ref"].rsplit("/", 1)[-1]
        return _resolve_schema_refs(_component_schema(registry, name), registry)
    return {key: _resolve_schema_refs(value, registry) for key, value in node.items()}


def _map_message_serializer(serializer_class) -> dict:
    view = APIView()
    view.request = Request(APIRequestFactory().post("/"))
    view.format_kwarg = None
    auto_schema = AutoSchema()
    auto_schema.view = view
    auto_schema.method = "POST"
    auto_schema.path = "/"
    auto_schema.registry = ComponentRegistry()
    schema = auto_schema._map_serializer(serializer_class(), "request")
    return _resolve_schema_refs(schema, auto_schema.registry)


def _map_polymorphic_proxy_oneof(proxy: PolymorphicProxySerializer) -> dict:
    view = APIView()
    view.request = Request(APIRequestFactory().get("/"))
    view.format_kwarg = None
    auto_schema = AutoSchema()
    auto_schema.view = view
    auto_schema.method = "GET"
    auto_schema.path = "/"
    auto_schema.registry = ComponentRegistry()
    return PolymorphicProxySerializerExtension(target=proxy).map_serializer(auto_schema, "response")


class LogSearchConditionOpenAPITest(SimpleTestCase):
    def test_log_search_input_exposes_nested_condition_and_operator_choices(self):
        """LOG_SEARCH 输入在 OpenAPI 中展开条件字段，并列出全局操作符与字段类型。"""

        schema = _map_message_serializer(LogSearchInputSchema.drf_serializer)
        condition = schema["properties"]["condition"]
        self.assertEqual(
            set(condition["properties"]),
            {"scope_type", "scope_id", "start_time", "end_time", "conditions"},
        )
        item = condition["properties"]["conditions"]["items"]
        self.assertEqual(
            set(item["properties"]["operator"]["enum"]),
            {choice[0] for choice in QueryConditionOperator.choices},
        )
        field = item["properties"]["field"]["properties"]
        self.assertEqual(set(field), {"raw_name", "field_type", "keys"})
        self.assertEqual(set(field["field_type"]["enum"]), {choice[0] for choice in FieldType.choices})
        documented = str(schema)
        self.assertIn("allow_operators", documented)
        self.assertIn("isnull", documented)
        self.assertIn("between", documented)

    def test_log_search_input_precheck_keeps_filter_shape(self):
        """运行时仍按 Pydantic 校验 filters 形态，OpenAPI 枚举不替代字段白名单。"""

        payload = {
            "condition": {
                "scope_type": "system",
                "scope_id": "bk-audit",
                "start_time": "2026-09-22T00:00:00+08:00",
                "end_time": "2026-09-23T00:00:00+08:00",
                "conditions": [
                    {
                        "field": {"raw_name": "username", "field_type": "string", "keys": []},
                        "operator": "eq",
                        "filters": ["admin"],
                    },
                    {
                        "field": {"raw_name": "extend_data", "field_type": "string", "keys": ["ticket_id"]},
                        "operator": "eq",
                        "filters": ["Story-1"],
                    },
                    {
                        "field": {"raw_name": "username", "field_type": "string", "keys": []},
                        "operator": "isnull",
                        "filters": [],
                    },
                ],
            }
        }
        parsed = LogSearchInputSchema.model_validate(payload)
        self.assertEqual(parsed.condition.conditions[1].field.keys, ["ticket_id"])
        self.assertEqual(parsed.condition.conditions[2].filters, [])

        payload["condition"]["conditions"][2]["filters"] = ["admin"]
        with self.assertRaises(ValidationError):
            LogSearchInputSchema.model_validate(payload)
        payload["condition"]["conditions"][2] = {
            "field": {"raw_name": "username", "field_type": "string", "keys": []},
            "operator": "between",
            "filters": ["only-one"],
        }
        with self.assertRaises(ValidationError):
            LogSearchInputSchema.model_validate(payload)


class MessageOpenAPIStartupContractTest(SimpleTestCase):
    def setUp(self):
        # 业务 Handler（audit_search）常驻注册表后，本测试需要三种消息类型空闲：
        # 先卸载保存、结束后原样恢复，避免依赖收集顺序破坏全局单例。
        self._saved_handlers = {
            message_type: message_handler_registry.unregister(message_type)
            for message_type in (
                MessageType.SYSTEM_SELECTION,
                MessageType.USER_INTENT,
                MessageType.LOG_SEARCH,
            )
        }

    def tearDown(self):
        # 清除测试注册的替身，并恢复常驻业务 Handler。
        for message_type, handler in self._saved_handlers.items():
            message_handler_registry.unregister(message_type)
            if handler is not None:
                message_handler_registry.register(handler)

    def test_first_openapi_generation_includes_registered_handlers_and_freezes(self):
        message_handler_registry.register(StartupAlphaMessageHandler())
        message_handler_registry.register(StartupBetaMessageHandler())
        input_proxy = PolymorphicProxySerializer(
            component_name="AIMessageInputDataStartupGate",
            serializers=lambda: _message_schema_models("input_model"),
            resource_type_field_name=None,
        )
        output_proxy = PolymorphicProxySerializer(
            component_name="AIMessageOutputDataStartupGate",
            serializers=lambda: _message_schema_models("output_model"),
            resource_type_field_name=None,
        )

        input_schema = _map_polymorphic_proxy_oneof(input_proxy)
        output_schema = _map_polymorphic_proxy_oneof(output_proxy)
        input_refs = {item["$ref"] for item in input_schema["oneOf"]}
        output_refs = {item["$ref"] for item in output_schema["oneOf"]}

        self.assertIn("#/components/schemas/StartupAlphaMessageInput", input_refs)
        self.assertIn("#/components/schemas/StartupBetaMessageInput", input_refs)
        self.assertIn("#/components/schemas/StartupAlphaMessageOutput", output_refs)
        self.assertIn("#/components/schemas/StartupBetaMessageOutput", output_refs)
        self.assertNotIn("discriminator", input_schema)
        self.assertNotIn("discriminator", output_schema)

        frozen_input = input_proxy.serializers
        frozen_output = output_proxy.serializers
        message_handler_registry.register(StartupGammaMessageHandler())

        self.assertIs(input_proxy.serializers, frozen_input)
        self.assertIs(output_proxy.serializers, frozen_output)
        self.assertNotIn(StartupGammaMessageInput, frozen_input)
        self.assertNotIn(StartupGammaMessageOutput, frozen_output)
        refreshed_input_refs = {item["$ref"] for item in _map_polymorphic_proxy_oneof(input_proxy)["oneOf"]}
        self.assertNotIn("#/components/schemas/StartupGammaMessageInput", refreshed_input_refs)

    def test_openapi_deduplicates_unregistered_message_fallback_schema(self):
        proxy = PolymorphicProxySerializer(
            component_name="AIMessageInputDataFallbackGate",
            serializers=lambda: _message_schema_models("input_model"),
            resource_type_field_name=None,
        )

        schema = _map_polymorphic_proxy_oneof(proxy)

        self.assertEqual(
            [item["$ref"] for item in schema["oneOf"]],
            ["#/components/schemas/MessageSchema"],
        )

    def test_openapi_deduplicates_schema_shared_by_multiple_handlers(self):
        message_handler_registry.register(EchoSyncHandler())
        message_handler_registry.register(EchoAsyncHandler())
        proxy = PolymorphicProxySerializer(
            component_name="AIMessageInputDataSharedModelGate",
            serializers=lambda: _message_schema_models("input_model"),
            resource_type_field_name=None,
        )

        schema = _map_polymorphic_proxy_oneof(proxy)

        self.assertEqual(
            [item["$ref"] for item in schema["oneOf"]],
            [
                "#/components/schemas/EchoInput",
                "#/components/schemas/MessageSchema",
            ],
        )


@mock.patch("services.web.ai_assistant.resources.message.get_request_username", return_value="alice")
class MessageResourceTest(TestCase):
    def setUp(self):
        self.conversation = Conversation.objects.create(created_by="alice", updated_by="alice")
        self.sync_handler = FeedbackEchoSyncHandler()
        self.async_handler = EchoAsyncHandler()
        self.attachment_handler = FeedbackAttachmentEchoHandler()
        self.async_attachment_handler = EchoAttachmentAsyncHandler()
        register_test_message_handler(self.sync_handler)
        register_test_message_handler(self.async_handler)
        attachment_handler_registry.register(self.attachment_handler)
        attachment_handler_registry.register(self.async_attachment_handler)

    def tearDown(self):
        message_handler_registry.unregister(MessageType.SYSTEM_SELECTION)
        message_handler_registry.unregister(MessageType.USER_INTENT)
        ensure_business_handlers_registered()
        attachment_handler_registry.unregister(AttachmentType.FIELD_STATISTICS)
        attachment_handler_registry.unregister(AttachmentType.AI_ANALYSIS)

    def test_update_message_returns_replaced_content_with_existing_feedback_and_attachment(self, _username):
        message = MessageService(user="alice").create(
            conversation=self.conversation,
            message_type=MessageType.SYSTEM_SELECTION,
            input_data={"text": "old"},
        )
        # 全异步化：create 返回 PROCESSING，编辑前置收敛为成功终态（模拟任务完成）
        Message.objects.filter(pk=message.pk).update(
            status=ExecutionStatus.SUCCESS, output_data={"content": "system:old"}
        )
        Attachment.objects.create(
            source_message=message,
            attachment_type=AttachmentType.FIELD_STATISTICS,
            status=ExecutionStatus.SUCCESS,
            created_by="alice",
            updated_by="alice",
        )
        Feedback.objects.create(
            source_type=FeedbackSourceType.MESSAGE,
            source_id=message.id,
            feedback_type=FeedbackType.LIKE,
            created_by="alice",
            updated_by="alice",
        )
        before = GetMessage().request({"message_uid": str(message.uid)})

        response = UpdateMessage().request({"message_uid": str(message.uid), "input_data": {"text": "new"}})

        self.assertEqual(response["uid"], before["uid"])
        self.assertEqual(response["input_data"], {"text": "new"})
        self.assertEqual(response["output_data"], {"content": "system:new"})
        self.assertEqual(response["status"], ExecutionStatus.SUCCESS)
        self.assertEqual(response["attachments"], before["attachments"])
        self.assertEqual(response["feedback"], before["feedback"])
        self.assertNotIn("context_data", response)
        self.assertNotIn("task_id", response)
        self.assertEqual(GetMessage().request({"message_uid": str(message.uid)}), response)
        self.assertEqual(Message.objects.count(), 1)

    def test_update_resource_rejects_invalid_typed_input(self, _username):
        message = MessageService(user="alice").create(
            conversation=self.conversation,
            message_type=MessageType.SYSTEM_SELECTION,
            input_data={"text": "old"},
        )
        # 全异步化：create 返回 PROCESSING，编辑前置收敛为成功终态（模拟任务完成）
        Message.objects.filter(pk=message.pk).update(status=ExecutionStatus.SUCCESS)
        with self.assertRaises(MessageSnapshotValidationError):
            UpdateMessage().request({"message_uid": str(message.uid), "input_data": {"unknown": "new"}})
        message.refresh_from_db()
        self.assertEqual(message.input_data, {"text": "old"})

    def test_update_async_resource_returns_processing_for_original_uid(self, _username):
        message = Message.objects.create(
            conversation=self.conversation,
            message_type=MessageType.USER_INTENT,
            status=ExecutionStatus.SUCCESS,
            input_data={"text": "old"},
            output_data={"content": "old"},
            created_by="alice",
            updated_by="alice",
        )
        with mock.patch.object(self.async_handler.async_task, "apply_async"):
            with self.captureOnCommitCallbacks(execute=True):
                response = UpdateMessage().request({"message_uid": str(message.uid), "input_data": {"text": "new"}})
        self.assertEqual(response["uid"], str(message.uid))
        self.assertEqual(response["status"], ExecutionStatus.PROCESSING)
        self.assertEqual(response["input_data"], {"text": "new"})
        self.assertIsNone(response["output_data"])

    def test_create_sync_message_returns_success_without_internal_fields(self, _username):
        """同步 Handler 创建即返回 SUCCESS，接口不暴露内部执行字段。"""

        response = CreateMessage().request(
            {
                "conversation_uid": str(self.conversation.uid),
                "message_type": MessageType.SYSTEM_SELECTION,
                "input_data": {"text": "system-a"},
            }
        )

        self.assertEqual(response["status"], ExecutionStatus.SUCCESS)
        self.assertEqual(response["input_data"], {"text": "system-a"})
        self.assertNotIn("context_data", response)
        self.assertEqual(response["output_data"], {"content": "system:system-a"})
        self.assertIsNone(response["parent_message_uid"])
        self.assertEqual(response["attachments"], [])
        for internal_field in ("id", "task_id", "stream_config", "stream_archive"):
            self.assertNotIn(internal_field, response)

    def test_create_async_message_returns_processing_and_detail_observes_success(self, _username):
        with mock.patch.object(self.async_handler.async_task, "apply_async"):
            with self.captureOnCommitCallbacks(execute=True):
                created = CreateMessage().request(
                    {
                        "conversation_uid": str(self.conversation.uid),
                        "message_type": MessageType.USER_INTENT,
                        "input_data": {"text": "search"},
                    }
                )
        self.assertEqual(created["status"], ExecutionStatus.PROCESSING)
        self.assertIsNone(created["output_data"])

        message = Message.objects.get(uid=created["uid"])
        execution = load_message_execution(
            message_id=message.id,
            task_id=message.task_id,
            celery_task_id=message.task_id,
        )
        finish_message_success(
            execution=execution,
            task_id=message.task_id,
            output_data={"content": "async:search"},
        )

        detail = GetMessage().request({"message_uid": created["uid"]})
        self.assertEqual(detail["status"], ExecutionStatus.SUCCESS)
        self.assertEqual(detail["output_data"], {"content": "async:search"})

    def test_parent_message_uid_is_preserved(self, _username):
        parent = CreateMessage().request(
            {
                "conversation_uid": str(self.conversation.uid),
                "message_type": MessageType.SYSTEM_SELECTION,
                "input_data": {"text": "parent"},
            }
        )

        child = CreateMessage().request(
            {
                "conversation_uid": str(self.conversation.uid),
                "message_type": MessageType.SYSTEM_SELECTION,
                "parent_message_uid": parent["uid"],
                "input_data": {"text": "child"},
            }
        )

        self.assertEqual(child["parent_message_uid"], parent["uid"])

    def test_list_can_hide_content_but_keeps_status_and_attachment_summary(self, _username):
        created = CreateMessage().request(
            {
                "conversation_uid": str(self.conversation.uid),
                "message_type": MessageType.SYSTEM_SELECTION,
                "input_data": {"text": "system-a"},
            }
        )
        message = Message.objects.get(uid=created["uid"])
        attachment = Attachment.objects.create(
            source_message=message,
            attachment_type=AttachmentType.AI_ANALYSIS,
            title="风险分析",
            status=ExecutionStatus.PROCESSING,
            input_data={},
            context_data={},
            output_data=None,
            created_by="alice",
            updated_by="alice",
        )
        latest_attachment = Attachment.objects.create(
            source_message=message,
            attachment_type=AttachmentType.FIELD_STATISTICS,
            title="字段统计",
            status=ExecutionStatus.SUCCESS,
            input_data={},
            context_data={},
            output_data={"count": 1},
            created_by="alice",
            updated_by="alice",
        )

        window = ListMessages().request({"conversation_uid": str(self.conversation.uid), "include_content": False})

        self.assertEqual(window["first_uid"], created["uid"])
        self.assertEqual(window["last_uid"], created["uid"])
        item = window["results"][0]
        self.assertEqual(item["status"], ExecutionStatus.SUCCESS)
        self.assertNotIn("input_data", item)
        self.assertNotIn("context_data", item)
        self.assertNotIn("output_data", item)
        self.assertEqual(
            set(item["attachments"][0]),
            {
                "uid",
                "attachment_type",
                "status",
                "title",
                "content_updated_at",
                "created_at",
                "supports_feedback",
                "export_formats",
            },
        )
        self.assertEqual(item["attachments"][0]["export_formats"], [])
        self.assertEqual(
            [summary["uid"] for summary in item["attachments"]],
            [str(latest_attachment.uid), str(attachment.uid)],
        )

        detail = GetMessage().request({"message_uid": created["uid"]})
        self.assertEqual(detail["input_data"], {"text": "system-a"})
        self.assertNotIn("context_data", detail)

    def test_message_response_exposes_current_feedback_and_list_uses_one_feedback_query(self, _username):
        messages = [
            Message.objects.create(
                conversation=self.conversation,
                message_type=MessageType.SYSTEM_SELECTION,
                status=ExecutionStatus.SUCCESS,
                input_data={"text": f"message-{index}"},
                context_data={"prefix": "system"},
                output_data={"content": f"system:message-{index}"},
                created_by="alice",
                updated_by="alice",
            )
            for index in range(20)
        ]
        Feedback.objects.create(
            source_type=FeedbackSourceType.MESSAGE,
            source_id=messages[0].id,
            feedback_type=FeedbackType.LIKE,
            comment="有帮助",
            created_by="alice",
            updated_by="alice",
        )

        with CaptureQueriesContext(connection) as queries:
            window = MessageService(user="alice").list(
                conversation_uid=str(self.conversation.uid),
                limit=20,
                include_content=False,
            )
            response = MessageWindowResponseSerializer(window).data

        feedback_selects = [
            query["sql"]
            for query in queries.captured_queries
            if "ai_assistant_feedback" in query["sql"].lower() and query["sql"].lstrip().upper().startswith("SELECT")
        ]
        self.assertEqual(len(feedback_selects), 1)
        self.assertTrue(response["results"][0]["supports_feedback"])
        self.assertEqual(response["results"][0]["feedback"]["source_uid"], str(messages[0].uid))
        self.assertNotIn(
            "feedback", response["results"][0]["attachments"][0] if response["results"][0]["attachments"] else {}
        )

    def test_list_after_anchor_discovers_new_messages(self, _username):
        first = CreateMessage().request(
            {
                "conversation_uid": str(self.conversation.uid),
                "message_type": MessageType.SYSTEM_SELECTION,
                "input_data": {"text": "first"},
            }
        )
        second = CreateMessage().request(
            {
                "conversation_uid": str(self.conversation.uid),
                "message_type": MessageType.SYSTEM_SELECTION,
                "input_data": {"text": "second"},
            }
        )

        window = ListMessages().request(
            {
                "conversation_uid": str(self.conversation.uid),
                "anchor_uid": first["uid"],
                "direction": MessageHistoryDirection.AFTER,
            }
        )

        self.assertEqual([item["uid"] for item in window["results"]], [second["uid"]])

    def test_cross_user_resources_are_hidden(self, _username):
        foreign_conversation = Conversation.objects.create(created_by="bob", updated_by="bob")
        foreign_message = Message.objects.create(
            conversation=foreign_conversation,
            message_type=MessageType.SYSTEM_SELECTION,
            status=ExecutionStatus.SUCCESS,
            input_data={"text": "foreign"},
            context_data={"prefix": "system"},
            output_data={"content": "system:foreign"},
            created_by="bob",
            updated_by="bob",
        )

        with self.assertRaises(ConversationNotFound):
            CreateMessage().request(
                {
                    "conversation_uid": str(foreign_conversation.uid),
                    "message_type": MessageType.SYSTEM_SELECTION,
                    "input_data": {"text": "forbidden"},
                }
            )
        with self.assertRaises(MessageNotFound):
            GetMessage().request({"message_uid": str(foreign_message.uid)})
        with self.assertRaises(InvalidMessageAnchor):
            ListMessages().request(
                {
                    "conversation_uid": str(self.conversation.uid),
                    "anchor_uid": str(foreign_message.uid),
                    "direction": MessageHistoryDirection.AFTER,
                }
            )

    def test_corrupted_database_snapshot_is_rejected_on_read(self, _username):
        message = Message.objects.create(
            conversation=self.conversation,
            message_type=MessageType.SYSTEM_SELECTION,
            status=ExecutionStatus.SUCCESS,
            input_data={"invalid": True},
            context_data={"prefix": "system"},
            output_data={"content": "system:value"},
            created_by="alice",
            updated_by="alice",
        )

        with self.assertRaises(MessageSnapshotValidationError):
            GetMessage().request({"message_uid": str(message.uid)})

    def create_failed_async_message(self, **overrides):
        values = {
            "conversation": self.conversation,
            "message_type": MessageType.USER_INTENT,
            "status": ExecutionStatus.FAILED,
            "task_id": "task-old",
            "input_data": {"text": "search"},
            "context_data": {"prefix": "async"},
            "output_data": {"content": "old"},
            "error_code": "OLD_ERROR",
            "error_message": "旧错误",
            "created_by": "alice",
            "updated_by": "alice",
        }
        values.update(overrides)
        return Message.objects.create(**values)

    def test_retry_message_returns_original_uid_processing_dto(self, _username):
        message = self.create_failed_async_message()

        with mock.patch.object(self.async_handler.async_task, "apply_async"):
            with self.captureOnCommitCallbacks(execute=True):
                response = RetryMessage().request({"message_uid": str(message.uid)})

        self.assertEqual(response["uid"], str(message.uid))
        self.assertEqual(response["status"], ExecutionStatus.PROCESSING)
        self.assertEqual(response["input_data"], {"text": "search"})
        self.assertIsNone(response["output_data"])
        self.assertNotIn("context_data", response)
        self.assertNotIn("task_id", response)

    def test_retry_message_rejects_invalid_state(self, _username):
        message = self.create_failed_async_message(
            status=ExecutionStatus.PROCESSING,
            task_id="task-processing",
        )

        with self.assertRaises(InvalidMessageState):
            RetryMessage().request({"message_uid": str(message.uid)})

    def test_retry_message_hides_foreign_and_deleted_conversation(self, _username):
        foreign_conversation = Conversation.objects.create(created_by="bob", updated_by="bob")
        foreign = self.create_failed_async_message(
            conversation=foreign_conversation,
            created_by="bob",
            updated_by="bob",
        )
        deleted = self.create_failed_async_message(task_id="task-deleted")
        self.conversation.delete()

        for message in (foreign, deleted):
            with self.subTest(message=message.uid), self.assertRaises(MessageNotFound):
                RetryMessage().request({"message_uid": str(message.uid)})


@override_settings(ROOT_URLCONF="services.web.urls")
class MessageResourceRoutingTest(TestCase):
    def test_message_routes_use_external_uid(self):
        message_uid = str(uuid4())

        self.assertEqual(resolve("/api/v1/ai_assistant/messages/").url_name, "messages-list")
        nested_attachment_match = resolve(f"/api/v1/ai_assistant/messages/{message_uid}/attachments/")
        self.assertEqual(nested_attachment_match.kwargs, {"message_uid": message_uid})
        detail_match = resolve(f"/api/v1/ai_assistant/messages/{message_uid}/")
        self.assertEqual(detail_match.kwargs, {"message_uid": message_uid})
        retry_match = resolve(f"/api/v1/ai_assistant/messages/{message_uid}/retry/")
        self.assertEqual(retry_match.kwargs, {"message_uid": message_uid})
