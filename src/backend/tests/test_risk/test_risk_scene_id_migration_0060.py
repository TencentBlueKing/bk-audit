# -*- coding: utf-8 -*-
"""Risk.scene_id 迁移 0060 的结构守卫与中断恢复测试。"""
import importlib
from unittest import mock

from django.apps import apps
from django.db import connection
from django.test import TestCase

from services.web.risk.models import Risk

migration_0060 = importlib.import_module("services.web.risk.migrations.0060_add_risk_scene_id_and_backfill")


class _State:
    """最小化的 to_state 替身，仅暴露 .apps 供 get_model 使用。"""

    apps = apps


class _FakeSchemaEditor:
    """记录被执行的 SQL，避免真正改动测试库结构。"""

    def __init__(self, connection_):
        self.executed_sql = []
        self.connection = connection_

    def execute(self, sql, params=None):
        self.executed_sql.append(sql)

    def _create_index_name(self, table, column_names, *args, **kwargs):
        # 复用 Django 真实命名规则，保证与迁移内部调用一致
        with connection.schema_editor() as real_editor:
            return real_editor._create_index_name(table, column_names, *args, **kwargs)

    def _create_index_sql(self, model, *, fields=None, name=None, **kwargs):
        columns = ", ".join(field.column for field in fields or [])
        return "CREATE INDEX {} ON {} ({})".format(name, model._meta.db_table, columns)


def _expected_index_name_of(field) -> str:
    """复用 Django 真实命名规则，得到 db_index=True 字段的预期索引名。"""
    with connection.schema_editor() as schema_editor:
        return schema_editor._create_index_name(Risk._meta.db_table, [field.column])


class TestRiskSceneIdMigration0060(TestCase):
    def _make_operation(self):
        field = Risk._meta.get_field("scene_id")
        return migration_0060.SafeAddField(
            model_name="risk",
            name="scene_id",
            field=field,
        )

    def _run(self, operation, column_is_present: bool, index_is_present: bool):
        schema_editor = _FakeSchemaEditor(connection)
        with mock.patch.object(migration_0060, "column_exists", return_value=column_is_present), mock.patch.object(
            migration_0060, "index_exists", return_value=index_is_present
        ):
            operation.database_forwards("risk", schema_editor, _State(), _State())
        return schema_editor

    def test_column_exists_skips_add_field_and_recovers_index(self):
        """列已存在但索引缺失时：跳过加列，并补齐预期的 db_index 索引。"""
        operation = self._make_operation()
        expected_index = _expected_index_name_of(Risk._meta.get_field("scene_id"))

        schema_editor = self._run(operation, column_is_present=True, index_is_present=False)

        # 不再执行 ADD COLUMN，而是补建索引
        self.assertFalse(any("ADD COLUMN" in sql for sql in schema_editor.executed_sql))
        self.assertTrue(any("CREATE INDEX" in sql for sql in schema_editor.executed_sql))
        self.assertTrue(any(expected_index in sql for sql in schema_editor.executed_sql))

    def test_column_exists_and_index_exists_skips_recreation(self):
        """列与索引都已存在时：不重复创建索引，保证迁移可幂等重跑。"""
        operation = self._make_operation()

        schema_editor = self._run(operation, column_is_present=True, index_is_present=True)

        self.assertEqual(schema_editor.executed_sql, [])

    def test_column_missing_falls_back_to_default_add_field(self):
        """列不存在时仍走 Django 原生 AddField 路径。"""
        operation = self._make_operation()

        schema_editor = _FakeSchemaEditor(connection)
        with mock.patch.object(migration_0060, "column_exists", return_value=False):
            with mock.patch.object(migration_0060.migrations.AddField, "database_forwards") as super_forwards:
                operation.database_forwards("risk", schema_editor, _State(), _State())

        super_forwards.assert_called_once()

    def test_expected_index_name_matches_django_naming_rule(self):
        """补齐索引名必须复用 Django 自动命名，避免与后续变更分歧。"""
        field = Risk._meta.get_field("scene_id")

        schema_editor = _FakeSchemaEditor(connection)
        name = migration_0060._expected_field_index_name(schema_editor, Risk._meta.db_table, field)

        self.assertEqual(name, _expected_index_name_of(field))
