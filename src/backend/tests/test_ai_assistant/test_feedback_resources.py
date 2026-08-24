import json
from unittest import mock
from uuid import uuid4

import yaml
from django.conf import settings
from django.test import override_settings
from django.urls import resolve
from drf_spectacular.views import SpectacularAPIView
from rest_framework.test import APIRequestFactory, force_authenticate

from services.web.ai_assistant.constants import (
    ExecutionStatus,
    FeedbackSourceType,
    FeedbackType,
    MessageType,
)
from services.web.ai_assistant.exceptions import FeedbackSourceNotFound
from services.web.ai_assistant.handlers import message_handler_registry
from services.web.ai_assistant.models import Conversation, Feedback, Message
from services.web.ai_assistant.resources.feedback import DeleteFeedback, UpsertFeedback
from services.web.ai_assistant.serializers.feedback import (
    FeedbackDeleteRequestSerializer,
    FeedbackResponseSerializer,
    FeedbackUpsertRequestSerializer,
)
from tests.base import TestCase
from tests.test_ai_assistant.handlers import FeedbackEchoSyncHandler, register_test_message_handler


class FeedbackRequestSerializerTest(TestCase):
    def test_upsert_serializer_validates_required_fields_and_comment_length(self):
        valid = FeedbackUpsertRequestSerializer(
            data={
                "source_type": FeedbackSourceType.MESSAGE,
                "source_uid": str(uuid4()),
                "feedback_type": FeedbackType.LIKE,
            }
        )
        self.assertTrue(valid.is_valid(), valid.errors)
        self.assertEqual(valid.validated_data["comment"], "")

        overlong_comment = FeedbackUpsertRequestSerializer(
            data={
                "source_type": FeedbackSourceType.MESSAGE,
                "source_uid": str(uuid4()),
                "feedback_type": FeedbackType.LIKE,
                "comment": "x" * (settings.AI_ASSISTANT_FEEDBACK_COMMENT_MAX_LENGTH + 1),
            }
        )
        self.assertFalse(overlong_comment.is_valid())
        self.assertIn("comment", overlong_comment.errors)

        for data in ({}, {"source_type": "INVALID", "source_uid": "invalid", "feedback_type": "NO"}):
            with self.subTest(data=data):
                self.assertFalse(FeedbackUpsertRequestSerializer(data=data).is_valid())
        self.assertFalse(FeedbackDeleteRequestSerializer(data={"feedback_uid": "invalid"}).is_valid())

    def test_all_feedback_api_fields_have_swagger_descriptions(self):
        for serializer_class in (
            FeedbackUpsertRequestSerializer,
            FeedbackDeleteRequestSerializer,
            FeedbackResponseSerializer,
        ):
            for field in serializer_class().fields.values():
                self.assertTrue(field.help_text)


@mock.patch("services.web.ai_assistant.resources.feedback.get_request_username", return_value="alice")
class FeedbackResourceTest(TestCase):
    def setUp(self):
        self.conversation = Conversation.objects.create(created_by="alice", updated_by="alice")
        self.message = Message.objects.create(
            conversation=self.conversation,
            message_type=MessageType.SYSTEM_SELECTION,
            status=ExecutionStatus.SUCCESS,
            input_data={"text": "feedback"},
            context_data={"prefix": "feedback"},
            output_data={"content": "feedback"},
            created_by="alice",
            updated_by="alice",
        )
        register_test_message_handler(FeedbackEchoSyncHandler())

    def tearDown(self):
        message_handler_registry.unregister(MessageType.SYSTEM_SELECTION)

    def test_post_overwrites_and_delete_removes_current_users_feedback(self, _username):
        request = {
            "source_type": FeedbackSourceType.MESSAGE,
            "source_uid": str(self.message.uid),
            "feedback_type": FeedbackType.LIKE,
            "comment": "有帮助",
        }
        created = UpsertFeedback().request(request)
        request.update(feedback_type=FeedbackType.DISLIKE, comment="不准确")
        overwritten = UpsertFeedback().request(request)

        self.assertEqual(created["uid"], overwritten["uid"])
        self.assertEqual(overwritten["source_uid"], str(self.message.uid))
        self.assertEqual(overwritten["feedback_type"], FeedbackType.DISLIKE)
        self.assertIsNone(DeleteFeedback().request({"feedback_uid": overwritten["uid"]}))
        self.assertFalse(Feedback.objects.exists())

    def test_cross_user_and_soft_deleted_sources_are_hidden(self, _username):
        foreign_conversation = Conversation.objects.create(created_by="bob", updated_by="bob")
        foreign_message = Message.objects.create(
            conversation=foreign_conversation,
            message_type=MessageType.SYSTEM_SELECTION,
            status=ExecutionStatus.SUCCESS,
            input_data={"text": "foreign"},
            context_data={"prefix": "foreign"},
            output_data={"content": "foreign"},
            created_by="bob",
            updated_by="bob",
        )
        deleted_conversation = Conversation.objects.create(created_by="alice", updated_by="alice", is_deleted=True)
        deleted_message = Message.objects.create(
            conversation=deleted_conversation,
            message_type=MessageType.SYSTEM_SELECTION,
            status=ExecutionStatus.SUCCESS,
            input_data={"text": "deleted"},
            context_data={"prefix": "deleted"},
            output_data={"content": "deleted"},
            created_by="alice",
            updated_by="alice",
        )
        foreign_feedback = Feedback.objects.create(
            source_type=FeedbackSourceType.MESSAGE,
            source_id=self.message.id,
            feedback_type=FeedbackType.LIKE,
            created_by="bob",
            updated_by="bob",
        )

        for message in (foreign_message, deleted_message):
            with self.subTest(message=message.uid), self.assertRaises(FeedbackSourceNotFound) as context:
                UpsertFeedback().request(
                    {
                        "source_type": FeedbackSourceType.MESSAGE,
                        "source_uid": str(message.uid),
                        "feedback_type": FeedbackType.LIKE,
                    }
                )
            self.assertEqual(context.exception.STATUS_CODE, 404)
        with self.assertRaises(FeedbackSourceNotFound) as context:
            DeleteFeedback().request({"feedback_uid": str(foreign_feedback.uid)})
        self.assertEqual(context.exception.STATUS_CODE, 404)


class FeedbackResourceRoutingTest(TestCase):
    class User:
        username = "alice"
        is_authenticated = True

    def test_feedback_routes_use_external_uid(self):
        feedback_uid = str(uuid4())
        self.assertEqual(resolve("/api/v1/ai_assistant/feedback/").url_name, "feedback-list")
        self.assertEqual(
            str(resolve(f"/api/v1/ai_assistant/feedback/{feedback_uid}/").kwargs["feedback_uid"]),
            feedback_uid,
        )

    @mock.patch("services.web.ai_assistant.resources.feedback.get_request_username", return_value="alice")
    def test_feedback_collection_accepts_post(self, _username):
        conversation = Conversation.objects.create(created_by="alice", updated_by="alice")
        message = Message.objects.create(
            conversation=conversation,
            message_type=MessageType.SYSTEM_SELECTION,
            status=ExecutionStatus.SUCCESS,
            input_data={"text": "feedback"},
            context_data={"prefix": "feedback"},
            output_data={"content": "feedback"},
            created_by="alice",
            updated_by="alice",
        )
        register_test_message_handler(FeedbackEchoSyncHandler())
        self.addCleanup(message_handler_registry.unregister, MessageType.SYSTEM_SELECTION)
        path = "/api/v1/ai_assistant/feedback/"
        request = APIRequestFactory().post(
            path,
            {
                "source_type": FeedbackSourceType.MESSAGE,
                "source_uid": str(message.uid),
                "feedback_type": FeedbackType.LIKE,
            },
            format="json",
        )
        force_authenticate(request, user=self.User())

        response = resolve(path).func(request)
        response.render()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["data"]["source_uid"], str(message.uid))

    @override_settings(ROOT_URLCONF="urls")
    def test_openapi_exposes_feedback_contract_and_resource_descriptions(self):
        request = APIRequestFactory().get("/api/schema/")
        request.user = mock.Mock(is_staff=True, is_authenticated=True)
        response = SpectacularAPIView.as_view()(request)
        response.render()
        schema = yaml.safe_load(response.content)

        feedback_operations = schema["paths"]["/api/v1/ai_assistant/feedback/"]
        self.assertIn("post", feedback_operations)
        self.assertNotIn("put", feedback_operations)
        feedback_path = feedback_operations["post"]
        delete_path = schema["paths"]["/api/v1/ai_assistant/feedback/{feedback_uid}/"]["delete"]
        self.assertEqual(feedback_path["description"], UpsertFeedback.__doc__)
        self.assertEqual(delete_path["description"], DeleteFeedback.__doc__)
        self.assertIn("requestBody", feedback_path)
        self.assertIn("200", feedback_path["responses"])
        self.assertNotIn("requestBody", delete_path)
        # BKResourceAutoSchema 对没有 ResponseSerializer 的 DELETE 一律生成 204/no body；这是平台既有契约。
        self.assertNotIn("200", delete_path["responses"])

    @mock.patch("services.web.ai_assistant.resources.feedback.get_request_username", return_value="alice")
    def test_delete_endpoint_uses_default_success_response_envelope(self, _username):
        feedback = Feedback.objects.create(
            source_type=FeedbackSourceType.MESSAGE,
            source_id=1,
            feedback_type=FeedbackType.LIKE,
            created_by="alice",
            updated_by="alice",
        )
        path = f"/api/v1/ai_assistant/feedback/{feedback.uid}/"
        view = resolve(path).func
        request = APIRequestFactory().delete(path)
        force_authenticate(request, user=self.User())

        response = view(request, feedback_uid=feedback.uid)
        response.render()
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["result"])
        self.assertEqual(payload["code"], 0)
        self.assertIsNone(payload["data"])
        self.assertIsNone(payload["message"])
