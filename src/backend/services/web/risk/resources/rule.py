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

from blueapps.utils.request_provider import get_local_request
from django.db.models import Q
from django.utils.translation import gettext_lazy

from apps.audit.resources import AuditMixinResource
from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.drf import ActionPermission
from apps.permission.handlers.resource_types import ResourceEnum
from core.exceptions import RiskRuleInUse
from core.utils.data import choices_to_dict
from services.web.risk.constants import RiskRuleOperator, RiskStatus
from services.web.risk.models import Risk, RiskRule, RiskRuleAuditInstance
from services.web.risk.serializers import (
    BatchUpdateRiskRulePriorityIndexReqSerializer,
    CreateRiskRuleReqSerializer,
    ListRiskResponseSerializer,
    ListRiskRuleReqSerializer,
    RiskRuleInfoSerializer,
    ToggleRiskRuleRequestSerializer,
    UpdateRiskRuleReqSerializer,
)
from services.web.scene.constants import ResourceVisibilityType


class RiskRuleMeta(AuditMixinResource, abc.ABC):
    tags = ["RiskRule"]


class ListRiskRule(RiskRuleMeta):
    name = gettext_lazy("风险处理规则列表")
    RequestSerializer = ListRiskRuleReqSerializer
    ResponseSerializer = RiskRuleInfoSerializer
    many_response_data = True
    audit_action = ActionEnum.LIST_RULE

    def perform_request(self, validated_request_data):
        # 场景过滤
        scene_id = validated_request_data.pop("scene_id", None)
        # 排序
        order_field = validated_request_data.pop("order_field", "-priority_index")
        # 构造筛选条件
        q = Q()
        for key, val in validated_request_data.items():
            _q = Q()
            for item in val:
                _q |= Q(**{key: item})
            q &= _q
        # 按场景过滤（通过 ResourceBinding）
        if scene_id is not None:
            from blueapps.utils.request_provider import get_local_request

            from services.web.scene.permissions import check_scene_permission

            check_scene_permission(get_local_request(), scene_id, require_role="user")
        from services.web.scene.filters import SceneScopeFilter

        # 筛选（SceneScopeFilter 会处理 scene_id 过滤，未指定时返回全部）
        rules = SceneScopeFilter.filter_queryset(
            queryset=RiskRule.load_latest_rules().filter(q),
            scene_id=scene_id,
            resource_type=ResourceVisibilityType.RISK_RULE,
            pk_field="rule_id",
        ).order_by(order_field)
        return rules


class ListAllRiskRule(RiskRuleMeta):
    name = gettext_lazy("风险处理规则列表")

    def perform_request(self, validated_request_data):
        if not ActionPermission(
            actions=[ActionEnum.LIST_RULE, ActionEnum.LIST_RISK, ActionEnum.PROCESS_RISK]
        ).has_permission(request=get_local_request(), view=self):
            return []
        return [
            {"id": risk_rule.rule_id, "name": risk_rule.name, "version": risk_rule.version}
            for risk_rule in RiskRule.objects.all()
        ]


class CreateRiskRule(RiskRuleMeta):
    name = gettext_lazy("创建风险处理规则")
    RequestSerializer = CreateRiskRuleReqSerializer
    ResponseSerializer = RiskRuleInfoSerializer
    audit_action = ActionEnum.CREATE_RULE

    def perform_request(self, validated_request_data):
        # 场景权限校验
        scene_id = validated_request_data.pop("scene_id", None)
        if scene_id is not None:
            from blueapps.utils.request_provider import get_local_request

            from services.web.scene.permissions import check_scene_permission

            check_scene_permission(get_local_request(), scene_id, require_role="manager")
        instance: RiskRule = RiskRule.objects.create(**validated_request_data, version=1, is_enabled=False)
        instance.rule_id = instance.id
        instance.priority_index = RiskRule.objects.all().order_by("-priority_index").first().priority_index + 1
        instance.save(update_fields=["rule_id", "priority_index"])
        # 创建 ResourceBinding 关联（scene_id 必传，序列化器已校验）
        from services.web.scene.filters import SceneScopeFilter

        SceneScopeFilter.create_resource_binding(
            resource_id=str(instance.rule_id),
            resource_type=ResourceVisibilityType.RISK_RULE,
            scene_id=scene_id,
        )
        self.add_audit_instance_to_context(instance=RiskRuleAuditInstance(instance))
        return instance


class UpdateRiskRule(RiskRuleMeta):
    name = gettext_lazy("更新风险处理规则")
    RequestSerializer = UpdateRiskRuleReqSerializer
    ResponseSerializer = RiskRuleInfoSerializer
    audit_action = ActionEnum.EDIT_RULE

    def perform_request(self, validated_request_data):
        rule = RiskRule.get_rule_or_404(rule_id=validated_request_data["rule_id"])
        origin_data = RiskRuleInfoSerializer(rule).data
        instance = RiskRule.objects.create(
            **validated_request_data,
            version=rule.version + 1,
            priority_index=rule.priority_index,
            created_at=rule.created_at,
            created_by=rule.created_by,
            is_enabled=rule.is_enabled,
        )
        setattr(instance, "instance_origin_data", origin_data)
        self.add_audit_instance_to_context(instance=RiskRuleAuditInstance(instance))
        return instance


class DeleteRiskRule(RiskRuleMeta):
    name = gettext_lazy("删除风险处理规则")
    audit_action = ActionEnum.DELETE_RULE

    def perform_request(self, validated_request_data):
        if Risk.objects.filter(rule_id=validated_request_data["rule_id"]).exclude(status=RiskStatus.CLOSED).exists():
            raise RiskRuleInUse()
        instances = RiskRule.objects.filter(rule_id=validated_request_data["rule_id"]).order_by("-version")
        if not instances:
            return
        self.add_audit_instance_to_context(instance=RiskRuleAuditInstance(instances.first()))
        instances.delete()


class ListRiskByRule(RiskRuleMeta):
    name = gettext_lazy("获取处理规则命中的风险")
    ResponseSerializer = ListRiskResponseSerializer
    many_response_data = True
    audit_action = ActionEnum.LIST_RISK
    audit_resource_type = ResourceEnum.RISK

    def perform_request(self, validated_request_data):
        rule = RiskRule.get_rule_or_404(rule_id=validated_request_data["rule_id"])
        q = RiskRuleOperator.build_query_filter(rule.scope) & Q(
            Q(event_time__gte=rule.created_at) | Q(status=RiskStatus.NEW)
        )
        qs = Risk.load_authed_risks(action=ActionEnum.LIST_RISK)
        risks = Risk.annotated_queryset(qs).exclude(status=RiskStatus.CLOSED).filter(q)
        return risks


class ToggleRiskRule(RiskRuleMeta):
    name = gettext_lazy("启停风险处理规则")
    RequestSerializer = ToggleRiskRuleRequestSerializer
    ResponseSerializer = RiskRuleInfoSerializer
    audit_action = ActionEnum.EDIT_RULE

    def perform_request(self, validated_request_data):
        rule = RiskRule.get_rule_or_404(rule_id=validated_request_data["rule_id"])
        origin_data = RiskRuleInfoSerializer(rule).data
        rule.is_enabled = validated_request_data["is_enabled"]
        rule.save(update_fields=["is_enabled"])
        setattr(rule, "instance_origin_data", origin_data)
        self.add_audit_instance_to_context(instance=RiskRuleAuditInstance(rule))
        return rule


class ListRiskRuleOperator(RiskRuleMeta):
    name = gettext_lazy("获取风险处理规则匹配方式")

    def perform_request(self, validated_request_data):
        return choices_to_dict(RiskRuleOperator)


class BatchUpdateRiskRulePriorityIndex(RiskRuleMeta):
    name = gettext_lazy("批量调整风险处理规则优先级")
    RequestSerializer = BatchUpdateRiskRulePriorityIndexReqSerializer
    audit_action = ActionEnum.EDIT_RULE

    def perform_request(self, validated_request_data):
        for config in validated_request_data["config"]:
            rule = RiskRule.objects.filter(rule_id=config["rule_id"]).order_by("-version").first()
            if not rule:
                continue
            origin_data = RiskRuleInfoSerializer(rule).data
            RiskRule._objects.filter(rule_id=rule.rule_id).update(
                priority_index=config["priority_index"], is_enabled=config["is_enabled"]
            )
            rule.refresh_from_db()
            setattr(rule, "instance_origin_data", origin_data)
            self.add_audit_instance_to_context(instance=RiskRuleAuditInstance(rule))
