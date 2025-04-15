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

import datetime
from functools import cached_property
from typing import List, Union

from bk_audit.constants.log import DEFAULT_EMPTY_VALUE
from bk_audit.log.models import AuditInstance
from blueapps.utils.request_provider import get_request_username
from django.db import models
from django.db.models import Max, Q, QuerySet
from django.utils.translation import gettext_lazy
from iam import DjangoQuerySetConverter

from apps.permission.handlers.actions import ActionEnum, ActionMeta, get_action_by_id
from apps.permission.handlers.permission import Permission
from core.models import OperateRecordModel, SoftDeleteModel, UUIDField
from services.web.risk.constants import (
    EventMappingFields,
    RiskLabel,
    RiskStatus,
    TicketNodeStatus,
)
from services.web.strategy_v2.models import Strategy


def generate_risk_id() -> str:
    """ "
    年月日时分秒+6位随机码
    """

    now = datetime.datetime.now()
    risk_id = f"{now.strftime('%Y%m%d%H%M%S')}{('%.6f' % now.timestamp()).split('.')[1]}"
    if Risk.objects.filter(risk_id=risk_id).exists():
        return generate_risk_id()
    return risk_id


class Risk(OperateRecordModel):
    """
    Risk
    """

    risk_id = models.CharField(gettext_lazy("Risk ID"), primary_key=True, max_length=255, default=generate_risk_id)
    event_content = models.TextField(EventMappingFields.EVENT_CONTENT.description, null=True, blank=True)
    raw_event_id = models.CharField(EventMappingFields.RAW_EVENT_ID.description, max_length=255, db_index=True)
    strategy = models.ForeignKey(
        Strategy,
        db_constraint=False,
        verbose_name=EventMappingFields.STRATEGY_ID.description,
        on_delete=models.DO_NOTHING,
        related_name='risks',
    )
    event_evidence = models.TextField(EventMappingFields.EVENT_EVIDENCE.description, null=True, blank=True)
    event_type = models.JSONField(EventMappingFields.EVENT_TYPE.description, null=True, blank=True, default=list)
    event_data = models.JSONField(EventMappingFields.EVENT_DATA.description, null=True, blank=True)
    event_time = models.DateTimeField(EventMappingFields.EVENT_TIME.description, db_index=True)
    event_end_time = models.DateTimeField(
        EventMappingFields.EVENT_TIME.description, db_index=True, null=True, blank=True
    )
    event_source = models.CharField(
        EventMappingFields.EVENT_SOURCE.description, max_length=255, db_index=True, null=True, blank=True
    )
    operator = models.JSONField(EventMappingFields.OPERATOR.description, null=True, blank=True)
    status = models.CharField(
        gettext_lazy("Risk Status"), choices=RiskStatus.choices, default=RiskStatus.NEW, max_length=32, db_index=True
    )
    rule_id = models.BigIntegerField(gettext_lazy("Risk Rule ID"), null=True, blank=True)
    rule_version = models.IntegerField(gettext_lazy("Risk Rule Version"), null=True, blank=True)
    origin_operator = models.JSONField(
        gettext_lazy("Origin Operator"), max_length=64, null=True, blank=True, default=list
    )
    current_operator = models.JSONField(
        gettext_lazy("Current Operator"), max_length=64, null=True, blank=True, default=list
    )
    notice_users = models.JSONField(gettext_lazy("Notice Users"), default=list, null=True, blank=True)
    tags = models.JSONField(gettext_lazy("Tags"), default=list, null=True, blank=True)
    risk_label = models.CharField(
        gettext_lazy("Risk Label"),
        max_length=32,
        default=RiskLabel.NORMAL,
        null=True,
        blank=True,
        choices=RiskLabel.choices,
    )
    last_operate_time = models.DateTimeField(gettext_lazy("Last Operate Time"), auto_now=True, db_index=True)
    title = models.TextField(gettext_lazy("Risk Title"), null=True, blank=True, default=None)

    class Meta:
        verbose_name = gettext_lazy("Risk")
        verbose_name_plural = verbose_name
        ordering = ["-event_time"]
        index_together = [["strategy", "raw_event_id", "status"], ["strategy", "event_time"]]

    @classmethod
    def load_authed_risks(cls, action: Union[ActionMeta, str]) -> QuerySet:
        """
        获取有权限处理的风险
        """

        queryset = Risk.objects.all()

        q = Q(
            risk_id__in=TicketPermission.objects.filter(
                operator=get_request_username(), action=ActionEnum.LIST_RISK.id
            ).values("risk_id")
        )

        permission = Permission(get_request_username())
        request = permission.make_request(action=get_action_by_id(action), resources=[])
        policies = permission.iam_client._do_policy_query(request)
        if not policies:
            return queryset.filter(q)

        from services.web.risk.provider import RiskResourceProvider

        q |= DjangoQuerySetConverter(key_mapping=RiskResourceProvider.key_mapping).convert(policies)
        return queryset.filter(q)

    @cached_property
    def last_history(self) -> Union["TicketNode", None]:
        from services.web.risk.handlers.ticket import MisReport, ReOpenMisReport

        nodes = TicketNode.objects.filter(risk_id=self.risk_id).order_by("-timestamp")
        for node in nodes:
            if node.action not in [MisReport.__name__, ReOpenMisReport.__name__]:
                return node
        return TicketNode()

    def auth_operators(self, action: str, operators: List[str]) -> None:
        """
        授权处理人查看权限
        """

        TicketPermission.objects.bulk_create(
            objs=[TicketPermission(risk_id=self.risk_id, action=action, operator=operator) for operator in operators],
            ignore_conflicts=True,
        )


class RiskAuditInstance(AuditInstance):
    """
    Risk Audit Instance
    """

    @property
    def instance_id(self):
        """
        实例ID
        @rtype: str
        """
        return getattr(self.instance, "risk_id", DEFAULT_EMPTY_VALUE)

    @property
    def instance_name(self):
        """
        实例名
        @rtype: str
        """
        return getattr(self.instance, "risk_id", DEFAULT_EMPTY_VALUE)

    @property
    def instance_data(self):
        """
        实例信息 JSON
        @rtype: dict
        """
        from services.web.risk.serializers import RiskInfoSerializer

        return RiskInfoSerializer(self.instance).data


def get_next_pa_id() -> int:
    pa = ProcessApplication.objects.all().order_by("-auto_id").first()
    if pa:
        return (pa.auto_id or 0) + 1
    return 1


class ProcessApplication(SoftDeleteModel):
    """
    处理套餐
    """

    id = models.BigAutoField(gettext_lazy("ID"), primary_key=True)
    uniq_id = UUIDField(gettext_lazy("UUID"), unique=True)
    name = models.CharField(gettext_lazy("Name"), max_length=64, db_index=True)
    sops_template_id = models.BigIntegerField(gettext_lazy("SOps Template ID"))
    need_approve = models.BooleanField(gettext_lazy("Need Approve"), default=True)
    approve_service_id = models.BigIntegerField(gettext_lazy("Approve Service ID"), null=True, blank=True)
    approve_config = models.JSONField(gettext_lazy("Approve Config"), null=True, blank=True)
    description = models.TextField(gettext_lazy("Description"), null=True, blank=True)
    is_enabled = models.BooleanField(gettext_lazy("Is Enabled"), default=True)

    class Meta:
        verbose_name = gettext_lazy("Process Application")
        verbose_name_plural = verbose_name
        ordering = ["-updated_at"]


class RiskRule(SoftDeleteModel):
    """
    风险处理规则
    """

    id = models.BigAutoField(gettext_lazy("ID"), primary_key=True)
    uniq_id = UUIDField(gettext_lazy("UUID"), unique=True)
    rule_id = models.BigIntegerField(gettext_lazy("Rule ID"), db_index=True, null=True, blank=True)
    version = models.IntegerField(gettext_lazy("版本号"), null=True, blank=True)
    name = models.CharField(gettext_lazy("Risk Rule Name"), max_length=64, db_index=True)
    scope = models.JSONField(gettext_lazy("Rule Scope"))
    pa_id = models.BigIntegerField(gettext_lazy("Process Application ID"), db_index=True, null=True, blank=True)
    pa_params = models.JSONField(gettext_lazy("Process Application Params"), null=True, blank=True)
    auto_close_risk = models.BooleanField(gettext_lazy("Auto Close Risk"), default=True)
    priority_index = models.IntegerField(gettext_lazy("Priority Index"), default=0)
    is_enabled = models.BooleanField(gettext_lazy("Is Enabled"), default=True)

    class Meta:
        verbose_name = gettext_lazy("Risk Rule")
        verbose_name_plural = verbose_name
        ordering = ["-updated_at"]
        unique_together = [["rule_id", "version"]]
        index_together = [["priority_index", "rule_id", "version"]]

    @classmethod
    def get_rule_or_404(cls, **kwargs) -> "RiskRule":
        rule = cls.objects.filter(**kwargs).order_by("-version").first()
        if rule:
            return rule
        raise cls.DoesNotExist()

    @classmethod
    def load_latest_rules(cls) -> QuerySet:
        max_versions = cls.objects.all().order_by().values("rule_id").annotate(max_version=Max("version"))
        q = Q()
        for v in max_versions:
            q |= Q(rule_id=v["rule_id"], version=v["max_version"])
        return cls.objects.filter(q)


class RiskRuleAuditInstance(AuditInstance):
    """
    Risk Rule Audit Instance
    """

    @property
    def instance_id(self):
        """
        实例ID
        @rtype: str
        """
        return getattr(self.instance, "rule_id", DEFAULT_EMPTY_VALUE)

    @property
    def instance_name(self):
        """
        实例名
        @rtype: str
        """
        return getattr(self.instance, "name", DEFAULT_EMPTY_VALUE)

    @property
    def instance_data(self):
        """
        实例信息 JSON
        @rtype: dict
        """
        from services.web.risk.serializers import RiskRuleInfoSerializer

        return RiskRuleInfoSerializer(self.instance).data


class RiskExperience(SoftDeleteModel):
    """
    Risk Experience
    """

    risk_id = models.CharField(gettext_lazy("Risk ID"), max_length=255, db_index=True)
    content = models.TextField(gettext_lazy("Risk Experience Content"))

    class Meta:
        verbose_name = gettext_lazy("Risk Experience")
        verbose_name_plural = verbose_name
        ordering = ["-id"]


class TicketNode(models.Model):
    """
    Ticket History
    """

    id = UUIDField(verbose_name=gettext_lazy("ID"), primary_key=True)
    risk_id = models.CharField(gettext_lazy("Risk ID"), max_length=255, db_index=True)
    operator = models.CharField(gettext_lazy("Operator"), max_length=255, db_index=True)
    current_operator = models.JSONField(gettext_lazy("Current Operator"), null=True, blank=True, default=list)
    action = models.CharField(gettext_lazy("Action"), max_length=64, db_index=True)
    timestamp = models.FloatField(gettext_lazy("Timestamp"), db_index=True)
    time = models.CharField(gettext_lazy("Time"), max_length=32)
    process_result = models.JSONField("Process Result", default=dict)
    extra = models.JSONField("Extra", default=dict)
    status = models.CharField(
        gettext_lazy("Status"),
        max_length=32,
        choices=TicketNodeStatus.choices,
        default=TicketNodeStatus.RUNNING,
        db_index=True,
    )

    class Meta:
        verbose_name = gettext_lazy("Ticket History")
        verbose_name_plural = verbose_name
        ordering = ["-timestamp"]


class TicketPermission(models.Model):
    """
    Ticket Permission
    """

    risk_id = models.CharField(gettext_lazy("Risk ID"), max_length=255, db_index=True)
    action = models.CharField(gettext_lazy("Action"), max_length=32, db_index=True)
    operator = models.CharField(gettext_lazy("Operator"), max_length=255, db_index=True)
    authorized_at = models.DateTimeField(gettext_lazy("Authorized Time"), auto_now_add=True)

    class Meta:
        verbose_name = gettext_lazy("Ticket Permission")
        verbose_name_plural = verbose_name
        ordering = ["-id"]
        unique_together = [["risk_id", "action", "operator"]]
