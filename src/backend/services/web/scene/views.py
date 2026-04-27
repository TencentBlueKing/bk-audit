# -*- coding: utf-8 -*-
from bk_resource import resource
from bk_resource.viewsets import ResourceRoute, ResourceViewSet

from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.drf import (
    IAMPermission,
    InstanceActionPermission,
    insert_permission_field,
)
from apps.permission.handlers.resource_types import ResourceEnum


class SceneViewSet(ResourceViewSet):
    """
    场景管理 ViewSet（SaaS 管理员专属）

    GET    /api/v1/scenes/                     场景列表
    POST   /api/v1/scenes/                     创建场景
    GET    /api/v1/scenes/{scene_id}/           场景详情
    PUT    /api/v1/scenes/{scene_id}/           编辑场景
    DELETE /api/v1/scenes/{scene_id}/           删除场景
    POST   /api/v1/scenes/{scene_id}/disable/   停用场景
    POST   /api/v1/scenes/{scene_id}/enable/    启用场景
    GET    /api/v1/scenes/{scene_id}/get_scene_info/       场景信息（场景管理员可查看）
    PATCH  /api/v1/scenes/{scene_id}/update_scene_info/    编辑场景基础信息（场景管理员）
    """

    lookup_field = "scene_id"

    def get_scene_id(self):
        return self.kwargs.get("scene_id")

    def get_permissions(self):
        if self.action == "my_role_permissions":
            return []
        if self.action in ["list", "create", "retrieve", "update", "destroy", "disable", "enable"]:
            return [IAMPermission(actions=[ActionEnum.MANAGE_PLATFORM])]
        if self.action in ["get_scene_info", "update_scene_info"]:
            if self.request.method == "GET":
                return [
                    InstanceActionPermission(
                        actions=[ActionEnum.VIEW_SCENE],
                        resource_meta=ResourceEnum.SCENE,
                        get_instance_id=self.get_scene_id,
                    )
                ]
            return [
                InstanceActionPermission(
                    actions=[ActionEnum.MANAGE_SCENE],
                    resource_meta=ResourceEnum.SCENE,
                    get_instance_id=self.get_scene_id,
                )
            ]
        if self.action in ["scene_permission_systems", "scene_permission_tables"]:
            return [
                InstanceActionPermission(
                    actions=[ActionEnum.MANAGE_SCENE],
                    resource_meta=ResourceEnum.SCENE,
                    get_instance_id=self.get_scene_id,
                )
            ]
        return []

    resource_routes = [
        ResourceRoute(
            "GET",
            resource.scene.list_scene,
            enable_paginate=True,
        ),
        ResourceRoute(
            "GET",
            resource.scene.list_all_scene,
            endpoint="all",
            decorators=[
                insert_permission_field(
                    actions=[ActionEnum.MANAGE_SCENE, ActionEnum.VIEW_SCENE],
                    id_field=lambda item: item["scene_id"],
                    data_field=lambda data: data,
                )
            ],
        ),
        ResourceRoute("GET", resource.scene.get_my_role_permissions, endpoint="my_role_permissions"),
        ResourceRoute("POST", resource.scene.create_scene),
        ResourceRoute("GET", resource.scene.retrieve_scene, pk_field="scene_id"),
        ResourceRoute("PUT", resource.scene.update_scene, pk_field="scene_id"),
        ResourceRoute("DELETE", resource.scene.delete_scene, pk_field="scene_id"),
        ResourceRoute("POST", resource.scene.disable_scene, endpoint="disable", pk_field="scene_id"),
        ResourceRoute("POST", resource.scene.enable_scene, endpoint="enable", pk_field="scene_id"),
        ResourceRoute("GET", resource.scene.get_scene_info, endpoint="get_scene_info", pk_field="scene_id"),
        ResourceRoute("PATCH", resource.scene.update_scene_info, endpoint="update_scene_info", pk_field="scene_id"),
        ResourceRoute(
            "GET",
            resource.scene.get_scene_permission_systems,
            endpoint="scene_permission_systems",
            pk_field="scene_id",
        ),
        ResourceRoute(
            "GET",
            resource.scene.get_scene_permission_tables,
            endpoint="scene_permission_tables",
            pk_field="scene_id",
        ),
    ]
