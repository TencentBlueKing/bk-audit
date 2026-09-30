"""AI 会话 HTTP 入口的 Scope 权限边界回归。"""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import override_settings
from django.urls import resolve
from rest_framework.test import APIRequestFactory, force_authenticate

from core.exceptions import PermissionException
from services.web.ai_assistant.constants import (
    AttachmentType,
    ExecutionStatus,
    FeedbackSourceType,
    FeedbackType,
    MessageType,
    SidebarNodeType,
)
from services.web.ai_assistant.models import (
    Attachment,
    ConversationSidebarNode,
    Feedback,
    Message,
)
from services.web.ai_assistant.permissions import AIAssistantScopePermission
from services.web.ai_assistant.services import ConversationService
from services.web.common.scope_permission import ScopePermission
from tests.base import TestCase
from tests.test_ai_assistant.factories import (
    create_conversation,
    create_conversation_group,
)


@override_settings(ROOT_URLCONF="services.web.urls")
class AIAssistantScopePermissionTest(TestCase):
    class User:
        username = "alice"
        is_authenticated = True

    def setUp(self):
        super().setUp()
        self.username_patch = patch("services.web.ai_assistant.permissions.get_request_username", return_value="alice")
        self.username_patch.start()
        self.addCleanup(self.username_patch.stop)
        self.conversation = create_conversation(scope_type="scene", scope_id="2", created_by="alice")
        self.group = create_conversation_group(scope_type="system", scope_id="bk_audit", created_by="alice")
        self.message = Message.objects.create(
            conversation=self.conversation,
            message_type=MessageType.LOG_SEARCH,
            status=ExecutionStatus.SUCCESS,
            created_by="alice",
        )
        self.attachment = Attachment.objects.create(
            source_message=self.message,
            attachment_type=AttachmentType.AI_ANALYSIS,
            status=ExecutionStatus.SUCCESS,
            created_by="alice",
        )
        self.feedback = Feedback.objects.create(
            source_type=FeedbackSourceType.MESSAGE,
            source_id=self.message.id,
            feedback_type=FeedbackType.LIKE,
            created_by="alice",
        )
        self.node = ConversationSidebarNode.objects.create(
            conversation=self.conversation,
            node_type=SidebarNodeType.CONVERSATION,
            scope_type="scene",
            scope_id="2",
            created_by="alice",
        )

    def request(self, method, suffix, data=None, request_format="json"):
        """通过真实路由执行权限及 Resource 调用链。"""

        path = f"/api/v1/ai_assistant/{suffix}"
        request = getattr(APIRequestFactory(), method)(path, data or {}, format=request_format)
        force_authenticate(request, user=self.User())
        match = resolve(path.split("?", 1)[0])
        return match.func(request, **match.kwargs)

    def test_every_scoped_route_rejects_revoked_access(self):
        """所有对外 Scope 路由均必须在业务调用前拒绝失权用户。"""

        scope = {"scope_type": "scene", "scope_id": "2"}
        routes = [
            ("post", "conversation_groups/", scope),
            ("patch", f"conversation_groups/{self.group.uid}/", {}),
            ("delete", f"conversation_groups/{self.group.uid}/", {}),
            ("post", "conversations/", scope),
            ("get", "conversations/", scope),
            ("get", f"conversations/{self.conversation.uid}/", {}),
            ("patch", f"conversations/{self.conversation.uid}/", {}),
            ("delete", f"conversations/{self.conversation.uid}/", {}),
            ("post", "conversations/clear/", scope),
            ("post", "messages/", {"conversation_uid": str(self.conversation.uid)}),
            ("get", "messages/", {"conversation_uid": str(self.conversation.uid)}),
            ("get", f"messages/{self.message.uid}/", {}),
            ("patch", f"messages/{self.message.uid}/", {}),
            ("post", f"messages/{self.message.uid}/retry/", {}),
            ("post", f"messages/{self.message.uid}/attachments/", {}),
            ("get", f"messages/{self.message.uid}/preview-export/", {}),
            ("post", f"messages/{self.message.uid}/full-export/", {}),
            ("get", "attachments/", scope),
            ("get", f"attachments/{self.attachment.uid}/", {}),
            ("patch", f"attachments/{self.attachment.uid}/", {}),
            ("post", f"attachments/{self.attachment.uid}/retry/", {}),
            ("get", f"attachments/{self.attachment.uid}/export/", {}),
            ("get", f"attachments/{self.attachment.uid}/stream/snapshot/", {}),
            ("get", f"attachments/{self.attachment.uid}/stream/", {}),
            ("post", "feedback/", {"source_type": "MESSAGE", "source_uid": str(self.message.uid)}),
            ("post", "feedback/", {"source_type": "ATTACHMENT", "source_uid": str(self.attachment.uid)}),
            ("delete", f"feedback/{self.feedback.uid}/", {}),
            ("get", "conversation_sidebar/pinned/", scope),
            ("get", "conversation_sidebar/search/", scope),
            ("get", "conversation_sidebar/nodes/", scope),
            ("post", "conversation_sidebar/nodes/move/", scope),
            (
                "put",
                "conversation_sidebar/nodes/pin/",
                {"node_type": "CONVERSATION", "node_uid": str(self.conversation.uid)},
            ),
        ]
        denied = PermissionException(action_name="查看范围", apply_url="", permission={})
        with patch.object(ScopePermission, "check_scope_entry", side_effect=denied) as check_scope:
            for method, suffix, data in routes:
                with self.subTest(method=method, path=suffix):
                    check_scope.reset_mock()
                    self.assertEqual(self.request(method, suffix, data).status_code, 403)
                    check_scope.assert_called_once()
                    actual = check_scope.call_args.args[0]
                    expected = (
                        ("system", "bk_audit")
                        if suffix.startswith("conversation_groups/") and method != "post"
                        else ("scene", "2")
                    )
                    self.assertEqual((actual.scope_type, actual.scope_id), expected)

    def test_cross_queries_return_empty_without_entry_authorization(self):
        with (
            patch.object(ScopePermission, "check_scope_entry") as check_scope,
            patch.object(ScopePermission, "get_scene_ids", return_value=[]),
            patch.object(ScopePermission, "get_system_ids", return_value=[]),
            patch("services.web.ai_assistant.resources.conversation.get_request_username", return_value="alice"),
            patch("services.web.ai_assistant.resources.attachment.get_request_username", return_value="alice"),
        ):
            for scope_type in ("cross_scene", "cross_system"):
                for suffix in (
                    "attachments/",
                    "conversation_sidebar/pinned/",
                    "conversation_sidebar/search/",
                    "conversation_sidebar/nodes/",
                ):
                    with self.subTest(scope_type=scope_type, path=suffix):
                        response = self.request("get", suffix, {"scope_type": scope_type, "keyword": "hello"})
                        self.assertEqual(response.status_code, 200)
                        if suffix.endswith(("search/", "nodes/")):
                            self.assertEqual(response.data["total"], 0)
                            self.assertEqual(response.data["results"], [])
                        else:
                            self.assertEqual(response.data, [])
        check_scope.assert_not_called()

    def test_deleted_conversation_hides_all_dependent_uid_entries(self):
        type(self.conversation).objects.filter(pk=self.conversation.pk).update(is_deleted=True)
        routes = (
            ("get", f"messages/{self.message.uid}/", {}),
            ("get", f"attachments/{self.attachment.uid}/", {}),
            ("post", "feedback/", {"source_type": "MESSAGE", "source_uid": str(self.message.uid)}),
            ("delete", f"feedback/{self.feedback.uid}/", {}),
            (
                "put",
                "conversation_sidebar/nodes/pin/",
                {"node_type": "CONVERSATION", "node_uid": str(self.conversation.uid)},
            ),
        )
        with patch.object(ScopePermission, "check_scope_entry") as check_scope:
            for method, suffix, data in routes:
                with self.subTest(path=suffix):
                    self.assertEqual(self.request(method, suffix, data).status_code, 404)
        check_scope.assert_not_called()

    def test_path_uid_cannot_be_overridden_by_query(self):
        other = create_conversation(created_by="bob")
        with patch.object(ScopePermission, "check_scope_entry") as check_scope:
            response = self.request(
                "get", f"conversations/{other.uid}/", {"conversation_uid": str(self.conversation.uid)}
            )
        self.assertEqual(response.status_code, 404)
        check_scope.assert_not_called()

    def test_head_message_list_uses_get_route_query_and_authorizes_scope(self):
        denied = PermissionException(action_name="查看范围", apply_url="", permission={})
        with (
            patch("services.web.ai_assistant.resources.message.get_request_username", return_value="alice"),
            patch.object(ScopePermission, "check_scope_entry", side_effect=denied) as check_scope,
        ):
            response = self.request("head", f"messages/?conversation_uid={self.conversation.uid}")
        self.assertEqual(response.status_code, 403)
        check_scope.assert_called_once()

    def test_form_request_does_not_skip_scope_authorization(self):
        denied = PermissionException(action_name="查看范围", apply_url="", permission={})
        with (
            patch("services.web.ai_assistant.resources.conversation.get_request_username", return_value="alice"),
            patch.object(ScopePermission, "check_scope_entry", side_effect=denied) as check_scope,
        ):
            response = self.request(
                "post", "conversations/", {"scope_type": "scene", "scope_id": "2"}, request_format="multipart"
            )
        self.assertEqual(response.status_code, 403)
        check_scope.assert_called_once()

    def test_foreign_conversation_is_hidden_before_scope_check(self):
        other = create_conversation(created_by="bob")
        with patch.object(ScopePermission, "check_scope_entry") as check_scope:
            response = self.request("get", f"conversations/{other.uid}/")
        self.assertEqual(response.status_code, 404)
        check_scope.assert_not_called()

    def test_attachment_creation_preserves_invalid_source_error(self):
        other = create_conversation(created_by="bob")
        foreign_message = Message.objects.create(
            conversation=other, message_type=MessageType.LOG_SEARCH, status=ExecutionStatus.SUCCESS, created_by="bob"
        )
        with patch.object(ScopePermission, "check_scope_entry") as check_scope:
            response = self.request(
                "post",
                f"messages/{foreign_message.uid}/attachments/",
                {"attachment_type": "AI_ANALYSIS", "input_data": {"text": "hello"}},
            )
        self.assertEqual(response.status_code, 400)
        check_scope.assert_not_called()

    def test_authorized_detail_checks_scope_once(self):
        with (
            patch("services.web.ai_assistant.resources.conversation.get_request_username", return_value="alice"),
            patch.object(ScopePermission, "check_scope_entry") as check_scope,
        ):
            response = self.request("get", f"conversations/{self.conversation.uid}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["uid"], str(self.conversation.uid))
        self.assertEqual(check_scope.call_count, 1)

    def test_invalid_pin_type_stays_in_resource_validation(self):
        with patch.object(ScopePermission, "check_scope_entry") as check_scope:
            response = self.request(
                "put",
                "conversation_sidebar/nodes/pin/",
                {"node_type": "GROUP", "node_uid": str(self.group.uid), "is_pinned": True},
            )
        self.assertNotEqual(response.status_code, 200)
        self.assertNotEqual(response.status_code, 404)
        check_scope.assert_not_called()

    def test_scope_uses_serializer_normalization_and_body_precedence(self):
        with (
            patch("services.web.ai_assistant.resources.conversation.get_request_username", return_value="alice"),
            patch.object(ScopePermission, "check_scope_entry") as check_scope,
        ):
            response = self.request(
                "post",
                "conversations/?scope_type=scene&scope_id=1",
                {"scope_type": " system ", "scope_id": " bk_audit "},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["scope_id"], "bk_audit")
        self.assertEqual(check_scope.call_count, 1)
        self.assertEqual(
            (check_scope.call_args.args[0].scope_type, check_scope.call_args.args[0].scope_id), ("system", "bk_audit")
        )

    def test_integer_uuid_cannot_bypass_object_authorization(self):
        denied = PermissionException(action_name="查看范围", apply_url="", permission={})
        with patch.object(ScopePermission, "check_scope_entry", side_effect=denied) as check_scope:
            response = self.request("post", "messages/", {"conversation_uid": self.conversation.uid.int})
        self.assertEqual(response.status_code, 403)
        check_scope.assert_called_once()

    def test_options_preserves_metadata_endpoint(self):
        with patch.object(ScopePermission, "check_scope_entry") as check_scope:
            allowed = AIAssistantScopePermission().has_permission(
                SimpleNamespace(method="OPTIONS"), SimpleNamespace(action="metadata")
            )
        self.assertTrue(allowed)
        check_scope.assert_not_called()

    def test_create_conversation_denies_scope_before_business_service(self):
        """请求中的具体 Scope 失权时，不能进入会话创建逻辑。"""

        path = "/api/v1/ai_assistant/conversations/"
        request = APIRequestFactory().post(path, {"scope_type": "scene", "scope_id": "01"}, format="json")
        force_authenticate(request, user=self.User())
        denied = PermissionException(action_name="查看场景", apply_url="", permission={})

        with (
            patch.object(ScopePermission, "check_scope_entry", side_effect=denied),
            patch.object(ConversationService, "create_conversation") as create_conversation,
        ):
            response = resolve(path).func(request)

        self.assertEqual(response.status_code, 403)
        create_conversation.assert_not_called()

    def test_conversation_detail_uses_persisted_scope_before_business_service(self):
        """详情不接受调用方伪造的 Scope；本人失权时禁止进入领域读取。"""

        conversation = create_conversation(scope_type="system", scope_id="bk_audit", created_by="alice")
        path = f"/api/v1/ai_assistant/conversations/{conversation.uid}/"
        request = APIRequestFactory().get(path, {"scope_type": "scene", "scope_id": "1"})
        force_authenticate(request, user=self.User())
        denied = PermissionException(action_name="查看系统", apply_url="", permission={})

        with (
            patch("services.web.ai_assistant.permissions.get_request_username", return_value="alice"),
            patch.object(ScopePermission, "check_scope_entry", side_effect=denied) as check_scope,
            patch.object(ConversationService, "get_conversation") as get_conversation,
        ):
            response = resolve(path).func(request, conversation_uid=str(conversation.uid))

        self.assertEqual(response.status_code, 403)
        self.assertEqual(check_scope.call_args.args[0].scope_type, "system")
        self.assertEqual(check_scope.call_args.args[0].scope_id, "bk_audit")
        get_conversation.assert_not_called()
