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

from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.drf import (
    IAMPermission,
    InstanceActionPermission,
    insert_action_permission_field,
)
from apps.permission.handlers.resource_types import ResourceEnum


class SystemsViewSet(ResourceViewSet):
    def get_permissions(self):
        if self.action in ["all"]:
            return []
        if self.action in ["list"]:
            return [IAMPermission(actions=[ActionEnum.LIST_SYSTEM])]
        return [InstanceActionPermission(actions=[ActionEnum.VIEW_SYSTEM], resource_meta=ResourceEnum.SYSTEM)]

    resource_routes = [
        ResourceRoute("GET", resource.meta.system_list, enable_paginate=True),
        ResourceRoute("GET", resource.meta.system_info, pk_field="system_id"),
        # 附带权限信息
        ResourceRoute("GET", resource.meta.system_list_all, endpoint="all"),
        # 新增系统操作
        ResourceRoute("POST", resource.meta.create_system),
        ResourceRoute("PUT", resource.meta.update_system, pk_field="system_id"),
        ResourceRoute("PUT", resource.meta.favorite_system, pk_field="system_id", endpoint="favorite"),
    ]


class ResourceTypesViewSet(ResourceViewSet):
    """资源类型接口"""

    def get_permissions(self):
        if self.action in ["resource_type_search"]:
            return []
        if self.action in ["resource_type_schema_search"]:
            return [
                InstanceActionPermission(actions=[ActionEnum.SEARCH_REGULAR_EVENT], resource_meta=ResourceEnum.SYSTEM)
            ]
        return [InstanceActionPermission(actions=[ActionEnum.VIEW_SYSTEM], resource_meta=ResourceEnum.SYSTEM)]

    resource_routes = [
        ResourceRoute(
            "GET",
            resource.meta.resource_type_list,
            pk_field="system_id",
            endpoint="resource_types",
            decorators=[insert_action_permission_field(actions=[ActionEnum.MANAGE_GLOBAL_SETTING])],
        ),
        ResourceRoute("GET", resource.meta.resource_type_schema, pk_field="system_id", endpoint="resource_type_schema"),
        ResourceRoute("GET", resource.meta.resource_type_search_list, endpoint="resource_type_search"),
        ResourceRoute(
            "GET", resource.meta.resource_type_schema, pk_field="system_id", endpoint="resource_type_schema_search"
        ),
        # 新增资源类型操作
        ResourceRoute("POST", resource.meta.create_resource_type),
        ResourceRoute("PUT", resource.meta.update_resource_type, pk_field="system_id"),
        ResourceRoute("PUT", resource.meta.bulk_update_resource_type, endpoint="bulk"),
        ResourceRoute("DELETE", resource.meta.delete_resource_type, pk_field="system_id"),
    ]


class ActionsViewSet(ResourceViewSet):
    """操作接口"""

    def get_permissions(self):
        return []

    resource_routes = [
        ResourceRoute("GET", resource.meta.action_list, pk_field="system_id", endpoint="actions"),
        ResourceRoute("GET", resource.meta.action_search_list, endpoint="action_search"),
        # 新增操作操作
        ResourceRoute("POST", resource.meta.create_action),
        ResourceRoute("PUT", resource.meta.update_action, pk_field="system_id"),
        ResourceRoute("PUT", resource.meta.bulk_update_action, endpoint="bulk"),
        ResourceRoute("DELETE", resource.meta.delete_action, pk_field="system_id"),
    ]


class ResourceTypesViewSet(ResourceViewSet):
    lookup_field = "unique_id"

    def get_system_id(self):
        return self.kwargs.get('system_id') or self.kwargs.get('unique_id', '').spilit(':')[0]

    def get_permissions(self):
        if self.action not in ["bulk_create"]:
            return [
                InstanceActionPermission(
                    actions=[ActionEnum.EDIT_SYSTEM],
                    resource_meta=ResourceEnum.SYSTEM,
                    get_instance_id=self.get_system_id,
                )
            ]
        return []

    resource_routes = [
        ResourceRoute("GET", resource.meta.list_resource_type),
        ResourceRoute("GET", resource.meta.get_resource_type_tree, endpoint="tree"),
        ResourceRoute("POST", resource.meta.bulk_create_resource_type, endpoint="bulk_create"),
        ResourceRoute("POST", resource.meta.create_resource_type),
        ResourceRoute("GET", resource.meta.get_resource_type, pk_field='unique_id'),
        ResourceRoute("PUT", resource.meta.update_resource_type, pk_field='unique_id'),
        ResourceRoute("DELETE", resource.meta.delete_resource_type, pk_field='unique_id'),
    ]
