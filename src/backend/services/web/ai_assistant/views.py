from bk_resource.viewsets import ResourceRoute, ResourceViewSet
from blueapps.contrib.drf.utils.pagination import CustomPageNumberPagination
from drf_spectacular.types import OpenApiTypes

from core.utils.spectacular import BKResourceAutoSchema
from services.web.ai_assistant.constants import ScopePermissionSource
from services.web.ai_assistant.permissions import AIAssistantScopePermission
from services.web.ai_assistant.renderers import EventStreamRenderer
from services.web.ai_assistant.resources.attachment import (
    CreateAttachment,
    ExportAttachment,
    GetAttachment,
    ListAttachments,
    RetryAttachment,
    UpdateAttachment,
)
from services.web.ai_assistant.resources.column import (
    ApplyColumnConfig,
    ListColumnConfig,
)
from services.web.ai_assistant.resources.conversation import (
    ClearConversations,
    CreateConversation,
    CreateConversationGroup,
    DeleteConversation,
    DeleteConversationGroup,
    GetConversation,
    ListConversations,
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
    UpdateMessage,
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


class AIAssistantScopeViewSet(ResourceViewSet):
    """为 AI 资源路由附加统一的 HTTP Scope 权限入口。"""

    scope_permission_map = {}

    def get_permissions(self):
        """保留既有权限类并附加 AI 会话 Scope 权限。"""

        return [*super().get_permissions(), AIAssistantScopePermission()]


class AIAssistantPaginatedViewSet(AIAssistantScopeViewSet):
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


class ConversationGroupsViewSet(AIAssistantScopeViewSet):
    """会话分组生命周期接口。"""

    lookup_field = "group_uid"
    scope_permission_map = {
        "create": ScopePermissionSource.REQUEST,
        "partial_update": ScopePermissionSource.GROUP,
        "destroy": ScopePermissionSource.GROUP,
    }
    resource_routes = [
        ResourceRoute("POST", CreateConversationGroup),
        ResourceRoute("PATCH", UpdateConversationGroup, pk_field="group_uid"),
        ResourceRoute("DELETE", DeleteConversationGroup, pk_field="group_uid"),
    ]


class ConversationsViewSet(AIAssistantScopeViewSet):
    """会话生命周期及全量摘要查询接口。"""

    pagination_class = None

    lookup_field = "conversation_uid"
    scope_permission_map = {
        "create": ScopePermissionSource.REQUEST,
        "list": ScopePermissionSource.QUERY,
        "retrieve": ScopePermissionSource.CONVERSATION,
        "partial_update": ScopePermissionSource.CONVERSATION,
        "destroy": ScopePermissionSource.CONVERSATION,
        "clear": ScopePermissionSource.REQUEST,
    }
    resource_routes = [
        ResourceRoute("POST", CreateConversation),
        ResourceRoute("GET", ListConversations),
        ResourceRoute("GET", GetConversation, pk_field="conversation_uid"),
        ResourceRoute("PATCH", UpdateConversation, pk_field="conversation_uid"),
        ResourceRoute("DELETE", DeleteConversation, pk_field="conversation_uid"),
        ResourceRoute("POST", ClearConversations, endpoint="clear"),
    ]


class MessagesViewSet(AIAssistantScopeViewSet):
    """消息创建、历史窗口和异步状态轮询接口。"""

    lookup_field = "message_uid"
    scope_permission_map = {
        "create": ScopePermissionSource.CONVERSATION,
        "list": ScopePermissionSource.CONVERSATION,
        "attachments": ScopePermissionSource.ATTACHMENT_SOURCE,
        **{
            action: ScopePermissionSource.MESSAGE
            for action in ("retrieve", "partial_update", "retry", "preview-export", "full-export")
        },
    }
    resource_routes = [
        ResourceRoute("POST", CreateMessage),
        ResourceRoute("GET", ListMessages),
        ResourceRoute("GET", GetMessage, pk_field="message_uid"),
        ResourceRoute("PATCH", UpdateMessage, pk_field="message_uid"),
        ResourceRoute("POST", RetryMessage, endpoint="retry", pk_field="message_uid"),
        ResourceRoute("POST", CreateAttachment, endpoint="attachments", pk_field="message_uid"),
        ResourceRoute("GET", PreviewExportMessage, endpoint="preview-export", pk_field="message_uid"),
        ResourceRoute("POST", CreateMessageFullExport, endpoint="full-export", pk_field="message_uid"),
    ]


class AttachmentsViewSet(AIAssistantScopeViewSet):
    """附件创建后的查询、编辑、重试和流式订阅接口。"""

    schema = AttachmentAutoSchema()
    pagination_class = None
    lookup_field = "attachment_uid"
    scope_permission_map = {
        "list": ScopePermissionSource.QUERY,
        **{
            action: ScopePermissionSource.ATTACHMENT
            for action in ("retrieve", "partial_update", "retry", "export", "stream/snapshot", "stream")
        },
    }
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


class FeedbackViewSet(AIAssistantScopeViewSet):
    """当前用户对成功消息或附件的反馈写入与取消接口。"""

    lookup_field = "feedback_uid"
    scope_permission_map = {"create": ScopePermissionSource.FEEDBACK_SOURCE, "destroy": ScopePermissionSource.FEEDBACK}
    resource_routes = [
        ResourceRoute("POST", UpsertFeedback),
        ResourceRoute("DELETE", DeleteFeedback, pk_field="feedback_uid"),
    ]


class ColumnConfigViewSet(ResourceViewSet):
    """AI 日志检索展示字段的自定义选择与跨设备同步接口（按用户隔离）。"""

    resource_routes = [
        ResourceRoute("GET", ListColumnConfig),
        ResourceRoute("POST", ApplyColumnConfig, endpoint="apply"),
    ]


class ConversationSidebarViewSet(AIAssistantPaginatedViewSet):
    """侧栏置顶列表和跨会话标题搜索。"""

    pagination_class = AIAssistantPageNumberPagination
    scope_permission_map = {"pinned": ScopePermissionSource.QUERY, "search": ScopePermissionSource.QUERY}
    page_response_serializers = {"search": ConversationSearchResponseSerializer}
    resource_routes = [
        ResourceRoute("GET", ListPinnedConversations, endpoint="pinned"),
        ResourceRoute("GET", SearchConversations, endpoint="search", enable_paginate=True),
    ]


class ConversationSidebarNodesViewSet(AIAssistantPaginatedViewSet):
    """根列表或组内 Node 的读取与顺序操作。"""

    pagination_class = AIAssistantPageNumberPagination
    scope_permission_map = {
        "list": ScopePermissionSource.QUERY,
        "move": ScopePermissionSource.SIDEBAR_NODE,
        "pin": ScopePermissionSource.CONVERSATION_NODE,
    }
    page_response_serializers = {"list": SidebarNodeResponseSerializer}
    resource_routes = [
        ResourceRoute("GET", ListConversationSidebarNodes, enable_paginate=True),
        ResourceRoute("POST", MoveConversationSidebarNode, endpoint="move"),
        ResourceRoute("PUT", PinConversationSidebarNode, endpoint="pin"),
    ]
