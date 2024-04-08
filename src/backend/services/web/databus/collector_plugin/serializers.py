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

from django.utils.translation import gettext_lazy
from rest_framework import serializers

from services.web.databus.constants import (
    PLUGIN_CONDITION_SEPARATOR_OPTION,
    CollectorParamConditionMatchType,
    CollectorParamConditionTypeEnum,
    EtlConfigEnum,
    PluginSceneChoices,
)
from services.web.databus.models import CollectorPlugin


class PluginConditionSeparatorFiltersSerializer(serializers.Serializer):
    op = serializers.CharField(label=gettext_lazy("匹配方式"), default=PLUGIN_CONDITION_SEPARATOR_OPTION)
    logic_op = serializers.CharField(label=gettext_lazy("逻辑操作符"))
    fieldindex = serializers.CharField(label=gettext_lazy("匹配项所在列"))
    word = serializers.CharField(label=gettext_lazy("匹配值"))


class PluginConditionSerializer(serializers.Serializer):
    """
    插件过滤方式序列化
    """

    type = serializers.ChoiceField(label=gettext_lazy("过滤方式类型"), choices=CollectorParamConditionTypeEnum.choices)
    match_type = serializers.ChoiceField(
        label=gettext_lazy("过滤方式"),
        required=False,
        allow_blank=False,
        allow_null=False,
        choices=CollectorParamConditionMatchType.choices,
    )
    match_content = serializers.CharField(
        label=gettext_lazy("过滤内容"), max_length=255, required=False, allow_null=True, allow_blank=True
    )
    separator = serializers.CharField(
        label=gettext_lazy("分隔符"), trim_whitespace=False, required=False, allow_null=True, allow_blank=True
    )
    separator_filters = PluginConditionSeparatorFiltersSerializer(label=gettext_lazy("过滤规则"), required=False, many=True)

    def validate(self, attrs: dict) -> dict:
        condition_type = attrs.get("type")
        if condition_type == CollectorParamConditionTypeEnum.NONE:
            return {"type": CollectorParamConditionTypeEnum.NONE}
        if condition_type != CollectorParamConditionTypeEnum.SEPARATOR:
            attrs.pop("separator_filters", None)
            attrs.pop("separator", None)
        if condition_type != CollectorParamConditionTypeEnum.MATCH:
            attrs.pop("match_type", None)
            attrs.pop("match_content", None)
        return super().validate(attrs)


class PluginParamSerializer(serializers.Serializer):
    """
    插件参数序列化
    """

    paths = serializers.ListField(
        label=gettext_lazy("日志路径"), child=serializers.CharField(max_length=255), required=False
    )
    conditions = PluginConditionSerializer(required=False)


class PluginBaseSerializer(serializers.Serializer):
    namespace = serializers.CharField(label=gettext_lazy("命名空间"))
    etl_config = serializers.CharField(label=gettext_lazy("清洗配置"), default=EtlConfigEnum.BK_LOG_JSON.value)
    etl_params = serializers.JSONField(label=gettext_lazy("清洗参数"), allow_null=True, default=dict)
    is_default = serializers.BooleanField(label=gettext_lazy("作为默认插件"), default=False)
    extra_fields = serializers.ListField(
        label=gettext_lazy("拓展字段"), allow_null=True, required=False, child=serializers.JSONField()
    )

    def validate_etl_params(self, value: dict):
        value = value or dict()
        value["retain_original_text"] = True
        return value


class CreatePluginRequestSerializer(PluginBaseSerializer):
    plugin_scene = serializers.ChoiceField(
        label=gettext_lazy("插件场景"), choices=PluginSceneChoices.choices, default=PluginSceneChoices.COLLECTOR
    )


class UpdatePluginRequestSerializer(CreatePluginRequestSerializer):
    collector_plugin_id = serializers.IntegerField(label=gettext_lazy("采集插件ID"))


class CreatePluginResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = CollectorPlugin
        fields = ["collector_plugin_id", "collector_plugin_name"]


class PluginListResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = CollectorPlugin
        fields = "__all__"
