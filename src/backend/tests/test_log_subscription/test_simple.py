# -*- coding: utf-8 -*-
"""
日志订阅功能简化测试

由于项目的 OperateRecordModel 要求 created_by 字段，
这里提供简化的测试用例验证核心功能。
"""

from django.test import TestCase

from services.web.log_subscription.models import (
    LogDataSource,
    LogSubscription,
    LogSubscriptionItem,
)


class LogSubscriptionSimpleTest(TestCase):
    """日志订阅简化测试"""

    def setUp(self):
        """测试前准备"""
        self.test_user = "test_user"

    def test_data_source_creation(self):
        """测试数据源创建"""
        source = LogDataSource.objects.create(
            source_id="test_source",
            name="测试数据源",
            bkbase_table_id="591_test_table",
            storage_type="doris",
            created_by=self.test_user,
            updated_by=self.test_user,
        )

        self.assertEqual(source.source_id, "test_source")
        self.assertEqual(source.get_table_name(), "591_test_table.doris")

    def test_subscription_creation(self):
        """测试订阅配置创建"""
        subscription = LogSubscription.objects.create(
            name="测试订阅",
            is_enabled=True,
            created_by=self.test_user,
            updated_by=self.test_user,
        )

        self.assertEqual(subscription.name, "测试订阅")
        self.assertIsNotNone(subscription.token)

    def test_subscription_item_creation(self):
        """测试配置项创建"""
        subscription = LogSubscription.objects.create(
            name="测试订阅",
            created_by=self.test_user,
            updated_by=self.test_user,
        )

        source = LogDataSource.objects.create(
            source_id="test_source",
            name="测试数据源",
            bkbase_table_id="591_test_table",
            created_by=self.test_user,
            updated_by=self.test_user,
        )

        item = LogSubscriptionItem.objects.create(
            subscription=subscription,
            name="配置项1",
            condition={},
            created_by=self.test_user,
            updated_by=self.test_user,
        )
        item.data_sources.add(source)

        self.assertEqual(item.name, "配置项1")
        self.assertEqual(item.data_sources.count(), 1)

    def test_sql_generator(self):
        """测试 SQL 生成器"""

        from core.sql.builder.builder import BKBaseQueryBuilder
        from core.sql.builder.generator import BkBaseComputeSqlGenerator
        from core.sql.constants import FieldType, Operator
        from core.sql.model import (
            Condition,
            Field,
            Pagination,
            SqlConfig,
            Table,
            WhereCondition,
        )

        # 构建时间条件
        time_condition = WhereCondition(
            condition=Condition(
                field=Field(
                    table="591_test.doris",
                    raw_name="dtEventTimeStamp",
                    display_name="dtEventTimeStamp",
                    field_type=FieldType.LONG,
                ),
                operator=Operator.BETWEEN,
                filters=[1704067200000, 1704153600000],
            )
        )

        sql_config = SqlConfig(
            from_table=Table(table_name="591_test.doris"),
            select_fields=[],  # 空列表表示 SELECT *
            where=time_condition,
            pagination=Pagination(limit=10, offset=0),
        )

        generator = BkBaseComputeSqlGenerator(BKBaseQueryBuilder())
        query = generator.generate(sql_config)
        sql = str(query)

        self.assertIn("SELECT", sql)
        self.assertIn("FROM", sql)
        self.assertIn("WHERE", sql)
        self.assertIn("591_test.doris", sql)

    def test_sql_generator_with_fields(self):
        """测试 SQL 生成器 - 指定字段"""
        from core.sql.builder.builder import BKBaseQueryBuilder
        from core.sql.builder.generator import BkBaseComputeSqlGenerator
        from core.sql.constants import FieldType, Operator
        from core.sql.model import (
            Condition,
            Field,
            Pagination,
            SqlConfig,
            Table,
            WhereCondition,
        )

        time_condition = WhereCondition(
            condition=Condition(
                field=Field(
                    table="591_test.doris",
                    raw_name="dtEventTimeStamp",
                    display_name="dtEventTimeStamp",
                    field_type=FieldType.LONG,
                ),
                operator=Operator.BETWEEN,
                filters=[1704067200000, 1704153600000],
            )
        )

        sql_config = SqlConfig(
            from_table=Table(table_name="591_test.doris"),
            select_fields=[
                Field(
                    table="591_test.doris",
                    raw_name="field1",
                    display_name="field1",
                    field_type=FieldType.STRING,
                ),
                Field(
                    table="591_test.doris",
                    raw_name="field2",
                    display_name="field2",
                    field_type=FieldType.STRING,
                ),
            ],
            where=time_condition,
            pagination=Pagination(limit=10, offset=0),
        )

        generator = BkBaseComputeSqlGenerator(BKBaseQueryBuilder())
        query = generator.generate(sql_config)
        sql = str(query)

        self.assertIn("field1", sql)
        self.assertIn("field2", sql)

    def test_required_fields_validation(self):
        """测试必须筛选字段验证"""
        from core.sql.model import WhereCondition

        source = LogDataSource.objects.create(
            source_id="test_source",
            name="测试数据源",
            bkbase_table_id="591_test_table",
            required_filter_fields=["system_id"],
            created_by=self.test_user,
            updated_by=self.test_user,
        )

        # 有必须筛选字段但没有条件，应该失败
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            source.validate_required_fields(None)

        # 有条件但缺少必须字段，应该失败
        condition = WhereCondition.model_validate(
            {
                "condition": {
                    "field": {
                        "table": "t",
                        "raw_name": "other_field",
                        "display_name": "other_field",
                        "field_type": "string",
                    },
                    "operator": "eq",
                    "filters": ["value"],
                }
            }
        )
        with self.assertRaises(ValidationError):
            source.validate_required_fields(condition)

        # 包含必须字段，应该成功
        condition = WhereCondition.model_validate(
            {
                "condition": {
                    "field": {
                        "table": "t",
                        "raw_name": "system_id",
                        "display_name": "system_id",
                        "field_type": "string",
                    },
                    "operator": "eq",
                    "filters": ["value"],
                }
            }
        )
        self.assertTrue(source.validate_required_fields(condition))
