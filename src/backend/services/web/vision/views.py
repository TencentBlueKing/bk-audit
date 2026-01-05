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
from core.utils.renderers import API200Renderer
from services.web.common.caller_permission import should_skip_permission_from
from services.web.tool.models import Tool
from services.web.tool.permissions import (
    UseToolPermission,
    check_bkvision_share_permission,
)
from services.web.vision.models import Scenario, VisionPanel


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
                    inner_key = k[len("constants["): -1]
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
        return [IAMPermission(actions=[ActionEnum.LIST_BASE_PANEL])]


class PanelsViewSet(BKVisionViewSet):
    def get_permissions(self):
        if self.action in ["list"]:
            scenario = self.request.query_params.get("scenario")
            if scenario in self.escape_scenario:
                return []
        return super().get_permissions()

    resource_routes = [
        ResourceRoute("GET", resource.vision.list_panels),
    ]


class BKVisionInstanceViewSet(BKVisionViewSet):
    def get_permissions(self):
        instance_id = self.get_instance_id()
        panel: VisionPanel = get_object_or_404(VisionPanel, id=instance_id)
        # 部分场景无需鉴权
        if panel.scenario in self.escape_scenario:
            return []
        elif panel.scenario == Scenario.TOOL.value:
            # 工具场景除了meta无需鉴权
            return []
        return [
            InstanceActionPermission(
                actions=[ActionEnum.VIEW_BASE_PANEL],
                resource_meta=ResourceEnum.PANEL,
                get_instance_id=self.get_instance_id,
            )
        ]

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
        instance_id = self.get_instance_id()
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
