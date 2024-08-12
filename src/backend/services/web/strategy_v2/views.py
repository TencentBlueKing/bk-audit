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
    insert_permission_field,
)
from apps.permission.handlers.resource_types import ResourceEnum


class StrategyViewSet(ResourceViewSet):
    def get_permissions(self):
        if self.action in ["list"]:
            return [IAMPermission(actions=[ActionEnum.LIST_STRATEGY])]
        if self.action in ["create"]:
            return [IAMPermission(actions=[ActionEnum.CREATE_STRATEGY])]
        if self.action in ["update", "toggle", "retry"]:
            return [InstanceActionPermission(actions=[ActionEnum.EDIT_STRATEGY], resource_meta=ResourceEnum.STRATEGY)]
        if self.action in ["destroy"]:
            return [InstanceActionPermission(actions=[ActionEnum.DELETE_STRATEGY], resource_meta=ResourceEnum.STRATEGY)]
        return []

    resource_routes = [
        ResourceRoute(
            "GET",
            resource.strategy_v2.list_strategy,
            enable_paginate=True,
            decorators=[
                insert_permission_field(
                    actions=[ActionEnum.EDIT_STRATEGY, ActionEnum.DELETE_STRATEGY],
                    id_field=lambda item: item["strategy_id"],
                    data_field=lambda data: data["results"],
                )
            ],
        ),
        ResourceRoute("GET", resource.strategy_v2.list_strategy_all, endpoint="all"),
        ResourceRoute("POST", resource.strategy_v2.create_strategy),
        ResourceRoute("PUT", resource.strategy_v2.update_strategy, pk_field="strategy_id"),
        ResourceRoute("DELETE", resource.strategy_v2.delete_strategy, pk_field="strategy_id"),
        ResourceRoute("POST", resource.strategy_v2.toggle_strategy, pk_field="strategy_id", endpoint="toggle"),
        ResourceRoute("GET", resource.strategy_v2.get_strategy_common, endpoint="common"),
        ResourceRoute("GET", resource.strategy_v2.get_strategy_status, endpoint="status"),
        ResourceRoute("PUT", resource.strategy_v2.retry_strategy, pk_field="strategy_id", endpoint="retry"),
        ResourceRoute("GET", resource.strategy_v2.get_strategy_display_info, endpoint="display_info"),
    ]


class StrategyTagsViewSet(ResourceViewSet):
    def get_permissions(self):
        if self.action in ["list"]:
            return [IAMPermission(actions=[ActionEnum.LIST_STRATEGY])]
        return []

    resource_routes = [
        ResourceRoute("GET", resource.strategy_v2.list_strategy_tags),
    ]


class StrategyFieldsViewSet(ResourceViewSet):
    def get_permissions(self):
        if self.action in ["fields_config"]:
            return [IAMPermission(actions=[ActionEnum.LIST_STRATEGY])]
        return []

    resource_routes = [
        ResourceRoute("GET", resource.strategy_v2.list_strategy_fields),
        ResourceRoute("GET", resource.strategy_v2.get_strategy_field_value, endpoint="value"),
        ResourceRoute("GET", resource.strategy_v2.get_event_fields_config, endpoint="fields_config"),
    ]


class StrategyTableViewSet(ResourceViewSet):
    resource_routes = [
        ResourceRoute("GET", resource.strategy_v2.list_tables),
        ResourceRoute("GET", resource.strategy_v2.get_rt_fields, endpoint="rt_fields"),
    ]
