"""AI 会话 HTTP Scope 权限入口。

View 声明 action 的 Scope 来源，具体授权复用公共 ScopePermission。
对象按当前用户定位后读取持久化归属；Resource 继续负责业务协议和状态校验。
"""

from uuid import UUID

from rest_framework.exceptions import ValidationError as SerializerValidationError
from rest_framework.permissions import BasePermission

from apps.permission.handlers.actions.action import ActionEnum
from core.models import get_request_username
from services.web.ai_assistant.constants import (
    FeedbackSourceType,
    ScopePermissionSource,
    SidebarNodeType,
)
from services.web.ai_assistant.exceptions import (
    AttachmentNotFound,
    ConversationGroupNotFound,
    ConversationNotFound,
    FeedbackSourceNotFound,
    InvalidAttachmentSource,
    MessageNotFound,
    SidebarNodeNotFound,
)
from services.web.ai_assistant.models import (
    Attachment,
    Conversation,
    ConversationGroup,
    ConversationSidebarNode,
    Feedback,
    Message,
)
from services.web.ai_assistant.services.scope import normalize_concrete_scope
from services.web.common.constants import ScopeType
from services.web.common.scope_permission import ScopeContext, ScopePermission


class AIAssistantScopePermission(BasePermission):
    """按 action 声明定位用户对象的 Scope，并委托公共权限判定。"""

    def has_permission(self, request, view) -> bool:
        """在业务调用前鉴权；cross 查询的可见行由后续数据过滤决定。"""

        if request.method == "OPTIONS" or view.action is None:
            return True  # 元数据与不支持的方法不执行 Resource 业务。
        source = view.scope_permission_map[view.action]
        route = next(
            route
            for route in view.resource_routes
            if (
                route.endpoint
                or (
                    "retrieve"
                    if route.method == "GET" and route.pk_field
                    else view.EMPTY_ENDPOINT_METHODS[route.method]
                )
            )
            == view.action
        )
        # 按 ResourceRoute 取参，HEAD 沿用 GET；items() 与 QueryDict 字段取单值一致。
        request_params = request.query_params if route.method == "GET" else request.data
        params = dict(request_params.items())
        params.update(view.kwargs)
        # 复用接口字段标准化，避免 UUID 整数、字符串空白等造成鉴权与业务对象不一致。
        fields = route.resource_class.RequestSerializer().fields
        for name in (
            "scope_type",
            "scope_id",
            "source_type",
            "conversation_uid",
            "group_uid",
            "message_uid",
            "attachment_uid",
            "feedback_uid",
            "source_uid",
            "node_uid",
        ):
            if name in params and name in fields:
                try:
                    params[name] = fields[name].run_validation(params[name])
                except SerializerValidationError:
                    return True  # 原 Resource 序列化器统一返回协议错误，不进入业务。
        username = get_request_username()
        scope = self._resolve_scope(source=source, params=params, username=username)
        if scope is None or scope.is_cross_scope:
            return True
        action = ActionEnum.VIEW_SCENE if scope.is_scene_scope else ActionEnum.VIEW_SYSTEM
        ScopePermission(username=username).check_scope_entry(scope, action)
        return True

    def _resolve_scope(self, *, source: ScopePermissionSource, params: dict, username: str) -> ScopeContext | None:
        """从请求或本人对象解析 Scope；缺失、非法字段留给 Resource 序列化器。"""

        if source in {ScopePermissionSource.REQUEST, ScopePermissionSource.QUERY}:
            scope_type, scope_id = params.get("scope_type"), params.get("scope_id")
            if scope_type not in ScopeType.values:
                return None
            if not scope_id and scope_type not in {ScopeType.CROSS_SCENE, ScopeType.CROSS_SYSTEM}:
                return None
            scope = ScopeContext(scope_type=scope_type, scope_id=scope_id)
            if scope.is_cross_scope:
                return scope  # cross 写请求由各 Resource 的请求序列化器拒绝
            return normalize_concrete_scope(scope_type=scope_type, scope_id=scope_id)

        field = {
            ScopePermissionSource.CONVERSATION: "conversation_uid",
            ScopePermissionSource.GROUP: "group_uid",
            ScopePermissionSource.MESSAGE: "message_uid",
            ScopePermissionSource.ATTACHMENT_SOURCE: "message_uid",
            ScopePermissionSource.ATTACHMENT: "attachment_uid",
            ScopePermissionSource.FEEDBACK: "feedback_uid",
            ScopePermissionSource.FEEDBACK_SOURCE: "source_uid",
            ScopePermissionSource.CONVERSATION_NODE: "node_uid",
        }[source]
        try:
            uid = UUID(str(params[field]))
        except (KeyError, ValueError, TypeError, AttributeError):
            return None

        if source == ScopePermissionSource.CONVERSATION:
            return self._query_scope(
                Conversation.objects.filter(uid=uid, created_by=username, is_deleted=False),
                error=ConversationNotFound,
            )
        if source == ScopePermissionSource.GROUP:
            return self._query_scope(
                ConversationGroup.objects.filter(uid=uid, created_by=username), error=ConversationGroupNotFound
            )
        if source == ScopePermissionSource.CONVERSATION_NODE:
            if params.get("node_type") != SidebarNodeType.CONVERSATION:
                return None  # 非会话置顶由原请求序列化器拒绝，不提前定位错误类型的对象。
            return self._query_scope(
                ConversationSidebarNode.objects.filter(
                    conversation__uid=uid,
                    conversation__created_by=username,
                    conversation__is_deleted=False,
                    created_by=username,
                    node_type=SidebarNodeType.CONVERSATION,
                ),
                fields=("conversation__scope_type", "conversation__scope_id"),
                error=SidebarNodeNotFound,
            )
        if source == ScopePermissionSource.FEEDBACK:
            feedback = Feedback.objects.filter(uid=uid, created_by=username).values("source_type", "source_id").first()
            if feedback is None:
                raise FeedbackSourceNotFound()
            return self._source_scope(
                username=username,
                source_type=feedback["source_type"],
                lookup={"id": feedback["source_id"]},
                error=FeedbackSourceNotFound,
            )
        if source == ScopePermissionSource.FEEDBACK_SOURCE:
            if params.get("source_type") not in FeedbackSourceType.values:
                return None
            return self._source_scope(
                username=username, source_type=params["source_type"], lookup={"uid": uid}, error=FeedbackSourceNotFound
            )
        if source == ScopePermissionSource.ATTACHMENT_SOURCE:
            return self._source_scope(
                username=username,
                source_type=FeedbackSourceType.MESSAGE,
                lookup={"uid": uid},
                error=InvalidAttachmentSource,
            )
        return self._source_scope(
            username=username,
            source_type=FeedbackSourceType.MESSAGE
            if source == ScopePermissionSource.MESSAGE
            else FeedbackSourceType.ATTACHMENT,
            lookup={"uid": uid},
            error=MessageNotFound if source == ScopePermissionSource.MESSAGE else AttachmentNotFound,
        )

    def _source_scope(self, *, username: str, source_type: str, lookup: dict, error: type[Exception]) -> ScopeContext:
        """消息、附件与反馈统一追溯会话归属，保持来源对象的用户边界。"""

        if source_type == FeedbackSourceType.MESSAGE:
            queryset = Message.objects.filter(
                **lookup, created_by=username, conversation__created_by=username, conversation__is_deleted=False
            )
            fields = ("conversation__scope_type", "conversation__scope_id")
        else:
            queryset = Attachment.objects.filter(
                **lookup,
                created_by=username,
                source_message__conversation__created_by=username,
                source_message__conversation__is_deleted=False
            )
            fields = ("source_message__conversation__scope_type", "source_message__conversation__scope_id")
        return self._query_scope(queryset, fields=fields, error=error)

    @staticmethod
    def _query_scope(queryset, *, fields=("scope_type", "scope_id"), error: type[Exception]) -> ScopeContext:
        """仅查询 Scope 字段；对象不属于当前用户时返回原有不存在异常。"""

        pair = queryset.values_list(*fields).first()
        if pair is None:
            raise error()
        return normalize_concrete_scope(scope_type=pair[0], scope_id=pair[1])
