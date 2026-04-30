# -*- coding: utf-8 -*-

import json
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase
from rest_framework.exceptions import ErrorDetail

from core.utils.renderers import APIRenderer


class TestAPIRenderer(SimpleTestCase):
    def _render_error(self, data):
        response = SimpleNamespace(status_code=400, data=data)
        request = SimpleNamespace(otel_trace_id=None)
        with mock.patch("blueapps.utils.request_provider.get_or_create_local_request_id", return_value="req-id"):
            rendered = APIRenderer().render(
                data=None,
                renderer_context={
                    "response": response,
                    "request": request,
                },
            )
        return json.loads(rendered)

    def test_params_error_message_is_rendered_as_plain_string(self):
        payload = self._render_error({"params_error": [ErrorDetail("处理套餐不存在", code="invalid")]})

        self.assertEqual(payload["message"], "处理套餐不存在")
        self.assertEqual(payload["errors"], {"params_error": ["处理套餐不存在"]})

    def test_field_error_message_is_rendered_as_plain_string(self):
        payload = self._render_error({"pa_id": [ErrorDetail("处理套餐不存在", code="invalid")]})

        self.assertEqual(payload["message"], "pa_id: 处理套餐不存在")
        self.assertEqual(payload["errors"], {"pa_id": ["处理套餐不存在"]})

    def test_list_error_message_is_rendered_as_plain_string(self):
        payload = self._render_error([ErrorDetail("处理套餐不存在", code="invalid")])

        self.assertEqual(payload["message"], "处理套餐不存在")
        self.assertEqual(payload["errors"], ["处理套餐不存在"])
