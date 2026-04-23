# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at https://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import abc
import contextlib
from typing import Tuple

from bk_resource import resource
from bk_resource.viewsets import ResourceRoute, ResourceViewSet
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext
from rest_framework.permissions import BasePermission

from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.drf import IAMPermission, InstanceActionPermission
from apps.permission.handlers.resource_types import ResourceEnum
from core.exceptions import ValidationError
from core.models import get_request_username
from core.utils.data import get_value_by_request_or_path
from core.utils.renderers import API200Renderer
from services.web.common.caller_permission import should_skip_permission_from
from services.web.common.constants import BindingResourceType
from services.web.common.scope_permission import ScopeInstancePermission
from services.web.scene.constants import PanelStatus
from services.web.tool.models import Tool
from services.web.tool.permissions import (
    UseToolPermission,
    check_bkvision_share_permission,
)
from services.web.vision.models import Scenario, SceneReportGroup, VisionPanel


class ToolVisionPermission(BasePermission):
    def __init__(self, try_skip_permission=False):
        self.try_skip_permission = try_skip_permission

    def has_permission(self, request, view):
        # 优先：从 query 参数 constants[...] 中抽取上下文做 caller 鉴权
        # 仅当 constants 存在且校验通过时放行（通常用于 Meta 接口）
        panel_id, tool_uid = self.get_tool_and_panel_id(request)
        if self.try_skip_permission:
            constants = self._extract_constants_from_query(request)
            constants['current_type'] = "tool"
            constants['current_object_id'] = tool_uid
            if should_skip_permission_from(constants, request.user.username):
                return True

        perm = UseToolPermission(
            get_instance_id=lambda: tool_uid,
        )
        # 工具使用权限校验（返回布尔值）
        if not perm.has_permission(request, view):
            return False
        # 图表分享权限校验（失败抛异常，成功继续）
        check_bkvision_share_permission(Tool.last_version_tool(tool_uid).get_permission_owner(), panel_id)
        return True

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)

    @staticmethod
    def _extract_constants_from_query(request) -> dict:
        """从 query_params 中抽取 constants[...] 的键值作为权限上下文"""
        params = getattr(request, "query_params", {}) or {}
        extracted = {'tool_variables': []}
        with contextlib.suppress(Exception):
            for k, v in params.items():
                if k.startswith("constants[") and k.endswith("]"):
                    inner_key = k[len("constants[") : -1]
                    if inner_key:
                        extracted[inner_key] = v
        caller_params = [
            "caller_resource_type",
            "caller_resource_id",
            "drill_field",
            "event_start_time",
            "event_end_time",
            "tool_variables",
        ]
        for k, v in extracted.copy().items():
            if k not in caller_params:
                extracted['tool_variables'].append({'raw_name': k, 'value': extracted.pop(k)})
        return extracted

    def get_tool_and_panel_id(self, request) -> Tuple[str, str]:
        instance_id: str = request.query_params.get("share_uid") or request.data.get("share_uid")
        panel = get_object_or_404(VisionPanel, id=instance_id)
        actual_instance_id = panel.vision_id
        tool_uid = None
        tool_relation = panel.tools.first()
        if tool_relation:
            tool_uid = tool_relation.tool.uid

        if actual_instance_id and tool_uid:
            return actual_instance_id, tool_uid
        raise ValidationError(message=gettext("无法获取报表ID"))


class UsePanelPermission(ScopeInstancePermission):
    """检查用户是否拥有使用Panel的权限（含启停态与管理员例外）。"""

    def __init__(self, *args, **kwargs):
        super().__init__(
            resource_type=BindingResourceType.PANEL,
            status_getter=self._get_panel_status,
            published_status=PanelStatus.PUBLISHED,
            *args,
            **kwargs,
        )

    @staticmethod
    def _get_panel_status(panel_id: str):
        panel = VisionPanel.objects.filter(id=panel_id).first()
        return panel.status if panel else None


class ShareDetailPermission(BasePermission):
    def has_permission(self, request, view):
        instance_id: str = request.query_params.get("share_uid") or request.data.get("share_uid")
        return check_bkvision_share_permission(get_request_username(), instance_id)

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class API200ViewSet(ResourceViewSet, abc.ABC):
    renderer_classes = [API200Renderer]


class BKVisionViewSet(ResourceViewSet, abc.ABC):
    escape_scenario = [Scenario.PER_APP.value]  # 去除接口鉴权

    def get_permissions(self):
        return []


class PanelsViewSet(BKVisionViewSet):
    """报表广场相关接口。

    - GET /panel/                    报表列表
    - GET /panel/group/              分组列表（system/cross_system 视角返回空）
    - POST /panel/favorite/          收藏/取消收藏
    - GET /panel/get_panel_preference/     获取用户偏好
    - PUT /panel/update_panel_preference/  更新用户偏好
    """

    resource_routes = [
        ResourceRoute("GET", resource.vision.list_panels),
        ResourceRoute("GET", resource.vision.list_scene_report_group, endpoint="group"),
        ResourceRoute("POST", resource.vision.toggle_panel_favorite, endpoint="favorite"),
        ResourceRoute("GET", resource.vision.get_panel_preference, endpoint="get_panel_preference"),
        ResourceRoute("PUT", resource.vision.update_panel_preference, endpoint="update_panel_preference"),
    ]


class BKVisionInstanceViewSet(BKVisionViewSet):
    def get_permissions(self):
        try:
            instance_id = self.get_instance_id()
        except ValidationError:
            return []

        panel: VisionPanel = get_object_or_404(VisionPanel, id=instance_id)
        # 部分场景无需鉴权
        if panel.scenario in self.escape_scenario:
            return []
        elif panel.scenario == Scenario.TOOL.value:
            # 工具场景除了meta无需鉴权
            return []
        return [UsePanelPermission(get_instance_id=self.get_instance_id)]

    def get_instance_id(self):
        instance_id: str = self.request.query_params.get("share_uid") or self.request.data.get("share_uid")
        if instance_id:
            return instance_id
        raise ValidationError(message=gettext("无法获取报表ID"))


class MetaViewSet(API200ViewSet, BKVisionInstanceViewSet):
    resource_routes = [
        ResourceRoute("GET", resource.vision.query_meta, endpoint="query"),
    ]

    def get_permissions(self):
        try:
            instance_id = self.get_instance_id()
        except ValidationError:
            return [ToolVisionPermission(try_skip_permission=True)]

        panel: VisionPanel = get_object_or_404(VisionPanel, id=instance_id)
        if panel.scenario == Scenario.TOOL.value:
            return [ToolVisionPermission(try_skip_permission=True)]
        return super().get_permissions()


class DatasetViewSet(API200ViewSet, BKVisionInstanceViewSet):
    resource_routes = [
        ResourceRoute("POST", resource.vision.query_dataset, endpoint="query"),
    ]


class FieldViewSet(API200ViewSet, BKVisionInstanceViewSet):
    resource_routes = [
        ResourceRoute("POST", resource.vision.query_field_data, endpoint="preview_data", pk_field="uid"),
    ]


class VariableViewSet(API200ViewSet, BKVisionInstanceViewSet):
    resource_routes = [
        ResourceRoute("POST", resource.vision.query_variable_data, endpoint="query"),
        ResourceRoute("POST", resource.vision.query_test_variable, endpoint="test"),
    ]


class ShareViewSet(BKVisionViewSet):
    resource_routes = [
        ResourceRoute("GET", resource.vision.query_share_list, endpoint="share_list"),
        ResourceRoute("GET", resource.vision.query_share_detail, endpoint="share_detail"),
    ]

    def get_permissions(self):
        if self.action in ["share_list"]:
            return []
        if self.action in ["share_detail"]:
            return [ShareDetailPermission()]
        return super().get_permissions()


# ==================== 场景报表管理 ====================


class PlatformPanelViewSet(ResourceViewSet):
    """
    平台级报表增删改 ViewSet（SaaS 管理员）

    POST   /bkvision/api/v1/panel/platform/                  创建平台级报表
    PUT    /bkvision/api/v1/panel/platform/{panel_id}/        编辑平台级报表
    DELETE /bkvision/api/v1/panel/platform/{panel_id}/        删除平台级报表
    POST   /bkvision/api/v1/panel/platform/{panel_id}/publish/ 上架/下架
    """

    def get_permissions(self):
        return [IAMPermission(actions=[ActionEnum.MANAGE_PLATFORM])]

    resource_routes = [
        ResourceRoute("GET", resource.vision.list_platform_panels, enable_paginate=True),
        ResourceRoute("POST", resource.vision.create_platform_panel),
        ResourceRoute("PUT", resource.vision.update_platform_panel, pk_field="panel_id"),
        ResourceRoute("DELETE", resource.vision.delete_platform_panel, pk_field="panel_id"),
        ResourceRoute("POST", resource.vision.publish_platform_panel, endpoint="publish", pk_field="panel_id"),
    ]


class SceneManageBaseViewSet(ResourceViewSet):
    """场景管理相关接口基类（统一 scene_id 提取和场景管理员权限）。"""

    def get_scene_id(self):
        scene_id = self.request.query_params.get("scene_id") or self.request.data.get("scene_id")
        if scene_id:
            return scene_id
        raise ValidationError(message=gettext("无法获取场景ID"))

    def get_permissions(self):
        return [
            InstanceActionPermission(
                actions=[ActionEnum.MANAGE_SCENE],
                resource_meta=ResourceEnum.SCENE,
                get_instance_id=self.get_scene_id,
            )
        ]


class ScenePanelManageViewSet(SceneManageBaseViewSet):
    """
    场景级报表增删改 ViewSet（场景管理员）

    GET    /bkvision/api/v1/panel/scene/                场景报表列表
    POST   /bkvision/api/v1/panel/scene/                创建场景级报表
    PUT    /bkvision/api/v1/panel/scene/{panel_id}/     编辑场景级报表
    DELETE /bkvision/api/v1/panel/scene/{panel_id}/     删除场景级报表
    POST   /bkvision/api/v1/panel/scene/{panel_id}/publish/ 上架/下架场景报表
    """

    lookup_field = "panel_id"
    resource_bound_actions = {"update", "destroy", "publish"}

    def _get_scene_id_from_panel(self):
        """优先使用详情路由中的 panel_id，再通过报表绑定关系反查所属场景。"""
        from services.web.scene.constants import BindingType, ResourceVisibilityType
        from services.web.scene.models import ResourceBinding

        panel_id = get_value_by_request_or_path(self.request, "panel_id")
        if not panel_id:
            raise ValidationError(message=gettext("无法获取报表ID"))

        binding = get_object_or_404(
            ResourceBinding,
            resource_type=ResourceVisibilityType.PANEL,
            resource_id=str(panel_id),
            binding_type=BindingType.SCENE_BINDING,
        )
        binding_scene = binding.binding_scenes.first()
        if not binding_scene:
            raise ValidationError(message=gettext("无法获取场景ID"))
        return str(binding_scene.scene_id)

    def get_permissions(self):
        action = getattr(self, "action", None)
        get_instance_id = self._get_scene_id_from_panel if action in self.resource_bound_actions else self.get_scene_id
        return [
            InstanceActionPermission(
                actions=[ActionEnum.MANAGE_SCENE],
                resource_meta=ResourceEnum.SCENE,
                get_instance_id=get_instance_id,
            )
        ]

    resource_routes = [
        ResourceRoute("GET", resource.vision.list_scene_panels),
        ResourceRoute("POST", resource.vision.create_scene_panel),
        ResourceRoute("PUT", resource.vision.update_scene_panel, pk_field="panel_id"),
        ResourceRoute("DELETE", resource.vision.delete_scene_panel, pk_field="panel_id"),
        ResourceRoute("POST", resource.vision.publish_scene_panel, endpoint="publish", pk_field="panel_id"),
    ]


class SceneReportGroupManageViewSet(SceneManageBaseViewSet):
    """场景报表分组管理 ViewSet（场景管理员）。"""

    lookup_field = "group_id"
    group_bound_actions = {"update", "destroy"}

    def _get_scene_id_from_request(self):
        scene_id = self.request.query_params.get("scene_id") or self.request.data.get("scene_id")
        if scene_id:
            return scene_id
        raise ValidationError(message=gettext("无法获取场景ID"))

    def _get_scene_id_from_group(self):
        group_id = (
            self.kwargs.get("group_id")
            or self.request.query_params.get("group_id")
            or self.request.data.get("group_id")
        )
        if not group_id:
            raise ValidationError(message=gettext("无法获取分组ID"))

        group = get_object_or_404(SceneReportGroup, id=group_id)
        return str(group.scene_id)

    def get_permissions(self):
        get_instance_id = (
            self._get_scene_id_from_group
            if self.action in self.group_bound_actions
            else self._get_scene_id_from_request
        )
        return [
            InstanceActionPermission(
                actions=[ActionEnum.MANAGE_SCENE],
                resource_meta=ResourceEnum.SCENE,
                get_instance_id=get_instance_id,
            )
        ]

    resource_routes = [
        ResourceRoute("POST", resource.vision.create_scene_report_group),
        ResourceRoute("PUT", resource.vision.update_scene_report_group, pk_field="group_id"),
        ResourceRoute("DELETE", resource.vision.delete_scene_report_group, pk_field="group_id"),
        ResourceRoute("POST", resource.vision.update_scene_report_group_order, endpoint="order"),
        ResourceRoute("POST", resource.vision.update_scene_report_group_panel_order, endpoint="item/order"),
    ]
