# -*- coding: utf-8 -*-
from unittest import mock

from django.test import SimpleTestCase, override_settings
from django.urls import Resolver404, resolve
from rest_framework.test import APIRequestFactory

from services.web.risk.resources.risk import ListRiskAPIGW
from services.web.risk.urls import router
from services.web.risk.views import RiskAPIGWViewSet


@override_settings(ROOT_URLCONF="services.web.urls")
class TestRiskAPIGWRouting(SimpleTestCase):
    def test_risk_apigw_prefix_registered_to_merged_viewset(self):
        registry = {prefix: viewset for prefix, viewset, _ in router.registry}

        self.assertIs(registry["risk_apigw"], RiskAPIGWViewSet)

    def test_risk_apigw_list_route_resolves_to_merged_viewset(self):
        match = resolve("/api/v1/risk_apigw/")

        self.assertIs(match.func.cls, RiskAPIGWViewSet)

    def test_legacy_risks_apigw_route_removed(self):
        with self.assertRaises(Resolver404):
            resolve("/api/v1/risks_apigw/")

    def test_legacy_risk_list_apigw_route_removed(self):
        with self.assertRaises(Resolver404):
            resolve("/api/v1/risk_list_apigw/")


class TestRiskAPIGWViewSet(SimpleTestCase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()

    def test_post_list_uses_apigw_permission_and_list_risk_resource(self):
        view = RiskAPIGWViewSet.as_view({"post": "create"})
        request = self.factory.post("/api/v1/risk_apigw/", {}, format="json")

        with (
            mock.patch("core.permissions.get_app_info") as mock_get_app_info,
            mock.patch.object(
                ListRiskAPIGW,
                "request",
                autospec=True,
                return_value={"results": [], "count": 0},
            ) as mock_request,
        ):
            response = view(request)

        self.assertEqual(response.status_code, 200)
        mock_get_app_info.assert_called_once()
        mock_request.assert_called_once()
        self.assertEqual(mock_request.call_args.kwargs["request_data"], {})
        self.assertIn("_request", mock_request.call_args.kwargs)

    def test_post_list_with_detail_true_passes_param(self):
        """测试 with_detail=True 时参数被正确传递"""
        view = RiskAPIGWViewSet.as_view({"post": "create"})
        request = self.factory.post("/api/v1/risk_apigw/", {"with_detail": True}, format="json")

        with (
            mock.patch("core.permissions.get_app_info") as mock_get_app_info,
            mock.patch.object(
                ListRiskAPIGW,
                "request",
                autospec=True,
                return_value={"results": [], "count": 0},
            ) as mock_request,
        ):
            response = view(request)

        self.assertEqual(response.status_code, 200)
        mock_get_app_info.assert_called_once()
        mock_request.assert_called_once()
        self.assertEqual(mock_request.call_args.kwargs["request_data"]["with_detail"], True)

    def test_post_list_without_detail_defaults_to_false(self):
        """测试不传 with_detail 时默认为 False"""
        view = RiskAPIGWViewSet.as_view({"post": "create"})
        request = self.factory.post("/api/v1/risk_apigw/", {}, format="json")

        with (
            mock.patch("core.permissions.get_app_info") as _,
            mock.patch.object(
                ListRiskAPIGW,
                "request",
                autospec=True,
                return_value={"results": [], "count": 0},
            ) as mock_request,
        ):
            response = view(request)

        self.assertEqual(response.status_code, 200)
        mock_request.assert_called_once()
        # 不传 with_detail 时不应该出现在 request_data 中，或默认为 False
        request_data = mock_request.call_args.kwargs["request_data"]
        self.assertFalse(request_data.get("with_detail", False))
