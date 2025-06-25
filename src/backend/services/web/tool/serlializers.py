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

from services.web.tool.constants import (
    BkvisionConfig,
    SQLDataSearchConfig,
    ToolTypeEnum,
)
from services.web.tool.models import Tool


class ToolCreateRequestSerializer(serializers.Serializer):
    tool_type = serializers.ChoiceField(choices=ToolTypeEnum.choices, label=gettext_lazy("工具类型"))
    config = serializers.DictField(label=gettext_lazy("工具配置"))
    name = serializers.CharField(label=gettext_lazy("工具名称"))
    description = serializers.CharField(required=False, allow_blank=True, label=gettext_lazy("工具描述"))
    namespace = serializers.CharField(label=gettext_lazy("命名空间"))
    version = serializers.IntegerField(default=1, label=gettext_lazy("版本"))
    tags = serializers.ListField(
        child=serializers.CharField(), required=False, allow_empty=True, label=gettext_lazy("标签列表"), default=[]
    )

    def validate(self, attrs):
        tool_type = attrs["tool_type"]
        config = attrs["config"]

        if tool_type == ToolTypeEnum.BK_VISION:
            BkvisionConfig(**config)
        elif tool_type == ToolTypeEnum.DATA_SEARCH:
            SQLDataSearchConfig(**config)
        else:
            raise serializers.ValidationError({"tool_type": f"不支持的工具类型: {tool_type}"})

        return attrs


class ToolUpdateRequestSerializer(serializers.Serializer):
    uid = serializers.CharField(label=gettext_lazy("工具 UID"))
    config = serializers.DictField(label=gettext_lazy("工具配置"))
    name = serializers.CharField(label=gettext_lazy("工具名称"))
    description = serializers.CharField(required=False, allow_blank=True, label=gettext_lazy("工具描述"))
    tags = serializers.ListField(
        child=serializers.CharField(), required=True, allow_empty=True, label=gettext_lazy("标签列表")
    )

    def validate(self, attrs):

        uid = attrs["uid"]
        config = attrs["config"]

        tool = Tool.last_version_tool(uid)
        tool_type = tool.tool_type

        if tool_type == ToolTypeEnum.BK_VISION:
            BkvisionConfig(**config)
        elif tool_type == ToolTypeEnum.DATA_SEARCH:
            SQLDataSearchConfig(**config)
        else:
            raise serializers.ValidationError({"uid": f"不支持的工具类型: {tool_type}"})
        return attrs


class ToolResponseSerializer(serializers.Serializer):
    uid = serializers.CharField(label=gettext_lazy("工具 UID"))
    version = serializers.IntegerField(label=gettext_lazy("工具版本"))


class ToolDeleteRetrieveRequestSerializer(serializers.Serializer):
    uid = serializers.CharField(label=gettext_lazy("工具 UID"))


class ToolListAllResponseSerializer(serializers.Serializer):
    uid = serializers.CharField(label=gettext_lazy("工具 UID"))
    name = serializers.CharField(label=gettext_lazy("工具名称"))
    tool_type = serializers.ChoiceField(choices=ToolTypeEnum.choices, label=gettext_lazy("工具类型"))
    version = serializers.IntegerField(label=gettext_lazy("工具版本"))
    namespace = serializers.CharField(allow_blank=True, label=gettext_lazy("命名空间"))
    permission = serializers.DictField(required=False, label=gettext_lazy("权限信息"))


class ToolListResponseSerializer(serializers.Serializer):
    uid = serializers.CharField(label=gettext_lazy("工具 UID"))
    name = serializers.CharField(label=gettext_lazy("工具名称"))
    tool_type = serializers.ChoiceField(choices=ToolTypeEnum.choices, label=gettext_lazy("工具类型"))
    version = serializers.IntegerField(label=gettext_lazy("工具版本"))
    description = serializers.CharField(allow_blank=True, label=gettext_lazy("工具描述"))
    namespace = serializers.CharField(allow_blank=True, label=gettext_lazy("命名空间"))
    config = serializers.DictField(label=gettext_lazy("工具配置"))
    permission = serializers.DictField(required=False, label=gettext_lazy("权限信息"))


class ToolRetrieveResponseSerializer(serializers.Serializer):
    uid = serializers.CharField(label=gettext_lazy("工具 UID"))
    name = serializers.CharField(label=gettext_lazy("工具名称"))
    tool_type = serializers.ChoiceField(choices=ToolTypeEnum.choices, label=gettext_lazy("工具类型"))
    version = serializers.IntegerField(label=gettext_lazy("工具版本"))
    description = serializers.CharField(allow_blank=True, label=gettext_lazy("工具描述"))
    namespace = serializers.CharField(allow_blank=True, label=gettext_lazy("命名空间"))
    config = serializers.DictField(label=gettext_lazy("工具配置"))


class ListRequestSerializer(serializers.Serializer):
    keyword = serializers.CharField(required=False, allow_blank=True, label="搜索关键字")
    limit = serializers.IntegerField(required=False, min_value=1, default=10, label="每页条数")
    offset = serializers.IntegerField(required=False, min_value=0, default=0, label="偏移量")
    tags = serializers.ListField(
        child=serializers.IntegerField(), required=False, allow_empty=True, label="标签ID列表", default=[]
    )


class ListToolTagsResponseSerializer(serializers.Serializer):
    """
    List Tool Tags
    """

    tag_id = serializers.CharField(label=gettext_lazy("Tag ID"))
    tag_name = serializers.CharField(label=gettext_lazy("Tag Name"))
    tool_count = serializers.IntegerField(label=gettext_lazy("Tool Count"))
