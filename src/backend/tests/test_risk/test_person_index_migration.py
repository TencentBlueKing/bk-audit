import importlib
from types import SimpleNamespace

from django.db import migrations
from django.test import SimpleTestCase
from django.utils import timezone


class _CaptureManager:
    def __init__(self):
        self.created_objs = []

    def using(self, _db_alias):
        return self

    def bulk_create(self, objs, batch_size=None, ignore_conflicts=False):
        self.created_objs = list(objs)


class _RiskPersonIndexModel:
    objects = _CaptureManager()

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class RiskPersonIndexMigrationTests(SimpleTestCase):
    def setUp(self):
        _RiskPersonIndexModel.objects = _CaptureManager()
        self.migration = importlib.import_module("services.web.risk.migrations.0057_riskpersonindex_risk_risk_level")

    def test_process_batch_sets_person_index_updated_at_for_incremental_bkbase_pull(self):
        risk = SimpleNamespace(
            risk_id="risk-migration",
            operator=["operator-a"],
            current_operator=["current-a"],
            notice_users=["notice-a"],
        )

        risk_count, person_count = self.migration.process_batch(_RiskPersonIndexModel, [risk], "default")

        self.assertEqual(risk_count, 1)
        self.assertEqual(person_count, 3)
        self.assertTrue(_RiskPersonIndexModel.objects.created_objs)
        for index_obj in _RiskPersonIndexModel.objects.created_objs:
            self.assertIsNotNone(index_obj.created_at)
            self.assertIsNotNone(index_obj.updated_at)
            self.assertTrue(timezone.is_aware(index_obj.updated_at))

    def test_process_batch_backfills_person_index_when_strategy_missing(self):
        risk = SimpleNamespace(
            risk_id="risk-missing-strategy",
            strategy_id=404,
            operator=["operator-a"],
            current_operator=["current-a"],
            notice_users=["notice-a"],
        )

        risk_count, person_count = self.migration.process_batch(_RiskPersonIndexModel, [risk], "default")

        self.assertEqual(risk_count, 1)
        self.assertEqual(person_count, 3)
        relation_users = {
            (index_obj.relation_type, index_obj.user) for index_obj in _RiskPersonIndexModel.objects.created_objs
        }
        self.assertEqual(
            relation_users,
            {
                ("operator", "operator-a"),
                ("current_operator", "current-a"),
                ("notice_user", "notice-a"),
            },
        )

    def test_migration_builds_new_indexes_after_backfill(self):
        operations = self.migration.Migration.operations
        run_python_indexes = [
            index for index, operation in enumerate(operations) if isinstance(operation, migrations.RunPython)
        ]
        backfill_index = run_python_indexes[0]
        post_check_index = run_python_indexes[-1]
        index_names = [operation.index.name for operation in operations if isinstance(operation, migrations.AddIndex)]

        self.assertEqual(len(run_python_indexes), 2)
        self.assertNotIn("risk_person_type_user_rid_idx", index_names)
        self.assertNotIn("risk_event_time_id_idx", index_names)
        for index, operation in enumerate(operations):
            if isinstance(operation, (migrations.AddIndex, migrations.AlterUniqueTogether)):
                self.assertGreater(index, backfill_index)
                self.assertLess(index, post_check_index)
            if isinstance(operation, migrations.AlterField) and operation.name == "risk_level":
                self.assertGreater(index, backfill_index)
                self.assertLess(index, post_check_index)

    def test_risk_level_order_migration_field_uses_choices(self):
        operation = next(
            operation
            for operation in self.migration.Migration.operations
            if isinstance(operation, migrations.AddField) and operation.name == "risk_level_order"
        )

        self.assertEqual(operation.field.choices, self.migration.MigrationRiskLevelOrder.choices)
        self.assertEqual(operation.field.default, self.migration.DEFAULT_RISK_LEVEL_ORDER)
