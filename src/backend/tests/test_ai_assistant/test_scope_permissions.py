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
from tests.test_ai_assistant.base import make_condition
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
        self.group_node = ConversationSidebarNode.objects.create(
            group=self.group,
            node_type=SidebarNodeType.GROUP,
            scope_type=self.group.scope_type,
            scope_id=self.group.scope_id,
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
            (
                "post",
                "conversation_sidebar/nodes/move/",
                {"source_node_type": "CONVERSATION", "source_node_uid": str(self.conversation.uid)},
            ),
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

    def test_invalid_scope_creation_is_a_client_error(self):
        """写请求的非法范围及缺参由公共异常处理返回 400。"""
        for data in (
            {"scope_type": "cross_system", "scope_id": "ignored"},
            {"scope_type": "unknown"},
            {"scope_type": "scene", "scope_id": "invalid-id"},
            {},
        ):
            with self.subTest(data=data), patch.object(ConversationService, "create_conversation") as create:
                response = self.request("post", "conversations/", data)
                self.assertEqual(response.status_code, 400)
                create.assert_not_called()

    def test_attachment_list_derives_scope_from_resource_uid(self):
        """按消息或会话查附件无需重复传 Scope，仍只返回本人附件。"""
        with (
            patch.object(ScopePermission, "check_scope_entry") as check,
            patch("services.web.ai_assistant.resources.attachment.get_request_username", return_value="alice"),
        ):
            for query in (
                {"source_message_uid": str(self.message.uid), "sort": "-created_at"},
                {"conversation_uid": str(self.conversation.uid)},
                {"source_message_uid": str(self.message.uid), "conversation_uid": str(self.conversation.uid)},
                {"source_message_uid": str(self.message.uid), "scope_type": "system", "scope_id": "forged"},
            ):
                with self.subTest(query=query):
                    check.reset_mock()
                    response = self.request("get", "attachments/", query)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual([item["uid"] for item in response.data], [str(self.attachment.uid)])
                    check.assert_called_once()
                    scope = check.call_args.args[0]
                    self.assertEqual((scope.scope_type, scope.scope_id), ("scene", "2"))

    def test_concrete_collection_authorizes_once_and_filters_requested_scope(self):
        """入口鉴权一次，列表按具体范围过滤，不再次枚举权限。"""
        with (
            patch.object(ScopePermission, "check_scope_entry") as check,
            patch.object(ScopePermission, "get_scene_ids") as scene_ids,
            patch.object(ScopePermission, "get_system_ids") as system_ids,
            patch("services.web.ai_assistant.resources.attachment.get_request_username", return_value="alice"),
            patch("services.web.ai_assistant.resources.conversation.get_request_username", return_value="alice"),
        ):
            for suffix in (
                "attachments/",
                "conversations/",
                "conversation_sidebar/nodes/",
                "conversation_sidebar/pinned/",
                "conversation_sidebar/search/",
            ):
                with self.subTest(path=suffix):
                    check.reset_mock()
                    query = {"scope_type": "scene", "scope_id": "2"}
                    if suffix.endswith("search/"):
                        query["keyword"] = "hello"
                    response = self.request("get", suffix, query)
                    self.assertEqual(response.status_code, 200, response.data)
                    check.assert_called_once()
                    if suffix == "attachments/":
                        self.assertEqual([item["uid"] for item in response.data], [str(self.attachment.uid)])
            scene_ids.assert_not_called()
            system_ids.assert_not_called()

    def test_attachment_uid_filters_use_intersection(self):
        """同传两个 UID 取交集，不能扩展到另一个会话的附件。"""
        other = create_conversation(scope_type="system", scope_id="bk_audit", created_by="alice")
        other_message = Message.objects.create(
            conversation=other,
            message_type=MessageType.LOG_SEARCH,
            status=ExecutionStatus.SUCCESS,
            created_by="alice",
        )
        Attachment.objects.create(
            source_message=other_message,
            attachment_type=AttachmentType.AI_ANALYSIS,
            status=ExecutionStatus.SUCCESS,
            created_by="alice",
        )
        with (
            patch.object(ScopePermission, "check_scope_entry") as check,
            patch("services.web.ai_assistant.resources.attachment.get_request_username", return_value="alice"),
        ):
            response = self.request(
                "get",
                "attachments/",
                {
                    "source_message_uid": str(self.message.uid),
                    "conversation_uid": str(other.uid),
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
        check.assert_called_once()
        scope = check.call_args.args[0]
        self.assertEqual((scope.scope_type, scope.scope_id), ("scene", "2"))

    def test_resource_filtered_attachment_list_rejects_revoked_and_foreign_resources(self):
        """不能通过缺省或伪造请求 Scope 绕过资源所有权和实际归属权限。"""
        denied = PermissionException(action_name="查看范围", apply_url="", permission={})
        for key, uid in (("source_message_uid", self.message.uid), ("conversation_uid", self.conversation.uid)):
            with self.subTest(key=key), patch.object(ScopePermission, "check_scope_entry", side_effect=denied):
                self.assertEqual(self.request("get", "attachments/", {key: str(uid)}).status_code, 403)
        other = create_conversation(created_by="bob")
        with patch.object(ScopePermission, "check_scope_entry") as check:
            self.assertEqual(self.request("get", "attachments/", {"conversation_uid": str(other.uid)}).status_code, 404)
            check.assert_not_called()

    def test_unanchored_attachment_list_still_requires_scope(self):
        """只有 UID 已确定查询范围才允许省略 Scope。"""
        self.assertEqual(self.request("get", "attachments/").status_code, 400)

    def test_create_inside_group_derives_scope(self):
        """组内创建会话由分组绑定范围，根创建仍需显式 Scope。"""
        with (
            patch.object(ScopePermission, "check_scope_entry") as check,
            patch("services.web.ai_assistant.resources.conversation.get_request_username", return_value="alice"),
        ):
            response = self.request("post", "conversations/", {"group_uid": str(self.group.uid)})
        self.assertEqual(response.status_code, 200)
        self.assertEqual((response.data["scope_type"], response.data["scope_id"]), ("system", "bk_audit"))
        check.assert_called_once()

    def test_undeclared_uid_does_not_override_collection_authorization(self):
        """未在接口协议中声明的 UID 不能改变鉴权范围。"""
        denied = PermissionException(action_name="查看范围", apply_url="", permission={})
        with patch.object(ScopePermission, "check_scope_entry", side_effect=denied) as check:
            response = self.request(
                "get",
                "conversations/",
                {
                    "scope_type": "system",
                    "scope_id": "denied",
                    "source_message_uid": str(self.message.uid),
                },
            )
        self.assertEqual(response.status_code, 403)
        scope = check.call_args.args[0]
        self.assertEqual((scope.scope_type, scope.scope_id), ("system", "denied"))

    def test_group_children_and_move_derive_scope_from_source(self):
        """组内列表和节点移动均可由业务 UID 派生具体归属。"""
        with (
            patch.object(ScopePermission, "check_scope_entry") as check,
            patch("services.web.ai_assistant.resources.conversation.get_request_username", return_value="alice"),
        ):
            response = self.request(
                "get",
                "conversation_sidebar/nodes/",
                {"parent_node_type": "GROUP", "parent_node_uid": str(self.group.uid)},
            )
            self.assertEqual(response.status_code, 200)
            scope = check.call_args.args[0]
            self.assertEqual((scope.scope_type, scope.scope_id), ("system", "bk_audit"))
            response = self.request(
                "post",
                "conversation_sidebar/nodes/move/",
                {"source_node_type": "CONVERSATION", "source_node_uid": str(self.conversation.uid)},
            )
            self.assertEqual(response.status_code, 200)
            scope = check.call_args.args[0]
            self.assertEqual((scope.scope_type, scope.scope_id), ("scene", "2"))

    def test_resource_scoped_nodes_reject_revoked_permission(self):
        """组内列表和移动均不能通过省略 Scope 绕过归属权限。"""
        denied = PermissionException(action_name="查看范围", apply_url="", permission={})
        routes = (
            (
                "get",
                "conversation_sidebar/nodes/",
                {
                    "parent_node_type": "GROUP",
                    "parent_node_uid": str(self.group.uid),
                },
            ),
            (
                "post",
                "conversation_sidebar/nodes/move/",
                {
                    "source_node_type": "CONVERSATION",
                    "source_node_uid": str(self.conversation.uid),
                },
            ),
        )
        with patch.object(ScopePermission, "check_scope_entry", side_effect=denied):
            for method, suffix, data in routes:
                with self.subTest(suffix=suffix):
                    self.assertEqual(self.request(method, suffix, data).status_code, 403)

    def test_full_export_public_default_and_invalid_config(self):
        """真实 HTTP 链路对缺省列配置成功执行，对非法列结构返回 400。"""
        self.message.input_data = {"condition": make_condition().model_dump(mode="json")}
        self.message.save(update_fields=["input_data"])
        with (
            patch.object(ScopePermission, "check_scope_entry"),
            patch("services.web.ai_assistant.resources.message.get_request_username", return_value="alice"),
            patch(
                "services.web.ai_assistant.services.log_export.FullExportService.create_task",
                return_value={"id": 123, "status": "READY"},
            ) as create,
        ):
            for body in ({}, {"export_config": {}}, {"export_config": {"flatten_extension": True}}):
                with self.subTest(body=body):
                    response = self.request("post", f"messages/{self.message.uid}/full-export/", body)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.data, {"export_task_id": 123, "status": "READY"})
                    self.assertEqual(create.call_args.kwargs["export_config"]["field_scope"], "specified")
            for config in ([1], {"field_scope": "unknown"}, {"field_scope": "specified", "fields": [1]}):
                with self.subTest(config=config):
                    create.reset_mock()
                    response = self.request(
                        "post", f"messages/{self.message.uid}/full-export/", {"export_config": config}
                    )
                    self.assertEqual(response.status_code, 400)
                    create.assert_not_called()

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
