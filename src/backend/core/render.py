# -*- coding: utf-8 -*-

import json
import logging
import re
from typing import Dict, List, Union

from django.utils import translation
from jinja2 import Environment

logger = logging.getLogger(__name__)


def jinja2_environment(**options: Dict) -> Environment:
    """创建jinja2的环境执行环境 ."""
    env = Environment(extensions=["jinja2.ext.i18n"], **options)
    env.install_gettext_translations(translation, newstyle=True)
    return env


class Jinja2Renderer:
    """
    Jinja2渲染器
    """

    @staticmethod
    def render(template_value: str, context: dict) -> str:
        """
        只支持json和re函数
        """
        return jinja2_environment().from_string(template_value).render({"json": json, "re": re, **context})


def jinja_render(template_value: Union[str, dict, list], context: dict) -> Union[str, Dict, List]:
    """使用jinja渲染对象 ."""
    if isinstance(template_value, str):
        return Jinja2Renderer.render(template_value, context) or template_value
    if isinstance(template_value, dict):
        render_value = {}
        for key, value in template_value.items():
            render_value[key] = jinja_render(value, context)
        return render_value
    if isinstance(template_value, list):
        return [jinja_render(value, context) for value in template_value]
    return template_value
