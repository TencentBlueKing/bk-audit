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

from rest_framework import serializers

from services.web.tool.constants import ToolTypeEnum


class ToolCreateRequestSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=ToolTypeEnum.choices)
    config = serializers.DictField()

    def validate(self, attrs):
        tool_type = attrs["type"]
        config = attrs["config"]

        if tool_type == ToolTypeEnum.DATA_SEARCH:
            required_keys = ["sql", "input_variable", "output_fields"]
            for key in required_keys:
                if key not in config:
                    raise serializers.ValidationError(f"SQL 工具 config 缺少必填字段：{key}")
        elif tool_type == ToolTypeEnum.BK_VISION:
            if "uid" not in config:
                raise serializers.ValidationError({"config": "BKVision 工具 config 缺少必填字段：uid"})

        return attrs


class ToolUpdateRequestSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=ToolTypeEnum.choices)
    config = serializers.DictField()

    def validate(self, attrs):
        tool_type = attrs["type"]
        config = attrs["config"]

        if "uid" not in config:
            raise serializers.ValidationError({"config": "config 中必须包含 uid 字段"})

        if tool_type == ToolTypeEnum.DATA_SEARCH:
            required_keys = ["sql", "input_variable", "output_fields"]
            for key in required_keys:
                if key not in config:
                    raise serializers.ValidationError(f"SQL 工具 config 缺少必填字段：{key}")
        elif tool_type == ToolTypeEnum.BK_VISION:
            if "uid" not in config:
                raise serializers.ValidationError({"config": "BKVision 工具 config 缺少必填字段：uid"})

        return attrs


class ToolResponseSerializer(serializers.Serializer):
    uid = serializers.CharField()
    version = serializers.IntegerField()


class ToolDeleteRetrieveRequestSerializer(serializers.Serializer):
    uid = serializers.CharField()


class ToolRetrieveResponseSerializer(serializers.Serializer):
    uid = serializers.CharField()
    name = serializers.CharField()
    type = serializers.ChoiceField(choices=ToolTypeEnum.choices)
    version = serializers.IntegerField()
    description = serializers.CharField(allow_blank=True)
    namespace = serializers.CharField(allow_blank=True)
    config = serializers.DictField()
    panel = serializers.DictField(required=False, allow_null=True)


class ToolListResponseSerializer(serializers.Serializer):
    uid = serializers.CharField()
    name = serializers.CharField()
    type = serializers.ChoiceField(choices=ToolTypeEnum.choices, source="tool_type")
    version = serializers.IntegerField()
    description = serializers.CharField()
    namespace = serializers.CharField()
    updated_at = serializers.DateTimeField()
    created_by = serializers.CharField()
    permission = serializers.DictField(required=False)
