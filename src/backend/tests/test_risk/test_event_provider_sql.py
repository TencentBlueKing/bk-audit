# -*- coding: utf-8 -*-
from core.sql.constants import AggregateType, FieldType
from tests.base import TestCase


class TestEventProviderSqlBuilder(TestCase):
    """测试 EventProviderSqlBuilder"""

    def test_build_aggregate_sql(self):
        """测试聚合 SQL 生成"""
        from services.web.risk.handlers.event_provider_sql import (
            EventFieldConfig,
            EventProviderSqlBuilder,
        )

        builder = EventProviderSqlBuilder(
            table_name="591_test_table_1.doris",
            strategy_id=123,
            raw_event_id="test_event",
            start_time=1000,
            end_time=2000,
        )
        field = EventFieldConfig(
            raw_name="用户名",
            display_name="count_username",
            aggregate=AggregateType.COUNT,
        )
        sql = builder.build_aggregate_sql([field])

        self.assertIn("COUNT", sql)
        self.assertIn("JSON_EXTRACT_STRING", sql)
        self.assertIn("用户名", sql)
        self.assertIn("strategy_id", sql)
        self.assertIn("count_username", sql)

    def test_build_latest_sql(self):
        """测试 Latest SQL 生成"""
        from services.web.risk.handlers.event_provider_sql import (
            EventFieldConfig,
            EventProviderSqlBuilder,
        )

        builder = EventProviderSqlBuilder(
            table_name="591_test_table_1.doris",
            strategy_id=123,
            raw_event_id="test_event",
            start_time=1000,
            end_time=2000,
        )
        field = EventFieldConfig(raw_name="用户名", display_name="latest_username")
        sql = builder.build_latest_sql([field])

        self.assertIn("DESC", sql)
        self.assertIn("LIMIT", sql)
        self.assertIn("JSON_EXTRACT_STRING", sql)
        self.assertIn("latest_username", sql)

    def test_build_first_sql(self):
        """测试 First SQL 生成"""
        from services.web.risk.handlers.event_provider_sql import (
            EventFieldConfig,
            EventProviderSqlBuilder,
        )

        builder = EventProviderSqlBuilder(
            table_name="591_test_table_1.doris",
            strategy_id=123,
            raw_event_id="test_event",
            start_time=1000,
            end_time=2000,
        )
        field = EventFieldConfig(raw_name="用户名", display_name="first_username")
        sql = builder.build_first_sql([field])

        self.assertIn("ASC", sql)
        self.assertIn("LIMIT", sql)
        self.assertIn("first_username", sql)

    def test_field_type_cast(self):
        """测试字段类型 CAST"""
        from services.web.risk.handlers.event_provider_sql import (
            EventFieldConfig,
            EventProviderSqlBuilder,
        )

        builder = EventProviderSqlBuilder(
            table_name="591_test_table_1.doris",
            strategy_id=123,
            raw_event_id="test_event",
            start_time=1000,
            end_time=2000,
        )
        field = EventFieldConfig(
            raw_name="操作起始时间",
            display_name="max_time",
            field_type=FieldType.LONG,
            aggregate=AggregateType.MAX,
        )
        sql = builder.build_aggregate_sql([field])

        self.assertIn("CAST", sql)
        self.assertIn("BIGINT", sql)

    def test_empty_fields_returns_none(self):
        """测试空字段列表返回 None"""
        from services.web.risk.handlers.event_provider_sql import (
            EventProviderSqlBuilder,
        )

        builder = EventProviderSqlBuilder(
            table_name="591_test_table_1.doris",
            strategy_id=123,
            raw_event_id="test_event",
            start_time=1000,
            end_time=2000,
        )

        self.assertIsNone(builder.build_aggregate_sql([]))
        self.assertIsNone(builder.build_first_sql([]))
        self.assertIsNone(builder.build_latest_sql([]))
