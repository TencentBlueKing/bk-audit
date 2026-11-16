"""验证Flow迁移清单只接受明确旧身份和当前租户的新引用。"""

from copy import deepcopy

from django.test import SimpleTestCase, override_settings

from services.web.bkbase import flow_migration


def migration_manifest(strategy_id=7):
    """审计预填旧身份，BKBase只补迁移结果、Ref和原输出RT。"""
    return {
        "schema_version": 1,
        "source": {"tenant": "legacy_a", "project_id": 11},
        "mappings": [
            {
                "strategy_id": strategy_id,
                "audit_namespace": "audit",
                "legacy_flow_id": 41,
                "flow": {"kind": "Flow", "tenant": "tenant_a", "namespace": "migrated", "name": "flow_41"},
                "output_rt_id": "7_existing_output",
                "migration_status": "succeeded",
            }
        ],
    }


class FlowMigrationManifestTests(SimpleTestCase):
    def validate(self, payload, **kwargs):
        return flow_migration.validate_manifest(
            payload,
            context={"tenant": "tenant_a"},
            legacy_tenant="legacy_a",
            legacy_project_id=11,
            limit=kwargs.get("limit", 20),
        )

    @override_settings(BKBASE_PROJECT_ID=999)
    def test_explicit_old_project_is_not_replaced_by_current_configuration(self):
        manifest = migration_manifest()
        self.assertEqual(self.validate(manifest), manifest["mappings"])

    def test_invalid_old_scope_format_and_unbounded_batches_are_rejected(self):
        for key, value in [("tenant", "other_legacy"), ("project_id", 12)]:
            payload = migration_manifest()
            payload["source"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.validate(payload)
        for payload in [
            [],
            {},
            {**migration_manifest(), "schema_version": True},
            {**migration_manifest(), "mappings": []},
            {**migration_manifest(), "mappings": [None]},
        ]:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.validate(payload)
        for limit in [0, 21]:
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                self.validate(migration_manifest(), limit=limit)

    def test_every_mapping_requires_exact_business_and_resource_identity(self):
        for field, value in [
            ("strategy_id", True),
            ("strategy_id", 0),
            ("legacy_flow_id", "41"),
            ("audit_namespace", ""),
            ("output_rt_id", ""),
            ("migration_status", "failed"),
        ]:
            payload = migration_manifest()
            payload["mappings"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.validate(payload)
        for field, value in [("kind", "ResultTable"), ("tenant", "tenant_b"), ("namespace", ""), ("name", "")]:
            payload = migration_manifest()
            payload["mappings"][0]["flow"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.validate(payload)

    def test_duplicate_strategy_old_flow_or_target_ref_is_rejected_before_any_reads(self):
        for duplicate in ["strategy_id", "legacy_flow_id", "flow"]:
            payload = migration_manifest()
            other = deepcopy(payload["mappings"][0])
            other.update(strategy_id=8, legacy_flow_id=42, flow={**other["flow"], "name": "flow_42"})
            other[duplicate] = deepcopy(payload["mappings"][0][duplicate])
            payload["mappings"].append(other)
            with self.subTest(duplicate=duplicate), self.assertRaises(ValueError):
                self.validate(payload)
        payload = migration_manifest()
        payload["mappings"] *= 21
        with self.assertRaises(ValueError):
            self.validate(payload)
