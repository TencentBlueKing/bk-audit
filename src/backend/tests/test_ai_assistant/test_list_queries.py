"""会话与附件列表的筛选、排序及数据库限量契约。"""

from datetime import timedelta
from unittest import mock

from django.db import connection
from django.http import QueryDict
from django.test.utils import CaptureQueriesContext
from django.urls import resolve
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from services.web.ai_assistant.constants import (
    AttachmentType,
    ExecutionStatus,
    MessageType,
)
from services.web.ai_assistant.models import Attachment, Message
from services.web.ai_assistant.resources import conversation as conversation_resources
from services.web.ai_assistant.resources.attachment import ListAttachments
from services.web.ai_assistant.serializers.attachment import (
    AttachmentListRequestSerializer,
)
from services.web.common.scope_permission import ScopePermission
from tests.base import TestCase
from tests.test_ai_assistant.factories import (
    create_conversation as create_test_conversation,
)
from tests.test_ai_assistant.handlers import (
    EchoAttachmentAsyncHandler,
    EchoAttachmentSyncHandler,
    use_attachment_handler,
)


class ConversationListScopeTest(TestCase):
    """平铺会话列表与一期侧栏遵循同一可见 scope 边界。"""

    def setUp(self):
        """准备同用户跨场景、系统会话，真实查询只替换外部权限结果。"""
        patcher = mock.patch(
            "services.web.ai_assistant.resources.conversation.get_request_username", return_value="alice"
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.scene_one = create_test_conversation(scope_type="scene", scope_id="1", created_by="alice")
        create_test_conversation(scope_type="scene", scope_id="2", created_by="alice")
        self.system_one = create_test_conversation(scope_type="system", scope_id="test-system", created_by="alice")
        create_test_conversation(scope_type="system", scope_id="hidden-system", created_by="alice")

    @mock.patch.object(ScopePermission, "get_scene_ids", return_value=[1])
    def test_concrete_scope_limits_flat_list(self, _permission):
        """具体场景查询不能返回其他场景或系统会话。"""
        response = conversation_resources.ListConversations().request(scope_type="scene", scope_id="1")
        self.assertEqual([row["uid"] for row in response], [str(self.scene_one.uid)])
        self.assertEqual((response[0]["scope_type"], response[0]["scope_id"]), ("scene", "1"))

    @mock.patch.object(ScopePermission, "get_scene_ids", return_value=[1])
    @mock.patch.object(ScopePermission, "get_system_ids", return_value=["test-system"])
    def test_cross_scope_only_lists_authorized_direction(self, _systems, _scenes):
        """跨场景和跨系统分别只返回其方向内授权范围的会话。"""
        for scope_type, conversation in (("cross_scene", self.scene_one), ("cross_system", self.system_one)):
            with self.subTest(scope_type=scope_type):
                response = conversation_resources.ListConversations().request(scope_type=scope_type)
                self.assertEqual([row["uid"] for row in response], [str(conversation.uid)])

    @mock.patch.object(ScopePermission, "get_scene_ids", return_value=[])
    def test_cross_scope_with_no_visibility_is_empty(self, _permission):
        """没有可见场景时返回空数组。"""
        self.assertEqual(conversation_resources.ListConversations().request(scope_type="cross_scene"), [])


class ListQueriesTest(TestCase):
    """真实资源请求确保筛选、排序、限量在序列化前完成。"""

    scope = {"scope_type": "scene", "scope_id": "1"}

    def setUp(self):
        """准备当前用户及其他用户会话，并隔离附件类型注册。"""
        for module in ("attachment", "conversation"):
            patcher = mock.patch(
                f"services.web.ai_assistant.resources.{module}.get_request_username", return_value="alice"
            )
            patcher.start()
            self.addCleanup(patcher.stop)
        for target, kwargs in (
            ("services.web.ai_assistant.permissions.get_request_username", {"return_value": "alice"}),
            ("services.web.common.scope_permission.ScopePermission.check_scope_entry", {}),
            ("services.web.common.scope_permission.ScopePermission.get_scene_ids", {"return_value": [1]}),
        ):
            self.enterContext(mock.patch(target, **kwargs))
        use_attachment_handler(self, EchoAttachmentAsyncHandler())
        use_attachment_handler(self, EchoAttachmentSyncHandler())
        self.conversation = create_test_conversation(title="有报告", created_by="alice", updated_by="alice")
        self.empty = create_test_conversation(title="空会话", created_by="alice", updated_by="alice")
        self.other = create_test_conversation(title="他人会话", created_by="bob", updated_by="bob")
        self.source = Message.objects.create(
            conversation=self.conversation,
            message_type=MessageType.LOG_SEARCH,
            status=ExecutionStatus.SUCCESS,
            created_by="alice",
            updated_by="alice",
        )
        now = timezone.now()
        self.first = Attachment.objects.create(
            source_message=self.source,
            attachment_type=AttachmentType.AI_ANALYSIS,
            title="报告 Alpha",
            status=ExecutionStatus.SUCCESS,
            content_updated_at=now,
            created_by="alice",
            updated_by="alice",
        )
        self.second = Attachment.objects.create(
            source_message=self.source,
            attachment_type=AttachmentType.AI_ANALYSIS,
            title="报告 Beta",
            status=ExecutionStatus.SUCCESS,
            content_updated_at=now - timedelta(days=1),
            created_by="alice",
            updated_by="alice",
        )
        Attachment.objects.filter(id=self.first.id).update(created_at=now - timedelta(days=2))
        Attachment.objects.filter(id=self.second.id).update(created_at=now - timedelta(days=1))

    def test_attachment_default_sort_limit_and_unlimited(self):
        """默认按内容更新时间倒序，limit作用于数据库结果，不传保持全量。"""
        with self.assertNumQueries(1):
            response = ListAttachments().request(**self.scope, conversation_uid=str(self.conversation.uid), limit=1)
        self.assertEqual([item["uid"] for item in response], [str(self.first.uid)])
        response = ListAttachments().request(**self.scope, conversation_uid=str(self.conversation.uid))
        self.assertEqual([item["uid"] for item in response], [str(self.first.uid), str(self.second.uid)])

    def test_attachment_sort_before_limit_and_keyword(self):
        """消息块可按创建时间倒序，标题模糊搜索和限制数量可组合。"""
        response = ListAttachments().request(
            **self.scope, source_message_uid=str(self.source.uid), sort="-created_at", limit=1
        )
        self.assertEqual([item["uid"] for item in response], [str(self.second.uid)])
        response = ListAttachments().request(**self.scope, keyword="Alpha", sort="title", limit=1)
        self.assertEqual([item["uid"] for item in response], [str(self.first.uid)])

    def test_sort_formats_and_invalid_list_arguments(self):
        """复用排序字段支持CSV、数组、重复参数并拒绝任意数据库字段。"""
        for data in (
            {"sort": "title,-created_at"},
            {"sort": ["title", "-created_at"]},
            QueryDict("scope_type=scene&scope_id=1&sort=title&sort=-created_at"),
        ):
            serializer = AttachmentListRequestSerializer(
                data=data if isinstance(data, QueryDict) else {**self.scope, **data}
            )
            self.assertTrue(serializer.is_valid(), serializer.errors)
            self.assertEqual(serializer.validated_data["order_fields"], ["title", "-created_at"])
        for data in (
            {"limit": 0},
            {"limit": -1},
            {"limit": 101},
            {"sort": "source_message__created_by"},
            {"sort": "--title"},
        ):
            serializer = AttachmentListRequestSerializer(
                data=data if isinstance(data, QueryDict) else {**self.scope, **data}
            )
            self.assertFalse(serializer.is_valid(), data)

    def test_sort_ties_use_stable_id_order(self):
        """显式排序字段相同仍有稳定顺序，避免limit窗口随机变化。"""
        Attachment.objects.filter(source_message=self.source).update(title="同名")
        response = ListAttachments().request(**self.scope, sort="title", limit=1)
        self.assertEqual([item["uid"] for item in response], [str(self.second.uid)])

    def test_conversations_are_flat_visible_and_filter_by_attachments(self):
        """全量列表不依赖侧栏节点，存在多个附件也不重复会话。"""
        with self.assertNumQueries(1):
            response = conversation_resources.ListConversations().request(**self.scope)
        self.assertEqual({item["uid"] for item in response}, {str(self.conversation.uid), str(self.empty.uid)})
        with self.assertNumQueries(1):
            response = conversation_resources.ListConversations().request(**self.scope, has_attachments=True)
        self.assertEqual([item["uid"] for item in response], [str(self.conversation.uid)])
        response = conversation_resources.ListConversations().request(**self.scope, has_attachments=False)
        self.assertEqual([item["uid"] for item in response], [str(self.empty.uid)])
        self.conversation.delete()
        self.assertEqual(conversation_resources.ListConversations().request(**self.scope, has_attachments=True), [])

    def test_conversation_attachment_type_filters_existence(self):
        """类型筛选只按本用户该类型附件判断，反向筛选也是相同语义。"""
        response = conversation_resources.ListConversations().request(
            **self.scope, attachment_type=AttachmentType.FIELD_STATISTICS
        )
        self.assertEqual(response, [])
        response = conversation_resources.ListConversations().request(
            **self.scope, has_attachments=False, attachment_type=AttachmentType.AI_ANALYSIS
        )
        self.assertEqual([item["uid"] for item in response], [str(self.empty.uid)])
        response = conversation_resources.ListConversations().request(
            **self.scope, has_attachments=True, attachment_type="FIELD_STATISTICS,AI_ANALYSIS"
        )
        self.assertEqual([item["uid"] for item in response], [str(self.conversation.uid)])
        Attachment.objects.filter(id__in=[self.first.id, self.second.id]).update(created_by="bob")
        self.assertEqual(conversation_resources.ListConversations().request(**self.scope, has_attachments=True), [])

    def test_get_routes_return_arrays_and_limit_in_sql(self):
        """真实GET路由保持数组响应，重复sort参数和limit落到数据库。"""
        factory = APIRequestFactory()
        user = mock.Mock(username="alice", is_authenticated=True)
        path = "/api/v1/ai_assistant/attachments/"
        request = factory.get(path + "?scope_type=scene&scope_id=1&sort=-created_at&sort=title&limit=1")
        force_authenticate(request, user=user)
        with CaptureQueriesContext(connection) as captured:
            response = resolve(path).func(request)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([item["uid"] for item in response.data], [str(self.second.uid)])
        self.assertTrue(any("LIMIT 1" in query["sql"].upper() for query in captured), captured.captured_queries)
        path = "/api/v1/ai_assistant/conversations/"
        request = factory.get(path, {**self.scope, "has_attachments": "true", "attachment_type": "AI_ANALYSIS"})
        force_authenticate(request, user=user)
        response = resolve(path).func(request)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([item["uid"] for item in response.data], [str(self.conversation.uid)])

    def test_get_conversations_type_without_boolean_implies_has_attachments(self):
        """真实QueryDict中未传布尔值不能被DRF当作False。"""
        path = "/api/v1/ai_assistant/conversations/"
        for params, expected in (
            ({"attachment_type": "AI_ANALYSIS"}, [str(self.conversation.uid)]),
            ({"attachment_type": "AI_ANALYSIS", "has_attachments": "false"}, [str(self.empty.uid)]),
        ):
            with self.subTest(params=params):
                request = APIRequestFactory().get(path, {**self.scope, **params})
                force_authenticate(request, user=mock.Mock(username="alice", is_authenticated=True))
                response = resolve(path).func(request)
                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual([item["uid"] for item in response.data], expected)

    def test_conversation_attachment_counts_include_all_types_and_states(self):
        """类型筛选不截断统计，空类型补零，其他用户附件不计入。"""
        Attachment.objects.create(
            source_message=self.source,
            attachment_type=AttachmentType.FIELD_STATISTICS,
            status=ExecutionStatus.FAILED,
            created_by="alice",
            updated_by="alice",
        )
        Attachment.objects.create(
            source_message=self.source,
            attachment_type=AttachmentType.AI_STATISTICS,
            status=ExecutionStatus.PROCESSING,
            created_by="bob",
            updated_by="bob",
        )
        with self.assertNumQueries(1):
            response = conversation_resources.ListConversations().request(
                **self.scope, attachment_type=AttachmentType.AI_ANALYSIS
            )
        self.assertEqual(len(response), 1)
        self.assertEqual(response[0]["attachment_count"], 3)
        self.assertEqual(
            response[0]["attachment_counts_by_type"],
            {
                "FIELD_STATISTICS": 1,
                "AI_STATISTICS": 0,
                "AI_ANALYSIS": 2,
            },
        )
        response = conversation_resources.ListConversations().request(**self.scope, has_attachments=False)
        self.assertEqual(response[0]["attachment_count"], 0)
        self.assertEqual(
            response[0]["attachment_counts_by_type"],
            {
                "FIELD_STATISTICS": 0,
                "AI_STATISTICS": 0,
                "AI_ANALYSIS": 0,
            },
        )

    def test_conversation_counts_remain_one_query_across_multiple_messages(self):
        """同会话多消息正确汇总，多会话仍只执行一次数据库查询。"""
        source = Message.objects.create(
            conversation=self.conversation,
            message_type=MessageType.LOG_SEARCH,
            status=ExecutionStatus.SUCCESS,
            created_by="alice",
            updated_by="alice",
        )
        Attachment.objects.create(
            source_message=source,
            attachment_type=AttachmentType.AI_ANALYSIS,
            status=ExecutionStatus.PROCESSING,
            created_by="alice",
            updated_by="alice",
        )
        for index in range(5):
            create_test_conversation(title=f"空会话{index}", created_by="alice", updated_by="alice")
        with self.assertNumQueries(1):
            response = conversation_resources.ListConversations().request(**self.scope)
        rows = {row["uid"]: row for row in response}
        self.assertEqual(len(rows), 7)
        self.assertEqual(rows[str(self.conversation.uid)]["attachment_count"], 3)
        self.assertEqual(rows[str(self.conversation.uid)]["attachment_counts_by_type"]["AI_ANALYSIS"], 3)
        self.assertEqual(sum(row["attachment_count"] for row in response), 3)
