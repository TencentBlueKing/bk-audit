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
from pymysql.converters import escape_string
from pydantic import ValidationError
from pypika import Order as pypikaOrder
from pypika.queries import QueryBuilder
from pypika.terms import ValueWrapper

from core.sql.builder.functions import Concat, GroupConcat, JsonContains
from core.sql.builder.generator import SQLGenerator
from core.sql.constants import (
    AggregateType,
    FieldType,
    FilterConnector,
    JoinType,
    Operator,
)
from core.sql.exceptions import TableNotRegisteredError
from core.sql.model import (
    Condition,
    Field,
    HavingCondition,
    JoinTable,
    LinkField,
    Order,
    Pagination,
    SqlConfig,
    Table,
    WhereCondition,
)
from tests.base import TestCase

from core.sql.builder.terms import DorisVariantField
from core.sql.constants import DORIS_FIELD_KEY_QUOTE
from services.web.query.utils.doris import DorisQuerySQLBuilder
from services.web.query.utils.search_config import QueryConditionOperator
from unittest.mock import patch


class TestSQLGenerator(TestCase):
    def setUp(self):
        self.query_builder = QueryBuilder()

    def test_single_table_query(self):
        """测试单表查询的 SQL 生成，包含普通字段和JSON字段"""
        # 测试普通字段和JSON字段混合查询
        config = SqlConfig(
            select_fields=[
                Field(table="users", raw_name="id", display_name="user_id", field_type=FieldType.INT),
                Field(table="users", raw_name="name", display_name="user_name", field_type=FieldType.STRING),
                Field(
                    table="users",
                    raw_name="profile",
                    display_name="user_profile",
                    field_type=FieldType.STRING,
                    keys=["address", "city"],  # JSON字段子key查询
                ),
            ],
            from_table=Table(table_name="users"),
        )
        query = SQLGenerator(self.query_builder).generate(config)
        expected_query = (
            'SELECT "users"."id" "user_id","users"."name" "user_name",'
            'CAST(GET_JSON_OBJECT("users"."profile",\'$.["address"].["city"]\') AS STRING) "user_profile" '
            'FROM "users" "users"'
        )
        self.assertEqual(str(query), expected_query, f"Expected: {expected_query}, but got: {query}")

    def test_join_table_query(self):
        """测试联表查询的 SQL 生成"""
        config = SqlConfig(
            select_fields=[
                Field(table="users", raw_name="id", display_name="user_id", field_type=FieldType.INT),
                Field(table="orders", raw_name="order_id", display_name="order_id", field_type=FieldType.INT),
            ],
            from_table=Table(table_name="users"),
            join_tables=[
                JoinTable(
                    join_type=JoinType.INNER_JOIN,
                    link_fields=[LinkField(left_field="id", right_field="user_id")],
                    left_table=Table(table_name="users"),
                    right_table=Table(table_name="orders"),
                )
            ],
        )
        generator = SQLGenerator(self.query_builder)
        query = generator.generate(config)
        expected_query = (
            'SELECT "users"."id" "user_id","orders"."order_id" "order_id" FROM "users" '
            '"users" JOIN "orders" "orders" ON "users"."id"="orders"."user_id"'
        )
        self.assertEqual(str(query), expected_query, f"Expected: {expected_query}, but got: {query}")

    def test_join_with_multiple_link_fields(self):
        """多个 link_fields 应使用 AND 组合在同一个 ON 子句中"""
        config = SqlConfig(
            select_fields=[
                Field(table="users", raw_name="id", display_name="user_id", field_type=FieldType.INT),
                Field(table="orders", raw_name="order_id", display_name="order_id", field_type=FieldType.INT),
            ],
            from_table=Table(table_name="users"),
            join_tables=[
                JoinTable(
                    join_type=JoinType.INNER_JOIN,
                    link_fields=[
                        LinkField(left_field="id", right_field="user_id"),
                        LinkField(left_field="name", right_field="user_name"),
                    ],
                    left_table=Table(table_name="users"),
                    right_table=Table(table_name="orders"),
                )
            ],
        )
        generator = SQLGenerator(self.query_builder)
        query = generator.generate(config)
        expected_query = (
            'SELECT "users"."id" "user_id","orders"."order_id" "order_id" FROM "users" "users" '
            'JOIN "orders" "orders" ON "users"."id"="orders"."user_id" AND "users"."name"="orders"."user_name"'
        )
        self.assertEqual(str(query), expected_query, f"Expected: {expected_query}, but got: {query}")

    def test_where_conditions(self):
        """测试条件筛选的 SQL 生成，包含普通字段和JSON字段"""
        config = SqlConfig(
            select_fields=[
                Field(table="users", raw_name="id", display_name="user_id", field_type=FieldType.INT),
            ],
            from_table=Table(table_name="users"),
            where=WhereCondition(
                connector=FilterConnector.AND,
                conditions=[
                    WhereCondition(
                        condition=Condition(
                            field=Field(
                                table="users", raw_name="age", display_name="user_age", field_type=FieldType.INT
                            ),
                            operator=Operator.EQ,
                            filter=18,
                        )
                    ),
                    WhereCondition(
                        condition=Condition(
                            field=Field(
                                table="users",
                                raw_name="country",
                                display_name="user_country",
                                field_type=FieldType.STRING,
                            ),
                            operator=Operator.EQ,
                            filter="Ireland",
                        )
                    ),
                    WhereCondition(
                        condition=Condition(
                            field=Field(
                                table="users",
                                raw_name="name",
                                display_name="user_name",
                                field_type=FieldType.STRING,
                            ),
                            operator=Operator.LIKE,
                            filter="%Jack%",
                        )
                    ),
                    WhereCondition(
                        condition=Condition(
                            field=Field(
                                table="users",
                                raw_name="address",
                                display_name="user_address",
                                field_type=FieldType.STRING,
                                keys=["k1", "k2"],  # JSON字段子key查询
                            ),
                            operator=Operator.EQ,
                            filter="Dublin",
                        )
                    ),
                ],
            ),
        )
        generator = SQLGenerator(self.query_builder)
        query = generator.generate(config)
        expected_query = (
            'SELECT "users"."id" "user_id" '
            'FROM "users" "users" '
            'WHERE "users"."age"=18 AND "users"."country"=\'Ireland\' '
            'AND "users"."name" LIKE \'%Jack%\' '
            'AND CAST(GET_JSON_OBJECT("users"."address",\'$.["k1"].["k2"]\') AS STRING)=\'Dublin\''
        )
        self.assertEqual(str(query), expected_query, f"Expected: {expected_query}, but got: {query}")

    def test_invalid_field_source(self):
        """测试无效字段来源的捕获"""
        config = SqlConfig(
            select_fields=[
                Field(table="invalid_table", raw_name="id", display_name="invalid_id", field_type=FieldType.INT),
            ],
            from_table=Table(table_name="users"),
        )
        generator = SQLGenerator(self.query_builder)
        with self.assertRaisesRegex(TableNotRegisteredError, r"表 'invalid_table' 未在配置中声明。"):
            generator.generate(config)

    def test_order_by_with_invalid_table(self):
        """测试排序字段来源不合法时的异常捕获"""
        config = SqlConfig(
            select_fields=[
                Field(table="users", raw_name="id", display_name="user_id", field_type=FieldType.INT),
            ],
            from_table=Table(table_name="users"),
            order_by=[
                Order(
                    field=Field(
                        table="orders", raw_name="date", display_name="order_date", field_type=FieldType.STRING
                    ),
                    order=pypikaOrder.desc,
                )
            ],
        )
        generator = SQLGenerator(self.query_builder)
        with self.assertRaisesRegex(TableNotRegisteredError, r"表 'orders' 未在配置中声明。"):
            generator.generate(config)

    def test_pagination_disabled(self):
        """测试无分页功能的查询"""
        config = SqlConfig(
            select_fields=[
                Field(table="users", raw_name="id", display_name="user_id", field_type=FieldType.INT),
            ],
            from_table=Table(table_name="users"),
        )
        generator = SQLGenerator(self.query_builder)
        query = generator.generate(config)
        expected_query = 'SELECT "users"."id" "user_id" FROM "users" "users"'
        self.assertEqual(str(query), expected_query, f"Expected: {expected_query}, but got: {query}")

    def test_multiple_join_tables(self):
        """测试多表 JOIN 的 SQL 生成"""
        config = SqlConfig(
            select_fields=[
                Field(table="users", raw_name="id", display_name="user_id", field_type=FieldType.INT),
                Field(table="orders", raw_name="order_id", display_name="order_id", field_type=FieldType.INT),
                Field(
                    table="products", raw_name="product_name", display_name="product_name", field_type=FieldType.STRING
                ),
            ],
            from_table=Table(table_name="users"),
            join_tables=[
                JoinTable(
                    join_type=JoinType.INNER_JOIN,
                    link_fields=[LinkField(left_field="id", right_field="user_id")],
                    left_table=Table(table_name="users"),
                    right_table=Table(table_name="orders"),
                ),
                JoinTable(
                    join_type=JoinType.LEFT_JOIN,
                    link_fields=[LinkField(left_field="order_id", right_field="id")],
                    left_table=Table(table_name="orders"),
                    right_table=Table(table_name="products"),
                ),
            ],
        )
        generator = SQLGenerator(self.query_builder)
        query = generator.generate(config)
        expected_query = (
            'SELECT "users"."id" "user_id","orders"."order_id" "order_id","products"."product_name" "product_name" '
            'FROM "users" "users" JOIN "orders" "orders" ON "users"."id"="orders"."user_id" '
            'LEFT JOIN "products" "products" ON "orders"."order_id"="products"."id"'
        )
        self.assertEqual(str(query), expected_query, f"Expected: {expected_query}, but got: {query}")

    def test_order_by_multiple_fields(self):
        """测试 ORDER BY 多字段"""
        config = SqlConfig(
            select_fields=[
                Field(table="users", raw_name="id", display_name="user_id", field_type=FieldType.INT),
            ],
            from_table=Table(table_name="users"),
            order_by=[
                Order(
                    field=Field(table="users", raw_name="age", display_name="user_age", field_type=FieldType.INT),
                    order=pypikaOrder.asc,
                ),
                Order(
                    field=Field(table="users", raw_name="name", display_name="user_name", field_type=FieldType.STRING),
                    order=pypikaOrder.desc,
                ),
            ],
        )
        generator = SQLGenerator(self.query_builder)
        query = generator.generate(config)
        expected_query = (
            'SELECT "users"."id" "user_id" FROM "users" "users" ORDER BY "users"."age" ASC,"users"."name" DESC'
        )
        self.assertEqual(str(query), expected_query, f"Expected: {expected_query}, but got: {query}")

    def test_group_by_with_where(self):
        """测试 GROUP BY 子句，包含普通字段和JSON字段"""
        config = SqlConfig(
            select_fields=[
                Field(
                    table="users", raw_name="id", display_name="user_id", field_type=FieldType.INT, aggregate="COUNT"
                ),
                Field(table="users", raw_name="country", display_name="user_country", field_type=FieldType.STRING),
                Field(
                    table="users",
                    raw_name="profile",
                    display_name="user_city",
                    field_type=FieldType.STRING,
                    keys=["address", "city"],  # 添加JSON字段子key查询
                ),
            ],
            from_table=Table(table_name="users"),
            group_by=[
                Field(table="users", raw_name="country", display_name="user_country", field_type=FieldType.STRING),
                Field(
                    table="users",
                    raw_name="profile",
                    display_name="user_city",
                    field_type=FieldType.STRING,
                    keys=["address", "city"],  # 分组字段也支持JSON子key
                ),
            ],
            where=WhereCondition(
                condition=Condition(
                    field=Field(
                        table="users", raw_name="country", display_name="user_country", field_type=FieldType.STRING
                    ),
                    operator=Operator.EQ,
                    filter="Ireland",
                )
            ),
        )
        generator = SQLGenerator(self.query_builder)
        query = generator.generate(config)
        expected_query = (
            'SELECT COUNT("users"."id") "user_id","users"."country" "user_country",'
            'CAST(GET_JSON_OBJECT("users"."profile",\'$.["address"].["city"]\') AS STRING) "user_city" '
            'FROM "users" "users" WHERE "users"."country"=\'Ireland\' '
            'GROUP BY "users"."country",CAST(GET_JSON_OBJECT("users"."profile",\'$.["address"].["city"]\') AS STRING)'
        )
        self.assertEqual(str(query), expected_query, f"Expected: {expected_query}, but got: {query}")

    def test_group_by_with_having(self):
        """
        测试在存在聚合字段的情况下，使用 HAVING 子句对聚合结果进行筛选，包含JSON字段
        """
        config = SqlConfig(
            select_fields=[
                Field(
                    table="orders",
                    raw_name="id",
                    display_name="count_id",
                    field_type=FieldType.INT,
                    aggregate=AggregateType.COUNT,
                ),
                Field(
                    table="orders",
                    raw_name="status",
                    display_name="status",
                    field_type=FieldType.STRING,
                ),
                Field(
                    table="orders",
                    raw_name="details",
                    display_name="product_category",
                    field_type=FieldType.STRING,
                    keys=["product", "category"],  # 添加JSON字段子key查询
                ),
            ],
            from_table=Table(table_name="orders"),
            group_by=[
                Field(
                    table="orders",
                    raw_name="status",
                    display_name="status",
                    field_type=FieldType.STRING,
                ),
                Field(
                    table="orders",
                    raw_name="details",
                    display_name="product_category",
                    field_type=FieldType.STRING,
                    keys=["product", "category"],  # 分组字段也支持JSON子key
                ),
            ],
            having=HavingCondition(
                condition=Condition(
                    field=Field(
                        table="orders",
                        raw_name="id",
                        display_name="count_id",
                        field_type=FieldType.INT,
                        aggregate=AggregateType.COUNT,
                    ),
                    operator=Operator.GT,
                    filter=100,
                )
            ),
        )
        generator = SQLGenerator(self.query_builder)
        query = generator.generate(config)

        expected_query = (
            'SELECT COUNT("orders"."id") "count_id","orders"."status" "status",'
            'CAST(GET_JSON_OBJECT("orders"."details",\'$.["product"].["category"]\') AS STRING) "product_category" '
            'FROM "orders" "orders" '
            'GROUP BY "orders"."status",'
            'CAST(GET_JSON_OBJECT("orders"."details",\'$.["product"].["category"]\') AS STRING) '
            'HAVING COUNT("orders"."id")>100'
        )
        self.assertEqual(str(query), expected_query, f"Expected: {expected_query}, but got: {query}")

    def test_auto_inferred_group_by(self):
        """
        测试自动推导 GROUP BY：如果没有指定 group_by，但存在聚合字段，则对非聚合字段进行分组，包含JSON字段
        """
        config = SqlConfig(
            select_fields=[
                Field(table="orders", raw_name="id", display_name="order_id", field_type=FieldType.INT),
                Field(
                    table="orders",
                    raw_name="amount",
                    display_name="amount_sum",
                    field_type=FieldType.INT,
                    aggregate=AggregateType.SUM,
                ),
                Field(
                    table="orders",
                    raw_name="details",
                    display_name="product_type",
                    field_type=FieldType.STRING,
                    keys=["product", "type"],  # 添加JSON字段子key查询
                ),
            ],
            from_table=Table(table_name="orders"),
        )
        generator = SQLGenerator(self.query_builder)
        query = generator.generate(config)
        # 期望自动分组 "id" 和 JSON字段
        expected_query = (
            'SELECT "orders"."id" "order_id",SUM("orders"."amount") "amount_sum",'
            'CAST(GET_JSON_OBJECT("orders"."details",\'$.["product"].["type"]\') AS STRING) "product_type" '
            'FROM "orders" "orders" '
            'GROUP BY "orders"."id",CAST(GET_JSON_OBJECT("orders"."details",\'$.["product"].["type"]\') AS STRING)'
        )
        self.assertEqual(str(query), expected_query, f"Expected: {expected_query}, got: {query}")

    def test_unsupported_operator(self):
        """测试不支持的 Operator 时抛出异常"""
        with self.assertRaises(ValidationError):
            config = SqlConfig(
                select_fields=[
                    Field(table="users", raw_name="id", display_name="user_id", field_type=FieldType.INT),
                ],
                from_table=Table(table_name="users"),
                where=WhereCondition(
                    condition=Condition(
                        field=Field(
                            table="users", raw_name="name", display_name="user_name", field_type=FieldType.STRING
                        ),
                        operator="unknown_op",
                        filter="test",
                        filters=[],
                    )
                ),
            )
            generator = SQLGenerator(self.query_builder)
            generator.generate(config)

    def test_nested_where_conditions(self):
        """
        测试复杂嵌套的 AND/OR 条件，仅使用 EQ / NEQ / REG / NREG / INCLUDE / EXCLUDE 操作符:
        """
        config = SqlConfig(
            select_fields=[
                Field(table="users", raw_name="id", display_name="user_id", field_type=FieldType.INT),
            ],
            from_table=Table(table_name="users"),
            where=WhereCondition(
                connector=FilterConnector.AND,
                conditions=[
                    WhereCondition(
                        connector=FilterConnector.OR,
                        conditions=[
                            WhereCondition(
                                condition=Condition(
                                    field=Field(
                                        table="users",
                                        raw_name="name",
                                        display_name="user_name",
                                        field_type=FieldType.STRING,
                                    ),
                                    operator=Operator.NEQ,
                                    filter="David",
                                    filters=[],
                                )
                            ),
                            WhereCondition(
                                condition=Condition(
                                    field=Field(
                                        table="users",
                                        raw_name="name",
                                        display_name="user_name",
                                        field_type=FieldType.STRING,
                                    ),
                                    operator=Operator.EQ,
                                    filter="Jack",
                                    filters=[],
                                )
                            ),
                        ],
                    ),
                ],
            ),
        )
        generator = SQLGenerator(self.query_builder)
        query = generator.generate(config)
        expected_query = (
            'SELECT "users"."id" "user_id" '
            'FROM "users" "users" '
            'WHERE "users"."name"<>\'David\' OR "users"."name"=\'Jack\''
        )
        self.assertEqual(str(query), expected_query, f"Expected: {expected_query}, got: {query}")

    def test_multiple_aggregates(self):
        """测试同一条 SELECT 中包含多个聚合字段"""
        config = SqlConfig(
            select_fields=[
                Field(
                    table="orders",
                    raw_name="id",
                    display_name="order_count",
                    field_type=FieldType.INT,
                    aggregate=AggregateType.COUNT,
                ),
                Field(
                    table="orders",
                    raw_name="amount",
                    display_name="amount_max",
                    field_type=FieldType.INT,
                    aggregate=AggregateType.MAX,
                ),
                Field(table="orders", raw_name="status", display_name="status", field_type=FieldType.STRING),
            ],
            from_table=Table(table_name="orders"),
        )
        generator = SQLGenerator(self.query_builder)
        query = generator.generate(config)
        expected_query = (
            'SELECT COUNT("orders"."id") "order_count",MAX("orders"."amount") "amount_max","orders"."status" "status" '
            'FROM "orders" "orders" GROUP BY "orders"."status"'
        )
        self.assertEqual(str(query), expected_query, f"Expected: {expected_query}, got: {query}")

    def test_invalid_aggregate_type(self):
        """测试不支持的聚合类型时，是否正确抛出异常"""
        with self.assertRaises(ValidationError):
            config = SqlConfig(
                select_fields=[
                    Field(
                        table="orders",
                        raw_name="price",
                        display_name="price_custom",
                        field_type=FieldType.INT,
                        aggregate="INVALID_AGG",
                    ),
                ],
                from_table=Table(table_name="orders"),
            )
            generator = SQLGenerator(self.query_builder)
            generator.generate(config)

    def test_multi_join_simple_where(self):
        """
        测试多表联表 + 简单 WHERE 条件
        """
        config = SqlConfig(
            select_fields=[
                Field(table="users", raw_name="id", display_name="user_id", field_type=FieldType.INT),
                Field(table="orders", raw_name="order_id", display_name="order_id", field_type=FieldType.INT),
                Field(table="products", raw_name="name", display_name="product_name", field_type=FieldType.STRING),
            ],
            from_table=Table(table_name="users"),
            join_tables=[
                JoinTable(
                    join_type=JoinType.INNER_JOIN,
                    link_fields=[LinkField(left_field="id", right_field="user_id")],
                    left_table=Table(table_name="users"),
                    right_table=Table(table_name="orders"),
                ),
                JoinTable(
                    join_type=JoinType.LEFT_JOIN,
                    link_fields=[LinkField(left_field="product_id", right_field="id")],
                    left_table=Table(table_name="orders"),
                    right_table=Table(table_name="products"),
                ),
            ],
            where=WhereCondition(
                condition=Condition(
                    field=Field(
                        table="users", raw_name="country", display_name="user_country", field_type=FieldType.STRING
                    ),
                    operator=Operator.EQ,
                    filter="Ireland",
                    filters=[],
                )
            ),
        )
        generator = SQLGenerator(self.query_builder)
        query = generator.generate(config)
        expected_query = (
            'SELECT "users"."id" "user_id","orders"."order_id" "order_id","products"."name" "product_name" '
            'FROM "users" "users" '
            'JOIN "orders" "orders" '
            'ON "users"."id"="orders"."user_id" '
            'LEFT JOIN "products" "products" '
            'ON "orders"."product_id"="products"."id" '
            'WHERE "users"."country"=\'Ireland\''
        )
        self.assertEqual(str(query), expected_query, f"Expected: {expected_query}, got: {query}")

    def test_multi_join_nested_where(self):
        """
        测试多表联表 + 复杂嵌套 WHERE 条件
        """
        config = SqlConfig(
            select_fields=[
                Field(table="users", raw_name="id", display_name="user_id", field_type=FieldType.INT),
            ],
            from_table=Table(table_name="users"),
            join_tables=[
                JoinTable(
                    join_type=JoinType.INNER_JOIN,
                    link_fields=[LinkField(left_field="id", right_field="user_id")],
                    left_table=Table(table_name="users"),
                    right_table=Table(table_name="orders"),
                ),
                JoinTable(
                    join_type=JoinType.LEFT_JOIN,
                    link_fields=[LinkField(left_field="product_id", right_field="id")],
                    left_table=Table(table_name="orders"),
                    right_table=Table(table_name="products"),
                ),
            ],
            where=WhereCondition(
                connector=FilterConnector.AND,
                conditions=[
                    WhereCondition(
                        connector=FilterConnector.OR,
                        conditions=[
                            WhereCondition(
                                condition=Condition(
                                    field=Field(
                                        table="users",
                                        raw_name="name",
                                        display_name="user_name",
                                        field_type=FieldType.STRING,
                                    ),
                                    operator=Operator.NEQ,
                                    filter="David",
                                    filters=[],
                                )
                            ),
                            WhereCondition(
                                condition=Condition(
                                    field=Field(
                                        table="users",
                                        raw_name="name",
                                        display_name="user_name",
                                        field_type=FieldType.STRING,
                                    ),
                                    operator=Operator.EQ,
                                    filter="Jack",
                                    filters=[],
                                )
                            ),
                        ],
                    ),
                    WhereCondition(
                        connector=FilterConnector.AND,
                        conditions=[
                            WhereCondition(
                                connector=FilterConnector.OR,
                                conditions=[
                                    WhereCondition(
                                        condition=Condition(
                                            field=Field(
                                                table="orders",
                                                raw_name="status",
                                                display_name="order_status",
                                                field_type=FieldType.STRING,
                                            ),
                                            operator=Operator.EQ,
                                            filter="pending",
                                            filters=[],
                                        )
                                    ),
                                    WhereCondition(
                                        condition=Condition(
                                            field=Field(
                                                table="orders",
                                                raw_name="status",
                                                display_name="order_status",
                                                field_type=FieldType.STRING,
                                            ),
                                            operator=Operator.NEQ,
                                            filter="canceled",
                                            filters=[],
                                        )
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        )
        generator = SQLGenerator(self.query_builder)
        query = generator.generate(config)
        expected_query = (
            'SELECT "users"."id" "user_id" '
            'FROM "users" "users" '
            'JOIN "orders" "orders" ON "users"."id"="orders"."user_id" '
            'LEFT JOIN "products" "products" ON "orders"."product_id"="products"."id" '
            'WHERE ("users"."name"<>\'David\' OR "users"."name"=\'Jack\') AND '
            '("orders"."status"=\'pending\' OR "orders"."status"<>\'canceled\')'
        )
        self.assertEqual(str(query), expected_query, f"Expected: {expected_query}, got: {query}")

    def test_multi_join_nested_having(self):
        """
        测试多表联表 + 嵌套 HAVING 条件
        """
        config = SqlConfig(
            select_fields=[
                Field(
                    table="orders",
                    raw_name="price",
                    display_name="total_price",
                    field_type=FieldType.INT,
                    aggregate=AggregateType.SUM,
                ),
                Field(
                    table="products",
                    raw_name="name",
                    display_name="product_name",
                    field_type=FieldType.STRING,
                ),
            ],
            from_table=Table(table_name="users"),
            join_tables=[
                JoinTable(
                    join_type=JoinType.INNER_JOIN,
                    link_fields=[LinkField(left_field="id", right_field="user_id")],
                    left_table=Table(table_name="users"),
                    right_table=Table(table_name="orders"),
                ),
                JoinTable(
                    join_type=JoinType.LEFT_JOIN,
                    link_fields=[LinkField(left_field="order_id", right_field="id")],
                    left_table=Table(table_name="orders"),
                    right_table=Table(table_name="products"),
                ),
            ],
            having=HavingCondition(
                connector=FilterConnector.AND,
                conditions=[
                    HavingCondition(
                        condition=Condition(
                            field=Field(
                                table="orders",
                                raw_name="price",
                                display_name="total_price",
                                field_type=FieldType.INT,
                                aggregate=AggregateType.SUM,
                            ),
                            operator=Operator.GT,
                            filter=100,
                        )
                    ),
                    HavingCondition(
                        condition=Condition(
                            field=Field(
                                table="orders",
                                raw_name="price",
                                display_name="total_price",
                                field_type=FieldType.INT,
                                aggregate=AggregateType.SUM,
                            ),
                            operator=Operator.LT,
                            filter=500,
                        )
                    ),
                ],
            ),
        )
        generator = SQLGenerator(self.query_builder)
        query = generator.generate(config)
        expected_query = (
            'SELECT SUM("orders"."price") "total_price","products"."name" "product_name" '
            'FROM "users" "users" '
            'JOIN "orders" "orders" ON "users"."id"="orders"."user_id" '
            'LEFT JOIN "products" "products" ON "orders"."order_id"="products"."id" GROUP BY "products"."name" '
            'HAVING SUM("orders"."price")>100 AND SUM("orders"."price")<500'
        )
        self.assertEqual(str(query), expected_query, f"Expected: {expected_query}, got: {query}")

    def test_join_with_aggregation_and_group_by(self):
        """
        测试联表 + 聚合函数 + 显式分组
        """
        config = SqlConfig(
            select_fields=[
                Field(
                    table="orders",
                    raw_name="price",
                    display_name="total_price",
                    field_type=FieldType.INT,
                    aggregate=AggregateType.SUM,
                ),
                Field(
                    table="users",
                    raw_name="country",
                    display_name="user_country",
                    field_type=FieldType.STRING,
                ),
            ],
            from_table=Table(table_name="users"),
            join_tables=[
                JoinTable(
                    join_type=JoinType.INNER_JOIN,
                    link_fields=[LinkField(left_field="id", right_field="user_id")],
                    left_table=Table(table_name="users"),
                    right_table=Table(table_name="orders"),
                )
            ],
            where=WhereCondition(
                condition=Condition(
                    field=Field(
                        table="users", raw_name="country", display_name="user_country", field_type=FieldType.STRING
                    ),
                    operator=Operator.EQ,
                    filter="Ireland",
                    filters=[],
                )
            ),
            having=HavingCondition(
                condition=Condition(
                    field=Field(
                        table="orders",
                        raw_name="price",
                        display_name="orders_price",
                        field_type=FieldType.INT,
                        aggregate=AggregateType.SUM,
                    ),
                    operator=Operator.GT,
                    filter="5",
                    filters=[],
                )
            ),
            group_by=[
                Field(table="users", raw_name="country", display_name="user_country", field_type=FieldType.STRING),
            ],
        )
        generator = SQLGenerator(self.query_builder)
        query = generator.generate(config)
        expected_query = (
            'SELECT SUM("orders"."price") "total_price","users"."country" "user_country" '
            'FROM "users" "users" '
            'JOIN "orders" "orders" ON "users"."id"="orders"."user_id" '
            'WHERE "users"."country"=\'Ireland\' '
            'GROUP BY "users"."country" '
            'HAVING SUM("orders"."price")>5'
        )
        self.assertEqual(str(query), expected_query, f"Expected: {expected_query}, got: {query}")

    def test_join_with_auto_group_by(self):
        """
        当 group_by 未指定，但出现聚合字段 + 非聚合字段时，应自动对非聚合字段进行分组
        """
        config = SqlConfig(
            select_fields=[
                Field(
                    table="orders",
                    raw_name="price",
                    display_name="total_price",
                    field_type=FieldType.INT,
                    aggregate=AggregateType.SUM,
                ),
                Field(
                    table="orders",
                    raw_name="status",
                    display_name="order_status",
                    field_type=FieldType.STRING,
                ),
            ],
            from_table=Table(table_name="users"),
            join_tables=[
                JoinTable(
                    join_type=JoinType.INNER_JOIN,
                    link_fields=[LinkField(left_field="id", right_field="user_id")],
                    left_table=Table(table_name="users"),
                    right_table=Table(table_name="orders"),
                )
            ],
        )
        generator = SQLGenerator(self.query_builder)
        query = generator.generate(config)
        expected_query = (
            'SELECT SUM("orders"."price") "total_price","orders"."status" "order_status" '
            'FROM "users" "users" '
            'JOIN "orders" "orders" ON "users"."id"="orders"."user_id" '
            'GROUP BY "orders"."status"'
        )
        self.assertEqual(str(query), expected_query, f"Expected: {expected_query}, got: {query}")

    def test_join_with_order_by_and_pagination(self):
        """
        测试联表 + 排序 + 分页
        """
        config = SqlConfig(
            select_fields=[
                Field(table="users", raw_name="id", display_name="user_id", field_type=FieldType.INT),
                Field(table="orders", raw_name="order_id", display_name="order_id", field_type=FieldType.INT),
            ],
            from_table=Table(table_name="users"),
            join_tables=[
                JoinTable(
                    join_type=JoinType.INNER_JOIN,
                    link_fields=[LinkField(left_field="id", right_field="user_id")],
                    left_table=Table(table_name="users"),
                    right_table=Table(table_name="orders"),
                )
            ],
            order_by=[
                Order(
                    field=Field(
                        table="orders", raw_name="created_at", display_name="created_at", field_type=FieldType.STRING
                    ),
                    order=pypikaOrder.desc,
                )
            ],
            pagination=Pagination(limit=10, offset=20),
        )
        generator = SQLGenerator(self.query_builder)
        query = generator.generate(config)
        expected_query = (
            'SELECT "users"."id" "user_id","orders"."order_id" "order_id" '
            'FROM "users" "users" '
            'JOIN "orders" "orders" ON "users"."id"="orders"."user_id" '
            'ORDER BY "orders"."created_at" DESC '
            'LIMIT 10 OFFSET 20'
        )
        self.assertEqual(str(query), expected_query, f"Expected: {expected_query}, got: {query}")

    def test_alias_normal_usage(self):
        """
        新增用例：测试在 from_table 和 join_tables 中，使用不同 alias 时是否能正确生成 SQL
        """
        config = SqlConfig(
            select_fields=[
                Field(
                    table="user_alias",
                    raw_name="id",
                    display_name="user_id",
                    field_type=FieldType.INT,
                ),
                Field(
                    table="order_alias",
                    raw_name="order_id",
                    display_name="order_id",
                    field_type=FieldType.INT,
                ),
            ],
            from_table=Table(table_name="users", alias="user_alias"),
            join_tables=[
                JoinTable(
                    join_type=JoinType.INNER_JOIN,
                    link_fields=[LinkField(left_field="id", right_field="user_id")],
                    left_table=Table(table_name="users", alias="user_alias"),
                    right_table=Table(table_name="orders", alias="order_alias"),
                )
            ],
        )
        generator = SQLGenerator(self.query_builder)
        query = generator.generate(config)
        expected_query = (
            'SELECT "user_alias"."id" "user_id","order_alias"."order_id" "order_id" '
            'FROM "users" "user_alias" '
            'JOIN "orders" "order_alias" ON "user_alias"."id"="order_alias"."user_id"'
        )
        self.assertEqual(str(query), expected_query, f"Expected: {expected_query}, but got: {query}")

    def test_json_field_cast_timestamp_to_long(self):
        """
        测试 TIMESTAMP 类型字段在 Hive 中 JSON 抽取后转换为 long（timestamp -> long）
        """
        config = SqlConfig(
            select_fields=[
                Field(
                    table="event_rt",
                    raw_name="raw",
                    display_name="timestamp_extracted",
                    field_type=FieldType.TIMESTAMP,
                    is_json=True,
                    keys=["timestamp"],
                )
            ],
            from_table=Table(table_name="event_rt"),
        )
        generator = SQLGenerator(self.query_builder)
        query = generator.generate(config)
        expected_sql = (
            'SELECT CAST(GET_JSON_OBJECT("event_rt"."raw",\'$.["timestamp"]\') AS LONG) "timestamp_extracted" '
            'FROM "event_rt" "event_rt"'
        )
        self.assertEqual(str(query), expected_sql)

    def test_json_field_cast_text_to_string(self):
        """
        测试 TEXT 类型字段在 Hive 中 JSON 抽取后转换为 string（text -> string）
        """
        config = SqlConfig(
            select_fields=[
                Field(
                    table="event_rt",
                    raw_name="raw",
                    display_name="text_extracted",
                    field_type=FieldType.TEXT.value,  # TEXT 类型
                    is_json=True,
                    keys=["text"],
                )
            ],
            from_table=Table(table_name="event_rt"),
        )
        generator = SQLGenerator(self.query_builder)
        query = generator.generate(config)
        expected_sql = (
            'SELECT CAST(GET_JSON_OBJECT("event_rt"."raw",\'$.["text"]\') AS STRING) "text_extracted" '
            'FROM "event_rt" "event_rt"'
        )

        self.assertEqual(str(query), expected_sql, msg=f"\nExpected:\n{expected_sql}\nGot:\n{str(query)}")


class TestSQLFunctions(TestCase):
    """核心函数输出验证"""

    def test_json_contains_function(self):
        expr = JsonContains(ValueWrapper("col"), '["a"]')
        self.assertEqual(str(expr), "JSON_CONTAINS('col','[\"a\"]')")
        expr_with_path = JsonContains(ValueWrapper("col"), '"a"', "$.path")
        self.assertEqual(str(expr_with_path), "JSON_CONTAINS('col','\"a\"','$.path')")

    def test_group_concat_function(self):
        expr = GroupConcat(ValueWrapper("field"))
        self.assertEqual(str(expr), "GROUP_CONCAT('field')")

    def test_concat_function(self):
        expr = Concat(ValueWrapper("a"), ValueWrapper("b"))
        self.assertEqual(str(expr), "CONCAT('a','b')")


class TestDorisVariantFieldSanitize(TestCase):
    def test_sanitize_variant_key_type_and_empty(self):
        """ _sanitize_variant_key 对类型和空字符串做校验 """
        field = DorisVariantField(keys=["k1"], name="snapshot_resource_type_info")
        # 非字符串 -> TypeError
        with self.assertRaises(TypeError):
            field._sanitize_variant_key(123)  # type: ignore[arg-type]
        # 空字符串 -> ValueError
        with self.assertRaises(ValueError):
            field._sanitize_variant_key("")

    def test_sanitize_variant_key_escape_injection_payload(self):
        """ 恶意 payload 作为 Variant keys 参与 Doris 查询条件时，会被 escape_string 转义，避免拼出可执行 SQL 片段"""
        payload = "foo'\''] !=0 or 1=1; --"
        builder = DorisQuerySQLBuilder(
            table="test_table",
            conditions=[
                {
                    "field": {
                        "raw_name": "snapshot_resource_type_info",
                        "keys": [payload],
                    },
                    "operator": QueryConditionOperator.EQ.value,
                    "filters": ["bk-audit"],
                }
            ],
            sort_list=[],
            page=1,
            page_size=10,
        )
        sql = builder.build_data_sql()

        field = DorisVariantField(keys=[payload], name="snapshot_resource_type_info")
        expected = field._sanitize_variant_key(payload)
        expected_fragment = f"[{DORIS_FIELD_KEY_QUOTE}{expected}{DORIS_FIELD_KEY_QUOTE}]"
        self.assertIn(expected_fragment, sql)
        # 模拟 escape_string 返回 bytes 类型，让 isinstance 分支执行
        with patch("pymysql.converters.escape_string", return_value=b"foo\\'\\'\\''] !=0 or 1=1; --"):
            field_bytes = DorisVariantField(
                keys=[payload],
                name="snapshot_resource_type_info",
            )
            expected_bytes = field_bytes._sanitize_variant_key(payload)
            expected_fragment_bytes = (
                f"[{DORIS_FIELD_KEY_QUOTE}{expected_bytes}{DORIS_FIELD_KEY_QUOTE}]"
            )
            builder_bytes = DorisQuerySQLBuilder(
                table="test_table",
                conditions=[
                    {
                        "field": {
                            "raw_name": "snapshot_resource_type_info",
                            "keys": [payload],
                        },
                        "operator": QueryConditionOperator.EQ.value,
                        "filters": ["bk-audit"],
                    }
                ],
                sort_list=[],
                page=1,
                page_size=10,
            )
            sql_bytes = builder_bytes.build_data_sql()
            self.assertIn(
                expected_fragment_bytes,
                sql_bytes,
                msg=f"\nExpected fragment (bytes):\n{expected_fragment_bytes}\nGot SQL:\n{sql_bytes}",
            )

    def test_format_keys_quote_normal_keys(self):
        """ 正常 keys: ["k1", "k2"] => "['k1']['k2']"（或使用 DORIS_FIELD_KEY_QUOTE） """
        field = DorisVariantField(
            keys=["k1", "k2"],
            name="snapshot_resource_type_info",
        )
        sql_fragment = field.format_keys_quote()
        self.assertEqual(
            sql_fragment,
            (
                f"[{DORIS_FIELD_KEY_QUOTE}k1{DORIS_FIELD_KEY_QUOTE}]"
                f"[{DORIS_FIELD_KEY_QUOTE}k2{DORIS_FIELD_KEY_QUOTE}]"
            ),
        )

    @patch("core.sql.builder.terms.escape_string")
    def test_sanitize_variant_key_escape_return_bytes(self, mock_escape_string):
        """ 当 escape_string 返回 bytes 时，_sanitize_variant_key 能正确 decode 成 str """
        mock_escape_string.return_value = b"escaped_payload"
        field = DorisVariantField(keys=["k1"], name="snapshot_resource_type_info")
        result = field._sanitize_variant_key("foo")
        # 确认调用了 escape_string
        mock_escape_string.assert_called_once_with("foo")
        # 确认最终返回的是 str，而不是 bytes
        self.assertIsInstance(result, str)
        self.assertEqual(result, "escaped_payload")

    def test_variant_like_with_injection_payload(self):
        """
        恶意 payload 作为 LIKE 条件参与 Variant 查询时：
        - 字段访问仍然是 snapshot_resource_type_info['id'] 这种受控形式
        """
        payload =r"foo'\''] !=0 or 1=1; --"

        builder = DorisQuerySQLBuilder(
            table="test_table",
            conditions=[
                {
                    "field": {
                        "raw_name": "snapshot_resource_type_info",
                        "keys": ["id"],
                    },
                    "operator": QueryConditionOperator.LIKE.value,
                    "filters": [payload],
                }
            ],
            sort_list=[],
            page=1,
            page_size=10,
        )

        sql = builder.build_data_sql()
        print(sql)
        self.assertIn("`snapshot_resource_type_info`['id']", sql)

        # 2）确认是 LIKE 查询，并且前缀形如 LIKE '%foo...'
        self.assertIn("LIKE '%foo", sql)

        expected_sub = "foo''\\''''] !=0 or 1=1; --"
        self.assertIn(
            expected_sub,
            sql,
            msg=f"\n原始 payload:\n{payload}\n"
                f"期望转义后片段:\n{expected_sub}\n"
                f"实际 SQL:\n{sql}",
        )


