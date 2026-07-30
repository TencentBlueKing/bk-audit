# -*- coding: utf-8 -*-
from django.utils.translation import gettext
from rest_framework.exceptions import ParseError
from rest_framework.parsers import JSONParser


class JSONObjectJSONParser(JSONParser):
    """仅接受 JSON object，避免 ResourceViewSet 在合并路径参数时处理标量请求体。"""

    def parse(self, stream, media_type=None, parser_context=None):
        data = super().parse(stream, media_type=media_type, parser_context=parser_context)
        if not isinstance(data, dict):
            raise ParseError(gettext("请求体必须为 JSON 对象，不能为字符串、数组或 null"))
        return data
