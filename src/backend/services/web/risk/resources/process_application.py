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

import abc

from blueapps.utils.request_provider import get_local_request, get_request_username
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy

from apps.audit.resources import AuditMixinResource
from apps.meta.constants import OrderTypeChoices
from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.drf import ActionPermission
from apps.permission.handlers.resource_types import ResourceEnum
from services.web.risk.constants import ApproveTicketFields, RiskStatus
from services.web.risk.models import (
    ProcessApplication,
    Risk,
    RiskRule,
    TicketPermission,
    UserType,
)
from services.web.risk.serializers import (
    CreateProcessApplicationsReqSerializer,
    ListProcessApplicationsReqSerializer,
    ListRiskResponseSerializer,
    ProcessApplicationsInfoSerializer,
    RiskRuleInfoSerializer,
    ToggleProcessApplicationReqSerializer,
    UpdateProcessApplicationsReqSerializer,
)


class ProcessApplicationMeta(AuditMixinResource, abc.ABC):
    tags = ["ProcessApplication"]


class ListProcessApplications(ProcessApplicationMeta):
    name = gettext_lazy("获取处理套餐列表")
    RequestSerializer = ListProcessApplicationsReqSerializer
    ResponseSerializer = ProcessApplicationsInfoSerializer
    many_response_data = True
    audit_action = ActionEnum.LIST_PA

    def perform_request(self, validated_request_data):
        # 构造排序条件
        order_field = validated_request_data.pop("order_field", "-created_at")
        # 构造筛选条件
        q = Q()
        for key, val in validated_request_data.items():
            _q = Q()
            for item in val:
                _q |= Q(**{key: item})
            q &= _q
        # 筛选数据
        process_applications = ProcessApplication.objects.filter(q).order_by("-is_enabled", order_field)
        # 获取关联的规则
        rule_map = {
            item["pa_id"]: item["count"]
            for item in RiskRule.load_latest_rules()
            .filter(pa_id__in=process_applications.values("id"))
            .values("pa_id")
            .annotate(count=Count("pa_id"))
            .order_by()
        }
        for pa in process_applications:
            setattr(pa, "rule_count", rule_map.get(pa.id, 0))
        return process_applications


class ListAllProcessApplications(ProcessApplicationMeta):
    name = gettext_lazy("获取所有处理套餐列表")
    audit_action = ActionEnum.LIST_PA

    def perform_request(self, validated_request_data):
        if (
            not ActionPermission(
                actions=[
                    ActionEnum.LIST_PA,
                    ActionEnum.LIST_RISK,
                    ActionEnum.PROCESS_RISK,
                    ActionEnum.CREATE_RULE,
                    ActionEnum.EDIT_RULE,
                    ActionEnum.LIST_RULE,
                ]
            ).has_permission(request=get_local_request(), view=self)
            and not TicketPermission.objects.filter(user=get_request_username(), user_type=UserType.OPERATOR).exists()
        ):
            return []
        return [
            {"id": pa.id, "name": pa.name, "sops_template_id": pa.sops_template_id, "is_enabled": pa.is_enabled}
            for pa in ProcessApplication.objects.all()
        ]


class CreateProcessApplication(ProcessApplicationMeta):
    name = gettext_lazy("创建处理套餐")
    RequestSerializer = CreateProcessApplicationsReqSerializer
    ResponseSerializer = ProcessApplicationsInfoSerializer
    audit_action = ActionEnum.CREATE_PA

    def perform_request(self, validated_request_data):
        return ProcessApplication.objects.create(**validated_request_data)


class UpdateProcessApplication(ProcessApplicationMeta):
    name = gettext_lazy("更新处理套餐")
    RequestSerializer = UpdateProcessApplicationsReqSerializer
    ResponseSerializer = ProcessApplicationsInfoSerializer
    audit_action = ActionEnum.EDIT_PA

    def perform_request(self, validated_request_data):
        pa = get_object_or_404(ProcessApplication, id=validated_request_data["id"])
        for key, val in validated_request_data.items():
            setattr(pa, key, val)
        pa.save()
        return pa


class ListRiskByPA(ProcessApplicationMeta):
    name = gettext_lazy("获取处理套餐命中的风险")
    ResponseSerializer = ListRiskResponseSerializer
    many_response_data = True
    audit_action = ActionEnum.LIST_RISK
    audit_resource_type = ResourceEnum.RISK

    def perform_request(self, validated_request_data):
        # 获取处理套餐实例
        pa = get_object_or_404(ProcessApplication, id=validated_request_data["id"])
        # 获取规则列表
        rules = RiskRule.objects.filter(pa_id=pa.id)
        # 拼接筛选条件
        q = Q()
        for rule in rules:
            q |= Q(rule_id=rule.rule_id, rule_version=rule.version)
        risks = Risk.load_authed_risks(action=ActionEnum.LIST_RISK).exclude(status=RiskStatus.CLOSED).filter(q)
        return risks


class ListRuleByPA(ProcessApplicationMeta):
    name = gettext_lazy("获取处理套餐关联的规则")
    ResponseSerializer = RiskRuleInfoSerializer
    many_response_data = True
    audit_action = ActionEnum.LIST_RULE

    def perform_request(self, validated_request_data):
        # 获取处理套餐实例
        pa = get_object_or_404(ProcessApplication, id=validated_request_data["id"])
        # 获取规则列表
        order_field = validated_request_data.get("order_field", "-created_at")
        order_field = (
            f"-{order_field}" if validated_request_data.get("order_type") == OrderTypeChoices.DESC else order_field
        )
        return RiskRule.load_latest_rules().filter(pa_id=pa.id).order_by("-is_enabled", order_field)


class ToggleProcessApplication(ProcessApplicationMeta):
    name = gettext_lazy("启停处理套餐")
    RequestSerializer = ToggleProcessApplicationReqSerializer
    audit_action = ActionEnum.EDIT_PA

    def perform_request(self, validated_request_data):
        pa = get_object_or_404(ProcessApplication, id=validated_request_data["id"])
        pa.is_enabled = validated_request_data["is_enabled"]
        pa.save(update_fields=["is_enabled"])


class ApproveBuildInFields(ProcessApplicationMeta):
    name = gettext_lazy("审批内置字段")

    def perform_request(self, validated_request_data):
        return [
            {"id": getattr(ApproveTicketFields, f).key, "name": getattr(ApproveTicketFields, f).key}
            for f in dir(ApproveTicketFields)
            if not f.startswith("_") and f not in ["RISK_LEVEL", "DESCRIPTION"]
        ]
