from collections.abc import Iterator

from django.http import StreamingHttpResponse
from django.utils.translation import gettext_lazy

from core.models import get_request_username
from services.web.ai_assistant.resources.conversation import AIAssistantResource
from services.web.ai_assistant.schemas import UIStreamEvent
from services.web.ai_assistant.serializers.attachment import (
    AttachmentDetailRequestSerializer,
)
from services.web.ai_assistant.serializers.stream import (
    AttachmentStreamRequestSerializer,
    AttachmentStreamSnapshotResponseSerializer,
)
from services.web.ai_assistant.services.attachment_stream import AttachmentStreamService
from services.web.ai_assistant.streaming.sse import (
    encode_sse_event,
    encode_sse_heartbeat,
)

# Last-Event-ID 是 EventSource 断线重连时自动补发的标准 Header。
LAST_EVENT_ID_HEADER = "HTTP_LAST_EVENT_ID"


class GetAttachmentStreamSnapshot(AIAssistantResource):
    """获取流式附件已持久化的事件快照，供首次进入或收到 reset 后重建 UI。"""

    name = gettext_lazy("获取附件流快照")
    RequestSerializer = AttachmentDetailRequestSerializer
    ResponseSerializer = AttachmentStreamSnapshotResponseSerializer

    def perform_request(self, validated_request_data):
        snapshot = AttachmentStreamService(user=get_request_username()).get_snapshot(
            attachment_uid=str(validated_request_data["attachment_uid"]),
        )
        # Response Serializer 不识别 Pydantic 对象，这里显式转为 JSON 兼容结构。
        return snapshot.model_dump(mode="json")


class GetAttachmentStream(AIAssistantResource):
    """供原生 EventSource 订阅附件实时增量，支持 Last-Event-ID 游标续传；300 秒无业务事件会主动关闭。

    服务端会发送 heartbeat，前端 onerror 应关闭旧 EventSource、重新查询详情和
    快照，并且仅当附件仍为 PROCESSING 时才重连；命名平台事件可用 addEventListener 接收。
    """

    name = gettext_lazy("订阅附件流")
    bind_request = True
    RequestSerializer = AttachmentStreamRequestSerializer

    def perform_request(self, validated_request_data):
        request = validated_request_data.pop("_request", None)
        last_stream_id = self._resolve_cursor(
            request=request, query_cursor=validated_request_data.get("last_stream_id")
        )
        # Header/query 优先级决议完成后再校验，避免低优先级 query 抢先拒绝请求。
        last_stream_id = AttachmentStreamService.normalize_cursor(last_stream_id)
        events = AttachmentStreamService(user=get_request_username()).iter_events(
            attachment_uid=str(validated_request_data["attachment_uid"]),
            execution_id=validated_request_data["execution_id"],
            last_stream_id=last_stream_id,
        )
        response = StreamingHttpResponse(self._encode(events), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        # 显式关闭反向代理缓冲，否则事件会被攒批后才下发，失去流式意义。
        response["X-Accel-Buffering"] = "no"
        return response

    @staticmethod
    def _resolve_cursor(*, request, query_cursor: str | None) -> str | None:
        """Header 游标优先于 query；空白 Header 视为未提供。"""

        header_cursor = (request.META.get(LAST_EVENT_ID_HEADER) or "").strip() if request else ""
        return header_cursor or query_cursor

    @staticmethod
    def _encode(events: Iterator[UIStreamEvent | None]) -> Iterator[bytes]:
        """把事件迭代器转为 SSE 字节流；``None`` 编码为心跳。"""

        try:
            for event in events:
                yield encode_sse_heartbeat() if event is None else encode_sse_event(event)
        finally:
            close = getattr(events, "close", None)
            if callable(close):
                close()
