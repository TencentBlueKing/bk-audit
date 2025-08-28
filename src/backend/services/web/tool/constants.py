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
from typing import Annotated, Any, Dict, List, Optional, Union

from django.utils.translation import gettext_lazy
from drf_pydantic import BaseModel
from pydantic import Field as PydanticField
from pydantic import validator
from rest_framework.fields import CharField, JSONField
from typing_extensions import TypedDict

from apps.meta.models import EnumMappingRelatedType
from core.choices import TextChoices, register_choices


@register_choices("ToolType")
class ToolTypeEnum(TextChoices):
    """
    工具类型
    """

    DATA_SEARCH = "data_search", gettext_lazy("数据查询")
    API = "api", gettext_lazy("API")
    BK_VISION = "bk_vision", gettext_lazy("BK Vision")


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

    raw_name: str  # 字段名
    display_name: str  # 展示名
    description: str = PydanticField(default_factory=str)  # 字段描述


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

    @validator('choices')
    def validate_choices_keys(cls, v):
        """确保每个choice中的key值唯一"""
        seen_keys = set()

        for item in v:
            key = item['key']
            if key in seen_keys:
                raise ValueError(f"发现重复的key: {key}")
            seen_keys.add(key)
        return v


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


class ToolTagsEnum(TextChoices):
    """
    工具特殊展示标签
    """

    ALL_TOOLS = "全部工具", gettext_lazy("全部工具")
    MY_CREATED_TOOLS = "我创建的", gettext_lazy("我创建的")
    RECENTLY_USED_TOOLS = "最近使用", gettext_lazy("最近使用")


class BKVisionInputVariable(DataSearchBaseField):
    """
    BK Vision输入变量
    """

    field_category: BKVisionFieldCategory  # 字段类别(前端类型)
    required: bool = PydanticField(True, description="是否必填")
    default_value: Annotated[
        Union[str, int, float, bool, dict, list, None], JSONField(allow_null=True)
    ] = PydanticField(None, description="字段默认值")


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
        None, description="变量的详细描述"
    )
    source_field: str  # 工具变量


class DrillConfig(BaseModel):
    """
    数据查询下钻配置
    """

    tool: Tool
    config: List[ToolDrillConfig] = PydanticField(default_factory=list)


class SQLDataSearchOutputField(DataSearchBaseField):
    """
    SQL数据查询输出字段
    """

    drill_config: Optional[DrillConfig] = None  # 下钻配置
    enum_mappings: Optional[EnumMappingConfig] = None


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


class BkVisionConfig(BaseModel):
    """
    BK Vision配置 -- 当工具为 BK Vision时使用
    """

    uid: str  # BK Vision 图表ID
    input_variable: List[BKVisionInputVariable] = PydanticField(default_factory=list)  # 输入变量


All_TOOLS_ID = "-3"
MY_CREATED_TOOLS_ID = "-4"
RECENTLY_USED_TOOLS_ID = "-5"
