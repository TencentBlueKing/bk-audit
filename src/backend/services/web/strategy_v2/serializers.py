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
from typing import List

from django.utils.translation import gettext, gettext_lazy
from rest_framework import serializers

from apps.meta.constants import OrderTypeChoices
from services.web.analyze.constants import (
    FilterConnector,
    FilterOperator,
    FlowDataSourceNodeType,
    OffsetUnit,
)
from services.web.analyze.models import ControlVersion
from services.web.strategy_v2.constants import (
    BKMONITOR_AGG_INTERVAL_MIN,
    STRATEGY_SCHEDULE_TIME,
    ConnectorChoices,
    RiskLevel,
    StrategyAlgorithmOperator,
    StrategyOperator,
    TableType,
)
from services.web.strategy_v2.exceptions import SchedulePeriodInvalid
from services.web.strategy_v2.models import Strategy


class EventFieldSerializer(serializers.Serializer):
    field_name = serializers.CharField(label=gettext_lazy("Field Name"))
    display_name = serializers.CharField(label=gettext_lazy("Field Display Name"))
    is_priority = serializers.BooleanField(label=gettext_lazy("Is Priority"))
    description = serializers.CharField(label=gettext_lazy("Field Description"))


class CreateStrategyRequestSerializer(serializers.ModelSerializer):
    """
    Create Strategy
    """

    tags = serializers.ListField(
        label=gettext_lazy("Tags"), child=serializers.CharField(label=gettext_lazy("Tag Name")), default=list
    )
    event_basic_field_configs = serializers.ListField(
        label=gettext_lazy("Event Basic Field Configs"), child=EventFieldSerializer(), default=list, allow_empty=True
    )
    event_data_field_configs = serializers.ListField(
        label=gettext_lazy("Event Data Field Configs"), child=EventFieldSerializer(), default=list, allow_empty=True
    )
    event_evidence_field_configs = serializers.ListField(
        label=gettext_lazy("Event Evidence Field Configs"), child=EventFieldSerializer(), default=list, allow_empty=True
    )
    risk_level = serializers.ChoiceField(label=gettext_lazy("Risk Level"), choices=RiskLevel.choices)
    risk_title = serializers.CharField(label=gettext_lazy("Risk Title"))
    processor_groups = serializers.ListField(
        label=gettext_lazy("Processor Groups"),
        child=serializers.IntegerField(label=gettext_lazy("Processor Group")),
        allow_empty=False,
    )

    class Meta:
        model = Strategy
        fields = [
            "namespace",
            "strategy_name",
            "control_id",
            "control_version",
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
        ]

    def validate(self, attrs: dict) -> dict:
        data = super().validate(attrs)
        # check control
        if not ControlVersion.objects.filter(
            control_id=data["control_id"], control_version=data["control_version"]
        ).exists():
            raise serializers.ValidationError(gettext("Control Version not Exists"))
        # check name
        if Strategy.objects.filter(strategy_name=attrs["strategy_name"]).exists():
            raise serializers.ValidationError(gettext("Strategy Name Duplicate"))
        # return
        return data


class CreateStrategyResponseSerializer(serializers.ModelSerializer):
    """
    Create Strategy
    """

    class Meta:
        model = Strategy
        fields = ["strategy_id", "strategy_name"]


class UpdateStrategyRequestSerializer(serializers.ModelSerializer):
    """
    Update Strategy
    """

    tags = serializers.ListField(
        label=gettext_lazy("Tags"), child=serializers.CharField(label=gettext_lazy("Tag Name")), default=list
    )
    strategy_id = serializers.IntegerField(label=gettext_lazy("Strategy ID"))
    event_basic_field_configs = serializers.ListField(
        label=gettext_lazy("Event Basic Field Configs"), child=EventFieldSerializer(), default=list, allow_empty=True
    )
    event_data_field_configs = serializers.ListField(
        label=gettext_lazy("Event Data Field Configs"), child=EventFieldSerializer(), default=list, allow_empty=True
    )
    event_evidence_field_configs = serializers.ListField(
        label=gettext_lazy("Event Evidence Field Configs"), child=EventFieldSerializer(), default=list, allow_empty=True
    )
    risk_title = serializers.CharField(label=gettext_lazy("Risk Title"))
    processor_groups = serializers.ListField(
        label=gettext_lazy("Processor Groups"),
        child=serializers.IntegerField(label=gettext_lazy("Processor Group")),
        allow_empty=False,
    )
    risk_level = serializers.ChoiceField(label=gettext_lazy("Risk Level"), choices=RiskLevel.choices)

    class Meta:
        model = Strategy
        # 若有可变化的字段变更，需要同步修改本地更新的字段列表 LOCAL_UPDATE_FIELDS
        fields = [
            "strategy_id",
            "strategy_name",
            "control_id",
            "control_version",
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
        ]

    def validate(self, attrs: dict) -> dict:
        data = super().validate(attrs)
        # check control
        if not ControlVersion.objects.filter(
            control_id=data["control_id"], control_version=data["control_version"]
        ).exists():
            raise serializers.ValidationError(gettext("Control Version not Exists"))
        # check name
        if (
            Strategy.objects.filter(strategy_name=attrs["strategy_name"])
            .exclude(strategy_id=attrs["strategy_id"])
            .exists()
        ):
            raise serializers.ValidationError(gettext("Strategy Name Duplicate"))
        # return
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
        label=gettext_lazy("排序方式"), required=False, allow_null=True, allow_blank=True, choices=OrderTypeChoices.choices
    )

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


class ListStrategyResponseSerializer(serializers.ModelSerializer):
    """
    List Strategy
    """

    tags = serializers.ListField(
        label=gettext_lazy("Tags"), child=serializers.IntegerField(label=gettext_lazy("Tag ID"))
    )

    class Meta:
        model = Strategy
        exclude = ["backend_data"]


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
            "notice_groups",
            "risk_level",
            "risk_hazard",
            "risk_guidance",
            "risk_title",
            "processor_groups",
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


class ChoiceListSerializer(serializers.Serializer):
    """
    Choice List
    """

    label = serializers.CharField(label=gettext_lazy("Label"), allow_blank=True, allow_null=True)
    value = serializers.CharField(label=gettext_lazy("Value"))
    config = serializers.JSONField(label=gettext_lazy("Config"), required=False)


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


class AIOPSSceneConfigSerializer(serializers.Serializer):
    """
    AIOPS Scene Config
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

    table_type = serializers.ChoiceField(label=gettext_lazy("Table Type"), choices=TableType.choices)
    namespace = serializers.CharField(label=gettext_lazy("Namespace"), required=False)


class GetRTFieldsRequestSerializer(serializers.Serializer):
    """
    Get RT Fields
    """

    table_id = serializers.CharField(label=gettext_lazy("Table ID"))


class GetRTFieldsResponseSerializer(serializers.Serializer):
    """
    Get RT Fields
    """

    label = serializers.CharField(label=gettext_lazy("Label"))
    value = serializers.CharField(label=gettext_lazy("value"))
    field_type = serializers.CharField(label=gettext_lazy("Field Type"))


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
    example = serializers.CharField(label=gettext_lazy("Example"), allow_blank=True)


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


class GetStrategyDisplayInfoRequestSerializer(serializers.Serializer):
    strategy_ids = serializers.CharField(label=gettext_lazy("Strategy IDs"))

    def validate_strategy_ids(self, strategy_ids: str) -> List[int]:
        try:
            return [int(s) for s in strategy_ids.split(",") if s]
        except ValueError:
            raise serializers.ValidationError(gettext("Strategy ID Invalid"))
