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
from services.web.ai_assistant.models import Attachment, Conversation, Message
from services.web.ai_assistant.resources import conversation as conversation_resources
from services.web.ai_assistant.resources.attachment import ListAttachments
from services.web.ai_assistant.serializers.attachment import (
    AttachmentListRequestSerializer,
)
from tests.base import TestCase
from tests.test_ai_assistant.handlers import (
    EchoAttachmentAsyncHandler,
    EchoAttachmentSyncHandler,
    use_attachment_handler,
)


class ListQueriesTest(TestCase):
    """真实资源请求确保筛选、排序、限量在序列化前完成。"""

    def setUp(self):
        """准备当前用户及其他用户会话，并隔离附件类型注册。"""
        for module in ("attachment", "conversation"):
            patcher = mock.patch(
                f"services.web.ai_assistant.resources.{module}.get_request_username", return_value="alice"
            )
            patcher.start()
            self.addCleanup(patcher.stop)
        use_attachment_handler(self, EchoAttachmentAsyncHandler())
        use_attachment_handler(self, EchoAttachmentSyncHandler())
        self.conversation = Conversation.objects.create(title="有报告", created_by="alice", updated_by="alice")
        self.empty = Conversation.objects.create(title="空会话", created_by="alice", updated_by="alice")
        self.other = Conversation.objects.create(title="他人会话", created_by="bob", updated_by="bob")
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
            response = ListAttachments().request(conversation_uid=str(self.conversation.uid), limit=1)
        self.assertEqual([item["uid"] for item in response], [str(self.first.uid)])
        response = ListAttachments().request(conversation_uid=str(self.conversation.uid))
        self.assertEqual([item["uid"] for item in response], [str(self.first.uid), str(self.second.uid)])

    def test_attachment_sort_before_limit_and_keyword(self):
        """消息块可按创建时间倒序，标题模糊搜索和限制数量可组合。"""
        response = ListAttachments().request(source_message_uid=str(self.source.uid), sort="-created_at", limit=1)
        self.assertEqual([item["uid"] for item in response], [str(self.second.uid)])
        response = ListAttachments().request(keyword="Alpha", sort="title", limit=1)
        self.assertEqual([item["uid"] for item in response], [str(self.first.uid)])

    def test_sort_formats_and_invalid_list_arguments(self):
        """复用排序字段支持CSV、数组、重复参数并拒绝任意数据库字段。"""
        for data in (
            {"sort": "title,-created_at"},
            {"sort": ["title", "-created_at"]},
            QueryDict("sort=title&sort=-created_at"),
        ):
            serializer = AttachmentListRequestSerializer(data=data)
            self.assertTrue(serializer.is_valid(), serializer.errors)
            self.assertEqual(serializer.validated_data["order_fields"], ["title", "-created_at"])
        for data in (
            {"limit": 0},
            {"limit": -1},
            {"limit": 101},
            {"sort": "source_message__created_by"},
            {"sort": "--title"},
        ):
            serializer = AttachmentListRequestSerializer(data=data)
            self.assertFalse(serializer.is_valid(), data)

    def test_sort_ties_use_stable_id_order(self):
        """显式排序字段相同仍有稳定顺序，避免limit窗口随机变化。"""
        Attachment.objects.filter(source_message=self.source).update(title="同名")
        response = ListAttachments().request(sort="title", limit=1)
        self.assertEqual([item["uid"] for item in response], [str(self.second.uid)])

    def test_conversations_are_flat_visible_and_filter_by_attachments(self):
        """全量列表不依赖侧栏节点，存在多个附件也不重复会话。"""
        with self.assertNumQueries(1):
            response = conversation_resources.ListConversations().request()
        self.assertEqual({item["uid"] for item in response}, {str(self.conversation.uid), str(self.empty.uid)})
        with self.assertNumQueries(1):
            response = conversation_resources.ListConversations().request(has_attachments=True)
        self.assertEqual([item["uid"] for item in response], [str(self.conversation.uid)])
        response = conversation_resources.ListConversations().request(has_attachments=False)
        self.assertEqual([item["uid"] for item in response], [str(self.empty.uid)])
        self.conversation.delete()
        self.assertEqual(conversation_resources.ListConversations().request(has_attachments=True), [])

    def test_conversation_attachment_type_filters_existence(self):
        """类型筛选只按本用户该类型附件判断，反向筛选也是相同语义。"""
        response = conversation_resources.ListConversations().request(attachment_type=AttachmentType.FIELD_STATISTICS)
        self.assertEqual(response, [])
        response = conversation_resources.ListConversations().request(
            has_attachments=False, attachment_type=AttachmentType.AI_ANALYSIS
        )
        self.assertEqual([item["uid"] for item in response], [str(self.empty.uid)])
        response = conversation_resources.ListConversations().request(
            has_attachments=True, attachment_type="FIELD_STATISTICS,AI_ANALYSIS"
        )
        self.assertEqual([item["uid"] for item in response], [str(self.conversation.uid)])
        Attachment.objects.filter(id__in=[self.first.id, self.second.id]).update(created_by="bob")
        self.assertEqual(conversation_resources.ListConversations().request(has_attachments=True), [])

    def test_get_routes_return_arrays_and_limit_in_sql(self):
        """真实GET路由保持数组响应，重复sort参数和limit落到数据库。"""
        factory = APIRequestFactory()
        user = mock.Mock(username="alice", is_authenticated=True)
        path = "/api/v1/ai_assistant/attachments/"
        request = factory.get(path + "?sort=-created_at&sort=title&limit=1")
        force_authenticate(request, user=user)
        with CaptureQueriesContext(connection) as captured:
            response = resolve(path).func(request)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([item["uid"] for item in response.data], [str(self.second.uid)])
        self.assertTrue(any("LIMIT 1" in query["sql"].upper() for query in captured), captured.captured_queries)
        path = "/api/v1/ai_assistant/conversations/"
        request = factory.get(path, {"has_attachments": "true", "attachment_type": "AI_ANALYSIS"})
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
                request = APIRequestFactory().get(path, params)
                force_authenticate(request, user=mock.Mock(username="alice", is_authenticated=True))
                response = resolve(path).func(request)
                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual([item["uid"] for item in response.data], expected)
