# -*- coding: utf-8 -*-
"""
AI Markdown rendering helpers.

Use HTML escaping to prevent raw HTML injection from AI outputs.
"""

import mistune

_AI_MARKDOWN = mistune.create_markdown(
    escape=True,
    renderer="html",
    plugins=["strikethrough", "footnotes", "table"],
)


def render_ai_markdown(text: str) -> str:
    if not text:
        return ""
    return _AI_MARKDOWN(text)
