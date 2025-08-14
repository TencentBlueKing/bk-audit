# -*- coding: utf-8 -*-
from bk_resource import resource
from bk_resource.viewsets import ResourceRoute, ResourceViewSet

from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.drf import insert_permission_field
from apps.permission.handlers.resource_types import ResourceEnum
from core.models import get_request_username
from core.utils.data import get_value_by_request
from services.web.tool.permissions import (
    CreatorBasePermissionPermission,
    UseToolPermission,
)


class ToolViewSet(ResourceViewSet):
    lookup_field = "uid"

    def get_permissions(self):
        if self.action == "update":
            return [CreatorBasePermissionPermission()]
        if self.action == "destroy":
            return [CreatorBasePermissionPermission()]
        if self.action in ["execute"]:
            return [
                UseToolPermission(
                    actions=[ActionEnum.USE_TOOL],
                    resource_meta=ResourceEnum.TOOL,
                )
            ]
        return []

    def get_tool_uid(self):
        return get_value_by_request(self.request, "uid")

    resource_routes = [
        ResourceRoute("GET", resource.tool.list_tool_tags, endpoint="tags"),
        ResourceRoute("GET", resource.tool.list_tool, enable_paginate=True),
        ResourceRoute("DELETE", resource.tool.delete_tool, pk_field="uid"),
        ResourceRoute("POST", resource.tool.create_tool),
        ResourceRoute("PUT", resource.tool.update_tool, pk_field="uid"),
        ResourceRoute("POST", resource.tool.execute_tool, endpoint="execute", pk_field="uid"),
        ResourceRoute("GET", resource.tool.list_tool_all, endpoint="all"),
        ResourceRoute(
            "GET",
            resource.tool.get_tool_detail,
            pk_field="uid",
            decorators=[
                insert_permission_field(
                    actions=[ActionEnum.USE_TOOL],
                    id_field=lambda item: item["uid"],
                    always_allowed=lambda item: item.get("created_by") == get_request_username(),
                    many=False,
                )
            ],
        ),
        ResourceRoute("POST", resource.tool.sql_analyse, endpoint="sql_analyse"),
        ResourceRoute("POST", resource.tool.user_query_table_auth_check, endpoint="user_query_table_auth_check"),
    ]
