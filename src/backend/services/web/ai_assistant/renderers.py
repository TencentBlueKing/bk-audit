from core.utils.renderers import APIRenderer


class EventStreamRenderer(APIRenderer):
    """让 DRF 接受 SSE 请求；正常流由 ``StreamingHttpResponse`` 直接输出。"""

    media_type = "text/event-stream"
    format = "event-stream"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        """建流前发生异常时，继续返回平台统一的 JSON 错误结构。"""

        response = (renderer_context or {}).get("response")
        if response is not None:
            response["Content-Type"] = APIRenderer.media_type
        return super().render(data, APIRenderer.media_type, renderer_context)
