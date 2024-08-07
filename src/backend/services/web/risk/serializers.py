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
import json
from typing import List, Union

from blueapps.utils.request_provider import get_request_username
from django.conf import settings
from django.utils.translation import gettext, gettext_lazy
from rest_framework import serializers

from apps.meta.constants import OrderTypeChoices
from core.utils.distutils import strtobool
from core.utils.tools import mstimestamp_to_date_string
from services.web.risk.constants import EventMappingFields, RiskLabel, RiskRuleOperator
from services.web.risk.models import (
    ProcessApplication,
    Risk,
    RiskExperience,
    RiskRule,
    TicketNode,
)
from services.web.strategy_v2.constants import RiskLevel
from services.web.strategy_v2.serializers import EventFieldSerializer


class CreateEventSerializer(serializers.Serializer):
    """
    生成审计事件
    """

    event_content = serializers.CharField(
        label=EventMappingFields.EVENT_CONTENT.description, default=str, allow_blank=True, allow_null=True
    )
    raw_event_id = serializers.CharField(
        label=EventMappingFields.RAW_EVENT_ID.description, default=str, allow_blank=True, allow_null=True
    )
    strategy_id = serializers.IntegerField(label=EventMappingFields.STRATEGY_ID.description)
    event_data = serializers.JSONField(label=EventMappingFields.EVENT_DATA.description, default=dict, allow_null=True)
    event_time = serializers.IntegerField(label=EventMappingFields.EVENT_TIME.description, default=int)
    event_evidence = serializers.CharField(
        label=EventMappingFields.EVENT_EVIDENCE.description, default=str, allow_null=True, allow_blank=True
    )
    event_type = serializers.CharField(
        label=EventMappingFields.EVENT_TYPE.description, default=str, allow_null=True, allow_blank=True
    )
    event_source = serializers.CharField(
        label=EventMappingFields.EVENT_SOURCE.description, default=str, allow_null=True, allow_blank=True
    )
    operator = serializers.CharField(
        label=EventMappingFields.OPERATOR.description, default=str, allow_null=True, allow_blank=True
    )

    def validate_event_data(self, event_data: dict) -> str:
        error = serializers.ValidationError(gettext("%s 不是有效的 JSON") % EventMappingFields.EVENT_DATA.field_name)
        if isinstance(event_data, str):
            try:
                event_data = json.loads(event_data)
            except Exception:
                raise error
        if not isinstance(event_data, Union[dict, None]):
            raise error
        return json.dumps(event_data, ensure_ascii=False)

    def validate_event_time(self, event_time: int) -> int:
        if event_time:
            return event_time
        return int(datetime.datetime.now().timestamp() * 1000)


class CreateRiskSerializer(CreateEventSerializer):
    """
    生成审计风险
    """

    dtEventTimeStamp = serializers.IntegerField(required=False)

    def validate(self, attrs: dict) -> dict:
        data = super().validate(attrs)
        if data.get("dtEventTimeStamp"):
            # 优先使用 dtEventTimeStamp 生成
            # 避免查询关联事件列表接口
            # 由于 event_time 与 dtEventTimeStamp 不一致
            # 导致关联事件为空或者不准确
            data["event_time"] = data.pop("dtEventTimeStamp")
        return data

    def validate_event_data(self, event_data: dict) -> str:
        return json.loads(super().validate_event_data(event_data))


class CreateEventAPIResponseSerializer(serializers.Serializer):
    """
    Create Event Response
    """

    event_ids = serializers.ListField(
        label=gettext_lazy("Event IDs"), child=serializers.CharField(label=gettext_lazy("Event ID"))
    )


class CreateEventBKMSerializer(CreateEventSerializer):
    """
    生成审计事件(带ID)
    """

    event_id = serializers.CharField(label=EventMappingFields.EVENT_ID.description)


class CreateEventAPISerializer(serializers.Serializer):
    """
    从API生成审计事件
    """

    events = CreateEventSerializer(many=True)


class ListEventRequestSerializer(serializers.Serializer):
    """
    List event
    """

    namespace = serializers.CharField(label=gettext_lazy("Namespace"), default=settings.DEFAULT_NAMESPACE)
    start_time = serializers.CharField(label=gettext_lazy("Start Time"))
    end_time = serializers.CharField(label=gettext_lazy("End Time"))
    page = serializers.IntegerField(label=gettext_lazy("Page"), min_value=1)
    page_size = serializers.IntegerField(label=gettext_lazy("Page Size"), min_value=1)
    risk_id = serializers.CharField(label=gettext_lazy("Risk ID"))

    def to_internal_value(self, data: dict) -> dict:
        new_data = super().to_internal_value(data)
        for key, val in data.items():
            if key not in new_data.keys():
                new_data[key] = val
        return new_data


class ListEventResponseSerializer(serializers.Serializer):
    """
    List Event
    """

    page = serializers.IntegerField(label=gettext_lazy("Page"))
    num_pages = serializers.IntegerField(label=gettext_lazy("Total Pages"))
    total = serializers.IntegerField(label=gettext_lazy("Total"))
    results = serializers.ListField(label=gettext_lazy("Events"), child=serializers.JSONField())

    def validate_results(self, results: List[dict]) -> List[dict]:
        for e in results:
            try:
                e["event_time"] = mstimestamp_to_date_string(int(e["event_time"]))
            except (KeyError, TypeError, ValueError):
                e["event_time"] = ""
        return results


class RiskInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Risk
        fields = "__all__"


class ListRiskRequestSerializer(serializers.Serializer):
    """
    List Risk
    """

    risk_id = serializers.CharField(label=gettext_lazy("Risk ID"), required=False)
    strategy_id = serializers.CharField(label=gettext_lazy("Strategy ID"), required=False)
    operator = serializers.CharField(label=gettext_lazy("Operator"), required=False)
    status = serializers.CharField(label=gettext_lazy("Risk Status"), required=False)
    start_time = serializers.DateTimeField(label=gettext_lazy("Start Time"), required=False)
    end_time = serializers.DateTimeField(label=gettext_lazy("End Time"), required=False)
    event_type = serializers.CharField(label=gettext_lazy("Risk Type"), required=False)
    current_operator = serializers.CharField(label=gettext_lazy("Current Operator"), required=False)
    tags = serializers.CharField(label=gettext_lazy("Tags"), required=False)
    event_content = serializers.CharField(label=gettext_lazy("Event Content"), required=False)
    risk_label = serializers.CharField(label=gettext_lazy("Risk Label"), required=False)
    order_field = serializers.CharField(label=gettext_lazy("排序字段"), required=False, allow_null=True, allow_blank=True)
    order_type = serializers.ChoiceField(
        label=gettext_lazy("排序方式"), required=False, allow_null=True, allow_blank=True, choices=OrderTypeChoices.choices
    )

    def validate(self, attrs: dict) -> dict:
        # 校验
        data = super().validate(attrs)
        # 排序
        if data.get("order_field") and data.get("order_type"):
            data["order_field"] = (
                f"-{data['order_field']}"
                if data.pop("order_type") == OrderTypeChoices.DESC
                else data.pop("order_field")
            )
        # 时间转换
        if data.get("start_time"):
            data["event_time__gte"] = [data.pop("start_time")]
        if data.get("end_time"):
            data["event_time__lt"] = [data.pop("end_time")]
        # 字段转换
        if data.get("operator"):
            data["operator__contains"] = data.pop("operator")
        if data.get("event_type"):
            data["event_type__contains"] = data.pop("event_type")
        if data.get("current_operator"):
            data["current_operator__contains"] = data.pop("current_operator")
        if data.get("tags"):
            data["tags__contains"] = data.pop("tags")
        if data.get("event_content"):
            data["event_content__contains"] = data.pop("event_content")
        # 格式转换
        for key, val in attrs.items():
            if key in ["event_time__gte", "event_time__lt", "order_type", "order_field"]:
                continue
            if key in ["tags__contains"]:
                data[key] = [int(i) for i in val.split(",") if i]
                continue
            data[key] = [i for i in val.split(",") if i]
        return data


class ListRiskResponseSerializer(serializers.ModelSerializer):
    """
    List Risk
    """

    experiences = serializers.IntegerField(required=False)

    class Meta:
        model = Risk
        fields = [
            "risk_id",
            "event_content",
            "strategy_id",
            "event_time",
            "event_end_time",
            "operator",
            "status",
            "current_operator",
            "notice_users",
            "tags",
            "risk_label",
            "experiences",
            "last_operate_time",
        ]


class ProcessApplicationsInfoSerializer(serializers.ModelSerializer):
    rule_count = serializers.IntegerField(default=0, required=False)

    class Meta:
        model = ProcessApplication
        fields = "__all__"


class ApproveConfigSerializer(serializers.Serializer):
    def validate(self, attrs: dict) -> dict:
        data = super().validate(attrs)
        if attrs.get("need_approve") and not attrs.get("approve_service_id"):
            raise serializers.ValidationError(gettext("未配置审批流"))
        return data


class CreateProcessApplicationsReqSerializer(ApproveConfigSerializer, serializers.ModelSerializer):
    class Meta:
        model = ProcessApplication
        fields = [
            "name",
            "sops_template_id",
            "need_approve",
            "approve_service_id",
            "approve_config",
            "description",
        ]

    def validate_name(self, name: str) -> str:
        if ProcessApplication.objects.filter(name=name).exists():
            raise serializers.ValidationError(gettext("处理套餐名称重复"))
        return name


class UpdateProcessApplicationsReqSerializer(ApproveConfigSerializer, serializers.ModelSerializer):
    id = serializers.CharField()

    class Meta:
        model = ProcessApplication
        fields = [
            "id",
            "name",
            "sops_template_id",
            "need_approve",
            "approve_service_id",
            "approve_config",
            "description",
        ]

    def validate(self, attrs: dict) -> dict:
        data = super().validate(attrs)
        if ProcessApplication.objects.filter(name=data["name"]).exclude(id=data["id"]).exists():
            raise serializers.ValidationError(gettext("处理套餐名称重复"))
        return data


class RiskRuleInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskRule
        fields = "__all__"


class RuleScopeValidator(serializers.Serializer):
    def validate_scope(self, scope: List[dict]) -> List[dict]:
        q = RiskRuleOperator.build_query_filter(scope)
        try:
            Risk.objects.filter(q)
        except ValueError:
            raise serializers.ValidationError(gettext("适用范围匹配值异常"))
        return scope


class CreateRiskRuleReqSerializer(RuleScopeValidator, serializers.ModelSerializer):
    class Meta:
        model = RiskRule
        fields = ["name", "scope", "pa_id", "pa_params", "auto_close_risk"]

    def validate_name(self, name: str) -> str:
        if RiskRule.objects.filter(name=name).exists():
            raise serializers.ValidationError(gettext("规则名称重复"))
        return name


class UpdateRiskRuleReqSerializer(RuleScopeValidator, serializers.ModelSerializer):
    class Meta:
        model = RiskRule
        fields = ["rule_id", "name", "scope", "pa_id", "pa_params", "auto_close_risk"]

    def validate(self, attrs: dict) -> dict:
        data = super().validate(attrs)
        if RiskRule.objects.filter(name=data["name"]).exclude(rule_id=data["rule_id"]).exists():
            raise serializers.ValidationError(gettext("规则名称重复"))
        return data


class ToggleRiskRuleRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskRule
        fields = ["rule_id", "is_enabled"]


class BatchUpdateRiskRulePriorityIndexItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskRule
        fields = ["rule_id", "priority_index", "is_enabled"]


class BatchUpdateRiskRulePriorityIndexReqSerializer(serializers.Serializer):
    config = BatchUpdateRiskRulePriorityIndexItemSerializer(many=True)


class UpdateRiskLabelReqSerializer(serializers.ModelSerializer):
    risk_id = serializers.CharField()
    risk_label = serializers.ChoiceField(choices=RiskLabel.choices)
    new_operators = serializers.ListField(child=serializers.CharField(), required=False)
    description = serializers.CharField(required=False)
    revoke_process = serializers.BooleanField(default=True)

    class Meta:
        model = Risk
        fields = ["risk_id", "risk_label", "new_operators", "description", "revoke_process"]

    def validate(self, attrs):
        data = super().validate(attrs)
        if data["risk_label"] == RiskLabel.MISREPORT and not attrs.get("description"):
            raise serializers.ValidationError(gettext("Misreport Description Not Set"))
        return data


class ListRiskRuleReqSerializer(serializers.Serializer):
    rule_id = serializers.CharField(label=gettext_lazy("Rule ID"), required=False)
    name = serializers.CharField(label=gettext_lazy("Rule Name"), required=False)
    updated_by = serializers.CharField(label=gettext_lazy("Update User"), required=False)
    is_enabled = serializers.CharField(label=gettext_lazy("Is Enabled"), required=False)
    order_field = serializers.CharField(label=gettext_lazy("排序字段"), required=False, allow_null=True, allow_blank=True)
    order_type = serializers.ChoiceField(
        label=gettext_lazy("排序方式"), required=False, allow_null=True, allow_blank=True, choices=OrderTypeChoices.choices
    )

    def to_internal_value(self, data):
        data = super().to_internal_value(data)
        result = {}
        for key, val in data.items():
            # 特殊字段直接透传
            if key in ["order_field", "order_type"]:
                continue
            # is_enabled 字段需要拆分为数组，并且转为 bool 值
            if key == "is_enabled":
                result[key] = [strtobool(i) for i in val.split(",") if i]
                continue
            # 自增ID需要转换为数字
            if key == "rule_id":
                result[key] = [int(i) for i in val.split(",") if i]
                continue
            # 名字需要模糊匹配
            if key == "name":
                result[f"{key}__contains"] = [i for i in val.split(",") if i]
                continue
            # 其他字段需要拆分为数组
            result[key] = [i for i in val.split(",") if i]
        # 处理排序
        if data.get("order_field"):
            result["order_field"] = "{}{}".format(
                "-" if data.get("order_type") == OrderTypeChoices.DESC else "", data["order_field"]
            )
        return result


class CustomCloseRiskRequestSerializer(serializers.Serializer):
    risk_id = serializers.CharField(label=gettext_lazy("Risk ID"))
    description = serializers.CharField(label=gettext_lazy("处理说明"))


class CustomTransRiskReqSerializer(serializers.Serializer):
    risk_id = serializers.CharField(label=gettext_lazy("Risk ID"))
    new_operators = serializers.ListField(label=gettext_lazy("新处理人"), child=serializers.CharField(), min_length=1)
    description = serializers.CharField(label=gettext_lazy("处理说明"))

    def validate_new_operators(self, new_operators: List[str]) -> List[str]:
        if len(new_operators) == 1 and new_operators[0] == get_request_username():
            raise serializers.ValidationError(gettext("不能转单给自己"))
        return new_operators


class RiskExperienceInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskExperience
        fields = "__all__"


class SaveRiskExperienceReqSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskExperience
        fields = ["risk_id", "content"]


class ListRiskExperienceReqSerializer(serializers.Serializer):
    risk_id = serializers.CharField()


class ReopenRiskReqSerializer(serializers.Serializer):
    risk_id = serializers.CharField()
    new_operators = serializers.ListField(label=gettext_lazy("新处理人"), child=serializers.CharField(), min_length=1)


class CustomAutoProcessReqSerializer(serializers.Serializer):
    risk_id = serializers.CharField()
    pa_id = serializers.IntegerField()
    pa_params = serializers.JSONField()
    auto_close_risk = serializers.BooleanField()


class ToggleProcessApplicationReqSerializer(serializers.Serializer):
    id = serializers.CharField()
    is_enabled = serializers.BooleanField()


class ListProcessApplicationsReqSerializer(serializers.Serializer):
    id = serializers.CharField(required=False)
    name = serializers.CharField(required=False)
    updated_by = serializers.CharField(required=False)
    is_enabled = serializers.CharField(required=False)
    order_field = serializers.CharField(label=gettext_lazy("排序字段"), required=False, allow_null=True, allow_blank=True)
    order_type = serializers.ChoiceField(
        label=gettext_lazy("排序方式"), required=False, allow_null=True, allow_blank=True, choices=OrderTypeChoices.choices
    )

    def validate(self, attrs: dict) -> dict:
        data = {}
        attrs = super().validate(attrs)
        # 处理排序
        if attrs.get("order_field"):
            data["order_field"] = "{}{}".format(
                "-" if attrs.pop("order_type", OrderTypeChoices.ASC) == OrderTypeChoices.DESC else "",
                attrs.pop("order_field"),
            )
        # 处理字段
        for key, val in attrs.items():
            if key == "is_enabled":
                data[key] = [strtobool(val) for val in val.split(",") if val]
                continue
            if key == "name":
                data[f"{key}__contains"] = [val for val in val.split(",") if val]
                continue
            if key == "id":
                data[key] = [int(val) for val in val.split(",") if val]
                continue
            data[key] = [val for val in val.split(",") if val]
        return data


class TicketNodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketNode
        exclude = ["extra"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.update(instance.extra)
        return data


class ForceRevokeAutoProcessReqSerializer(serializers.Serializer):
    node_id = serializers.CharField()
    risk_id = serializers.CharField()


class ForceRevokeApproveTicketReqSerializer(serializers.Serializer):
    node_id = serializers.CharField()
    risk_id = serializers.CharField()


class RetryAutoProcessReqSerializer(serializers.Serializer):
    node_id = serializers.CharField()
    risk_id = serializers.CharField()


class GetRiskFieldsByStrategyRequestSerializer(serializers.Serializer):
    strategy_id = serializers.IntegerField()


class GetRiskFieldsByStrategyResponseSerializer(serializers.Serializer):
    key = serializers.CharField()
    name = serializers.CharField()
    unique = serializers.BooleanField(default=False)


class RetrieveRiskStrategyInfoResponseSerializer(serializers.Serializer):
    risk_level = serializers.ChoiceField(
        label=gettext_lazy("Risk Level"), choices=RiskLevel.choices, required=False, allow_null=True
    )
    risk_hazard = serializers.CharField(label=gettext_lazy("Risk Hazard"), required=False, allow_null=True)
    risk_guidance = serializers.CharField(label=gettext_lazy("Risk Guidance"), required=False, allow_null=True)

    event_basic_field_configs = serializers.ListField(
        label=gettext_lazy("Event Basic Field Configs"), child=EventFieldSerializer(), default=list, allow_empty=True
    )
    event_data_field_configs = serializers.ListField(
        label=gettext_lazy("Event Data Field Configs"), child=EventFieldSerializer(), default=list, allow_empty=True
    )
    event_evidence_field_configs = serializers.ListField(
        label=gettext_lazy("Event Evidence Field Configs"), child=EventFieldSerializer(), default=list, allow_empty=True
    )
