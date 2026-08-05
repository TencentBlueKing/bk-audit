# -*- coding: utf-8 -*-
from unittest import mock

from django.test import SimpleTestCase, override_settings
from django.urls import resolve
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
