# -*- coding: utf-8 -*-
from django.utils.translation import gettext
from jinja2 import Undefined


class RiskTitleUndefined(Undefined):
    def __str__(self) -> str:
        """
        未定义字段返回指定字符串
        """

        return gettext("(未获取到变量值:%s)") % self._undefined_name
