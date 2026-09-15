"""从透传的 AG-UI 事件中提取日志分析最终产物。

通用 Agent API 只负责完整转发 JSON 对象事件；本模块在日志分析业务边界解释
assistant 文本消息。只有收到 TEXT_MESSAGE_END 的消息才可成为最终报告，避免将
网络中断时的半截正文写入 Attachment。
"""

from django.conf import settings

from api.bk_plugins_ai_agent.agui import AGUIEventType


class LogAnalysisArtifactExtractor:
    """在固定内存预算内提取最后一条完整的 assistant 文本消息。

    日志分析只需要一个最终报告，因此新的 assistant START 会替换未闭合候选。
    正文使用 bytearray 紧凑缓冲，避免大量微小 delta 产生无界 Python 对象。
    """

    def __init__(self, max_content_bytes: int | None = None) -> None:
        self._active_message_id: str | None = None
        self._active_content = bytearray()
        self._max_content_bytes = (
            settings.AI_ASSISTANT_ATTACHMENT_MARKDOWN_MAX_BYTES if max_content_bytes is None else max_content_bytes
        )
        if self._max_content_bytes <= 0:
            raise ValueError("max_content_bytes must be positive")
        self._final_content = ""

    def _discard_active_message(self) -> None:
        """丢弃当前未闭合候选。"""

        self._active_message_id = None
        self._active_content.clear()

    def consume(self, event: dict) -> None:
        """消费一个业务事件；未知事件保持原样交给流归档而不参与产物提取。"""

        event_type = event.get("type")
        if event_type == AGUIEventType.RUN_ERROR:
            # 同一 HTTP 流可能继续承载上游重试事件，错误前的候选正文不能误判为成功产物。
            self._discard_active_message()
            self._final_content = ""
            return

        message_id = event.get("messageId")
        if not isinstance(message_id, str) or not message_id:
            return
        if event_type == AGUIEventType.TEXT_MESSAGE_START:
            role = event.get("role")
            if isinstance(role, str) and role.lower() == "assistant":
                self._active_message_id = message_id
                self._active_content.clear()
            elif message_id == self._active_message_id:
                self._discard_active_message()
            return
        if event_type == AGUIEventType.TEXT_MESSAGE_CONTENT:
            if message_id != self._active_message_id:
                return
            delta = event.get("delta")
            if isinstance(delta, str) and delta:
                delta_bytes = delta.encode("utf-8")
                if len(self._active_content) + len(delta_bytes) > self._max_content_bytes:
                    # 超限消息不再保留；后续合法新消息仍可成为最终产物。
                    self._discard_active_message()
                    self._final_content = ""
                    return
                self._active_content.extend(delta_bytes)
            return
        if event_type == AGUIEventType.TEXT_MESSAGE_END and message_id == self._active_message_id:
            self._final_content = self._active_content.decode("utf-8")
            self._discard_active_message()

    @property
    def buffered_content_bytes(self) -> int:
        """返回当前候选正文占用的字节数，供容量观测和测试使用。"""

        return len(self._active_content)

    @property
    def final_content(self) -> str:
        """返回最后一条完整正文；有效性及大小限制由输出快照模型统一校验。"""

        return self._final_content


__all__ = ["LogAnalysisArtifactExtractor"]
