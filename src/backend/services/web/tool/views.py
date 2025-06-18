# -*- coding: utf-8 -*-
from bk_resource import resource
from bk_resource.viewsets import ResourceRoute, ResourceViewSet

from services.web.tool.permissions import CreatorBasePermissionPermission


class ToolViewSet(ResourceViewSet):
    lookup_field = "uid"

    def get_permissions(self):
        if self.action == "update":
            return [CreatorBasePermissionPermission()]
        if self.action == "destroy":
            return [CreatorBasePermissionPermission()]
        return []

    resource_routes = [
        ResourceRoute("GET", resource.tool.list_tool_tags, endpoint="tags"),
        ResourceRoute("GET", resource.tool.list_tool, enable_paginate=True),
        ResourceRoute("DELETE", resource.tool.delete_tool, pk_field="uid"),
        ResourceRoute("POST", resource.tool.create_tool),
        ResourceRoute("PUT", resource.tool.update_tool, pk_field="uid"),
        ResourceRoute("POST", resource.tool.execute_tool, endpoint="execute", pk_field="uid"),
        ResourceRoute("GET", resource.tool.list_tool_all, endpoint="all"),
        ResourceRoute("GET", resource.tool.get_tool_detail, pk_field="uid"),
    ]
