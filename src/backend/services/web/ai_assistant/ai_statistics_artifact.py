"""从 assistant 最终正文中提取 AI 统计图表配置标签块。

本模块只做纯字符串标签切分，不解析 JSON 或图表 schema。
提取失败时抛出低基数原因枚举，异常消息不携带 Agent 原文。
"""

from services.web.ai_assistant.constants import AIStatisticsArtifactErrorReason


class AIStatisticsArtifactExtractionError(ValueError):
    """表示 AI 统计标签协议失败，不携带原始产物内容。"""

    def __init__(self, reason: AIStatisticsArtifactErrorReason) -> None:
        self.reason = reason
        super().__init__(reason.value)


def extract_ai_statistics_chart_config(content: str, *, start_tag: str, end_tag: str) -> str:
    """提取唯一标签块的内部原文，不解释内容格式。"""

    if content.count(start_tag) != 1:
        raise AIStatisticsArtifactExtractionError(AIStatisticsArtifactErrorReason.START_TAG_COUNT_INVALID)
    if content.count(end_tag) != 1:
        raise AIStatisticsArtifactExtractionError(AIStatisticsArtifactErrorReason.END_TAG_COUNT_INVALID)
    start_index = content.index(start_tag) + len(start_tag)
    end_index = content.index(end_tag)
    if end_index < start_index:
        raise AIStatisticsArtifactExtractionError(AIStatisticsArtifactErrorReason.TAG_ORDER_INVALID)
    extracted = content[start_index:end_index]
    if not extracted.strip():
        raise AIStatisticsArtifactExtractionError(AIStatisticsArtifactErrorReason.EMPTY_CONTENT)
    return extracted
