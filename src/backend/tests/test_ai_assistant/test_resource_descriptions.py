import inspect
from unittest import mock

import yaml
from django.test import SimpleTestCase, override_settings
from drf_spectacular.views import SpectacularAPIView
from rest_framework.test import APIRequestFactory

from services.web.ai_assistant.resources.stream import GetAttachmentStream
from services.web.ai_assistant.urls import router
from services.web.ai_assistant.views import (
    AttachmentsViewSet,
    ConversationSidebarNodesViewSet,
    ConversationsViewSet,
    MessagesViewSet,
)


class ResourceDescriptionTest(SimpleTestCase):
    def test_attachment_stream_description_explains_eventsource_reconnect(self):
        description = inspect.getdoc(GetAttachmentStream)

        for keyword in ("EventSource", "300 秒", "onerror", "PROCESSING", "addEventListener"):
            with self.subTest(keyword=keyword):
                self.assertIn(keyword, description)

    def test_every_resource_route_defines_own_description(self):
        # 直接使用生产路由注册表，保证后续新增 ViewSet 会自动进入接口描述门禁。
        for _, viewset_class, _ in router.registry:
            for route in viewset_class.resource_routes:
                resource_class = route.resource_class
                with self.subTest(viewset=viewset_class.__name__, resource=resource_class.__name__):
                    self.assertTrue(
                        inspect.getdoc(resource_class),
                        f"{resource_class.__name__} 缺少接口描述",
                    )
                    self.assertIsNotNone(
                        resource_class.__doc__,
                        f"{resource_class.__name__} 不能只继承资源基类描述",
                    )

    @override_settings(ROOT_URLCONF="urls")
    def test_key_openapi_operations_expose_frontend_facing_descriptions(self):
        request = APIRequestFactory().get("/api/schema/")
        request.user = mock.Mock(is_staff=True, is_authenticated=True)
        response = SpectacularAPIView.as_view()(request)
        response.render()
        paths = yaml.safe_load(response.content)["paths"]

        cases = (
            (
                "/api/v1/ai_assistant/conversations/",
                "post",
                "初始化消息",
                ConversationsViewSet,
            ),
            ("/api/v1/ai_assistant/messages/", "get", "锚点", MessagesViewSet),
            (
                "/api/v1/ai_assistant/messages/{message_uid}/retry/",
                "post",
                "原 UID",
                MessagesViewSet,
            ),
            (
                "/api/v1/ai_assistant/messages/{message_uid}/attachments/",
                "post",
                "成功消息",
                MessagesViewSet,
            ),
            (
                "/api/v1/ai_assistant/attachments/{attachment_uid}/retry/",
                "post",
                "原对象",
                AttachmentsViewSet,
            ),
            (
                "/api/v1/ai_assistant/attachments/{attachment_uid}/stream/snapshot/",
                "get",
                "快照",
                AttachmentsViewSet,
            ),
            (
                "/api/v1/ai_assistant/attachments/{attachment_uid}/stream/",
                "get",
                "续传",
                AttachmentsViewSet,
            ),
            (
                "/api/v1/ai_assistant/conversation_sidebar/nodes/move/",
                "post",
                "before",
                ConversationSidebarNodesViewSet,
            ),
        )
        for path, method, keyword, viewset_class in cases:
            with self.subTest(path=path, method=method):
                description = paths[path][method]["description"]
                self.assertIn(keyword, description)
                self.assertNotEqual(description, inspect.getdoc(viewset_class))
