# -*- coding: utf-8 -*-
import json
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, override_settings
from django.urls import resolve
from rest_framework import status
from rest_framework.parsers import JSONParser
from rest_framework.test import APIRequestFactory

from services.web.tool.views import ToolViewSet


@override_settings(ROOT_URLCONF="services.web.urls")
class TestBKResourceRequestDataCompat(SimpleTestCase):
    def test_detail_resource_route_rejects_form_body_without_internal_error(self):
        request = APIRequestFactory().post(
            "/api/v1/namespaces/default/tool/tool-1/execute/",
            data="params={}",
            content_type="application/x-www-form-urlencoded",
        )
        view = resolve("/api/v1/namespaces/default/tool/tool-1/execute/").func
        route = next(route for route in ToolViewSet.resource_routes if route.endpoint == "execute")

        with (
            mock.patch.object(ToolViewSet, "get_permissions", return_value=[]),
            mock.patch.object(route.resource_class, "request", return_value={"tool_type": "api", "data": {}}),
        ):
            response = view(request, namespace="default", uid="tool-1")

        self.assertEqual(response.status_code, 200)

    def test_detail_resource_route_rejects_scalar_body_without_internal_error(self):
        request = APIRequestFactory().post(
            "/api/v1/namespaces/default/tool/tool-1/execute/",
            data='"{}"',
            content_type="application/json",
        )
        view = resolve("/api/v1/namespaces/default/tool/tool-1/execute/").func
        route = next(route for route in ToolViewSet.resource_routes if route.endpoint == "execute")

        with (
            mock.patch.object(ToolViewSet, "get_permissions", return_value=[]),
            mock.patch.object(ToolViewSet, "parser_classes", [JSONParser]),
            mock.patch.object(route.resource_class, "request", return_value={"tool_type": "api", "data": {}}),
        ):
            response = view(request, namespace="default", uid="tool-1")

        self.assertEqual(response.status_code, 400)
        self.assertIn("请求体必须为 JSON/Form 对象", str(response.data))

    def test_detail_resource_route_limits_json_request_body(self):
        self._assert_request_body_limit(
            "application/json",
            b'{"params":{},"caller_resource_id":"sample %s"}',
        )

    def test_detail_resource_route_limits_urlencoded_request_body(self):
        self._assert_request_body_limit(
            "application/x-www-form-urlencoded",
            b"params.label=sample&caller_resource_id=sample+%s",
        )

    def _assert_request_body_limit(self, content_type, body_template):
        path = "/api/v1/namespaces/default/tool/tool-1/execute/"
        match = resolve(path)
        route = next(route for route in ToolViewSet.resource_routes if route.endpoint == "execute")
        resource_class = route.resource_class
        resource_result = {"tool_type": "api", "data": {}}
        body_base_size = len(body_template % b"")
        limit = settings.DATA_UPLOAD_MAX_MEMORY_SIZE

        for body_size in (limit - 1, limit, limit + 1):
            with self.subTest(body_size=body_size):
                padding = b"x" * (body_size - body_base_size)
                request = APIRequestFactory().post(path, data=body_template % padding, content_type=content_type)
                with (
                    mock.patch.object(ToolViewSet, "get_permissions", return_value=[]),
                    mock.patch.object(resource_class, "request", return_value=resource_result) as resource_request,
                    mock.patch.object(resource_class, "support_data_collect", False),
                ):
                    response = match.func(request, **match.kwargs)
                    response.render()

                self.assertEqual(response["Content-Type"], "application/json")
                payload = json.loads(response.content)
                if body_size > limit:
                    self.assertEqual(response.status_code, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
                    self.assertIs(payload["result"], False)
                    self.assertEqual(payload["code"], 413)
                    self.assertTrue(payload["message"])
                    self.assertIsNone(payload["data"])
                    self.assertIsNone(payload["errors"])
                    self.assertIn("request_id", payload)
                    self.assertIn("trace_id", payload)
                    resource_request.assert_not_called()
                else:
                    self.assertEqual(response.status_code, status.HTTP_200_OK)
                    self.assertIs(payload["result"], True)
                    self.assertEqual(payload["data"], resource_result)
                    resource_request.assert_called_once()
                    request_data = resource_request.call_args.kwargs["request_data"]
                    self.assertEqual(request_data["uid"], "tool-1")
                    self.assertEqual(request_data["namespace"], "default")
                    self.assertTrue(
                        request_data["caller_resource_id"] == "sample " + padding.decode("ascii"),
                        "请求字段内容应完整保留",
                    )
