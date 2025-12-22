# -*- coding: utf-8 -*-
"""
日志订阅 SQL 生成器测试
"""

from django.test import TestCase
from pypika.enums import Order as PypikaOrder

from core.sql.builder.builder import BKBaseQueryBuilder
from core.sql.builder.generator import BkBaseComputeSqlGenerator
from core.sql.constants import FieldType, FilterConnector, Operator
from core.sql.model import (
    Condition,
    Field,
    Order,
    Pagination,
    SqlConfig,
    Table,
    WhereCondition,
)


class BkBaseComputeSqlGeneratorTest(TestCase):
    """测试 BkBaseComputeSqlGenerator - SELECT * 和 generate_count"""

    def setUp(self):
        """设置测试数据"""
        self.table_name = "591_test_table.doris"
        self.time_field = "dtEventTimeStamp"
        self.start_time = 1702368000000
        self.end_time = 1702371600000

        # 基础时间条件
        self.time_condition = WhereCondition(
            condition=Condition(
                field=Field(
                    table=self.table_name,
                    raw_name=self.time_field,
                    display_name=self.time_field,
                    field_type=FieldType.LONG,
                ),
                operator=Operator.BETWEEN,
                filters=[self.start_time, self.end_time],
            )
        )

        self.generator = BkBaseComputeSqlGenerator(BKBaseQueryBuilder())

    def test_select_all(self):
        """测试 SELECT * 查询"""
        sql_config = SqlConfig(
            from_table=Table(table_name=self.table_name),
            select_fields=[],  # 空列表表示 SELECT *
            where=self.time_condition,
            order_by=[
                Order(
                    field=Field(
                        table=self.table_name,
                        raw_name=self.time_field,
                        display_name=self.time_field,
                        field_type=FieldType.LONG,
                    ),
                    order=PypikaOrder.desc,
                )
            ],
            pagination=Pagination(limit=10, offset=0),
        )

        query = self.generator.generate(sql_config)
        sql = str(query)

        # 验证 SQL
        self.assertIn("SELECT *", sql)
        self.assertIn("FROM 591_test_table.doris", sql)
        self.assertIn("WHERE", sql)
        self.assertIn("`dtEventTimeStamp` BETWEEN", sql)
        self.assertIn("ORDER BY", sql)
        self.assertIn("LIMIT 10", sql)

    def test_select_specific_fields(self):
        """测试指定字段查询"""
        sql_config = SqlConfig(
            from_table=Table(table_name=self.table_name),
            select_fields=[
                Field(
                    table=self.table_name,
                    raw_name="field1",
                    display_name="field1",
                    field_type=FieldType.STRING,
                ),
                Field(
                    table=self.table_name,
                    raw_name="field2",
                    display_name="field2",
                    field_type=FieldType.STRING,
                ),
            ],
            where=self.time_condition,
            order_by=[
                Order(
                    field=Field(
                        table=self.table_name,
                        raw_name=self.time_field,
                        display_name=self.time_field,
                        field_type=FieldType.LONG,
                    ),
                    order=PypikaOrder.desc,
                )
            ],
            pagination=Pagination(limit=10, offset=0),
        )

        query = self.generator.generate(sql_config)
        sql = str(query)

        # 验证 SQL
        self.assertIn("`field1`", sql)
        self.assertIn("`field2`", sql)
        self.assertNotIn("SELECT *", sql)

    def test_generate_count(self):
        """测试 COUNT 查询"""
        sql_config = SqlConfig(
            from_table=Table(table_name=self.table_name),
            select_fields=[],
            where=self.time_condition,
        )

        count_query = self.generator.generate_count(sql_config)
        count_sql = str(count_query)

        # 验证 COUNT SQL
        self.assertIn("SELECT COUNT(*)", count_sql)
        self.assertIn("`count`", count_sql)
        self.assertIn("FROM 591_test_table.doris", count_sql)
        self.assertIn("WHERE", count_sql)
        self.assertIn("LIMIT 1", count_sql)

    def test_or_condition(self):
        """测试 OR 条件"""
        # 条件1：system_id = 'bk_log'
        cond1 = WhereCondition(
            condition=Condition(
                field=Field(
                    table=self.table_name,
                    raw_name="system_id",
                    display_name="system_id",
                    field_type=FieldType.STRING,
                ),
                operator=Operator.EQ,
                filters=["bk_log"],
            )
        )

        # 条件2：system_id = 'bk_iam'
        cond2 = WhereCondition(
            condition=Condition(
                field=Field(
                    table=self.table_name,
                    raw_name="system_id",
                    display_name="system_id",
                    field_type=FieldType.STRING,
                ),
                operator=Operator.EQ,
                filters=["bk_iam"],
            )
        )

        # OR 组合
        or_condition = WhereCondition(connector=FilterConnector.OR, conditions=[cond1, cond2])

        # 最终条件：时间 AND (cond1 OR cond2)
        final_condition = WhereCondition(connector=FilterConnector.AND, conditions=[self.time_condition, or_condition])

        sql_config = SqlConfig(
            from_table=Table(table_name=self.table_name),
            select_fields=[],
            where=final_condition,
            pagination=Pagination(limit=10, offset=0),
        )

        query = self.generator.generate(sql_config)
        sql = str(query)

        # 验证 OR 逻辑
        self.assertIn("`system_id`='bk_log'", sql)
        self.assertIn("`system_id`='bk_iam'", sql)
        self.assertIn("OR", sql)

    def test_pagination(self):
        """测试分页"""
        sql_config = SqlConfig(
            from_table=Table(table_name=self.table_name),
            select_fields=[],
            where=self.time_condition,
            pagination=Pagination(limit=20, offset=40),
        )

        query = self.generator.generate(sql_config)
        sql = str(query)

        # 验证分页
        self.assertIn("LIMIT 20", sql)
        self.assertIn("OFFSET 40", sql)
