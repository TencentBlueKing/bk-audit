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

from services.web.tool.constants import PermissionTypeEnum, Tool, ToolTypeEnum


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
        else:
            raise serializers.ValidationError(f"不支持的工具类型: {tool_type}")

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
    auth_type = serializers.CharField()
    auth_users = serializers.ListField(child=serializers.CharField(), required=False)
    config = serializers.DictField()
    panel = serializers.DictField(required=False, allow_null=True)


class ToolListRequestSerializer(serializers.Serializer):
    keyword = serializers.CharField(required=False, allow_blank=True, help_text="搜索关键词：名称、描述、创建人")
    filter_by = serializers.ChoiceField(
        choices=[("all", "全部"), ("mine", "我创建的")],
        required=False,
        default="all",
        help_text="过滤方式：全部 / 我创建的",
    )
    sort = serializers.ChoiceField(
        choices=[("updated", "更新时间"), ("latest_used", "最近使用")],
        required=False,
        default="updated",
        help_text="排序方式：更新时间 / 最近使用",
    )


class ToolListResponseSerializer(serializers.ModelSerializer):
    tool_type = serializers.ChoiceField(choices=ToolTypeEnum.choices, help_text="工具类型")
    auth_type = serializers.ChoiceField(choices=PermissionTypeEnum.choices, help_text="权限类型")
    creator = serializers.SerializerMethodField()
    latest_used_time = serializers.DateTimeField(required=False, allow_null=True, help_text="最近使用时间")

    class Meta:
        model = Tool
        fields = [
            "uid",
            "name",
            "namespace",
            "version",
            "description",
            "tool_type",
            "auth_type",
            "creator",
            "updated_at",
            "latest_used_time",
        ]

    def get_creator(self, obj):
        return obj.created_by
