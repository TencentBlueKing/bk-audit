# -*- coding: utf-8 -*-
from datetime import datetime, timezone
from unittest import mock

from django.test import SimpleTestCase, override_settings
from django.urls import resolve
from rest_framework.test import APIRequestFactory, force_authenticate

from core.permissions import UserAPIGWPermission
from services.web.risk.constants import AnalyseReportStatus, AnalyseReportType
from services.web.risk.mcp_views import (
    MCPUserAnalyseReportViewSet,
    MCPUserEventViewSet,
    MCPUserRiskViewSet,
)
from services.web.risk.models import AnalyseReport, AnalyseReportRisk, Risk
from services.web.risk.permissions import RiskViewPermission
from services.web.risk.views import RiskAPIGWViewSet
from services.web.strategy_v2.constants import RiskLevel
from services.web.strategy_v2.models import Strategy
from tests.base import TestCase


@override_settings(ROOT_URLCONF="services.web.urls")
class TestMCPUserRiskRouting(SimpleTestCase):
    def test_new_routes_resolve_to_user_viewsets(self):
        risk_match = resolve("/api/v1/mcp_user/risk/risk-1/")

        self.assertIs(risk_match.func.cls, MCPUserRiskViewSet)
        self.assertEqual(risk_match.kwargs, {"risk_id": "risk-1"})
        self.assertIs(resolve("/api/v1/mcp_user/event/").func.cls, MCPUserEventViewSet)
        self.assertIs(
            resolve("/api/v1/mcp_user/analyse_report/1/risks/").func.cls,
            MCPUserAnalyseReportViewSet,
        )

    def test_legacy_application_route_is_unchanged(self):
        self.assertIs(resolve("/api/v1/risk_apigw/risk-1/").func.cls, RiskAPIGWViewSet)


class TestMCPUserRiskViewSet(SimpleTestCase):
    def test_risk_action_combines_user_gateway_and_risk_permission(self):
        viewset = MCPUserRiskViewSet()
        viewset.action = "retrieve"

        permissions = viewset.get_permissions()

        self.assertIsInstance(permissions[0], UserAPIGWPermission)
        self.assertIsInstance(permissions[1], RiskViewPermission)

    def test_report_risk_list_uses_standard_pagination(self):
        route = MCPUserAnalyseReportViewSet.resource_routes[0]

        self.assertTrue(route.enable_paginate)


class TestMCPUserAnalyseReportViewSet(TestCase):
    class User:
        username = "owner"
        is_authenticated = True

    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        strategy = Strategy.objects.create(
            namespace="default",
            strategy_name="mcp-user-report-strategy",
            risk_level=RiskLevel.HIGH.value,
        )
        self.report = AnalyseReport.objects.create(
            title="MCP 用户态报告",
            report_type=AnalyseReportType.SYSTEM,
            risk_count=2,
            status=AnalyseReportStatus.SUCCESS,
            prompt_params={},
            created_by="owner",
        )
        for risk_id in ("mcp-user-risk-1", "mcp-user-risk-2"):
            Risk.objects.create(
                risk_id=risk_id,
                raw_event_id=f"raw-{risk_id}",
                strategy=strategy,
                status="new",
                event_time=datetime.now(timezone.utc),
            )
            AnalyseReportRisk.objects.create(report=self.report, risk_id=risk_id)

    def test_report_owner_gets_standard_paginated_response(self):
        view = MCPUserAnalyseReportViewSet.as_view({"post": "risks"})
        request = self.factory.post(
            f"/api/v1/mcp_user/analyse_report/{self.report.report_id}/risks/?page=1&page_size=1",
            {},
            format="json",
        )
        force_authenticate(request, user=self.User())

        with (
            mock.patch("core.permissions.get_app_info"),
            mock.patch("services.web.risk.resources.analyse_report.get_request_username", return_value="owner"),
        ):
            response = view(request, report_id=self.report.report_id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 2)
        self.assertEqual(len(response.data["results"]), 1)
