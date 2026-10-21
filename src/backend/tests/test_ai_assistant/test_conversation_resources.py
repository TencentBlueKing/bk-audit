import json
from unittest.mock import Mock, patch

import yaml
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import resolve
from drf_spectacular.views import SpectacularAPIView
from rest_framework.test import APIRequestFactory, force_authenticate

from services.web.ai_assistant.constants import (
    ExecutionStatus,
    MessageType,
    SidebarNodeType,
)
from services.web.ai_assistant.exceptions import CrossScopeMutationNotAllowed
from services.web.ai_assistant.handlers import message_handler_registry
from services.web.ai_assistant.models import Conversation, ConversationSidebarNode
from services.web.ai_assistant.resources.conversation import (
    ClearConversations,
    CreateConversation,
    CreateConversationGroup,
    DeleteConversation,
    DeleteConversationGroup,
    GetConversation,
    ListConversationSidebarNodes,
    ListPinnedConversations,
    MoveConversationSidebarNode,
    PinConversationSidebarNode,
    SearchConversations,
    UpdateConversation,
    UpdateConversationGroup,
)
from services.web.ai_assistant.serializers.conversation import (
    ConversationCreateRequestSerializer,
    ConversationSearchResponseSerializer,
    SidebarNodeResponseSerializer,
)
from tests.base import TestCase
from tests.test_ai_assistant.handlers import (
    EchoSyncHandler,
    register_test_message_handler,
)


@patch("services.web.ai_assistant.resources.conversation.get_request_username", return_value="alice")
class ConversationResourceTest(TestCase):
    """资源测试统一走 request()，覆盖请求和响应序列化链路。"""

    def setUp(self):
        self.scope_permission_patch = patch(
            "services.web.ai_assistant.services.scope.ScopePermission.check_scope_entry"
        )
        self.scope_permission_patch.start()
        self.addCleanup(self.scope_permission_patch.stop)
        for method_name, visible_ids in (("get_scene_ids", ["1"]), ("get_system_ids", ["bk_audit"])):
            permission_patch = patch(
                f"services.web.ai_assistant.services.scope.ScopePermission.{method_name}",
                return_value=visible_ids,
            )
            permission_patch.start()
            self.addCleanup(permission_patch.stop)
        register_test_message_handler(EchoSyncHandler())

    def tearDown(self):
        message_handler_registry.unregister(MessageType.SYSTEM_SELECTION)

    @staticmethod
    def _with_default_scope(data):
        """给非 scope 专项用例补充默认 concrete 测试场景。"""

        return {"scope_type": "scene", "scope_id": "1", **data}

    def create_group(self, data):
        """走资源完整序列化链路创建测试分组。"""

        resource = CreateConversationGroup()
        return resource.request(self._with_default_scope(data))

    def create_conversation(self, data):
        """走资源完整序列化链路创建测试会话。"""

        resource = CreateConversation()
        return resource.request(self._with_default_scope(data))

    def move_sidebar_node(self, data):
        return MoveConversationSidebarNode().request(self._with_default_scope(data))

    def test_non_create_resources_use_resource_default_empty_request_contract(self, _username):
        """清空必须绑定明确 scope，置顶列表继续使用空请求。"""

        self.assertEqual(ClearConversations.RequestSerializer.__name__, "ClearConversationsRequestSerializer")
        self.assertEqual(ListPinnedConversations.RequestSerializer.__name__, "SidebarScopeQuerySerializer")

    def test_create_conversation_serializer_supplies_default_title(self, _username):
        serializer = ConversationCreateRequestSerializer(data={"scope_type": "scene", "scope_id": "1"})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["title"], "新对话")

    def test_create_resources_return_the_persisted_concrete_scope(self, _username):
        group = self.create_group({"name": "系统分组", "scope_type": "system", "scope_id": "bk_audit"})
        conversation = self.create_conversation(
            {"scope_type": "system", "scope_id": "bk_audit", "group_uid": group["uid"]}
        )

        self.assertEqual((group["scope_type"], group["scope_id"]), ("system", "bk_audit"))
        self.assertEqual((conversation["scope_type"], conversation["scope_id"]), ("system", "bk_audit"))

    def test_clear_resource_deletes_only_the_requested_scope(self, _username):
        selected = self.create_conversation({"scope_type": "scene", "scope_id": "1"})
        other_scope = self.create_conversation({"scope_type": "scene", "scope_id": "2"})

        ClearConversations().request({"scope_type": "scene", "scope_id": "1"})

        self.assertFalse(Conversation.objects.filter(uid=selected["uid"]).exists())
        self.assertTrue(Conversation.objects.filter(uid=other_scope["uid"]).exists())

    def test_clear_resource_rejects_cross_scope_mutation(self, _username):
        with self.assertRaises(CrossScopeMutationNotAllowed):
            ClearConversations().request({"scope_type": "cross_scene", "scope_id": ""})

    def test_group_crud_returns_external_fields(self, _username):
        created = self.create_group({"name": "  审计分组  "})

        self.assertEqual(created["name"], "审计分组")
        self.assertNotIn("id", created)

        updated = UpdateConversationGroup().request({"group_uid": created["uid"], "name": "新名称"})
        self.assertEqual(updated["name"], "新名称")

        self.assertIsNone(DeleteConversationGroup().request({"group_uid": created["uid"]}))

    def test_conversation_crud_and_clear(self, _username):
        created = self.create_conversation({})

        self.assertEqual(created["title"], "新对话")
        self.assertIsNone(created["initial_message"])
        self.assertNotIn("id", created)
        self.assertEqual(GetConversation().request({"conversation_uid": created["uid"]})["uid"], created["uid"])

        updated = UpdateConversation().request({"conversation_uid": created["uid"], "title": "检索会话"})
        self.assertEqual(updated["title"], "检索会话")
        self.assertIsNone(DeleteConversation().request({"conversation_uid": created["uid"]}))

        self.create_conversation({})
        self.create_conversation({})
        self.assertIsNone(ClearConversations().request({"scope_type": "scene", "scope_id": "1"}))
        self.assertEqual(Conversation.objects.filter(created_by="alice").count(), 0)

        custom = self.create_conversation({"title": "指定标题"})
        self.assertEqual(custom["title"], "指定标题")

    def test_conversation_can_atomically_create_system_selection_message(self, _username):
        created = self.create_conversation(
            {
                "initial_message": {
                    "message_type": MessageType.SYSTEM_SELECTION,
                    "input_data": {"text": "system-a"},
                }
            }
        )

        self.assertEqual(created["title"], "新对话")
        self.assertEqual(created["initial_message"]["conversation_uid"], created["uid"])
        # 初始化消息复用统一创建链路，同步 Handler 在事务内直接收敛为终态。
        self.assertEqual(created["initial_message"]["status"], ExecutionStatus.SUCCESS)

    def test_conversation_can_be_created_directly_in_group(self, _username):
        """创建接口直接落组内节点，响应协议保持不变。"""

        group = self.create_group({"name": "目标分组"})

        created = self.create_conversation({"title": "组内会话", "group_uid": group["uid"]})

        self.assertEqual(
            set(created),
            {"uid", "title", "scope_type", "scope_id", "created_at", "updated_at", "initial_message"},
        )
        self.assertIsNone(created["initial_message"])
        node = ConversationSidebarNode.objects.get(conversation__uid=created["uid"])
        self.assertEqual(str(node.parent_node.group.uid), str(group["uid"]))

    def test_sidebar_list_pin_move_and_search(self, _username):
        group = self.create_group({"name": "目标分组"})
        first = self.create_conversation({})
        second = self.create_conversation({})
        UpdateConversation().request({"conversation_uid": first["uid"], "title": "审计检索一"})
        UpdateConversation().request({"conversation_uid": second["uid"], "title": "审计检索二"})

        moved = self.move_sidebar_node(
            {
                "source_node_type": SidebarNodeType.CONVERSATION,
                "source_node_uid": first["uid"],
                "target_node_type": SidebarNodeType.GROUP,
                "target_node_uid": group["uid"],
            }
        )
        self.assertEqual((moved["scope_type"], moved["scope_id"]), ("scene", "1"))
        self.assertEqual(moved["group"], {"uid": group["uid"], "name": "目标分组"})

        moved_group = self.move_sidebar_node(
            {
                "source_node_type": SidebarNodeType.GROUP,
                "source_node_uid": group["uid"],
                "before_node_type": SidebarNodeType.CONVERSATION,
                "before_node_uid": second["uid"],
            }
        )
        self.assertEqual(moved_group["conversation_count"], 1)
        self.assertEqual(moved_group["unpinned_conversation_count"], 1)

        pinned = PinConversationSidebarNode().request(
            {
                "node_type": SidebarNodeType.CONVERSATION,
                "node_uid": first["uid"],
                "is_pinned": True,
            }
        )
        self.assertIsNotNone(pinned["pinned_at"])

        root_nodes = SidebarNodeResponseSerializer(
            ListConversationSidebarNodes().request(self._with_default_scope({})),
            many=True,
        ).data
        group_nodes = SidebarNodeResponseSerializer(
            ListConversationSidebarNodes().request(
                self._with_default_scope({"parent_node_type": SidebarNodeType.GROUP, "parent_node_uid": group["uid"]})
            ),
            many=True,
        ).data
        pinned_nodes = ListPinnedConversations().request(self._with_default_scope({}))
        search_results = ConversationSearchResponseSerializer(
            SearchConversations().request(self._with_default_scope({"keyword": "审计检索"})),
            many=True,
        ).data

        self.assertEqual(
            [node["node_type"] for node in root_nodes], [SidebarNodeType.GROUP, SidebarNodeType.CONVERSATION]
        )
        self.assertEqual(group_nodes, [])
        self.assertEqual([node["node_uid"] for node in pinned_nodes], [first["uid"]])
        self.assertEqual({item["node_uid"] for item in search_results}, {first["uid"], second["uid"]})
        self.assertTrue(all((item["scope_type"], item["scope_id"]) == ("scene", "1") for item in pinned_nodes))
        self.assertTrue(all((item["scope_type"], item["scope_id"]) == ("scene", "1") for item in search_results))
        self.assertTrue(next(item for item in search_results if item["node_uid"] == first["uid"])["is_pinned"])
        self.assertFalse(next(item for item in search_results if item["node_uid"] == second["uid"])["is_pinned"])
        self.assertNotIn("position", pinned_nodes[0])

        group_node = next(node for node in root_nodes if node["node_type"] == SidebarNodeType.GROUP)
        conversation_node = next(node for node in root_nodes if node["node_type"] == SidebarNodeType.CONVERSATION)
        self.assertEqual((group_node["scope_type"], group_node["scope_id"]), ("scene", "1"))
        self.assertEqual((conversation_node["scope_type"], conversation_node["scope_id"]), ("scene", "1"))
        self.assertEqual(group_node["conversation_count"], 1)
        self.assertEqual(group_node["unpinned_conversation_count"], 0)

    def test_cross_scope_sidebar_resources_return_only_authorized_bound_scopes(self, _username):
        scene_group = self.create_group({"name": "场景分组", "scope_id": "1"})
        scene_one = self.create_conversation({"title": "共享审计", "scope_id": "1", "group_uid": scene_group["uid"]})
        scene_two = self.create_conversation({"title": "共享审计", "scope_id": "2"})
        system = self.create_conversation({"title": "共享审计", "scope_type": "system", "scope_id": "bk_audit"})

        with (
            patch(
                "services.web.ai_assistant.services.scope.ScopePermission.get_scene_ids",
                return_value=[1, 2],
            ),
            patch(
                "services.web.ai_assistant.services.scope.ScopePermission.get_system_ids",
                return_value=["bk_audit"],
            ),
        ):
            scene_nodes = SidebarNodeResponseSerializer(
                ListConversationSidebarNodes().request({"scope_type": "cross_scene"}), many=True
            ).data
            group_children = SidebarNodeResponseSerializer(
                ListConversationSidebarNodes().request(
                    {
                        "scope_type": "cross_scene",
                        "parent_node_type": SidebarNodeType.GROUP,
                        "parent_node_uid": scene_group["uid"],
                    }
                ),
                many=True,
            ).data
            scene_search = ConversationSearchResponseSerializer(
                SearchConversations().request({"keyword": "共享", "scope_type": "cross_scene"}), many=True
            ).data
            system_search = ConversationSearchResponseSerializer(
                SearchConversations().request({"keyword": "共享", "scope_type": "cross_system"}),
                many=True,
            ).data

        self.assertEqual(
            {(node["node_type"], node["node_uid"]) for node in scene_nodes},
            {(SidebarNodeType.GROUP, scene_group["uid"]), (SidebarNodeType.CONVERSATION, scene_two["uid"])},
        )
        self.assertEqual({node["node_uid"] for node in group_children}, {scene_one["uid"]})
        self.assertEqual(
            {(item["scope_type"], item["scope_id"]) for item in scene_search},
            {("scene", "1"), ("scene", "2")},
        )
        self.assertEqual({item["node_uid"] for item in system_search}, {system["uid"]})
        self.assertTrue(all(item["scope_type"] != "cross_scene" for item in scene_nodes))

    def test_move_resource_supports_after_anchor(self, _username):
        first = self.create_conversation({"title": "first"})
        second = self.create_conversation({"title": "second"})
        third = self.create_conversation({"title": "third"})

        moved = self.move_sidebar_node(
            {
                "source_node_type": SidebarNodeType.CONVERSATION,
                "source_node_uid": first["uid"],
                "after_node_type": SidebarNodeType.CONVERSATION,
                "after_node_uid": third["uid"],
            }
        )
        root_nodes = SidebarNodeResponseSerializer(
            ListConversationSidebarNodes().request(self._with_default_scope({})),
            many=True,
        ).data

        self.assertEqual(moved["node_uid"], first["uid"])
        self.assertEqual(
            [node["node_uid"] for node in root_nodes],
            [third["uid"], first["uid"], second["uid"]],
        )

    def test_delete_group_soft_deletes_nested_conversation(self, _username):
        group = self.create_group({"name": "待删除"})
        conversation = self.create_conversation({})
        self.move_sidebar_node(
            {
                "source_node_type": SidebarNodeType.CONVERSATION,
                "source_node_uid": conversation["uid"],
                "target_node_type": SidebarNodeType.GROUP,
                "target_node_uid": group["uid"],
            }
        )

        DeleteConversationGroup().request({"group_uid": group["uid"]})

        self.assertFalse(Conversation.objects.filter(uid=conversation["uid"]).exists())
        self.assertFalse(ConversationSidebarNode.objects.filter(created_by="alice").exists())

    @override_settings(ROOT_URLCONF="urls")
    def test_openapi_separates_operation_semantics_from_response_shape(self, _username):
        request = APIRequestFactory().get("/api/schema/")
        request.user = Mock(is_staff=True, is_authenticated=True)

        response = SpectacularAPIView.as_view()(request)
        response.render()
        schema = yaml.safe_load(response.content)
        paths = schema["paths"]

        pinned = paths["/api/v1/ai_assistant/conversation_sidebar/pinned/"]["get"]
        pinned_schema = pinned["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual(pinned["operationId"], "api_v1_ai_assistant_conversation_sidebar_pinned_list")
        self.assertEqual(
            pinned_schema["properties"]["data"],
            {"type": "array", "items": {"$ref": "#/components/schemas/SidebarNodeResponse"}},
        )

        message_list = paths["/api/v1/ai_assistant/messages/"]["get"]
        message_list_schema = message_list["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual(message_list["operationId"], "api_v1_ai_assistant_messages_list")
        self.assertEqual(
            message_list_schema["properties"]["data"], {"$ref": "#/components/schemas/MessageWindowResponse"}
        )

        message_detail = paths["/api/v1/ai_assistant/messages/{message_uid}/"]["get"]
        message_detail_schema = message_detail["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual(message_detail["operationId"], "api_v1_ai_assistant_messages_retrieve")
        self.assertEqual(message_detail_schema["properties"]["data"], {"$ref": "#/components/schemas/MessageResponse"})

        # 无响应序列化器的 GET 也不能因为 collection 路由语义被误包装成数组。
        ping_schema = paths["/ping/"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual(ping_schema.get("type"), "object")

        for list_path in (
            "/api/v1/databus/namespaces/{namespace}/collector_plugins/",
            "/api/v1/meta/namespaces/{namespace}/general_config/",
        ):
            list_schema = paths[list_path]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
            self.assertEqual(list_schema["properties"]["data"].get("type"), "array")


@override_settings(ROOT_URLCONF="services.web.urls")
class ConversationResourceRoutingTest(TestCase):
    class User:
        username = "alice"
        is_authenticated = True

    def setUp(self):
        super().setUp()
        permission_username = patch("services.web.ai_assistant.permissions.get_request_username", return_value="alice")
        permission_username.start()
        self.addCleanup(permission_username.stop)
        self.factory = APIRequestFactory()
        self.scope_permission_patch = patch(
            "services.web.ai_assistant.services.scope.ScopePermission.check_scope_entry"
        )
        self.scope_permission_patch.start()
        self.addCleanup(self.scope_permission_patch.stop)
        for method_name, visible_ids in (("get_scene_ids", ["1"]), ("get_system_ids", ["bk_audit"])):
            permission_patch = patch(
                f"services.web.ai_assistant.services.scope.ScopePermission.{method_name}",
                return_value=visible_ids,
            )
            permission_patch.start()
            self.addCleanup(permission_patch.stop)

    def test_sidebar_routes_use_nested_node_endpoints(self):
        self.assertEqual(
            resolve("/api/v1/ai_assistant/conversation_sidebar/nodes/").url_name,
            "conversation_sidebar_nodes-list",
        )
        self.assertEqual(
            resolve("/api/v1/ai_assistant/conversation_sidebar/nodes/move/").url_name,
            "conversation_sidebar_nodes-move",
        )
        self.assertEqual(
            resolve("/api/v1/ai_assistant/conversation_sidebar/nodes/pin/").url_name,
            "conversation_sidebar_nodes-pin",
        )

    def test_detail_routes_name_external_uid_parameters(self):
        group_match = resolve("/api/v1/ai_assistant/conversation_groups/group-uuid/")
        conversation_match = resolve("/api/v1/ai_assistant/conversations/conversation-uuid/")

        self.assertEqual(group_match.kwargs, {"group_uid": "group-uuid"})
        self.assertEqual(conversation_match.kwargs, {"conversation_uid": "conversation-uuid"})

    @patch("services.web.ai_assistant.resources.conversation.get_request_username", return_value="alice")
    def test_delete_endpoint_uses_default_success_response_envelope(self, _username):
        group = CreateConversationGroup().request({"name": "待删除", "scope_type": "scene", "scope_id": "1"})
        path = f"/api/v1/ai_assistant/conversation_groups/{group['uid']}/"
        view = resolve(path).func
        request = self.factory.delete(path)
        force_authenticate(request, user=self.User())

        response = view(request, group_uid=group["uid"])
        response.render()
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["result"])
        self.assertEqual(payload["code"], 0)
        self.assertIsNone(payload["data"])
        self.assertIsNone(payload["message"])

    @patch("services.web.ai_assistant.resources.conversation.get_request_username", return_value="alice")
    def test_sidebar_nodes_use_twenty_default_and_one_hundred_max_page_size(self, _username):
        for _ in range(105):
            CreateConversation().request({"scope_type": "scene", "scope_id": "1"})
        view = resolve("/api/v1/ai_assistant/conversation_sidebar/nodes/").func

        default_request = self.factory.get(
            "/api/v1/ai_assistant/conversation_sidebar/nodes/", {"scope_type": "scene", "scope_id": "1"}
        )
        force_authenticate(default_request, user=self.User())
        with CaptureQueriesContext(connection) as query_context:
            default_response = view(default_request)

        max_request = self.factory.get(
            "/api/v1/ai_assistant/conversation_sidebar/nodes/",
            {"page": 1, "page_size": 1000, "scope_type": "scene", "scope_id": "1"},
        )
        force_authenticate(max_request, user=self.User())
        max_response = view(max_request)

        self.assertEqual(default_response.status_code, 200)
        self.assertEqual(default_response.data["total"], 105)
        self.assertEqual(len(default_response.data["results"]), 20)
        node_selects = [
            query["sql"]
            for query in query_context.captured_queries
            if "ai_assistant_conversationsidebarnode" in query["sql"]
            and query["sql"].lstrip().upper().startswith("SELECT")
        ]
        self.assertTrue(any("LIMIT 20" in sql.upper() for sql in node_selects), node_selects)
        self.assertEqual(max_response.data["total"], 105)
        self.assertEqual(len(max_response.data["results"]), 100)
