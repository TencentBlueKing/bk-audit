# -*- coding: utf-8 -*-
"""风险描述列和连接字符集要能存下 emoji。历史截断数据不在迁移里回填。"""

import importlib

from django.db import connection
from django.test import TestCase
from django.utils import timezone

from services.web.risk.models import Risk

EMOJI_CONTENT = "### \U0001f7e1 mock operator pasted mock content"


class CharsetMigrationDefinitionTest(TestCase):
    """字符集迁移应按表合并执行，且回退时保留 utf8mb4 列定义。"""

    def test_charset_migrations_group_columns_by_table_and_do_not_reverse(self):
        cases = (
            ("services.web.risk.migrations.0065_alter_risk_longtext_charset_utf8mb4", 4),
            ("services.web.strategy_v2.migrations.0028_alter_strategy_longtext_charset_utf8mb4", 2),
        )

        for module_path, expected_operation_count in cases:
            with self.subTest(module_path=module_path):
                migration = importlib.import_module(module_path).Migration
                self.assertEqual(len(migration.operations), expected_operation_count)
                self.assertTrue(all(operation.reverse_sql == operation.noop for operation in migration.operations))

        risk_migration = importlib.import_module(
            "services.web.risk.migrations.0065_alter_risk_longtext_charset_utf8mb4"
        ).Migration
        risk_table_sql = [operation.sql for operation in risk_migration.operations if "`risk_risk`" in operation.sql]
        self.assertEqual(len(risk_table_sql), 1)
        self.assertEqual(risk_table_sql[0].count("MODIFY COLUMN"), 5)


class EventContentCharsetTest(TestCase):
    def test_connection_and_event_content_column_are_utf8mb4(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT @@character_set_connection")
            self.assertEqual(cursor.fetchone()[0], "utf8mb4")
            cursor.execute(
                """
                SELECT CHARACTER_SET_NAME
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'risk_risk'
                  AND COLUMN_NAME = 'event_content'
                """
            )
            self.assertEqual(cursor.fetchone()[0], "utf8mb4")

    def test_event_content_roundtrip_keeps_emoji(self):
        risk = Risk.objects.create(
            strategy_id=1,
            event_time=timezone.now(),
            event_content=EMOJI_CONTENT,
            event_data={"event_content": EMOJI_CONTENT},
        )
        risk.refresh_from_db()
        self.assertEqual(risk.event_content, EMOJI_CONTENT)
