import importlib
import json
from pathlib import Path

from django.test import SimpleTestCase

from apps.permission.handlers.resource_types import ResourceEnum

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def load_iam_operations():
    return json.loads((BACKEND_ROOT / "support-files/iam/initial.json").read_text())["operations"]


class IAMInitialResourceTypeTests(SimpleTestCase):
    def test_risk_person_index_declared_in_iam_initial_json(self):
        resource_type = next(
            (
                operation["data"]
                for operation in load_iam_operations()
                if operation["operation"] == "upsert_resource_type"
                and operation["data"]["id"] == ResourceEnum.RISK_PERSON_INDEX.id
            ),
            None,
        )

        self.assertEqual(
            resource_type,
            {
                "id": "risk_person_index",
                "name": "风险人员索引",
                "name_en": "Risk Person Index",
                "description": "",
                "description_en": "",
                "parents": [],
                "provider_config": {"path": "/api/v1/iam/resources/"},
                "version": 1,
            },
        )

    def test_permission_migration_runs_iam_initial_json_for_risk_person_index(self):
        migration = importlib.import_module("apps.permission.migrations.0019_add_resource_type_risk_person_index")

        self.assertEqual(migration.Migration.migration_json, "initial.json")
        self.assertIn(("permission", "0018_update_action_resource_type"), migration.Migration.dependencies)
