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
from typing import Callable, List, Set

from django.shortcuts import get_object_or_404
from django.utils.translation import gettext

from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.drf import IAMPermission, InstanceActionPermission
from apps.permission.handlers.permission import Permission
from apps.permission.handlers.resource_types import ResourceEnum
from core.exceptions import PermissionException
from services.web.risk.models import Risk, TicketPermission, UserType
from services.web.strategy_v2.models import Strategy


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
        super().__init__(actions=[ActionEnum.PROCESS_RISK])

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


class BatchRiskTicketPermission(IAMPermission):
    """
    批量风险处理权限
    """

    def __init__(self, get_risk_ids: Callable):
        super().__init__(actions=[ActionEnum.PROCESS_RISK])
        self.get_risk_ids = get_risk_ids

    def has_permission(self, request, view):
        # 校验风险处理人
        risk_ids = self.get_risk_ids()
        risks = Risk.objects.filter(risk_id__in=risk_ids).only("current_operator")
        no_permission_risk_ids = [
            risk.risk_id
            for risk in risks
            if not (risk.current_operator and request.user.username in risk.current_operator)
        ]
        if not no_permission_risk_ids:
            return True
        # 校验IAM权限
        self.resources = [risk_objs[0] for risk_objs in ResourceEnum.RISK.batch_create_instance(no_permission_risk_ids)]
        return super().has_permission(request, view)


class GenerateStrategyRiskPermission:
    """
    手动生成策略风险权限
    """

    def __init__(self, request):
        self.request = request
        self.perm_client = Permission(request=request)

    @staticmethod
    def _collect_strategy_ids(events: List[dict]) -> Set[int]:
        strategy_ids = set()
        for event in events:
            strategy_id = event.get("strategy_id")
            if isinstance(strategy_id, int):
                strategy_ids.add(strategy_id)
            elif isinstance(strategy_id, str) and strategy_id.strip().isdigit():
                strategy_ids.add(int(strategy_id))
        return strategy_ids

    def ensure_allowed(self, events: List[dict]):
        user = getattr(self.request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            self._raise_permission_denied()

        strategy_ids = self._collect_strategy_ids(events)
        if not strategy_ids:
            self._raise_permission_denied()

        strategy_records = Strategy.objects.filter(strategy_id__in=strategy_ids).values(
            "strategy_id", "created_by", "updated_by"
        )
        found_ids = {record["strategy_id"] for record in strategy_records}
        owner_ids = {
            record["strategy_id"]
            for record in strategy_records
            if user.username and user.username in {record.get("created_by") or "", record.get("updated_by") or ""}
        }

        missing_ids = strategy_ids.difference(found_ids)
        if missing_ids:
            self._raise_permission_denied(ResourceEnum.STRATEGY.create_instance(missing_ids.pop()))

        for strategy_id in strategy_ids.difference(owner_ids):
            resource = ResourceEnum.STRATEGY.create_instance(strategy_id)
            if any(
                self.perm_client.is_allowed(action, [resource])
                for action in (ActionEnum.EDIT_STRATEGY, ActionEnum.GENERATE_STRATEGY_RISK)
            ):
                continue
            self._raise_permission_denied(resource)

    def _raise_permission_denied(self, resource=None):
        resources = [resource] if resource else []
        apply_data, apply_url = self.perm_client.get_apply_data([ActionEnum.GENERATE_STRATEGY_RISK], resources)
        raise PermissionException(
            action_name=gettext(ActionEnum.GENERATE_STRATEGY_RISK.name),
            permission=apply_data,
            apply_url=apply_url,
        )
