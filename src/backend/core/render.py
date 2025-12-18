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

from typing import Dict, List, Union

from django.utils import translation
from django.utils.translation import gettext
from jinja2 import Undefined
from jinja2.sandbox import SandboxedEnvironment


class VariableUndefined(Undefined):
    def __str__(self) -> str:
        """
        未定义字段返回指定字符串
        """

        return gettext("(未获取到变量值:%s)") % self._undefined_name


def jinja2_environment(allow_safe: bool = False, *args, **kwargs) -> SandboxedEnvironment:
    """
    创建一个Jinja2沙箱环境
    :param allow_safe: 是否允许使用 |safe 过滤器, 关闭后强制使用会抛出 TemplateAssertionError
    """

    env = SandboxedEnvironment(extensions=["jinja2.ext.i18n"], *args, **kwargs)
    env.install_gettext_translations(translation, newstyle=True)

    # 从过滤器列表中移除 safe，彻底禁止其使用
    if not allow_safe and 'safe' in env.filters:
        del env.filters['safe']

    return env


class Jinja2Renderer:
    """
    Jinja2渲染器
    """

    def __init__(self, *args, **kwargs):
        self.env = jinja2_environment(*args, **kwargs)

    def _render(self, template_value: str, context: dict) -> str:
        """
        只支持json和re函数
        """
        return self.env.from_string(template_value).render(context)

    def jinja_render(self, template_value: Union[str, dict, list], context: dict) -> Union[str, Dict, List]:
        """使用jinja渲染对象 ."""
        if isinstance(template_value, str):
            return self._render(template_value, context) or template_value
        if isinstance(template_value, dict):
            render_value = {}
            for key, value in template_value.items():
                render_value[key] = self.jinja_render(value, context)
            return render_value
        if isinstance(template_value, list):
            return [self.jinja_render(value, context) for value in template_value]
        return template_value
