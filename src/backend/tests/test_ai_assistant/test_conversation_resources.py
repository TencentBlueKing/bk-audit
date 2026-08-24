import json
from unittest.mock import patch

from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import resolve
from rest_framework.test import APIRequestFactory, force_authenticate

from services.web.ai_assistant.constants import (
    ExecutionStatus,
    MessageType,
    SidebarNodeType,
)
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
from tests.test_ai_assistant.handlers import EchoSyncHandler, register_test_message_handler


@patch("services.web.ai_assistant.resources.conversation.get_request_username", return_value="alice")
class ConversationResourceTest(TestCase):
    """资源测试统一走 request()，覆盖请求和响应序列化链路。"""

    def setUp(self):
        register_test_message_handler(EchoSyncHandler())

    def tearDown(self):
        message_handler_registry.unregister(MessageType.SYSTEM_SELECTION)

    def test_non_create_resources_use_resource_default_empty_request_contract(self, _username):
        """创建会话参数不得出现在清空和置顶列表接口中。"""

        self.assertIsNone(ClearConversations.RequestSerializer)
        self.assertIsNone(ListPinnedConversations.RequestSerializer)

    def test_create_conversation_serializer_supplies_default_title(self, _username):
        serializer = ConversationCreateRequestSerializer(data={})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["title"], "新对话")

    def test_group_crud_returns_external_fields(self, _username):
        created = CreateConversationGroup().request({"name": "  审计分组  "})

        self.assertEqual(created["name"], "审计分组")
        self.assertNotIn("id", created)

        updated = UpdateConversationGroup().request({"group_uid": created["uid"], "name": "新名称"})
        self.assertEqual(updated["name"], "新名称")

        self.assertIsNone(DeleteConversationGroup().request({"group_uid": created["uid"]}))

    def test_conversation_crud_and_clear(self, _username):
        created = CreateConversation().request({})

        self.assertEqual(created["title"], "新对话")
        self.assertIsNone(created["initial_message"])
        self.assertNotIn("id", created)
        self.assertEqual(GetConversation().request({"conversation_uid": created["uid"]})["uid"], created["uid"])

        updated = UpdateConversation().request({"conversation_uid": created["uid"], "title": "检索会话"})
        self.assertEqual(updated["title"], "检索会话")
        self.assertIsNone(DeleteConversation().request({"conversation_uid": created["uid"]}))

        CreateConversation().request({})
        CreateConversation().request({})
        self.assertIsNone(ClearConversations().request({}))
        self.assertEqual(Conversation.objects.filter(created_by="alice").count(), 0)

        custom = CreateConversation().request({"title": "指定标题"})
        self.assertEqual(custom["title"], "指定标题")

    def test_conversation_can_atomically_create_system_selection_message(self, _username):
        created = CreateConversation().request(
            {
                "initial_message": {
                    "message_type": MessageType.SYSTEM_SELECTION,
                    "input_data": {"text": "system-a"},
                }
            }
        )

        self.assertEqual(created["title"], "新对话")
        self.assertEqual(created["initial_message"]["conversation_uid"], created["uid"])
        self.assertEqual(created["initial_message"]["status"], ExecutionStatus.SUCCESS)
        self.assertEqual(created["initial_message"]["output_data"], {"content": "system:system-a"})

    def test_sidebar_list_pin_move_and_search(self, _username):
        group = CreateConversationGroup().request({"name": "目标分组"})
        first = CreateConversation().request({})
        second = CreateConversation().request({})
        UpdateConversation().request({"conversation_uid": first["uid"], "title": "审计检索一"})
        UpdateConversation().request({"conversation_uid": second["uid"], "title": "审计检索二"})

        moved = MoveConversationSidebarNode().request(
            {
                "source_node_type": SidebarNodeType.CONVERSATION,
                "source_node_uid": first["uid"],
                "target_node_type": SidebarNodeType.GROUP,
                "target_node_uid": group["uid"],
            }
        )
        self.assertEqual(moved["group"], {"uid": group["uid"], "name": "目标分组"})

        moved_group = MoveConversationSidebarNode().request(
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
            ListConversationSidebarNodes().request({}),
            many=True,
        ).data
        group_nodes = SidebarNodeResponseSerializer(
            ListConversationSidebarNodes().request(
                {"parent_node_type": SidebarNodeType.GROUP, "parent_node_uid": group["uid"]}
            ),
            many=True,
        ).data
        pinned_nodes = ListPinnedConversations().request({})
        search_results = ConversationSearchResponseSerializer(
            SearchConversations().request({"keyword": "审计检索"}),
            many=True,
        ).data

        self.assertEqual(
            [node["node_type"] for node in root_nodes], [SidebarNodeType.GROUP, SidebarNodeType.CONVERSATION]
        )
        self.assertEqual(group_nodes, [])
        self.assertEqual([node["node_uid"] for node in pinned_nodes], [first["uid"]])
        self.assertEqual({item["node_uid"] for item in search_results}, {first["uid"], second["uid"]})
        self.assertTrue(next(item for item in search_results if item["node_uid"] == first["uid"])["is_pinned"])
        self.assertFalse(next(item for item in search_results if item["node_uid"] == second["uid"])["is_pinned"])
        self.assertNotIn("position", pinned_nodes[0])

        group_node = next(node for node in root_nodes if node["node_type"] == SidebarNodeType.GROUP)
        self.assertEqual(group_node["conversation_count"], 1)
        self.assertEqual(group_node["unpinned_conversation_count"], 0)

    def test_delete_group_soft_deletes_nested_conversation(self, _username):
        group = CreateConversationGroup().request({"name": "待删除"})
        conversation = CreateConversation().request({})
        MoveConversationSidebarNode().request(
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


@override_settings(ROOT_URLCONF="services.web.urls")
class ConversationResourceRoutingTest(TestCase):
    class User:
        username = "alice"
        is_authenticated = True

    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()

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
        group = CreateConversationGroup().request({"name": "待删除"})
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
            CreateConversation().request({})
        view = resolve("/api/v1/ai_assistant/conversation_sidebar/nodes/").func

        default_request = self.factory.get("/api/v1/ai_assistant/conversation_sidebar/nodes/")
        force_authenticate(default_request, user=self.User())
        with CaptureQueriesContext(connection) as query_context:
            default_response = view(default_request)

        max_request = self.factory.get(
            "/api/v1/ai_assistant/conversation_sidebar/nodes/",
            {"page": 1, "page_size": 1000},
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
