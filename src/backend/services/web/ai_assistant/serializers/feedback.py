from django.conf import settings
from rest_framework import serializers

from services.web.ai_assistant.constants import FeedbackSourceType, FeedbackType


class FeedbackResponseSerializer(serializers.Serializer):
    """当前用户对单个消息或附件的公开反馈快照。"""

    uid = serializers.UUIDField(help_text="反馈对外 UUID")
    source_type = serializers.ChoiceField(choices=FeedbackSourceType.choices, help_text="反馈来源类型")
    source_uid = serializers.UUIDField(help_text="反馈来源对象 UUID")
    feedback_type = serializers.ChoiceField(choices=FeedbackType.choices, help_text="赞或踩")
    comment = serializers.CharField(allow_blank=True, help_text="可选反馈说明")
    created_at = serializers.DateTimeField(help_text="反馈创建时间")
    updated_at = serializers.DateTimeField(help_text="反馈最后更新时间")


class FeedbackUpsertRequestSerializer(serializers.Serializer):
    """创建或覆盖当前用户对单个来源对象的反馈。"""

    source_type = serializers.ChoiceField(choices=FeedbackSourceType.choices, help_text="反馈来源类型")
    source_uid = serializers.UUIDField(help_text="反馈来源对象 UUID")
    feedback_type = serializers.ChoiceField(choices=FeedbackType.choices, help_text="赞或踩")
    comment = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=settings.AI_ASSISTANT_FEEDBACK_COMMENT_MAX_LENGTH,
        help_text="可选反馈说明",
    )


class FeedbackDeleteRequestSerializer(serializers.Serializer):
    """取消当前用户自己的反馈。"""

    feedback_uid = serializers.UUIDField(help_text="待删除反馈 UUID")
