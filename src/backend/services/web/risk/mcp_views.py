# -*- coding: utf-8 -*-
from bk_resource import resource
from bk_resource.viewsets import ResourceRoute

from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.resource_types import ResourceEnum
from core.view_sets import UserAPIGWViewSet
from services.web.risk.permissions import RiskViewPermission


class MCPUserRiskViewSet(UserAPIGWViewSet):
    """供 MCP 调用的风险用户态接口。"""

    lookup_field = "risk_id"

    def get_permissions(self):
        permissions = super().get_permissions()
        if self.action in {"retrieve", "strategy_info"}:
            permissions.append(
                RiskViewPermission(
                    actions=[ActionEnum.LIST_RISK],
                    resource_meta=ResourceEnum.RISK,
                    lookup_field="risk_id",
                )
            )
        return permissions

    resource_routes = [
        ResourceRoute("GET", resource.risk.retrieve_risk_apigw, pk_field="risk_id"),
        ResourceRoute(
            "GET",
            resource.risk.retrieve_risk_strategy_info_apigw,
            pk_field="risk_id",
            endpoint="strategy_info",
        ),
    ]


class MCPUserEventViewSet(UserAPIGWViewSet):
    """供 MCP 调用的事件用户态接口。"""

    def get_permissions(self):
        return [
            *super().get_permissions(),
            RiskViewPermission(
                actions=[ActionEnum.LIST_RISK],
                resource_meta=ResourceEnum.RISK,
                get_instance_id=lambda: self.request.query_params.get("risk_id"),
            ),
        ]

    resource_routes = [ResourceRoute("GET", resource.risk.list_event_apigw)]


class MCPUserAnalyseReportViewSet(UserAPIGWViewSet):
    """供 MCP 调用的报告关联风险用户态接口。"""

    lookup_field = "report_id"
    resource_routes = [
        ResourceRoute(
            "POST",
            resource.risk.list_analyse_report_risk,
            pk_field="report_id",
            endpoint="risks",
            enable_paginate=True,
        )
    ]
