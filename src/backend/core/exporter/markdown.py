"""跨业务复用的 AI Markdown 安全渲染工具。"""

import mistune

# 统一转义模型输出的原始 HTML，避免下游直接嵌入 PDF 或页面时发生注入。
_AI_MARKDOWN = mistune.create_markdown(
    escape=True,
    renderer="html",
    plugins=["strikethrough", "footnotes", "table"],
)


def render_ai_markdown(text: str) -> str:
    """将 AI Markdown 渲染为已转义的 HTML，空内容保持为空字符串。"""

    return _AI_MARKDOWN(text) if text else ""
