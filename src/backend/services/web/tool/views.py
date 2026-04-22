# -*- coding: utf-8 -*-
from bk_resource import resource
from bk_resource.viewsets import ResourceRoute, ResourceViewSet
from django.utils.translation import gettext

from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.drf import (
    AnyOfPermissions,
    IAMPermission,
    InstanceActionPermission,
)
from apps.permission.handlers.resource_types import ResourceEnum
from core.exceptions import ValidationError
from core.utils.data import get_value_by_request, get_value_by_request_or_path
from services.web.tool.permissions import CallerContextPermission, UseToolPermission


class ToolViewSet(ResourceViewSet):
    lookup_field = "uid"

    def get_permissions(self):
        if self.action in ["sql_analyse_with_tool"]:
            return [UseToolPermission(get_instance_id=self.get_tool_uid)]
        if self.action in ["execute", "enum_mapping_by_collection_keys", "enum_mapping_by_collection"]:
            return [
                AnyOfPermissions(
                    CallerContextPermission(),
                    UseToolPermission(),
                )
            ]
        return []

    def get_tool_uid(self):
        """工具详情类接口优先从请求上下文中的路由主键读取 uid。"""
        return get_value_by_request_or_path(self.request, "uid")

    resource_routes = [
        ResourceRoute(
            "POST",
            resource.tool.get_tool_enum_mapping_by_collection_keys,
            endpoint="enum_mapping_by_collection_keys",
        ),
        ResourceRoute("POST", resource.tool.get_tool_enum_mapping_by_collection, endpoint="enum_mapping_by_collection"),
        ResourceRoute("GET", resource.tool.list_tool_tags, endpoint="tags"),
        ResourceRoute("GET", resource.tool.list_tool, enable_paginate=True),
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
        ResourceRoute("GET", resource.tool.get_tool_detail_by_name_apigw, endpoint="detail_by_name"),
    ]


# ==================== 场景工具管理 ====================


class PlatformSceneToolViewSet(ResourceViewSet):
    """
    平台级场景工具增删改 ViewSet（SaaS 管理员）

    POST   /api/v1/tool/platform/                创建平台级工具
    PUT    /api/v1/tool/platform/{uid}/          编辑平台级工具
    DELETE /api/v1/tool/platform/{uid}/          删除平台级工具
    POST   /api/v1/tool/platform/{uid}/publish/  上架/下架
    """

    def get_permissions(self):
        return [IAMPermission(actions=[ActionEnum.MANAGE_PLATFORM])]

    resource_routes = [
        ResourceRoute("POST", resource.tool.create_platform_scene_tool),
        ResourceRoute("PUT", resource.tool.update_platform_scene_tool, pk_field="uid"),
        ResourceRoute("DELETE", resource.tool.delete_platform_scene_tool, pk_field="uid"),
        ResourceRoute("POST", resource.tool.publish_platform_scene_tool, endpoint="publish", pk_field="uid"),
    ]


class SceneScopeToolViewSet(ResourceViewSet):
    """
    场景级工具增删改 ViewSet（场景管理员）

    POST   /api/v1/tool/scene/                  创建场景级工具
    PUT    /api/v1/tool/scene/{uid}/            编辑场景级工具
    DELETE /api/v1/tool/scene/{uid}/            删除场景级工具
    POST   /api/v1/tool/scene/{uid}/publish/    上架/下架
    """

    lookup_field = "uid"
    resource_bound_actions = {"update", "destroy", "publish"}

    def get_scene_id(self):
        return get_value_by_request(self.request, "scene_id")

    def get_scene_id_from_tool(self):
        """通过工具绑定关系反查场景，避免详情接口信任可伪造的请求 scene_id。"""
        from django.shortcuts import get_object_or_404

        from services.web.scene.constants import BindingType, ResourceVisibilityType
        from services.web.scene.models import ResourceBinding

        uid = get_value_by_request_or_path(self.request, "uid")
        if not uid:
            raise ValidationError(message=gettext("无法获取工具UID"))

        binding = get_object_or_404(
            ResourceBinding,
            resource_type=ResourceVisibilityType.TOOL,
            resource_id=uid,
            binding_type=BindingType.SCENE_BINDING,
        )
        binding_scene = binding.binding_scenes.first()
        if not binding_scene:
            raise ValidationError(message=gettext("无法获取场景ID"))
        return str(binding_scene.scene_id)

    def get_permissions(self):
        get_instance_id = (
            self.get_scene_id_from_tool if self.action in self.resource_bound_actions else self.get_scene_id
        )
        return [
            InstanceActionPermission(
                actions=[ActionEnum.MANAGE_SCENE],
                resource_meta=ResourceEnum.SCENE,
                get_instance_id=get_instance_id,
            )
        ]

    resource_routes = [
        ResourceRoute("POST", resource.tool.create_scene_scope_tool),
        ResourceRoute("PUT", resource.tool.update_scene_scope_tool, pk_field="uid"),
        ResourceRoute("DELETE", resource.tool.delete_scene_scope_tool, pk_field="uid"),
        ResourceRoute("POST", resource.tool.publish_scene_scope_tool, endpoint="publish", pk_field="uid"),
    ]
