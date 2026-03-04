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
    ActionPermission,
    AnyOfPermissions,
    IAMPermission,
    InstanceActionPermission,
    insert_permission_field,
)
from apps.permission.handlers.resource_types import ResourceEnum
from services.web.tool.permissions import CallerContextPermission


class StrategyViewSet(ResourceViewSet):
    def get_permissions(self):
        if self.action in ["list", "strategy_running_status_list", "retrieve"]:
            return [IAMPermission(actions=[ActionEnum.LIST_STRATEGY])]
        if self.action in ["create"]:
            return [IAMPermission(actions=[ActionEnum.CREATE_STRATEGY])]
        if self.action in ["update", "toggle", "retry"]:
            return [InstanceActionPermission(actions=[ActionEnum.EDIT_STRATEGY], resource_meta=ResourceEnum.STRATEGY)]
        if self.action in ["destroy"]:
            return [InstanceActionPermission(actions=[ActionEnum.DELETE_STRATEGY], resource_meta=ResourceEnum.STRATEGY)]
        if self.action in ["enum_mapping_by_collection_keys", "enum_mapping_by_collection"]:
            return [AnyOfPermissions(CallerContextPermission(), IAMPermission(actions=[ActionEnum.LIST_STRATEGY]))]
        return []

    resource_routes = [
        ResourceRoute("GET", resource.strategy_v2.retrieve_strategy, pk_field="strategy_id"),
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
        ResourceRoute(
            "POST",
            resource.strategy_v2.get_strategy_enum_mapping_by_collection_keys,
            endpoint="enum_mapping_by_collection_keys",
        ),
        ResourceRoute(
            "POST", resource.strategy_v2.get_strategy_enum_mapping_by_collection, endpoint="enum_mapping_by_collection"
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
        ResourceRoute(
            "POST", resource.strategy_v2.rule_audit_source_type_check, endpoint="rule_audit_source_type_check"
        ),
        ResourceRoute(
            "GET",
            resource.strategy_v2.strategy_running_status_list,
            pk_field="strategy_id",
            endpoint="strategy_running_status_list",
        ),
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
        return []

    resource_routes = [
        ResourceRoute("GET", resource.strategy_v2.list_strategy_fields),
        ResourceRoute("GET", resource.strategy_v2.get_strategy_field_value, endpoint="value"),
        ResourceRoute("GET", resource.strategy_v2.get_event_fields_config, endpoint="fields_config"),
    ]


class StrategyTableViewSet(ResourceViewSet):
    def get_permissions(self):
        return [
            ActionPermission(
                actions=[
                    ActionEnum.CREATE_STRATEGY,
                    ActionEnum.LIST_STRATEGY,
                    ActionEnum.EDIT_STRATEGY,
                    ActionEnum.DELETE_STRATEGY,
                ]
            )
        ]

    resource_routes = [
        ResourceRoute("GET", resource.strategy_v2.list_tables),
        ResourceRoute("GET", resource.strategy_v2.get_rt_fields, endpoint="rt_fields"),
        ResourceRoute("GET", resource.strategy_v2.get_rt_meta, endpoint="rt_meta"),
        ResourceRoute("GET", resource.strategy_v2.get_rt_last_data, endpoint="rt_last_data"),
        ResourceRoute("GET", resource.strategy_v2.bulk_get_rt_fields, endpoint="bulk_rt_fields"),
    ]


class LinkTableViewSet(ResourceViewSet):
    def get_permissions(self):
        if self.action in ["list", "tags"]:
            return [IAMPermission(actions=[ActionEnum.LIST_LINK_TABLE])]
        if self.action in ["create"]:
            return [IAMPermission(actions=[ActionEnum.CREATE_LINK_TABLE])]
        if self.action in ["update"]:
            return [
                InstanceActionPermission(actions=[ActionEnum.EDIT_LINK_TABLE], resource_meta=ResourceEnum.LINK_TABLE)
            ]
        if self.action in ["destroy"]:
            return [
                InstanceActionPermission(actions=[ActionEnum.DELETE_LINK_TABL], resource_meta=ResourceEnum.LINK_TABLE)
            ]
        if self.action in ["retrieve"]:
            return [
                InstanceActionPermission(actions=[ActionEnum.VIEW_LINK_TABLE], resource_meta=ResourceEnum.LINK_TABLE)
            ]
        return []

    resource_routes = [
        ResourceRoute(
            "GET",
            resource.strategy_v2.list_link_table,
            enable_paginate=True,
            decorators=[
                insert_permission_field(
                    actions=[ActionEnum.VIEW_LINK_TABLE, ActionEnum.EDIT_LINK_TABLE, ActionEnum.DELETE_LINK_TABL],
                    id_field=lambda item: item["uid"],
                    data_field=lambda data: data["results"],
                )
            ],
        ),
        ResourceRoute("GET", resource.strategy_v2.get_link_table, pk_field="uid"),
        ResourceRoute("GET", resource.strategy_v2.list_link_table_all, endpoint="all"),
        ResourceRoute("POST", resource.strategy_v2.create_link_table),
        ResourceRoute("PUT", resource.strategy_v2.update_link_table, pk_field="uid"),
        ResourceRoute("DELETE", resource.strategy_v2.delete_link_table, pk_field="uid"),
        ResourceRoute("GET", resource.strategy_v2.list_link_table_tags, endpoint="tags"),
    ]


class ReportViewSet(ResourceViewSet):
    """
    风险报告配置相关接口

    提供报告模板配置所需的风险变量和聚合函数列表。
    以及报告预览接口。
    """

    def get_permissions(self):
        return []

    resource_routes = [
        ResourceRoute("GET", resource.strategy_v2.list_risk_variables, endpoint="risk_variables"),
        ResourceRoute("GET", resource.strategy_v2.list_aggregation_functions, endpoint="aggregation_functions"),
        ResourceRoute("POST", resource.strategy_v2.preview_risk_report, endpoint="preview"),
    ]
