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
from typing import Annotated, Optional

from django.utils.translation import gettext_lazy
from pydantic import Field as PydanticField
from rest_framework import serializers
from rest_framework.fields import DictField

from core.sql.model import Table as RawTable
from core.sql.parser.model import SelectField, SqlVariable
from services.web.tool.constants import (
    BkVisionConfig,
    DataSearchConfigTypeEnum,
    SQLDataSearchConfig,
    ToolTypeEnum,
)
from services.web.tool.models import Tool


class ListToolTagsResponseSerializer(serializers.Serializer):
    """
    List Tool Tags
    """

    tag_id = serializers.CharField(label=gettext_lazy("Tag ID"))
    tag_name = serializers.CharField(label=gettext_lazy("Tag Name"))
    tool_count = serializers.IntegerField(label=gettext_lazy("Tool Count"), required=False)


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
    data_search_config_type = serializers.ChoiceField(
        choices=DataSearchConfigTypeEnum.choices,
        required=False,
        label=gettext_lazy("数据查询配置类型"),
        help_text=gettext_lazy("仅在 tool_type=data_search 时必须，支持 simple/sql"),
    )

    def validate(self, attrs):
        tool_type = attrs["tool_type"]
        config = attrs["config"]
        if tool_type == ToolTypeEnum.DATA_SEARCH:
            data_search_config_type = attrs["data_search_config_type"]

        if tool_type == ToolTypeEnum.BK_VISION:
            validated_config = BkVisionConfig(**config).model_dump()
        elif tool_type == ToolTypeEnum.DATA_SEARCH:
            DataSearchConfigTypeEnum(data_search_config_type)
            validated_config = SQLDataSearchConfig(**config).model_dump()
        else:
            raise serializers.ValidationError({"tool_type": f"不支持的工具类型: {tool_type}"})
        attrs["config"] = validated_config
        return attrs


class ToolUpdateRequestSerializer(serializers.Serializer):
    uid = serializers.CharField(label=gettext_lazy("工具 UID"))
    config = serializers.DictField(required=False, label=gettext_lazy("工具配置"))
    name = serializers.CharField(required=False, label=gettext_lazy("工具名称"))
    namespace = serializers.CharField(required=False, label=gettext_lazy("命名空间"))
    description = serializers.CharField(required=False, allow_blank=True, label=gettext_lazy("工具描述"))
    tags = serializers.ListField(
        child=serializers.CharField(), required=True, allow_empty=True, label=gettext_lazy("标签列表")
    )

    def validate(self, attrs):
        uid = attrs["uid"]
        config = attrs.get("config")

        tool = Tool.last_version_tool(uid)
        tool_type = tool.tool_type

        if tool_type == ToolTypeEnum.BK_VISION:
            validated_config = BkVisionConfig(**config).model_dump()
        elif tool_type == ToolTypeEnum.DATA_SEARCH:
            validated_config = SQLDataSearchConfig(**config).model_dump()
        else:
            raise serializers.ValidationError({"uid": f"不支持的工具类型: {tool_type}"})

        attrs["config"] = validated_config
        return attrs


class ToolResponseSerializer(serializers.Serializer):
    uid = serializers.CharField(label=gettext_lazy("工具 UID"))
    version = serializers.IntegerField(label=gettext_lazy("工具版本"))


class ToolDeleteRetrieveRequestSerializer(serializers.Serializer):
    uid = serializers.CharField(label=gettext_lazy("工具 UID"))


class ToolListAllResponseSerializer(serializers.Serializer):
    uid = serializers.CharField(label=gettext_lazy("工具 UID"))
    name = serializers.CharField(label=gettext_lazy("工具名称"))
    description = serializers.CharField(allow_blank=True, label=gettext_lazy("工具描述"))
    tool_type = serializers.ChoiceField(choices=ToolTypeEnum.choices, label=gettext_lazy("工具类型"))
    version = serializers.IntegerField(label=gettext_lazy("工具版本"))
    namespace = serializers.CharField(allow_blank=True, label=gettext_lazy("命名空间"))
    permission = serializers.DictField(required=False, label=gettext_lazy("权限信息"))
    tags = serializers.ListField(child=serializers.CharField(), label=gettext_lazy("标签列表"))
    strategies = serializers.ListField(child=serializers.IntegerField(), label="关联策略")


class ToolListResponseSerializer(serializers.Serializer):
    uid = serializers.CharField(label=gettext_lazy("工具 UID"))
    name = serializers.CharField(label=gettext_lazy("工具名称"))
    tool_type = serializers.ChoiceField(choices=ToolTypeEnum.choices, label=gettext_lazy("工具类型"))
    version = serializers.IntegerField(label=gettext_lazy("工具版本"))
    description = serializers.CharField(allow_blank=True, label=gettext_lazy("工具描述"))
    namespace = serializers.CharField(allow_blank=True, label=gettext_lazy("命名空间"))
    created_by = serializers.CharField(label=gettext_lazy("创建人"))
    created_at = serializers.DateTimeField(label=gettext_lazy("创建时间"))
    tags = serializers.ListField(child=serializers.CharField(), label=gettext_lazy("标签列表"))
    permission = serializers.DictField(required=False, label=gettext_lazy("权限信息"))
    strategies = serializers.ListField(child=serializers.IntegerField(), label="关联策略")


class ToolRetrieveResponseSerializer(serializers.Serializer):
    uid = serializers.CharField(label=gettext_lazy("工具 UID"))
    name = serializers.CharField(label=gettext_lazy("工具名称"))
    tool_type = serializers.ChoiceField(choices=ToolTypeEnum.choices, label=gettext_lazy("工具类型"))
    version = serializers.IntegerField(label=gettext_lazy("工具版本"))
    description = serializers.CharField(allow_blank=True, label=gettext_lazy("工具描述"))
    namespace = serializers.CharField(allow_blank=True, label=gettext_lazy("命名空间"))
    created_by = serializers.CharField(label=gettext_lazy("创建人"))
    created_at = serializers.DateTimeField(label=gettext_lazy("创建时间"))
    updated_by = serializers.CharField(label=gettext_lazy("更新人"))
    updated_at = serializers.DateTimeField(label=gettext_lazy("更新时间"))
    permission = serializers.DictField(required=False, label=gettext_lazy("权限信息"))
    strategies = serializers.ListField(child=serializers.IntegerField(), label="关联策略")
    config = serializers.DictField(label=gettext_lazy("工具配置"))
    tags = serializers.ListField(child=serializers.CharField(), label=gettext_lazy("标签列表"))
    data_search_config_type = serializers.SerializerMethodField()

    def get_data_search_config_type(self, obj):
        if hasattr(obj, "data_search_config") and obj.data_search_config:
            return obj.data_search_config.data_search_config_type
        return None


class ListRequestSerializer(serializers.Serializer):
    keyword = serializers.CharField(required=False, allow_blank=True, label="搜索关键字")
    tags = serializers.ListField(
        child=serializers.IntegerField(), required=False, allow_empty=True, label="标签ID列表", default=[]
    )
    my_created = serializers.BooleanField(required=False, default=False, label="是否筛选我创建的")
    recent_used = serializers.BooleanField(required=False, default=False, label="是否筛选最近使用")


class SqlAnalyseRequestSerializer(serializers.Serializer):
    """SQL 分析请求参数"""

    sql = serializers.CharField(label=gettext_lazy("SQL"))
    dialect = serializers.CharField(required=False, allow_blank=True, allow_null=True, default='hive')
    with_permission = serializers.BooleanField(required=False, default=False)


class Table(RawTable):
    """
    带业务逻辑的表
    """

    permission: Annotated[Optional[dict], DictField(allow_empty=True, allow_null=True, default=dict)] = PydanticField(
        default_factory=dict, description="权限信息"
    )


class SqlAnalyseResponseSerializer(serializers.Serializer):
    referenced_tables = Table.drf_serializer(many=True)
    sql_variables = SqlVariable.drf_serializer(many=True)
    result_fields = SelectField.drf_serializer(many=True)
    original_sql = serializers.CharField()
    dialect = serializers.CharField(allow_null=True, required=False)


class ExecuteToolReqSerializer(serializers.Serializer):
    uid = serializers.CharField()
    params = serializers.JSONField()


class ExecuteToolRespSerializer(serializers.Serializer):
    data = serializers.DictField()
    tool_type = serializers.ChoiceField(choices=ToolTypeEnum.choices)


class UserQueryTableAuthCheckReqSerializer(serializers.Serializer):
    tables = serializers.ListField(label=gettext_lazy("表名列表"), child=serializers.CharField())


class UserQueryTableAuthCheckRespSerializer(serializers.Serializer):
    has_auth = serializers.BooleanField()
