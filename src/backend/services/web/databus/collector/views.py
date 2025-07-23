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

from bk_resource import api, resource
from bk_resource.viewsets import ResourceRoute, ResourceViewSet
from django.utils.translation import gettext

from apps.meta.permissions import SystemPermissionHandler
from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.drf import (
    IAMPermission,
    InstanceActionPermission,
    insert_permission_field,
)
from apps.permission.handlers.resource_types import ResourceEnum
from core.exceptions import ValidationError
from services.web.databus.models import CollectorConfig


class CollectorsViewSet(ResourceViewSet):
    def get_permissions(self):
        if self.action in [
            "etl_preview",
            "batch_subscription_status",
            "bulk_system_collectors_status",
            "pre_check",
            "list_bcs_clusters",
            "validate_container_config_yaml",
            "get_bcs_yaml_template",
        ]:
            return []
        if self.action in ["api_push", "create_api_push", "api_push_tail_log"]:
            return [
                InstanceActionPermission(
                    actions=[ActionEnum.EDIT_SYSTEM],
                    resource_meta=ResourceEnum.SYSTEM,
                    get_instance_id=self.get_system_id,
                )
            ]
        if self.action in ["join_data"]:
            return [IAMPermission(actions=[ActionEnum.MANAGE_GLOBAL_SETTING])]
        if self.action == "get_collector_info":
            return [
                SystemPermissionHandler.system_view_permissions(get_instance_id=self.get_system_id),
                InstanceActionPermission(
                    actions=[ActionEnum.VIEW_COLLECTION_BK_LOG],
                    resource_meta=ResourceEnum.COLLECTION_BK_LOG,
                    get_instance_id=self.get_collector_config_id,
                ),
            ]

        if self.action in ["update_collector", "delete_collector"]:
            return [
                SystemPermissionHandler.system_edit_permissions(get_instance_id=self.get_system_id),
                InstanceActionPermission(
                    actions=[
                        ActionEnum.VIEW_COLLECTION_BK_LOG,
                        ActionEnum.MANAGE_COLLECTION_BK_LOG,
                    ],
                    resource_meta=ResourceEnum.COLLECTION_BK_LOG,
                    get_instance_id=self.get_collector_config_id,
                ),
            ]
        return SystemPermissionHandler.system_view_permissions(get_instance_id=self.get_system_id)

    def get_collector_config_id(self):
        return (
            self.kwargs.get("pk")
            or self.request.query_params.get("collector_config_id")
            or self.request.data.get("collector_config_id")
        )

    def get_system_id(self):
        # step 1: 根据collector_id转换成实际的system_id
        collector_config_id = self.kwargs.get("pk")
        if not collector_config_id:
            collector_config_id = self.request.query_params.get(
                "collector_config_id", self.request.data.get("collector_config_id")
            )

        if collector_config_id:
            collector = resource.databus.collector.get_collector(collector_config_id=collector_config_id)
            return collector["system_id"]

        # step 2: 直接从数据中获取 system_id
        system_id = self.request.query_params.get("system_id", self.request.data.get("system_id"))
        if system_id:
            return system_id
        raise ValidationError(message=gettext("无法获取系统ID"))

    resource_routes = [
        ResourceRoute(
            "GET",
            resource.databus.collector.get_collectors,
            decorators=[
                insert_permission_field(
                    actions=[ActionEnum.VIEW_COLLECTION_BK_LOG, ActionEnum.MANAGE_COLLECTION_BK_LOG],
                    id_field=lambda item: item["collector_config_id"],
                )
            ],
        ),
        ResourceRoute("GET", resource.databus.collector.get_collector_info, pk_field="collector_config_id"),
        ResourceRoute("PUT", resource.databus.collector.update_collector, pk_field="collector_config_id"),
        ResourceRoute("DELETE", resource.databus.collector.delete_collector, pk_field="collector_config_id"),
        ResourceRoute("POST", resource.databus.collector.create_collector),
        ResourceRoute(
            "POST",
            resource.databus.collector.collector_etl,
            endpoint="collector_etl",
            pk_field="collector_config_id",
        ),
        ResourceRoute(
            "GET", api.bk_log.get_subscript_task_status, endpoint="task_status", pk_field="collector_config_id"
        ),
        ResourceRoute("GET", api.bk_log.get_collector_tail_log, endpoint="tail_log", pk_field="collector_config_id"),
        ResourceRoute(
            "GET",
            resource.databus.collector.system_collectors_status,
            endpoint="system_collectors_status",
        ),
        ResourceRoute(
            "GET",
            resource.databus.collector.bulk_system_collectors_status,
            endpoint="bulk_system_collectors_status",
        ),
        ResourceRoute(
            "GET", api.bk_log.get_subscript_task_detail, endpoint="task_detail", pk_field="collector_config_id"
        ),
        ResourceRoute("POST", api.bk_log.retry_subscript_task, endpoint="retry_task", pk_field="collector_config_id"),
        ResourceRoute(
            "GET", api.bk_log.get_subscription_status, pk_field="collector_config_id", endpoint="subscription_status"
        ),
        ResourceRoute("POST", resource.databus.collector.etl_preview, endpoint="etl_preview"),
        ResourceRoute("GET", api.bk_log.batch_subscription_status, endpoint="batch_subscription_status"),
        ResourceRoute("PUT", resource.databus.collector.toggle_join_data, endpoint="join_data"),
        ResourceRoute(
            "GET",
            resource.databus.collector.etl_field_history,
            endpoint="etl_field_history",
            pk_field="collector_config_id",
        ),
        ResourceRoute("GET", api.bk_log.pre_check_collector_en_name, endpoint="pre_check"),
        ResourceRoute("POST", api.bk_log.validate_container_config_yaml, endpoint="validate_container_config_yaml"),
        ResourceRoute("GET", resource.databus.collector.get_bcs_yaml_template, endpoint="get_bcs_yaml_template"),
        ResourceRoute("POST", resource.databus.collector.create_bcs_collector, endpoint="bcs_collector"),
        ResourceRoute(
            "PUT",
            resource.databus.collector.update_bcs_collector,
            endpoint="update_bcs_collector",
            pk_field="collector_config_id",
        ),
        ResourceRoute("GET", resource.databus.collector.get_api_push, endpoint="api_push"),
        ResourceRoute("POST", resource.databus.collector.create_api_push, endpoint="create_api_push"),
        ResourceRoute("GET", resource.databus.collector.api_push_host, endpoint="api_push_host"),
        ResourceRoute("GET", resource.databus.collector.api_push_tail_log, endpoint="api_push_tail_log"),
        ResourceRoute("GET", resource.databus.collector.snapshot_status, endpoint="snapshot_status"),
    ]


class DataIdBase:
    def get_system_id(self):
        # step 1: 根据bk_data_id转换成实际的system_id
        bk_data_id = self.kwargs.get("pk")
        if not bk_data_id:
            bk_data_id = self.request.query_params.get("bk_data_id") or self.request.data.get("bk_data_id")
        if bk_data_id:
            try:
                return CollectorConfig.objects.get(bk_data_id=bk_data_id).system_id
            except CollectorConfig.DoesNotExist:
                pass
        # step 2: 直接从数据中获取 system_id
        system_id = self.request.query_params.get("system_id") or self.request.data.get("system_id")
        if system_id:
            return system_id
        raise ValidationError(message=gettext("无法获取系统ID"))


class DataIdsViewSet(DataIdBase, ResourceViewSet):
    def get_permissions(self):
        if self.action in ["list"]:
            return SystemPermissionHandler.system_view_permissions(get_instance_id=self.get_system_id)
        if self.action in ["tail", "destroy"]:
            return [
                InstanceActionPermission(
                    actions=[ActionEnum.EDIT_SYSTEM],
                    resource_meta=ResourceEnum.SYSTEM,
                    get_instance_id=self.get_system_id,
                )
            ]
        return []

    resource_routes = [
        ResourceRoute("POST", resource.databus.collector.apply_data_id_source, endpoint="apply_source"),
        ResourceRoute("GET", resource.databus.collector.get_system_data_id_list),
        ResourceRoute("GET", resource.databus.collector.get_my_data_id_list, endpoint="mine"),
        ResourceRoute("GET", resource.databus.collector.get_data_id_detail, pk_field="bk_data_id"),
        ResourceRoute("GET", resource.databus.collector.get_data_id_tail, pk_field="bk_data_id", endpoint="tail"),
        ResourceRoute("DELETE", resource.databus.collector.delete_data_id, pk_field="bk_data_id"),
    ]


class DataIdEtlViewSet(DataIdBase, ResourceViewSet):
    def get_permissions(self):
        if self.action in ["create", "field_history"]:
            return [
                InstanceActionPermission(
                    actions=[ActionEnum.EDIT_SYSTEM],
                    resource_meta=ResourceEnum.SYSTEM,
                    get_instance_id=self.get_system_id,
                )
            ]
        return []

    resource_routes = [
        ResourceRoute("POST", resource.databus.collector.data_id_etl_storage),
        ResourceRoute("POST", resource.databus.collector.data_id_etl_preview, endpoint="preview"),
        ResourceRoute(
            "GET", resource.databus.collector.data_id_etl_field_history, pk_field="bk_data_id", endpoint="field_history"
        ),
    ]
