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

from apps.meta.permissions import SystemPermissionHandler


class SystemDiagnosisViewSet(ResourceViewSet):
    def get_permissions(self):
        if self.action in ["change_diagnosis_push", "delete_diagnosis_push"]:
            return SystemPermissionHandler.system_edit_permissions(lookup_field="pk")
        return []

    resource_routes = [
        # 系统诊断推送接口
        ResourceRoute(
            "PUT",
            resource.meta.change_system_diagnosis_push,
            endpoint="change_diagnosis_push",
            pk_field="system_id",
        ),
        ResourceRoute(
            "DELETE",
            resource.meta.delete_system_diagnosis_push,
            endpoint="delete_diagnosis_push",
            pk_field="system_id",
        ),
    ]
