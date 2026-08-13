from django.contrib import admin

from services.web.ai_assistant.models import (
    Attachment,
    Conversation,
    ConversationGroup,
    ConversationSidebarNode,
    Feedback,
    Message,
)


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
        "created_by",
        "created_at",
        "updated_by",
        "updated_at",
    ]


@admin.register(Attachment)
class AttachmentAdmin(ReadOnlyCreateDeleteAdminMixin, admin.ModelAdmin):
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
        "content_updated_at",
        "is_stream",
        "stream_config",
        "stream_archive",
        "created_by",
        "created_at",
        "updated_by",
        "updated_at",
    ]


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ["id", "uid", "source_type", "source_id", "feedback_type", "created_by", "created_at"]
    list_filter = ["source_type", "feedback_type", "created_at"]
    search_fields = ["=uid", "=source_id", "created_by", "comment"]
    # 来源和归属不可从 Admin 改写，避免反馈被转移到其他对象或用户。
    readonly_fields = ["uid", "source_type", "source_id", "created_by", "created_at", "updated_by", "updated_at"]
