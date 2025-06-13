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
from typing import List, Union

from pypika.enums import Order
from pypika.functions import Avg, Count, Max, Min
from pypika.queries import QueryBuilder
from pypika.terms import BasicCriterion, Criterion, EmptyCriterion, Function

from apps.meta.utils.fields import STANDARD_FIELDS
from core.constants import OrderTypeChoices
from core.sql.builder.builder import BKBaseQueryBuilder, BkBaseTable
from core.sql.builder.functions import DateTrunc, FromUnixTime, PercentileApprox
from core.sql.builder.terms import (
    DorisField,
    DorisJsonTypeExtractFunction,
    DorisVariantField,
    PypikaField,
)
from core.sql.builder.utils import operate
from core.sql.constants import FieldType
from services.web.query.utils.search_config import QueryConditionOperator


class BaseDorisSQLBuilder:
    """日志查询SQL构建器"""

    VARIANT_FIELDS = {f.field_name for f in STANDARD_FIELDS if f.is_json and not f.property["dynamic_content"]}
    JSON_TYPE_FIELDS = {f.field_name for f in STANDARD_FIELDS if f.is_json and f.property["dynamic_content"]}

    def __init__(
        self,
        table: str,
        conditions: List[dict],
        sort_list: List[dict],
        page: int,
        page_size: int,
    ):
        self.conditions = conditions
        self.sort_list = sort_list
        self.page = page
        self.page_size = page_size
        self.table = self._build_base_table(table)
        self.query = BKBaseQueryBuilder().from_(self.table)

    def _build_base_table(self, table: str) -> BkBaseTable:
        """
        构建基础数据表
        """
        return BkBaseTable(table)

    def get_pypika_field(self, name: str, keys: List[str] = None) -> Union[DorisField, Function]:
        """
        获取pypika字段
        """
        if name in self.VARIANT_FIELDS and keys:
            return DorisVariantField(name=name, table=self.table, keys=keys)
        if name in self.JSON_TYPE_FIELDS and keys:
            return DorisJsonTypeExtractFunction(DorisField(name=name, table=self.table), keys=keys)
        return DorisField(name=name, table=self.table)

    def build_filters(self, pypika_field: DorisField, operator: str, filters: list) -> BasicCriterion:
        """
        构建筛选条件
        """

        if operator in [QueryConditionOperator.LIKE.value, QueryConditionOperator.NOT_LIKE.value]:
            filters = [f"%{item}%" for item in filters]
        value = filters[0] if filters else ""
        return operate(operator, pypika_field, value, filters)

    def _build_filter_condition(self) -> Criterion:
        """
        构建过滤条件
        """

        condition = EmptyCriterion()
        for item in self.conditions:
            condition &= self.build_filters(
                self.get_pypika_field(name=item["field"]["raw_name"], keys=item["field"].get("keys", [])),
                item["operator"],
                item.get("filters", []),
            )
        return condition

    def _build_where(self, query: QueryBuilder) -> QueryBuilder:
        """
        组合 WHERE 条件
        """

        return query.where(self._build_filter_condition())

    def _build_order_by(self, query: QueryBuilder) -> QueryBuilder:
        """
        构建排序逻辑
        """

        for sort_item in self.sort_list:
            order_field = sort_item["order_field"]
            order_type = sort_item["order_type"]
            order = Order.desc if order_type == OrderTypeChoices.DESC else Order.asc
            query = query.orderby(self.get_pypika_field(name=order_field), order=order)
        return query


class DorisQuerySQLBuilder(BaseDorisSQLBuilder):
    def build_data_sql(self) -> str:
        """
        生成完整数据查询
        """
        query = self.query.select("*")
        query = self._build_where(query)
        query = self._build_order_by(query)
        return str(query.limit(self.page_size).offset(self.page_size * (self.page - 1)))

    def build_count_sql(self) -> str:
        """
        生成统计查询
        """

        return str(self._build_where(self.query).select(Count("*").as_("count")).limit(1))


class DorisStatisticSQLBuilder(BaseDorisSQLBuilder):
    def _build_base_table(self, table: str) -> BkBaseTable:
        """
        构建基础数据表
        """
        return super()._build_base_table(table).as_("event_table")

    def build_statistic_sql(self, field_name: str, field_type: FieldType) -> dict[str, str]:
        """
        生成统计数据查询，基于字段类型生成相应的统计数据
        """
        query = self._build_where(self.query)

        # 使用 get_pypika_fields 来获取字段对象
        field = self.get_pypika_field(field_name)

        # 1. 总行数
        total_rows_query = query.select(Count('*').as_("total_rows"))

        # 2. 出现行数（非空）
        non_empty_rows_query = query.select(Count(field).as_("non_empty_rows"))

        # 3. 非空行数占比
        non_empty_ratio_query = query.select((Count(field) / Count('*')).as_("non_empty_ratio"))

        if field_type in (FieldType.STRING, FieldType.TEXT):  # 文本字段的统计
            # 4. Top 5（出现次数）值
            top_5_values_query = (
                query.select(field, Count(field).as_("count"))
                .groupby(field)
                .orderby(PypikaField("count"), order=Order.desc)
            ).limit(5)

            time_interval = DateTrunc(FromUnixTime(self.get_pypika_field('dteventtimestamp') / 1000), "HOUR")

            # 5. 时间序列统计（按分钟）
            time_series_query = (
                query.select(
                    field,
                    time_interval.as_("time_interval"),
                    Count(field).as_("count"),
                )
                .join(top_5_values_query)
                .on(field == getattr(top_5_values_query, field_name))  # 修改连接条件
                .groupby(time_interval, field)
                .orderby(time_interval, order=Order.desc)
            )

            # 返回每个查询
            return {
                "total_rows": str(total_rows_query),
                "non_empty_rows": str(non_empty_rows_query),
                "non_empty_ratio": str(non_empty_ratio_query),
                "top_5_values": str(top_5_values_query),
                "top_5_time_series": str(time_series_query),
                "max_value": None,
                "min_value": None,
                "avg_value": None,
                "median_value": None,
            }

        else:
            max_value_query = query.select(Max(field).as_("max_value"))
            min_value_query = query.select(Min(field).as_("min_value"))
            avg_value_query = query.select(Avg(field).as_("avg_value"))
            median_value_query = query.select(PercentileApprox(field, 0.5).as_("median_value"))

            # 返回每个查询
            return {
                "total_rows": str(total_rows_query),
                "non_empty_rows": str(non_empty_rows_query),
                "non_empty_ratio": str(non_empty_ratio_query),
                "max_value": str(max_value_query),
                "min_value": str(min_value_query),
                "avg_value": str(avg_value_query),
                "median_value": str(median_value_query),
                "top_5_values": None,
                "top_5_time_series": None,
            }
