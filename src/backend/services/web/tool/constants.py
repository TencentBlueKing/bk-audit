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
import abc
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from django.utils.translation import gettext, gettext_lazy
from drf_pydantic import BaseModel
from pydantic import Field as PydanticField
from pydantic import field_validator
from rest_framework.fields import CharField, DictField, JSONField, ListField
from typing_extensions import TypedDict

from apps.meta.models import EnumMappingRelatedType
from core.choices import TextChoices, register_choices
from core.utils.data import validate_unique_keys


@register_choices("ToolType")
class ToolTypeEnum(TextChoices):
    """
    工具类型
    """

    DATA_SEARCH = "data_search", gettext_lazy("数据查询")
    API = "api", gettext_lazy("API")
    BK_VISION = "bk_vision", gettext_lazy("BK Vision")


# ==========================================
# SQL 工具配置
# ==========================================


@register_choices("DataSearchConfigType")
class DataSearchConfigTypeEnum(TextChoices):
    """
    数据查询配置类型
    """

    SIMPLE = "simple", gettext_lazy("简易模式")
    SQL = "sql", gettext_lazy("SQL模式")


@register_choices("FieldCategory")
class FieldCategory(TextChoices):
    """
    字段类别(前端类型)
    """

    INPUT = "input", gettext_lazy("输入框")
    NUMBER_INPUT = "number_input", gettext_lazy("数字输入框")
    TIME_RANGE_SELECT = "time_range_select", gettext_lazy("时间范围选择器")
    TIME_SELECT = "time_select", gettext_lazy("时间选择器")
    PERSON_SELECT = "person_select", gettext_lazy("人员选择器")
    MULTISELECT = "multiselect", gettext_lazy("下拉列表")


@register_choices("TargetValueType")
class TargetValueTypeEnum(TextChoices):
    """
    下钻目标值类型枚举
    """

    FIXED_VALUE = "fixed_value", gettext_lazy("固定值")
    FIELD = "field", gettext_lazy("字段")


class DataSearchBaseField(BaseModel, abc.ABC):
    """
    数据查询基本字段
    """

    raw_name: str = PydanticField(title=gettext_lazy("字段名"))
    display_name: str = PydanticField(title=gettext_lazy("显示名"))
    description: str = PydanticField(default_factory=str, title=gettext_lazy("字段描述"))


class ChoiceItem(TypedDict):
    key: str
    name: Any


class EnumMappingConfig(BaseModel):
    """工具枚举映射配置"""

    collection_id: Optional[str] = PydanticField(
        default="auto-generate", description="枚举集合ID（自动生成，无需手动指定）", max_length=255, allow_mutation=False
    )
    mappings: List[Dict[str, str]] = PydanticField(
        default_factory=list, description="枚举键值对列表，格式：[{'key': '1', 'name': 'Active'}]"
    )
    related_type: EnumMappingRelatedType = PydanticField(
        EnumMappingRelatedType.TOOL, description="关联类型（固定为'tool'）", allow_mutation=False
    )
    related_object_id: Optional[str] = PydanticField(
        default="uid", description="关联工具UID", max_length=255, allow_mutation=False
    )


class SQLDataSearchInputVariable(DataSearchBaseField):
    """
    SQL数据查询输入变量
    """

    required: bool  # 是否必填
    field_category: FieldCategory  # 字段类别(前端类型)
    choices: List[ChoiceItem] = PydanticField(default_factory=list)  # 字段选项(用于不同字段类别下前端展示配置)
    default_value: Annotated[
        Union[str, int, float, bool, dict, list, None], JSONField(allow_null=True)
    ] = PydanticField(None, description="字段默认值")

    @field_validator('choices')
    @classmethod
    def validate_choices(cls, v):
        return validate_unique_keys(v, key_field='key', error_msg=lambda val: f"选项值 '{val}' 已存在")


class Tool(BaseModel):
    """
    工具
    """

    uid: str  # 工具UID
    version: int  # 工具版本


class ToolDrillConfig(BaseModel):
    """
    工具下钻配置
    """

    target_value_type: TargetValueTypeEnum
    target_field_type: Annotated[
        Optional[str], CharField(allow_blank=True, allow_null=True, default=None)
    ] = PydanticField("", description="引用字段类型用于前端区分字段")
    target_value: Annotated[Union[str, int, float, bool, dict, list], JSONField(allow_null=True)] = PydanticField(
        None, description="固定值/引用字段"
    )
    source_field: str  # 工具变量


class DrillConfig(BaseModel):
    """
    数据查询下钻配置
    """

    tool: Tool
    config: List[ToolDrillConfig] = PydanticField(default_factory=list)
    drill_name: Annotated[Optional[str], CharField(allow_blank=True, allow_null=True, default=None)] = PydanticField(
        None, description="下钻工具名称"
    )


class TableOutputField(DataSearchBaseField):
    """
    数据查询表格输出字段
    """

    drill_config: Optional[List[DrillConfig]] = None  # 下钻配置
    enum_mappings: Optional[EnumMappingConfig] = None


class SQLDataSearchOutputField(TableOutputField):
    """
    SQL数据查询输出字段
    """

    pass


class Table(BaseModel):
    table_name: str  # 表名


class SQLDataSearchConfig(BaseModel):
    """
    SQL模式数据查询配置 -- 当工具为数据检索且配置类型为 SQL 类型时使用
    """

    sql: str = PydanticField(title="SQL语句")
    referenced_tables: List[Table]  # RT表
    input_variable: List[SQLDataSearchInputVariable]  # 输入变量
    output_fields: List[SQLDataSearchOutputField]  # 输出字段


# ==========================================
# Bkvision 工具配置
# ==========================================


@register_choices("BKVisionFieldCategory")
class BKVisionFieldCategory(TextChoices):
    """
    BK Vision字段类别(前端类型)
    """

    BUTTON = "button", gettext_lazy("按钮")
    CASCADER = "cascader", gettext_lazy("级联选择器")
    INPUTER = "inputer", gettext_lazy("输入框")
    RADIOS = "radios", gettext_lazy("单选按钮组")
    SELECTOR = "selector", gettext_lazy("选择器")
    TIME_PICKER = "time-picker", gettext_lazy("时间选择器")
    TIME_RANGER = "time-ranger", gettext_lazy("时间范围选择器")
    VARIABLE = "variable", gettext_lazy("变量")


class BKVisionInputVariable(DataSearchBaseField):
    """
    BK Vision输入变量
    """

    field_category: BKVisionFieldCategory  # 字段类别(前端类型)
    required: bool = PydanticField(True, description="是否必填")
    default_value: Annotated[
        Union[str, int, float, bool, dict, list, None], JSONField(allow_null=True)
    ] = PydanticField(None, description="字段默认值")
    raw_default_value: Annotated[
        Union[str, int, float, bool, dict, list, None], JSONField(allow_null=True)
    ] = PydanticField(None, description="原始字段默认值")
    is_default_value: bool = PydanticField(True, description="是否默认值")


class BkVisionConfig(BaseModel):
    """
    BK Vision配置 -- 当工具为 BK Vision时使用
    """

    uid: str  # BK Vision 图表ID
    input_variable: List[BKVisionInputVariable] = PydanticField(default_factory=list)  # 输入变量


class ToolTagsEnum(TextChoices):
    """
    工具特殊展示标签
    """

    ALL_TOOLS = "-3", gettext_lazy("全部工具")
    MY_CREATED_TOOLS = "-4", gettext_lazy("我创建的")
    RECENTLY_USED_TOOLS = "-5", gettext_lazy("最近使用")


# ==========================================
# Api 工具配置
# ==========================================


class ApiAuthMethod(TextChoices):
    """
    API认证方法
    """

    BK_APP_AUTH = "bk_app_auth", gettext_lazy("蓝鲸应用认证")
    NONE = "none", gettext_lazy("无认证")


class BkAppAuthConfigSchema(BaseModel):
    """蓝鲸认证需要的具体字段"""

    bk_app_code: str = PydanticField(..., description="应用ID")
    bk_app_secret: str = PydanticField(..., description="应用密钥")


class BkAuthItem(BaseModel):
    method: Literal[ApiAuthMethod.BK_APP_AUTH] = ApiAuthMethod.BK_APP_AUTH
    config: BkAppAuthConfigSchema  # 这里的 config 强类型约束为 BkAppAuthConfigSchema


class NoAuthItem(BaseModel):
    method: Literal[ApiAuthMethod.NONE] = ApiAuthMethod.NONE


class ParamField(BaseModel):
    """
    参数字段
    """

    key: str = PydanticField(title=gettext_lazy("参数字段"))
    value: str = PydanticField(title=gettext_lazy("参数值"))
    description: str = PydanticField(title=gettext_lazy("参数描述"), default_factory=str)


class ApiRequestMethod(TextChoices):
    """
    API请求方法
    """

    GET = "GET", gettext_lazy("GET")
    POST = "POST", gettext_lazy("POST")


class ApiConfig(BaseModel):
    """
    API配置
    """

    url: str = PydanticField(title=gettext_lazy("请求地址"))
    method: ApiRequestMethod = PydanticField(title=gettext_lazy("请求方法"))
    # 这里定义 auth_config 可以是上面定义的任意一种 Item
    # discriminator="method" 告诉 Pydantic：
    # "请先看 method 字段的值，如果是 'bk_app_auth'，就用 BkAuthItem 来校验"
    auth_config: Annotated[Union[BkAuthItem, NoAuthItem], DictField()] = PydanticField(
        title=gettext_lazy("认证配置"), discriminator="method"
    )
    headers: List[ParamField] = PydanticField(title=gettext_lazy("请求头"))

    @field_validator('headers')
    @classmethod
    def validate_unique_headers(cls, v):
        return validate_unique_keys(v, key_field='key', error_msg=lambda key: gettext("请求头%s重复") % key)


@register_choices("api_variable_position")
class ApiVariablePosition(TextChoices):
    """
    API变量位置
    """

    QUERY = "query", gettext_lazy("查询参数")
    BODY = "body", gettext_lazy("请求体")
    PATH = "path", gettext_lazy("路径参数")


class ApiInputVariableBase(DataSearchBaseField):
    """
    输入变量
    """

    required: bool = PydanticField(title=gettext_lazy("是否必填"))
    field_category: FieldCategory = PydanticField(title=gettext_lazy("前端类型"))
    default_value: Annotated[
        Union[str, int, float, bool, dict, list, None], JSONField(allow_null=True)
    ] = PydanticField(None, title=gettext_lazy("字段默认值"))
    is_show: bool = PydanticField(title=gettext_lazy("用户是否可见"))
    position: ApiVariablePosition = PydanticField(title=gettext_lazy("变量位置"))


class ApiStandardInputVariable(ApiInputVariableBase):
    """
    标准输入变量
    """

    field_category: Literal[
        FieldCategory.INPUT,
        FieldCategory.NUMBER_INPUT,
        FieldCategory.TIME_SELECT,
        FieldCategory.PERSON_SELECT,
    ] = PydanticField(title=gettext_lazy("前端类型"))


class ApiSelectInputVariable(ApiInputVariableBase):
    """
    选择输入变量
    """

    field_category: Literal[FieldCategory.MULTISELECT] = FieldCategory.MULTISELECT
    choices: List[ChoiceItem] = PydanticField(
        default_factory=list,
        title=gettext_lazy("字段选项"),
        description=gettext_lazy("用于不同字段类别下前端展示配置"),
    )

    @field_validator('choices')
    @classmethod
    def validate_choices(cls, v):
        return validate_unique_keys(v, key_field='key', error_msg=lambda key: gettext("选项值 %s 重复") % key)


class TimeRangeSplitConfig(BaseModel):
    """
    时间范围分割配置
    """

    start_field: str = PydanticField(min_length=1, title=gettext_lazy("开始时间参数名"))
    end_field: str = PydanticField(min_length=1, title=gettext_lazy("结束时间参数名"))


class TimeRangeInputVariable(ApiInputVariableBase):
    """
    时间范围变量 (特有逻辑)
    """

    field_category: Literal[FieldCategory.TIME_RANGE_SELECT] = FieldCategory.TIME_RANGE_SELECT
    # 时间范围分割配置
    split_config: TimeRangeSplitConfig = PydanticField(title=gettext_lazy("时间范围分割配置"))


class ApiOutputFieldType(TextChoices):
    """
    API输出字段类型
    """

    KV = "kv", gettext_lazy("键值对")
    TABLE = "table", gettext_lazy("表格")


class KvOutputField(BaseModel):
    """
    KV 类型：没有额外的配置
    """

    field_type: Literal[ApiOutputFieldType.KV] = ApiOutputFieldType.KV


class ApiJsonField(DataSearchBaseField):
    """
    API JSON 字段
    """

    json_path: str = PydanticField(title=gettext_lazy("字段路径"))


class ApiTableOutputField(TableOutputField, ApiJsonField):
    """API 表格内部列定义"""

    pass


class TableFieldTypeConfig(BaseModel):
    """
    表格字段类型配置
    """

    field_type: Literal[ApiOutputFieldType.TABLE] = ApiOutputFieldType.TABLE
    output_fields: List[ApiTableOutputField] = PydanticField(default_factory=list, title=gettext_lazy("输出字段"))


class ApiOutputField(ApiJsonField):
    """
    API输出字段
    """

    field_config: Annotated[Union[TableFieldTypeConfig, KvOutputField], DictField()] = PydanticField(
        title=gettext_lazy("字段配置"), discriminator="field_type"
    )
    drill_config: Optional[List[DrillConfig]] = PydanticField(None, title=gettext_lazy("下钻配置"))
    enum_mappings: Optional[EnumMappingConfig] = PydanticField(None, title=gettext_lazy("字段值映射配置"))


class ApiOutputGroup(BaseModel):
    """
    API输出分组
    """

    name: str = PydanticField(title=gettext_lazy("分组名"))
    output_fields: List[ApiOutputField] = PydanticField(default_factory=list, title=gettext_lazy("输出字段"))


class ApiOutputConfiguration(BaseModel):
    """
    API 输出整体配置
    """

    # 1. 分组开关
    enable_grouping: bool = PydanticField(
        title=gettext_lazy("开启输出分组"), description=gettext_lazy("关闭时前端将忽略分组名，直接展示所有字段")
    )

    # 2. 统一的数据结构
    groups: List[ApiOutputGroup] = PydanticField(default_factory=list, title=gettext_lazy("输出分组列表"))

    @field_validator('groups')
    @classmethod
    def validate_unique_groups(cls, v):
        return validate_unique_keys(v, key_field='name', error_msg=lambda key: gettext("分组名 %s 重复") % key)


# API 输入变量
ApiInputVariableUnion = Annotated[
    Union[TimeRangeInputVariable, ApiStandardInputVariable, ApiSelectInputVariable],
    PydanticField(discriminator="field_category"),
]


class ApiToolConfig(BaseModel):
    """
    API工具配置
    """

    api_config: ApiConfig
    input_variable: Annotated[List[ApiInputVariableUnion], ListField(child=DictField())] = PydanticField(
        default_factory=list, title=gettext_lazy("输入变量")
    )
    output_config: ApiOutputConfiguration = PydanticField(title=gettext_lazy("输出配置"))


class APIToolExecuteParams(BaseModel):
    raw_name: str = PydanticField(title=gettext_lazy("执行入参名"))
    value: str = PydanticField(title=gettext_lazy("执行入参值"))
    position: ApiVariablePosition = PydanticField(title=gettext_lazy("参数位置"))


class APIToolVariable(BaseModel):
    uid: str = PydanticField(title=gettext_lazy("工具uid"))
    execute_variables: Annotated[List[APIToolExecuteParams], ListField(child=DictField())] = PydanticField(
        default_factory=list, title=gettext_lazy("输入变量")
    )
