from bk_resource.viewsets import ResourceRoute, ResourceViewSet
from blueapps.contrib.drf.utils.pagination import CustomPageNumberPagination
from drf_spectacular.types import OpenApiTypes

from core.utils.spectacular import BKResourceAutoSchema
from services.web.ai_assistant.renderers import EventStreamRenderer
from services.web.ai_assistant.resources.attachment import (
    CreateAttachment,
    ExportAttachment,
    GetAttachment,
    ListAttachments,
    RetryAttachment,
    UpdateAttachment,
)
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
from services.web.ai_assistant.resources.feedback import DeleteFeedback, UpsertFeedback
from services.web.ai_assistant.resources.message import (
    CreateMessage,
    CreateMessageFullExport,
    GetMessage,
    ListMessages,
    PreviewExportMessage,
    RetryMessage,
)
from services.web.ai_assistant.resources.stream import (
    GetAttachmentStream,
    GetAttachmentStreamSnapshot,
)
from services.web.ai_assistant.serializers.conversation import (
    ConversationSearchResponseSerializer,
    SidebarNodeResponseSerializer,
)


class AIAssistantPageNumberPagination(CustomPageNumberPagination):
    """会话侧栏默认按 20 条懒加载，单次最多返回 100 条。"""

    page_size = 20
    max_page_size = 100


class AIAssistantPaginatedViewSet(ResourceViewSet):
    """先对 QuerySet 做数据库分页，再使用当前 action 对应 DTO 序列化。"""

    page_response_serializers = {}

    def paginate_queryset(self, queryset):
        page = super().paginate_queryset(queryset)
        serializer_class = self.page_response_serializers[self.action]
        return serializer_class(page, many=True).data


class AttachmentAutoSchema(BKResourceAutoSchema):
    """补充附件列表、即时文件导出和 SSE 订阅的专属 OpenAPI 响应协议。"""

    def _is_list_view(self, serializer=None):
        route = self._get_matched_route()
        if route and route.resource_class is ListAttachments:
            return True
        return super()._is_list_view(serializer)

    def get_response_serializers(self):
        """按实际 Content-Type 描述导出文件与事件流，避免被默认 JSON Renderer 误标。"""

        route = self._get_matched_route()
        if route and route.resource_class is ExportAttachment:
            return {
                (200, "text/markdown"): OpenApiTypes.BINARY,
                (200, "application/pdf"): OpenApiTypes.BINARY,
            }
        if route and route.resource_class is GetAttachmentStream:
            # SSE 是长连接文本流，没有一次性 JSON body 可供描述。
            return {(200, "text/event-stream"): OpenApiTypes.STR}
        return super().get_response_serializers()


class ConversationGroupsViewSet(ResourceViewSet):
    """会话分组生命周期接口。"""

    lookup_field = "group_uid"
    resource_routes = [
        ResourceRoute("POST", CreateConversationGroup),
        ResourceRoute("PATCH", UpdateConversationGroup, pk_field="group_uid"),
        ResourceRoute("DELETE", DeleteConversationGroup, pk_field="group_uid"),
    ]


class ConversationsViewSet(ResourceViewSet):
    """会话生命周期接口。"""

    lookup_field = "conversation_uid"
    resource_routes = [
        ResourceRoute("POST", CreateConversation),
        ResourceRoute("GET", GetConversation, pk_field="conversation_uid"),
        ResourceRoute("PATCH", UpdateConversation, pk_field="conversation_uid"),
        ResourceRoute("DELETE", DeleteConversation, pk_field="conversation_uid"),
        ResourceRoute("POST", ClearConversations, endpoint="clear"),
    ]


class MessagesViewSet(ResourceViewSet):
    """消息创建、历史窗口和异步状态轮询接口。"""

    lookup_field = "message_uid"
    resource_routes = [
        ResourceRoute("POST", CreateMessage),
        ResourceRoute("GET", ListMessages),
        ResourceRoute("GET", GetMessage, pk_field="message_uid"),
        ResourceRoute("POST", RetryMessage, endpoint="retry", pk_field="message_uid"),
        ResourceRoute("POST", CreateAttachment, endpoint="attachments", pk_field="message_uid"),
        ResourceRoute("GET", PreviewExportMessage, endpoint="preview-export", pk_field="message_uid"),
        ResourceRoute("POST", CreateMessageFullExport, endpoint="full-export", pk_field="message_uid"),
    ]


class AttachmentsViewSet(ResourceViewSet):
    """附件创建后的查询、编辑、重试和流式订阅接口。"""

    schema = AttachmentAutoSchema()
    pagination_class = None
    lookup_field = "attachment_uid"
    resource_routes = [
        ResourceRoute("GET", ListAttachments),
        ResourceRoute("GET", GetAttachment, pk_field="attachment_uid"),
        ResourceRoute("GET", ExportAttachment, endpoint="export", pk_field="attachment_uid"),
        ResourceRoute("GET", GetAttachmentStreamSnapshot, endpoint="stream/snapshot", pk_field="attachment_uid"),
        ResourceRoute("GET", GetAttachmentStream, endpoint="stream", pk_field="attachment_uid"),
        ResourceRoute("PATCH", UpdateAttachment, pk_field="attachment_uid"),
        ResourceRoute("POST", RetryAttachment, endpoint="retry", pk_field="attachment_uid"),
    ]

    def get_renderers(self):
        """SSE action 单独参与 ``text/event-stream`` 内容协商，其余接口保持统一 JSON。"""

        if self.action == "stream":
            return [EventStreamRenderer()]
        return super().get_renderers()


class FeedbackViewSet(ResourceViewSet):
    """当前用户对成功消息或附件的反馈写入与取消接口。"""

    lookup_field = "feedback_uid"
    resource_routes = [
        ResourceRoute("POST", UpsertFeedback),
        ResourceRoute("DELETE", DeleteFeedback, pk_field="feedback_uid"),
    ]


class ConversationSidebarViewSet(AIAssistantPaginatedViewSet):
    """侧栏置顶列表和跨会话标题搜索。"""

    pagination_class = AIAssistantPageNumberPagination
    page_response_serializers = {"search": ConversationSearchResponseSerializer}
    resource_routes = [
        ResourceRoute("GET", ListPinnedConversations, endpoint="pinned"),
        ResourceRoute("GET", SearchConversations, endpoint="search", enable_paginate=True),
    ]


class ConversationSidebarNodesViewSet(AIAssistantPaginatedViewSet):
    """根列表或组内 Node 的读取与顺序操作。"""

    pagination_class = AIAssistantPageNumberPagination
    page_response_serializers = {"list": SidebarNodeResponseSerializer}
    resource_routes = [
        ResourceRoute("GET", ListConversationSidebarNodes, enable_paginate=True),
        ResourceRoute("POST", MoveConversationSidebarNode, endpoint="move"),
        ResourceRoute("PUT", PinConversationSidebarNode, endpoint="pin"),
    ]
