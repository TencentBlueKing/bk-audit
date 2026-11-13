"""从管理命令验证已有资产维护的逐项确认和未知结果恢复。"""
from copy import deepcopy
from io import StringIO
from unittest import mock

import requests
from bk_resource import resource
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from api.bk_base_v4.default import CleanGet, CleanUpdate, DataStorageUpdate
from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig, ResourceType, System
from services.web.bkbase import asset_etl_maintenance as maintenance
from services.web.bkbase import clean, storage
from services.web.bkbase.constants import BKBASE_V4_STORAGE_CLUSTER_MAP
from services.web.databus.collector.snapshot.join.etl_storage import (
    AssetEtlStorageHandler,
)
from services.web.databus.constants import (
    DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
    JoinDataType,
    SnapshotRunningStatus,
)
from services.web.databus.models import Snapshot, SnapshotStorage


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="default", BKBASE_V4_NAMESPACE="audit")
class AssetEtlCommandFlowTests(TestCase):
    def setUp(self):
        self.system = System.objects.create(
            system_id="asset_flow", namespace="audit", callback_url="https://test.invalid"
        )
        self.resource_type = ResourceType.objects.create(
            system_id="asset_flow", resource_type_id="asset", unique_id="asset_flow:asset"
        )

        def ref(kind, name):
            return {"kind": kind, "tenant": "default", "namespace": "audit", "name": name}

        self.clean_ref = ref("Clean", "clean_a")
        self.store_refs = {"hdfs": ref("DataStorage", "hdfs_a"), "redis": ref("DataStorage", "redis_a")}
        self.snapshot = Snapshot.objects.create(
            system_id="asset_flow",
            resource_type_id="asset",
            status=SnapshotRunningStatus.RUNNING,
            bkbase_data_id=11,
            bkbase_processing_id="legacy_clean",
            bkbase_table_id="11_rt",
            custom_config={"old": 1},
            bkbase_v4_resources={
                "clean": self.clean_ref,
                "clean_role": "owner",
                "data_id": ref("DataId", "data_a"),
                "data_source": ref("DataSource", "source_a"),
                "result_table": ref("ResultTable", "actual_rt"),
                "result_table_id": "11_rt",
                "storages": self.store_refs,
            },
        )
        for kind in self.store_refs:
            SnapshotStorage.objects.create(
                snapshot=self.snapshot, storage_type=kind, status=SnapshotRunningStatus.RUNNING
            )
        self.clusters = {
            kind: ref("Hdfs" if kind == "hdfs" else "Redis", kind + "_cluster") for kind in self.store_refs
        }
        self.clean_value = {
            "kind": "Clean",
            "metadata": {**self.clean_ref, "labels": {"processing_id": "legacy_clean"}},
            "spec": {
                "rules": ["old"],
                "config_revision": 1,
                "deploy_revision": 1,
                "desired_status": "Running",
                "current_status": "Running",
                "raw_data_id": 11,
                "data_id": ref("DataId", "data_a"),
                "result_table_id": "11_rt",
                "result_table_source": "new",
            },
            "status": {"phase": "Ok"},
        }
        self.stores = {
            kind: {
                "kind": "DataStorage",
                "metadata": ref_value,
                "spec": {
                    "old": kind,
                    "tableInfo": {"source": ref("ResultTable", "actual_rt"), "storage": self.clusters[kind]},
                    "taskFieldSetting": {"index_fields": [{"index": 0}]},
                },
                "status": {"phase": "Ok"},
            }
            for kind, ref_value in self.store_refs.items()
        }
        self.writes = []
        self.sent_specs = {}
        self.sent_clean_spec = None
        self.timeout_kind = None
        self.real_plan = maintenance._build_plan
        self.real_owner_check = maintenance._check_local_owners
        self.enterContext(mock.patch.object(maintenance, "snapshot_lock", create=True))
        self.enterContext(mock.patch.object(maintenance, "resource_lock", create=True))
        self.enterContext(mock.patch.object(maintenance, "_check_local_owners"))
        self.enterContext(mock.patch.object(maintenance, "_build_plan", side_effect=self.plan))
        gateway = maintenance.api.bk_base_v4
        self.enterContext(
            mock.patch.object(gateway, "clean_get", side_effect=lambda **kwargs: deepcopy(self.clean_value))
        )
        self.enterContext(mock.patch.object(gateway, "data_storage_get", side_effect=self.get_store))
        self.enterContext(mock.patch.object(gateway, "clean_update", side_effect=self.update_clean))
        self.enterContext(mock.patch.object(gateway, "data_storage_update", side_effect=self.update_store))
        self.enterContext(mock.patch.object(gateway, "clean_create", side_effect=AssertionError("unexpected POST")))
        self.enterContext(
            mock.patch.object(gateway, "data_storage_create", side_effect=AssertionError("unexpected POST"))
        )

    def plan(self, context, snapshot, system, resource_type, target_config, **kwargs):
        configs = {
            kind: {
                "storage_type": kind,
                "key_fields": ["id", "resource_type_id", "system_id"],
                "fields": [{"field_name": "other", "is_index": True}],
            }
            for kind in self.store_refs
        }
        return {
            "resources": {"clean": deepcopy(self.clean_value), "storages": deepcopy(self.stores)},
            "clean_patch": {"rules": ["new"]},
            "storage_specs": {
                kind: maintenance._desired_storage_spec(self.stores[kind]["spec"], configs[kind])
                for kind in self.store_refs
            },
            "storage_configs": configs,
            "clusters": self.clusters,
        }

    def get_store(self, **kwargs):
        return deepcopy(next(value for value in self.stores.values() if value["metadata"]["name"] == kwargs["name"]))

    def update_clean(self, **kwargs):
        self.writes.append("clean")
        self.sent_clean_spec = deepcopy(kwargs["spec"])
        self.clean_value["spec"] = {**deepcopy(kwargs["spec"]), "current_status": "Running"}
        return deepcopy(self.clean_value)

    def update_store(self, **kwargs):
        kind = next(kind for kind, ref in self.store_refs.items() if ref["name"] == kwargs["name"])
        self.writes.append(kind)
        self.sent_specs[kind] = deepcopy(kwargs["spec"])
        if self.timeout_kind == kind:
            raise requests.Timeout("synthetic unknown outcome")
        self.stores[kind]["spec"] = deepcopy(kwargs["spec"])
        return deepcopy(self.stores[kind])

    def command(self, *extra):
        return call_command(
            "update_asset_etl",
            "--system-id",
            "asset_flow",
            "--resource-type-id",
            "asset",
            "--custom-config",
            '{"new":2}',
            *extra,
            stdout=StringIO()
        )

    def test_conflicting_new_v4_clean_labels_are_rejected_before_any_command_write(self):
        original_binding = deepcopy(self.snapshot.bkbase_v4_resources)
        for label, value in (("raw_data_id", "99"), ("result_table_id", "11_other")):
            with self.subTest(label=label):
                self.snapshot.bkbase_processing_id = None
                self.snapshot.bkbase_v4_resources = deepcopy(original_binding)
                self.snapshot.save(update_fields=["bkbase_processing_id", "bkbase_v4_resources"])
                self.clean_value["metadata"]["labels"] = {label: value}
                with self.assertRaisesRegex(CommandError, "Clean ownership changed"):
                    self.command()
                self.assertEqual(self.writes, [])
                self.snapshot.refresh_from_db()
                self.assertEqual(self.snapshot.custom_config, {"old": 1})

    def test_unresolved_new_v4_clean_create_is_rejected_before_command_claim_or_write(self):
        binding = {**self.snapshot.bkbase_v4_resources, "clean_pending_create": True}
        self.snapshot.bkbase_processing_id = None
        self.snapshot.bkbase_v4_resources = binding
        self.snapshot.save(update_fields=["bkbase_processing_id", "bkbase_v4_resources"])
        with mock.patch.object(maintenance, "_build_plan", side_effect=self.real_plan):
            with self.assertRaisesRegex(CommandError, "unresolved creation"):
                self.command()
        self.assertEqual(self.writes, [])
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.custom_config, {"old": 1})
        self.assertEqual(self.snapshot.bkbase_v4_resources, binding)

    def test_mixed_storage_timeout_reentry_does_not_resend_confirmed_steps(self):
        self.timeout_kind = "redis"
        with self.assertRaises(CommandError):
            self.command()
        self.assertEqual(self.writes, ["clean", "hdfs", "redis"])
        self.assertNotIn("current_status", self.sent_clean_spec)
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.custom_config, {"old": 1})
        with self.assertRaises(CommandError):
            self.command()
        self.assertEqual(self.writes, ["clean", "hdfs", "redis"])
        self.stores["redis"]["spec"] = self.plan(None, None, None, None, None)["storage_specs"]["redis"]
        self.command()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.custom_config, {"new": 2})
        self.assertEqual(self.writes, ["clean", "hdfs", "redis"])
        for spec in self.sent_specs.values():
            self.assertNotIn("index_fields", spec["taskFieldSetting"])
            self.assertEqual(spec["taskFieldSetting"]["key_fields"], ["id", "resource_type_id", "system_id"])

    def test_actual_local_storage_writer_conflict_refuses_before_first_write(self):
        Snapshot.objects.create(
            system_id="other",
            resource_type_id="asset",
            bkbase_v4_resources={"storages": {"hdfs": self.store_refs["hdfs"]}},
        )
        with mock.patch.object(maintenance, "_build_plan", side_effect=self.real_plan), mock.patch.object(
            maintenance, "_check_local_owners", side_effect=self.real_owner_check
        ):
            with self.assertRaises(CommandError):
                self.command()
        self.assertEqual(self.writes, [])

    def test_non_asset_snapshot_is_rejected_without_writes(self):
        self.snapshot.join_data_type = JoinDataType.BASIC
        self.snapshot.save(update_fields=["join_data_type"])
        with self.assertRaises(CommandError):
            self.command()
        self.assertEqual(self.writes, [])
        self.snapshot.refresh_from_db()
        self.assertNotIn("asset_etl_maintenance", self.snapshot.bkbase_v4_resources)

    def test_explicit_retry_resends_only_unknown_unchanged_storage(self):
        self.timeout_kind = "redis"
        with self.assertRaises(CommandError):
            self.command()
        self.timeout_kind = None
        self.command("--retry-unknown")
        self.assertEqual(self.writes, ["clean", "hdfs", "redis", "redis"])
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.custom_config, {"new": 2})

    def test_failed_applied_clean_retry_claims_new_higher_revision_before_put(self):
        original = self.update_clean
        revisions = []

        def update(**kwargs):
            current = Snapshot.objects.get(pk=self.snapshot.pk).bkbase_v4_resources["asset_etl_maintenance"]["step"]
            self.assertEqual(current["state"], "claimed")
            self.assertEqual(current["revision"], kwargs["spec"]["deploy_revision"])
            revisions.append(kwargs["spec"]["deploy_revision"])
            response = original(**kwargs)
            self.clean_value["status"]["phase"] = "Failed" if len(revisions) == 1 else "Ok"
            return response

        with mock.patch.object(maintenance.api.bk_base_v4, "clean_update", side_effect=update):
            with self.assertRaises(CommandError):
                self.command()
            self.command("--retry-unknown")
        self.assertEqual(len(revisions), 2)
        self.assertGreater(revisions[1], revisions[0])
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.custom_config, {"new": 2})

    def test_unknown_unapplied_clean_retry_keeps_original_target_revision(self):
        with mock.patch.object(maintenance.api.bk_base_v4, "clean_update", side_effect=requests.Timeout("unknown")):
            with self.assertRaises(CommandError):
                self.command()
        self.snapshot.refresh_from_db()
        step = self.snapshot.bkbase_v4_resources["asset_etl_maintenance"]["step"]
        original_revision = step["revision"]
        self.command("--retry-unknown")
        self.assertEqual(self.sent_clean_spec["deploy_revision"], original_revision)

    def test_failed_clean_retry_timeout_can_retry_same_new_revision(self):
        original = self.update_clean

        def applied_but_failed(**kwargs):
            response = original(**kwargs)
            self.clean_value["status"]["phase"] = "Failed"
            return response

        with mock.patch.object(maintenance.api.bk_base_v4, "clean_update", side_effect=applied_but_failed):
            with self.assertRaises(CommandError):
                self.command()
        with mock.patch.object(maintenance.api.bk_base_v4, "clean_update", side_effect=requests.Timeout("unknown")):
            with self.assertRaises(CommandError):
                self.command("--retry-unknown")
        self.snapshot.refresh_from_db()
        step = self.snapshot.bkbase_v4_resources["asset_etl_maintenance"]["step"]
        self.assertEqual(step["state"], "unknown")
        retry_revision = step["revision"]

        def success(**kwargs):
            response = original(**kwargs)
            self.clean_value["status"]["phase"] = "Ok"
            return response

        with mock.patch.object(maintenance.api.bk_base_v4, "clean_update", side_effect=success):
            self.command("--retry-unknown")
        self.assertEqual(self.sent_clean_spec["deploy_revision"], retry_revision)

    def test_pending_clean_after_write_cannot_report_success_or_write_storage(self):
        original = self.update_clean

        def pending(**kwargs):
            response = original(**kwargs)
            self.clean_value["status"]["phase"] = "Pending"
            return response

        with mock.patch.object(maintenance.api.bk_base_v4, "clean_update", side_effect=pending):
            with self.assertRaises(CommandError):
                self.command()
        self.assertEqual(self.writes, ["clean"])
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.custom_config, {"old": 1})

    def test_configuration_drift_after_remote_write_cannot_commit_old_result(self):
        original = self.update_clean

        def changed(**kwargs):
            result = original(**kwargs)
            Snapshot.objects.filter(pk=self.snapshot.pk).update(pull_config={"period": 99})
            return result

        with mock.patch.object(maintenance.api.bk_base_v4, "clean_update", side_effect=changed):
            with self.assertRaises(CommandError):
                self.command()
        self.assertEqual(self.writes, ["clean"])
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.custom_config, {"old": 1})
        self.assertEqual(self.snapshot.bkbase_v4_resources["asset_etl_maintenance"]["step"]["state"], "claimed")

    def test_source_configuration_drift_during_preflight_prevents_all_writes(self):
        def changed(*args, **kwargs):
            value = self.plan(*args, **kwargs)
            System.objects.filter(pk=self.system.pk).update(callback_url="https://changed.invalid")
            return value

        with mock.patch.object(maintenance, "_build_plan", side_effect=changed):
            with self.assertRaises(CommandError):
                self.command()
        self.assertEqual(self.writes, [])
        self.snapshot.refresh_from_db()
        self.assertNotIn("asset_etl_maintenance", self.snapshot.bkbase_v4_resources)

    def test_storage_put_preserves_unmanaged_fields_changed_after_preflight(self):
        original = self.get_store
        changed = False

        def read(**kwargs):
            nonlocal changed
            if kwargs["name"] == "hdfs_a" and not changed:
                self.stores["hdfs"]["spec"]["alias"] = "new_external_alias"
                changed = True
            return original(**kwargs)

        with mock.patch.object(maintenance.api.bk_base_v4, "data_storage_get", side_effect=read):
            self.command()
        self.assertEqual(self.sent_specs["hdfs"]["alias"], "new_external_alias")

    def test_storage_get_default_null_after_put_is_confirmed_without_rewrite(self):
        original = self.update_store

        def defaults(**kwargs):
            result = original(**kwargs)
            kind = next(kind for kind, ref in self.store_refs.items() if ref["name"] == kwargs["name"])
            self.stores[kind]["spec"]["taskFieldSetting"]["index_fields"] = None
            return result

        with mock.patch.object(maintenance.api.bk_base_v4, "data_storage_update", side_effect=defaults):
            self.command()
        self.assertEqual(self.writes, ["clean", "hdfs", "redis"])

    def test_existing_matching_storage_with_null_index_needs_no_write(self):
        self.clean_value["spec"]["rules"] = ["new"]
        plan = self.plan(None, None, None, None, None)
        for kind, desired in plan["storage_specs"].items():
            self.stores[kind]["spec"] = deepcopy(desired)
            self.stores[kind]["spec"]["taskFieldSetting"]["index_fields"] = None
        self.command()
        self.assertEqual(self.writes, [])
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.custom_config, {"new": 2})

    def test_external_plan_change_before_first_put_refuses_all_writes(self):
        calls = 0

        def changed(*args, **kwargs):
            nonlocal calls
            calls += 1
            value = self.plan(*args, **kwargs)
            if calls > 1:
                value["clean_patch"] = {"rules": ["changed_schema"]}
            return value

        with mock.patch.object(maintenance, "_build_plan", side_effect=changed):
            with self.assertRaises(CommandError):
                self.command()
        self.assertEqual(self.writes, [])

    def test_changed_plan_on_resume_does_not_retry_unknown_write(self):
        self.timeout_kind = "redis"
        with self.assertRaises(CommandError):
            self.command()
        before = list(self.writes)

        def changed(*args, **kwargs):
            value = self.plan(*args, **kwargs)
            value["storage_configs"]["redis"]["key_fields"] = ["other"]
            return value

        with mock.patch.object(maintenance, "_build_plan", side_effect=changed):
            with self.assertRaises(CommandError):
                self.command("--retry-unknown")
        self.assertEqual(self.writes, before)
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.bkbase_v4_resources["asset_etl_maintenance"]["step"]["state"], "unknown")

    def test_stale_write_receipt_history_is_not_treated_as_new_history(self):
        for value in self.stores.values():
            value["status"]["history_id"] = 1
        original = self.update_store

        def stale_receipt(**kwargs):
            response = original(**kwargs)
            kind = next(kind for kind, ref in self.store_refs.items() if ref["name"] == kwargs["name"])
            self.stores[kind]["status"]["history_id"] = 2
            return response

        with mock.patch.object(maintenance.api.bk_base_v4, "data_storage_update", side_effect=stale_receipt):
            self.command()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.custom_config, {"new": 2})

    def test_command_clean_get_and_put_use_real_sdk_without_current_status_in_body(self):
        self.clean_value["spec"].update(
            config_revision=0,
            deploy_revision=0,
            created_by="creator",
            created_at="2026-01-01 01:00:00",
            updated_by="old_actor",
            updated_at="2026-01-01 02:00:00",
        )
        null_fields = (
            "analyzed_fields",
            "zh_analyzed_fields",
            "doc_value_fields",
            "json_fields",
            "original_json_fields",
            "value_fields",
            "flattened_fields",
            "tokenizers",
        )
        for value in self.stores.values():
            value["spec"]["taskFieldSetting"].update({name: None for name in null_fields})
            value["spec"]["taskFieldSetting"]["key_fields"] = ["old_key"]
            value["spec"]["taskFieldSetting"]["index_fields"] = None
        reader, writer, storage_writer = CleanGet(), CleanUpdate(), DataStorageUpdate()

        def respond(value):
            response = mock.Mock(status_code=200)
            response.raise_for_status.return_value = None
            response.json.return_value = {"result": True, "code": "00", "data": deepcopy(value)}
            return response

        reader.session.request = mock.Mock(side_effect=lambda *args, **kwargs: respond(self.clean_value))

        def put(*args, **kwargs):
            body = kwargs["json"]
            self.assertNotIn("current_status", body["spec"])
            self.assertIsNone(body["status"])
            result = self.update_clean(spec=body["spec"])
            self.clean_value["spec"].update(updated_by="new_actor", updated_at="2026-01-01 03:00:00")
            return respond(result)

        writer.session.request = mock.Mock(side_effect=put)

        def storage_put(*args, **kwargs):
            body = kwargs["json"]
            self.assertNotIn("index_fields", body["spec"]["taskFieldSetting"])
            self.assertEqual(body["spec"]["taskFieldSetting"]["key_fields"], ["id", "resource_type_id", "system_id"])
            for name in null_fields:
                self.assertIsNone(body["spec"]["taskFieldSetting"][name])
            result = self.update_store(name=body["metadata"]["name"], spec=body["spec"])
            kind = next(kind for kind, ref in self.store_refs.items() if ref["name"] == body["metadata"]["name"])
            self.stores[kind]["spec"]["taskFieldSetting"]["index_fields"] = None
            return respond(result)

        storage_writer.session.request = mock.Mock(side_effect=storage_put)
        with mock.patch.object(reader, "build_header", return_value={}), mock.patch.object(
            writer, "build_header", return_value={}
        ), mock.patch.object(storage_writer, "build_header", return_value={}), mock.patch.object(
            maintenance.api.bk_base_v4, "clean_get", reader.request
        ), mock.patch.object(
            maintenance.api.bk_base_v4, "clean_update", writer.request
        ), mock.patch.object(
            maintenance.api.bk_base_v4, "data_storage_update", storage_writer.request
        ):
            self.command()
        self.assertGreaterEqual(reader.session.request.call_count, 2)
        self.assertEqual(writer.session.request.call_count, 1)
        self.assertEqual(storage_writer.session.request.call_count, 2)
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.custom_config, {"new": 2})

    def test_clean_get_with_server_managed_audit_fields_confirms_after_update(self):
        self.clean_value["spec"].update(
            created_by="creator",
            created_at="2026-01-01 01:00:00",
            updated_by="old_actor",
            updated_at="2026-01-01 02:00:00",
        )
        original = self.update_clean

        def rewritten(**kwargs):
            response = original(**kwargs)
            self.clean_value["spec"].update(updated_by="new_actor", updated_at="2026-01-01 03:00:00")
            return response

        with mock.patch.object(maintenance.api.bk_base_v4, "clean_update", side_effect=rewritten):
            self.command()
        self.assertEqual(self.writes, ["clean", "hdfs", "redis"])
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.custom_config, {"new": 2})

    @override_settings(ASSET_RT_STORAGE_CLUSTER="legacy", ASSET_RT_EXPIRE_TIME="7d")
    def test_command_uses_real_preflight_and_handler_for_existing_bound_resources(self):
        binding = self.snapshot.bkbase_v4_resources

        def object_value(ref_value, spec, labels=None):
            return {
                "kind": ref_value["kind"],
                "metadata": {**ref_value, "labels": labels or {}},
                "spec": spec,
                "status": {"phase": "Ok"},
            }

        def load(context, received):
            return {
                "source": object_value(
                    binding["data_source"],
                    {
                        "data_id": binding["data_id"],
                        "desired_status": "Running",
                        "current_status": "Running",
                        "report_config": {"data_path": ".data.results"},
                    },
                    {"raw_data_id": "11"},
                ),
                "data_id": object_value(binding["data_id"], {}),
                "clean": deepcopy(self.clean_value),
                "rt": object_value(binding["result_table"], {}, {"result_table_id": "11_rt"}),
                "storages": deepcopy(self.stores),
            }

        with mock.patch.object(maintenance, "_build_plan", side_effect=self.real_plan) as plans, mock.patch.object(
            maintenance, "_check_local_owners", side_effect=self.real_owner_check
        ), mock.patch.object(maintenance, "_load_existing", side_effect=load), mock.patch.object(
            maintenance.storage,
            "resolve_storage_cluster",
            side_effect=lambda context, **kw: self.clusters[kw["storage_type"]],
        ), mock.patch.object(
            resource.meta,
            "resource_type_schema",
            return_value=[{"id": "custom_field", "type": "string", "description": "Synthetic"}],
        ) as schemas:
            self.command()
        self.assertEqual(schemas.call_count, plans.call_count)
        self.assertEqual(self.writes, ["clean", "hdfs", "redis"])
        self.assertNotIn("current_status", self.sent_clean_spec)
        for spec in self.sent_specs.values():
            self.assertEqual(spec["taskFieldSetting"]["key_fields"], ["id", "resource_type_id", "system_id"])
            self.assertNotIn("index_fields", spec["taskFieldSetting"])
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.custom_config, {"new": 2})

    @override_settings(DEFAULT_NAMESPACE="audit", ASSET_RT_EXPIRE_TIME="2d")
    def test_new_v4_doris_expiry_command_keeps_clean_echo_and_does_not_require_legacy_pid(self):
        self.store_refs = {"doris": {**self.store_refs["hdfs"], "name": "doris_a"}}
        self.clusters = {"doris": {"kind": "Doris", "tenant": "default", "namespace": "audit", "name": "doris_cluster"}}
        self.snapshot.bkbase_processing_id = None
        self.snapshot.bkbase_v4_resources["storages"] = self.store_refs
        self.snapshot.save(update_fields=["bkbase_processing_id", "bkbase_v4_resources"])
        SnapshotStorage.objects.filter(snapshot=self.snapshot).delete()
        SnapshotStorage.objects.create(
            snapshot=self.snapshot, storage_type="doris", status=SnapshotRunningStatus.RUNNING
        )
        GlobalMetaConfig.set(
            DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
            {"bkbase_cluster_id": "doris_cluster"},
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key="audit",
        )
        GlobalMetaConfig.set(
            BKBASE_V4_STORAGE_CLUSTER_MAP,
            {"doris": {"doris_cluster": self.clusters["doris"]}},
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key="audit",
        )
        binding = self.snapshot.bkbase_v4_resources

        def object_value(ref, spec, labels=None):
            return {
                "kind": ref["kind"],
                "metadata": {**ref, "labels": labels or {}},
                "spec": spec,
                "status": {"phase": "Ok"},
            }

        def load(context, received):
            return {
                "source": object_value(
                    binding["data_source"],
                    {
                        "data_id": binding["data_id"],
                        "desired_status": "Running",
                        "current_status": "Running",
                        "report_config": {"data_path": ".data.results"},
                    },
                    {"raw_data_id": "11"},
                ),
                "data_id": object_value(binding["data_id"], {}),
                "clean": deepcopy(self.clean_value),
                "rt": object_value(binding["result_table"], {}, {"result_table_id": "11_rt"}),
                "storages": deepcopy(self.stores),
            }

        with mock.patch.object(
            resource.meta,
            "resource_type_schema",
            return_value=[{"id": "id", "type": "string", "description": "Synthetic"}],
        ), mock.patch.object(maintenance, "_build_plan", side_effect=self.real_plan), mock.patch.object(
            maintenance, "_check_local_owners", side_effect=self.real_owner_check
        ), mock.patch.object(
            maintenance, "_load_existing", side_effect=load
        ):
            handler = AssetEtlStorageHandler(
                11,
                self.system,
                self.resource_type,
                "doris",
                snapshot=self.snapshot,
                pull_report_config={"data_path": ".data.results"},
            )
            declared = clean.convert_rules(handler.json_config, fields=handler.result_table_fields)
            self.clean_value["metadata"]["labels"] = {}
            self.clean_value["spec"]["rules"] = deepcopy(declared)
            for rule in self.clean_value["spec"]["rules"]:
                operator = rule["operator"]
                if operator["type"] == "assign":
                    operator.update(fixed_value=None, time_format=operator.get("time_format"))
                elif operator["type"] == "json_de":
                    operator["error_strategy"] = "drop"
                elif operator["type"] == "iter" and operator.get("reserve_index") is False:
                    operator.pop("reserve_index")
            with override_settings(ASSET_RT_EXPIRE_TIME="1d"):
                initial = storage.convert_storage_config(handler.storage_config)
            initial["tableInfo"].update(source=binding["result_table"], storage=self.clusters["doris"])
            self.stores = {"doris": object_value(self.store_refs["doris"], initial)}
            original_clean = deepcopy(self.clean_value)
            self.command()
            self.assertEqual(self.writes, ["doris"])
            expected = deepcopy(initial)
            expected["tableInfo"]["expire"] = 2
            self.assertEqual(self.sent_specs["doris"], expected)
            self.assertEqual(self.clean_value, original_clean)
            self.snapshot.refresh_from_db()
            self.assertIsNone(self.snapshot.bkbase_processing_id)
            self.assertFalse(self.snapshot.bkbase_v4_resources["asset_etl_maintenance"]["active"])
