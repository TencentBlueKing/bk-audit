from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import QuerySet, Subquery
from django.utils import timezone

from services.web.ai_assistant.constants import SidebarNodeType
from services.web.ai_assistant.exceptions import (
    ConversationGroupNotFound,
    ConversationNotFound,
)
from services.web.ai_assistant.models import (
    Conversation,
    ConversationGroup,
    ConversationSidebarNode,
    Message,
)
from services.web.ai_assistant.services.message import MessageService
from services.web.ai_assistant.services.sidebar import ConversationSidebarService


@dataclass(frozen=True, slots=True)
class ConversationCreation:
    """会话创建的原子结果，初始化消息可为空。"""

    conversation: Conversation
    initial_message: Message | None


class ConversationService:
    """统一编排会话/分组与侧栏 Node 的生命周期事务。"""

    def __init__(self, *, user: str):
        """绑定当前操作用户，同一次领域调用不再重复传递 user。"""

        self.user = user
        self.sidebar_service = ConversationSidebarService(user=user)
        self.message_service = MessageService(user=user)

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
        # 删除和移动统一锁 Group Node。只有会话 Node 才允许以它为父节点，
        # 因此该精确行锁足以阻止删除过程中有会话移入或移出。
        ConversationSidebarNode.objects.select_for_update().filter(
            group=group,
            created_by=self.user,
        ).first()
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

    def create_conversation(
        self,
        *,
        title: str,
        initial_message: Mapping[str, Any] | None = None,
    ) -> ConversationCreation:
        """创建会话、根 Node 和可选初始化消息，数据库写入保持原子性。"""

        operation_time = timezone.now()
        conversation = Conversation(
            title=title,
            created_by=self.user,
            updated_by=self.user,
            updated_at=operation_time,
        )
        prepared = None
        if initial_message is not None:
            # Handler 可能访问外部元数据，必须在数据库事务开始前完成。
            prepared = self.message_service.prepare_initial(
                conversation=conversation,
                message_type=initial_message["message_type"],
                input_data=initial_message["input_data"],
            )

        with transaction.atomic():
            conversation.save(update_record=False, force_insert=True)
            self.sidebar_service.create_node(conversation=conversation)
            message = None
            if prepared is not None:
                message = self.message_service.create_prepared(
                    conversation=conversation,
                    prepared=prepared,
                )
        return ConversationCreation(conversation=conversation, initial_message=message)

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

        # clear 与消息/附件最终写入共用 Conversation 行锁；后续删除严格绑定这批
        # 初始 ID，避免 READ COMMITTED 下误删事务期间并发创建的新会话 Node。
        conversation_ids = list(
            Conversation.objects.select_for_update()
            .filter(created_by=self.user, is_deleted=False)
            .order_by("id")
            .values_list("id", flat=True)
        )
        Conversation.objects.filter(created_by=self.user, id__in=conversation_ids).delete()
        self._delete_nodes_in_batches(
            ConversationSidebarNode.objects.filter(
                created_by=self.user,
                node_type=SidebarNodeType.CONVERSATION,
                conversation_id__in=conversation_ids,
            )
        )

    @staticmethod
    def _delete_nodes_in_batches(queryset: QuerySet[ConversationSidebarNode]) -> None:
        """分批物理删除 Node，将 Django Collector 的单次内存占用限制在固定范围。"""

        batch_size = settings.AI_ASSISTANT_SIDEBAR_NODE_DELETE_BATCH_SIZE
        while node_ids := list(queryset.order_by("id").values_list("id", flat=True)[:batch_size]):
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
