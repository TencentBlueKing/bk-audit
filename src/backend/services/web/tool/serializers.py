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
from drf_spectacular.utils import PolymorphicProxySerializer, extend_schema_field
from pydantic import Field as PydanticField
from rest_framework import serializers
from rest_framework.fields import DictField

from core.sql.model import Table as RawTable
from core.sql.parser.model import SelectField, SqlVariable
from services.web.common.caller_permission import CALLER_RESOURCE_TYPE_CHOICES
from services.web.tool.constants import (
    ApiToolConfig,
    BkVisionConfig,
    DataSearchConfigTypeEnum,
    SQLDataSearchConfig,
    ToolTypeEnum,
)
from services.web.tool.executor.model import (
    APIToolExecuteParams,
    ApiToolExecuteResult,
    BkVisionExecuteResult,
    DataSearchToolExecuteParams,
    DataSearchToolExecuteResult,
)
from services.web.tool.models import Tool


class ListToolTagsResponseSerializer(serializers.Serializer):
    """
    List Tool Tags
    """

    tag_id = serializers.CharField(label=gettext_lazy("Tag ID"))
    tag_name = serializers.CharField(label=gettext_lazy("Tag Name"))
    tool_count = serializers.IntegerField(label=gettext_lazy("Tool Count"), required=False)


# 针对 config 字段的多态 Schema 定义
@extend_schema_field(
    PolymorphicProxySerializer(
        component_name='ToolConfigPoly',
        serializers={
            'data_search': SQLDataSearchConfig,
            'api': ApiToolConfig,
            'bk_vision': BkVisionConfig,
        },
        resource_type_field_name='tool_type',
    )
)
class ToolConfigField(serializers.DictField):
    """
    自定义字段，用于支持多态文档生成
    """

    pass


# 针对 params 字段的多态 Schema 定义
@extend_schema_field(
    PolymorphicProxySerializer(
        component_name='ToolParamsPoly',
        serializers=[
            APIToolExecuteParams,
            DataSearchToolExecuteParams,
        ],
        resource_type_field_name=None,
    )
)
class ToolParamsField(serializers.DictField):
    """
    自定义字段，用于支持多态文档生成
    """


@extend_schema_field(
    PolymorphicProxySerializer(
        component_name='ToolResultPoly',
        serializers=[
            DataSearchToolExecuteResult,
            ApiToolExecuteResult,
            BkVisionExecuteResult,
        ],
        resource_type_field_name=None,
    )
)
class ToolResultField(serializers.DictField):
    """
    自定义字段，用于支持多态执行结果文档
    """

    pass


class ToolCreateRequestSerializer(serializers.Serializer):
    tool_type = serializers.ChoiceField(choices=ToolTypeEnum.choices, label=gettext_lazy("工具类型"))
    config = ToolConfigField(label=gettext_lazy("工具配置"), help_text=gettext_lazy("根据工具类型，配置结构不同"))
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
    updated_time = serializers.DateTimeField(required=False, label="更新时间", format="%Y-%m-%d %H:%M:%S", allow_null=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        tool_type = attrs["tool_type"]
        config = attrs["config"]
        if tool_type == ToolTypeEnum.DATA_SEARCH and "data_search_config_type" not in attrs:
            raise serializers.ValidationError({"data_search_config_type": gettext_lazy("数据查询配置类型不能为空")})

        if tool_type == ToolTypeEnum.BK_VISION:
            validated_config = BkVisionConfig.model_validate(config).model_dump()
        elif tool_type == ToolTypeEnum.DATA_SEARCH:
            validated_config = SQLDataSearchConfig.model_validate(config).model_dump()
        elif tool_type == ToolTypeEnum.API:
            validated_config = ApiToolConfig.model_validate(config).model_dump()
        else:
            raise serializers.ValidationError({"tool_type": f"不支持的工具类型: {tool_type}"})
        attrs["config"] = validated_config
        return attrs


class ToolUpdateRequestSerializer(serializers.Serializer):
    uid = serializers.CharField(label=gettext_lazy("工具 UID"))
    config = ToolConfigField(required=False, label=gettext_lazy("工具配置"), help_text=gettext_lazy("根据工具类型，配置结构不同"))
    name = serializers.CharField(required=False, label=gettext_lazy("工具名称"))
    namespace = serializers.CharField(required=False, label=gettext_lazy("命名空间"))
    description = serializers.CharField(required=False, allow_blank=True, label=gettext_lazy("工具描述"))
    tags = serializers.ListField(
        child=serializers.CharField(), required=True, allow_empty=True, label=gettext_lazy("标签列表")
    )
    updated_time = serializers.DateTimeField(required=False, label="更新时间", format="%Y-%m-%d %H:%M:%S", allow_null=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        uid = attrs["uid"]
        config = attrs.get("config")

        tool = Tool.last_version_tool(uid)
        tool_type = tool.tool_type

        if config:
            if tool_type == ToolTypeEnum.BK_VISION:
                validated_config = BkVisionConfig.model_validate(config).model_dump()
            elif tool_type == ToolTypeEnum.DATA_SEARCH:
                validated_config = SQLDataSearchConfig.model_validate(config).model_dump()
            elif tool_type == ToolTypeEnum.API:
                validated_config = ApiToolConfig.model_validate(config).model_dump()
            else:
                raise serializers.ValidationError({"uid": f"不支持的工具类型: {tool_type}"})
            attrs["config"] = validated_config
        return attrs


class ToolResponseSerializer(serializers.Serializer):
    uid = serializers.CharField(label=gettext_lazy("工具 UID"))
    version = serializers.IntegerField(label=gettext_lazy("工具版本"))


class ToolRetrieveRequestSerializer(serializers.Serializer):
    uid = serializers.CharField(label=gettext_lazy("工具 UID"))


class ToolListAllResponseSerializer(serializers.ModelSerializer):
    permission = serializers.DictField(required=False, label=gettext_lazy("权限信息"))
    tags = serializers.ListField(child=serializers.CharField(), label=gettext_lazy("标签列表"))
    strategies = serializers.ListField(child=serializers.IntegerField(), label="关联策略")
    favorite = serializers.BooleanField(required=False, default=False, label=gettext_lazy("是否收藏"))

    class Meta:
        model = Tool
        fields = [
            "uid",
            "name",
            "description",
            "tool_type",
            "version",
            "namespace",
            "permission",
            "tags",
            "strategies",
            "favorite",
        ]


class ToolSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tool
        fields = "__all__"


class ToolListResponseSerializer(serializers.ModelSerializer):
    tags = serializers.ListField(child=serializers.CharField(), label=gettext_lazy("标签列表"))
    permission = serializers.DictField(required=False, label=gettext_lazy("权限信息"))
    strategies = serializers.ListField(child=serializers.IntegerField(), label="关联策略")
    favorite = serializers.BooleanField(required=False, default=False, label=gettext_lazy("是否收藏"))

    class Meta:
        model = Tool
        fields = [
            "uid",
            "name",
            "tool_type",
            "version",
            "description",
            "namespace",
            "updated_by",
            "updated_at",
            "created_by",
            "created_at",
            "tags",
            "permission",
            "strategies",
            "is_bkvision",
            "favorite",
        ]


class ToolRetrieveResponseSerializer(serializers.ModelSerializer):
    permission = serializers.DictField(required=False, label=gettext_lazy("权限信息"))
    strategies = serializers.ListField(child=serializers.IntegerField(), label="关联策略")
    tags = serializers.ListField(child=serializers.CharField(), label=gettext_lazy("标签列表"))
    config = ToolConfigField(label=gettext_lazy("工具配置"), help_text=gettext_lazy("根据工具类型，配置结构不同"))
    data_search_config_type = serializers.SerializerMethodField()
    permission_owner = serializers.SerializerMethodField()
    favorite = serializers.BooleanField(required=False, default=False, label=gettext_lazy("是否收藏"))

    def get_data_search_config_type(self, obj):
        if hasattr(obj, "data_search_config") and obj.data_search_config:
            return obj.data_search_config.data_search_config_type
        return None

    def get_permission_owner(self, obj: Tool):
        return obj.get_permission_owner()

    class Meta:
        model = Tool
        fields = [
            "uid",
            "name",
            "tool_type",
            "version",
            "description",
            "namespace",
            "created_by",
            "created_at",
            "updated_by",
            "updated_at",
            "permission",
            "strategies",
            "config",
            "tags",
            "data_search_config_type",
            "permission_owner",
            "is_bkvision",
            "favorite",
        ]


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


class SqlAnalyseWithToolRequestSerializer(SqlAnalyseRequestSerializer):
    """SQL 分析(带工具)请求参数"""

    uid = serializers.CharField(label=gettext_lazy("工具 UID"))


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
    params = ToolParamsField(label=gettext_lazy("工具执行参数"))
    caller_resource_type = serializers.ChoiceField(required=False, choices=CALLER_RESOURCE_TYPE_CHOICES)
    caller_resource_id = serializers.CharField(required=False, allow_blank=True)
    drill_field = serializers.CharField(required=False, allow_blank=True)
    event_start_time = serializers.CharField(required=False, allow_blank=True)
    event_end_time = serializers.CharField(required=False, allow_blank=True)


class ExecuteToolRespSerializer(serializers.Serializer):
    data = ToolResultField(label=gettext_lazy("执行结果"))
    tool_type = serializers.ChoiceField(choices=ToolTypeEnum.choices)


class UserQueryTableAuthCheckReqSerializer(serializers.Serializer):
    tables = serializers.ListField(label=gettext_lazy("表名列表"), child=serializers.CharField())
    username = serializers.CharField(
        label=gettext_lazy("用户名"),
        required=False,
        allow_blank=True,
        help_text="默认使用当前登录用户，也可指定其他用户",
    )


class UserQueryTableAuthCheckRespSerializer(serializers.Serializer):
    has_auth = serializers.BooleanField()


class ToolExecuteDebugSerializer(serializers.Serializer):
    tool_type = serializers.ChoiceField(choices=ToolTypeEnum.choices, label=gettext_lazy("工具类型"))
    config = ToolConfigField(label=gettext_lazy("工具配置"), help_text=gettext_lazy("根据工具类型，配置结构不同"))
    params = ToolParamsField(
        label=gettext_lazy("调试执行参数"),
        required=False,
        default=dict,
        help_text=gettext_lazy("与正式执行时一致的工具入参"),
    )


class ToolFavoriteReqSerializer(serializers.Serializer):
    """工具收藏请求序列化器"""

    uid = serializers.CharField(label=gettext_lazy("工具 UID"))
    favorite = serializers.BooleanField(label=gettext_lazy("收藏"))


class ToolFavoriteRespSerializer(serializers.Serializer):
    """工具收藏响应序列化器"""

    favorite = serializers.BooleanField(label=gettext_lazy("是否收藏"))
