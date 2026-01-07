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
import json
from datetime import datetime, timedelta
from typing import List

from django.utils.translation import gettext, gettext_lazy
from rest_framework import serializers

from apps.meta.constants import OrderTypeChoices
from apps.meta.serializers import (
    BatchUpdateEnumMappingSerializer,
    EnumMappingByCollectionKeysSerializer,
    EnumMappingByCollectionSerializer,
)
from core.serializers import ChoiceListSerializer, OrderSerializer
from services.web.analyze.constants import (
    ControlTypeChoices,
    FilterConnector,
    FilterOperator,
    FlowDataSourceNodeType,
    OffsetUnit,
)
from services.web.analyze.exceptions import ControlNotExist
from services.web.analyze.models import Control, ControlVersion
from services.web.common.caller_permission import CALLER_RESOURCE_TYPE_CHOICES
from services.web.risk.constants import EVENT_BASIC_MAP_FIELDS
from services.web.risk.report_config import ReportConfig
from services.web.strategy_v2.constants import (
    BKMONITOR_AGG_INTERVAL_MIN,
    STRATEGY_SCHEDULE_TIME,
    STRATEGY_STATUS_DEFAULT_INTERVAL,
    ConnectorChoices,
    LinkTableJoinType,
    LinkTableTableType,
    ListLinkTableSortField,
    ListTableType,
    RiskLevel,
    RuleAuditAggregateType,
    RuleAuditConditionOperator,
    RuleAuditConfigType,
    RuleAuditFieldType,
    RuleAuditSourceType,
    RuleAuditWhereConnector,
    StrategyAlgorithmOperator,
    StrategyOperator,
    StrategySource,
    StrategyType,
    TableType,
)
from services.web.strategy_v2.exceptions import (
    LinkTableNameExist,
    SchedulePeriodInvalid,
    StrategyTypeNotSupport,
)
from services.web.strategy_v2.models import LinkTable, Strategy, StrategyTool
from services.web.tool.constants import DrillConfig

# 从 Pydantic BaseModel 生成的 DRF 序列化器类
ReportConfigSerializer = type(ReportConfig.drf_serializer())


def merge_select_field_type(strategy: Strategy, event_data_field_configs: List[dict]) -> List[dict]:
    """
    将策略 configs.select 中的 field_type 合并到 event_data_field_configs，按 (field_name, display_name) 唯一键匹配。
    """

    if not strategy or not event_data_field_configs:
        return event_data_field_configs

    select_fields = (strategy.configs or {}).get("select", []) if isinstance(strategy.configs, dict) else []

    field_type_map = {
        select["display_name"]: select["field_type"] for select in select_fields if select.get("field_type")
    }

    for field in event_data_field_configs:
        field_name = field["field_name"]
        field_type = field_type_map.get(field_name)
        if field_type:
            field["field_type"] = field_type
        else:
            field["field_type"] = None
    return event_data_field_configs


class MapFieldSerializer(serializers.Serializer):
    source_field = serializers.CharField(
        label=gettext_lazy("Source Field"),
        required=False,
        help_text=gettext_lazy("来源字段的display_name，在查询中唯一"),
    )
    target_value = serializers.CharField(
        label=gettext_lazy("Target Value"), required=False, help_text=gettext_lazy("固定值")
    )

    def validate(self, attrs):
        # 来源字段和目标值至少设置一个,优先级：目标值>来源字段
        attrs = super().validate(attrs)
        if not any([attrs.get("source_field"), attrs.get("target_value")]):
            raise serializers.ValidationError(gettext("Source Field or Target Value must be set at least one"))
        return attrs


class EnumMappingConfigSerializer(BatchUpdateEnumMappingSerializer):
    related_type = serializers.CharField(max_length=255, read_only=True, default="strategy")
    related_object_id = serializers.CharField(max_length=255, read_only=True, default="strategy_id")
    # Ensure collection_id is not user-modifiable and auto-generated key
    collection_id = serializers.CharField(read_only=True, default='auto-generate')


class EnumMappingByCollectionWithCallerSerializer(EnumMappingByCollectionSerializer):
    """
    枚举集合查询（携带可选的 caller 权限上下文）
    """

    # 可选：调用方上下文（目前支持 risk）
    caller_resource_type = serializers.ChoiceField(required=False, choices=CALLER_RESOURCE_TYPE_CHOICES)
    caller_resource_id = serializers.CharField(required=False, allow_blank=True)


class EnumMappingByCollectionKeysWithCallerSerializer(EnumMappingByCollectionKeysSerializer):
    """
    枚举查询（携带可选的 caller 权限上下文）
    """

    # 可选：调用方上下文（目前支持 risk）
    caller_resource_type = serializers.ChoiceField(required=False, choices=CALLER_RESOURCE_TYPE_CHOICES)
    caller_resource_id = serializers.CharField(required=False, allow_blank=True)


class EventFieldSerializer(serializers.Serializer):
    field_name = serializers.CharField(label=gettext_lazy("Field Name"))
    display_name = serializers.CharField(label=gettext_lazy("Field Display Name"))
    is_priority = serializers.BooleanField(label=gettext_lazy("Is Priority"))
    description = serializers.CharField(label=gettext_lazy("Field Description"), default="", allow_blank=True)
    enum_mappings = EnumMappingConfigSerializer(
        label=gettext_lazy("Enum Mappings"),
        required=False,
        allow_null=True,
    )
    drill_config = DrillConfig.drf_serializer(label=gettext_lazy("下钻配置"), many=True, default=list, allow_null=True)
    is_show = serializers.BooleanField(label=gettext_lazy("是否展示"), default=True)
    duplicate_field = serializers.BooleanField(label=gettext_lazy("是否去重字段"), default=False, required=False)
    field_type = serializers.CharField(
        label=gettext_lazy("Field Type"), required=False, default=None, allow_null=True, allow_blank=True
    )


class EventBasicFieldSerializer(EventFieldSerializer):
    map_config = MapFieldSerializer(label=gettext_lazy("Map Field"), required=False, allow_null=True)


class StrategySerializer(serializers.Serializer):
    strategy_type = serializers.ChoiceField(
        label=gettext_lazy("Storage Type"), choices=StrategyType.choices, default=StrategyType.MODEL.value
    )

    def _validate_strategy_type(self, validated_request_data: dict):
        """
        校验策略类型
        """

        strategy_type = validated_request_data["strategy_type"]
        sql_value = validated_request_data.get("sql")
        if sql_value and strategy_type != StrategyType.RULE.value:
            raise serializers.ValidationError(gettext("SQL is only allowed for rule strategy"))
        if strategy_type == StrategyType.MODEL.value:
            if not (validated_request_data.get("control_id") and validated_request_data.get("control_version")):
                raise serializers.ValidationError(
                    gettext("control_id and control_version are required when strategy_type is model"),
                )
            # check control
            if not ControlVersion.objects.filter(
                control_id=validated_request_data["control_id"],
                control_version=validated_request_data["control_version"],
            ).exists():
                raise serializers.ValidationError(gettext("Control Version not Exists"))
        elif strategy_type == StrategyType.RULE.value:
            if validated_request_data.get("configs", {}).get("config_type") != RuleAuditConfigType.LINK_TABLE:
                validated_request_data["link_table_uid"] = None
                validated_request_data["link_table_version"] = None
                return
            link_table = validated_request_data.get("configs", {}).get("data_source", {}).get("link_table", {})
            # 提取策略内的联表信息
            validated_request_data["link_table_uid"] = link_table.get("uid")
            validated_request_data["link_table_version"] = link_table.get("version")

    def _validate_configs(self, validated_request_data: dict):
        """
        校验策略配置
        """

        strategy_type = validated_request_data["strategy_type"]
        # 模型审计
        if strategy_type == StrategyType.MODEL.value:
            control_type_id = Control.objects.get(control_id=validated_request_data["control_id"]).control_type_id
            if control_type_id == ControlTypeChoices.BKM.value:
                configs_serializer_class = BKMStrategySerializer
            elif control_type_id == ControlTypeChoices.AIOPS.value:
                configs_serializer_class = AIOPSConfigSerializer
            else:
                raise ControlNotExist()
        # 规则审计
        elif strategy_type == StrategyType.RULE.value:
            configs_serializer_class = RuleAuditSerializer
        else:
            raise StrategyTypeNotSupport()
        configs_serializer = configs_serializer_class(data=validated_request_data["configs"])
        configs_serializer.is_valid(raise_exception=True)
        validated_request_data["configs"] = configs_serializer.validated_data
        return validated_request_data

    def _validate_event_basic_field_configs(self, validated_request_data: dict):
        """
        校验事件基本信息字段配置
        """

        strategy_type = validated_request_data["strategy_type"]
        if strategy_type != StrategyType.RULE.value:
            return
        event_basic_field_configs = validated_request_data["event_basic_field_configs"]
        mapped_fields = {field["field_name"] for field in event_basic_field_configs if field.get("map_config")}
        # 检查需要配置映射的字段
        for field in EVENT_BASIC_MAP_FIELDS:
            if field.field_name not in mapped_fields:
                raise serializers.ValidationError(gettext("%s Need to configure mapping") % field.description)
        return validated_request_data

    def _validate_report_config(self, validated_request_data: dict):
        """
        校验报告配置

        规则：如果 report_enabled 开启，则必须有 report_config
        """
        report_enabled = validated_request_data.get("report_enabled", False)
        report_config = validated_request_data.get("report_config")

        if report_enabled and not report_config:
            raise serializers.ValidationError(gettext("report_config is required when report_enabled is True"))


class CreateStrategyRequestSerializer(StrategySerializer, serializers.ModelSerializer):
    """
    Create Strategy
    """

    sql = serializers.CharField(
        label=gettext_lazy("Rule Audit SQL"),
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    tags = serializers.ListField(
        label=gettext_lazy("Tags"), child=serializers.CharField(label=gettext_lazy("Tag Name")), default=list
    )
    event_basic_field_configs = serializers.ListField(
        label=gettext_lazy("Event Basic Field Configs"),
        child=EventBasicFieldSerializer(),
        default=list,
        allow_empty=True,
    )
    event_data_field_configs = serializers.ListField(
        label=gettext_lazy("Event Data Field Configs"), child=EventFieldSerializer(), default=list, allow_empty=True
    )
    event_evidence_field_configs = serializers.ListField(
        label=gettext_lazy("Event Evidence Field Configs"), child=EventFieldSerializer(), default=list, allow_empty=True
    )
    risk_meta_field_config = serializers.ListField(
        label=gettext_lazy("Risk Meta Field Config"), child=EventBasicFieldSerializer(), default=list, allow_empty=True
    )
    risk_level = serializers.ChoiceField(label=gettext_lazy("Risk Level"), choices=RiskLevel.choices)
    risk_title = serializers.CharField(label=gettext_lazy("Risk Title"))
    source = serializers.ChoiceField(
        label=gettext_lazy("Strategy Source"), choices=StrategySource.choices, default=StrategySource.USER
    )
    processor_groups = serializers.ListField(
        label=gettext_lazy("Processor Groups"),
        child=serializers.IntegerField(label=gettext_lazy("Processor Group")),
        allow_empty=False,
    )
    report_config = ReportConfigSerializer(required=False, allow_null=True)

    class Meta:
        model = Strategy
        fields = [
            "namespace",
            "strategy_name",
            "control_id",
            "control_version",
            "strategy_type",
            "sql",
            "configs",
            "tags",
            "notice_groups",
            "description",
            "risk_level",
            "risk_hazard",
            "risk_guidance",
            "risk_title",
            "processor_groups",
            "event_basic_field_configs",
            "event_data_field_configs",
            "event_evidence_field_configs",
            "risk_meta_field_config",
            "source",
            "report_enabled",
            "report_config",
        ]

    def validate(self, attrs: dict) -> dict:
        data = super().validate(attrs)
        # check type
        self._validate_strategy_type(data)
        # check name
        if Strategy.objects.filter(strategy_name=attrs["strategy_name"]).exists():
            raise serializers.ValidationError(gettext("Strategy Name Duplicate"))
        # check configs
        self._validate_configs(data)
        # check event_basic_field_configs
        self._validate_event_basic_field_configs(data)
        # check report_config
        self._validate_report_config(data)
        return data


class CreateStrategyResponseSerializer(serializers.ModelSerializer):
    """
    Create Strategy
    """

    class Meta:
        model = Strategy
        fields = ["strategy_id", "strategy_name"]


class UpdateStrategyRequestSerializer(StrategySerializer, serializers.ModelSerializer):
    """
    Update Strategy
    """

    sql = serializers.CharField(
        label=gettext_lazy("Rule Audit SQL"),
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    tags = serializers.ListField(
        label=gettext_lazy("Tags"), child=serializers.CharField(label=gettext_lazy("Tag Name")), default=list
    )
    strategy_id = serializers.IntegerField(label=gettext_lazy("Strategy ID"))
    event_basic_field_configs = serializers.ListField(
        label=gettext_lazy("Event Basic Field Configs"),
        child=EventBasicFieldSerializer(),
        default=list,
        allow_empty=True,
    )
    event_data_field_configs = serializers.ListField(
        label=gettext_lazy("Event Data Field Configs"), child=EventFieldSerializer(), default=list, allow_empty=True
    )
    event_evidence_field_configs = serializers.ListField(
        label=gettext_lazy("Event Evidence Field Configs"), child=EventFieldSerializer(), default=list, allow_empty=True
    )
    risk_meta_field_config = serializers.ListField(
        label=gettext_lazy("Risk Meta Field Config"), child=EventBasicFieldSerializer(), default=list, allow_empty=True
    )
    risk_title = serializers.CharField(label=gettext_lazy("Risk Title"))
    source = serializers.ChoiceField(
        label=gettext_lazy("Strategy Source"), choices=StrategySource.choices, default=StrategySource.USER
    )
    processor_groups = serializers.ListField(
        label=gettext_lazy("Processor Groups"),
        child=serializers.IntegerField(label=gettext_lazy("Processor Group")),
        allow_empty=False,
    )
    risk_level = serializers.ChoiceField(label=gettext_lazy("Risk Level"), choices=RiskLevel.choices)
    report_config = ReportConfigSerializer(required=False, allow_null=True)

    class Meta:
        model = Strategy
        # 若有可变化的字段变更，需要同步修改本地更新的字段列表 LOCAL_UPDATE_FIELDS
        fields = [
            "namespace",
            "strategy_id",
            "strategy_name",
            "control_id",
            "control_version",
            "strategy_type",
            "sql",
            "configs",
            "tags",
            "notice_groups",
            "description",
            "risk_level",
            "risk_hazard",
            "risk_guidance",
            "risk_title",
            "processor_groups",
            "event_basic_field_configs",
            "event_data_field_configs",
            "event_evidence_field_configs",
            "risk_meta_field_config",
            "source",
            "report_enabled",
            "report_config",
        ]

    def validate(self, attrs: dict) -> dict:
        data = super().validate(attrs)
        # check type
        self._validate_strategy_type(data)
        # check name
        if (
            Strategy.objects.filter(strategy_name=attrs["strategy_name"])
            .exclude(strategy_id=attrs["strategy_id"])
            .exists()
        ):
            raise serializers.ValidationError(gettext("Strategy Name Duplicate"))
        # check configs
        self._validate_configs(data)
        # check event_basic_field_configs
        self._validate_event_basic_field_configs(data)
        # check report_config
        self._validate_report_config(data)
        return data


class UpdateStrategyResponseSerializer(serializers.ModelSerializer):
    """
    Update Strategy
    """

    class Meta:
        model = Strategy
        fields = ["strategy_id", "strategy_name"]


class ListStrategyRequestSerializer(serializers.Serializer):
    """
    List Strategy
    """

    namespace = serializers.CharField(label=gettext_lazy("Namespace"))
    strategy_id = serializers.CharField(label=gettext_lazy("Strategy ID"), required=False)
    strategy_name = serializers.CharField(label=gettext_lazy("Strategy Name"), required=False)
    tag = serializers.CharField(label=gettext_lazy("Tag"), required=False)
    status = serializers.CharField(label=gettext_lazy("Status"), required=False)
    order_field = serializers.CharField(label=gettext_lazy("排序字段"), required=False, allow_null=True, allow_blank=True)
    order_type = serializers.ChoiceField(
        label=gettext_lazy("排序方式"),
        required=False,
        allow_null=True,
        allow_blank=True,
        choices=OrderTypeChoices.choices,
    )
    link_table_uid = serializers.CharField(label=gettext_lazy("Link Table UID"), required=False)
    strategy_type = serializers.CharField(label=gettext_lazy("Strategy Type"), required=False)

    def validate(self, attrs: dict) -> dict:
        data = super().validate(attrs)
        # split into array
        for key, val in data.items():
            if key in ["namespace", "order_field", "order_type"]:
                continue
            data[key] = [i for i in val.split(",") if i] if val else []
        # order
        if attrs.get("order_field") and attrs.get("order_type"):
            attrs["order_field"] = (
                f"-{attrs['order_field']}" if attrs.get("order_type") == OrderTypeChoices.DESC else attrs["order_field"]
            )
        else:
            attrs.pop("order_field", None)
            attrs.pop("order_type", None)
        return data


class StrategyToolSerializer(serializers.ModelSerializer):
    class Meta:
        model = StrategyTool
        fields = [
            "field_name",
            "field_source",
            "tool_uid",
            "tool_version",
        ]


class ListStrategyResponseSerializer(serializers.ModelSerializer):
    """
    List Strategy
    """

    tags = serializers.SerializerMethodField()
    risk_count = serializers.IntegerField(label=gettext_lazy("Risk Count"))
    tools = StrategyToolSerializer(many=True, read_only=True)

    def get_tags(self, obj):
        """
        从预加载的策略标签关系中获取tag_id列表
        """
        if hasattr(obj, 'prefetched_tags'):
            # 使用预加载的数据
            return [tag_rel.tag_id for tag_rel in obj.prefetched_tags]
        else:
            # 回退方案：直接使用关系查询
            return list(obj.tags.values_list('tag_id', flat=True))

    class Meta:
        model = Strategy
        exclude = ["backend_data"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["event_data_field_configs"] = merge_select_field_type(instance, data.get("event_data_field_configs", []))
        return data


class StrategyInfoSerializer(serializers.ModelSerializer):
    """
    Strategy Info
    """

    class Meta:
        model = Strategy
        fields = [
            "namespace",
            "strategy_id",
            "strategy_name",
            "control_id",
            "control_version",
            "is_formal",
            "source",
            "notice_groups",
            "risk_level",
            "risk_hazard",
            "risk_guidance",
            "risk_title",
            "processor_groups",
            "report_enabled",
            "report_config",
        ]


class StrategyDetailSerializer(serializers.ModelSerializer):
    """
    策略详情序列化器

    返回策略全量配置（包含 report_config），用于策略编辑页面。
    与 ListStrategyResponseSerializer 保持返回逻辑一致。
    """

    tags = serializers.SerializerMethodField()
    tools = StrategyToolSerializer(many=True, read_only=True)

    def get_tags(self, obj):
        """
        从预加载的策略标签关系中获取 tag_id 列表
        """
        if hasattr(obj, 'prefetched_tags'):
            return [tag_rel.tag_id for tag_rel in obj.prefetched_tags]
        else:
            return list(obj.tags.values_list('tag_id', flat=True))

    class Meta:
        model = Strategy
        fields = "__all__"

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["event_data_field_configs"] = merge_select_field_type(instance, data.get("event_data_field_configs", []))
        return data


class StrategyProviderSerializer(serializers.ModelSerializer):
    """
    用于 Provider 的策略快照/Schema 序列化器
    - 显式声明 strategy_id 为可写普通字段，便于在 Schema 中展示
    """

    strategy_id = serializers.IntegerField(label=gettext_lazy("Strategy ID"))

    class Meta:
        model = Strategy
        fields = [
            "namespace",
            "strategy_id",
            "strategy_name",
            "control_id",
            "control_version",
            "strategy_type",
            "configs",
            "sql",
            "link_table_uid",
            "link_table_version",
            "status",
            "status_msg",
            "backend_data",
            "notice_groups",
            "processor_groups",
            "description",
            "risk_level",
            "risk_hazard",
            "risk_guidance",
            "risk_title",
            "event_basic_field_configs",
            "event_data_field_configs",
            "event_evidence_field_configs",
            "risk_meta_field_config",
            "is_formal",
        ]


class ToggleStrategyRequestSerializer(serializers.Serializer):
    """
    Toggle Strategy
    """

    strategy_id = serializers.IntegerField(label=gettext_lazy("Strategy ID"))
    toggle = serializers.BooleanField(label=gettext_lazy("Toggle"))


class ListStrategyTagsResponseSerializer(serializers.Serializer):
    """
    List Strategy Tags
    """

    tag_id = serializers.CharField(label=gettext_lazy("Tag ID"))
    tag_name = serializers.CharField(label=gettext_lazy("Tag Name"))
    strategy_count = serializers.IntegerField(label=gettext_lazy("Strategy Count"))


class StrategyTagResourceSerializer(serializers.Serializer):
    """Serializer for IAM strategy tag resource snapshot."""

    id = serializers.IntegerField(label=gettext_lazy("ID"))
    tag_id = serializers.IntegerField(label=gettext_lazy("Tag ID"))
    strategy_id = serializers.IntegerField(label=gettext_lazy("Strategy ID"))


class AggConditionSerializer(serializers.Serializer):
    """
    Agg Condition
    """

    key = serializers.CharField(label=gettext_lazy("Key"))
    value = serializers.ListField(label=gettext_lazy("Value"), child=serializers.CharField())
    method = serializers.ChoiceField(label=gettext_lazy("Method"), choices=StrategyOperator.choices)
    condition = serializers.ChoiceField(label=gettext_lazy("Condition"), choices=ConnectorChoices.choices)


class AlgorithmsSerializer(serializers.Serializer):
    """
    Algorithms
    """

    method = serializers.ChoiceField(label=gettext_lazy("Method"), choices=StrategyAlgorithmOperator.choices)
    threshold = serializers.IntegerField(label=gettext_lazy("Threshold"))


class DetectsSerializer(serializers.Serializer):
    """
    Detects
    """

    count = serializers.IntegerField(label=gettext_lazy("Count"))
    alert_window = serializers.IntegerField(label=gettext_lazy("Alert Window"))


class BKMStrategySerializer(serializers.Serializer):
    """
    BKM Strategy
    """

    agg_condition = AggConditionSerializer(label=gettext_lazy("Condition"), many=True)
    agg_dimension = serializers.ListField(label=gettext_lazy("Dimension"), child=serializers.CharField())
    agg_interval = serializers.IntegerField(label=gettext_lazy("Interval"), min_value=BKMONITOR_AGG_INTERVAL_MIN)
    algorithms = AlgorithmsSerializer(label=gettext_lazy("Algorithms"), many=True)
    detects = DetectsSerializer(label=gettext_lazy("Detects"))


class GetStrategyFieldValueRequestSerializer(serializers.Serializer):
    """
    Get Strategy Field Value
    """

    namespace = serializers.CharField(label=gettext_lazy("Namespace"))
    field_name = serializers.CharField(label=gettext_lazy("Field Name"))
    system_id = serializers.CharField(label=gettext_lazy("System ID"), required=False)


class GetStrategyFieldValueResponseSerializer(serializers.Serializer):
    """
    Get Strategy Field Value
    """

    label = serializers.CharField(label=gettext_lazy("Label"))
    value = serializers.CharField(label=gettext_lazy("Value"))
    children = serializers.ListField(label=gettext_lazy("Children"), required=False)


class ListStrategyFieldsRequestSerializer(serializers.Serializer):
    """
    List Strategy Fields
    """

    namespace = serializers.CharField(label=gettext_lazy("Namespace"))
    system_id = serializers.CharField(label=gettext_lazy("System ID"), required=False)
    action_id = serializers.CharField(label=gettext_lazy("Action ID"), required=False)


class ListStrategyFieldsResponseSerializer(serializers.Serializer):
    """
    List Strategy Fields
    """

    field_name = serializers.CharField(label=gettext_lazy("Field Name"))
    description = serializers.CharField(label=gettext_lazy("Description"))
    field_type = serializers.CharField(label=gettext_lazy("Field Type"))
    is_dimension = serializers.BooleanField(label=gettext_lazy("Dimension"))


class GetStrategyCommonResponseSerializer(serializers.Serializer):
    """
    Get Strategy Common
    """

    strategy_operator = ChoiceListSerializer(label=gettext_lazy("Strategy Operator"), many=True)
    filter_operator = ChoiceListSerializer(label=gettext_lazy("Filter Operator"), many=True)
    algorithm_operator = ChoiceListSerializer(label=gettext_lazy("Filter Operator"), many=True)
    table_type = ChoiceListSerializer(label=gettext_lazy("Table Type"), many=True)
    strategy_status = ChoiceListSerializer(label=gettext_lazy("Strategy Status"), many=True)
    offset_unit = ChoiceListSerializer(label=gettext_lazy("Offset Unit"), many=True)
    mapping_type = ChoiceListSerializer(label=gettext_lazy("Mapping Type"), many=True)
    risk_level = ChoiceListSerializer(label=gettext_lazy("Risk Level"), many=True)
    strategy_type = ChoiceListSerializer(label=gettext_lazy("Strategy Type"), many=True)
    link_table_join_type = ChoiceListSerializer(label=gettext_lazy("Link Table Join Type"), many=True)
    link_table_table_type = ChoiceListSerializer(label=gettext_lazy("Link Table Table Type"), many=True)
    rule_audit_aggregate_type = ChoiceListSerializer(label=gettext_lazy("Rule Audit Aggregate Type"), many=True)
    rule_audit_field_type = ChoiceListSerializer(label=gettext_lazy("Rule Audit Field Type"), many=True)
    rule_audit_config_type = ChoiceListSerializer(label=gettext_lazy("Rule Audit Config Type"), many=True)
    rule_audit_source_type = ChoiceListSerializer(label=gettext_lazy("Rule Audit Source Type"), many=True)
    rule_audit_condition_operator = ChoiceListSerializer(label=gettext_lazy("Rule Audit Condition Operator"), many=True)
    rule_audit_where_connector = ChoiceListSerializer(label=gettext_lazy("Rule Audit Where Connector"), many=True)


class AIOPSDataSourceFilterSerializer(serializers.Serializer):
    """
    AIOPS Data Source Filter
    """

    key = serializers.CharField(label=gettext_lazy("Field Name"))
    method = serializers.ChoiceField(label=gettext_lazy("Method"), choices=FilterOperator.choices)
    value = serializers.ListField(label=gettext_lazy("Value"), child=serializers.CharField())
    connector = serializers.ChoiceField(label=gettext_lazy("Connector"), choices=FilterConnector.choices)


class AIOPSDataSourceFieldsSerializer(serializers.Serializer):
    """
    Fields
    """

    field_name = serializers.CharField(label=gettext_lazy("Field Name"))
    source_field = serializers.CharField(label=gettext_lazy("Source Field"))


class AIOPSDataSourceSerializer(serializers.Serializer):
    """
    Data Source
    """

    source_type = serializers.ChoiceField(label=gettext_lazy("Source Type"), choices=FlowDataSourceNodeType.choices)
    result_table_id = serializers.CharField(label=gettext_lazy("Result Table ID"))
    bk_biz_id = serializers.CharField(
        label=gettext_lazy("BK Biz ID"), allow_null=True, allow_blank=True, required=False
    )
    filter_config = AIOPSDataSourceFilterSerializer(label=gettext_lazy("Filter Config"), many=True)
    fields = serializers.JSONField(label=gettext_lazy("Fields"))


class ScheduleConfigSerializer(serializers.Serializer):
    """
    Schedule Config
    """

    count_freq = serializers.IntegerField(label=gettext_lazy("Schedule Period"), min_value=1)
    schedule_period = serializers.ChoiceField(label=gettext_lazy("Schedule Period Unit"), choices=OffsetUnit.choices)

    def validate(self, attr: dict) -> dict:
        data = super().validate(attr)
        if any(
            [
                data["schedule_period"] == OffsetUnit.HOUR and data["count_freq"] > STRATEGY_SCHEDULE_TIME * 24,
                data["schedule_period"] == OffsetUnit.DAY and data["count_freq"] > STRATEGY_SCHEDULE_TIME,
            ]
        ):
            raise SchedulePeriodInvalid()
        return data


class AIOPSSceneConfigSerializer(ScheduleConfigSerializer):
    """
    AIOPS Scene Config
    """

    ...


class AIOPSConfigSerializer(serializers.Serializer):
    """
    AIOPS Config
    """

    data_source = AIOPSDataSourceSerializer(label=gettext_lazy("Data Source"))
    config_type = serializers.ChoiceField(label=gettext_lazy("配置类型"), choices=TableType.choices)
    aiops_config = AIOPSSceneConfigSerializer(label=gettext_lazy("AIOPS Config"), required=False)
    variable_config = serializers.ListField(label=gettext_lazy("方案参数"), required=False, child=serializers.JSONField())


class ListTablesRequestSerializer(serializers.Serializer):
    """
    List Tables
    """

    table_type = serializers.ChoiceField(label=gettext_lazy("Table Type"), choices=ListTableType.choices)
    namespace = serializers.CharField(label=gettext_lazy("Namespace"), required=False)


class GetRTFieldsRequestSerializer(serializers.Serializer):
    """
    Get RT Fields
    """

    table_id = serializers.CharField(label=gettext_lazy("Table ID"))


class GetRTMetaRequestSerializer(serializers.Serializer):
    """
    Get RT Meta
    """

    table_id = serializers.CharField(label=gettext_lazy("Table ID"))


class GetRTLastDataRequestSerializer(serializers.Serializer):
    """
    Get RT Last Data
    """

    table_id = serializers.CharField(label=gettext_lazy("Table ID"))
    limit = serializers.IntegerField(label=gettext_lazy("Limit"), required=False, default=5)


class BulkGetRTFieldsRequestSerializer(serializers.Serializer):
    """
    Bulk Get RT Fields
    """

    table_ids = serializers.CharField(
        label=gettext_lazy("Table IDS"), help_text=gettext_lazy("Multiple separated by commas")
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        attrs['table_ids'] = list(dict.fromkeys(attrs['table_ids'].split(',')))
        return attrs


class GetRTFieldsResponseSerializer(serializers.Serializer):
    """
    Get RT Fields
    """

    label = serializers.CharField(label=gettext_lazy("Label"))
    value = serializers.CharField(label=gettext_lazy("value"))
    alias = serializers.CharField(label=gettext_lazy("Alias"))
    field_type = serializers.CharField(label=gettext_lazy("Field Type"))
    spec_field_type = serializers.CharField(label=gettext_lazy("Spec Field Type"))
    property = serializers.DictField(label=gettext_lazy("Property"))


class BulkGetRTFieldsResponseSerializer(serializers.Serializer):
    """
    Bulk Get RT Fields
    """

    table_id = serializers.CharField(label=gettext_lazy("Table ID"))
    fields = serializers.ListField(child=GetRTFieldsResponseSerializer())


class GetStrategyStatusRequestSerializer(serializers.Serializer):
    """
    Get Strategy Status
    """

    strategy_ids = serializers.CharField(label=gettext_lazy("Strategy IDs"))

    def validate_strategy_ids(self, strategy_ids: str) -> List[int]:
        try:
            return [int(s) for s in strategy_ids.split(",") if s]
        except ValueError:
            raise serializers.ValidationError(gettext("Strategy ID Invalid"))


class RetryStrategyRequestSerializer(serializers.Serializer):
    """
    Retry Strategy
    """

    strategy_id = serializers.IntegerField(label=gettext_lazy("Strategy ID"))


class GetEventInfoFieldsRequestSerializer(serializers.Serializer):
    """
    Get Event Info Fields
    """

    strategy_id = serializers.IntegerField(label=gettext_lazy("Strategy ID"), required=False)


class EventInfoFieldSerializer(serializers.Serializer):
    """
    Get Event Info Fields
    """

    field_name = serializers.CharField(label=gettext_lazy("Name"))
    display_name = serializers.CharField(label=gettext_lazy("Display Name"))
    description = serializers.CharField(label=gettext_lazy("Description"), allow_blank=True)
    example = serializers.CharField(label=gettext_lazy("Example"), allow_blank=True, allow_null=True)
    is_show = serializers.BooleanField(label=gettext_lazy("是否展示"), default=True)
    duplicate_field = serializers.BooleanField(label=gettext_lazy("是否去重字段"), default=False, required=False)

    def to_internal_value(self, data):
        # example 可能是 list 或 bool，均转换为字符串进行展示
        example = data["example"]
        try:
            if isinstance(example, (list, dict)):
                data["example"] = json.dumps(example)
        except Exception:  # NOCC:broad-except(需要处理所有错误)
            pass
        finally:
            data["example"] = str(example)
        return super().to_internal_value(data)


class GetEventInfoFieldsResponseSerializer(serializers.Serializer):
    """
    Get Event Info Fields
    """

    event_basic_field_configs = serializers.ListField(
        label=gettext_lazy("Event Basic Field Configs"), child=EventInfoFieldSerializer()
    )
    event_data_field_configs = serializers.ListField(
        label=gettext_lazy("Event Data Field Configs"), child=EventInfoFieldSerializer(), required=False
    )
    event_evidence_field_configs = serializers.ListField(
        label=gettext_lazy("Event Evidence Field Configs"), child=EventInfoFieldSerializer(), required=False
    )
    risk_meta_field_config = serializers.ListField(
        label=gettext_lazy("Risk Meta Field Config"), child=EventInfoFieldSerializer(), required=False
    )


class GetStrategyDisplayInfoRequestSerializer(serializers.Serializer):
    strategy_ids = serializers.CharField(label=gettext_lazy("Strategy IDs"))

    def validate_strategy_ids(self, strategy_ids: str) -> List[int]:
        try:
            return [int(s) for s in strategy_ids.split(",") if s]
        except ValueError:
            raise serializers.ValidationError(gettext("Strategy ID Invalid"))


class LinkTableInfoSerializer(serializers.ModelSerializer):
    """
    LinkTable Info
    """

    class Meta:
        model = LinkTable
        fields = ["namespace", "uid", "name", "version", "description"]


class LinkTableConfigTableSerializer(serializers.Serializer):
    """
    联表配置表
    """

    rt_id = serializers.CharField(label=gettext_lazy("Result Table ID"))
    table_type = serializers.ChoiceField(label=gettext_lazy("Table Type"), choices=LinkTableTableType.choices)
    display_name = serializers.CharField(
        label=gettext_lazy("Display Name"), required=False, allow_blank=True, allow_null=True
    )
    system_ids = serializers.ListField(
        label=gettext_lazy("System IDs"), child=serializers.CharField(max_length=64), required=False
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs["table_type"] == LinkTableTableType.EVENT_LOG and not attrs.get("system_ids"):
            raise serializers.ValidationError(gettext("System IDs is required"))
        # display_name 默认值为 rt_id
        if not attrs.get("display_name"):
            attrs["display_name"] = attrs["rt_id"]
        return attrs


class LinkTableLinkFieldInfoSerializer(serializers.Serializer):
    """
    联表连接字段信息
    """

    field_name = serializers.CharField(label=gettext_lazy("Field Name"))
    display_name = serializers.CharField(
        label=gettext_lazy("Display Name"), default=None, allow_blank=True, allow_null=True
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        # display_name 默认值为 field_name
        if not attrs.get("display_name"):
            attrs["display_name"] = attrs["field_name"]
        return attrs


class LinkTableLinkFieldSerializer(serializers.Serializer):
    """
    联表连接字段
    """

    left_field = LinkTableLinkFieldInfoSerializer(label=gettext_lazy("Left Table Field"))
    right_field = LinkTableLinkFieldInfoSerializer(label=gettext_lazy("Right Table Field"))


class LinkTableLinkSerializer(serializers.Serializer):
    """
    联表连接配置
    """

    join_type = serializers.ChoiceField(label=gettext_lazy("Join Type"), choices=LinkTableJoinType)
    link_fields = serializers.ListField(
        label=gettext_lazy("Link Fields"), child=LinkTableLinkFieldSerializer(), allow_empty=False
    )
    left_table = LinkTableConfigTableSerializer(label=gettext_lazy("Left Table"))
    right_table = LinkTableConfigTableSerializer(label=gettext_lazy("Right Table"))


class LinkTableConfigSerializer(serializers.Serializer):
    """
    联表配置
    """

    links = serializers.ListField(label=gettext_lazy("Links"), child=LinkTableLinkSerializer(), allow_empty=False)


class CreateLinkTableRequestSerializer(serializers.ModelSerializer):
    tags = serializers.ListField(
        label=gettext_lazy("Tags"), child=serializers.CharField(label=gettext_lazy("Tag Name")), default=list
    )
    config = LinkTableConfigSerializer(label=gettext_lazy("Link Table Config"))

    class Meta:
        model = LinkTable
        fields = ["namespace", "name", "config", "description", "tags"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        namespace = attrs.get('namespace')
        name = attrs.get('name')

        # 联合唯一校验
        if LinkTable.objects.filter(namespace=namespace, name=name).exists():
            raise LinkTableNameExist()

        return attrs


class CreateLinkTableResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = LinkTable
        fields = [
            "uid",
            "version",
        ]


class UpdateLinkTableRequestSerializer(serializers.ModelSerializer):
    tags = serializers.ListField(
        label=gettext_lazy("Tags"), child=serializers.CharField(label=gettext_lazy("Tag Name")), required=False
    )
    config = LinkTableConfigSerializer(label=gettext_lazy("Link Table Config"), required=False)

    class Meta:
        model = LinkTable
        fields = ["namespace", "uid", "name", "tags", "config", "description"]
        extra_kwargs = {
            "name": {"required": False},
            "description": {"required": False},
        }

    def validate(self, attrs):
        attrs = super().validate(attrs)
        # 获取关键字段
        namespace = attrs.get('namespace')
        name = attrs.get('name')
        uid = attrs.get('uid')

        # 联合唯一校验
        if LinkTable.objects.filter(namespace=namespace, name=name).exclude(uid=uid).exists():
            raise LinkTableNameExist()

        return attrs


class UpdateLinkTableResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = LinkTable
        fields = [
            "uid",
            "version",
        ]


class TagsReqSerializer(serializers.Serializer):
    tags = serializers.CharField(label=gettext_lazy("Tags"), required=False, help_text=gettext_lazy("逗号分隔的标签ID列表"))

    def validate_tags(self, tags: str) -> List[int]:
        return [int(tag) for tag in tags.split(",") if tag and tag.isdigit()] if tags else []


class ListLinkTableRequestSerializer(OrderSerializer, TagsReqSerializer):
    order_field = serializers.ChoiceField(
        label=gettext_lazy("排序字段"),
        required=False,
        allow_null=True,
        allow_blank=True,
        choices=ListLinkTableSortField.choices,
    )

    namespace = serializers.CharField(label=gettext_lazy("Namespace"))
    name__contains = serializers.CharField(label=gettext_lazy("Link Table Name"), required=False)
    created_by = serializers.CharField(label=gettext_lazy("Created By"), required=False)
    updated_by = serializers.CharField(label=gettext_lazy("Updated By"), required=False)
    no_tag = serializers.BooleanField(label=gettext_lazy("No Tag"), default=False)
    uid = serializers.CharField(label=gettext_lazy("Link Table UID"), required=False)


class ListLinkTableAllResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = LinkTable
        fields = ["uid", "name", "version"]


class ListLinkTableResponseSerializer(serializers.ModelSerializer):
    tags = serializers.ListField(
        label=gettext_lazy("Tags"), child=serializers.IntegerField(label=gettext_lazy("Tag ID"))
    )
    strategy_count = serializers.IntegerField(label=gettext_lazy("Strategy Count"))
    need_update_strategy = serializers.BooleanField(label=gettext_lazy("Need Update Strategy"))

    class Meta:
        model = LinkTable
        exclude = ["config"]


class GetLinkTableRequestSerializer(serializers.Serializer):
    uid = serializers.CharField(label=gettext_lazy("Link Table UID"))
    version = serializers.IntegerField(label=gettext_lazy("Version"), required=False)


class GetLinkTableResponseSerializer(serializers.ModelSerializer):
    tags = serializers.ListField(
        label=gettext_lazy("Tags"), child=serializers.IntegerField(label=gettext_lazy("Tag ID"))
    )

    class Meta:
        model = LinkTable
        fields = "__all__"


class ListLinkTableTagsResponseSerializer(serializers.Serializer):
    """
    List Link Table Tags
    """

    tag_id = serializers.CharField(label=gettext_lazy("Tag ID"))
    tag_name = serializers.CharField(label=gettext_lazy("Tag Name"))
    link_table_count = serializers.IntegerField(label=gettext_lazy("Link Table Count"))


class RuleAuditFieldSerializer(serializers.Serializer):
    """
    Rule Audit Field
    """

    table = serializers.CharField(label=gettext_lazy("Table"))
    raw_name = serializers.CharField(label=gettext_lazy("Raw Name"))
    display_name = serializers.CharField(label=gettext_lazy("Display Name"))
    field_type = serializers.ChoiceField(label=gettext_lazy("Field Type"), choices=RuleAuditFieldType.choices)
    aggregate = serializers.ChoiceField(
        label=gettext_lazy("Aggregate"), choices=RuleAuditAggregateType.choices, allow_null=True, default=None
    )
    remark = serializers.CharField(label=gettext_lazy("Remark"), required=False, default="", allow_blank=True)
    keys = serializers.ListField(
        label=gettext_lazy("Keys"), child=serializers.CharField(), required=False, allow_empty=True, default=list
    )


class RuleAuditLinkTableSerializer(serializers.Serializer):
    """
    Rule Audit Link Table
    """

    uid = serializers.CharField(label=gettext_lazy("UID"))
    version = serializers.IntegerField(label=gettext_lazy("Version"))


class RuleAuditDataSourceSerializer(serializers.Serializer):
    """
    Rule Audit DataSource
    """

    source_type = serializers.ChoiceField(label=gettext_lazy("Source Type"), choices=RuleAuditSourceType.choices)
    rt_id = serializers.CharField(label=gettext_lazy("Result Table ID"), required=False, allow_blank=True)
    system_ids = serializers.ListField(
        label=gettext_lazy("System ID"), child=serializers.CharField(), required=False, allow_empty=True
    )
    link_table = RuleAuditLinkTableSerializer(label=gettext_lazy("Link Table"), required=False, allow_null=True)
    display_name = serializers.CharField(
        label=gettext_lazy("Display Name"), required=False, allow_blank=True, allow_null=True
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        # display_name 默认值为 rt_id
        if attrs.get("rt_id") and not attrs.get("display_name"):
            attrs['display_name'] = attrs['rt_id']
        return attrs


class RuleAuditConditionSerializer(serializers.Serializer):
    """
    Rule Audit Condition
    """

    field = RuleAuditFieldSerializer(label=gettext_lazy("Field"))
    operator = serializers.ChoiceField(label=gettext_lazy("Operator"), choices=RuleAuditConditionOperator.choices)
    filter = serializers.JSONField(
        label="Filter",
        default="",
        help_text=gettext_lazy("单个筛选值，可以是字符串、整数或浮点数"),
    )
    filters = serializers.ListField(
        label="Filters",
        child=serializers.JSONField(),
        default=list,
        help_text=gettext_lazy("多个筛选值，每个值可以是字符串、整数或浮点数"),
        allow_empty=True,
    )


class RuleAuditWhereSerializer(serializers.Serializer):
    """
    Rule Audit Where
    """

    index = serializers.IntegerField(label=gettext_lazy("Index"), required=False, default=0)
    connector = serializers.ChoiceField(
        label=gettext_lazy("Connector"),
        choices=RuleAuditWhereConnector.choices,
        default=RuleAuditWhereConnector.AND.value,
    )
    conditions = serializers.ListField(
        label=gettext_lazy("Conditions"), child=serializers.DictField(), required=False, allow_empty=True
    )
    condition = RuleAuditConditionSerializer(label=gettext_lazy("Condition"), required=False)

    def to_internal_value(self, instance):
        """
        自定义序列化逻辑: 递归解析 conditions
        """

        ret = super().to_internal_value(instance)

        # 递归处理 conditions
        conditions = instance.get('conditions', [])
        ret['conditions'] = [RuleAuditWhereSerializer(condition, context=self.context).data for condition in conditions]

        return ret

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs.get("condition") and attrs.get("conditions"):
            raise serializers.ValidationError(
                gettext("Rule Audit Where can not have condition and conditions at the same time")
            )
        return attrs


class RuleAuditHavingSerializer(RuleAuditWhereSerializer):
    def to_internal_value(self, instance):
        """
        自定义序列化逻辑: 递归解析 conditions
        """

        ret = super().to_representation(instance)

        # 递归处理 conditions
        conditions = instance.get('conditions', [])
        ret['conditions'] = [
            RuleAuditHavingSerializer(condition, context=self.context).data for condition in conditions
        ]

        return ret

    def validate(self, attrs):
        """如果 condition 存在，检查其 field 中的 aggregate"""
        attrs = super().validate(attrs)
        condition = attrs.get("condition", {})
        if condition:
            field = condition.get('field', {})
            if field and 'aggregate' in field and not field['aggregate']:
                raise serializers.ValidationError(gettext("Field in having condition must have aggregate set to True"))
        return attrs


class RuleAuditSerializer(serializers.Serializer):
    """
    Rule Audit
    """

    config_type = serializers.ChoiceField(
        label=gettext_lazy("Rule Audit Config Type"), choices=RuleAuditConfigType.choices
    )
    data_source = RuleAuditDataSourceSerializer(label=gettext_lazy("Rule Audit Data Source"))
    select = serializers.ListField(
        label=gettext_lazy("Rule Audit Select"), child=RuleAuditFieldSerializer(), allow_empty=False
    )
    where = RuleAuditWhereSerializer(label=gettext_lazy("Rule Audit Where"), required=False, allow_null=True)
    having = RuleAuditHavingSerializer(label=gettext_lazy("Rule Audit Having"), required=False, allow_null=True)
    schedule_config = ScheduleConfigSerializer(label=gettext_lazy("Rule Audit Schedule Config"), required=False)

    def _normalize_empty_clause(self, clause: dict | None) -> dict | None:
        # 传了 None 或者空容器 => 直接视为没有 where / having
        if not clause:
            return None

        # 分别取出单条件 / 多条件
        single = clause.get("condition")
        multiple = clause.get("conditions")

        # 如果二者都“空”（None、空 dict、空 list 都算）
        if not single and not multiple:
            return None
        return clause

    def validate(self, attrs):
        attrs = super().validate(attrs)

        attrs["where"] = self._normalize_empty_clause(attrs.get("where"))
        attrs["having"] = self._normalize_empty_clause(attrs.get("having"))

        # 高层校验：确保 config_type 与 data_source 的业务逻辑匹配
        # 1. 日志需要指定 rt_id,system_ids
        # 2. 资产和其他数据需要指定 rt_id
        # 3. 联表需要指定 link_table
        config_type = attrs["config_type"]
        data_source = attrs["data_source"]
        match config_type:
            case RuleAuditConfigType.EVENT_LOG.value:
                if not (data_source.get("rt_id") and data_source.get("system_ids")):
                    raise serializers.ValidationError(
                        gettext("Config type: %s need rt_id and system_ids") % config_type
                    )
            case RuleAuditConfigType.BUILD_ID_ASSET.value | RuleAuditConfigType.BIZ_RT.value:
                if not data_source.get("rt_id"):
                    raise serializers.ValidationError(gettext("Config type: %s need rt_id") % config_type)
            case RuleAuditConfigType.LINK_TABLE.value:
                if not data_source.get("link_table"):
                    raise serializers.ValidationError(gettext("Config type: %s need link_table") % config_type)
        # 校验 schedule_config 和 data_source
        source_type = data_source["source_type"]
        if source_type == RuleAuditSourceType.BATCH and not attrs.get("schedule_config"):
            raise serializers.ValidationError(gettext("Batch rule audit need schedule_config"))
        return attrs


class RuleAuditSourceTypeCheckReqSerializer(serializers.Serializer):
    """
    Rule Audit Source Type Check Req Serializer
    """

    namespace = serializers.CharField(label=gettext_lazy("Namespace"))
    config_type = serializers.ChoiceField(
        label=gettext_lazy("Rule Audit Config Type"), choices=RuleAuditConfigType.choices
    )
    rt_id = serializers.CharField(
        label=gettext_lazy("Result Table ID"), required=False, allow_null=True, allow_blank=True
    )
    link_table = RuleAuditLinkTableSerializer(label=gettext_lazy("Link Table"), required=False, allow_null=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        config_type = attrs["config_type"]
        if config_type != RuleAuditConfigType.LINK_TABLE.value:
            if not attrs.get("rt_id"):
                raise serializers.ValidationError(gettext("Config type: %s need rt_id") % config_type)
        elif not attrs.get("link_table"):
            raise serializers.ValidationError(gettext("Config type: %s need link_table") % config_type)
        return attrs


class RuleAuditSourceTypeCheckRespSerializer(serializers.Serializer):
    support_source_types = serializers.ListField(
        label=gettext_lazy("Support Source Types"),
        child=serializers.ChoiceField(choices=RuleAuditSourceType.choices),
    )


class StrategyRunningStatusListReqSerializer(serializers.Serializer):
    strategy_id = serializers.IntegerField(label=gettext_lazy("Strategy ID"))
    start_time = serializers.DateTimeField(label=gettext_lazy("Start Time"), required=False)
    end_time = serializers.DateTimeField(label=gettext_lazy("End Time"), required=False)
    limit = serializers.IntegerField(label=gettext_lazy("Limit"), default=100)
    offset = serializers.IntegerField(label=gettext_lazy("Offset"), default=0)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if not (attrs.get("start_time") and attrs.get("end_time")):
            end_time = datetime.now()
            start_time = end_time - timedelta(days=STRATEGY_STATUS_DEFAULT_INTERVAL)
            attrs["start_time"] = start_time
            attrs["end_time"] = end_time
        if attrs["end_time"] < attrs["start_time"]:
            raise serializers.ValidationError(gettext("End time must be greater than start time"))
        return attrs


class RunningStatusSerializer(serializers.Serializer):
    schedule_time = serializers.CharField(label=gettext_lazy("调度时间"))
    err_msg = serializers.CharField(label=gettext_lazy("错误信息"), allow_blank=True, allow_null=True)
    status = serializers.CharField(label=gettext_lazy("状态"), allow_blank=True, allow_null=True)
    status_str = serializers.CharField(label=gettext_lazy("状态字符串"), allow_blank=True, allow_null=True)
    risk_count = serializers.IntegerField(label=gettext_lazy("风险数量"))
    data_time = serializers.CharField(label=gettext_lazy("数据时间"))


class StrategyRunningStatusListRespSerializer(serializers.Serializer):
    strategy_running_status = RunningStatusSerializer(many=True)


# ============== 报告相关序列化器 ==============


class RetrieveStrategyRequestSerializer(serializers.Serializer):
    """
    获取策略详情请求序列化器
    """

    strategy_id = serializers.IntegerField(label=gettext_lazy("策略ID"))


class PreviewReportRequestSerializer(serializers.Serializer):
    """
    报告预览请求序列化器
    """

    risk_id = serializers.CharField(label=gettext_lazy("风险ID"))
    report_config = ReportConfigSerializer()


class PreviewReportResponseSerializer(serializers.Serializer):
    """
    报告预览响应序列化器
    """

    task_id = serializers.CharField(label=gettext_lazy("任务ID"))
    status = serializers.CharField(label=gettext_lazy("任务状态"))


class RiskVariableResponseSerializer(serializers.Serializer):
    """
    风险变量响应序列化器
    """

    field = serializers.CharField(label=gettext_lazy("字段名"))
    name = serializers.CharField(label=gettext_lazy("字段显示名"))
    description = serializers.CharField(label=gettext_lazy("字段描述"), allow_blank=True)


class AggregationFunctionResponseSerializer(serializers.Serializer):
    """
    聚合函数响应序列化器
    """

    id = serializers.CharField(label=gettext_lazy("聚合函数标识"))
    name = serializers.CharField(label=gettext_lazy("聚合函数显示名"))
    supported_field_types = serializers.ListField(label=gettext_lazy("支持的字段类型"), child=serializers.CharField())
