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

from apps.permission.handlers.actions.action import ActionEnum
from apps.permission.handlers.drf import IAMPermission, insert_action_permission_field


class StoragesViewSet(ResourceViewSet):
    iam_action_mappings = {
        "list": ActionEnum.LIST_STORAGE,
        "create": ActionEnum.CREATE_STORAGE,
        "update": ActionEnum.EDIT_STORAGE,
        "destroy": ActionEnum.DELETE_STORAGE,
        "activate": ActionEnum.EDIT_STORAGE,
    }

    def get_permissions(self):
        # redis 为创建/更新二合一端点，按请求体 redis_id 拆分写权限（BKSEC 1578945）：
        # 无 redis_id → 创建 → CREATE_STORAGE；有 redis_id → 更新 → EDIT_STORAGE
        if self.action == "redis":
            redis_id = self._get_redis_id()
            action = ActionEnum.EDIT_STORAGE if redis_id else ActionEnum.CREATE_STORAGE
            return [IAMPermission(actions=[action])]
        if self.iam_action_mappings.get(self.action):
            return [IAMPermission(actions=[self.iam_action_mappings[self.action]])]
        return [IAMPermission(actions=[ActionEnum.LIST_STORAGE])]

    def _get_redis_id(self):
        """从请求体获取 redis_id（DRF initialize_request 先于 get_permissions，request.data 可用）"""
        try:
            return self.request.data.get("redis_id")
        except Exception:  # NOCC:broad-except(非 JSON body 等场景按创建处理，由 IAM 权限兜底)
            return None

    resource_routes = [
        ResourceRoute(
            "GET",
            resource.databus.storage.storage_list,
            decorators=[insert_action_permission_field(actions=[ActionEnum.EDIT_STORAGE, ActionEnum.DELETE_STORAGE])],
        ),
        ResourceRoute("POST", api.bk_log.connectivity_detect, endpoint="connectivity_detect"),
        ResourceRoute("GET", api.bk_log.batch_connectivity_detect, endpoint="batch_connectivity_detect"),
        ResourceRoute("POST", resource.databus.storage.create_storage),
        ResourceRoute("PUT", resource.databus.storage.update_storage, pk_field="cluster_id"),
        ResourceRoute("DELETE", resource.databus.storage.delete_storage, pk_field="cluster_id"),
        ResourceRoute("POST", api.bk_log.node_attrs, endpoint="node_attrs"),
        ResourceRoute("PUT", resource.databus.storage.storage_activate, pk_field="cluster_id", endpoint="activate"),
        ResourceRoute("POST", resource.databus.storage.create_or_update_redis, endpoint="redis"),
    ]
