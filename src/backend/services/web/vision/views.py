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

from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.drf import IAMPermission
from core.utils.renderers import API200Renderer


class BKVisionViewSet(abc.ABC):
    renderer_classes = [API200Renderer]

    def get_permissions(self):
        return [IAMPermission(actions=[ActionEnum.VIEW_BASE_PANEL])]


class MetaViewSet(BKVisionViewSet, ResourceViewSet):
    resource_routes = [
        ResourceRoute("GET", resource.vision.query_meta, endpoint="query"),
    ]


class DatasourceViewSet(BKVisionViewSet, ResourceViewSet):
    resource_routes = [
        ResourceRoute("POST", resource.vision.query_data, endpoint="query"),
    ]
