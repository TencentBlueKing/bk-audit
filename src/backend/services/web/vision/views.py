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

from bk_resource import resource
from bk_resource.viewsets import ResourceRoute, ResourceViewSet
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext

from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.drf import IAMPermission, InstanceActionPermission
from apps.permission.handlers.resource_types import ResourceEnum
from core.exceptions import ValidationError
from core.utils.renderers import API200Renderer
from services.web.vision.models import Scenario, VisionPanel


class API200ViewSet(ResourceViewSet, abc.ABC):
    renderer_classes = [API200Renderer]


class BKVisionViewSet(ResourceViewSet, abc.ABC):
    escape_scenario = [Scenario.PER_APP.value]  # 单系统报表去除接口鉴权，直接采用 filter 鉴权

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
    ]


class QueryShareVisionViewSet(API200ViewSet, BKVisionViewSet):
    resource_routes = [
        ResourceRoute("GET", resource.vision.query_share_list, endpoint="query_share_vision"),
        ResourceRoute("GET", resource.vision.query_share_detail, endpoint="query_share_vision_detail"),
    ]
