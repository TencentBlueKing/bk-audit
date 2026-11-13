"""经真实management入口验证有界迁移，外部Flow仅允许受控GET。"""

import json
import tempfile
from contextlib import contextmanager
from copy import deepcopy
from io import StringIO
from pathlib import Path
from unittest import mock

import requests
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TransactionTestCase, override_settings

from services.web.bkbase import flow_migration
from services.web.strategy_v2.constants import (
    RuleAuditConfigType,
    StrategyStatusChoices,
    StrategyType,
)
from services.web.strategy_v2.models import Strategy
from tests.test_bkbase.test_flow_migration import migration_manifest


@override_settings(
    BKBASE_API_VERSION="v4",
    BKBASE_V4_TENANT="tenant_a",
    BKBASE_V4_NAMESPACE="audit",
    BKBASE_PROJECT_ID=999,
    APP_CODE="synthetic_app",
    SECRET_KEY="synthetic_secret",
    BK_RESOURCE={
        "PLATFORM_AUTH_ENABLED": True,
        "PLATFORM_AUTH_ACCESS_USERNAME": "synthetic_platform",
        "PLATFORM_AUTH_ACCESS_TOKEN": "synthetic_token",
    },
)
class FlowMigrationCommandTests(TransactionTestCase):
    def setUp(self):
        self.strategy = Strategy.objects.create(
            namespace="audit",
            strategy_name="synthetic rule",
            strategy_type=StrategyType.RULE,
            status=StrategyStatusChoices.DISABLED,
            configs={"config_type": RuleAuditConfigType.BIZ_RT, "data_source": {"rt_id": "7_input"}},
            backend_data={
                "flow_id": 41,
                "raw_table_name": "existing_output",
                "sql_node_id": 31,
                "storage_node_ids": [32],
                "data_source_node_ids": [30],
                "retained": {"keep": True},
            },
        )
        self.before = deepcopy(self.strategy.backend_data)
        self.payload = migration_manifest(self.strategy.pk)
        self.ref = self.payload["mappings"][0]["flow"]
        self.remote = {
            "kind": "Flow",
            "metadata": self.ref,
            "spec": {
                "nodes": [
                    {"kind": "StreamSourceNode", "name": "arbitrary_migrated_source"},
                    {
                        "kind": "StreamNode",
                        "name": "arbitrary_migrated_sql",
                        "inputs": ["arbitrary_migrated_source"],
                        "output": "7_existing_output",
                    },
                ]
            },
            "status": {"phase": "Ok"},
        }
        self.http = []
        self.enterContext(mock.patch("requests.sessions.Session.request", side_effect=self.transport))
        self.enterContext(mock.patch.object(flow_migration, "resource_lock", side_effect=self.lock))
        self.temp = self.enterContext(tempfile.TemporaryDirectory(prefix="bkbase-flow-mapping-"))
        self.input = Path(self.temp) / "input.json"
        self.reports = 0

    @contextmanager
    def lock(self, *args):
        yield

    def transport(self, method, url, **kwargs):
        self.assertEqual(method, "GET", "Migration must never write BKBase")
        self.assertFalse(connection.in_atomic_block, "GET must precede the local row-lock transaction")
        self.http.append((method, url))
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps({"result": True, "code": "00", "data": self.remote}).encode()
        return response

    def run_command(self, apply=False, payload=None):
        self.input.write_text(json.dumps(payload or self.payload))
        self.reports += 1
        report = Path(self.temp) / f"report-{self.reports}.jsonl"
        stdout = StringIO()
        try:
            call_command(
                "import_bkbase_v4_flow_mappings",
                input=str(self.input),
                report=str(report),
                legacy_tenant="legacy_a",
                legacy_project_id=11,
                apply=apply,
                stdout=stdout,
            )
        finally:
            self.report = report
        return stdout.getvalue(), [json.loads(line) for line in report.read_text().splitlines()]

    def test_default_dry_run_reads_arbitrary_node_names_and_writes_no_binding(self):
        out, events = self.run_command()
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.backend_data, self.before)
        self.assertIn("dry-run", out)
        preview = next(event for event in events if event["event"] == "preview")
        self.assertEqual(preview["before_backend_data"], self.before)
        self.assertEqual(
            preview["after_backend_data"]["bkbase_v4"],
            {
                "flow": self.ref,
                "output_rt_id": "7_existing_output",
                "output_name": "existing_output",
            },
        )
        self.assertEqual(len(self.http), 1)

    def test_apply_preserves_legacy_and_other_binding_fields_and_is_idempotent(self):
        self.strategy.backend_data["bkbase_v4"] = {"retained_v4": {"keep": True}}
        self.strategy.save(update_record=False, update_fields=["backend_data"])
        self.before = deepcopy(self.strategy.backend_data)
        out, events = self.run_command(apply=True)
        self.strategy.refresh_from_db()
        after = deepcopy(self.strategy.backend_data)
        self.assertEqual(
            {key: after[key] for key in self.before if key != "bkbase_v4"},
            {key: self.before[key] for key in self.before if key != "bkbase_v4"},
        )
        self.assertEqual(
            after["bkbase_v4"],
            {
                "retained_v4": {"keep": True},
                "flow": self.ref,
                "output_rt_id": "7_existing_output",
                "output_name": "existing_output",
            },
        )
        self.assertEqual(self.strategy.status, StrategyStatusChoices.DISABLED)
        self.assertNotIn("managed_nodes", after["bkbase_v4"])
        prepared = next(event for event in events if event["event"] == "before_apply")
        self.assertEqual(prepared["before_backend_data"], self.before)
        self.assertEqual(prepared["after_backend_data"], after)
        self.assertIn("updated=1", out)
        out, _ = self.run_command(apply=True)
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.backend_data, after)
        self.assertIn("unchanged=1", out)

    def test_local_identity_output_and_existing_mapping_conflicts_refuse_changes(self):
        original = deepcopy(self.payload)
        for change in [
            {"audit_namespace": "other"},
            {"legacy_flow_id": 42},
            {"output_rt_id": "8_existing_output"},
            {"output_rt_id": "7_other_output"},
        ]:
            payload = deepcopy(original)
            payload["mappings"][0].update(change)
            with self.subTest(change=change), self.assertRaises(CommandError):
                self.run_command(apply=True, payload=payload)
            self.strategy.refresh_from_db()
            self.assertEqual(self.strategy.backend_data, self.before)
        self.strategy.backend_data["bkbase_v4"] = {"flow": {**self.ref, "name": "already_bound_elsewhere"}}
        self.strategy.save(update_record=False, update_fields=["backend_data"])
        with self.assertRaises(CommandError):
            self.run_command(apply=True)

    def test_unknown_flow_mismatched_identity_and_ambiguous_output_are_rejected(self):
        original = deepcopy(self.remote)
        for remote in [
            {**original, "metadata": {**self.ref, "name": "other"}},
            {**original, "spec": {"nodes": []}},
            {
                **original,
                "spec": {
                    "nodes": original["spec"]["nodes"] + [{**original["spec"]["nodes"][1], "name": "duplicate_output"}]
                },
            },
        ]:
            self.remote = remote
            with self.subTest(remote=remote), self.assertRaises(CommandError):
                self.run_command(apply=True)
        with mock.patch.object(flow_migration.flow, "read_flow_nodes", side_effect=ValueError("unknown Flow")):
            with self.assertRaises(CommandError):
                self.run_command(apply=True)
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.backend_data, self.before)

    def test_in_flight_and_unknown_writes_are_rejected(self):
        for binding in [
            {"pending_spec": {"nodes": []}},
            {"flow_write": {"id": "writer"}},
            {"pure_operation": {"observing": True}},
            {"pure_operation": {"outcome_unknown": True}},
            {"pure_operation": {"write_fence": True}},
            {"delete_operation": {"pending": True}},
        ]:
            self.strategy.backend_data = {**self.before, "bkbase_v4": binding}
            self.strategy.save(update_record=False, update_fields=["backend_data"])
            with self.subTest(binding=binding), self.assertRaises(CommandError):
                self.run_command(apply=True)
            self.strategy.refresh_from_db()
            self.assertEqual(self.strategy.backend_data, {**self.before, "bkbase_v4": binding})

    def test_shared_old_flow_or_target_ref_is_rejected_even_if_alias_is_deleted(self):
        for alias_backend in [{"flow_id": 41}, {"bkbase_v4": {"flow": self.ref}}]:
            alias = Strategy.objects.create(
                namespace="audit",
                strategy_name="synthetic alias",
                backend_data=alias_backend,
                strategy_type=StrategyType.RULE,
                status=StrategyStatusChoices.DISABLED,
                is_deleted=True,
            )
            with self.subTest(alias=alias_backend), self.assertRaises(CommandError):
                self.run_command(apply=True)
            Strategy._objects.filter(pk=alias.pk).delete()
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.backend_data, self.before)

    def test_local_change_between_preview_and_apply_is_not_overwritten(self):
        @contextmanager
        def change_before_lock(*args):
            Strategy.objects.filter(pk=self.strategy.pk).update(backend_data={**self.before, "concurrent": "keep"})
            yield

        with mock.patch.object(flow_migration, "resource_lock", side_effect=change_before_lock):
            with self.assertRaises(CommandError):
                self.run_command(apply=True)
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.backend_data, {**self.before, "concurrent": "keep"})

    def test_apply_without_a_writable_new_report_does_not_change_database(self):
        self.input.write_text(json.dumps(self.payload))
        report = Path(self.temp) / "existing-report.jsonl"
        report.write_text("retained evidence\n")
        with self.assertRaises(CommandError):
            call_command(
                "import_bkbase_v4_flow_mappings",
                input=str(self.input),
                report=str(report),
                legacy_tenant="legacy_a",
                legacy_project_id=11,
                apply=True,
                stdout=StringIO(),
            )
        self.assertEqual(report.read_text(), "retained evidence\n")
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.backend_data, self.before)

    def test_old_values_are_in_report_before_the_real_database_save(self):
        original_save = Strategy.save

        def checked_save(strategy, *args, **kwargs):
            if kwargs.get("update_fields") == ["backend_data"]:
                report = Path(self.temp) / f"report-{self.reports}.jsonl"
                events = [json.loads(line) for line in report.read_text().splitlines()]
                prepared = next(event for event in events if event["event"] == "before_apply")
                self.assertEqual(prepared["before_backend_data"], self.before)
                self.assertEqual(prepared["after_backend_data"], strategy.backend_data)
            return original_save(strategy, *args, **kwargs)

        with mock.patch.object(Strategy, "save", new=checked_save):
            self.run_command(apply=True)
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.backend_data["bkbase_v4"]["flow"], self.ref)

    def test_second_get_rechecks_remote_output_before_any_binding_write(self):
        original = self.transport

        def changed_remote(method, url, **kwargs):
            if self.http:
                self.remote["spec"]["nodes"][1]["output"] = "7_changed_output"
            return original(method, url, **kwargs)

        with mock.patch("requests.sessions.Session.request", side_effect=changed_remote):
            with self.assertRaises(CommandError):
                self.run_command(apply=True)
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.backend_data, self.before)

    def test_partial_apply_failure_keeps_committed_row_and_its_recovery_report(self):
        other = Strategy.objects.create(
            namespace="audit",
            strategy_name="synthetic second rule",
            strategy_type=StrategyType.RULE,
            status=StrategyStatusChoices.DISABLED,
            configs={"config_type": RuleAuditConfigType.BIZ_RT, "data_source": {"rt_id": "7_input"}},
            backend_data={"flow_id": 42, "raw_table_name": "second_output"},
        )
        other_before = deepcopy(other.backend_data)
        row = deepcopy(self.payload["mappings"][0])
        row.update(strategy_id=other.pk, legacy_flow_id=42, output_rt_id="7_second_output")
        row["flow"]["name"] = "flow_42"
        self.payload["mappings"].append(row)
        original = self.transport
        original_remote = deepcopy(self.remote)

        def transport_batch(method, url, **kwargs):
            self.remote = deepcopy(original_remote)
            if "/flow_42/" in url:
                self.remote["metadata"] = row["flow"]
                self.remote["spec"]["nodes"][1]["output"] = "7_second_output" if len(self.http) < 3 else "7_changed"
            return original(method, url, **kwargs)

        with mock.patch("requests.sessions.Session.request", side_effect=transport_batch):
            with self.assertRaises(CommandError):
                self.run_command(apply=True)
        self.strategy.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(self.strategy.backend_data["bkbase_v4"]["flow"], self.ref)
        self.assertEqual(other.backend_data, other_before)
        events = [json.loads(line) for line in self.report.read_text().splitlines()]
        prepared = next(event for event in events if event["event"] == "before_apply")
        self.assertEqual(prepared["before_backend_data"], self.before)
        self.assertEqual([event["strategy_id"] for event in events if event["event"] == "updated"], [self.strategy.pk])
        self.assertTrue(any(event["event"] == "error" and event["stage"] == "apply" for event in events))
