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
from django.shortcuts import get_object_or_404

from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.drf import IAMPermission, InstanceActionPermission
from apps.permission.handlers.resource_types import ResourceEnum
from services.web.risk.models import Risk, TicketPermission, UserType


class RiskViewPermission(InstanceActionPermission):
    """
    风险查看权限
    """

    def has_risk_permission(self, risk_id: str, operator: str) -> bool:
        """
        校验风险权限
        """

        if self.has_risk_local_permission(risk_id, operator):
            return True
        resource = self.resource_meta.create_instance(risk_id)
        self.resources = [resource]
        return IAMPermission.has_permission(self, None, None)

    def has_risk_local_permission(self, risk_id: str, operator: str) -> bool:
        """
        校验本地风险权限。
        """
        return all(
            [
                TicketPermission.objects.filter(
                    user_type__in=[UserType.NOTICE_USER, UserType.OPERATOR],
                    risk_id=risk_id,
                    action=action.id,
                    user=operator,
                ).exists()
                for action in self.actions
            ]
        )

    def has_permission(self, request, view):
        risk_id = view.kwargs.get(self.lookup_field) or self.get_instance_id()
        if self.has_risk_local_permission(risk_id, request.user.username):
            return True
        return super().has_permission(request, view)


class RiskTicketPermission(IAMPermission):
    """
    风险处理权限
    """

    def __init__(self):
        super().__init__(actions=[ActionEnum.EDIT_RISK])

    def has_permission(self, request, view):
        # 校验风险处理人
        risk_id = view.kwargs.get("pk") or request.data.get("risk_id") or request.query_params.get("risk_id") or ""
        if risk_id:
            risk = get_object_or_404(Risk, risk_id=risk_id)
            if risk.current_operator and request.user.username in risk.current_operator:
                return True
        # 校验IAM权限
        self.resources = [ResourceEnum.RISK.create_instance(risk_id)]
        return super().has_permission(request, view)
