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
import uuid
from typing import List

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext, gettext_lazy
from rest_framework import serializers

from apps.meta.constants import OrderTypeChoices
from apps.meta.models import Tag
from core.serializers import AnyValueField, TimestampIntegerField
from core.utils.distutils import strtobool
from core.utils.time import mstimestamp_to_date_string
from services.web.risk.constants import (
    RAW_EVENT_ID_REMARK,
    RISK_LEVEL_ORDER_FIELD,
    EventFilterOperator,
    EventMappingFields,
    RiskLabel,
    RiskRuleOperator,
    RiskStatus,
    RiskViewType,
)
from services.web.risk.models import (
    ManualEvent,
    ProcessApplication,
    Risk,
    RiskExperience,
    RiskReport,
    RiskRule,
    TicketNode,
    TicketPermission,
)
from services.web.strategy_v2.models import Strategy
from services.web.strategy_v2.serializers import (
    EventFieldSerializer,
    merge_select_field_type,
)


class CreateEventSerializer(serializers.Serializer):
    """
    生成审计事件
    """

    event_content = serializers.CharField(
        label=EventMappingFields.EVENT_CONTENT.description, default=str, allow_blank=True, allow_null=True
    )
    raw_event_id = serializers.CharField(
        label=EventMappingFields.RAW_EVENT_ID.description, default=lambda: uuid.uuid1().hex
    )
    strategy_id = serializers.IntegerField(label=EventMappingFields.STRATEGY_ID.description)
    event_data = serializers.JSONField(label=EventMappingFields.EVENT_DATA.description, default=dict, allow_null=True)
    event_time = serializers.IntegerField(label=EventMappingFields.EVENT_TIME.description, default=int, allow_null=True)
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
        if not isinstance(event_data, dict):
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
    risk_ids = serializers.ListField(
        label=gettext_lazy("Event IDs"),
        child=serializers.CharField(label=gettext_lazy("Event ID")),
        required=False,
        allow_empty=True,
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
    gen_risk = serializers.BooleanField(label=gettext_lazy("Generate Risk"), default=False)
    risk_id = serializers.CharField(label=gettext_lazy("Risk ID"), required=False, allow_blank=True)


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
            if key not in new_data.keys() and key not in ["_request"]:
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
    event_end_time = serializers.SerializerMethodField()

    def get_event_end_time(self, obj: Risk) -> str | None:
        """
        获取事件结束时间。
        如果存在毫秒/微秒，则向上取整到下一秒。
        """
        dt = obj.event_end_time

        if dt is None:
            return None

        # 核心逻辑：检查是否存在微秒
        if dt.microsecond > 0:
            # 1. 先去掉微秒 (归零)
            # 2. 再加上1秒，实现“向上取整”
            dt = dt.replace(microsecond=0) + datetime.timedelta(seconds=1)

        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())

        dt = timezone.localtime(dt)

        # 因为 SerializerMethodField 不会自动使用 settings.py 中的格式，
        # 所以我们需要在这里手动格式化为您的全局格式
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def validate_results(self, results: List[dict]) -> List[dict]:
        for e in results:
            if e.get("dtEventTimeStamp"):
                # 优先使用 dtEventTimeStamp 生成
                # 避免查询关联事件列表接口
                # 由于 event_time 与 dtEventTimeStamp 不一致
                # 导致关联事件为空或者不准确
                e["event_time"] = e["dtEventTimeStamp"]
            try:
                e["event_time"] = mstimestamp_to_date_string(int(e["event_time"]))
            except (KeyError, TypeError, ValueError):
                e["event_time"] = ""
        return results


class RiskReportSerializer(serializers.ModelSerializer):
    """
    风险报告序列化器
    """

    class Meta:
        model = RiskReport
        fields = "__all__"


class RiskInfoSerializer(serializers.ModelSerializer):
    strategy_id = serializers.IntegerField(label=gettext_lazy("Strategy ID"))
    tags = serializers.SerializerMethodField()
    event_end_time = serializers.SerializerMethodField()
    has_report = serializers.SerializerMethodField()
    report_enabled = serializers.BooleanField(source="strategy.report_enabled", default=False, read_only=True)
    report = RiskReportSerializer(read_only=True)

    def get_has_report(self, obj: Risk) -> bool:
        """检查风险是否有报告"""
        return hasattr(obj, "report")

    def to_representation(self, instance: Risk):
        data = super().to_representation(instance)
        if getattr(instance, "manual_synced", True) is False:
            data["status"] = RiskStatus.STAND_BY.value
        return data

    def get_event_end_time(self, obj: Risk) -> str | None:
        """
        获取事件结束时间。
        如果存在毫秒/微秒，则向上取整到下一秒。
        """
        dt = obj.event_end_time

        if dt is None:
            return None

        # 核心逻辑：检查是否存在微秒
        if dt.microsecond > 0:
            # 1. 先去掉微秒 (归零)
            # 2. 再加上1秒，实现“向上取整”
            dt = dt.replace(microsecond=0) + datetime.timedelta(seconds=1)

        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())

        dt = timezone.localtime(dt)

        # 因为 SerializerMethodField 不会自动使用 settings.py 中的格式，
        # 所以我们需要在这里手动格式化为您的全局格式
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def get_tags(self, obj: Risk):
        """
        获取风险标签ID列表,从策略获取
        """

        return obj.get_tag_ids()

    class Meta:
        model = Risk
        exclude = ["strategy"]


class RiskProviderSerializer(serializers.ModelSerializer):
    strategy_id = serializers.IntegerField(label=gettext_lazy("Strategy ID"))
    event_time_timestamp = TimestampIntegerField(label=gettext_lazy("Event Time Timestamp(ms)"), source="event_time")
    event_end_time_timestamp = TimestampIntegerField(
        label=gettext_lazy("Event End Time Timestamp(ms)"), source="event_end_time"
    )
    last_operate_time_timestamp = TimestampIntegerField(
        label=gettext_lazy("Last Operate Time Timestamp(ms)"), source="last_operate_time"
    )

    class Meta:
        model = Risk
        exclude = ["strategy"]


class ManualEventProviderSerializer(serializers.ModelSerializer):
    strategy_id = serializers.IntegerField(label=gettext_lazy("Strategy ID"))
    event_time_timestamp = TimestampIntegerField(label=gettext_lazy("Event Time Timestamp(ms)"), source="event_time")
    last_operate_time_timestamp = TimestampIntegerField(
        label=gettext_lazy("Last Operate Time Timestamp(ms)"), source="last_operate_time"
    )

    class Meta:
        model = ManualEvent
        exclude = ["strategy"]


class ManualEventSerializer(serializers.ModelSerializer):
    strategy_id = serializers.IntegerField(label=gettext_lazy("Strategy ID"))
    event_time_timestamp = TimestampIntegerField(label=gettext_lazy("Event Time Timestamp(ms)"), source="event_time")

    class Meta:
        model = ManualEvent
        exclude = ["strategy"]


class ListEventFieldsByStrategyRequestSerializer(serializers.Serializer):
    # 支持多个策略；不传或为空返回所有策略的字段
    strategy_ids = serializers.ListField(child=serializers.IntegerField(), required=False, allow_empty=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs.get("strategy_ids") and isinstance(attrs["strategy_ids"], str):
            attrs["strategy_ids"] = [int(i) for i in attrs["strategy_ids"].split(",") if i]
        return attrs


class ListEventFieldsByStrategyResponseSerializer(serializers.Serializer):
    field_name = serializers.CharField(label=gettext_lazy("字段名"))
    display_name = serializers.CharField(label=gettext_lazy("字段显示名"))
    id = serializers.CharField(label=gettext_lazy("字段ID"))


class RiskEventSubscriptionQuerySerializer(serializers.Serializer):
    token = serializers.CharField(label=gettext_lazy("订阅 Token"))
    start_time = serializers.IntegerField(label=gettext_lazy("开始时间(ms)"), help_text=gettext_lazy("Unix 毫秒时间戳"))
    end_time = serializers.IntegerField(label=gettext_lazy("结束时间(ms)"), help_text=gettext_lazy("Unix 毫秒时间戳"))
    page = serializers.IntegerField(label=gettext_lazy("页码"), min_value=1, default=1)
    page_size = serializers.IntegerField(label=gettext_lazy("单页数量"), min_value=1, max_value=1000, default=1000)
    raw = serializers.BooleanField(label=gettext_lazy("仅返回 SQL"), required=False, default=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs["start_time"] > attrs["end_time"]:
            raise serializers.ValidationError({"params_error": gettext_lazy("开始时间需小于等于结束时间")})
        return attrs


class RiskEventSubscriptionQueryResponseSerializer(serializers.Serializer):
    page = serializers.IntegerField(label=gettext_lazy("页码"))
    page_size = serializers.IntegerField(label=gettext_lazy("单页数量"))
    total = serializers.IntegerField(label=gettext_lazy("总数"))
    results = serializers.ListField(
        label=gettext_lazy("数据"),
        child=serializers.JSONField(label=gettext_lazy("订阅结果行")),
        help_text=gettext_lazy("透传 BKBase 查询结果，字段结构由订阅配置决定"),
        allow_empty=True,
    )
    query_sql = serializers.CharField(label="query_sql")
    count_sql = serializers.CharField(label="count_sql")


class EventFieldFilterItemSerializer(serializers.Serializer):
    field = serializers.CharField(label=gettext_lazy("字段名"))
    display_name = serializers.CharField(label=gettext_lazy("字段显示名"))
    operator = serializers.ChoiceField(label=gettext_lazy("操作符"), choices=EventFilterOperator.choices)
    value = AnyValueField(label=gettext_lazy("值"))


class TicketPermissionProviderSerializer(serializers.ModelSerializer):
    """用于反向拉取 TicketPermission 的快照结构"""

    # 显式声明，便于在 Schema 中展示
    authorized_at = serializers.DateTimeField(label=gettext_lazy("Authorized Time"))
    authorized_at_timestamp = TimestampIntegerField(
        label=gettext_lazy("Authorized Time Timestamp(ms)"), source="authorized_at"
    )

    class Meta:
        model = TicketPermission
        fields = "__all__"


class ListRiskRequestSerializer(serializers.Serializer):
    """
    List Risk
    """

    risk_id = serializers.CharField(label=gettext_lazy("Risk ID"), allow_blank=True, required=False)
    strategy_id = serializers.CharField(label=gettext_lazy("Strategy ID"), allow_blank=True, required=False)
    operator = serializers.CharField(label=gettext_lazy("Operator"), allow_blank=True, required=False)
    status = serializers.CharField(label=gettext_lazy("Risk Status"), allow_blank=True, required=False)
    start_time = serializers.DateTimeField(label=gettext_lazy("Start Time"), required=False)
    end_time = serializers.DateTimeField(label=gettext_lazy("End Time"), required=False)
    event_type = serializers.CharField(label=gettext_lazy("Risk Type"), allow_blank=True, required=False)
    current_operator = serializers.CharField(label=gettext_lazy("Current Operator"), allow_blank=True, required=False)
    notice_users = serializers.CharField(label=gettext_lazy("Notice Users"), allow_blank=True, required=False)
    tags = serializers.CharField(label=gettext_lazy("Tags"), allow_blank=True, required=False)
    event_content = serializers.CharField(label=gettext_lazy("Event Content"), allow_blank=True, required=False)
    risk_label = serializers.CharField(label=gettext_lazy("Risk Label"), allow_blank=True, required=False)
    use_bkbase = serializers.BooleanField(label=gettext_lazy("是否通过BKBase查询"), required=False, default=False)
    order_field = serializers.CharField(
        label=gettext_lazy("排序字段"),
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="risk_level:根据风险等级排序",
    )
    order_type = serializers.ChoiceField(
        label=gettext_lazy("排序方式"),
        required=False,
        allow_null=True,
        allow_blank=True,
        choices=OrderTypeChoices.choices,
    )
    risk_level = serializers.CharField(
        label=gettext_lazy("Risk Level"), required=False, allow_blank=True, allow_null=True
    )
    title = serializers.CharField(label=gettext_lazy("Risk Title"), allow_blank=True, required=False)
    event_filters = EventFieldFilterItemSerializer(label=gettext_lazy("关联事件字段筛选"), many=True, required=False)

    def validate(self, attrs: dict) -> dict:
        # 校验
        data = super().validate(attrs)
        event_filters = data.get("event_filters") or []
        raw_order_field = data.get("order_field") or attrs.get("order_field")
        normalized_order_field = (raw_order_field or "").lstrip("-")
        if normalized_order_field.startswith("event_data."):
            if not event_filters:
                raise serializers.ValidationError(gettext("关联事件字段排序需同时指定事件筛选条件"))
            event_field_name = normalized_order_field[len("event_data.") :].strip()
            filter_fields = {(item.get("field") or "").strip() for item in event_filters if isinstance(item, dict)}
            filter_fields_with_prefix = {f"event_data.{field}" for field in filter_fields if field}
            if (
                event_field_name
                and event_field_name not in filter_fields
                and normalized_order_field not in filter_fields_with_prefix
            ):
                raise serializers.ValidationError(gettext("关联事件字段排序需在筛选条件中包含字段：%s") % event_field_name)
        # 排序
        # 兼容：前端传入 risk_level 作为排序字段时，转换为 strategy__risk_level
        if data.get("order_field") == Strategy.risk_level.field.name:
            data["order_field"] = RISK_LEVEL_ORDER_FIELD
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
        if data.get("notice_users"):
            data["notice_users__contains"] = data.pop("notice_users")
        if data.get("tags"):
            data["tag_objs__in"] = data.pop("tags")
        if data.get("event_content"):
            data["event_content__contains"] = data.pop("event_content")
        if data.get("title"):
            data["title__contains"] = data.pop("title")
        event_filters = event_filters or []
        data["event_filters"] = event_filters
        data["use_bkbase"] = bool(data.get("use_bkbase", False))
        # 格式转换
        for key, val in attrs.items():
            if key in ["event_time__gte", "event_time__lt", "order_type", "order_field", "use_bkbase", "event_filters"]:
                continue
            if key in ["tag_objs__in"]:
                data[key] = [int(i) for i in val.split(",") if i]
                continue
            data[key] = [i for i in val.split(",") if i]
        return data


class ListRiskMetaRequestSerializer(serializers.Serializer):
    risk_view_type = serializers.ChoiceField(
        label=gettext_lazy("Risk View Type"), required=False, choices=RiskViewType.choices
    )
    start_time = serializers.DateTimeField(label=gettext_lazy("Start Time"), required=False)
    end_time = serializers.DateTimeField(label=gettext_lazy("End Time"), required=False)

    def validate(self, attrs):
        # 校验
        data = super().validate(attrs)
        # 时间转换
        if data.get("start_time"):
            data["event_time__gte"] = [data.pop("start_time")]
        if data.get("end_time"):
            data["event_time__lt"] = [data.pop("end_time")]
        return data


class ListRiskTagsRespSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(label=gettext_lazy("Tag ID"), source="tag_id")
    name = serializers.CharField(label=gettext_lazy("Tag Name"), source="tag_name")

    class Meta:
        model = Tag
        fields = ["id", "name"]


class ListRiskStrategyRespSerializer(serializers.ModelSerializer):
    label = serializers.CharField(label=gettext_lazy("Label"), source="strategy_name")
    value = serializers.IntegerField(label=gettext_lazy("Value"), source="strategy_id")

    class Meta:
        model = Strategy
        fields = ["label", "value"]


class ListRiskResponseSerializer(serializers.ModelSerializer):
    """
    List Risk
    """

    experiences = serializers.IntegerField(required=False)
    event_data = serializers.SerializerMethodField()
    event_content = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    event_end_time = serializers.SerializerMethodField()
    has_report = serializers.SerializerMethodField()
    report_enabled = serializers.BooleanField(source="strategy.report_enabled", default=False, read_only=True)

    def get_has_report(self, obj: Risk):
        """
        检查风险是否有报告
        使用 annotated 属性避免 N+1 查询
        """
        return getattr(obj, "_has_report", False)

    def get_event_data(self, obj: Risk):
        """
        返回风险列表中用于展示的事件数据。
        """
        return getattr(obj, "filtered_event_data", {})

    def get_event_content(self, obj):
        return getattr(obj, "event_content_short")

    def get_tags(self, obj: Risk):
        """
        获取风险标签ID列表
        支持从策略获取或快照获取，并优化查询性能
        """
        if hasattr(obj.strategy, 'prefetched_tags'):
            # 使用预加载的数据，避免N+1查询
            return [tag_rel.tag.tag_id for tag_rel in obj.strategy.prefetched_tags]
        else:
            # 回退到实时查询
            return obj.get_tag_ids()

    def get_event_end_time(self, obj: Risk) -> str | None:
        """
        获取事件结束时间。
        如果存在毫秒/微秒，则向上取整到下一秒。
        """
        dt = obj.event_end_time

        if dt is None:
            return None

        # 核心逻辑：检查是否存在微秒
        if dt.microsecond > 0:
            # 1. 先去掉微秒 (归零)
            # 2. 再加上1秒，实现“向上取整”
            dt = dt.replace(microsecond=0) + datetime.timedelta(seconds=1)

        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())

        dt = timezone.localtime(dt)

        # 因为 SerializerMethodField 不会自动使用 settings.py 中的格式，
        # 所以我们需要在这里手动格式化为您的全局格式
        return dt.strftime("%Y-%m-%d %H:%M:%S")

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
            "event_data",
            "tags",
            "risk_label",
            "experiences",
            "last_operate_time",
            "title",
            "has_report",
            "report_enabled",
        ]

    def to_representation(self, instance: Risk):
        data = super().to_representation(instance)
        if getattr(instance, "manual_synced", True) is False:
            data["status"] = RiskStatus.STAND_BY.value
        return data


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
        label=gettext_lazy("排序方式"),
        required=False,
        allow_null=True,
        allow_blank=True,
        choices=OrderTypeChoices.choices,
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


class CustomTransBaseReqSerializer(serializers.Serializer):
    new_operators = serializers.ListField(label=gettext_lazy("新处理人"), child=serializers.CharField(), min_length=1)
    description = serializers.CharField(label=gettext_lazy("处理说明"))


class CustomTransRiskReqSerializer(CustomTransBaseReqSerializer):
    risk_id = serializers.CharField(label=gettext_lazy("Risk ID"))


class BulkCustomTransRiskReqSerializer(CustomTransBaseReqSerializer):
    risk_ids = serializers.ListField(label=gettext_lazy("Risk IDs"), child=serializers.CharField(), min_length=1)

    def validate_risk_ids(self, risk_ids: List[str]) -> List[str]:
        return sorted(list(set(risk_ids)))


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
        label=gettext_lazy("排序方式"),
        required=False,
        allow_null=True,
        allow_blank=True,
        choices=OrderTypeChoices.choices,
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


class RetrieveRiskStrategyInfoAPIGWRequestSerializer(serializers.Serializer):
    risk_id = serializers.CharField()
    prohibit_enum_mappings = serializers.BooleanField(required=False, default=True)


class RetrieveRiskStrategyInfoResponseSerializer(serializers.ModelSerializer):
    event_basic_field_configs = serializers.ListField(
        label=gettext_lazy("Event Basic Field Configs"), child=EventFieldSerializer(), required=False, allow_empty=True
    )
    event_data_field_configs = serializers.ListField(
        label=gettext_lazy("Event Data Field Configs"), child=EventFieldSerializer(), required=False, allow_empty=True
    )
    event_evidence_field_configs = serializers.ListField(
        label=gettext_lazy("Event Evidence Field Configs"),
        child=EventFieldSerializer(),
        required=False,
        allow_empty=True,
    )
    risk_meta_field_config = serializers.ListField(
        label=gettext_lazy("Risk Meta Field Config"),
        child=EventFieldSerializer(),
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = Strategy
        fields = [
            "risk_level",
            "risk_hazard",
            "risk_guidance",
            "event_basic_field_configs",
            "event_data_field_configs",
            "event_evidence_field_configs",
            "risk_meta_field_config",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["event_data_field_configs"] = merge_select_field_type(instance, data.get("event_data_field_configs", []))
        # 对基础字段描述进行国际化
        event_basic_field_configs = data.get("event_basic_field_configs") or []
        for config in event_basic_field_configs:
            config["display_name"] = gettext(config["display_name"])
            # 兼容历史数据
            if config["field_name"] == EventMappingFields.RAW_EVENT_ID.field_name:
                config["description"] = str(RAW_EVENT_ID_REMARK)
        return data


class EventFieldAPIGWSerializer(EventFieldSerializer):
    enum_mappings = serializers.JSONField(required=False, allow_null=True)


class RetrieveRiskStrategyInfoAPIGWResponseSerializer(RetrieveRiskStrategyInfoResponseSerializer):
    event_basic_field_configs = serializers.ListField(
        label=gettext_lazy("Event Basic Field Configs"),
        child=EventFieldAPIGWSerializer(),
        required=False,
        allow_empty=True,
    )
    event_data_field_configs = serializers.ListField(
        label=gettext_lazy("Event Data Field Configs"),
        child=EventFieldAPIGWSerializer(),
        required=False,
        allow_empty=True,
    )
    event_evidence_field_configs = serializers.ListField(
        label=gettext_lazy("Event Evidence Field Configs"),
        child=EventFieldAPIGWSerializer(),
        required=False,
        allow_empty=True,
    )
    risk_meta_field_config = serializers.ListField(
        label=gettext_lazy("Risk Meta Field Config"),
        child=EventFieldAPIGWSerializer(),
        required=False,
        allow_empty=True,
    )

    def __init__(self, *args, **kwargs):
        self.prohibit_enum_mappings = kwargs.pop("prohibit_enum_mappings", False)
        super().__init__(*args, **kwargs)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self.prohibit_enum_mappings:
            return data
        for field_key in (
            "event_basic_field_configs",
            "event_data_field_configs",
            "event_evidence_field_configs",
            "risk_meta_field_config",
        ):
            for field_config in data.get(field_key, []):
                if isinstance(field_config, dict):
                    field_config.pop("enum_mappings", None)
        return data


class RiskExportReqSerializer(serializers.Serializer):
    """
    Risk Export Request Serializer
    """

    risk_ids = serializers.ListField(
        label=gettext_lazy("Risk IDs"), child=serializers.CharField(), min_length=1, max_length=300
    )
    risk_view_type = serializers.ChoiceField(
        label=gettext_lazy("Risk View Type"), required=False, choices=RiskViewType.choices
    )


class AIVariableSerializer(serializers.Serializer):
    """AI 变量配置序列化器"""

    name = serializers.CharField(label=gettext_lazy("AI变量名"), help_text=gettext_lazy("必须以 ai. 开头，如 ai.risk_summary"))
    prompt_template = serializers.CharField(label=gettext_lazy("AI提示词模板"), help_text=gettext_lazy("可以包含风险变量和事件变量"))

    def validate_name(self, value: str) -> str:
        """验证 AI 变量名必须以 ai. 开头"""
        if not value.startswith("ai."):
            raise serializers.ValidationError(gettext_lazy("AI变量名必须以 'ai.' 开头"))
        return value


class AIPreviewRequestSerializer(serializers.Serializer):
    """AI 智能体预览请求序列化器"""

    risk_id = serializers.CharField(label=gettext_lazy("风险ID"))
    ai_variables = serializers.ListField(
        child=AIVariableSerializer(),
        label=gettext_lazy("AI变量配置列表"),
        min_length=1,
        help_text=gettext_lazy("至少需要配置一个 AI 变量"),
    )


class AsyncTaskResponseSerializer(serializers.Serializer):
    """异步任务提交响应序列化器"""

    task_id = serializers.CharField(label=gettext_lazy("异步任务ID"))
    status = serializers.CharField(
        label=gettext_lazy("任务状态"), help_text=gettext_lazy("PENDING / RUNNING / SUCCESS / FAILURE")
    )


class TaskResultRequestSerializer(serializers.Serializer):
    """查询任务结果请求序列化器"""

    task_id = serializers.CharField(label=gettext_lazy("异步任务ID"))


class TaskResultResponseSerializer(serializers.Serializer):
    """查询任务结果响应序列化器"""

    task_id = serializers.CharField(label=gettext_lazy("异步任务ID"))
    status = serializers.CharField(
        label=gettext_lazy("任务状态"), help_text=gettext_lazy("PENDING / RUNNING / SUCCESS / FAILURE")
    )
    result = serializers.JSONField(
        label=gettext_lazy("任务结果"),
        help_text=gettext_lazy("SUCCESS 时返回结果，FAILURE 时返回错误信息"),
        allow_null=True,
        required=False,
    )


# ============ 风险报告相关序列化器 ============


class ListRiskBriefRequestSerializer(serializers.Serializer):
    """
    获取风险简要列表请求序列化器
    """

    strategy_id = serializers.IntegerField(required=False, label=gettext_lazy("策略ID"))
    start_time = serializers.DateTimeField(required=True, label=gettext_lazy("开始时间"))
    end_time = serializers.DateTimeField(required=True, label=gettext_lazy("结束时间"))


class ListRiskBriefResponseSerializer(serializers.ModelSerializer):
    """
    获取风险简要列表响应序列化器
    """

    class Meta:
        model = Risk
        fields = ["risk_id", "title", "strategy_id", "created_at"]


class UpdateRiskRequestSerializer(serializers.Serializer):
    """
    编辑风险请求序列化器
    """

    risk_id = serializers.CharField(label=gettext_lazy("风险ID"))
    title = serializers.CharField(required=False, label=gettext_lazy("风险标题"), max_length=256)


class RiskReportModelSerializer(serializers.ModelSerializer):
    """
    风险报告 ModelSerializer（用于创建/编辑响应）
    """

    auto_generate = serializers.BooleanField(
        label=gettext_lazy("是否开启自动生成报告"),
        source="risk.auto_generate_report",
        read_only=True,
    )

    class Meta:
        model = RiskReport
        fields = ["content", "status", "auto_generate", "created_at", "updated_at"]


class CreateRiskReportRequestSerializer(serializers.Serializer):
    """
    创建风险报告请求序列化器
    """

    risk_id = serializers.CharField(label=gettext_lazy("风险ID"))
    content = serializers.CharField(label=gettext_lazy("报告内容"))
    auto_generate = serializers.BooleanField(
        required=False,
        default=False,
        label=gettext_lazy("是否开启自动生成报告"),
    )


class UpdateRiskReportRequestSerializer(serializers.Serializer):
    """
    编辑风险报告请求序列化器
    """

    risk_id = serializers.CharField(label=gettext_lazy("风险ID"))
    content = serializers.CharField(label=gettext_lazy("报告内容"))
    auto_generate = serializers.BooleanField(
        default=False,
        label=gettext_lazy("是否开启自动生成报告"),
    )


class GenerateRiskReportRequestSerializer(serializers.Serializer):
    """
    生成风险报告请求序列化器
    """

    risk_id = serializers.CharField(label=gettext_lazy("风险ID"))


class GenerateRiskReportResponseSerializer(serializers.Serializer):
    """
    生成风险报告响应序列化器
    """

    task_id = serializers.CharField(label=gettext_lazy("异步任务ID"))
    status = serializers.CharField(label=gettext_lazy("任务状态"))
