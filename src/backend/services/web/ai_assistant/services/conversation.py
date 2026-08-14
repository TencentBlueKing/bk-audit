from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import QuerySet, Subquery
from django.utils import timezone

from services.web.ai_assistant.constants import (
    SIDEBAR_NODE_DELETE_BATCH_SIZE,
    SidebarNodeType,
)
from services.web.ai_assistant.exceptions import (
    ConversationGroupNotFound,
    ConversationNotFound,
)
from services.web.ai_assistant.models import (
    Conversation,
    ConversationGroup,
    ConversationSidebarNode,
)
from services.web.ai_assistant.services.sidebar import ConversationSidebarService


class ConversationService:
    """统一编排会话/分组与侧栏 Node 的生命周期事务。"""

    def __init__(self, *, user: str):
        """绑定当前操作用户，同一次领域调用不再重复传递 user。"""

        self.user = user
        self.sidebar_service = ConversationSidebarService(user=user)

    @transaction.atomic
    def create_group(self, *, name: str) -> ConversationGroup:
        """创建空分组并将其 Node 插入根列表最前。"""

        group = ConversationGroup.objects.create(name=name, created_by=self.user, updated_by=self.user)
        self.sidebar_service.create_node(group=group)
        return group

    def rename_group(self, *, group_uid: str, name: str) -> ConversationGroup:
        """重命名当前用户分组，并发修改按最后写入生效。"""

        group = self._get_group(group_uid=group_uid)
        group.name = name
        group.updated_at = timezone.now()
        group.updated_by = self.user
        group.save(update_record=False, update_fields=["name", "updated_by", "updated_at"])
        return group

    @transaction.atomic
    def delete_group(self, *, group_uid: str) -> None:
        """软删除组内会话，再物理删除分组和完整 Node 子树。"""

        group = self._get_group(group_uid=group_uid, for_update=True)
        child_nodes = ConversationSidebarNode.objects.filter(
            parent_node__group=group,
            created_by=self.user,
            conversation_id__isnull=False,
        )
        # 显式子查询避免 MySQL 对跨表 UPDATE 先将全部会话主键拉到 Python 内存。
        Conversation.objects.filter(
            created_by=self.user,
            id__in=Subquery(child_nodes.values("conversation_id")),
        ).delete()
        # 先分批删除会话 Node，避免 group.delete() 的 Collector 一次物化整个分组。
        self._delete_nodes_in_batches(child_nodes)
        # 此时 CASCADE Collector 只需处理分组和单个 Group Node；会话本体仅软删除。
        group.delete()

    @transaction.atomic
    def create_conversation(self) -> Conversation:
        """创建默认标题会话并将其 Node 插入根列表最前。"""

        conversation = Conversation.objects.create(created_by=self.user, updated_by=self.user)
        self.sidebar_service.create_node(conversation=conversation)
        return conversation

    def get_conversation(self, *, conversation_uid: str) -> Conversation:
        """获取当前用户的未删除会话。"""

        return self._get_conversation(conversation_uid=conversation_uid)

    def rename_conversation(self, *, conversation_uid: str, title: str) -> Conversation:
        """重命名当前用户会话，并发修改按最后写入生效。"""

        conversation = self._get_conversation(conversation_uid=conversation_uid)
        conversation.title = title
        conversation.updated_at = timezone.now()
        conversation.updated_by = self.user
        conversation.save(update_record=False, update_fields=["title", "updated_by", "updated_at"])
        return conversation

    @transaction.atomic
    def delete_conversation(self, *, conversation_uid: str) -> None:
        """软删除会话并物理删除 Node，一期不提供恢复。"""

        conversation = self._get_conversation(conversation_uid=conversation_uid, for_update=True)
        Conversation.objects.filter(id=conversation.id, created_by=self.user).delete()
        ConversationSidebarNode.objects.filter(conversation=conversation, created_by=self.user).delete()

    @transaction.atomic
    def clear_conversations(self) -> None:
        """清空当前用户的会话和会话 Node，保留分组及空分组 Node。"""

        Conversation.objects.filter(created_by=self.user).delete()
        self._delete_nodes_in_batches(
            ConversationSidebarNode.objects.filter(
                created_by=self.user,
                node_type=SidebarNodeType.CONVERSATION,
            )
        )

    @staticmethod
    def _delete_nodes_in_batches(queryset: QuerySet[ConversationSidebarNode]) -> None:
        """分批物理删除 Node，将 Django Collector 的单次内存占用限制在固定范围。"""

        while node_ids := list(queryset.order_by("id").values_list("id", flat=True)[:SIDEBAR_NODE_DELETE_BATCH_SIZE]):
            ConversationSidebarNode.objects.filter(id__in=node_ids).delete()

    def _get_group(self, *, group_uid: str, for_update: bool = False) -> ConversationGroup:
        """按外部 UID 获取当前用户分组，删除链路可显式请求行锁。"""

        queryset = ConversationGroup.objects.filter(created_by=self.user)
        if for_update:
            queryset = queryset.select_for_update()
        try:
            group = queryset.filter(uid=group_uid).first()
        except DjangoValidationError as error:
            raise ConversationGroupNotFound() from error
        if group is None:
            raise ConversationGroupNotFound()
        return group

    def _get_conversation(
        self,
        *,
        conversation_uid: str,
        for_update: bool = False,
    ) -> Conversation:
        """按外部 UID 获取当前用户会话，删除链路可显式请求行锁。"""

        queryset = Conversation.objects.filter(created_by=self.user)
        if for_update:
            queryset = queryset.select_for_update()
        try:
            conversation = queryset.filter(uid=conversation_uid).first()
        except DjangoValidationError as error:
            raise ConversationNotFound() from error
        if conversation is None:
            raise ConversationNotFound()
        return conversation
