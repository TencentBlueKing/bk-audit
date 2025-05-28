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
from typing import List, Optional

from django.utils.translation import gettext_lazy
from drf_pydantic import BaseModel
from pydantic import Field as PydanticField
from pydantic.v1 import root_validator

from core.choices import TextChoices


class ToolTypeEnum(TextChoices):
    """
    工具类型
    """

    DATA_SEARCH = "data_search", gettext_lazy("数据查询")
    API = "api", gettext_lazy("API")
    BK_VISION = "bk_vision", gettext_lazy("BK Vision")


class DataSearchConfigTypeEnum(TextChoices):
    """
    数据查询配置类型
    """

    SIMPLE = "simple", gettext_lazy("简易模式")
    SQL = "sql", gettext_lazy("SQL模式")


class FieldCategory(TextChoices):
    """
    字段类别(前端类型)
    """

    INPUT = "input", gettext_lazy("输入框")
    NUMBER_INPUT = "number_input", gettext_lazy("数字输入框")
    TIME_RANGE_SELECT = "time_range_select", gettext_lazy("时间范围选择器")
    TIME_SELECT = "time_select", gettext_lazy("时间选择器")
    PERSON_SELECT = "person_select", gettext_lazy("人员选择器")


class DataSearchBaseField(BaseModel, abc.ABC):
    """
    数据查询基本字段
    """

    raw_name: str  # 字段名
    display_name: str  # 展示名
    description: str = PydanticField(default_factory=str)  # 字段描述


class SQLDataSearchInputVariable(DataSearchBaseField):
    """
    SQL数据查询输入变量
    """

    required: bool  # 是否必填
    field_category: FieldCategory  # 字段类别(前端类型)
    choices: list = PydanticField(default_factory=list)  # 字段选项(用于不同字段类别下前端展示配置)


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

    target_field: str  # 目标字段
    source_field: Optional[str] = None  # 来源字段
    target_value: Optional[str] = None  # 固定值

    @root_validator
    def check_exclusive_fields(cls, values):
        sf, tv = values.get('source_field'), values.get('target_value')
        # 如果两个都为空，或两个都有值，都算校验失败
        if (sf is None) == (tv is None):
            raise ValueError('必须且只能提供 source_field 或 target_value 中的一个')
        return values


class DataSearchDrillConfig(BaseModel):
    """
    数据查询下钻配置
    """

    tool: Tool
    config: List[ToolDrillConfig] = PydanticField(default_factory=list)


class SQLDataSearchOutputField(DataSearchBaseField):
    """
    SQL数据查询输出字段
    """

    drill_config: Optional[DataSearchDrillConfig] = None  # 下钻配置


class Table(BaseModel):
    table_name: str  # 表名


class SQLDataSearchConfig(BaseModel):
    """
    SQL模式数据查询配置 -- 当工具为数据检索且配置类型为 SQL 类型时使用
    """

    referenced_tables: List[Table]  # RT表
    input_variable: List[SQLDataSearchInputVariable]  # 输入字段
    output_fields: List[SQLDataSearchOutputField]  # 输出字段


class BkvisionConfig(BaseModel):
    """
    BK Vision配置 -- 当工具为 BK Vision时使用
    """

    space_uid: str  # BK Vision 空间 ID
    uid: str  # BK Vision 图表ID
