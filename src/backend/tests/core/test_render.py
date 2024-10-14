# -*- coding: utf-8 -*-
from core.render import Jinja2Renderer
from services.web.risk.render import RiskTitleUndefined
from tests.base import TestCase


class TestJinja2Render(TestCase):
    def test_jinja_render(self):
        template_value = "render: {{content.title}} {{content.content}} {{title}} {{test}}"
        context = {"content": {"title": "title", "content": "content"}, "title": "title"}
        actual = Jinja2Renderer(undefined=RiskTitleUndefined).jinja_render(template_value, context)
        assert actual == "render: title content title (未获取到变量值:test)"
