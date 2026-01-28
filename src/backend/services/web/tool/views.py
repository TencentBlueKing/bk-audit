# -*- coding: utf-8 -*-
from bk_resource import resource
from bk_resource.viewsets import ResourceRoute, ResourceViewSet

from apps.permission.handlers.drf import AnyOfPermissions
from core.utils.data import get_value_by_request
from services.web.tool.permissions import (
    CallerContextPermission,
    ManageToolPermission,
    UseToolPermission,
)


class ToolViewSet(ResourceViewSet):
    lookup_field = "uid"

    def get_permissions(self):
        if self.action in ["update", "destroy", "sql_analyse_with_tool"]:
            return [ManageToolPermission()]
        if self.action in ["execute", "enum_mapping_by_collection_keys", "enum_mapping_by_collection"]:
            return [
                AnyOfPermissions(
                    CallerContextPermission(),
                    UseToolPermission(),
                )
            ]
        return []

    def get_tool_uid(self):
        return get_value_by_request(self.request, "uid")

    resource_routes = [
        ResourceRoute(
            "POST",
            resource.tool.get_tool_enum_mapping_by_collection_keys,
            endpoint="enum_mapping_by_collection_keys",
        ),
        ResourceRoute("POST", resource.tool.get_tool_enum_mapping_by_collection, endpoint="enum_mapping_by_collection"),
        ResourceRoute("GET", resource.tool.list_tool_tags, endpoint="tags"),
        ResourceRoute("GET", resource.tool.list_tool, enable_paginate=True),
        ResourceRoute("DELETE", resource.tool.delete_tool, pk_field="uid"),
        ResourceRoute("POST", resource.tool.create_tool),
        ResourceRoute("PUT", resource.tool.update_tool, pk_field="uid"),
        ResourceRoute("POST", resource.tool.execute_tool, endpoint="execute", pk_field="uid"),
        ResourceRoute("GET", resource.tool.list_tool_all, endpoint="all"),
        ResourceRoute("GET", resource.tool.get_tool_detail, pk_field="uid"),
        ResourceRoute("POST", resource.tool.sql_analyse, endpoint="sql_analyse"),
        ResourceRoute("POST", resource.tool.sql_analyse_with_tool, endpoint="sql_analyse_with_tool", pk_field="uid"),
        ResourceRoute("POST", resource.tool.user_query_table_auth_check, endpoint="user_query_table_auth_check"),
        ResourceRoute("POST", resource.tool.tool_execute_debug, endpoint="tool_execute_debug"),
        ResourceRoute("PUT", resource.tool.favorite_tool, pk_field="uid", endpoint="favorite"),
    ]


class ToolAPIGWViewSet(ResourceViewSet):
    """
    Execute Tool APIGW
    """

    def get_authenticators(self):
        return []

    def get_permissions(self):
        return []

    resource_routes = [
        ResourceRoute("POST", resource.tool.execute_tool_apigw, endpoint="execute", pk_field="uid"),
    ]
