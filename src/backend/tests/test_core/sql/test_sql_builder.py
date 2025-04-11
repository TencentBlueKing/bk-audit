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

from pydantic import ValidationError
from pypika import Order as pypikaOrder
from pypika.queries import QueryBuilder

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
from core.sql.sql_builder import SQLGenerator
from tests.base import TestCase


class TestSQLGenerator(TestCase):
    def setUp(self):
        self.query_builder = QueryBuilder()

    def test_single_table_query(self):
        """测试单表查询的 SQL 生成"""
        config = SqlConfig(
            select_fields=[
                Field(table="users", raw_name="id", display_name="user_id", field_type=FieldType.INT),
                Field(table="users", raw_name="name", display_name="user_name", field_type=FieldType.STRING),
            ],
            from_table=Table(table_name="users"),  # 新增改动：使用 Table 对象，无 alias
        )
        query = SQLGenerator(self.query_builder).generate(config)
        expected_query = 'SELECT "users"."id" "user_id","users"."name" "user_name" FROM "users" "users"'
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

    def test_where_conditions(self):
        """测试条件筛选的 SQL 生成"""
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
                                table="users", raw_name="name", display_name="user_name", field_type=FieldType.STRING
                            ),
                            operator=Operator.LIKE,
                            filter="%Jack%",
                        )
                    ),
                    WhereCondition(
                        condition=Condition(
                            field=Field(
                                table="users", raw_name="name", display_name="user_name", field_type=FieldType.STRING
                            ),
                            operator=Operator.NOT_LIKE,
                            filter="%Mark%",
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
            'AND "users"."name" LIKE \'%Jack%\' AND NOT "users"."name" LIKE \'%Mark%\''
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
        """测试 GROUP BY 子句"""
        config = SqlConfig(
            select_fields=[
                Field(
                    table="users", raw_name="id", display_name="user_id", field_type=FieldType.INT, aggregate="COUNT"
                ),
                Field(table="users", raw_name="country", display_name="user_country", field_type=FieldType.STRING),
            ],
            from_table=Table(table_name="users"),
            group_by=[
                Field(table="users", raw_name="country", display_name="user_country", field_type=FieldType.STRING),
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
            'SELECT COUNT("users"."id") "user_id","users"."country" "user_country" '
            'FROM "users" "users" WHERE "users"."country"=\'Ireland\' GROUP BY "users"."country"'
        )
        self.assertEqual(str(query), expected_query, f"Expected: {expected_query}, but got: {query}")

    def test_group_by_with_having(self):
        """
        测试在存在聚合字段的情况下，使用 HAVING 子句对聚合结果进行筛选
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
            ],
            from_table=Table(table_name="orders"),
            group_by=[
                Field(
                    table="orders",
                    raw_name="status",
                    display_name="status",
                    field_type=FieldType.STRING,
                )
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
            'SELECT COUNT("orders"."id") "count_id","orders"."status" "status" '
            'FROM "orders" "orders" '
            'GROUP BY "orders"."status" '
            'HAVING COUNT("orders"."id")>100'
        )
        self.assertEqual(str(query), expected_query, f"Expected: {expected_query}, but got: {query}")

    def test_auto_inferred_group_by(self):
        """
        测试自动推导 GROUP BY：如果没有指定 group_by，但存在聚合字段，则对非聚合字段进行分组
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
            ],
            from_table=Table(table_name="orders"),
        )
        generator = SQLGenerator(self.query_builder)
        query = generator.generate(config)
        # 期望自动分组 "id"
        expected_query = (
            'SELECT "orders"."id" "order_id",SUM("orders"."amount") "amount_sum" '
            'FROM "orders" "orders" GROUP BY "orders"."id"'
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
