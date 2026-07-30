# -*- coding: utf-8 -*-
from io import BytesIO

from django.test import SimpleTestCase
from rest_framework.exceptions import ParseError

from core.parsers import JSONObjectJSONParser


class TestJSONObjectJSONParser(SimpleTestCase):
    def parse(self, body):
        return JSONObjectJSONParser().parse(
            stream=BytesIO(body.encode()),
            media_type="application/json",
            parser_context={},
        )

    def test_accepts_json_object(self):
        self.assertEqual(self.parse('{"params": {}}'), {"params": {}})

    def test_rejects_non_object_json_body(self):
        for body in ('"{\\"params\\": {}}"', "[]", "null"):
            with self.subTest(body=body):
                with self.assertRaisesMessage(ParseError, "请求体必须为 JSON 对象"):
                    self.parse(body)
