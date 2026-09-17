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
    """获取流式附件的持久化过程快照，用于首次打开、刷新或 reset 后恢复 UI。

    ### Case：为 AI 统计展示生成过程

    先读附件详情；仅需要最终产物时直接轮询详情，不必调用本接口。
    选择过程展示时，恢复 events，保存 execution_id 和 latest_stream_id；
    execution_id 为空表示尚未启动，应等待后重读。使用同一快照的标识和游标订阅 SSE，
    latest_stream_id 为空时省略 SSE 的 last_stream_id 参数。
    重试期间可能暂时返回旧快照，须等待新的 execution_id，不能复用旧执行的结束状态。
    """

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

    ### Case：从快照继续接收过程

    `GET /api/v1/ai_assistant/attachments/{attachment_uid}/stream/`，查询参数：
    `execution_id={execution_id}&last_stream_id={latest_stream_id}`

    两个标识取自同一次快照，游标为空时省略 last_stream_id；Last-Event-ID Header 优先于查询游标。
    本接口返回 text/event-stream，不是普通 JSON。platform.stream_end 后关闭连接并读取附件详情；
    platform.stream_reset 后重新获取快照。Agent 消息结束事件不代表附件成功。
    仅需最终产物时无需调用本接口，可直接轮询附件详情。

    服务端会发送 heartbeat，前端 onerror 应关闭旧 EventSource、重新查询详情和
    快照，并且仅当附件仍为 PROCESSING 时才重连；命名平台事件可用 addEventListener 接收。
    """

    name = gettext_lazy("订阅附件流")
    bind_request = True
    RequestSerializer = AttachmentStreamRequestSerializer

    def validate_request_data(self, request_data):
        """使用 DRF 参数错误返回 400，避免缺失执行代际被资源层包装为 500。"""
        self._request_serializer = self.RequestSerializer(data=request_data, many=self.many_request_data)
        self._request_serializer.is_valid(raise_exception=True)
        return self._request_serializer.validated_data

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
