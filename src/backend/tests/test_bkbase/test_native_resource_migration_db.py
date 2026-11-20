"""在专属测试库验证Native DataId三类owner的真实持久化和CAS边界。"""
from contextlib import nullcontext
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

from django.db import connection
from django.test import TransactionTestCase, override_settings

from apps.meta.models import System
from services.web.bkbase import resource_migration
from services.web.bkbase.constants import CleanRole
from services.web.databus.constants import PluginSceneChoices
from services.web.databus.models import CollectorConfig, CollectorPlugin


def ref(kind, name):
    return {"kind": kind, "tenant": "tenant_a", "namespace": "known_resources", "name": name}


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit")
class NativeResourceMigrationDatabaseTests(TransactionTestCase):
    def setUp(self):
        self.context = {"version": "v4", "tenant": "tenant_a", "namespace": "audit"}
        self.plugin = CollectorPlugin.objects.create(
            namespace="audit",
            collector_plugin_id=931,
            collector_plugin_name="native",
            collector_plugin_name_en="native",
            bkdata_biz_id=7,
            table_id=71,
            index_set_id=81,
            plugin_scene=PluginSceneChoices.COLLECTOR,
            bkbase_table_id="7_original",
            bkbase_processing_id="legacy_parent",
            has_storage=True,
            bkbase_v4_resources={"retained": {"unknown": "keep"}},
        )
        self.row = {
            "owner": "plugin",
            "owner_pk": self.plugin.pk,
            "audit_namespace": "audit",
            "legacy": {"raw_data_id": 31, "processing_id": "legacy_parent", "result_table_id": "7_original"},
            "data_id": ref("DataId", "native_parent"),
            "clean": ref("Clean", "parent_clean"),
            "result_table": ref("ResultTable", "shared_table"),
            "storages": {
                "main": {"resource": ref("DataStorage", "main_store"), "cluster": ref("ElasticSearch", "es_target")}
            },
        }
        self.resources = {}
        self.add_resources(self.row, "new")
        self.sdk = mock.Mock()
        for getter in ("data_id_get", "clean_get", "result_table_resource_get", "data_storage_get"):
            getattr(self.sdk, getter).side_effect = self.read_resource
        self.enterContext(mock.patch.object(resource_migration, "api", SimpleNamespace(bk_base_v4=self.sdk)))
        self.enterContext(mock.patch.object(resource_migration, "resource_lock", side_effect=lambda *a: nullcontext()))

    def add_resources(self, row, role):
        """显式Ref提供身份；共享RT保留原创建者raw标签。"""
        for key in ("data_id", "clean", "result_table"):
            value = row[key]
            self.resources[value["name"]] = {
                "kind": value["kind"],
                "metadata": {k: value[k] for k in ("tenant", "namespace", "name")},
                "spec": {},
                "status": {"phase": "Ok"},
            }
        self.resources[row["data_id"]["name"]]["spec"] = {"predefined": {"dataId": row["legacy"]["raw_data_id"]}}
        self.resources[row["clean"]["name"]]["spec"] = {
            "data_id": row["data_id"],
            "raw_data_id": row["legacy"]["raw_data_id"],
            "result_table_source": role,
            "result_table_id": row["legacy"]["result_table_id"],
            "desired_status": "Stopped",
            "current_status": "Stopped",
            "config_revision": 1,
            "deploy_revision": 1,
        }
        table = self.resources[row["result_table"]["name"]]
        table["spec"] = {"predefiendResultTableId": "7_original"}
        table["metadata"]["labels"] = {"raw_data_id": "31"}
        for entry in row["storages"].values():
            value = entry["resource"]
            self.resources[value["name"]] = {
                "kind": "DataStorage",
                "metadata": {k: value[k] for k in ("tenant", "namespace", "name")},
                "spec": {"tableInfo": {"source": row["result_table"], "storage": entry["cluster"]}},
                "status": {"phase": "Ok"},
            }

    def read_resource(self, **params):
        self.assertFalse(connection.in_atomic_block, "远端读取不得占用数据库行锁事务")
        value = self.resources[params["name"]]
        self.assertEqual(params["namespace"], value["metadata"]["namespace"])
        return deepcopy(value)

    def apply_row(self, row):
        resource_migration.validate_manifest({"schema_version": 1, "mappings": [row]}, context=self.context)
        plan = resource_migration.preview_mapping(self.context, row)
        self.assertEqual(resource_migration.apply_mapping(self.context, row, plan, before_save=lambda: None), "updated")
        return plan

    def test_plugin_then_independent_collector_persist_only_explicit_bindings(self):
        before = self.plugin.bkbase_v4_resources.copy()
        plan = resource_migration.preview_mapping(self.context, self.row)
        self.plugin.refresh_from_db()
        self.assertEqual(self.plugin.bkbase_v4_resources, before)
        resource_migration.apply_mapping(self.context, self.row, plan, before_save=lambda: None)
        self.plugin.refresh_from_db()
        self.assertEqual(self.plugin.bkbase_v4_resources["clean_role"], CleanRole.OWNER)
        self.assertEqual(self.plugin.bkbase_v4_resources["retained"], before["retained"])
        self.assertEqual(self.plugin.bkbase_processing_id, "legacy_parent")
        System.objects.create(system_id="native_system", namespace="audit")
        child = CollectorConfig.objects.create(
            system_id="native_system",
            bk_biz_id=7,
            bk_data_id=32,
            collector_plugin_id=931,
            collector_config_id=932,
            collector_config_name="child",
            bkbase_table_id="7_original",
            processing_id="legacy_child",
        )
        row = {
            **deepcopy(self.row),
            "owner": "collector",
            "owner_pk": child.pk,
            "storages": {},
            "legacy": {"raw_data_id": 32, "processing_id": "legacy_child", "result_table_id": "7_original"},
            "data_id": ref("DataId", "native_child"),
            "clean": ref("Clean", "child_clean"),
        }
        self.add_resources(row, "existing")
        self.apply_row(row)
        child.refresh_from_db()
        self.assertEqual(child.bkbase_v4_resources["clean_role"], CleanRole.EXISTING)
        self.assertEqual(child.bkbase_v4_resources["source_raw_data_id"], 32)
        self.assertEqual(child.processing_id, "legacy_child")
        self.assertNotIn("data_source", child.bkbase_v4_resources)
        self.assertNotIn("storages", child.bkbase_v4_resources)
        result = resource_migration.observe_imported_resource(self.context, child)
        child.refresh_from_db()
        self.assertEqual(result["task_state"], "stopped")
        self.assertFalse(child.bkbase_v4_resources["clean_ready"])

    def test_event_plugin_keeps_main_doris_physical_target(self):
        self.plugin.plugin_scene = PluginSceneChoices.EVENT
        self.plugin.save(update_fields=["plugin_scene"])
        self.row["owner"] = "event_plugin"
        self.row["storages"]["main"].update(cluster=ref("Doris", "doris_target"), physical_table_name="events.original")
        self.add_resources(self.row, "new")
        with mock.patch.object(resource_migration.clean.GlobalMetaConfig, "get", return_value=None):
            self.apply_row(self.row)
        self.plugin.refresh_from_db()
        self.assertEqual(self.plugin.bkbase_v4_resources["physical_targets"], {"main": "events.original"})
        self.assertNotIn("data_source", self.plugin.bkbase_v4_resources)
        self.assertTrue(self.plugin.has_storage)

    def test_actual_row_change_after_preview_blocks_apply_without_overwrite(self):
        plan = resource_migration.preview_mapping(self.context, self.row)
        changed = {"retained": {"unknown": "keep"}, "concurrent_change": "preserve"}
        CollectorPlugin.objects.filter(pk=self.plugin.pk).update(bkbase_v4_resources=changed)
        before_save = mock.Mock()
        with self.assertRaises(ValueError):
            resource_migration.apply_mapping(self.context, self.row, plan, before_save=before_save)
        self.plugin.refresh_from_db()
        self.assertEqual(self.plugin.bkbase_v4_resources, changed)
        before_save.assert_not_called()
