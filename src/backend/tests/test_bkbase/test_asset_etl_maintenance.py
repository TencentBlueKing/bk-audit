"""资产维护最终配置必须消除 HDFS/Redis 不支持的索引字段。"""
from copy import deepcopy
from threading import Event, Thread
from types import SimpleNamespace
from unittest import mock

from django.db import close_old_connections, connection
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings

from apps.exceptions import SnapshotPreparingException
from apps.meta.models import ResourceType, System
from core.exceptions import LockError
from services.web.bkbase import asset_etl_maintenance, common, source
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.collector.resources import ToggleJoinDataResource
from services.web.databus.constants import SnapshotRunningStatus
from services.web.databus.models import Snapshot, SnapshotStorage


class AssetMaintenanceStorageTests(SimpleTestCase):
    def test_snapshot_lock_key_is_scoped_to_both_owner_identifiers(self):
        keys = []
        with mock.patch.object(common, "RedisLock") as locks:
            locks.return_value.acquire.return_value = True
            for system_id, resource_type in (("sys", "a"), ("sys", "a"), ("sys", "b")):
                with common.snapshot_lock(system_id, resource_type):
                    keys.append(locks.call_args.args[0])
        self.assertEqual(keys[0], keys[1])
        self.assertNotEqual(keys[0], keys[2])

    def test_load_existing_reads_only_explicit_refs(self):
        context = {"tenant": "default", "namespace": "audit"}

        def ref(kind, name):
            return {"tenant": "default", "namespace": "audit", "kind": kind, "name": name}

        binding = {
            "data_source": ref("DataSource", "source_a"),
            "data_id": ref("DataId", "data_a"),
            "clean": ref("Clean", "clean_a"),
            "result_table": ref("ResultTable", "rt_a"),
            "result_table_id": "11_logical",
            "storages": {"hdfs": ref("DataStorage", "storage_a")},
        }

        def response(**kwargs):
            return {"name": kwargs["name"]}

        gateway = asset_etl_maintenance.api.bk_base_v4
        with mock.patch.object(gateway, "data_source_get", side_effect=response), mock.patch.object(
            gateway, "data_id_get", side_effect=response
        ), mock.patch.object(gateway, "clean_get", side_effect=response), mock.patch.object(
            gateway, "result_table_resource_get", side_effect=response
        ), mock.patch.object(
            gateway, "data_storage_get", side_effect=response
        ), mock.patch.object(
            gateway, "clean_list", return_value=[]
        ) as clean_list, mock.patch.object(
            gateway, "data_storage_list", return_value=[]
        ) as storage_list, mock.patch.object(
            gateway, "clean_update", side_effect=AssertionError("unexpected write")
        ), mock.patch.object(
            gateway, "data_storage_update", side_effect=AssertionError("unexpected write")
        ):
            resources = asset_etl_maintenance._load_existing(context, binding)
        self.assertEqual(resources["rt"]["name"], "rt_a")
        self.assertEqual(resources["storages"]["hdfs"]["name"], "storage_a")
        clean_list.assert_not_called()
        storage_list.assert_not_called()

    def test_hdfs_and_redis_final_spec_removes_old_and_regenerated_index_fields(self):
        for kind in ("hdfs", "redis"):
            with self.subTest(kind=kind):
                old = {"tableInfo": {"retained": True}, "taskFieldSetting": {"index_fields": [{"index": 0}]}}
                payload = {
                    "storage_type": kind,
                    "key_fields": ["id", "resource_type_id", "system_id"],
                    "fields": [{"field_name": "field_a", "is_index": True}],
                }
                result = asset_etl_maintenance._desired_storage_spec(old, payload)
                self.assertEqual(result["taskFieldSetting"]["key_fields"], ["id", "resource_type_id", "system_id"])
                self.assertNotIn("index_fields", result["taskFieldSetting"])
                self.assertTrue(result["tableInfo"]["retained"])

    def test_doris_normal_indexes_remain(self):
        old = {"tableInfo": {}, "taskFieldSetting": {}}
        result = asset_etl_maintenance._desired_storage_spec(
            old, {"storage_type": "doris", "fields": [{"field_name": "field_a", "is_index": True}]}
        )
        self.assertEqual(result["taskFieldSetting"]["index_fields"], ["field_a"])

    def test_new_get_must_confirm_target_revision_and_running_state(self):
        ref = {"tenant": "default", "namespace": "audit", "kind": "Clean", "name": "clean_a"}
        desired = {"rules": ["new"], "config_revision": 8, "deploy_revision": 8, "desired_status": "Running"}
        resource = {
            "kind": "Clean",
            "metadata": ref,
            "status": {"phase": "Ok"},
            "spec": {**desired, "current_status": "Running"},
        }
        self.assertEqual(asset_etl_maintenance._observe_target(resource, ref, desired), "confirmed")
        self.assertEqual(
            asset_etl_maintenance._observe_target(resource, ref, {**desired, "current_status": "Stopped"}),
            "confirmed",
        )
        resource["status"]["phase"] = "Pending"
        self.assertEqual(asset_etl_maintenance._observe_target(resource, ref, desired), "pending")
        resource["status"]["phase"] = "Ok"
        resource["spec"]["deploy_revision"] = 7
        self.assertEqual(asset_etl_maintenance._observe_target(resource, ref, desired), "different")
        resource["status"]["phase"] = "Failed"
        self.assertEqual(asset_etl_maintenance._observe_target(resource, ref, desired), "failed")

    def test_clean_audit_fields_are_ignored_but_business_changes_are_not(self):
        ref = {"tenant": "default", "namespace": "audit", "kind": "Clean", "name": "clean_a"}
        desired = {
            "rules": ["new"],
            "config_revision": 8,
            "deploy_revision": 8,
            "desired_status": "Running",
            "created_by": "old",
            "created_at": "old",
            "updated_by": "old",
            "updated_at": "old",
            "description": "expected",
        }
        actual = {
            **desired,
            "created_by": "new",
            "created_at": "new",
            "updated_by": "new",
            "updated_at": "new",
            "current_status": "Running",
        }
        resource = {"kind": "Clean", "metadata": ref, "status": {"phase": "Ok"}, "spec": actual}
        self.assertEqual(asset_etl_maintenance._observe_target(resource, ref, desired), "confirmed")
        actual["description"] = "changed"
        self.assertEqual(asset_etl_maintenance._observe_target(resource, ref, desired), "different")

    def test_remote_identity_never_fills_missing_tenant(self):
        ref = {"tenant": "default", "namespace": "audit", "kind": "Clean", "name": "clean_a"}
        value = {
            "kind": "Clean",
            "metadata": {"namespace": "audit", "name": "clean_a"},
            "status": {"phase": "Ok"},
            "spec": {},
        }
        with self.assertRaises(BKBaseResourceMappingError):
            asset_etl_maintenance._observe_target(value, ref, {})

    def test_storage_requires_target_spec_and_unstopped_ok_status(self):
        ref = {"tenant": "default", "namespace": "audit", "kind": "DataStorage", "name": "storage_a"}
        desired = {"tableInfo": {"expire": 7}}
        resource = {
            "kind": "DataStorage",
            "metadata": {**ref, "annotations": {}},
            "status": {"phase": "Ok"},
            "spec": desired,
        }
        self.assertEqual(asset_etl_maintenance._observe_target(resource, ref, desired), "confirmed")
        self.assertEqual(asset_etl_maintenance._observe_target(resource, ref, desired, history_id=9), "pending")
        resource["status"]["history_id"] = 9
        self.assertEqual(asset_etl_maintenance._observe_target(resource, ref, desired, history_id=9), "confirmed")
        resource["metadata"]["annotations"]["task_stopped"] = "true"
        self.assertEqual(asset_etl_maintenance._observe_target(resource, ref, desired), "pending")

    def test_hdfs_null_index_is_equivalent_to_absent_but_doris_is_not(self):
        ref = {"tenant": "default", "namespace": "audit", "kind": "DataStorage", "name": "storage_a"}
        for kind in ("Hdfs", "Redis", "Doris"):
            desired = {"tableInfo": {"storage": {"kind": kind}}, "taskFieldSetting": {"key_fields": ["id"]}}
            actual = deepcopy(desired)
            actual["taskFieldSetting"]["index_fields"] = None
            value = {"kind": "DataStorage", "metadata": ref, "status": {"phase": "Ok"}, "spec": actual}
            expected = "different" if kind == "Doris" else "confirmed"
            self.assertEqual(asset_etl_maintenance._observe_target(value, ref, desired), expected)

    def test_other_null_fields_and_nonempty_index_are_not_ignored(self):
        ref = {"tenant": "default", "namespace": "audit", "kind": "DataStorage", "name": "storage_a"}
        desired = {"tableInfo": {"storage": {"kind": "Hdfs"}}, "taskFieldSetting": {}, "alias": None}
        actual = {"tableInfo": {"storage": {"kind": "Hdfs"}}, "taskFieldSetting": {}}
        value = {"kind": "DataStorage", "metadata": ref, "status": {"phase": "Ok"}, "spec": actual}
        self.assertEqual(asset_etl_maintenance._observe_target(value, ref, desired), "different")
        actual["alias"] = None
        actual["taskFieldSetting"]["index_fields"] = ["old_index"]
        self.assertEqual(asset_etl_maintenance._observe_target(value, ref, desired), "different")

    def test_storage_write_preflight_rejects_changed_source_or_cluster(self):
        rt = {"kind": "ResultTable", "tenant": "default", "namespace": "audit", "name": "rt"}
        cluster = {"kind": "Hdfs", "tenant": "default", "namespace": "audit", "name": "cluster"}
        snapshot = SimpleNamespace(bkbase_data_id=11, bkbase_processing_id="old")
        binding = {"result_table": rt, "result_table_id": "11_rt"}
        resource = {
            "metadata": {"labels": {}, "annotations": {}},
            "spec": {"tableInfo": {"source": rt, "storage": cluster}},
        }
        asset_etl_maintenance._validate_writable_resource(snapshot, binding, resource, "hdfs", cluster)
        resource["spec"]["tableInfo"]["storage"] = {**cluster, "name": "other"}
        with self.assertRaises(BKBaseResourceMappingError):
            asset_etl_maintenance._validate_writable_resource(snapshot, binding, resource, "hdfs", cluster)

    def test_unknown_write_never_retries_without_explicit_request_and_unchanged_base(self):
        step = {"state": "unknown", "before_digest": "before"}
        self.assertEqual(asset_etl_maintenance._decide_step(step, "confirmed", "other"), "advance")
        self.assertEqual(asset_etl_maintenance._decide_step(step, "pending", "before"), "wait")
        self.assertEqual(asset_etl_maintenance._decide_step(step, "different", "before"), "wait")
        self.assertEqual(asset_etl_maintenance._decide_step(step, "different", "before", retry=True), "retry")
        with self.assertRaises(BKBaseResourceMappingError):
            asset_etl_maintenance._decide_step(step, "different", "changed", retry=True)

    def test_failed_target_requires_explicit_retry_and_matching_configuration(self):
        step = {"state": "accepted", "before_digest": "before", "target_digest": "target"}
        self.assertEqual(asset_etl_maintenance._decide_step(step, "failed", "target"), "failed")
        self.assertEqual(
            asset_etl_maintenance._decide_step(step, "failed", "target", retry=True), "retry_applied_failed"
        )
        self.assertEqual(asset_etl_maintenance._decide_step(step, "failed", "before", retry=True), "retry")
        with self.assertRaises(BKBaseResourceMappingError):
            asset_etl_maintenance._decide_step(step, "failed", "changed", retry=True)

    def test_unknown_step_state_cannot_advance_even_if_remote_matches(self):
        with self.assertRaises(BKBaseResourceMappingError):
            asset_etl_maintenance._decide_step({"state": "unexpected"}, "confirmed", "target")

    def test_binding_validation_rejects_missing_and_cross_tenant_references(self):
        context = {"tenant": "default", "namespace": "audit"}

        def ref(kind, name):
            return {"tenant": "default", "namespace": "audit", "kind": kind, "name": name}

        binding = {
            "clean": ref("Clean", "clean_a"),
            "data_source": ref("DataSource", "source_a"),
            "clean_role": "owner",
            "data_id": ref("DataId", "data_a"),
            "result_table": ref("ResultTable", "actual_rt"),
            "result_table_id": "11_logical",
            "storages": {"hdfs": ref("DataStorage", "storage_a")},
        }
        snapshot = SimpleNamespace(bkbase_data_id=11, bkbase_processing_id="legacy", bkbase_table_id="11_logical")
        asset_etl_maintenance._validate_binding(context, snapshot, binding, ["hdfs"])
        for broken in (
            {**binding, "result_table": None},
            {**binding, "storages": {}},
            {**binding, "clean": {**binding["clean"], "tenant": "other"}},
        ):
            with self.subTest(broken=broken), self.assertRaises(BKBaseResourceMappingError):
                asset_etl_maintenance._validate_binding(context, snapshot, broken, ["hdfs"])
        snapshot.bkbase_table_id = "11_logical,other=value"
        with self.assertRaises(BKBaseResourceMappingError):
            asset_etl_maintenance._validate_binding(
                context, snapshot, {**binding, "result_table_id": snapshot.bkbase_table_id}, ["hdfs"]
            )
        snapshot.bkbase_table_id = "11_logical"
        snapshot.bkbase_data_id = -1
        with self.assertRaises(BKBaseResourceMappingError):
            asset_etl_maintenance._validate_binding(context, snapshot, binding, ["hdfs"])

    def test_existing_resource_validation_rejects_wrong_cluster_and_conflicting_label(self):
        context = {"tenant": "default", "namespace": "audit"}

        def ref(kind, name):
            return {"tenant": "default", "namespace": "audit", "kind": kind, "name": name}

        def resource(ref_value, spec, labels=None):
            return {"kind": ref_value["kind"], "metadata": {**ref_value, "labels": labels or {}}, "spec": spec}

        binding = {
            "clean": ref("Clean", "clean_a"),
            "data_id": ref("DataId", "data_a"),
            "data_source": ref("DataSource", "source_a"),
            "result_table": ref("ResultTable", "actual_rt"),
            "result_table_id": "11_logical",
            "storages": {"hdfs": ref("DataStorage", "task_a")},
        }
        snapshot = SimpleNamespace(bkbase_data_id=11, bkbase_processing_id="old_processing")
        cluster = ref("Hdfs", "cluster_a")
        source_value = resource(binding["data_source"], {"data_id": binding["data_id"]}, {"raw_data_id": "11"})
        source_value["spec"].update(desired_status="Running", current_status="Running")
        source_value["status"] = {"phase": "Ok"}
        clean_value = resource(
            binding["clean"],
            {
                "data_id": binding["data_id"],
                "raw_data_id": 11,
                "result_table_id": "11_logical",
                "result_table_source": "new",
                "desired_status": "Running",
            },
            {"processing_id": "old_processing"},
        )
        rt_value = resource(binding["result_table"], {}, {"result_table_id": "11_logical"})
        data_id_value = resource(binding["data_id"], {})
        data_id_value["status"] = {"phase": "Ok"}
        rt_value["status"] = {"phase": "Ok"}
        task = resource(
            binding["storages"]["hdfs"],
            {"tableInfo": {"source": binding["result_table"], "storage": cluster}},
            {"result_table_id": "11_logical"},
        )
        resources = {
            "source": source_value,
            "clean": clean_value,
            "data_id": data_id_value,
            "rt": rt_value,
            "storages": {"hdfs": task},
        }
        asset_etl_maintenance._validate_remote_resources(context, snapshot, binding, resources, {"hdfs": cluster})
        with self.assertRaises(BKBaseResourceMappingError):
            asset_etl_maintenance._validate_remote_resources(
                context, snapshot, binding, resources, {"hdfs": ref("Hdfs", "wrong")}
            )
        asset_etl_maintenance._validate_remote_resources(context, snapshot, binding, resources, {"hdfs": cluster})
        task["metadata"]["labels"].clear()
        asset_etl_maintenance._validate_remote_resources(context, snapshot, binding, resources, {"hdfs": cluster})
        task["metadata"]["labels"]["result_table_id"] = "11_wrong"
        with self.assertRaises(BKBaseResourceMappingError):
            asset_etl_maintenance._validate_remote_resources(context, snapshot, binding, resources, {"hdfs": cluster})
        task["metadata"]["labels"].clear()
        source_value["spec"]["desired_status"] = "Stopped"
        with self.assertRaises(BKBaseResourceMappingError):
            asset_etl_maintenance._validate_remote_resources(context, snapshot, binding, resources, {"hdfs": cluster})


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="default", BKBASE_V4_NAMESPACE="audit")
class AssetV4IdentityTests(SimpleTestCase):
    def setUp(self):
        self.context = {"tenant": "default", "namespace": "audit"}

        def ref(kind, name):
            return {"kind": kind, "tenant": "default", "namespace": "audit", "name": name}

        self.binding = {
            "clean_role": "owner",
            "clean": ref("Clean", "asset_a"),
            "data_source": ref("DataSource", "source_a"),
            "data_id": ref("DataId", "data_a"),
            "result_table": ref("ResultTable", "rt_a"),
            "result_table_id": "11_asset",
            "storages": {"doris": ref("DataStorage", "storage_a")},
        }
        self.cluster = ref("Doris", "cluster_a")
        self.snapshot = SimpleNamespace(bkbase_data_id=11, bkbase_processing_id=None, bkbase_table_id="11_asset")

        def resource(identity, spec, labels=None):
            return {
                "kind": identity["kind"],
                "metadata": {**{key: identity[key] for key in ("tenant", "namespace", "name")}, "labels": labels or {}},
                "spec": spec,
                "status": {"phase": "Ok"},
            }

        self.resources = {
            "source": resource(
                self.binding["data_source"],
                {"data_id": self.binding["data_id"], "desired_status": "Running", "current_status": "Running"},
                {"raw_data_id": "11"},
            ),
            "data_id": resource(self.binding["data_id"], {}),
            "clean": resource(
                self.binding["clean"],
                {
                    "data_id": self.binding["data_id"],
                    "raw_data_id": 11,
                    "result_table_id": "11_asset",
                    "result_table_source": "new",
                    "desired_status": "Running",
                },
            ),
            "rt": resource(self.binding["result_table"], {}, {"result_table_id": "11_asset"}),
            "storages": {
                "doris": resource(
                    self.binding["storages"]["doris"],
                    {"tableInfo": {"source": self.binding["result_table"], "storage": self.cluster}},
                )
            },
        }

    def validate_remote(self):
        asset_etl_maintenance._validate_remote_resources(
            self.context, self.snapshot, self.binding, self.resources, {"doris": self.cluster}
        )

    def test_new_v4_asset_accepts_absent_legacy_pid_with_complete_explicit_identity(self):
        for value in (None, ""):
            with self.subTest(value=value):
                self.snapshot.bkbase_processing_id = value
                try:
                    asset_etl_maintenance._validate_binding(self.context, self.snapshot, self.binding, ["doris"])
                    self.validate_remote()
                    asset_etl_maintenance._validate_writable_resource(
                        self.snapshot, self.binding, self.resources["clean"], "clean"
                    )
                except BKBaseResourceMappingError:
                    self.fail("Complete explicit pure-V4 Asset identity still requires a synthetic legacy PID")

    def test_legacy_pid_still_requires_exact_label_and_invalid_local_value_is_rejected(self):
        self.snapshot.bkbase_processing_id = "legacy_a"
        self.resources["clean"]["metadata"]["labels"]["processing_id"] = "legacy_a"
        self.validate_remote()
        for value in (None, "other"):
            self.resources["clean"]["metadata"]["labels"]["processing_id"] = value
            with self.subTest(label=value), self.assertRaises(BKBaseResourceMappingError):
                self.validate_remote()
            with self.assertRaises(BKBaseResourceMappingError):
                asset_etl_maintenance._validate_writable_resource(
                    self.snapshot, self.binding, self.resources["clean"], "clean"
                )
        for value in (False, 1, " "):
            self.snapshot.bkbase_processing_id = value
            with self.subTest(local=value), self.assertRaises(BKBaseResourceMappingError):
                asset_etl_maintenance._validate_binding(self.context, self.snapshot, self.binding, ["doris"])

    def test_existing_clean_identity_labels_must_match_in_preflight_and_locked_check(self):
        labels = self.resources["clean"]["metadata"]["labels"]
        for key, valid, invalid_values in (
            ("raw_data_id", "11", ("99", 11, None, False, "")),
            ("result_table_id", "11_asset", ("11_other", 11, None, False, "")),
        ):
            labels[key] = valid
            self.validate_remote()
            asset_etl_maintenance._validate_writable_resource(
                self.snapshot, self.binding, self.resources["clean"], "clean"
            )
            for value in invalid_values:
                labels[key] = value
                with self.subTest(label=key, value=value, stage="preflight"), self.assertRaises(
                    BKBaseResourceMappingError
                ):
                    self.validate_remote()
                with self.subTest(label=key, value=value, stage="locked"), self.assertRaises(
                    BKBaseResourceMappingError
                ):
                    asset_etl_maintenance._validate_writable_resource(
                        self.snapshot, self.binding, self.resources["clean"], "clean"
                    )
            labels.pop(key)

    def test_unresolved_clean_create_cannot_enter_bound_asset_maintenance(self):
        binding = {**self.binding, "clean_pending_create": True}
        with self.assertRaises(BKBaseResourceMappingError):
            asset_etl_maintenance._validate_binding(self.context, self.snapshot, binding, ["doris"])

    def test_absent_legacy_pid_does_not_weaken_source_output_role_or_storage_checks(self):
        original = deepcopy(self.resources)
        for path, value in (
            (("source", "spec", "data_id"), {**self.binding["data_id"], "name": "other"}),
            (("source", "metadata", "labels", "raw_data_id"), "99"),
            (("clean", "spec", "raw_data_id"), 99),
            (("clean", "spec", "result_table_source"), "existing"),
            (("clean", "spec", "result_table_id"), "11_other"),
            (("rt", "metadata", "labels", "result_table_id"), "11_other"),
            (("storages", "doris", "spec", "tableInfo", "source"), {**self.binding["result_table"], "name": "other"}),
            (("storages", "doris", "spec", "tableInfo", "storage"), {**self.cluster, "name": "other"}),
        ):
            self.resources = deepcopy(original)
            target = self.resources
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            with self.subTest(path=path), self.assertRaises(BKBaseResourceMappingError):
                self.validate_remote()
        for key, value in (("clean_role", "existing"), ("clean", {**self.binding["clean"], "tenant": "other"})):
            changed = {**self.binding, key: value}
            with self.subTest(key=key), self.assertRaises(BKBaseResourceMappingError):
                asset_etl_maintenance._validate_binding(self.context, self.snapshot, changed, ["doris"])

    def test_equivalent_rule_echo_does_not_create_a_new_revision_and_observation_confirms(self):
        declared = [
            {
                "input_id": "raw",
                "output_id": "value",
                "operator": {"type": "assign", "key_index": None, "output_type": "string"},
            }
        ]
        formal = deepcopy(declared)
        formal[0]["operator"].update(fixed_value=None, time_format=None)
        runner = asset_etl_maintenance._MaintenanceRunner(self.snapshot, None, None, {}, False)
        runner.plan = {"clean_patch": {"rules": declared}}
        spec = {
            "rules": formal,
            "config_revision": 10,
            "deploy_revision": 10,
            "desired_status": "Running",
            "current_status": "Running",
        }
        desired, revision = runner.desired_clean(spec, None)
        self.assertEqual(revision, 10)
        remote = {**self.resources["clean"], "spec": spec}
        self.assertEqual(asset_etl_maintenance._observe_target(remote, self.binding["clean"], desired), "confirmed")
        runner.verify_previous("clean", self.binding["clean"], remote)
        changed = deepcopy(desired)
        changed["rules"][0]["operator"]["key_index"] = ""
        self.assertEqual(asset_etl_maintenance._observe_target(remote, self.binding["clean"], changed), "different")

    def test_accepted_changed_rules_keep_the_original_target_digest_despite_default_echo(self):
        old = [
            {
                "input_id": "raw",
                "output_id": "value",
                "operator": {"type": "assign", "key_index": "old", "output_type": "string"},
            }
        ]
        wanted = deepcopy(old)
        wanted[0]["operator"]["key_index"] = "new"
        runner = asset_etl_maintenance._MaintenanceRunner(self.snapshot, None, None, {}, False)
        runner.plan = {"clean_patch": {"rules": wanted}}
        spec = {
            "rules": old,
            "config_revision": 10,
            "deploy_revision": 10,
            "desired_status": "Running",
            "current_status": "Running",
        }
        desired, revision = runner.desired_clean(spec, None)
        self.assertGreater(revision, 10)
        formal = deepcopy(desired)
        formal["rules"][0]["operator"].update(fixed_value=None, time_format=None)
        repeated, _ = runner.desired_clean(formal, {"revision": revision})
        self.assertEqual(
            asset_etl_maintenance._spec_digest(desired, "Clean"), asset_etl_maintenance._spec_digest(repeated, "Clean")
        )
        self.assertEqual(
            asset_etl_maintenance._observe_target(
                {**self.resources["clean"], "spec": formal}, self.binding["clean"], repeated
            ),
            "confirmed",
        )

    def test_final_verification_accepts_documented_echo_after_the_same_plan(self):
        wanted = [{"input_id": "raw", "output_id": "value", "operator": {"type": "assign", "key_index": None}}]
        formal = deepcopy(wanted)
        formal[0]["operator"]["fixed_value"] = None
        remote = {
            **self.resources["clean"],
            "spec": {
                "rules": formal,
                "config_revision": 10,
                "deploy_revision": 10,
                "desired_status": "Running",
                "current_status": "Running",
            },
        }
        plan = {
            "clean_patch": {"rules": wanted},
            "storage_configs": {},
            "clusters": {},
            "resources": {"clean": remote, "storages": {}},
        }
        self.snapshot.refresh_from_db = lambda: None
        runner = asset_etl_maintenance._MaintenanceRunner(self.snapshot, None, None, {}, False)
        runner.binding = {"clean": self.binding["clean"], "storages": {}}
        runner.plan_digest = asset_etl_maintenance._plan_digest(plan)
        with mock.patch.object(asset_etl_maintenance, "_build_plan", return_value=plan):
            try:
                runner.verify_final()
            except BKBaseResourceMappingError:
                self.fail("Final verification still treats the documented default echo as a business change")


class AssetMaintenanceClaimTests(TestCase):
    def setUp(self):
        System.objects.create(system_id="synthetic", namespace="audit", callback_url="https://example.test")
        ResourceType.objects.create(system_id="synthetic", resource_type_id="asset", unique_id="synthetic:asset")
        self.snapshot = Snapshot.objects.create(
            system_id="synthetic", resource_type_id="asset", status=SnapshotRunningStatus.RUNNING
        )

    @override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="default", BKBASE_V4_NAMESPACE="audit")
    def test_input_digest_detects_real_configuration_change_but_ignores_own_marker(self):
        first = asset_etl_maintenance._input_digest(self.snapshot, {"value": 1})
        self.snapshot.bkbase_v4_resources = {"asset_etl_maintenance": {"active": True}}
        self.snapshot.save(update_fields=["bkbase_v4_resources"])
        self.assertEqual(asset_etl_maintenance._input_digest(self.snapshot, {"value": 1}), first)
        self.snapshot.pull_config = {"period": 20}
        self.snapshot.save(update_fields=["pull_config"])
        self.assertNotEqual(asset_etl_maintenance._input_digest(self.snapshot, {"value": 1}), first)

    @override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="default", BKBASE_V4_NAMESPACE="audit")
    def test_locked_input_check_prevents_stale_callback_after_config_change(self):
        target = {"value": 1}
        expected = asset_etl_maintenance._input_digest(self.snapshot, target)
        callback = mock.Mock(return_value="saved")
        self.assertEqual(asset_etl_maintenance._checked_input(self.snapshot.pk, expected, target, callback), "saved")
        Snapshot.objects.filter(pk=self.snapshot.pk).update(pull_config={"period": 30})
        callback.reset_mock()
        with self.assertRaises(BKBaseResourceMappingError):
            asset_etl_maintenance._checked_input(self.snapshot.pk, expected, target, callback)
        callback.assert_not_called()

    @override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="default", BKBASE_V4_NAMESPACE="audit")
    def test_preflight_applies_candidate_config_only_in_memory_and_builds_all_targets(self):
        snapshot = self.snapshot
        snapshot.bkbase_data_id, snapshot.bkbase_processing_id, snapshot.bkbase_table_id = 11, "clean_old", "11_rt"
        snapshot.custom_config = {"old": True}
        snapshot.bkbase_v4_resources = {
            "clean_role": "owner",
            "result_table_id": "11_rt",
            "clean": {"name": "clean_a"},
            "storages": {"hdfs": {"name": "storage_a"}},
        }
        snapshot.save()
        SnapshotStorage.objects.create(snapshot=snapshot, storage_type="hdfs")
        clean_value = {
            "spec": {
                "rules": ["old"],
                "desired_status": "Running",
                "config_revision": 1,
                "deploy_revision": 1,
                "current_status": "Running",
            },
            "status": {"phase": "Ok"},
        }
        loaded = {
            "source": {"spec": {"report_config": {"data_path": None}}},
            "clean": clean_value,
            "storages": {"hdfs": {"spec": {"tableInfo": {}, "taskFieldSetting": {}}, "status": {"phase": "Ok"}}},
        }
        handler = mock.Mock()
        handler.clean_config = {"json_config": {"extract": []}, "fields": []}
        handler.storage_config = {
            "storage_type": "hdfs",
            "storage_cluster": "legacy",
            "fields": [],
            "key_fields": ["id", "resource_type_id", "system_id"],
        }
        with mock.patch.object(asset_etl_maintenance, "_validate_binding"), mock.patch.object(
            asset_etl_maintenance, "_check_local_owners"
        ), mock.patch.object(asset_etl_maintenance, "_load_existing", return_value=loaded), mock.patch.object(
            asset_etl_maintenance, "_validate_remote_resources"
        ), mock.patch.object(
            asset_etl_maintenance.storage, "resolve_storage_cluster", return_value={"name": "cluster"}
        ), mock.patch.object(
            asset_etl_maintenance, "AssetEtlStorageHandler", return_value=handler
        ) as constructor, mock.patch.object(
            asset_etl_maintenance.clean, "convert_rules", return_value=["new"]
        ):
            plan = asset_etl_maintenance._build_plan(
                {"tenant": "default", "namespace": "audit"},
                snapshot,
                System.objects.get(system_id="synthetic"),
                ResourceType.objects.get(system_id="synthetic"),
                {"new": True},
            )
            self.assertEqual(constructor.call_args.kwargs["pull_report_config"], {"data_path": None})
            snapshot.bkbase_v4_resources["asset_etl_maintenance"] = {
                "active": True,
                "step": {"ref": {"name": "clean_a"}, "state": "accepted"},
            }
            clean_value["status"]["phase"] = "Failed"
            with self.assertRaises(BKBaseResourceMappingError):
                asset_etl_maintenance._build_plan(
                    {"tenant": "default", "namespace": "audit"},
                    snapshot,
                    System.objects.get(system_id="synthetic"),
                    ResourceType.objects.get(system_id="synthetic"),
                    {"new": True},
                )
            asset_etl_maintenance._build_plan(
                {"tenant": "default", "namespace": "audit"},
                snapshot,
                System.objects.get(system_id="synthetic"),
                ResourceType.objects.get(system_id="synthetic"),
                {"new": True},
                retry_unknown=True,
            )
        self.assertEqual(plan["clean_patch"]["rules"], ["new"])
        self.assertEqual(
            plan["storage_specs"]["hdfs"]["taskFieldSetting"]["key_fields"], ["id", "resource_type_id", "system_id"]
        )
        self.assertEqual(constructor.call_args.kwargs["snapshot"].custom_config, {"new": True})
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.custom_config, {"old": True})

    def test_actual_same_local_writer_ref_is_rejected_but_read_only_table_is_not(self):
        ref = {"tenant": "default", "namespace": "audit", "kind": "DataStorage", "name": "task_a"}
        rt = {"tenant": "default", "namespace": "audit", "kind": "ResultTable", "name": "rt_a"}
        binding = {
            "result_table": rt,
            "storages": {"hdfs": ref},
            "clean": {"tenant": "default", "namespace": "audit", "kind": "Clean", "name": "clean_a"},
        }
        other = Snapshot.objects.create(
            system_id="other",
            resource_type_id="asset",
            bkbase_v4_resources={
                "result_table": rt,
                "clean_role": "existing",
                "storages": {},
            },
        )
        asset_etl_maintenance._check_local_owners(self.snapshot, binding)
        other.bkbase_v4_resources["storages"] = {"hdfs": ref}
        other.save(update_fields=["bkbase_v4_resources"])
        with self.assertRaises(BKBaseResourceMappingError):
            asset_etl_maintenance._check_local_owners(self.snapshot, binding)

    def test_same_intent_can_resume_but_different_input_cannot_replace_it(self):
        first = asset_etl_maintenance._begin_operation(self.snapshot.pk, "digest_a")
        resumed = asset_etl_maintenance._begin_operation(self.snapshot.pk, "digest_a")
        self.assertEqual(first["operation_id"], resumed["operation_id"])
        with self.assertRaises(BKBaseResourceMappingError):
            asset_etl_maintenance._begin_operation(self.snapshot.pk, "digest_b")

    def test_source_or_stop_operation_prevents_claim(self):
        for other in ({"pending_action": "stop"}, {"source_replay": {"active": True}}):
            self.snapshot.bkbase_v4_resources = other
            self.snapshot.save(update_fields=["bkbase_v4_resources"])
            with self.subTest(other=other), self.assertRaises(BKBaseResourceMappingError):
                asset_etl_maintenance._begin_operation(self.snapshot.pk, "digest_a")

    def test_write_claim_is_durable_and_old_callback_cannot_change_new_operation(self):
        operation = asset_etl_maintenance._begin_operation(self.snapshot.pk, "digest_a")
        step = {"ref": {"kind": "Clean", "name": "clean_a"}, "target_digest": "target_a", "revision": 5}
        asset_etl_maintenance._claim_step(self.snapshot.pk, operation["operation_id"], "digest_a", step)
        self.snapshot.refresh_from_db()
        current = self.snapshot.bkbase_v4_resources["asset_etl_maintenance"]
        self.assertEqual(current["step"]["state"], "claimed")
        with self.assertRaises(BKBaseResourceMappingError):
            asset_etl_maintenance._claim_step(self.snapshot.pk, operation["operation_id"], "digest_a", step)
        self.assertFalse(asset_etl_maintenance._record_step(self.snapshot.pk, "old_id", "digest_a", "accepted"))
        self.assertTrue(
            asset_etl_maintenance._record_step(self.snapshot.pk, operation["operation_id"], "digest_a", "unknown")
        )
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.bkbase_v4_resources["asset_etl_maintenance"]["step"]["state"], "unknown")

    def test_explicit_retry_reclaims_unknown_step_without_clearing_intent(self):
        operation = asset_etl_maintenance._begin_operation(self.snapshot.pk, "digest_a")
        step = {"ref": {"kind": "Clean", "name": "clean_a"}, "target_digest": "target_a", "revision": 5}
        asset_etl_maintenance._claim_step(self.snapshot.pk, operation["operation_id"], "digest_a", step)
        asset_etl_maintenance._record_step(self.snapshot.pk, operation["operation_id"], "digest_a", "unknown")
        asset_etl_maintenance._retry_step(self.snapshot.pk, operation["operation_id"], "target_a")
        self.snapshot.refresh_from_db()
        current = self.snapshot.bkbase_v4_resources["asset_etl_maintenance"]["step"]
        self.assertEqual(current["state"], "claimed")
        self.assertEqual(current["target_digest"], "target_a")

    @override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="default", BKBASE_V4_NAMESPACE="audit")
    def test_active_maintenance_blocks_stop_and_replay_before_any_remote_call(self):
        asset_etl_maintenance._begin_operation(self.snapshot.pk, "digest_a")
        self.snapshot.refresh_from_db()
        with mock.patch.object(source, "snapshot_lock"), mock.patch.object(source, "stop_source") as stop:
            with self.assertRaises(BKBaseResourceMappingError):
                source.stop_snapshot(self.snapshot, {})
            stop.assert_not_called()
        with mock.patch.object(source, "snapshot_lock"), mock.patch.object(source, "_replay_preflight") as preflight:
            self.assertFalse(source.prepare_snapshot_replay(self.snapshot, {}))
            preflight.assert_not_called()

    @override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="default", BKBASE_V4_NAMESPACE="audit")
    def test_stop_rechecks_replay_after_stale_snapshot_read(self):
        ref = {"tenant": "default", "namespace": "audit", "kind": "DataSource", "name": "source_a"}
        self.snapshot.bkbase_v4_resources = {"data_source": ref}
        self.snapshot.save(update_fields=["bkbase_v4_resources"])
        stale = Snapshot.objects.get(pk=self.snapshot.pk)
        self.snapshot.status = SnapshotRunningStatus.PREPARING
        self.snapshot.bkbase_v4_resources["source_replay"] = {"active": True}
        self.snapshot.save(update_fields=["status", "bkbase_v4_resources"])
        with mock.patch.object(source, "snapshot_lock"), mock.patch.object(source, "stop_source") as stop:
            with self.assertRaises(BKBaseResourceMappingError):
                source.stop_snapshot(stale, {})
            stop.assert_not_called()

    @override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="default", BKBASE_V4_NAMESPACE="audit")
    def test_active_maintenance_blocks_enable_before_precheck(self):
        asset_etl_maintenance._begin_operation(self.snapshot.pk, "digest_a")
        with mock.patch("services.web.databus.collector.resources.snapshot_lock"), mock.patch.object(
            ToggleJoinDataResource, "pre_check", side_effect=AssertionError("unexpected network")
        ):
            with self.assertRaises(SnapshotPreparingException):
                ToggleJoinDataResource().request(
                    {
                        "system_id": "synthetic",
                        "resource_type_id": "asset",
                        "is_enabled": True,
                        "pull_type": "partial",
                        "join_data_type": "asset",
                        "storage_type": [],
                    }
                )

    @override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="default", BKBASE_V4_NAMESPACE="audit")
    def test_stop_intent_persists_before_network_without_holding_new_db_atomic_block(self):
        ref = {"tenant": "default", "namespace": "audit", "kind": "DataSource", "name": "source_a"}
        self.snapshot.bkbase_v4_resources = {"data_source": ref}
        self.snapshot.save(update_fields=["bkbase_v4_resources"])
        depth = len(connection.atomic_blocks)

        def remote(context, selected):
            self.assertEqual(len(connection.atomic_blocks), depth)
            value = Snapshot.objects.get(pk=self.snapshot.pk).bkbase_v4_resources
            self.assertEqual(value["pending_action"], "stop")
            self.assertTrue(value["source_stop_token"])
            return {"ref": ref, "task_state": None, "message": ""}

        with mock.patch.object(source, "snapshot_lock"), mock.patch.object(source, "stop_source", side_effect=remote):
            self.assertFalse(source.stop_snapshot(self.snapshot, {}))
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.bkbase_v4_resources["pending_action"], "stop")

    @override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="default", BKBASE_V4_NAMESPACE="audit")
    def test_old_stop_response_does_not_overwrite_new_token(self):
        ref = {"tenant": "default", "namespace": "audit", "kind": "DataSource", "name": "source_a"}
        self.snapshot.bkbase_v4_resources = {"data_source": ref}
        self.snapshot.save(update_fields=["bkbase_v4_resources"])

        def remote(context, selected):
            current = Snapshot.objects.get(pk=self.snapshot.pk)
            current.bkbase_v4_resources["source_stop_token"] = "new_token"
            current.save(update_fields=["bkbase_v4_resources"])
            return {"ref": ref, "task_state": "stopped", "message": ""}

        with mock.patch.object(source, "snapshot_lock"), mock.patch.object(source, "stop_source", side_effect=remote):
            self.assertFalse(source.stop_snapshot(self.snapshot, {}))
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.RUNNING)
        self.assertEqual(self.snapshot.bkbase_v4_resources["source_stop_token"], "new_token")

    @override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="default", BKBASE_V4_NAMESPACE="audit")
    def test_replay_lock_contention_does_not_update_state_or_start_network(self):
        before = self.snapshot.bkbase_v4_resources.copy()
        with mock.patch.object(source, "snapshot_lock", side_effect=LockError(message="busy")), mock.patch.object(
            source, "_replay_preflight", side_effect=AssertionError("unexpected network")
        ):
            self.assertFalse(source.prepare_snapshot_replay(self.snapshot, {}))
            self.assertIsNone(source.advance_snapshot_replay(self.snapshot, {}))
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.bkbase_v4_resources, before)
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.RUNNING)


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="default", BKBASE_V4_NAMESPACE="audit")
class AssetMaintenanceContentionTests(TransactionTestCase):
    def test_persisted_stop_token_blocks_maintenance_after_simulated_lock_expiry(self):
        ref = {"tenant": "default", "namespace": "audit", "kind": "DataSource", "name": "source_a"}
        snapshot = Snapshot.objects.create(
            system_id="race",
            resource_type_id="asset",
            status=SnapshotRunningStatus.RUNNING,
            bkbase_v4_resources={"data_source": ref},
        )
        entered, release = Event(), Event()
        errors = []

        def remote(context, selected):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("test timeout")
            return {"ref": ref, "task_state": None, "message": ""}

        def stop_in_thread():
            close_old_connections()
            try:
                source.stop_snapshot(Snapshot.objects.get(pk=snapshot.pk), {})
            except Exception as error:
                errors.append(error)
            finally:
                close_old_connections()

        with mock.patch.object(source, "snapshot_lock"), mock.patch.object(source, "stop_source", side_effect=remote):
            thread = Thread(target=stop_in_thread)
            thread.start()
            try:
                self.assertTrue(entered.wait(5))
                with self.assertRaises(BKBaseResourceMappingError):
                    asset_etl_maintenance._begin_operation(snapshot.pk, "digest_a")
            finally:
                release.set()
                thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
