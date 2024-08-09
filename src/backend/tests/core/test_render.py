# -*- coding: utf-8 -*-

from core.render import jinja_render


def test_jinja_render():
    template_value = "render: {{content.title}} {{content.content}} {{title}}"
    context = {"content": {"title": "title", "content": "content"}, "title": "title"}
    actual = jinja_render(template_value, context)
    assert actual == "render: title content title"
