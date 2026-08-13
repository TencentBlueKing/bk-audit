import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy

from core.models import OperateRecordModel, SoftDeleteModel
from services.web.ai_assistant.constants import (
    DEFAULT_CONVERSATION_TITLE,
    AttachmentType,
    ExecutionStatus,
    FeedbackSourceType,
    FeedbackType,
    MessageType,
    SidebarNodeType,
)


class ExternalUIDModel(models.Model):
    """为平台对外接口提供不可枚举的 UUIDv4 标识。"""

    uid = models.UUIDField(gettext_lazy("外部 ID"), default=uuid.uuid4, editable=False, unique=True)

    class Meta:
        abstract = True


class ExecutionSnapshotModel(models.Model):
    """消息和附件共享的最小执行快照，不包含所有者和任务调度逻辑。"""

    status = models.CharField(
        gettext_lazy("执行状态"),
        max_length=32,
        choices=ExecutionStatus.choices,
        default=ExecutionStatus.PROCESSING,
        db_index=True,
    )
    task_id = models.CharField(gettext_lazy("任务 ID"), max_length=64, null=True, blank=True, db_index=True)
    input_data = models.JSONField(gettext_lazy("输入快照"), default=dict)
    context_data = models.JSONField(gettext_lazy("上下文快照"), default=dict)
    output_data = models.JSONField(gettext_lazy("输出快照"), default=None, null=True, blank=True)
    error_code = models.CharField(gettext_lazy("错误码"), max_length=64, default="", blank=True)
    error_message = models.TextField(gettext_lazy("脱敏错误信息"), default="", blank=True)

    class Meta:
        abstract = True


class ConversationGroup(ExternalUIDModel, OperateRecordModel):
    """用户可创建的会话分组，侧栏位置由对应 Node 维护。"""

    name = models.CharField(gettext_lazy("分组名称"), max_length=64)

    class Meta:
        verbose_name = gettext_lazy("AI 助手会话分组")
        verbose_name_plural = verbose_name


class Conversation(ExternalUIDModel, SoftDeleteModel):
    """AI 助手会话，仅承担历史记录和消息容器职责。"""

    title = models.CharField(gettext_lazy("会话标题"), max_length=255, default=DEFAULT_CONVERSATION_TITLE)

    class Meta:
        verbose_name = gettext_lazy("AI 助手会话")
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(
                fields=["created_by", "is_deleted", "updated_at", "id"],
                name="ai_conv_owner_list_idx",
            )
        ]


class ConversationSidebarNode(OperateRecordModel):
    """统一表达分组、会话在侧栏中的层级、顺序和置顶状态。"""

    node_type = models.CharField(gettext_lazy("节点类型"), max_length=32, choices=SidebarNodeType.choices)
    group = models.OneToOneField(
        ConversationGroup,
        verbose_name=gettext_lazy("分组"),
        related_name="sidebar_node",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    conversation = models.OneToOneField(
        Conversation,
        verbose_name=gettext_lazy("会话"),
        related_name="sidebar_node",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    # 仅会话节点可指向分组节点；根列表中的节点保持为空。
    parent_node = models.ForeignKey(
        "self",
        verbose_name=gettext_lazy("父节点"),
        related_name="children",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    # 同一容器内 position 越大越靠前，业务服务负责维护连续整数。
    position = models.PositiveBigIntegerField(gettext_lazy("排序位置"), default=0)
    # 置顶是会话节点的独立展示维度，不改变节点所在容器及 position。
    pinned_at = models.DateTimeField(gettext_lazy("置顶时间"), null=True, blank=True)

    class Meta:
        verbose_name = gettext_lazy("AI 助手侧栏节点")
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(
                fields=["created_by", "parent_node", "position", "id"],
                name="ai_node_container_pos_idx",
            ),
            models.Index(fields=["created_by", "pinned_at", "id"], name="ai_node_pinned_idx"),
        ]

    def clean(self):
        """防御性校验节点的静态关系，排序和权限由领域服务处理。"""

        super().clean()
        errors = {}
        if self.node_type == SidebarNodeType.GROUP:
            if not self.group_id:
                errors["group"] = gettext_lazy("分组节点必须关联分组")
            if self.conversation_id:
                errors["conversation"] = gettext_lazy("分组节点不能关联会话")
            if self.parent_node_id:
                errors["parent_node"] = gettext_lazy("分组节点只能位于根列表")
            if self.pinned_at:
                errors["pinned_at"] = gettext_lazy("分组节点不能置顶")
            if self.group_id:
                try:
                    group = self.group
                except ConversationGroup.DoesNotExist:
                    errors["group"] = gettext_lazy("关联分组不存在")
                else:
                    if group.created_by != self.created_by:
                        errors["group"] = gettext_lazy("节点与分组必须属于同一用户")
        elif self.node_type == SidebarNodeType.CONVERSATION:
            if not self.conversation_id:
                errors["conversation"] = gettext_lazy("会话节点必须关联会话")
            if self.group_id:
                errors["group"] = gettext_lazy("会话节点不能直接关联分组")
            if self.conversation_id:
                try:
                    conversation = self.conversation
                except Conversation.DoesNotExist:
                    errors["conversation"] = gettext_lazy("关联会话不存在")
                else:
                    if conversation.created_by != self.created_by:
                        errors["conversation"] = gettext_lazy("节点与会话必须属于同一用户")
            if self.parent_node_id:
                try:
                    parent_node = self.parent_node
                except ConversationSidebarNode.DoesNotExist:
                    errors["parent_node"] = gettext_lazy("父节点不存在")
                else:
                    if parent_node.node_type != SidebarNodeType.GROUP:
                        errors["parent_node"] = gettext_lazy("会话节点的父节点必须是分组节点")
                    elif parent_node.created_by != self.created_by:
                        errors["parent_node"] = gettext_lazy("父节点与会话节点必须属于同一用户")

        if errors:
            raise ValidationError(errors)


class Message(ExternalUIDModel, OperateRecordModel, ExecutionSnapshotModel):
    """记录一次用户输入及其平台输出，类型专属内容存放在 JSON 快照中。"""

    conversation = models.ForeignKey(
        Conversation,
        verbose_name=gettext_lazy("所属会话"),
        related_name="messages",
        on_delete=models.CASCADE,
    )
    # 父消息只表达业务因果关系，不决定前端是否合并展示。
    parent_message = models.ForeignKey(
        "self",
        verbose_name=gettext_lazy("父消息"),
        related_name="child_messages",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    message_type = models.CharField(gettext_lazy("消息类型"), max_length=32, choices=MessageType.choices)

    class Meta:
        verbose_name = gettext_lazy("AI 助手消息")
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=["conversation", "id"], name="ai_msg_conversation_idx"),
            models.Index(
                fields=["parent_message", "message_type", "id"],
                name="ai_msg_parent_type_idx",
            ),
            models.Index(fields=["status", "task_id"], name="ai_msg_task_idx"),
            models.Index(fields=["status", "updated_at", "id"], name="ai_msg_status_time_idx"),
        ]


class Attachment(ExternalUIDModel, OperateRecordModel, ExecutionSnapshotModel):
    """日志检索消息派生的统计、分析等类型化产物。"""

    source_message = models.ForeignKey(
        Message,
        verbose_name=gettext_lazy("来源消息"),
        related_name="attachments",
        on_delete=models.CASCADE,
    )
    attachment_type = models.CharField(gettext_lazy("附件类型"), max_length=32, choices=AttachmentType.choices)
    title = models.CharField(gettext_lazy("标题"), max_length=255, default="", blank=True)
    content_updated_at = models.DateTimeField(gettext_lazy("内容更新时间"), null=True, blank=True, db_index=True)
    is_stream = models.BooleanField(gettext_lazy("是否流式执行"), default=False)
    stream_config = models.JSONField(gettext_lazy("流式配置"), default=dict)
    # 保存已确认需要归档的完整事件对象，具体 AG-UI 协议由业务模块定义。
    stream_archive = models.JSONField(gettext_lazy("流式事件归档"), default=list, blank=True)

    class Meta:
        verbose_name = gettext_lazy("AI 助手附件")
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=["source_message", "id"], name="ai_att_source_idx"),
            models.Index(fields=["status", "task_id"], name="ai_att_task_idx"),
            models.Index(fields=["status", "updated_at", "id"], name="ai_att_status_time_idx"),
            models.Index(
                fields=["created_by", "attachment_type", "status", "content_updated_at", "id"],
                name="ai_att_owner_type_idx",
            ),
        ]


class Feedback(ExternalUIDModel, OperateRecordModel):
    """用户对消息或附件的当前反馈，不建立历史版本。"""

    source_type = models.CharField(gettext_lazy("来源类型"), max_length=32, choices=FeedbackSourceType.choices)
    # 来源对象按类型动态关联，服务层负责归属和存在性校验。
    source_id = models.PositiveBigIntegerField(gettext_lazy("来源 ID"))
    feedback_type = models.CharField(gettext_lazy("反馈类型"), max_length=16, choices=FeedbackType.choices)
    comment = models.TextField(gettext_lazy("反馈说明"), default="", blank=True)

    class Meta:
        verbose_name = gettext_lazy("AI 助手反馈")
        verbose_name_plural = verbose_name
        constraints = [
            models.UniqueConstraint(
                fields=["created_by", "source_type", "source_id"],
                name="ai_feedback_user_source_uniq",
            )
        ]
        indexes = [models.Index(fields=["source_type", "source_id"], name="ai_feedback_source_idx")]
