from bk_resource.viewsets import ResourceRoute, ResourceViewSet
from blueapps.contrib.drf.utils.pagination import CustomPageNumberPagination

from core.utils.spectacular import BKResourceAutoSchema
from services.web.ai_assistant.resources.attachment import (
    CreateAttachment,
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
from services.web.ai_assistant.resources.message import (
    CreateMessage,
    GetMessage,
    ListMessages,
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
    """修正附件列表的非分页数组响应 OpenAPI。"""

    def _is_list_view(self, serializer=None):
        route = self._get_matched_route()
        if route and route.resource_class is ListAttachments:
            return True
        return super()._is_list_view(serializer)


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
        ResourceRoute("POST", CreateAttachment, endpoint="attachments", pk_field="message_uid"),
    ]


class AttachmentsViewSet(ResourceViewSet):
    """附件创建后的查询、编辑和重试接口。"""

    schema = AttachmentAutoSchema()
    pagination_class = None
    lookup_field = "attachment_uid"
    resource_routes = [
        ResourceRoute("GET", ListAttachments),
        ResourceRoute("GET", GetAttachment, pk_field="attachment_uid"),
        ResourceRoute("PATCH", UpdateAttachment, pk_field="attachment_uid"),
        ResourceRoute("POST", RetryAttachment, endpoint="retry", pk_field="attachment_uid"),
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
