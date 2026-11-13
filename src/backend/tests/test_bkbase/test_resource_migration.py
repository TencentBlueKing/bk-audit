"""验证存量普通插件/采集项导入仅保存已核实的资源身份。

使用未保存的真实模型和内存持久化边界，不连接数据库、Redis或真实平台。
保留正式API请求序列化及HTTP GET，重点覆盖错绑、共享表与迁移期间并发。
"""

import json
import tempfile
from contextlib import contextmanager
from copy import deepcopy
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from urllib.parse import urlparse

import requests
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import Q
from django.test import SimpleTestCase, override_settings

from core.exceptions import LockError
from services.web.bkbase import resource_migration
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.constants import PluginSceneChoices
from services.web.databus.models import CollectorConfig, CollectorPlugin, Snapshot


def ref(kind, name, namespace="project_a"):
    return {"kind": kind, "tenant": "tenant_a", "namespace": namespace, "name": name}


def manifest():
    return {
        "schema_version": 1,
        "mappings": [
            {
                "owner": "plugin",
                "owner_pk": 101,
                "audit_namespace": "audit_demo",
                "legacy": {"raw_data_id": 11, "processing_id": "legacy_plugin", "result_table_id": "7_original"},
                "data_source": ref("DataSource", "actual_source", "sources"),
                "data_id": ref("DataId", "actual_data", "data"),
                "clean": ref("Clean", "migrated_clean", "cleans"),
                "result_table": ref("ResultTable", "actual_rt", "tables"),
                "storages": {
                    "main": {
                        "resource": ref("DataStorage", "actual_main", "tasks"),
                        "cluster": ref("ElasticSearch", "actual_es", "infra"),
                    }
                },
            }
        ],
    }


def matches_query(record, query):
    """在测试内存记录上执行真实Q的AND/OR和字段查找，覆盖归属查询而不连接DB。"""
    matches = []
    for child in query.children:
        if isinstance(child, Q):
            matches.append(matches_query(record, child))
            continue
        lookup, expected = child
        value = record
        for part in lookup.split("__"):
            value = value.get(part) if isinstance(value, dict) else getattr(value, part, None)
        matches.append(value == expected)
    result = all(matches) if query.connector == Q.AND else any(matches)
    return not result if query.negated else result


class MemoryWriters(list):
    """模拟查询返回集合，保留真实Q的筛选结果及排除自身行为。"""

    def exclude(self, **kwargs):
        return MemoryWriters(record for record in self if not matches_query(record, Q(**kwargs)))

    def exists(self):
        return bool(self)


class ResourceMigrationManifestTests(SimpleTestCase):
    def test_optional_physical_target_is_explicit_normalized_and_conflict_checked(self):
        payload = manifest()
        entry = payload["mappings"][0]["storages"]["main"]
        entry["physical_table_name"] = "write_{yyyyMMdd}_migrated"
        row = self.validate(payload)[0]
        owner = SimpleNamespace(bkbase_v4_resources={"physical_targets": {"replica": "saved_db.events"}})
        binding = resource_migration._merged_binding(owner, row)
        self.assertEqual(binding["physical_targets"], {"replica": "saved_db.events", "main": "write_%Y%m%d_migrated"})
        owner.bkbase_v4_resources["physical_targets"]["main"] = "different_target"
        with self.assertRaises(ValueError):
            resource_migration._merged_binding(owner, row)
        entry["physical_table_name"] = None
        with self.assertRaises(ValueError):
            self.validate(payload)

    def validate(self, payload, **kwargs):
        return resource_migration.validate_manifest(payload, context={"tenant": "tenant_a"}, **kwargs)

    def test_explicit_cross_project_references_remain_unchanged(self):
        payload = manifest()
        self.assertEqual(self.validate(payload), payload["mappings"])

    def test_bounded_unique_strict_inputs_are_required(self):
        invalid = [[], {}, {**manifest(), "schema_version": True}, {**manifest(), "mappings": []}]
        for field, value in [
            ("owner", "snapshot"),
            ("owner", []),
            ("owner_pk", True),
            ("owner_pk", 0),
            ("audit_namespace", ""),
            ("legacy", {"raw_data_id": 11, "processing_id": "old"}),
            ("storages", {"primary": {}}),
        ]:
            payload = manifest()
            payload["mappings"][0][field] = value
            invalid.append(payload)
        for key, value in [("tenant", "tenant_b"), ("kind", "DataId"), ("namespace", ""), ("name", "")]:
            payload = manifest()
            payload["mappings"][0]["clean"][key] = value
            invalid.append(payload)
        payload = manifest()
        payload["mappings"][0]["legacy"]["raw_data_id"] = True
        invalid.append(payload)
        payload = manifest()
        payload["mappings"] *= 21
        invalid.append(payload)
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.validate(payload)
        for limit in [0, 21, True]:
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                self.validate(manifest(), limit=limit)
        for duplicate in ["owner_pk", "clean"]:
            payload = manifest()
            other = deepcopy(payload["mappings"][0])
            other.update(owner_pk=102, clean=ref("Clean", "other"))
            other[duplicate] = deepcopy(payload["mappings"][0][duplicate])
            payload["mappings"].append(other)
            with self.subTest(duplicate=duplicate), self.assertRaises(ValueError):
                self.validate(payload)

    def test_reordered_same_storage_reference_cannot_claim_both_purposes(self):
        payload = manifest()
        main = payload["mappings"][0]["storages"]["main"]
        payload["mappings"][0]["storages"]["replica"] = {
            "resource": dict(reversed(list(main["resource"].items()))),
            "cluster": ref("Doris", "actual_doris", "infra"),
        }
        with self.assertRaisesRegex(ValueError, "同一个Storage"):
            self.validate(payload)


@override_settings(
    BKBASE_API_VERSION="v4",
    BKBASE_V4_TENANT="tenant_a",
    BKBASE_V4_NAMESPACE="project_a",
    APP_CODE="synthetic_app",
    SECRET_KEY="synthetic_secret",
    BK_RESOURCE={
        "PLATFORM_AUTH_ENABLED": True,
        "PLATFORM_AUTH_ACCESS_USERNAME": "synthetic_platform",
        "PLATFORM_AUTH_ACCESS_TOKEN": "synthetic_token",
    },
)
class ResourceMigrationTests(SimpleTestCase):
    def observe_imported(self):
        """真实后台Service入口只允许GET，绑定写入在内存模拟。"""
        handler = SimpleNamespace(plugin=self.plugin, build_clean_config=mock.Mock(return_value={}))

        def bind(owner, patch, *, remove=()):
            owner.bkbase_v4_resources.update(deepcopy(patch))

        with mock.patch.object(resource_migration.clean, "update_owner_binding", side_effect=bind), mock.patch.object(
            resource_migration.clean,
            "configure_clean",
            side_effect=AssertionError("Imported resources must not be configured"),
        ), mock.patch.object(
            resource_migration.storage,
            "configure_storage",
            side_effect=AssertionError("Imported storage must not be configured"),
        ):
            return resource_migration.clean.configure_plugin(handler)

    def test_imported_stopped_plugin_is_only_observed_by_background_service(self):
        self.resources[self.row["clean"]["name"]]["status"] = {"phase": "Ok"}
        self.import_plugin()
        self.calls.clear()
        self.plugin.bkbase_v4_resources["poll_count"] = resource_migration.clean.BKBASE_V4_MAX_POLLS
        result = self.observe_imported()
        self.assertEqual(result["task_state"], "stopped")
        self.assertFalse(self.plugin.bkbase_v4_resources["ready"])
        self.assertFalse(self.plugin.bkbase_v4_resources["clean_ready"])
        self.assertEqual(len(self.calls), 5)
        self.assertFalse(self.plugin.bkbase_v4_resources["blocked"])
        self.assertEqual(self.plugin.bkbase_v4_resources["poll_count"], 0)

    def test_imported_stopped_collector_does_not_become_a_startup_timeout(self):
        self.import_plugin()
        row = self.collector_row()
        self.add_resources(row, "existing")
        self.resources[row["clean"]["name"]]["status"] = {"phase": "Ok"}
        plan = resource_migration.preview_mapping(self.context, row)
        resource_migration.apply_mapping(self.context, row, plan, before_save=lambda: None)
        self.collector.bkbase_v4_resources["poll_count"] = resource_migration.clean.BKBASE_V4_MAX_POLLS

        def bind(owner, patch, *, remove=()):
            owner.bkbase_v4_resources.update(deepcopy(patch))

        with mock.patch.object(
            resource_migration.clean.CollectorConfig.objects, "filter"
        ) as queryset, mock.patch.object(resource_migration.clean, "update_owner_binding", side_effect=bind):
            queryset.return_value.filter.return_value = [self.collector]
            resource_migration.clean.poll_clean_operations()
        self.assertFalse(self.collector.bkbase_v4_resources["clean_ready"])
        self.assertFalse(self.collector.bkbase_v4_resources["blocked"])
        self.assertEqual(self.collector.bkbase_v4_resources["poll_count"], 0)

    def test_imported_plugin_readiness_requires_formal_running_state_and_identity(self):
        self.import_plugin()
        for value in self.resources.values():
            value["status"] = {"phase": "Ok"}
        self.resources[self.row["data_source"]["name"]]["spec"]["current_status"] = "Running"
        spec = self.resources[self.row["clean"]["name"]]["spec"]
        spec.update(current_status="Running", desired_status="Running", deploy_revision=spec["config_revision"])
        result = self.observe_imported()
        self.assertEqual(result["task_state"], "running")
        self.assertTrue(self.plugin.bkbase_v4_resources["ready"])
        self.resources[self.row["storages"]["main"]["resource"]["name"]]["metadata"]["name"] = "different"
        self.observe_imported()
        self.assertFalse(self.plugin.bkbase_v4_resources["ready"])

    def test_event_plugin_has_explicit_doris_migration_and_readonly_consumption(self):
        self.row["owner"] = "event_plugin"
        self.plugin.plugin_scene = PluginSceneChoices.EVENT
        self.row["storages"]["main"].update(
            cluster=ref("Doris", "event_doris", "infra"), physical_table_name="events_db.original"
        )
        self.resources.clear()
        self.add_resources(self.row, "new")
        self.resources[self.row["clean"]["name"]]["status"] = {"phase": "Ok"}
        saved = {
            resource_migration.clean.DORIS_EVENT_BKBASE_RT_ID_KEY: "7_original",
            resource_migration.clean.DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY: "events_db.original",
            resource_migration.clean.DORIS_EVENT_STORAGE_CONFIG_KEY: {"physical_table_name": "events_db.original"},
        }
        with mock.patch.object(
            resource_migration.clean.GlobalMetaConfig, "get", side_effect=lambda key, **kw: saved.get(key)
        ):
            rows = resource_migration.validate_manifest(
                {"schema_version": 1, "mappings": [self.row]}, context=self.context
            )
            self.assertEqual(rows[0]["owner"], "event_plugin")
            self.import_plugin()
            result = self.observe_imported()
            self.assertEqual(result["task_state"], "stopped")
            self.assertEqual(self.plugin.bkbase_v4_resources["physical_targets"], {"main": "events_db.original"})
            self.row["storages"]["main"]["physical_table_name"] = "events_db.wrong"
            with self.assertRaises(ValueError):
                resource_migration.preview_mapping(self.context, self.row)

    def test_explicit_physical_target_may_fill_missing_readback_but_rejects_different_formal_target(self):
        entry = self.row["storages"]["main"]
        entry["physical_table_name"] = "write_%Y%m%d_migrated"
        preview = resource_migration.preview_mapping(self.context, self.row)
        self.assertEqual(preview["after_binding"]["physical_targets"], {"main": "write_%Y%m%d_migrated"})
        self.resources[entry["resource"]["name"]]["spec"]["tableInfo"]["physical_table_name"] = "different_target"
        with self.assertRaises(ValueError):
            resource_migration.preview_mapping(self.context, self.row)

    def setUp(self):
        self.context = {"version": "v4", "tenant": "tenant_a", "namespace": "project_a"}
        self.payload = manifest()
        self.row = self.payload["mappings"][0]
        self.plugin = CollectorPlugin(
            pk=101,
            namespace="audit_demo",
            collector_plugin_id=17,
            collector_plugin_name="plugin",
            collector_plugin_name_en="synthetic",
            bkdata_biz_id=7,
            table_id=70,
            index_set_id=80,
            bkbase_table_id="7_original",
            bkbase_processing_id="legacy_plugin",
            has_storage=True,
            bkbase_v4_resources={"retained": {"unknown": ["keep"]}},
        )
        self.collector = CollectorConfig(
            pk=201,
            system_id="synthetic_system",
            bk_biz_id=8,
            bk_data_id=12,
            collector_plugin_id=17,
            collector_config_id=21,
            collector_config_name="collector",
            bkbase_table_id="7_original",
            processing_id="legacy_collector",
            bkbase_v4_resources={},
        )
        self.plugin.save = mock.Mock()
        self.collector.save = mock.Mock()
        self.plugin_manager = mock.Mock()
        self.collector_manager = mock.Mock()
        self.snapshot_manager = mock.Mock()
        self.plugin_manager.get.return_value = self.plugin
        self.collector_manager.get.return_value = self.collector
        self.plugin_manager.select_for_update.return_value = self.plugin_manager
        self.collector_manager.select_for_update.return_value = self.collector_manager
        self.writers = {CollectorPlugin: [self.plugin], CollectorConfig: [self.collector], Snapshot: []}
        self.plugin_candidates = [self.plugin]
        self.plugin_manager.filter.side_effect = self.plugin_filter
        self.collector_manager.filter.side_effect = lambda query: self.filter_writers(CollectorConfig, query)
        self.snapshot_manager.filter.side_effect = lambda query: self.filter_writers(Snapshot, query)
        self.enterContext(mock.patch.object(CollectorPlugin, "_objects", self.plugin_manager))
        self.enterContext(mock.patch.object(CollectorConfig, "_objects", self.collector_manager))
        self.enterContext(mock.patch.object(Snapshot, "_objects", self.snapshot_manager))
        self.enterContext(
            mock.patch.object(
                resource_migration.System.objects, "get", return_value=SimpleNamespace(namespace="audit_demo")
            )
        )
        self.in_transaction = False
        self.enterContext(mock.patch.object(resource_migration.transaction, "atomic", side_effect=self.atomic))
        self.enterContext(mock.patch.object(resource_migration, "resource_lock", side_effect=self.lock))
        self.calls = []
        self.resources = {}
        self.add_resources(self.row, "new")
        self.enterContext(mock.patch("requests.sessions.Session.request", side_effect=self.transport))

    @contextmanager
    def atomic(self):
        self.in_transaction = True
        try:
            yield
        finally:
            self.in_transaction = False

    @contextmanager
    def lock(self, *args):
        yield

    def plugin_filter(self, *args, **kwargs):
        if "collector_plugin_id" in kwargs:
            return self.plugin_candidates
        return self.filter_writers(CollectorPlugin, args[0])

    def filter_writers(self, model, query):
        return MemoryWriters(record for record in self.writers[model] if matches_query(record, query))

    def add_resources(self, row, source_role):
        legacy = row["legacy"]
        for key in ("data_source", "data_id", "clean", "result_table"):
            value = row[key]
            resource = {
                "kind": value["kind"],
                "metadata": {k: value[k] for k in ("tenant", "namespace", "name")},
                "spec": {},
                "status": {"phase": "Pending"},
            }
            self.resources[value["name"]] = resource
        self.resources[row["data_source"]["name"]].update(spec={"data_id": row["data_id"]})
        self.resources[row["data_source"]["name"]]["metadata"]["labels"] = {"raw_data_id": str(legacy["raw_data_id"])}
        self.resources[row["clean"]["name"]].update(
            spec={
                "raw_data_id": legacy["raw_data_id"],
                "data_id": row["data_id"],
                "result_table_id": legacy["result_table_id"],
                "result_table_source": source_role,
                "desired_status": "Stopped",
                "current_status": "Stopped",
                "config_revision": 2,
                "deploy_revision": 1,
            }
        )
        self.resources[row["clean"]["name"]]["metadata"]["labels"] = {"processing_id": legacy["processing_id"]}
        self.resources[row["result_table"]["name"]]["metadata"]["labels"] = {
            "result_table_id": legacy["result_table_id"]
        }
        for entry in row["storages"].values():
            value = entry["resource"]
            self.resources[value["name"]] = {
                "kind": "DataStorage",
                "metadata": {k: value[k] for k in ("tenant", "namespace", "name")},
                "spec": {"tableInfo": {"source": row["result_table"], "storage": entry["cluster"]}},
                "status": {"phase": "Ok"},
            }

    def transport(self, method, url, **kwargs):
        self.assertFalse(self.in_transaction, "Remote GET must stay outside the short database transaction")
        self.assertEqual(method.upper(), "GET", "Migration may never write the platform")
        path = urlparse(url).path
        self.calls.append(path)
        name = path.rstrip("/").split("/")[-1]
        self.assertIn(name, self.resources)
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps({"result": True, "code": "0", "data": deepcopy(self.resources[name])}).encode()
        response.headers["Content-Type"] = "application/json"
        response.url = url
        return response

    def run_command(self, *, apply=False, payload=None, report_name="report.jsonl"):
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        source = directory / "input.json"
        source.write_text(json.dumps(payload or self.payload))
        report = directory / report_name
        output = StringIO()
        call_command(
            "import_bkbase_v4_resource_mappings", input=str(source), report=str(report), apply=apply, stdout=output
        )
        return report, output.getvalue(), [json.loads(line) for line in report.read_text().splitlines()]

    def import_plugin(self):
        plan = resource_migration.preview_mapping(self.context, self.row)
        resource_migration.apply_mapping(self.context, self.row, plan, before_save=lambda: None)

    def collector_row(self):
        row = deepcopy(self.row)
        row.update(
            owner="collector",
            owner_pk=201,
            storages={},
            clean=ref("Clean", "collector_clean", "cleans"),
            data_source=ref("DataSource", "collector_source", "sources"),
            data_id=ref("DataId", "collector_data", "data"),
            legacy={"raw_data_id": 12, "processing_id": "legacy_collector", "result_table_id": "7_original"},
        )
        self.add_resources(row, "existing")
        return row

    def second_plugin(self):
        row = deepcopy(self.row)
        row.update(
            owner_pk=102, legacy={"raw_data_id": 21, "processing_id": "legacy_second", "result_table_id": "7_second"}
        )
        for key in ("data_source", "data_id", "clean", "result_table"):
            row[key]["name"] += "_second"
        row["storages"]["main"]["resource"]["name"] += "_second"
        other = deepcopy(self.plugin)
        other.pk, other.collector_plugin_id = 102, 18
        other.bkbase_processing_id, other.bkbase_table_id = "legacy_second", "7_second"
        other.save = mock.Mock()
        self.plugin_manager.get.side_effect = lambda **kwargs: {101: self.plugin, 102: other}[kwargs["pk"]]
        self.add_resources(row, "new")
        return row, other

    def test_default_dry_run_only_gets_all_explicit_references_and_preserves_local_state(self):
        before = deepcopy(self.plugin.bkbase_v4_resources)
        report, output, events = self.run_command()
        self.assertIn("dry-run scanned=1 updated=0", output)
        self.assertEqual(report.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.plugin.bkbase_v4_resources, before)
        self.plugin.save.assert_not_called()
        self.assertEqual(len(self.calls), 5)
        self.assertTrue(any("/namespaces/data/dataids/actual_data/" in path for path in self.calls))
        preview = events[1]
        self.assertEqual(preview["after_binding"]["source_raw_data_id"], 11)
        self.assertEqual(preview["after_binding"]["clean_role"], "owner")
        self.assertNotIn("ready", preview["after_binding"])
        self.assertNotIn("clean_ready", preview["after_binding"])
        self.assertEqual(preview["observed"]["clean"]["task_state"], None)

    def test_apply_changes_only_binding_and_is_idempotent_without_inventing_readiness(self):
        self.plugin.bkbase_v4_resources.update(ready=True, clean_ready=True)
        report, output, events = self.run_command(apply=True)
        self.assertIn("updated=1", output)
        self.assertEqual(self.plugin.bkbase_processing_id, "legacy_plugin")
        self.assertEqual(self.plugin.bkbase_table_id, "7_original")
        self.assertEqual(self.plugin.bkbase_v4_resources["retained"], {"unknown": ["keep"]})
        self.assertIs(self.plugin.bkbase_v4_resources["ready"], False)
        self.assertIs(self.plugin.bkbase_v4_resources["clean_ready"], False)
        self.assertEqual(
            self.plugin.bkbase_v4_resources["storages"], {"main": self.row["storages"]["main"]["resource"]}
        )
        self.plugin.save.assert_called_once_with(update_record=False, update_fields=["bkbase_v4_resources"])
        self.assertEqual([e["event"] for e in events], ["manifest", "preview", "before_apply", "updated", "complete"])
        self.plugin.bkbase_v4_resources.update(ready=True, clean_ready=True)
        self.plugin.save.reset_mock()
        _, output, _ = self.run_command(apply=True)
        self.assertIn("unchanged=1", output)
        self.assertTrue(self.plugin.bkbase_v4_resources["ready"])
        self.plugin.save.assert_not_called()

    def test_wrong_local_raw_processing_table_namespace_scene_or_deleted_owner_refuses_before_http(self):
        for field, value in [
            ("bkbase_processing_id", "other"),
            ("bkbase_table_id", "7_other"),
            ("namespace", "other"),
            ("plugin_scene", PluginSceneChoices.EVENT),
        ]:
            original = getattr(self.plugin, field)
            setattr(self.plugin, field, value)
            with self.subTest(field=field), self.assertRaises(ValueError):
                resource_migration.preview_mapping(self.context, self.row)
            setattr(self.plugin, field, original)
        self.assertEqual(self.calls, [])
        self.import_plugin()
        row = self.collector_row()
        for field, value in [("bk_data_id", 99), ("is_deleted", True)]:
            original = getattr(self.collector, field)
            setattr(self.collector, field, value)
            with self.subTest(field=field), self.assertRaises(ValueError):
                resource_migration.preview_mapping(self.context, row)
            setattr(self.collector, field, original)

    def test_missing_or_conflicting_formal_proofs_never_bind(self):
        paths = [
            ("actual_source", "metadata", "labels", {}),
            ("actual_source", "spec", "data_id", ref("DataId", "wrong")),
            ("actual_data", "metadata", "tenant", "tenant_b"),
            ("migrated_clean", "metadata", "labels", {}),
            ("migrated_clean", "metadata", "labels", {"processing_id": "other"}),
            ("migrated_clean", "spec", "raw_data_id", 99),
            ("migrated_clean", "spec", "result_table_id", "7_other"),
            ("migrated_clean", "spec", "result_table_source", "existing"),
            ("actual_rt", "metadata", "labels", {"result_table_id": "7_other"}),
            (
                "actual_main",
                "spec",
                "tableInfo",
                {"source": ref("ResultTable", "other"), "storage": self.row["storages"]["main"]["cluster"]},
            ),
            (
                "actual_main",
                "spec",
                "tableInfo",
                {"source": self.row["result_table"], "storage": ref("ElasticSearch", "wrong", "infra")},
            ),
        ]
        for name, section, key, value in paths:
            original = deepcopy(self.resources[name])
            self.resources[name][section][key] = value
            with self.subTest(name=name, key=key), self.assertRaises((ValueError, BKBaseResourceMappingError)):
                resource_migration.preview_mapping(self.context, self.row)
            self.resources[name] = original
        self.plugin.save.assert_not_called()

    def test_storage_purposes_follow_original_main_replica_and_explicit_cluster_kind(self):
        for mutate in (
            lambda row: row.update(storages={}),
            lambda row: row["storages"]["main"].update(cluster=ref("Doris", "wrong", "infra")),
        ):
            row = deepcopy(self.row)
            mutate(row)
            with self.subTest(row=row), self.assertRaises(ValueError):
                resource_migration.preview_mapping(self.context, row)
        self.plugin.has_replica_storage = True
        with self.assertRaises(ValueError):
            resource_migration.preview_mapping(self.context, self.row)

    def test_explicit_replica_is_verified_and_unknown_storage_keys_are_preserved(self):
        self.plugin.has_replica_storage = True
        self.row["storages"]["replica"] = {
            "resource": ref("DataStorage", "actual_replica", "replica_project"),
            "cluster": ref("Doris", "actual_doris", "infra"),
        }
        self.plugin.bkbase_v4_resources["storages"] = {"retained_purpose": {"keep": True}}
        self.add_resources(self.row, "new")
        plan = resource_migration.preview_mapping(self.context, self.row)
        self.assertEqual(
            plan["after_binding"]["storages"],
            {
                "retained_purpose": {"keep": True},
                "main": self.row["storages"]["main"]["resource"],
                "replica": self.row["storages"]["replica"]["resource"],
            },
        )
        self.assertEqual(set(plan["observed"]["storages"]), {"main", "replica"})

    def test_api_error_detail_is_preserved_in_private_report(self):
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        source, report = directory / "input.json", directory / "error.jsonl"
        source.write_text(json.dumps(self.payload))
        with mock.patch(
            "requests.sessions.Session.request", side_effect=requests.Timeout("synthetic upstream timeout")
        ):
            with self.assertRaises(CommandError):
                call_command(
                    "import_bkbase_v4_resource_mappings",
                    input=str(source),
                    report=str(report),
                    apply=True,
                    stdout=StringIO(),
                )
        events = [json.loads(line) for line in report.read_text().splitlines()]
        self.assertEqual(events[-1]["event"], "error")
        self.assertEqual(events[-1]["stage"], "preview")
        self.assertIn("timed out", events[-1]["error"])
        self.plugin.save.assert_not_called()

    def test_in_flight_markers_and_existing_mapping_conflicts_are_not_overwritten(self):
        original = deepcopy(self.plugin.bkbase_v4_resources)
        for key, value in [
            ("pending_action", "delete"),
            ("clean_pending_create", True),
            ("clean_delete_requested", True),
            ("outcome_unknown", True),
            ("replay", {"active": True}),
            ("clean", ref("Clean", "other")),
            ("source_raw_data_id", 99),
            ("storages", {"main": ref("DataStorage", "other")}),
        ]:
            self.plugin.bkbase_v4_resources = {**deepcopy(original), key: value}
            with self.subTest(key=key), self.assertRaises(ValueError):
                resource_migration.preview_mapping(self.context, self.row)
        self.plugin.save.assert_not_called()

    def test_storage_switch_and_update_intents_block_import_before_any_resource_read(self):
        before = deepcopy(self.plugin.bkbase_v4_resources)
        for key, operation in [
            ("storage_cluster_switch", {"operation_id": "reserved", "purpose": "main", "old": "1", "target": "2"}),
            ("storage_cluster_switch", {"operation_id": "unknown", "bklog_started": True}),
            ("storage_cluster_switch", {"operation_id": "unknown", "bklog_started": True, "failed": True}),
            ("storage_cluster_update", {"operation_id": "reserved"}),
            ("storage_cluster_update", {"operation_id": "unknown", "bklog_started": True}),
            ("storage_cluster_update", {"operation_id": "confirming", "bklog_started": True, "bklog_confirmed": True}),
            ("storage_cluster_update", "invalid"),
        ]:
            self.plugin.bkbase_v4_resources = {**deepcopy(before), key: operation, "ready": True}
            untouched = deepcopy(self.plugin.bkbase_v4_resources)
            with self.subTest(key=key, operation=operation), self.assertRaisesRegex(ValueError, "存储.*未决"):
                resource_migration.preview_mapping(self.context, self.row)
            self.assertEqual(self.plugin.bkbase_v4_resources, untouched)
        self.assertEqual(self.calls, [])
        self.plugin.save.assert_not_called()

    def test_terminal_failed_switch_and_completed_history_are_preserved(self):
        failed = {"operation_id": "terminal", "purpose": "main", "old": "1", "target": "2", "failed": True}
        history = [{"operation_id": "completed", "result": "succeeded"}]
        self.plugin.bkbase_v4_resources.update(storage_cluster_switch=failed, storage_cluster_history=history)
        plan = resource_migration.preview_mapping(self.context, self.row)
        self.assertEqual(plan["after_binding"]["storage_cluster_switch"], failed)
        self.assertEqual(plan["after_binding"]["storage_cluster_history"], history)

    def test_shared_plugin_pending_storage_update_blocks_collector_identity_import(self):
        self.import_plugin()
        row = self.collector_row()
        self.plugin.bkbase_v4_resources["storage_cluster_update"] = {
            "operation_id": "unknown",
            "bklog_started": True,
        }
        self.calls.clear()
        with self.assertRaisesRegex(ValueError, "存储.*未决"):
            resource_migration.preview_mapping(self.context, row)
        self.assertEqual(self.calls, [])
        self.collector.save.assert_not_called()

    def test_duplicate_clean_or_old_processing_owner_is_rejected(self):
        other = CollectorPlugin(pk=999, bkbase_processing_id="legacy_plugin", bkbase_v4_resources={})
        self.writers[CollectorPlugin].append(other)
        with self.assertRaisesRegex(ValueError, "归属"):
            resource_migration.preview_mapping(self.context, self.row)
        self.assertEqual(self.calls, [])

    def test_foreign_result_table_owner_or_storage_writer_blocks_preview_across_models(self):
        for model, binding in [
            (CollectorPlugin, {"result_table": dict(reversed(list(self.row["result_table"].items())))}),
            (Snapshot, {"result_table": self.row["result_table"], "clean_role": "owner"}),
            (CollectorConfig, {"result_table": self.row["result_table"], "clean_role": "owner"}),
            (CollectorPlugin, {"storages": {"replica": self.row["storages"]["main"]["resource"]}}),
            (Snapshot, {"storages": {"hdfs": dict(reversed(list(self.row["storages"]["main"]["resource"].items())))}}),
            (CollectorConfig, {"storages": {"main": self.row["storages"]["main"]["resource"]}}),
        ]:
            other = model(pk=999, bkbase_v4_resources=deepcopy(binding))
            if model is CollectorPlugin:
                other.namespace = "different_local_namespace"
                other.bkbase_processing_id = "different_processing"
            self.writers[model].append(other)
            with self.subTest(model=model, binding=binding), self.assertRaisesRegex(ValueError, "归属"):
                resource_migration.preview_mapping(self.context, self.row)
            self.writers[model].remove(other)
        self.assertEqual(self.calls, [])
        self.plugin.save.assert_not_called()

    def test_ownership_created_after_preview_is_rechecked_before_apply(self):
        plan = resource_migration.preview_mapping(self.context, self.row)
        self.writers[Snapshot].append(
            Snapshot(
                pk=999,
                bkbase_v4_resources={
                    "result_table": self.row["result_table"],
                    "clean_role": "owner",
                },
            )
        )
        with self.assertRaisesRegex(ValueError, "归属"):
            resource_migration.apply_mapping(self.context, self.row, plan, before_save=lambda: None)
        self.plugin.save.assert_not_called()

    def test_apply_locks_clean_result_table_and_every_storage_in_canonical_order(self):
        plan = resource_migration.preview_mapping(self.context, self.row)
        acquired = []

        @contextmanager
        def record_lock(context, resource_ref):
            acquired.append(deepcopy(resource_ref))
            yield

        with mock.patch.object(resource_migration, "resource_lock", side_effect=record_lock):
            resource_migration.apply_mapping(self.context, self.row, plan, before_save=lambda: None)
        expected = [self.row["clean"], self.row["result_table"], self.row["storages"]["main"]["resource"]]
        self.assertEqual(
            acquired,
            sorted(expected, key=lambda value: tuple(value[k] for k in ("kind", "tenant", "namespace", "name"))),
        )

    def test_result_table_lock_contention_stops_without_remote_reads_or_retry(self):
        plan = resource_migration.preview_mapping(self.context, self.row)
        self.calls.clear()
        attempts = []

        @contextmanager
        def unavailable(context, resource_ref):
            attempts.append(deepcopy(resource_ref))
            if resource_ref == self.row["result_table"]:
                raise LockError(message="synthetic resource busy")
            yield

        before_save = mock.Mock()
        with mock.patch.object(resource_migration, "resource_lock", side_effect=unavailable):
            with self.assertRaises(LockError):
                resource_migration.apply_mapping(self.context, self.row, plan, before_save=before_save)
        self.assertEqual([item["kind"] for item in attempts], ["Clean", "DataStorage", "ResultTable"])
        self.assertEqual(self.calls, [])
        before_save.assert_not_called()
        self.plugin.save.assert_not_called()

    def test_existing_snapshot_consumer_does_not_conflict_with_plugin_table_owner(self):
        self.writers[Snapshot].append(
            Snapshot(
                pk=999,
                bkbase_v4_resources={
                    "result_table": self.row["result_table"],
                    "clean_role": "existing",
                },
            )
        )
        plan = resource_migration.preview_mapping(self.context, self.row)
        self.assertEqual(plan["after_binding"]["clean_role"], "owner")

    def test_collector_requires_unique_previously_bound_owner_plugin_and_never_imports_storages(self):
        row = self.collector_row()
        with self.assertRaisesRegex(ValueError, "插件"):
            resource_migration.preview_mapping(self.context, row)
        self.import_plugin()
        plan = resource_migration.preview_mapping(self.context, row)
        self.assertEqual(plan["after_binding"]["clean_role"], "existing")
        self.assertNotIn("storages", plan["after_binding"])
        resource_migration.apply_mapping(self.context, row, plan, before_save=lambda: None)
        self.assertEqual(
            self.collector.bkbase_v4_resources["result_table"], self.plugin.bkbase_v4_resources["result_table"]
        )
        self.plugin_candidates *= 2
        with self.assertRaisesRegex(ValueError, "唯一"):
            resource_migration.preview_mapping(self.context, row)

    def test_collector_shared_result_table_and_plugin_clean_are_reverified(self):
        self.import_plugin()
        row = self.collector_row()
        original = deepcopy(self.plugin.bkbase_v4_resources)
        self.plugin.bkbase_v4_resources["result_table"] = ref("ResultTable", "other")
        with self.assertRaises(ValueError):
            resource_migration.preview_mapping(self.context, row)
        self.plugin.bkbase_v4_resources = original
        self.resources["migrated_clean"]["spec"]["result_table_id"] = "7_other"
        with self.assertRaises((ValueError, BKBaseResourceMappingError)):
            resource_migration.preview_mapping(self.context, row)

    def test_apply_rechecks_remote_before_short_transaction_and_cas_rejects_local_change(self):
        plan = resource_migration.preview_mapping(self.context, self.row)
        self.resources["actual_main"]["spec"]["tableInfo"]["source"] = ref("ResultTable", "other")
        with self.assertRaises((ValueError, BKBaseResourceMappingError)):
            resource_migration.apply_mapping(self.context, self.row, plan, before_save=lambda: None)
        self.resources["actual_main"]["spec"]["tableInfo"]["source"] = self.row["result_table"]
        self.plugin.etl_params = {"changed": True}
        with self.assertRaisesRegex(ValueError, "改变"):
            resource_migration.apply_mapping(self.context, self.row, plan, before_save=lambda: None)
        self.plugin.save.assert_not_called()

    def test_shared_plugin_change_after_preview_blocks_collector_apply(self):
        self.import_plugin()
        row = self.collector_row()
        plan = resource_migration.preview_mapping(self.context, row)
        self.plugin.storage_changed = True
        with self.assertRaisesRegex(ValueError, "改变"):
            resource_migration.apply_mapping(self.context, row, plan, before_save=lambda: None)
        self.collector.save.assert_not_called()

    def test_write_ahead_report_failure_cannot_change_local_binding(self):
        plan = resource_migration.preview_mapping(self.context, self.row)
        before = deepcopy(self.plugin.bkbase_v4_resources)
        with self.assertRaises(OSError):
            resource_migration.apply_mapping(
                self.context, self.row, plan, before_save=mock.Mock(side_effect=OSError("disk full"))
            )
        self.assertEqual(self.plugin.bkbase_v4_resources, before)
        self.plugin.save.assert_not_called()

    def test_report_contains_old_values_before_database_save_and_cannot_overwrite_existing_path(self):
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        source, report = directory / "input.json", directory / "private.jsonl"
        source.write_text(json.dumps(self.payload))

        def save(**kwargs):
            events = [json.loads(line) for line in report.read_text().splitlines()]
            self.assertEqual(events[-1]["event"], "before_apply")
            self.assertEqual(events[-1]["before_binding"], {"retained": {"unknown": ["keep"]}})

        self.plugin.save.side_effect = save
        call_command(
            "import_bkbase_v4_resource_mappings", input=str(source), report=str(report), apply=True, stdout=StringIO()
        )
        self.plugin.save.reset_mock()
        with self.assertRaises(CommandError):
            call_command(
                "import_bkbase_v4_resource_mappings",
                input=str(source),
                report=str(report),
                apply=True,
                stdout=StringIO(),
            )
        self.plugin.save.assert_not_called()

    def test_api_errors_are_reported_and_batch_is_not_applied(self):
        with mock.patch("requests.sessions.Session.request", side_effect=requests.Timeout("upstream timeout")):
            with self.assertRaises(CommandError):
                self.run_command(apply=True)
        self.plugin.save.assert_not_called()

    def test_any_preview_failure_prevents_the_entire_batch_from_writing(self):
        row, other = self.second_plugin()
        self.resources[row["clean"]["name"]]["metadata"]["labels"] = {}
        payload = {**self.payload, "mappings": [self.row, row]}
        with self.assertRaises(CommandError):
            self.run_command(apply=True, payload=payload)
        self.plugin.save.assert_not_called()
        other.save.assert_not_called()

    def test_partial_apply_failure_keeps_committed_rows_and_recovery_report(self):
        row, other = self.second_plugin()
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        source, report = directory / "input.json", directory / "partial.jsonl"
        source.write_text(json.dumps({**self.payload, "mappings": [self.row, row]}))
        self.plugin.save.side_effect = lambda **kwargs: self.resources[row["clean"]["name"]]["metadata"].update(
            labels={}
        )
        with self.assertRaisesRegex(CommandError, "此前已更新1条"):
            call_command(
                "import_bkbase_v4_resource_mappings",
                input=str(source),
                report=str(report),
                apply=True,
                stdout=StringIO(),
            )
        self.assertEqual(self.plugin.bkbase_v4_resources["clean"], self.row["clean"])
        other.save.assert_not_called()
        events = [json.loads(line) for line in report.read_text().splitlines()]
        self.assertEqual(
            [event["event"] for event in events], ["manifest", "preview", "preview", "before_apply", "updated", "error"]
        )
        self.assertEqual(events[-1]["stage"], "apply")

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_refuses_import_without_any_remote_read_or_local_write(self):
        with self.assertRaises(CommandError):
            self.run_command(apply=True)
        self.assertEqual(self.calls, [])
        self.plugin.save.assert_not_called()
