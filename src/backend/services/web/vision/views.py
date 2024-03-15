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
from django.utils.translation import gettext

from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.drf import IAMPermission, InstanceActionPermission
from apps.permission.handlers.resource_types import ResourceEnum
from core.exceptions import ValidationError
from core.utils.renderers import API200Renderer


class API200ViewSet(ResourceViewSet, abc.ABC):
    renderer_classes = [API200Renderer]


class BKVisionViewSet(ResourceViewSet, abc.ABC):
    def get_permissions(self):
        return [IAMPermission(actions=[ActionEnum.LIST_BASE_PANEL])]


class PanelsViewSet(BKVisionViewSet):
    resource_routes = [
        ResourceRoute("GET", resource.vision.list_panels),
    ]


class BKVisionInstanceViewSet(BKVisionViewSet):
    def get_permissions(self):
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
