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

from services.web.tool.constants import ToolTypeEnum
from services.web.tool.models import BkvisionToolConfig


class ToolCreateRequestSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=ToolTypeEnum.choices, label=gettext_lazy("工具类型"))
    config = serializers.DictField(label=gettext_lazy("工具配置"))
    name = serializers.CharField(label=gettext_lazy("工具名称"))
    description = serializers.CharField(allow_blank=True, required=False, label=gettext_lazy("工具描述"))
    namespace = serializers.CharField(label=gettext_lazy("命名空间"))

    def validate(self, attrs):
        tool_type = attrs["type"]
        config = attrs["config"]

        # 分发验证
        if tool_type == ToolTypeEnum.BK_VISION.value:
            self._validate_bkvision_config(config)
        elif tool_type == ToolTypeEnum.DATA_SEARCH.value:
            self._validate_sql_config(config)
        else:
            raise serializers.ValidationError({"type": f"不支持的工具类型: {tool_type}"})

        return attrs

    def _validate_bkvision_config(self, config):
        if not config.get("uid"):
            raise serializers.ValidationError({"config": "BK Vision 工具 config 缺少必填字段 uid"})

    def _validate_sql_config(self, config):
        required_keys = ["sql", "input_variable", "output_fields"]
        for key in required_keys:
            if key not in config:
                raise serializers.ValidationError({"config": f"SQL 工具 config 缺少必填字段：{key}"})


class ToolUpdateRequestSerializer(ToolCreateRequestSerializer):
    uid = serializers.CharField(required=True, label=gettext_lazy("工具 UID"))


class ToolResponseSerializer(serializers.Serializer):
    uid = serializers.CharField(label=gettext_lazy("工具 UID"))
    version = serializers.IntegerField(label=gettext_lazy("工具版本"))


class ToolDeleteRetrieveRequestSerializer(serializers.Serializer):
    uid = serializers.CharField(label=gettext_lazy("工具 UID"))


class TooListAllRetrieveResponseSerializer(serializers.Serializer):
    uid = serializers.CharField()
    name = serializers.CharField()
    type = serializers.ChoiceField(choices=ToolTypeEnum.choices, source="tool_type")
    version = serializers.IntegerField()
    description = serializers.CharField(allow_blank=True)
    namespace = serializers.CharField(allow_blank=True)
    config = serializers.DictField()
    panel = serializers.SerializerMethodField()

    def get_panel(self, obj):
        try:
            panel_config = BkvisionToolConfig.objects.select_related("panel").get(tool=obj)
            panel = panel_config.panel
            return {
                "vision_id": panel.vision_id,
                "name": panel.name,
                "handler": panel.handler,
                "scenario": panel.scenario,
                "priority_index": panel.priority_index,
            }
        except BkvisionToolConfig.DoesNotExist:
            return None

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # 如果不是 bk_vision，就移除 panel 字段
        if instance.tool_type != ToolTypeEnum.BK_VISION:
            rep.pop("panel", None)
        return rep
