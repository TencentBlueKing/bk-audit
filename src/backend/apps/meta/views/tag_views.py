# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
from bk_resource import resource
from bk_resource.viewsets import ResourceRoute, ResourceViewSet
from rest_framework.permissions import IsAuthenticated

from apps.meta.constants import TagBindingResourceType
from apps.meta.handlers.tag_binding import get_tool_binding_info
from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.drf import IAMPermission, InstanceActionPermission
from apps.permission.handlers.resource_types import ResourceEnum
from core.utils.data import get_value_by_request


class TagViewSet(ResourceViewSet):
    resource_routes = [
        ResourceRoute("GET", resource.meta.list_all_tags),
    ]


class TagBindingsViewSet(ResourceViewSet):
    """
    编辑策略/联表/工具的标签绑定

    PUT /api/v1/meta/namespaces/{namespace}/tags/bindings/
    """

    def get_resource_type(self):
        return get_value_by_request(self.request, "resource_type")

    def get_resource_id(self):
        return get_value_by_request(self.request, "resource_id")

    def get_strategy_id(self):
        resource_id = self.get_resource_id()
        return resource_id if resource_id and resource_id.isdigit() else None

    def get_tool_scene_id(self):
        return self._tool_scene_id

    def get_permissions(self):
        resource_type = self.get_resource_type()

        if resource_type == TagBindingResourceType.STRATEGY:
            return [
                InstanceActionPermission(
                    actions=[ActionEnum.EDIT_STRATEGY],
                    resource_meta=ResourceEnum.STRATEGY,
                    get_instance_id=self.get_strategy_id,
                )
            ]

        if resource_type == TagBindingResourceType.LINK_TABLE:
            return [
                InstanceActionPermission(
                    actions=[ActionEnum.EDIT_LINK_TABLE],
                    resource_meta=ResourceEnum.LINK_TABLE,
                    get_instance_id=self.get_resource_id,
                )
            ]

        if resource_type == TagBindingResourceType.TOOL:
            is_scene_tool, self._tool_scene_id = get_tool_binding_info(self.get_resource_id())
            if is_scene_tool:
                return [
                    InstanceActionPermission(
                        actions=[ActionEnum.MANAGE_SCENE],
                        resource_meta=ResourceEnum.SCENE,
                        get_instance_id=self.get_tool_scene_id,
                    )
                ]
            return [IAMPermission(actions=[ActionEnum.MANAGE_PLATFORM])]

        return [IsAuthenticated()]

    resource_routes = [
        ResourceRoute("PUT", resource.meta.save_tag_bindings, endpoint="bindings"),
    ]
