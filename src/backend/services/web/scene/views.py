# -*- coding: utf-8 -*-
from bk_resource import resource
from bk_resource.viewsets import ResourceRoute, ResourceViewSet


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
    GET    /api/v1/scenes/{scene_id}/info/       场景信息（场景管理员可查看）
    PATCH  /api/v1/scenes/{scene_id}/info/       编辑场景基础信息（场景管理员）
    GET    /api/v1/scenes/my/                    用户场景列表
    GET    /api/v1/scenes/selector/              场景选择器数据
    """

    resource_routes = [
        ResourceRoute("GET", resource.scene.list_scene, enable_paginate=True),
        ResourceRoute("POST", resource.scene.create_scene),
        ResourceRoute("GET", resource.scene.retrieve_scene, pk_field="scene_id"),
        ResourceRoute("PUT", resource.scene.update_scene, pk_field="scene_id"),
        ResourceRoute("DELETE", resource.scene.delete_scene, pk_field="scene_id"),
        ResourceRoute("POST", resource.scene.disable_scene, endpoint="disable", pk_field="scene_id"),
        ResourceRoute("POST", resource.scene.enable_scene, endpoint="enable", pk_field="scene_id"),
        ResourceRoute("GET", resource.scene.get_scene_info, endpoint="info", pk_field="scene_id"),
        ResourceRoute("PATCH", resource.scene.update_scene_info, endpoint="info", pk_field="scene_id"),
        ResourceRoute("GET", resource.scene.list_my_scenes, endpoint="my"),
        ResourceRoute("GET", resource.scene.get_scene_selector, endpoint="selector"),
    ]


class MenuViewSet(ResourceViewSet):
    """
    菜单权限控制

    GET /api/v1/menus/  根据用户角色返回可见菜单
    """

    resource_routes = [
        ResourceRoute("GET", resource.scene.list_menus),
    ]


class PermissionGuideViewSet(ResourceViewSet):
    """
    无权限引导页

    GET /api/v1/permission/guide/{module}/
    """

    resource_routes = [
        ResourceRoute("GET", resource.scene.get_permission_guide, pk_field="module"),
    ]
