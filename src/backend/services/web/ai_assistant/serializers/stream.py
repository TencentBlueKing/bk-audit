from rest_framework import serializers

from services.web.ai_assistant.constants import StreamArchiveStatus
from services.web.ai_assistant.schemas.stream import UIStreamEventDrfSerializer


class AttachmentStreamRequestSerializer(serializers.Serializer):
    """SSE 订阅参数；execution_id 防止把旧执行游标用于新 Redis Stream。"""

    attachment_uid = serializers.UUIDField(help_text="流式附件对外 UUID")
    execution_id = serializers.UUIDField(help_text="快照返回的流执行代际；换流后服务端返回 stream_reset")
    last_stream_id = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="Redis Stream 增量游标；最终生效的 Last-Event-ID Header 或 query 游标由服务端统一校验",
    )


class AttachmentStreamSnapshotResponseSerializer(serializers.Serializer):
    """已持久化事件快照；不暴露 Redis key 等内部流配置。"""

    # 直接复用 Pydantic 事件协议绑定的 DRF Serializer，避免两份字段定义漂移。
    events = UIStreamEventDrfSerializer(many=True, help_text="当前执行已持久化的事件快照")
    execution_id = serializers.UUIDField(allow_null=True, help_text="当前流执行代际；建立 SSE 时须原样传回")
    latest_stream_id = serializers.CharField(allow_null=True, help_text="快照中最新可用 Redis 游标")
    archive_status = serializers.ChoiceField(
        choices=StreamArchiveStatus.choices, help_text="快照完整性状态；非 COMPLETE 表示存在降级或截断"
    )
