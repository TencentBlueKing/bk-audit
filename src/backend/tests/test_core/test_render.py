# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

from jinja2 import TemplateAssertionError, UndefinedError

from core.render import Jinja2Renderer, VariableUndefined
from tests.base import TestCase


class TestJinja2Renderer(TestCase):
    def test_jinja_render_with_custom_undefined(self):
        template = "render: {{ title }} {{ test }}"
        context = {"title": "title_val"}
        renderer = Jinja2Renderer(undefined=VariableUndefined)
        actual = renderer.jinja_render(template, context)
        self.assertEqual(actual, "render: title_val (未获取到变量值:test)")

    def test_recursive_render(self):
        template = {"title": "Report for {{user.name}}", "details": ["ID: {{user.id}}"]}
        context = {"user": {"name": "Alice", "id": 123}}
        renderer = Jinja2Renderer()
        actual = renderer.jinja_render(template, context)
        self.assertEqual(actual, {"title": "Report for Alice", "details": ["ID: 123"]})

    def test_safe_filter_is_disallowed_by_default(self):
        """
        测试：默认情况下(allow_safe=False)，使用|safe过滤器会抛出异常
        """
        renderer = Jinja2Renderer()  # 默认 allow_safe=False
        with self.assertRaisesRegex(TemplateAssertionError, "No filter named 'safe'"):
            renderer.jinja_render("{{ '<br>' | safe }}", {})

    def test_special_char(self):
        """
        测试：特殊字符
        """

        template = "render: 游戏中文名: {{ 游戏中文名(game_name) }}"
        context = {"游戏中文名(game_name)": "王者荣耀"}
        renderer = Jinja2Renderer(undefined=VariableUndefined)
        with self.assertRaises(UndefinedError):
            renderer.jinja_render(template, context)

        template = """render: 游戏中文名: {{ event_data["游戏中文名 a(game_name」}）：:<>%%"] }}"""
        context = {"event_data": {"""游戏中文名 a(game_name」}）：:<>%%""": "xxx"}}
        renderer = Jinja2Renderer(undefined=VariableUndefined)
        actual = renderer.jinja_render(template, context)
        self.assertEqual(actual, "render: 游戏中文名: xxx")
