from django.contrib import admin, messages

from services.web.ai_assistant.constants import ExecutionStatus
from services.web.ai_assistant.exceptions import AIAssistantException
from services.web.ai_assistant.models import (
    Attachment,
    Conversation,
    ConversationGroup,
    ConversationSidebarNode,
    Feedback,
    Message,
)
from services.web.ai_assistant.services.attachment import AttachmentService


class ReadOnlyCreateDeleteAdminMixin:
    """禁止 Admin 绕过领域服务创建或删除平台核心对象。"""

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ConversationGroup)
class ConversationGroupAdmin(ReadOnlyCreateDeleteAdminMixin, admin.ModelAdmin):
    list_display = ["id", "uid", "name", "created_by", "created_at", "updated_at"]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["=uid", "name", "created_by"]
    readonly_fields = ["id", "uid", "name", "created_by", "created_at", "updated_by", "updated_at"]


@admin.register(Conversation)
class ConversationAdmin(ReadOnlyCreateDeleteAdminMixin, admin.ModelAdmin):
    list_display = ["id", "uid", "title", "is_deleted", "created_by", "created_at", "updated_at"]
    list_filter = ["is_deleted", "created_at", "updated_at"]
    search_fields = ["=uid", "title", "created_by"]
    readonly_fields = [
        "id",
        "uid",
        "title",
        "is_deleted",
        "created_by",
        "created_at",
        "updated_by",
        "updated_at",
    ]


@admin.register(ConversationSidebarNode)
class ConversationSidebarNodeAdmin(ReadOnlyCreateDeleteAdminMixin, admin.ModelAdmin):
    list_display = [
        "id",
        "node_type",
        "group",
        "conversation",
        "parent_node",
        "position",
        "pinned_at",
        "created_by",
    ]
    list_filter = ["node_type", "pinned_at", "created_at"]
    search_fields = ["=group__uid", "=conversation__uid", "created_by"]
    readonly_fields = [
        "id",
        "node_type",
        "group",
        "conversation",
        "parent_node",
        "position",
        "pinned_at",
        "created_by",
        "created_at",
        "updated_by",
        "updated_at",
    ]


@admin.register(Message)
class MessageAdmin(ReadOnlyCreateDeleteAdminMixin, admin.ModelAdmin):
    list_display = [
        "id",
        "uid",
        "conversation",
        "parent_message",
        "message_type",
        "status",
        "task_id",
        "created_by",
        "created_at",
    ]
    list_filter = ["message_type", "status", "created_at", "updated_at"]
    search_fields = ["=uid", "=conversation__uid", "=parent_message__uid", "task_id", "created_by"]
    readonly_fields = [
        "id",
        "uid",
        "conversation",
        "parent_message",
        "message_type",
        "status",
        "task_id",
        "input_data",
        "context_data",
        "output_data",
        "error_code",
        "error_message",
        "queued_at",
        "started_at",
        "last_activity_at",
        "finished_at",
        "created_by",
        "created_at",
        "updated_by",
        "updated_at",
    ]


@admin.register(Attachment)
class AttachmentAdmin(ReadOnlyCreateDeleteAdminMixin, admin.ModelAdmin):
    actions = ["retry_attachments"]
    list_display = [
        "id",
        "uid",
        "source_message",
        "attachment_type",
        "title",
        "status",
        "is_stream",
        "content_updated_at",
        "created_by",
    ]
    list_filter = ["attachment_type", "status", "is_stream", "created_at", "updated_at"]
    search_fields = ["=uid", "=source_message__uid", "title", "task_id", "created_by"]
    readonly_fields = [
        "id",
        "uid",
        "source_message",
        "attachment_type",
        "title",
        "status",
        "task_id",
        "input_data",
        "context_data",
        "output_data",
        "error_code",
        "error_message",
        "queued_at",
        "started_at",
        "last_activity_at",
        "finished_at",
        "content_updated_at",
        "is_stream",
        "stream_config",
        "stream_archive",
        "created_by",
        "created_at",
        "updated_by",
        "updated_at",
    ]

    @admin.action(description="重试选中的失败附件", permissions=["change"])
    def retry_attachments(self, request, queryset):
        """按附件原用户身份提交重试，并将实际管理员记录到 Admin 操作日志。

        重试资格、快照复用、并发抢占和事务后投递均由领域服务负责；业务拒绝
        逐项提示，不影响其他选中附件。任务投递失败也计入未提交数量。
        """

        submitted = 0
        rejected = 0
        for attachment in queryset.only("uid", "created_by").iterator():
            try:
                retried = AttachmentService(user=attachment.created_by).retry(attachment_uid=str(attachment.uid))
            except AIAssistantException as error:
                rejected += 1
                self.message_user(request, f"附件 {attachment.uid} 未提交重试：{error}", level=messages.WARNING)
                continue
            self.log_change(request, retried, f"提交附件重试，task_id={retried.task_id}")
            if retried.status == ExecutionStatus.FAILED:
                rejected += 1
                self.message_user(request, f"附件 {attachment.uid} 重试投递失败：{retried.error_message}", level=messages.ERROR)
            else:
                submitted += 1
        self.message_user(
            request,
            f"已提交重试 {submitted} 个，未提交 {rejected} 个",
            level=messages.WARNING if rejected else messages.SUCCESS,
        )


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ["id", "uid", "source_type", "source_id", "feedback_type", "created_by", "created_at"]
    list_filter = ["source_type", "feedback_type", "created_at"]
    search_fields = ["=uid", "=source_id", "created_by", "comment"]
    # 来源和归属不可从 Admin 改写，避免反馈被转移到其他对象或用户。
    readonly_fields = ["uid", "source_type", "source_id", "created_by", "created_at", "updated_by", "updated_at"]
