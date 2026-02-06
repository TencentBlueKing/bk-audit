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
import json
import operator
from functools import reduce
from typing import Dict, Optional, Type, Union

from pypika import Table
from pypika.functions import Cast, Count
from pypika.queries import QueryBuilder
from pypika.terms import BasicCriterion, EmptyCriterion, Function

from core.sql.builder.builder import BkBaseTable
from core.sql.builder.functions import GetJsonObject
from core.sql.builder.terms import DorisJsonTypeExtractFunction, PypikaField
from core.sql.builder.utils import get_function, operate
from core.sql.constants import AggregateType, FieldType, FilterConnector
from core.sql.exceptions import (
    FilterValueError,
    InvalidAggregateTypeError,
    MissingFromOrJoinError,
    TableNotRegisteredError,
    UnsupportedJoinTypeError,
)
from core.sql.model import Condition, Field, HavingCondition, SqlConfig
from core.sql.model import Table as SqlTable
from core.sql.model import WhereCondition


class SQLGenerator:
    """SQL 生成器"""

    table_cls = Table
    field_type_cls = PypikaField
    table_map: Dict[str, Table]
    config: SqlConfig = None
    drill_function = GetJsonObject

    def __init__(
        self,
        query_builder: QueryBuilder,
        table_cls: Type[Table] = None,
        field_type_cls: Type[PypikaField] = None,
        drill_function: Type[Function] = None,
    ):
        """
        初始化生成器
        :param query_builder: PyPika 的 QueryBuilder 对象
        :param table_cls: 自定义的 Table 类
        :param field_type_cls: 自定义的字段类型类
        """
        self.query_builder = query_builder
        self.table_cls = table_cls or self.table_cls
        self.field_type_cls = field_type_cls or self.field_type_cls
        self.drill_function = drill_function or self.drill_function

    def _register_tables(self):
        """注册所有有效的表名"""
        register_tables = {}

        # 添加主表到注册表
        if self.config.from_table:
            alias = self.config.from_table.alias or self.config.from_table.table_name
            register_tables[alias] = self.config.from_table

        # 添加连接表到注册表
        for join_table in self.config.join_tables or []:
            for table in [join_table.left_table, join_table.right_table]:
                alias = table.alias or table.table_name
                register_tables[alias] = table

        # 更新 table_map 映射
        self.table_map.update(
            {alias: self.table_cls(table.table_name).as_(alias) for alias, table in register_tables.items()}
        )

    def _get_table(self, table: Union[str, SqlTable]) -> Table:
        """根据表名获取 Table 对象"""
        if isinstance(table, SqlTable):
            table = table.alias or table.table_name
        if table not in self.table_map:
            raise TableNotRegisteredError(table)
        return self.table_map[table]

    def _get_pypika_field(self, field: Field) -> PypikaField:
        """根据 Field 获取 PyPika 字段"""
        table = self._get_table(field.table)
        pypika_field = self.field_type_cls.get_field(table, field)
        # 若存在下钻字段
        if field.keys:
            pypika_field = self.drill_function(
                pypika_field,
                "$.{}".format(".".join([f"[{json.dumps(k)}]" for k in field.keys])),
                str(field.field_type).upper(),
            )
            if hasattr(pypika_field, 'cast_to'):
                pypika_field = pypika_field.cast_to()
        return pypika_field

    def generate(self, config: SqlConfig) -> QueryBuilder:
        """根据配置构建 SQL 查询"""
        self.config = config
        self.table_map = {}
        self._register_tables()
        query = self.query_builder
        query = self._build_from(query)
        query = self._build_select(query)
        query = self._build_where(query)
        query = self._build_group_by(query)
        query = self._build_having(query)
        query = self._build_order_by(query)
        query = self._build_pagination(query)
        return query

    def _build_from(self, query: QueryBuilder) -> QueryBuilder:
        """添加 FROM 子句"""
        if not (self.config.from_table or self.config.join_tables):
            raise MissingFromOrJoinError()
        from_table = self.config.join_tables[0].left_table if self.config.join_tables else self.config.from_table
        query = query.from_(self._get_table(from_table))
        if self.config.join_tables:
            query = self._build_join(self.config.from_table, query)
        return query

    def _build_join(self, from_table: Optional[str], query: QueryBuilder) -> QueryBuilder:
        """添加 JOIN 子句"""
        for join_table in self.config.join_tables:
            left_table = self._get_table(join_table.left_table)
            if not from_table:
                from_table = left_table
                query = query.from_(from_table)
            right_table = self._get_table(join_table.right_table)
            try:
                join_function = getattr(query, join_table.join_type.value.lower())
            except AttributeError:
                raise UnsupportedJoinTypeError(join_table.join_type)
            if not join_function:
                raise UnsupportedJoinTypeError(join_table.join_type)
            criterion = EmptyCriterion()
            for link_field in join_table.link_fields:
                criterion &= left_table.field(link_field.left_field) == right_table.field(link_field.right_field)
            query = join_function(right_table).on(criterion)
        return query

    def _build_select(self, query: QueryBuilder) -> QueryBuilder:
        """添加 SELECT 子句"""
        # 如果 select_fields 为空，使用 SELECT *
        if not self.config.select_fields:
            return query.select("*")

        for field in self.config.select_fields:
            if field.aggregate:
                # 如果存在聚合函数，使用 fn 调用
                pypika_field = self._build_aggregate(field)
            else:
                pypika_field = self._get_pypika_field(field)

            pypika_field = pypika_field.as_(field.display_name)
            query = query.select(pypika_field)
        return query

    def _build_aggregate(self, field: Field) -> PypikaField:
        # 如果存在聚合函数，使用 fn 调用
        pypika_field = self._get_pypika_field(field)
        aggregate_func = get_function(field.aggregate)
        if not aggregate_func:
            raise InvalidAggregateTypeError(field.aggregate)
        pypika_field = aggregate_func(pypika_field)
        return pypika_field

    def _build_where(self, query: QueryBuilder) -> QueryBuilder:
        """添加 WHERE 子句"""
        if self.config.where:
            criterion = self._apply_filter_conditions(self.config.where)
            if criterion:
                query = query.where(criterion)
        return query

    def _build_having(self, query: QueryBuilder) -> QueryBuilder:
        """添加 HAVING 子句"""
        if self.config.having:
            criterion = self._apply_filter_conditions(self.config.having)
            if criterion:
                query = query.having(criterion)
        return query

    def handle_condition(self, condition: Condition) -> BasicCriterion:
        """处理条件"""
        if condition.field.aggregate:
            # 如果条件字段是聚合函数，则使用聚合函数处理
            field = self._build_aggregate(condition.field)
            # 采用聚合函数规定的类型 or 字段本身类型
            filter_type = (condition.field.aggregate.result_data_type or condition.field.field_type).python_type
        else:
            # 否则，使用普通字段处理
            field = self._get_pypika_field(condition.field)
            filter_type = condition.field.field_type.python_type
        operator = condition.operator
        try:
            return operate(
                operator,
                field,
                filter_type(condition.filter) if condition.filter else None,
                [filter_type(f) for f in condition.filters],
            )
        except ValueError:
            raise FilterValueError(
                condition.field.raw_name, condition.filter or condition.filters, filter_type, condition.field.aggregate
            )

    def _apply_filter_conditions(self, condition: Union[WhereCondition, HavingCondition]) -> BasicCriterion:
        """递归构建 WHERE/HAVING 子句"""
        if condition.condition:
            return self.handle_condition(condition.condition)

        if condition.conditions:
            # 过滤掉空的查询条件，避免出现 Criterion.get_sql() got an unexpected keyword argument 'subcriterion'
            sub_criterions = []
            for sub_condition in condition.conditions:
                criterion = self._apply_filter_conditions(sub_condition)
                if not isinstance(criterion, EmptyCriterion):
                    sub_criterions.append(criterion)

            if not sub_criterions:
                return EmptyCriterion()

            op = operator.and_ if condition.connector == FilterConnector.AND else operator.or_
            return reduce(op, sub_criterions)

        return EmptyCriterion()

    def _build_group_by(self, query: QueryBuilder) -> QueryBuilder:
        """添加 GROUP BY 子句"""
        if self.config.group_by:
            # 如果明确指定了 group_by 字段，则使用它们
            for field in self.config.group_by:
                query = query.groupby(self._get_pypika_field(field))
        else:
            # 检查是否存在聚合字段
            has_aggregate = any(field.aggregate for field in self.config.select_fields)
            if not has_aggregate:
                return query
            # 自动推导非聚合字段进行分组
            for field in self.config.select_fields:
                if not field.aggregate:
                    query = query.groupby(self._get_pypika_field(field))
        return query

    def _build_order_by(self, query: QueryBuilder) -> QueryBuilder:
        """添加 ORDER BY 子句"""
        if self.config.order_by:
            for order in self.config.order_by:
                pypika_field = self._get_pypika_field(order.field)
                query = query.orderby(pypika_field, order=order.order)
        return query

    def _build_pagination(self, query: QueryBuilder) -> QueryBuilder:
        """添加 LIMIT 和 OFFSET 子句"""
        if self.config.pagination:
            if self.config.pagination.limit:
                query = query.limit(self.config.pagination.limit)
            if self.config.pagination.offset:
                query = query.offset(self.config.pagination.offset)
        return query

    def generate_count(self, config: SqlConfig) -> QueryBuilder:
        """
        生成 COUNT 查询

        与 generate() 类似，但只返回 COUNT(*) 而不是实际数据。
        不包含 SELECT、GROUP BY、HAVING、ORDER BY、PAGINATION。
        """
        self.config = config
        self.table_map = {}
        self._register_tables()
        query = self.query_builder
        query = self._build_from(query)
        query = self._build_where(query)
        query = query.select(Count("*").as_("count")).limit(1)
        return query


class BkBaseComputeSqlGenerator(SQLGenerator):
    """BK-BASE 计算模块的 SQL 生成器"""

    table_cls = BkBaseTable


class BkbaseDorisSqlGenerator(BkBaseComputeSqlGenerator):
    """
    Bkbase Doris SQL 生成器；支持 Doris JSON 字段下钻。
    """

    # GROUP_CONCAT 要求参数是 STRING 类型，这些聚合类型不做 CAST
    _STRING_ONLY_AGGREGATES = {AggregateType.LIST.value, AggregateType.LIST_DISTINCT.value}

    def _get_pypika_field(self, field: Field):
        if not field.keys:
            return super()._get_pypika_field(field)

        table = self._get_table(field.table)
        base_field = self.field_type_cls.get_field(table, field)
        json_value = DorisJsonTypeExtractFunction(base_field, field.keys, FieldType.STRING)

        # GROUP_CONCAT (LIST/LIST_DISTINCT) 要求参数是 STRING，跳过 CAST
        if field.aggregate in self._STRING_ONLY_AGGREGATES:
            return json_value

        target_type = field.field_type or FieldType.STRING
        if target_type in (FieldType.STRING, FieldType.TEXT):
            return json_value
        return Cast(json_value, target_type.query_data_type)
