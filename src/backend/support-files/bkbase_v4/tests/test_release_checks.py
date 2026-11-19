"""Standalone release checks: no Django setup, database, Redis or network."""

import copy
import hashlib
import importlib.util
import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    """Load the standalone command without importing the application."""
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ref(kind, name):
    return {"kind": kind, "tenant": "tenant", "namespace": "legacy_project", "name": name}


def fixtures():
    """Hand-checked old-schema strategy and its formal migrated Flow evidence."""
    context = {
        "environment": "formal-a",
        "database": {"host": "db-a", "port": "3306", "name": "audit"},
        "source": {"tenant": "old-a", "project_id": 18},
        "tenant": "tenant",
        "namespaces": ["new_default", "legacy_project"],
        "release_version": "release-2",
        "source_version": "old-1",
        "application": "audit-a",
        "api_origin": "https://platform.example",
    }
    row = {
        "model": "strategy_v2.strategy",
        "pk": 7,
        "fields": {
            "namespace": "audit-a",
            "status": "disabled",
            "backend_data": {"flow_id": 41, "raw_table_name": "out", "node_id": 913},
            "configs": {"config_type": "EventLog", "data_source": {"rt_id": "22_in"}},
        },
    }
    mapping = {
        "strategy_id": 7,
        "audit_namespace": "audit-a",
        "legacy_flow_id": 41,
        "flow": ref("Flow", "flow-41"),
        "output_rt_id": "22_out",
        "migration_status": "succeeded",
    }
    body = {
        "kind": "Flow",
        "metadata": {
            **{key: value for key, value in mapping["flow"].items() if key != "kind"},
            "annotations": {"task_stopped": "true"},
        },
        "status": {"phase": "Ok"},
        "spec": {
            "current_status": "Stopped",
            "nodes": [
                {
                    "kind": "StreamNode",
                    "name": "old-node",
                    "output": "22_out",
                    "inputs": ["src"],
                    "config": {"sql": "SELECT event_id FROM input"},
                },
                {"kind": "StreamSourceNode", "name": "src", "data": ref("ResultTable", "input")},
            ],
        },
    }
    plan = {
        "schema_version": 1,
        "context": copy.deepcopy(context),
        "objects": [
            {
                "model": row["model"],
                "pk": row["pk"],
                "action": "migrate",
                "scenario": "flow",
                "mapping": mapping,
                "source": context["source"],
                "expected_state": "stopped",
                "checks": [
                    {
                        "topic": "fields",
                        "ref": ref("ResultTable", "input"),
                        "pointer": "/spec/fields",
                        "equals": [{"field_name": "event_id", "field_type": "string"}],
                    },
                    {
                        "topic": "rules",
                        "ref": mapping["flow"],
                        "pointer": "/spec/nodes/0/config/sql",
                        "equals": "SELECT event_id FROM input",
                    },
                ],
            }
        ],
    }
    before = {
        "manifest": {
            "database": context["database"],
            "created_at": "2026-11-17T08:00:00+00:00",
            "version": "old-1",
            "source": context["source"],
            "model_counts": {
                "strategy_v2.strategy": 1,
                "strategy_v2.linktable": 0,
                "databus.collectorplugin": 0,
                "databus.collectorconfig": 0,
                "databus.snapshot": 0,
                "meta.globalmetaconfig": 0,
            },
        },
        "rows": [row],
    }
    receipts = {
        "schema_version": 1,
        "context": context,
        "items": [
            {
                "ref": mapping["flow"],
                "method": "GET",
                "url": "https://platform.example/v4/tenants/tenant/namespaces/legacy_project/flows/flow-41/",
                "http_status": 200,
                "collected_at": "2026-11-17T09:00:00+00:00",
                "body": body,
            }
        ],
    }
    input_ref = ref("ResultTable", "input")
    receipts["items"].append(
        {
            "ref": input_ref,
            "method": "GET",
            "url": "https://platform.example/v4/namespaces/legacy_project/resulttables/input/",
            "http_status": 200,
            "collected_at": "2026-11-17T09:00:00+00:00",
            "body": {
                "kind": "ResultTable",
                "metadata": {k: input_ref[k] for k in ("tenant", "namespace", "name")},
                "spec": {
                    "predefiendResultTableId": "22_in",
                    "fields": [{"field_name": "event_id", "field_type": "string"}],
                },
                "status": {"phase": "Ok"},
            },
        }
    )
    return context, plan, before, receipts


def resource_fixtures():
    """Native plugin mapping in the existing resource-import manifest shape."""
    context, plan, before, receipts = fixtures()
    row = {
        "model": "databus.collectorplugin",
        "pk": 3,
        "fields": {
            "namespace": "audit-a",
            "collector_plugin_id": 52,
            "plugin_scene": "collector",
            "bkbase_processing_id": "22_clean",
            "bkbase_table_id": "22_logs",
            "has_storage": True,
            "has_replica_storage": True,
            "etl_params": {"retain": "business-secret"},
        },
    }
    mapping = {
        "owner": "plugin",
        "owner_pk": 3,
        "audit_namespace": "audit-a",
        "legacy": {"raw_data_id": 99, "processing_id": "22_clean", "result_table_id": "22_logs"},
        "data_id": ref("DataId", "native-id"),
        "clean": ref("Clean", "native-clean"),
        "result_table": ref("ResultTable", "native-table"),
        "storages": {
            "main": {
                "resource": ref("DataStorage", "main-storage"),
                "cluster": ref("ElasticSearch", "es-cluster"),
                "physical_table_name": "logs_{yyyyMMdd}",
            },
            "replica": {
                "resource": ref("DataStorage", "replica-storage"),
                "cluster": ref("Doris", "doris-cluster"),
                "physical_table_name": "audit.logs",
            },
        },
    }
    rules = [{"operator": {"type": "json_de"}, "output_id": "event_id"}]
    bodies = [
        (mapping["data_id"], {"predefined": {"dataId": 99}}),
        (
            mapping["clean"],
            {
                "raw_data_id": 99,
                "data_id": mapping["data_id"],
                "result_table_source": "new",
                "result_table_id": "22_logs",
                "current_status": "Running",
                "desired_status": "Running",
                "rules": rules,
                "config_revision": 3,
                "deploy_revision": 3,
            },
        ),
        (
            mapping["result_table"],
            {"predefiendResultTableId": "22_logs", "fields": [{"field_name": "event_id", "field_type": "string"}]},
        ),
    ]
    bodies.extend(
        (entry["resource"], {"tableInfo": {"source": mapping["result_table"], "storage": entry["cluster"]}})
        for entry in mapping["storages"].values()
    )
    receipts["items"] = []
    routes = {
        "DataId": "/v4/namespaces/{namespace}/dataids/{name}/",
        "Clean": "/v4/tenants/{tenant}/namespaces/{namespace}/cleans/{name}/",
        "ResultTable": "/v4/namespaces/{namespace}/resulttables/{name}/",
        "DataStorage": "/v4/tenants/{tenant}/namespaces/{namespace}/datastorages/{name}/",
    }
    for resource, spec in bodies:
        body = {
            "kind": resource["kind"],
            "metadata": {k: resource[k] for k in ("tenant", "namespace", "name")},
            "spec": spec,
            "status": {"phase": "Ok"},
        }
        receipts["items"].append(
            {
                "ref": resource,
                "method": "GET",
                "http_status": 200,
                "url": context["api_origin"] + routes[resource["kind"]].format(**resource),
                "collected_at": "2026-11-17T09:00:00+00:00",
                "body": body,
            }
        )
    before["rows"] = [row]
    plan["objects"] = [
        {
            "model": row["model"],
            "pk": 3,
            "action": "migrate",
            "scenario": "plugin",
            "mapping": mapping,
            "expected_state": "running",
            "checks": [
                {
                    "topic": "fields",
                    "ref": mapping["result_table"],
                    "pointer": "/spec/fields",
                    "equals": copy.deepcopy(bodies[2][1]["fields"]),
                },
                {"topic": "rules", "ref": mapping["clean"], "pointer": "/spec/rules", "equals": copy.deepcopy(rules)},
            ],
        }
    ]
    return context, plan, before, receipts


class ReleaseChecksTests(unittest.TestCase):
    def setUp(self):
        self.checks = load("release_checks")
        self.context, self.plan, self.before, self.receipts = fixtures()
        self.now = datetime(2026, 11, 17, 10, tzinfo=timezone.utc)

    def run_check(self, after=None):
        for item in self.receipts["items"]:
            item["body_sha256"] = self.checks.digest(item["body"])
        return self.checks.verify(self.context, self.plan, self.before, self.receipts, after=after, now=self.now)

    def assert_code(self, result, code):
        self.assertIn(code, [item["code"] for item in result["checks"]])
        self.assertNotEqual(result["status"], "PASS")

    def after(self):
        after = copy.deepcopy(self.before)
        after["manifest"]["created_at"] = "2026-11-17T09:30:00+00:00"
        after["manifest"]["version"] = "release-2"
        after["rows"][0]["fields"]["backend_data"]["bkbase_v4"] = {
            "flow": ref("Flow", "flow-41"),
            "output_name": "out",
            "output_rt_id": "22_out",
        }
        return after

    def test_old_schema_without_v4_column_and_originally_stopped_flow_pass(self):
        with patch.object(socket, "socket", side_effect=AssertionError("network forbidden")):
            result = self.run_check()
        self.assertEqual(result["status"], "NOT_CHECKED")
        self.assertNotIn("FAIL", [c["status"] for c in result["checks"]])
        self.assertEqual(result["verification_mode"], "provided_offline_evidence")

    def test_scope_omission_and_duplicate_are_rejected(self):
        self.plan["objects"] = []
        self.assert_code(self.run_check(), "SCOPE_MISSING")
        self.plan["objects"] = fixtures()[1]["objects"] * 2
        self.assert_code(self.run_check(), "SCOPE_DUPLICATE")

    def prepare_no_migration_scope(self, excluded):
        """Build legal empty or fully excluded inventory without GET evidence."""
        self.context, self.plan, self.before, self.receipts = fixtures()
        self.receipts["items"] = []
        if excluded:
            self.plan["objects"] = [
                {
                    "model": "strategy_v2.strategy",
                    "pk": 7,
                    "action": "exclude",
                    "reason": "Originally disabled object is outside this migration",
                }
            ]
        else:
            self.before["rows"] = []
            self.before["manifest"]["model_counts"] = dict.fromkeys(self.before["manifest"]["model_counts"], 0)
            self.plan["objects"] = []

    def test_legal_empty_or_all_excluded_scope_is_not_checked_before_and_after(self):
        for excluded in (False, True):
            for postflight in (False, True):
                with self.subTest(excluded=excluded, postflight=postflight):
                    self.prepare_no_migration_scope(excluded)
                    after = copy.deepcopy(self.before) if postflight else None
                    if after is not None:
                        after["manifest"]["version"] = self.context["release_version"]
                    result = self.run_check(after)
                    self.assertEqual(result["status"], "NOT_CHECKED")
                    self.assert_code(result, "NO_MIGRATION_OBJECTS")
                    self.assertNotIn("FAIL", [check["status"] for check in result["checks"]])

    def test_no_migration_does_not_downgrade_invalid_scope_to_not_checked(self):
        for fault, code in (
            ("missing", "SCOPE_MISSING"),
            ("duplicate", "SCOPE_DUPLICATE"),
            ("reason", "EXCLUSION_REASON"),
            ("objects_type", "INPUT_STRUCTURE"),
        ):
            with self.subTest(fault=fault):
                self.prepare_no_migration_scope(True)
                if fault == "missing":
                    self.plan["objects"] = []
                elif fault == "duplicate":
                    self.plan["objects"] *= 2
                elif fault == "reason":
                    self.plan["objects"][0]["reason"] = " "
                else:
                    self.plan["objects"] = {}
                    self.before["rows"] = []
                result = self.run_check()
                self.assertEqual(result["status"], "FAIL")
                self.assert_code(result, code)

    def test_mixed_scope_still_checks_migration_and_preserves_excluded_fields(self):
        self.before["rows"].append(
            {
                "model": "meta.globalmetaconfig",
                "pk": 8,
                "fields": {"config_key": "unrelated", "config_value": {"retain": "original"}},
            }
        )
        self.before["manifest"]["model_counts"]["meta.globalmetaconfig"] = 1
        self.plan["objects"].append(
            {
                "model": "meta.globalmetaconfig",
                "pk": 8,
                "action": "exclude",
                "reason": "Unrelated setting",
            }
        )
        for after in (None, self.after()):
            result = self.run_check(after)
            self.assertEqual(result["status"], "NOT_CHECKED")  # Flow semantic equivalence remains manual.
            self.assertNotIn("FAIL", [check["status"] for check in result["checks"]])
            codes = {check["code"] for check in result["checks"]}
            self.assertIn("OBJECT_CHECKED", codes)
            self.assertIn("EXCLUDED_BY_SCOPE", codes)
            self.assertNotIn("NO_MIGRATION_OBJECTS", codes)
        after = self.after()
        after["rows"][1]["fields"]["config_value"]["retain"] = "changed"
        result = self.run_check(after)
        self.assertEqual(result["status"], "FAIL")
        self.assert_code(result, "PRESERVATION")

    def test_real_cli_no_migration_scope_exits_one_and_reports_not_checked(self):
        for excluded in (False, True):
            for stage in ("preflight", "postflight"):
                with self.subTest(excluded=excluded, stage=stage), tempfile.TemporaryDirectory() as directory:
                    self.prepare_no_migration_scope(excluded)
                    self.before["manifest"]["created_at"] = datetime.now(timezone.utc).isoformat()
                    root = Path(directory)
                    args = [sys.executable, str(ROOT / "release_checks.py"), stage]
                    for name, content in (("context", self.context), ("plan", self.plan), ("receipts", self.receipts)):
                        filename = root / f"{name}.json"
                        filename.write_text(json.dumps(content))
                        args += [f"--{name}", str(filename)]
                    for name in ("before", "after") if stage == "postflight" else ("before",):
                        bundle = root / name
                        bundle.mkdir()
                        data = json.dumps(self.before["rows"]).encode()
                        (bundle / "business.json").write_bytes(data)
                        manifest = {
                            **self.before["manifest"],
                            "schema_version": 1,
                            "complete": True,
                            "fixture": "business.json",
                            "size_bytes": len(data),
                            "sha256": hashlib.sha256(data).hexdigest(),
                        }
                        if name == "after":
                            manifest["version"] = self.context["release_version"]
                        (bundle / "manifest.json").write_text(json.dumps(manifest))
                        args += [f"--{name}", str(bundle)]
                    args += ["--output", str(root / "report.json")]
                    completed = subprocess.run(args, capture_output=True, text=True, check=False)
                    self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
                    report = json.loads((root / "report.json").read_text())
                    self.assertEqual(report["status"], "NOT_CHECKED")
                    self.assert_code(report, "NO_MIGRATION_OBJECTS")

    def test_wrong_tenant_and_unapproved_namespace_are_rejected(self):
        self.plan["objects"][0]["mapping"]["flow"]["tenant"] = "another"
        self.assert_code(self.run_check(), "INVALID_REF")
        self.plan["objects"][0]["mapping"]["flow"] = {**ref("Flow", "flow-41"), "namespace": "guess"}
        self.assert_code(self.run_check(), "INVALID_REF")

    def test_wrong_flow_output_and_legacy_id_are_rejected(self):
        self.receipts["items"][0]["body"]["spec"]["nodes"][0]["output"] = "999_other"
        self.assert_code(self.run_check(), "FLOW_OUTPUT")
        self.plan["objects"][0]["mapping"]["legacy_flow_id"] = 42
        self.assert_code(self.run_check(), "LEGACY_IDENTITY")

    def test_missing_resource_state_and_contract_are_not_checked(self):
        self.receipts["items"] = []
        self.assert_code(self.run_check(), "RECEIPT_MISSING")
        self.receipts = fixtures()[3]
        del self.receipts["items"][0]["body"]["spec"]["current_status"]
        del self.receipts["items"][0]["body"]["metadata"]["annotations"]
        self.assert_code(self.run_check(), "STATE_MISSING")
        self.plan["objects"][0]["checks"] = []
        self.assert_code(self.run_check(), "CONTRACT_MISSING")

    def test_http_error_wrong_get_path_stale_and_api_error_fail(self):
        for field, value, code in [
            ("http_status", 403, "RECEIPT_HTTP"),
            ("method", "POST", "RECEIPT_METHOD"),
            (
                "url",
                "https://platform.example/v4/tenants/tenant/namespaces/legacy_project/flows/another/",
                "RECEIPT_URL",
            ),
            (
                "url",
                "https://elsewhere.example/v4/tenants/tenant/namespaces/legacy_project/flows/flow-41/",
                "RECEIPT_URL",
            ),
            ("collected_at", "2026-11-16T09:00:00+00:00", "RECEIPT_TIME"),
        ]:
            self.receipts = fixtures()[3]
            self.receipts["items"][0][field] = value
            with self.subTest(field=field, value=value):
                self.assert_code(self.run_check(), code)
        self.receipts = fixtures()[3]
        self.receipts["items"][0]["body"] = {"code": 403, "result": False}
        self.assert_code(self.run_check(), "RECEIPT_API")

    def test_modified_body_digest_is_rejected(self):
        item = self.receipts["items"][0]
        item["body_sha256"] = "0" * 64
        result = self.checks.verify(self.context, self.plan, self.before, self.receipts, now=self.now)
        self.assert_code(result, "RECEIPT_DIGEST")

    def test_effective_postflight_and_preserved_old_node_id_pass(self):
        self.assertEqual(self.run_check(after=self.after())["status"], "NOT_CHECKED")

    def test_changed_old_field_unrelated_config_and_wrong_binding_fail(self):
        for mutate, code in [
            (lambda a: a["rows"][0]["fields"]["backend_data"].update(node_id=999), "PRESERVATION"),
            (lambda a: a["rows"][0]["fields"].update(status="running"), "PRESERVATION"),
            (lambda a: a["rows"][0]["fields"]["configs"].update(extra="secret-body"), "PRESERVATION"),
            (
                lambda a: a["rows"][0]["fields"]["backend_data"]["bkbase_v4"].update(output_rt_id="22_wrong"),
                "LOCAL_BINDING",
            ),
        ]:
            after = self.after()
            mutate(after)
            result = self.run_check(after=after)
            self.assert_code(result, code)
            self.assertNotIn("secret-body", json.dumps(result))

    def test_extra_and_missing_postflight_objects_fail(self):
        after = self.after()
        after["rows"] = []
        self.assert_code(self.run_check(after=after), "POST_SCOPE")

    def config_change(self, key, value, pk):
        self.plan.setdefault("approved_config_changes", []).append(
            {"instance_key": "audit-a", "config_key": key, "config_value": value}
        )
        return {
            "model": "meta.globalmetaconfig",
            "pk": pk,
            "fields": {
                "config_level": "namespace",
                "instance_key": "audit-a",
                "config_key": key,
                "config_value": value,
            },
        }

    def test_postflight_allows_approved_v4_configuration_creation_and_update(self):
        storage = self.config_change("bkbase_v4_storage_clusters", {"es": {}}, 8)
        profile = self.config_change("bkbase_v4_flow_config", {"operation_config": {}}, 9)
        old = copy.deepcopy(storage)
        old["fields"].update(config_value={}, created_by="", updated_by="operator-1")
        self.before["rows"].append(old)
        self.before["manifest"]["model_counts"][old["model"]] = 1
        self.plan["objects"].append({"model": old["model"], "pk": 8, "action": "exclude", "reason": "V4 setup"})
        after = self.after()
        storage["fields"].update(created_by="operator-2", updated_by="operator-2", updated_at="2026-11-17T09:30:00Z")
        after["rows"][1:] = [storage, profile]
        self.assertEqual(self.run_check(after=after)["status"], "NOT_CHECKED")

    def test_postflight_rejects_wrong_or_missing_approved_configuration(self):
        profile = self.config_change("bkbase_v4_flow_config", {"operation_config": {"slots": 1}}, 9)
        after = self.after()
        self.assert_code(self.run_check(after=after), "APPROVED_CONFIG_IDENTITY")
        profile["fields"]["config_value"] = {"operation_config": {"slots": True}}
        after["rows"].append(profile)
        self.assert_code(self.run_check(after=after), "APPROVED_CONFIG_VALUE")

    def test_only_declared_v4_config_keys_are_eligible_for_changes(self):
        unrelated = self.config_change("unrelated", {}, 9)
        self.assert_code(self.run_check(), "APPROVED_CONFIG_STRUCTURE")
        self.plan.pop("approved_config_changes")
        after = self.after()
        after["rows"].append(unrelated)
        self.assert_code(self.run_check(after=after), "POST_SCOPE")

    def test_baseline_window_is_independent_of_fresh_receipts_and_after_export(self):
        self.context.update(max_baseline_age_seconds=86400, max_evidence_age_seconds=14400)
        self.plan["context"].update(self.context)
        self.before["manifest"]["created_at"] = (self.now - timedelta(hours=8)).isoformat()
        self.assertEqual(self.run_check()["status"], "NOT_CHECKED")
        self.assertEqual(self.run_check(after=self.after())["status"], "NOT_CHECKED")
        after = self.after()
        after["manifest"]["created_at"] = (self.now - timedelta(hours=5)).isoformat()
        self.assert_code(self.run_check(after=after), "SNAPSHOT_TIME")
        self.receipts["items"][0]["collected_at"] = (self.now - timedelta(hours=5)).isoformat()
        self.assert_code(self.run_check(), "RECEIPT_TIME")

    def test_even_a_configured_baseline_window_rejects_expired_evidence(self):
        self.context["max_baseline_age_seconds"] = 86400
        self.plan["context"].update(self.context)
        self.before["manifest"]["created_at"] = (self.now - timedelta(days=2)).isoformat()
        self.assert_code(self.run_check(), "SNAPSHOT_TIME")

    def test_reports_are_private_exclusive_and_only_contain_summaries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            self.checks.write_private(path, self.run_check())
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                self.checks.write_private(path, {})
            self.assertNotIn("event_id", path.read_text())

    def test_load_existing_bundle_rejects_incomplete_and_duplicate_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = self.before["rows"]
            data = json.dumps(rows).encode()
            (root / "business.json").write_bytes(data)
            manifest = {
                "schema_version": 1,
                "complete": True,
                "fixture": "business.json",
                "size_bytes": len(data),
                "sha256": self.checks.hash_bytes(data),
                "model_counts": {"strategy_v2.strategy": 1},
            }
            (root / "manifest.json").write_text(json.dumps(manifest))
            self.assertEqual(self.checks.read_bundle(root)["rows"], rows)
            manifest["model_counts"]["strategy_v2.strategy"] = 2
            (root / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                self.checks.read_bundle(root)

    def test_originally_disabled_strategy_cannot_be_declared_running(self):
        self.plan["objects"][0]["expected_state"] = "running"
        self.assert_code(self.run_check(), "LEGACY_STATE")

    def test_field_and_rule_labels_cannot_turn_arbitrary_identity_pointers_into_contract_checks(self):
        self.plan["objects"][0]["checks"][1] = {
            "topic": "rules",
            "ref": ref("Flow", "flow-41"),
            "pointer": "/spec/nodes/0/name",
            "equals": "old-node",
        }
        self.assert_code(self.run_check(), "CONTRACT_STRUCTURE")

    def test_plugin_manifest_accepts_original_target_when_remote_omits_physical_name(self):
        self.context, self.plan, self.before, self.receipts = resource_fixtures()
        self.assertEqual(self.run_check()["status"], "NOT_CHECKED")

    def test_missing_storage_wrong_cluster_and_duplicate_ownership_fail(self):
        for change, code in [
            (lambda: self.plan["objects"][0]["mapping"]["storages"].pop("replica"), "STORAGE_PURPOSE"),
            (
                lambda: self.receipts["items"][3]["body"]["spec"]["tableInfo"].update(
                    storage=ref("ElasticSearch", "wrong")
                ),
                "STORAGE_IDENTITY",
            ),
            (
                lambda: self.plan["objects"][0]["mapping"]["storages"]["replica"].update(
                    resource=ref("DataStorage", "main-storage")
                ),
                "STORAGE_DUPLICATE",
            ),
        ]:
            self.context, self.plan, self.before, self.receipts = resource_fixtures()
            change()
            self.assert_code(self.run_check(), code)

    def test_source_rt_and_rule_differences_fail_without_echoing_business_content(self):
        self.context, self.plan, self.before, self.receipts = resource_fixtures()
        self.receipts["items"][0]["body"]["spec"]["predefined"]["dataId"] = 100
        self.assert_code(self.run_check(), "SOURCE_IDENTITY")
        self.context, self.plan, self.before, self.receipts = resource_fixtures()
        self.receipts["items"][2]["body"]["spec"]["fields"][0]["field_type"] = "secret_changed_type"
        result = self.run_check()
        self.assert_code(result, "CONTRACT_DIFFERENCE")
        self.assertNotIn("secret_changed_type", json.dumps(result))

    def test_plugin_postflight_checks_actual_storages_and_preserves_unknown_keys(self):
        self.context, self.plan, self.before, self.receipts = resource_fixtures()
        mapping = self.plan["objects"][0]["mapping"]
        after = copy.deepcopy(self.before)
        after["manifest"]["version"] = "release-2"
        after["rows"][0]["fields"]["bkbase_v4_resources"] = {
            **{key: mapping[key] for key in ("data_id", "clean", "result_table")},
            "source_raw_data_id": 99,
            "result_table_id": "22_logs",
            "clean_role": "owner",
            "migration_import": mapping,
            "storages": {p: e["resource"] for p, e in mapping["storages"].items()},
            "physical_targets": {"main": "logs_%Y%m%d", "replica": "audit.logs"},
        }
        self.assertEqual(self.run_check(after=after)["status"], "NOT_CHECKED")
        after["rows"][0]["fields"]["bkbase_v4_resources"]["storages"]["replica"] = ref("DataStorage", "wrong")
        self.assert_code(self.run_check(after=after), "LOCAL_BINDING")

    def test_export_scope_version_and_declared_source_are_verified(self):
        self.before["manifest"]["version"] = "different-old-code"
        self.assert_code(self.run_check(), "SNAPSHOT_VERSION")
        self.before = fixtures()[2]
        self.before["manifest"]["source"] = {"tenant": "other", "project_id": 18}
        self.assert_code(self.run_check(), "LEGACY_SOURCE")
        self.before = fixtures()[2]
        self.before["manifest"].pop("model_counts")
        self.assert_code(self.run_check(), "EXPORT_SCOPE_NOT_CHECKED")

    def test_snapshot_binding_verifies_data_storage_and_ready_cluster_without_writes(self):
        inspector = self.checks.Inspector(self.context, self.now)
        table, cluster = ref("ResultTable", "rt"), ref("Redis", "redis")
        binding = {
            "kind": "RedisBinding",
            "metadata": {k: v for k, v in ref("RedisBinding", "binding").items() if k != "kind"},
            "spec": {"data": table, "storage": cluster},
            "status": {
                "phase": "Ok",
                "related": [
                    {
                        "kind": "Redis",
                        "metadata": {k: cluster[k] for k in ("tenant", "namespace", "name")},
                        "status": {"phase": "Ok"},
                    }
                ],
            },
        }
        body = {"status": {"phase": "Ok", "related": [binding]}}
        with patch.object(socket, "socket", side_effect=AssertionError("network forbidden")):
            inspector.table_binding(body, table, cluster, "redis", "snapshot")
        self.assertEqual(inspector.checks, [])
        binding["spec"]["data"] = ref("ResultTable", "other")
        with self.assertRaises(self.checks.Invalid):
            inspector.table_binding(body, table, cluster, "redis", "snapshot")

    def test_snapshot_postflight_uses_actual_binding_shape_and_storage_kinds(self):
        for data_type, role in (("asset", "owner"), ("basic", "existing")):
            with self.subTest(data_type=data_type):
                self.context, self.plan, self.before, self.receipts = resource_fixtures()
                item, row = self.plan["objects"][0], self.before["rows"][0]
                item.update(model="databus.snapshot", scenario="snapshot")
                row.update(model="databus.snapshot")
                row["fields"].update(bkbase_data_id=99, status="running", join_data_type=data_type)
                for model in ("databus.collectorplugin", "databus.snapshot"):
                    self.before["manifest"]["model_counts"][model] = int(model == "databus.snapshot")
                mapping = item["mapping"]
                data_source = ref("DataSource", "source")
                mapping["data_source"] = data_source
                self.receipts["items"].append(
                    {
                        "ref": data_source,
                        "method": "GET",
                        "http_status": 200,
                        "url": self.context["api_origin"]
                        + "/v4/tenants/tenant/namespaces/legacy_project/datasources/source/",
                        "collected_at": "2026-11-17T09:00:00+00:00",
                        "body": {
                            "kind": "DataSource",
                            "metadata": {
                                "tenant": "tenant",
                                "namespace": "legacy_project",
                                "name": "source",
                                "labels": {"raw_data_id": "99"},
                            },
                            "spec": {
                                "data_id": mapping["data_id"],
                                "current_status": "Running",
                                "desired_status": "Running",
                            },
                            "status": {"phase": "Ok"},
                        },
                    }
                )
                main, replica = mapping["storages"].values()
                mapping["storages"] = {
                    "hdfs": {"resource": main["resource"], "cluster": ref("Hdfs", "hdfs-cluster")},
                    "doris": {"resource": replica["resource"], "cluster": replica["cluster"]},
                }
                for body, info in zip(self.receipts["items"][3:5], mapping["storages"].values(), strict=True):
                    body["body"]["spec"]["tableInfo"]["storage"] = info["cluster"]
                self.receipts["items"][1]["body"]["metadata"]["labels"] = {"processing_id": "22_clean"}
                self.receipts["items"][1]["body"]["spec"]["result_table_source"] = (
                    "new" if role == "owner" else "existing"
                )
                item["expected_binding"] = {
                    **{k: mapping[k] for k in ("data_source", "data_id", "clean", "result_table")},
                    "raw_data_id": 99,
                    "result_table_id": "22_logs",
                    "clean_role": role,
                    "storages": {k: v["resource"] for k, v in mapping["storages"].items()},
                }
                after = copy.deepcopy(self.before)
                after["manifest"]["version"] = "release-2"
                after["rows"][0]["fields"]["bkbase_v4_resources"] = item["expected_binding"]
                result = self.run_check(after=after)
                self.assertEqual(result["status"], "NOT_CHECKED", result["checks"])

    def test_plugin_scene_cannot_be_relabelled_and_snapshot_scope_cannot_hide_unknown_binding_fields(self):
        self.context, self.plan, self.before, self.receipts = resource_fixtures()
        self.before["rows"][0]["fields"]["plugin_scene"] = "event"
        self.assert_code(self.run_check(), "PLUGIN_SCENE")

    def test_decoy_flow_cannot_supply_sql_or_fields_for_wrong_primary_flow(self):
        decoy = copy.deepcopy(self.receipts["items"][0])
        decoy["ref"]["name"] = "decoy"
        decoy["body"]["metadata"]["name"] = "decoy"
        decoy["url"] = "https://platform.example/v4/tenants/tenant/namespaces/legacy_project/flows/decoy/"
        self.receipts["items"].append(decoy)
        self.receipts["items"][0]["body"]["spec"]["nodes"][0]["config"]["sql"] = "wrong SQL"
        for check in self.plan["objects"][0]["checks"]:
            check["ref"] = decoy["ref"]
        self.assert_code(self.run_check(), "CONTRACT_UNRELATED_REF")

    def test_clean_desired_state_cannot_disagree_with_actual_state(self):
        self.context, self.plan, self.before, self.receipts = resource_fixtures()
        self.receipts["items"][1]["body"]["spec"]["desired_status"] = "Stopped"
        self.assert_code(self.run_check(), "TASK_DESIRED_STATE")
        self.receipts["items"][1]["body"]["spec"].pop("desired_status")
        self.assert_code(self.run_check(), "STATE_DESIRED_MISSING")

    def test_wrong_flow_source_cannot_be_approved_by_changing_declared_sql_expectation(self):
        self.receipts["items"][1]["body"]["spec"]["predefiendResultTableId"] = "22_entirely_wrong_rt"
        self.plan["objects"][0]["checks"][1]["equals"] = "SELECT * FROM entirely_wrong_rt"
        self.receipts["items"][0]["body"]["spec"]["nodes"][0]["config"]["sql"] = "SELECT * FROM entirely_wrong_rt"
        self.assert_code(self.run_check(), "FLOW_SOURCE_IDENTITY")

    def test_event_plugin_cannot_override_existing_globalmeta_physical_target(self):
        self.context, self.plan, self.before, self.receipts = resource_fixtures()
        fields = self.before["rows"][0]["fields"]
        fields.update(plugin_scene="event", has_replica_storage=False)
        item = self.plan["objects"][0]
        item["scenario"] = item["mapping"]["owner"] = "event_plugin"
        item["mapping"]["storages"].pop("replica")
        item["mapping"]["storages"]["main"].update(
            cluster=ref("Doris", "doris-cluster"), physical_table_name="audit.wrong"
        )
        self.receipts["items"][3]["body"]["spec"]["tableInfo"]["storage"] = ref("Doris", "doris-cluster")
        self.before["rows"].append(
            {
                "model": "meta.globalmetaconfig",
                "pk": 12,
                "fields": {
                    "config_key": "doris_event_physical_table_name",
                    "config_level": "namespace",
                    "instance_key": "audit-a",
                    "config_value": "audit.original",
                },
            }
        )
        self.plan["objects"].append(
            {"model": "meta.globalmetaconfig", "pk": 12, "action": "exclude", "reason": "keep existing physical target"}
        )
        self.assert_code(self.run_check(), "EVENT_GLOBALMETA_TARGET")

    def test_real_cli_returns_nonzero_for_manual_gaps_and_refuses_evidence_overwrite(self):
        instant = datetime.now(timezone.utc).isoformat()
        self.before["manifest"]["created_at"] = instant
        for item in self.receipts["items"]:
            item["collected_at"] = instant
            item["body_sha256"] = self.checks.digest(item["body"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before = root / "before"
            before.mkdir()
            data = json.dumps(self.before["rows"]).encode()
            (before / "business.json").write_bytes(data)
            manifest = {
                **self.before["manifest"],
                "schema_version": 1,
                "complete": True,
                "fixture": "business.json",
                "size_bytes": len(data),
                "sha256": self.checks.hash_bytes(data),
            }
            (before / "manifest.json").write_text(json.dumps(manifest))
            for name, content in [("context", self.context), ("plan", self.plan), ("receipts", self.receipts)]:
                (root / f"{name}.json").write_text(json.dumps(content))
            args = [
                "preflight",
                "--context",
                str(root / "context.json"),
                "--plan",
                str(root / "plan.json"),
                "--before",
                str(before),
                "--receipts",
                str(root / "receipts.json"),
                "--output",
                str(root / "report.json"),
            ]
            with patch.object(socket, "socket", side_effect=AssertionError("network forbidden")), redirect_stdout(
                StringIO()
            ):
                self.assertEqual(self.checks.main(args), 1)
                self.assertEqual(self.checks.main(args), 2)
            self.assertEqual(json.loads((root / "report.json").read_text())["status"], "NOT_CHECKED")


class ExportTests(unittest.TestCase):
    def test_export_entry_accepts_real_string_project_settings_and_external_version_evidence(self):
        from types import SimpleNamespace

        export = load("export_fixture")
        context = fixtures()[0]
        deployed = {
            "environment": "formal-a",
            "application": "audit-a",
            "stage": "before",
            "version": "old-1",
            "image_digest": "sha256:" + "a" * 64,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "source": "deployment readback outside this tool",
        }
        settings = SimpleNamespace(APP_CODE="audit-a", BKBASE_PROJECT_ID="18")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "normal"
            result = export.export_target(
                FakeConnection(context["database"]),
                settings,
                context,
                root,
                {"strategy_v2.strategy": lambda: 0},
                lambda: [],
                deployed,
                stage="before",
            )
            self.assertEqual(result["status"], "EXPORTED")
            manifest = json.loads((root / "manifest.json").read_text())
            self.assertEqual(manifest["version_evidence"], "provided_deployment_readback")
            self.assertEqual(manifest["deployed_version_authenticity"], "NOT_CHECKED")
            for invalid in [True, "18x", "018", "", 0]:
                settings.BKBASE_PROJECT_ID = invalid
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    export.export_target(
                        FakeConnection(context["database"]),
                        settings,
                        context,
                        Path(directory) / "invalid",
                        {},
                        lambda: [],
                        deployed,
                        stage="before",
                    )

    def test_target_guard_and_read_only_transaction_precede_dump(self):
        export = load("export_fixture")
        context = fixtures()[0]
        connection = FakeConnection(context["database"])
        dumped = []

        def dump():
            self.assertIn("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY", connection.queries)
            dumped.append(True)
            return [{"model": "strategy_v2.strategy", "pk": 7, "fields": {"backend_data": {"flow_id": 41}}}]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "export"
            export.capture(connection, context, root, {"strategy_v2.strategy": lambda: 1}, dump, version="old-1")
            self.assertEqual(len(dumped), 1)
            self.assertEqual(connection.queries[-1], "ROLLBACK")
            self.assertEqual(os.stat(root / "business.json").st_mode & 0o777, 0o600)
            self.assertTrue(load("release_checks").read_bundle(root)["manifest"]["complete"])
        self.assertFalse(
            any(q.startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "ALTER")) for q in connection.queries)
        )

    def test_wrong_database_and_inconsistent_counts_leave_no_completed_bundle(self):
        export = load("export_fixture")
        context = fixtures()[0]
        connection = FakeConnection({**context["database"], "name": "other"})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "wrong"
            with self.assertRaises(ValueError):
                export.capture(connection, context, root, {}, lambda: [], version="old-1")
            self.assertFalse(root.exists())
            connection = FakeConnection(context["database"])
            root = Path(directory) / "counts"
            with self.assertRaises(ValueError):
                export.capture(
                    connection, context, root, {"strategy_v2.strategy": lambda: 1}, lambda: [], version="old-1"
                )
            self.assertFalse((root / "manifest.json").exists())
            self.assertEqual(connection.queries[-1], "ROLLBACK")


class FakeConnection:
    """DB-API boundary double: every query is fixed and returns metadata only."""

    vendor = "mysql"
    in_atomic_block = False

    def __init__(self, database):
        self.settings_dict = {"HOST": database["host"], "PORT": database["port"], "NAME": database["name"]}
        self.queries = []

    def get_autocommit(self):
        return True

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query):
        self.queries.append(query)

    def fetchone(self):
        return self.settings_dict["NAME"], "8.0"


if __name__ == "__main__":
    unittest.main()
