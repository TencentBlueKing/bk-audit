# -*- coding: utf-8 -*-
"""
AI Markdown rendering helpers.

Use HTML escaping to prevent raw HTML injection from AI outputs.
"""

from core.exporter.markdown import render_ai_markdown

__all__ = ["render_ai_markdown"]
