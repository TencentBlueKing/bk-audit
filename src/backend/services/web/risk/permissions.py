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
from typing import Callable, List, Optional, Set

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext

from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.drf import IAMPermission, InstanceActionPermission
from apps.permission.handlers.resource_types import ResourceEnum
from apps.permission.handlers.service import PermissionService
from core.exceptions import PermissionException, ValidationError
from core.models import get_request_username
from core.utils.data import get_value_by_request
from services.web.risk.exceptions import RiskConfirmPermissionDenied
from services.web.risk.models import Risk, TicketNode, TicketPermission, UserType
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
                    user_type__in=[UserType.NOTICE_USER, UserType.OPERATOR, UserType.CONFIRMER],
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


def user_may_confirm_risk(username: str, risk: Risk) -> bool:
    """确认人或平台管理员可对待确认风险做二次确认。"""

    if risk.confirmer and username in risk.confirmer:
        return True
    return PermissionService().is_allowed(ActionEnum.MANAGE_PLATFORM)


def ensure_user_may_confirm_risk(username: str, risk: Risk) -> None:
    if not user_may_confirm_risk(username, risk):
        raise RiskConfirmPermissionDenied()


class RiskConfirmPermission(IAMPermission):
    """确认人，或平台管理员，可确认。传入 get_risk_ids 时按批量校验。"""

    def __init__(self, get_risk_ids: Callable = None):
        super().__init__(actions=[ActionEnum.MANAGE_PLATFORM])
        self.get_risk_ids = get_risk_ids

    def has_permission(self, request, view):
        username = request.user.username
        if self.get_risk_ids:
            risks = Risk.objects.filter(risk_id__in=self.get_risk_ids()).only("confirmer")
            if bool(risks) and all(risk.confirmer and username in risk.confirmer for risk in risks):
                return True
            if PermissionService().is_allowed(ActionEnum.MANAGE_PLATFORM):
                return True
            raise RiskConfirmPermissionDenied()
        risk_id = view.kwargs.get("pk") or request.data.get("risk_id") or request.query_params.get("risk_id") or ""
        if not risk_id:
            if PermissionService().is_allowed(ActionEnum.MANAGE_PLATFORM):
                return True
            raise RiskConfirmPermissionDenied()
        risk = get_object_or_404(Risk, risk_id=risk_id)
        ensure_user_may_confirm_risk(username, risk)
        return True


class GenerateStrategyRiskPermission:
    """
    手动生成策略风险权限
    """

    def __init__(self, request):
        self.request = request
        self.perm_client = PermissionService(request=request)

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


def strategy_id_of_risk(risk_id: str):
    """由样例风险单反查所属策略。风险不存在或未关联策略时返回 None。"""

    if not risk_id:
        return None
    return Risk.objects.filter(risk_id=risk_id).values_list("strategy_id", flat=True).first()


def find_bksec_test_node_by_task_id(task_id: str) -> Optional[TicketNode]:
    """
    按 SOPS task_id 精确查找测试节点。

    process_result.task.task_id 可能存成 int 或 str，JSON 查询对类型敏感，两种都匹配。
    只命中测试节点，正式派单任务不能经这个入口回源。
    """

    normalized = str(task_id or "").strip()
    if not normalized:
        return None
    lookup = Q(process_result__task__task_id=normalized)
    if normalized.isdigit():
        lookup |= Q(process_result__task__task_id=int(normalized))
    return TicketNode.objects.filter(is_test=True, action="AutoProcess").filter(lookup).order_by("-timestamp").first()


def ensure_strategy_edit_permission(strategy_id) -> None:
    """校验当前用户对目标策略实例的编辑权限。无实例 ID 时直接拒绝。"""

    if strategy_id is None or str(strategy_id).strip().lower() in {"", "none", "null"}:
        raise ValidationError(message=gettext("无法获取权限校验资源实例ID"))
    username = get_request_username()
    client = PermissionService(username=username) if username else PermissionService()
    client.is_allowed(
        action=ActionEnum.EDIT_STRATEGY,
        resources=[ResourceEnum.STRATEGY.create_instance(strategy_id)],
        raise_exception=True,
    )


def ensure_risk_view_permission(risk_id: str) -> None:
    """
    校验当前用户对目标风险实例的查看权限，与预览、试发入口（RiskViewPermission）口径一致。

    本地票据（处理人/关注人/确认人）命中直接通过，否则走 IAM LIST_RISK；无权限抛 PermissionException。
    测试任务状态查询在回源 SOPS 前调用，防止持他人测试任务 ID 越权读取任务状态与节点失败原文。
    """

    permission = RiskViewPermission(actions=[ActionEnum.LIST_RISK], resource_meta=ResourceEnum.RISK)
    allowed = permission.has_risk_permission(risk_id=risk_id, operator=get_request_username())
    if not allowed:
        raise PermissionException(action_name=gettext(ActionEnum.LIST_RISK.name), permission={})


class BkSecTestTaskStatusPermission(IAMPermission):
    """
    测试任务状态查询权限。

    task_id 能定位到测试节点时，校验该节点风险所属策略的编辑权限。
    节点不存在时放行，由资源层返回 404，避免把「任务不存在」报成缺少实例 ID，也不回源 SOPS。
    只传 risk_id 时直接校验该风险所属策略。
    策略编辑通过后追加关联风险的查看鉴权，与预览、试发入口口径对齐，
    防止同策略编辑者持他人测试任务 ID 越权读取任务状态与节点失败原文。
    """

    def __init__(self):
        super().__init__(actions=[ActionEnum.EDIT_STRATEGY])

    def has_permission(self, request, view):
        task_id = get_value_by_request(request, "task_id") or ""
        risk_id = get_value_by_request(request, "risk_id") or ""
        if task_id:
            node = find_bksec_test_node_by_task_id(task_id)
            if node is None:
                return True
            risk_id = node.risk_id
        elif not risk_id:
            return True
        strategy_id = strategy_id_of_risk(risk_id)
        if strategy_id is None or str(strategy_id).strip().lower() in {"", "none", "null"}:
            raise ValidationError(message=gettext("无法获取权限校验资源实例ID"))
        self.resources = [ResourceEnum.STRATEGY.create_instance(strategy_id)]
        result = super().has_permission(request, view)
        ensure_risk_view_permission(risk_id)
        return result
