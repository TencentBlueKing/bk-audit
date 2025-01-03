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

import pytest
from pydantic import ValidationError
from pypika import Order as pypikaOrder
from pypika import Query

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
    JoinTable,
    LinkField,
    Order,
    Pagination,
    SqlConfig,
    WhereCondition,
)
from core.sql.sql_builder import SQLGenerator


def test_single_table_query():
    """测试单表查询的 SQL 生成"""
    query_builder = Query()
    config = SqlConfig(
        select_fields=[
            Field(table="users", raw_name="id", display_name="user_id", field_type=FieldType.INT),
            Field(table="users", raw_name="name", display_name="user_name", field_type=FieldType.STRING),
        ],
        from_table="users",
    )
    generator = SQLGenerator(query_builder, config)
    query = generator.generate()
    expected_query = 'SELECT "id" "user_id","name" "user_name" FROM "users"'
    assert str(query) == expected_query, f"Expected: {expected_query}, but got: {query}"


def test_join_table_query():
    """测试联表查询的 SQL 生成"""
    query_builder = Query()
    config = SqlConfig(
        select_fields=[
            Field(table="users", raw_name="id", display_name="user_id", field_type=FieldType.INT),
            Field(table="orders", raw_name="order_id", display_name="order_id", field_type=FieldType.INT),
        ],
        from_table="users",
        join_tables=[
            JoinTable(
                join_type=JoinType.INNER_JOIN,
                link_fields=[LinkField(left_field="id", right_field="user_id")],
                left_table="users",
                right_table="orders",
            )
        ],
    )
    generator = SQLGenerator(query_builder, config)
    query = generator.generate()
    expected_query = (
        'SELECT "users"."id" "user_id","orders"."order_id" "order_id" '
        'FROM "users" JOIN "orders" ON "users"."id"="orders"."user_id"'
    )
    assert str(query) == expected_query, f"Expected: {expected_query}, but got: {query}"


def test_where_conditions():
    """测试条件筛选的 SQL 生成"""
    query_builder = Query()
    config = SqlConfig(
        select_fields=[
            Field(table="users", raw_name="id", display_name="user_id", field_type=FieldType.INT),
        ],
        from_table="users",
        where=WhereCondition(
            connector=FilterConnector.AND,
            conditions=[
                WhereCondition(
                    condition=Condition(
                        field=Field(table="users", raw_name="age", display_name="user_age", field_type=FieldType.INT),
                        operator=Operator.EQ,
                        filter=18,
                    )
                ),
                WhereCondition(
                    condition=Condition(
                        field=Field(
                            table="users", raw_name="country", display_name="user_country", field_type=FieldType.STRING
                        ),
                        operator=Operator.EQ,
                        filter="Ireland",
                    )
                ),
            ],
        ),
    )
    generator = SQLGenerator(query_builder, config)
    query = generator.generate()
    expected_query = 'SELECT "id" "user_id" FROM "users" WHERE "age"=18 AND "country"=\'Ireland\''
    assert str(query) == expected_query, f"Expected: {expected_query}, but got: {query}"


def test_invalid_field_source():
    """测试无效字段来源的捕获"""
    query_builder = Query()
    config = SqlConfig(
        select_fields=[
            Field(table="invalid_table", raw_name="id", display_name="invalid_id", field_type=FieldType.INT),
        ],
        from_table="users",
    )
    generator = SQLGenerator(query_builder, config)
    with pytest.raises(TableNotRegisteredError, match="表 'invalid_table' 未在配置中声明。"):
        generator.generate()


def test_order_by_with_invalid_table():
    """测试排序字段来源不合法时的异常捕获"""
    query_builder = Query()
    config = SqlConfig(
        select_fields=[
            Field(table="users", raw_name="id", display_name="user_id", field_type=FieldType.INT),
        ],
        from_table="users",
        order_by=[
            Order(
                field=Field(table="orders", raw_name="date", display_name="order_date", field_type=FieldType.STRING),
                order=pypikaOrder.desc,
            )
        ],
    )
    generator = SQLGenerator(query_builder, config)
    with pytest.raises(TableNotRegisteredError, match="表 'orders' 未在配置中声明。"):
        generator.generate()


def test_pagination_disabled():
    """测试无分页功能的查询"""
    query_builder = Query()
    config = SqlConfig(
        select_fields=[
            Field(table="users", raw_name="id", display_name="user_id", field_type=FieldType.INT),
        ],
        from_table="users",
    )
    generator = SQLGenerator(query_builder, config)
    query = generator.generate()
    expected_query = 'SELECT "id" "user_id" FROM "users"'
    assert str(query) == expected_query, f"Expected: {expected_query}, but got: {query}"


def test_multiple_join_tables():
    """测试多表 JOIN 的 SQL 生成"""
    query_builder = Query()
    config = SqlConfig(
        select_fields=[
            Field(table="users", raw_name="id", display_name="user_id", field_type=FieldType.INT),
            Field(table="orders", raw_name="order_id", display_name="order_id", field_type=FieldType.INT),
            Field(table="products", raw_name="product_name", display_name="product_name", field_type=FieldType.STRING),
        ],
        from_table="users",
        join_tables=[
            JoinTable(
                join_type=JoinType.INNER_JOIN,
                link_fields=[LinkField(left_field="id", right_field="user_id")],
                left_table="users",
                right_table="orders",
            ),
            JoinTable(
                join_type=JoinType.LEFT_JOIN,
                link_fields=[LinkField(left_field="order_id", right_field="id")],
                left_table="orders",
                right_table="products",
            ),
        ],
    )
    generator = SQLGenerator(query_builder, config)
    query = generator.generate()
    expected_query = (
        'SELECT "users"."id" "user_id","orders"."order_id" "order_id","products"."product_name" "product_name" '
        'FROM "users" JOIN "orders" ON "users"."id"="orders"."user_id" '
        'LEFT JOIN "products" ON "orders"."order_id"="products"."id"'
    )
    assert str(query) == expected_query, f"Expected: {expected_query}, but got: {query}"


def test_order_by_multiple_fields():
    """测试 ORDER BY 多字段"""
    query_builder = Query()
    config = SqlConfig(
        select_fields=[
            Field(table="users", raw_name="id", display_name="user_id", field_type=FieldType.INT),
        ],
        from_table="users",
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
    generator = SQLGenerator(query_builder, config)
    query = generator.generate()
    expected_query = 'SELECT "id" "user_id" FROM "users" ORDER BY "age" ASC,"name" DESC'
    assert str(query) == expected_query, f"Expected: {expected_query}, but got: {query}"


def test_group_by_with_having():
    """测试 GROUP BY 子句"""
    query_builder = Query()
    config = SqlConfig(
        select_fields=[
            Field(table="users", raw_name="id", display_name="user_id", field_type=FieldType.INT, aggregate="COUNT"),
            Field(table="users", raw_name="country", display_name="user_country", field_type=FieldType.STRING),
        ],
        from_table="users",
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
    generator = SQLGenerator(query_builder, config)
    query = generator.generate()
    expected_query = (
        'SELECT COUNT("id") "user_id","country" "user_country" FROM '
        '"users" WHERE "country"=\'Ireland\' GROUP BY "country"'
    )
    assert str(query) == expected_query, f"Expected: {expected_query}, but got: {query}"


def test_auto_inferred_group_by():
    """测试自动推导 GROUP BY：如果没有指定 group_by，但存在聚合字段，则对非聚合字段进行分组"""
    query_builder = Query()
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
        from_table="orders",
    )
    generator = SQLGenerator(query_builder, config)
    query = generator.generate()
    # 期望自动分组 "id"
    expected_query = 'SELECT "id" "order_id",SUM("amount") "amount_sum" FROM "orders" GROUP BY "id"'
    assert str(query) == expected_query, f"Expected: {expected_query}, got: {query}"


def test_unsupported_operator():
    """测试不支持的 Operator 时抛出异常"""
    query_builder = Query()
    with pytest.raises(ValidationError):
        config = SqlConfig(
            select_fields=[
                Field(table="users", raw_name="id", display_name="user_id", field_type=FieldType.INT),
            ],
            from_table="users",
            where=WhereCondition(
                condition=Condition(
                    field=Field(table="users", raw_name="name", display_name="user_name", field_type=FieldType.STRING),
                    operator="unknown_op",  # 这里传入一个无效操作符
                    filter="test",
                    filters=[],
                )
            ),
        )
        generator = SQLGenerator(query_builder, config)

        generator.generate()


def test_nested_where_conditions():
    """
    测试复杂嵌套的 AND/OR 条件，仅使用 EQ / NEQ / REG / NREG / INCLUDE / EXCLUDE 操作符:
    """
    query_builder = Query()
    config = SqlConfig(
        select_fields=[
            Field(table="users", raw_name="id", display_name="user_id", field_type=FieldType.INT),
        ],
        from_table="users",
        where=WhereCondition(
            connector=FilterConnector.AND,  # 顶层使用 AND
            conditions=[
                WhereCondition(
                    connector=FilterConnector.OR,  # 子条件使用 OR
                    conditions=[
                        WhereCondition(
                            condition=Condition(
                                field=Field(
                                    table="users",
                                    raw_name="name",
                                    display_name="user_name",
                                    field_type=FieldType.STRING,
                                ),
                                operator=Operator.NEQ,  # name != 'David'
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
                                operator=Operator.EQ,  # name = 'Jack'
                                filter="Jack",
                                filters=[],
                            )
                        ),
                    ],
                ),
                WhereCondition(
                    condition=Condition(
                        field=Field(
                            table="users", raw_name="country", display_name="user_country", field_type=FieldType.STRING
                        ),
                        operator=Operator.REG,  # country ~ '^Ire'
                        filter="^Ire",
                        filters=[],
                    )
                ),
            ],
        ),
    )
    generator = SQLGenerator(query_builder, config)
    query = generator.generate()

    expected_query = (
        'SELECT "id" "user_id" FROM "users" WHERE ("name"<>\'David\' OR "name"=\'Jack\') AND "country" REGEX \'^Ire\''
    )

    assert str(query) == expected_query, f"Expected: {expected_query}, got: {query}"


def test_multiple_aggregates():
    """测试同一条 SELECT 中包含多个聚合字段"""
    query_builder = Query()
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
        from_table="orders",
    )
    generator = SQLGenerator(query_builder, config)
    query = generator.generate()
    # 期望自动分组 "status"
    expected_query = (
        'SELECT COUNT("id") "order_count",MAX("amount") "amount_max","status" "status" FROM "orders" GROUP BY "status"'
    )
    assert str(query) == expected_query, f"Expected: {expected_query}, got: {query}"


def test_invalid_aggregate_type():
    """测试不支持的聚合类型时，是否正确抛出异常"""
    query_builder = Query()
    with pytest.raises(ValidationError):
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
            from_table="orders",
        )
        generator = SQLGenerator(query_builder, config)

        generator.generate()


def test_multi_join_simple_where():
    """
    测试多表联表 + 简单 WHERE 条件
    """
    query_builder = Query()
    config = SqlConfig(
        select_fields=[
            Field(table="users", raw_name="id", display_name="user_id", field_type=FieldType.INT),
            Field(table="orders", raw_name="order_id", display_name="order_id", field_type=FieldType.INT),
            Field(table="products", raw_name="name", display_name="product_name", field_type=FieldType.STRING),
        ],
        from_table="users",
        join_tables=[
            JoinTable(
                join_type=JoinType.INNER_JOIN,
                link_fields=[LinkField(left_field="id", right_field="user_id")],
                left_table="users",
                right_table="orders",
            ),
            JoinTable(
                join_type=JoinType.LEFT_JOIN,
                link_fields=[LinkField(left_field="product_id", right_field="id")],
                left_table="orders",
                right_table="products",
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
    generator = SQLGenerator(query_builder, config)
    query = generator.generate()
    expected_query = (
        'SELECT "users"."id" "user_id","orders"."order_id" "order_id","products"."name" "product_name" '
        'FROM "users" '
        'JOIN "orders" ON "users"."id"="orders"."user_id" '
        'LEFT JOIN "products" ON "orders"."product_id"="products"."id" '
        'WHERE "users"."country"=\'Ireland\''
    )
    assert str(query) == expected_query, f"Expected: {expected_query}, got: {query}"


def test_multi_join_nested_where():
    """
    测试多表联表 + 复杂嵌套 WHERE 条件
    """
    query_builder = Query()
    config = SqlConfig(
        select_fields=[
            Field(table="users", raw_name="id", display_name="user_id", field_type=FieldType.INT),
        ],
        from_table="users",
        join_tables=[
            JoinTable(
                join_type=JoinType.INNER_JOIN,
                link_fields=[LinkField(left_field="id", right_field="user_id")],
                left_table="users",
                right_table="orders",
            ),
            JoinTable(
                join_type=JoinType.LEFT_JOIN,
                link_fields=[LinkField(left_field="product_id", right_field="id")],
                left_table="orders",
                right_table="products",
            ),
        ],
        where=WhereCondition(
            connector=FilterConnector.AND,
            conditions=[
                # 条件A: (users.name != 'David' OR users.name = 'Jack')
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
                                operator=Operator.NEQ,  # name != 'David'
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
                                operator=Operator.EQ,  # name = 'Jack'
                                filter="Jack",
                                filters=[],
                            )
                        ),
                    ],
                ),
                # 条件B: ((orders.status = 'pending' OR orders.status != 'canceled') AND products.category ~ '^food$')
                WhereCondition(
                    connector=FilterConnector.AND,
                    conditions=[
                        # B1: (orders.status = 'pending' OR orders.status != 'canceled')
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
                        # B2: products.category ~ '^food$'
                        WhereCondition(
                            condition=Condition(
                                field=Field(
                                    table="products",
                                    raw_name="category",
                                    display_name="product_category",
                                    field_type=FieldType.STRING,
                                ),
                                operator=Operator.REG,
                                filter="^food$",
                                filters=[],
                            )
                        ),
                    ],
                ),
            ],
        ),
    )
    generator = SQLGenerator(query_builder, config)
    query = generator.generate()

    expected_query = (
        'SELECT "users"."id" "user_id" '
        'FROM "users" '
        'JOIN "orders" ON "users"."id"="orders"."user_id" '
        'LEFT JOIN "products" ON "orders"."product_id"="products"."id" '
        'WHERE ("users"."name"<>\'David\' OR "users"."name"=\'Jack\') AND '
        '("orders"."status"=\'pending\' OR "orders"."status"<>\'canceled\') AND "products"."category" REGEX \'^food$\''
    )

    assert str(query) == expected_query, f"Expected: {expected_query}, got: {query}"


def test_join_with_aggregation_and_group_by():
    """
    测试联表 + 聚合函数 + 显式分组
    """
    query_builder = Query()
    config = SqlConfig(
        select_fields=[
            Field(
                table="orders",
                raw_name="price",
                display_name="total_price",
                field_type=FieldType.INT,
                aggregate="SUM",  # 例如: SUM
            ),
            Field(
                table="users",
                raw_name="country",
                display_name="user_country",
                field_type=FieldType.STRING,
            ),
        ],
        from_table="users",
        join_tables=[
            JoinTable(
                join_type=JoinType.INNER_JOIN,
                link_fields=[LinkField(left_field="id", right_field="user_id")],
                left_table="users",
                right_table="orders",
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
        group_by=[
            Field(table="users", raw_name="country", display_name="user_country", field_type=FieldType.STRING),
        ],
    )
    generator = SQLGenerator(query_builder, config)
    query = generator.generate()
    expected_query = (
        'SELECT SUM("orders"."price") "total_price","users"."country" "user_country" '
        'FROM "users" '
        'JOIN "orders" ON "users"."id"="orders"."user_id" '
        'WHERE "users"."country"=\'Ireland\' '
        'GROUP BY "users"."country"'
    )
    assert str(query) == expected_query, f"Expected: {expected_query}, got: {query}"


def test_join_with_auto_group_by():
    """
    当 group_by 未指定，但出现聚合字段 + 非聚合字段时，应自动对非聚合字段进行分组
    """
    query_builder = Query()
    config = SqlConfig(
        select_fields=[
            # 聚合字段
            Field(
                table="orders",
                raw_name="price",
                display_name="total_price",
                field_type=FieldType.INT,
                aggregate="SUM",
            ),
            # 非聚合字段
            Field(
                table="orders",
                raw_name="status",
                display_name="order_status",
                field_type=FieldType.STRING,
            ),
        ],
        from_table="users",
        join_tables=[
            JoinTable(
                join_type=JoinType.INNER_JOIN,
                link_fields=[LinkField(left_field="id", right_field="user_id")],
                left_table="users",
                right_table="orders",
            )
        ],
    )
    generator = SQLGenerator(query_builder, config)
    query = generator.generate()
    expected_query = (
        'SELECT SUM("orders"."price") "total_price","orders"."status" "order_status" '
        'FROM "users" '
        'JOIN "orders" ON "users"."id"="orders"."user_id" '
        'GROUP BY "orders"."status"'
    )
    assert str(query) == expected_query, f"Expected: {expected_query}, got: {query}"


def test_join_with_order_by_and_pagination():
    """
    测试联表 + 排序 + 分页
    """
    query_builder = Query()
    config = SqlConfig(
        select_fields=[
            Field(table="users", raw_name="id", display_name="user_id", field_type=FieldType.INT),
            Field(table="orders", raw_name="order_id", display_name="order_id", field_type=FieldType.INT),
        ],
        from_table="users",
        join_tables=[
            JoinTable(
                join_type=JoinType.INNER_JOIN,
                link_fields=[LinkField(left_field="id", right_field="user_id")],
                left_table="users",
                right_table="orders",
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
    generator = SQLGenerator(query_builder, config)
    query = generator.generate()
    expected_query = (
        'SELECT "users"."id" "user_id","orders"."order_id" "order_id" '
        'FROM "users" '
        'JOIN "orders" ON "users"."id"="orders"."user_id" '
        'ORDER BY "orders"."created_at" DESC '
        'LIMIT 10 OFFSET 20'
    )
    assert str(query) == expected_query, f"Expected: {expected_query}, got: {query}"


if __name__ == "__main__":
    test_single_table_query()
    test_join_table_query()
    test_where_conditions()
    test_invalid_field_source()
    test_order_by_with_invalid_table()
    test_pagination_disabled()
    test_multiple_join_tables()
    test_group_by_with_having()
    test_auto_inferred_group_by()
    test_unsupported_operator()
    test_nested_where_conditions()
    test_multiple_aggregates()
    test_invalid_aggregate_type()
    test_multi_join_simple_where()
    test_multi_join_nested_where()
    test_join_with_aggregation_and_group_by()
    test_join_with_auto_group_by()
    test_join_with_order_by_and_pagination()
