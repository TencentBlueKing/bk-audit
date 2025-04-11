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
from typing import List, Optional, Union

from pydantic import BaseModel
from pydantic import Field as PydanticField
from pypika import Order as PypikaOrder

from core.sql.constants import (
    AggregateType,
    FieldType,
    FilterConnector,
    JoinType,
    Operator,
)


class Table(BaseModel):
    """
    表
    """

    table_name: str  # 表名
    alias: Optional[str] = None  # 别名


class Field(BaseModel):
    """
    字段
    """

    table: str  # 表名
    raw_name: str  # 原始字段名称
    display_name: str  # 作为 sql 的列名，默认为原始字段名称
    field_type: FieldType  # 字段类型
    aggregate: Optional[AggregateType] = None  # 聚合函数
    keys: List[str] = PydanticField(default_factory=list)  # 字段 key 仅适用于 Doris Variant 类型

    def __init__(self, **data):
        super().__init__(**data)
        if self.display_name is None:
            self.display_name = self.raw_name


class LinkField(BaseModel):
    """
    关联字段
    """

    left_field: str  # 左表关联字段
    right_field: str  # 右表关联字段


class JoinTable(BaseModel):
    """
    联表
    """

    join_type: JoinType  # 连接类型
    link_fields: List[LinkField]  # 连接字段
    left_table: Table  # 左表
    right_table: Table  # 右表


class Condition(BaseModel):
    """
    条件
    """

    field: Field  # 字段
    operator: Operator  # 操作符
    filters: List[Union[str, int, float]] = PydanticField(default_factory=list)  # 多个筛选值 - 如果操作符需要操作多个值，使用该字段
    filter: Union[str, int, float] = PydanticField(default_factory=str)  # 筛选值 - 如果操作符只需要一个值，使用该字段


class WhereCondition(BaseModel):
    """
    Where筛选条件
    """

    connector: FilterConnector = FilterConnector.AND  # 连接符
    conditions: List["WhereCondition"] = PydanticField(default_factory=list)  # 子条件
    condition: Optional[Condition] = None  # 条件


class HavingCondition(WhereCondition):
    """Having筛选条件"""

    pass


class Order(BaseModel):
    """
    排序
    """

    field: Field  # 字段
    order: PypikaOrder  # 排序方式


class Pagination(BaseModel):
    """
    分页
    """

    limit: Optional[int] = None  # 限制数量
    offset: Optional[int] = None  # 偏移量


class SqlConfig(BaseModel):
    """
    sql 配置
    """

    select_fields: List[Field]  # 作为 sql 的列
    from_table: Optional[Table] = None  # 主表
    join_tables: Optional[List[JoinTable]] = None  # 联表
    where: Optional[WhereCondition] = None  # 筛选条件
    having: Optional[HavingCondition] = None  # 筛选条件
    group_by: List[Field] = PydanticField(default_factory=list)  # 分组条件；如果未指定但有聚合函数，则会自动添加 group by 条件
    order_by: List[Order] = PydanticField(default_factory=list)  # 排序条件
    pagination: Optional[Pagination] = None  # 分页条件
