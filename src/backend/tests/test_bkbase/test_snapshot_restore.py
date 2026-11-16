"""使用真实 SDK 及定时入口验证既有快照恢复，HTTP 全部模拟。"""
import json
from copy import deepcopy
from unittest import mock

import requests
from django.db import connection
from django.test import SimpleTestCase, TestCase, override_settings

from api.bk_base_v4.default import BkBaseV4Resource
from apps.exceptions import SnapshotPreparingException
from apps.meta.models import ResourceType, System
from apps.meta.resources import UpdateSystem
from core.utils.lock import RedisLock
from services.web.bkbase import snapshot_restore, source
from services.web.bkbase.common import snapshot_lock
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus import tasks
from services.web.databus.collector.resources import (
    CollectorEtlResource,
    ToggleJoinDataResource,
)
from services.web.databus.collector.snapshot.join.base import JoinConfig
from services.web.databus.collector.snapshot.join.http_pull import HttpPullHandler
from services.web.databus.constants import SnapshotRunningStatus
from services.web.databus.models import (
    CollectorConfig,
    CollectorPlugin,
    Snapshot,
    SnapshotStorage,
)
from tests.test_bkbase.system_snapshot_fixtures import seed_ready_system_snapshots
from tests.test_databus.collector.constants import CREATE_COLLECTOR_ETL_DATA


class HistoryObservationContractTests(SimpleTestCase):
    def resource(self, kind):
        return {
            "kind": kind,
            "metadata": {"tenant": "default", "namespace": "audit", "name": "synthetic"},
            "spec": {
                "desired_status": "Running",
                "current_status": "Running",
                "config_revision": 42,
                "deploy_revision": 42,
            },
            "status": {"phase": "Ok", "history_id": 22, "start_time": "new_lifecycle"},
        }

    def test_clean_and_source_history_changes_do_not_mask_the_matching_running_target(self):
        for kind in ("Clean", "DataSource"):
            with self.subTest(kind=kind):
                current = self.resource(kind)
                plan = {"baseline": "previous_config", "target": snapshot_restore._digest(current)}
                write = {"accepted": True, "history_id": 21}
                self.assertEqual(snapshot_restore._observed(current, plan, write), "running")

    def test_history_change_does_not_allow_a_different_explicit_target(self):
        for kind in ("Clean", "DataSource"):
            with self.subTest(kind=kind):
                current = self.resource(kind)
                plan = {"baseline": "previous_config", "target": snapshot_restore._digest(current)}
                current["spec"]["deploy_revision"] += 1
                with self.assertRaises(BKBaseResourceMappingError):
                    snapshot_restore._observed(current, plan, {"accepted": True, "history_id": 21})

    def test_same_configuration_source_still_requires_a_new_accepted_lifecycle(self):
        current = self.resource("DataSource")
        digest = snapshot_restore._digest(current)
        plan = {"baseline": digest, "target": digest, "start_time": "old_lifecycle"}
        write = {"accepted": True, "history_id": 21}
        current["status"]["start_time"] = "old_lifecycle"
        self.assertEqual(snapshot_restore._observed(current, plan, write), "pending")
        current["status"]["start_time"] = "new_lifecycle"
        self.assertEqual(snapshot_restore._observed(current, plan, {**write, "accepted": None}), "pending")
        self.assertEqual(snapshot_restore._observed(current, plan, write), "running")


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="default", BKBASE_V4_NAMESPACE="audit")
class SnapshotRestoreTests(TestCase):
    def setUp(self):
        seed_ready_system_snapshots()
        self.system = System.objects.create(
            system_id="restore_system", namespace="audit", callback_url="https://source.test", auth_token="synthetic"
        )
        resource = ResourceType.objects.create(
            system_id=self.system.system_id, resource_type_id="asset", unique_id="restore_system:asset", path="/objects"
        )
        self.binding = {
            "data_source": self.ref("DataSource", "source"),
            "data_id": self.ref("DataId", "data"),
            "clean": self.ref("Clean", "clean"),
            "clean_role": "owner",
            "result_table_id": "11_legacy_logical",
            "result_table": self.ref("ResultTable", "actual_rt"),
            "storages": {
                "hdfs": self.ref("DataStorage", "hdfs"),
                "doris": self.ref("DataStorage", "doris"),
            },
        }
        self.snapshot = Snapshot.objects.create(
            system_id=self.system.system_id,
            resource_type_id="asset",
            bkbase_data_id=71,
            bkbase_processing_id="legacy_clean",
            bkbase_table_id="11_legacy_logical",
            bkbase_v4_resources=self.binding,
        )
        for storage_type in self.binding["storages"]:
            SnapshotStorage.objects.create(snapshot=self.snapshot, storage_type=storage_type)
        config = HttpPullHandler(self.system, resource, self.snapshot, self.snapshot.join_data_type).config
        scope = config["access_conf_info"]["resource"]["scope"][0]
        self.resources = {
            "source": self.remote(
                "DataSource",
                "source",
                {
                    "data_id": self.binding["data_id"],
                    "data_conn": self.ref("DataConn", "conn"),
                    "desired_status": "Stopped",
                    "current_status": "Stopped",
                    "report_config": {
                        "type": "rest_api",
                        "http_mode": "PULL",
                        "data_conn_name": "conn",
                        "method": "post",
                        "path": "/objects",
                        "body": scope["body"]["content"],
                        "period": config["access_conf_info"]["collection_model"]["period"],
                        "period_unit": "minute",
                        "increment_field": {"type": "time", "time_format": "Unix Time Stamp(milliseconds)"},
                        "pagination": {
                            "start_offset": 0,
                            "limit": scope["body"]["page"]["limit"],
                            "total_path": "data.count",
                        },
                        "history_data": {"start_time": "123"},
                    },
                },
                raw_data_id="71",
            ),
            "conn": self.remote(
                "DataConn",
                "conn",
                {"conn_info": {"type": "rest_api", "url": "https://source.test", "headers": scope["headers"]}},
            ),
            "data": self.remote("DataId", "data", {}),
            "actual_rt": self.remote("ResultTable", "actual_rt", {}, result_table_id="11_legacy_logical"),
            "clean": self.remote(
                "Clean",
                "clean",
                {
                    "raw_data_id": 71,
                    "data_id": self.binding["data_id"],
                    "result_table_id": "11_legacy_logical",
                    "result_table_source": "new",
                    "desired_status": "Stopped",
                    "current_status": "Stopped",
                    "config_revision": 42,
                    "deploy_revision": 42,
                    "rules": [{"output_id": "keep"}],
                },
                processing_id="legacy_clean",
            ),
        }
        for key, kind in (("doris", "Doris"), ("hdfs", "Hdfs")):
            self.resources[key] = self.remote(
                "DataStorage",
                key,
                {
                    "tableInfo": {"source": self.binding["result_table"], "storage": self.ref(kind, key + "_cluster")},
                    "taskFieldSetting": {"key_fields": ["id", "resource_type_id", "system_id"]},
                },
                result_table_id="11_legacy_logical",
            )
            self.resources[key]["metadata"]["annotations"]["task_stopped"] = "true"
        self.requests = []
        self.timeout = None
        self.apply_then_timeout = False
        self.on_put = None
        self.on_get = None
        self.atomic_depth = len(connection.atomic_blocks)
        self.enterContext(mock.patch("requests.sessions.Session.request", side_effect=self.transport))
        self.enterContext(mock.patch.object(BkBaseV4Resource, "build_header", return_value={}))
        self.pre_check = self.enterContext(mock.patch.object(ToggleJoinDataResource, "pre_check", return_value=None))
        self.enterContext(mock.patch("core.lock.CacheLock")).return_value.locked = False

    @staticmethod
    def ref(kind, name):
        return {"kind": kind, "tenant": "default", "namespace": "audit", "name": name}

    def remote(self, kind, name, spec, **labels):
        return {
            "kind": kind,
            "metadata": {**self.ref(kind, name), "labels": labels, "annotations": {"keep": "value"}},
            "spec": spec,
            "status": {"phase": "Ok", "history_id": 10, "start_time": "2026-11-01 00:00:00.000000000 UTC"},
        }

    def transport(self, method, url, **kwargs):
        self.assertEqual(len(connection.atomic_blocks), self.atomic_depth, "HTTP inside DB transaction")
        name = url.rstrip("/").rsplit("/", 1)[-1]
        self.assertIn("/v4/", url)
        self.assertIn(name, self.resources)
        self.requests.append((method, name, deepcopy(kwargs.get("json"))))
        if method == "PUT":
            self.assertIsNone(kwargs["json"]["status"])
            if self.timeout == name and not self.apply_then_timeout:
                raise requests.Timeout("synthetic lost response")
            self.resources[name].update(deepcopy(kwargs["json"]))
            self.resources[name]["status"] = {
                "phase": "Pending",
                "history_id": 11,
                "start_time": "2026-11-01 00:01:00.000000000 UTC",
            }
            if self.on_put:
                self.on_put()
            if self.timeout == name:
                raise requests.Timeout("synthetic lost response")
        else:
            self.assertEqual(method, "GET")
            if self.on_get:
                self.on_get(name)
        result = requests.Response()
        result.status_code = 200
        result.url = url
        result.request = requests.Request(method, url).prepare()
        result._content = json.dumps({"result": True, "code": "00", "data": self.resources[name]}).encode()
        return result

    def enable(self, **changes):
        return ToggleJoinDataResource().request(
            {
                "system_id": self.system.system_id,
                "resource_type_id": "asset",
                "is_enabled": True,
                "storage_type": ["doris", "hdfs"],
                **changes,
            }
        )

    def puts(self):
        return [(name, payload) for method, name, payload in self.requests if method == "PUT"]

    def operation(self):
        self.snapshot.refresh_from_db()
        return self.snapshot.bkbase_v4_resources["source_replay"]

    def downstream_running(self):
        self.ready("clean")
        for key in self.binding["storages"]:
            self.resources[key]["metadata"]["annotations"]["task_stopped"] = "false"

    def advance(self, expected=SnapshotRunningStatus.PREPARING):
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, expected, self.snapshot.status_msg)

    def ready(self, key):
        current = self.resources[key]
        current["status"]["phase"] = "Ok"
        if key in ("clean", "source"):
            current["spec"].update(desired_status="Running", current_status="Running")

    def test_restore_existing_downstream_before_starting_the_source(self):
        old = deepcopy(self.resources)
        self.assertEqual(self.enable()["status"], SnapshotRunningStatus.PREPARING)
        self.assertEqual(self.puts(), [])
        self.advance()
        self.advance()
        self.assertEqual([key for key, _ in self.puts()], ["clean"])
        self.assertEqual(
            self.operation()["writes"]["clean"], {"accepted": True, "history_id": 11, "observed": "pending"}
        )
        self.ready("clean")
        self.advance()
        self.ready("doris")
        self.advance()
        self.ready("hdfs")
        self.advance()
        self.advance()
        self.assertEqual([key for key, _ in self.puts()], ["clean", "doris", "hdfs", "source"])
        payloads = dict(self.puts())
        self.assertEqual(payloads["clean"]["spec"]["rules"], old["clean"]["spec"]["rules"])
        self.assertGreater(payloads["clean"]["spec"]["deploy_revision"], 42)
        self.assertEqual(payloads["doris"]["metadata"]["annotations"], {"keep": "value", "task_stopped": "false"})
        self.assertEqual(payloads["doris"]["spec"], old["doris"]["spec"])
        self.assertEqual(payloads["source"]["spec"]["desired_status"], "Created")
        expected_report = deepcopy(old["source"]["spec"]["report_config"])
        expected_report["history_data"]["start_time"] = "0"
        self.assertEqual(payloads["source"]["spec"]["report_config"], expected_report)
        self.ready("source")
        self.advance(SnapshotRunningStatus.RUNNING)
        self.advance(SnapshotRunningStatus.RUNNING)
        self.assertEqual(len(self.puts()), 4)
        self.assertEqual(set(self.snapshot.storages.values_list("status", flat=True)), {SnapshotRunningStatus.RUNNING})

    def test_remote_binding_mismatch_leaves_snapshot_and_platform_untouched(self):
        self.resources["hdfs"]["spec"]["tableInfo"]["source"] = self.ref("ResultTable", "wrong_rt")
        before = Snapshot.objects.values().get(pk=self.snapshot.pk)
        with self.assertRaises(BKBaseResourceMappingError):
            self.enable()
        self.assertEqual(Snapshot.objects.values().get(pk=self.snapshot.pk), before)
        self.assertEqual(self.puts(), [])

    def test_missing_reference_does_not_precheck_or_mutate_snapshot(self):
        self.binding.pop("result_table")
        Snapshot.objects.filter(pk=self.snapshot.pk).update(bkbase_v4_resources=self.binding)
        with self.assertRaises(BKBaseResourceMappingError):
            self.enable()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.CLOSED)
        self.assertEqual(self.snapshot.bkbase_v4_resources, self.binding)
        self.assertEqual(self.requests, [])
        self.pre_check.assert_not_called()

    def test_pending_operation_refuses_another_toggle(self):
        self.enable()
        with self.assertRaises(SnapshotPreparingException):
            self.enable()
        self.advance()
        self.assertEqual([key for key, _ in self.puts()], ["clean"])

    def test_ready_existing_downstream_accepts_source_get_with_new_latest_history(self):
        self.downstream_running()
        self.enable()
        self.advance()
        self.assertEqual([key for key, _ in self.puts()], ["source"])
        self.assertTrue(self.operation()["writes"]["data_source"]["accepted"])
        self.ready("source")
        self.resources["source"]["status"]["history_id"] = 22
        self.advance(SnapshotRunningStatus.RUNNING)
        self.assertEqual(len(self.puts()), 1)

    def test_pending_and_failed_storage_never_start_source(self):
        self.ready("clean")
        self.enable()
        self.advance()
        self.advance()
        self.assertEqual([key for key, _ in self.puts()], ["doris"])
        self.resources["doris"]["status"]["phase"] = "Failed"
        self.advance(SnapshotRunningStatus.FAILED)
        self.assertFalse(self.operation()["active"])
        self.assertEqual(self.operation()["writes"]["doris"]["observed"], "failed")
        self.assertEqual(self.snapshot.storages.get(storage_type="doris").status, SnapshotRunningStatus.FAILED)
        self.advance(SnapshotRunningStatus.FAILED)
        self.assertEqual([key for key, _ in self.puts()], ["doris"])

    def test_explicit_failed_storage_recovery_waits_for_new_same_configuration_generation(self):
        self.downstream_running()
        storage = self.resources["doris"]
        storage["status"]["phase"] = "Failed"
        storage["metadata"]["annotations"]["bk_username"] = "original_operator"
        before = deepcopy(storage)

        def reuse_history_and_rewrite_updater():
            storage["status"]["history_id"] = before["status"]["history_id"]
            storage["metadata"]["annotations"]["bk_username"] = "new_operator"

        self.on_put = reuse_history_and_rewrite_updater
        self.enable()
        self.advance()
        [(name, payload)] = self.puts()
        self.assertEqual(name, "doris")
        self.assertEqual(payload, {"metadata": before["metadata"], "spec": before["spec"], "status": None})
        new_status = deepcopy(storage["status"])
        self.advance()
        storage["status"] = before["status"]
        self.advance()
        self.assertEqual([name for name, _ in self.puts()], ["doris"])
        storage["status"] = {**new_status, "phase": "Ok"}
        self.on_put = None
        self.advance()
        self.assertEqual([name for name, _ in self.puts()], ["doris", "source"])
        self.ready("source")
        self.advance(SnapshotRunningStatus.RUNNING)

    def test_unknown_same_storage_retry_never_resends_or_uses_unattributed_ok(self):
        self.downstream_running()
        self.resources["doris"]["status"]["phase"] = "Failed"
        self.timeout = "doris"
        self.apply_then_timeout = True
        self.enable()
        self.advance()
        self.resources["doris"]["status"]["phase"] = "Ok"
        self.resources["doris"]["status"]["history_id"] = 10
        with mock.patch.object(snapshot_restore, "BKBASE_V4_MAX_POLLS", 1):
            self.advance(SnapshotRunningStatus.FAILED)
        self.assertTrue(self.operation()["outcome_unknown"])
        self.enable()
        self.advance()
        self.assertEqual([name for name, _ in self.puts()], ["doris"])

    def test_attributed_storage_failure_can_be_retried_once_by_new_enable(self):
        self.downstream_running()
        self.resources["doris"]["status"]["phase"] = "Failed"
        self.enable()
        self.advance()
        self.resources["doris"]["status"]["phase"] = "Failed"
        self.advance(SnapshotRunningStatus.FAILED)
        self.assertEqual(self.operation()["writes"]["doris"]["observed"], "failed")
        self.advance(SnapshotRunningStatus.FAILED)
        self.assertEqual([name for name, _ in self.puts()], ["doris"])
        self.enable()
        self.advance()
        self.assertEqual([name for name, _ in self.puts()], ["doris", "doris"])

    def test_explicit_retry_after_unknown_only_observes_same_attempt(self):
        self.downstream_running()
        self.enable()
        self.timeout = "source"
        self.advance()
        self.assertTrue(self.operation()["outcome_unknown"])
        old_operation = self.operation()["operation_id"]
        with mock.patch.object(snapshot_restore, "BKBASE_V4_MAX_POLLS", 1):
            self.advance(SnapshotRunningStatus.FAILED)
        self.assertTrue(self.operation()["outcome_unknown"])
        self.enable()
        self.assertNotEqual(old_operation, self.operation()["operation_id"])
        self.advance()
        self.assertEqual([key for key, _ in self.puts()], ["source"])

    def test_unknown_applied_source_can_be_confirmed_without_another_write(self):
        self.downstream_running()
        self.enable()
        self.timeout = "source"
        self.apply_then_timeout = True
        self.advance()
        self.assertTrue(self.operation()["outcome_unknown"])
        self.advance()
        self.ready("source")
        self.advance(SnapshotRunningStatus.RUNNING)
        self.assertFalse(self.operation()["outcome_unknown"])
        self.assertIsNone(self.operation()["writes"]["data_source"]["accepted"])
        self.assertEqual(self.operation()["writes"]["data_source"]["observed"], "running")
        self.assertEqual(len(self.puts()), 1)

    def test_snapshot_lock_busy_skips_tick_without_spending_observation_budget(self):
        self.enable()
        with snapshot_lock(self.snapshot.system_id, self.snapshot.resource_type_id):
            self.advance()
        self.assertEqual(self.puts(), [])
        self.assertEqual(self.operation()["poll_count"], 0)
        self.advance()
        self.assertEqual(len(self.puts()), 1)

    def test_stale_put_receipt_cannot_overwrite_a_different_operation(self):
        self.enable()

        def supersede():
            state = self.operation()
            self.assertIsNone(state["writes"]["clean"]["accepted"])
            self.assertTrue(state["outcome_unknown"])
            self.snapshot.bkbase_v4_resources["source_replay"]["operation_id"] = "different"
            self.snapshot.save(update_fields=["bkbase_v4_resources"])

        self.on_put = supersede
        self.advance()
        self.assertEqual(self.operation()["operation_id"], "different")
        self.assertIsNone(self.operation()["writes"]["clean"]["accepted"])

    def test_remote_drift_or_local_shared_writer_prevents_any_restore_write(self):
        self.enable()
        self.resources["doris"]["spec"]["tableInfo"]["expire"] = 99
        self.advance(SnapshotRunningStatus.FAILED)
        self.assertEqual(self.puts(), [])
        Snapshot.objects.create(
            system_id="other_system",
            resource_type_id="different",
            bkbase_v4_resources={"clean": self.binding["clean"]},
        )
        before = Snapshot.objects.values().get(pk=self.snapshot.pk)
        with self.assertRaises(BKBaseResourceMappingError):
            self.enable()
        self.assertEqual(Snapshot.objects.values().get(pk=self.snapshot.pk), before)
        self.assertEqual(self.puts(), [])

    def basic_collector(self):
        self.snapshot.join_data_type = "basic"
        self.binding["storages"] = {"redis": self.ref("DataStorage", "redis")}
        self.snapshot.bkbase_v4_resources = self.binding
        self.snapshot.save(update_fields=["join_data_type", "bkbase_v4_resources"])
        self.snapshot.storages.all().delete()
        SnapshotStorage.objects.create(snapshot=self.snapshot, storage_type="redis")
        self.resources["redis"] = self.remote(
            "DataStorage",
            "redis",
            {
                "tableInfo": {
                    "source": self.binding["result_table"],
                    "storage": self.ref("Redis", "redis_cluster"),
                    "storage_type": "join",
                },
                "taskFieldSetting": {"key_fields": ["id", "resource_type_id", "system_id"]},
            },
            result_table_id="11_legacy_logical",
        )
        binding = {
            "clean": self.ref("Clean", "log_clean"),
            "clean_role": "existing",
            "data_id": self.ref("DataId", "log_input"),
            "source_raw_data_id": 81,
            "result_table": self.ref("ResultTable", "81_log_actual"),
            "clean_ready": True,
        }
        collector = CollectorConfig.objects.create(
            system_id=self.system.system_id,
            collector_config_name_en="unlinked",
            bk_biz_id=1,
            bk_data_id=81,
            collector_config_id=1,
            collector_plugin_id=1,
            bkbase_v4_resources=binding,
        )
        self.resources["81_log_actual"] = self.remote(
            "ResultTable",
            "81_log_actual",
            {"fields": [{"field_name": "snapshot_instance_data"}, {"field_name": "snapshot_instance_name"}]},
            result_table_id="81_log_actual",
        )
        self.resources["log_clean"] = self.remote(
            "Clean",
            "log_clean",
            {
                "raw_data_id": 81,
                "data_id": binding["data_id"],
                "result_table_id": "81_log_actual",
                "result_table_source": "existing",
                "desired_status": "Running",
                "current_status": "Running",
                "config_revision": 42,
                "deploy_revision": 42,
                "rules": [
                    {"input_id": "json_data", "output_id": "keep", "operator": {"type": "assign"}},
                    {
                        "input_id": "json_data",
                        "output_id": "snapshot_instance_data",
                        "operator": {"type": "assign", "key_index": "snapshot_instance_data", "output_type": "text"},
                    },
                ],
                "join": [
                    {
                        "result_table_id": "other_dimension",
                        "join_on": [{"this_field": "action_id", "target_field": "id"}],
                        "select": [{"field_name": "data", "type": "text", "as": "snapshot_action_info"}],
                    }
                ],
            },
        )
        self.initial_log_clean = deepcopy(self.resources["log_clean"])
        self.downstream_running()
        return collector

    def enable_basic(self):
        return self.enable(join_data_type="basic", storage_type=["redis"])

    def page_toggle(self, pull_type="partial"):
        return ToggleJoinDataResource().request(
            {
                "system_id": self.system.system_id,
                "resource_type_id": "asset",
                "is_enabled": True,
                "pull_type": pull_type,
            }
        )

    def test_enable_page_updates_full_to_partial_and_preserves_basic_redis(self):
        self.basic_collector()
        self.snapshot.pull_type = "full"
        self.snapshot.save(update_fields=["pull_type"])
        resource_type = ResourceType.objects.get(system_id=self.system.system_id, resource_type_id="asset")
        config = HttpPullHandler(self.system, resource_type, self.snapshot, "basic").config["access_conf_info"]
        self.resources["source"]["spec"]["report_config"].update(
            body=config["resource"]["scope"][0]["body"]["content"], period=config["collection_model"]["period"]
        )
        result = self.page_toggle()
        self.snapshot.refresh_from_db()
        self.assertEqual(result["status"], SnapshotRunningStatus.PREPARING)
        self.assertEqual(result["storage_type"], ["redis"])
        self.assertEqual(result["join_data_type"], "basic")
        self.assertEqual(self.snapshot.pull_type, "full")
        self.assertEqual(self.puts(), [])
        self.advance()
        self.assertIn('"start_time": <start>', self.puts()[-1][1]["spec"]["report_config"]["body"])
        self.ready("source")
        self.advance()
        self.resources["log_clean"]["status"]["phase"] = "Ok"
        self.advance(SnapshotRunningStatus.RUNNING)
        self.assertEqual(self.snapshot.pull_type, "partial")

    def test_enable_page_preserves_encrypted_conn_for_same_partial_mode(self):
        self.basic_collector()
        connection = self.resources["conn"]
        connection["metadata"]["annotations"]["conn_info_encrypted"] = "true"
        connection["spec"]["conn_info"]["headers"]["Authorization"] = "opaque-cipher"
        before = deepcopy(connection)
        self.assertEqual(self.page_toggle()["status"], SnapshotRunningStatus.PREPARING)
        self.advance()
        self.ready("source")
        self.advance()
        self.resources["log_clean"]["status"]["phase"] = "Ok"
        self.advance(SnapshotRunningStatus.RUNNING)
        self.assertEqual([name for name, _ in self.puts()], ["source", "log_clean"])
        self.assertEqual(self.snapshot.pull_type, "partial")
        self.assertEqual(self.resources["conn"], before)

    def test_enable_page_does_not_assume_unmarked_authorization_is_encrypted(self):
        self.basic_collector()
        self.resources["conn"]["spec"]["conn_info"]["headers"]["Authorization"] = "unverified-value"
        with self.assertRaises(BKBaseResourceMappingError):
            self.page_toggle()
        self.assertEqual(self.puts(), [])

    def test_enable_rejects_explicit_storage_change(self):
        self.basic_collector()
        with self.assertRaises(BKBaseResourceMappingError):
            self.enable(storage_type=["doris"], join_data_type="basic")
        self.assertEqual(self.puts(), [])

    def update_stopped_callback(self):
        callback = "https://new-source.test/instances"
        with mock.patch.object(System, "update_join_data") as schedule:
            UpdateSystem().request(system_id=self.system.system_id, namespace="audit", callback_url=callback)
        schedule.assert_called_once()
        self.system.refresh_from_db()
        tasks.refresh_system_snapshots.run(self.system.system_id)
        self.assertEqual(self.puts(), [])
        return callback

    def encrypt_connection_write(self):
        conn = self.resources["conn"]
        conn["metadata"]["annotations"]["conn_info_encrypted"] = "true"
        conn["spec"]["conn_info"]["headers"]["Authorization"] = "next-cipher"
        conn["spec"]["updated_by"] = "new_operator"

    def test_restore_updates_owned_asset_callback_connection_before_starting_source(self):
        self.downstream_running()
        callback = self.update_stopped_callback()
        self.assertNotIn("source_provision", self.snapshot.bkbase_v4_resources)
        self.assertEqual(self.page_toggle()["status"], SnapshotRunningStatus.PREPARING)
        self.on_put = self.encrypt_connection_write
        self.advance()
        self.on_put = None
        [(name, payload)] = self.puts()
        self.assertEqual(name, "conn")
        self.assertEqual(payload["spec"]["conn_info"]["url"], callback)
        self.assertEqual(payload["spec"]["conn_info"]["headers"]["Authorization"], self.system.base64_token)
        self.advance()
        self.assertEqual([name for name, _ in self.puts()], ["conn"])
        self.resources["conn"]["status"]["phase"] = "Ok"
        self.advance()
        self.assertEqual([name for name, _ in self.puts()], ["conn", "source"])
        self.assertEqual(self.puts()[-1][1]["spec"]["report_config"]["history_data"]["start_time"], "0")
        self.ready("source")
        self.advance(SnapshotRunningStatus.RUNNING)

    def test_restore_does_not_start_source_after_unattributed_encrypted_connection_update(self):
        self.downstream_running()
        self.update_stopped_callback()
        self.page_toggle()
        self.on_put = self.encrypt_connection_write
        self.timeout = "conn"
        self.apply_then_timeout = True
        self.advance()
        self.resources["conn"]["status"]["phase"] = "Ok"
        with mock.patch.object(snapshot_restore, "BKBASE_V4_MAX_POLLS", 1):
            self.advance(SnapshotRunningStatus.FAILED)
        self.assertTrue(self.operation()["outcome_unknown"])
        self.page_toggle()
        self.advance()
        self.assertEqual([name for name, _ in self.puts()], ["conn"])

    def test_restore_retries_attributed_failed_callback_connection_on_explicit_enable(self):
        self.downstream_running()
        callback = self.update_stopped_callback()
        self.page_toggle()
        self.on_put = self.encrypt_connection_write
        self.advance()
        connection = self.resources["conn"]
        connection["status"]["phase"] = "Failed"
        self.advance(SnapshotRunningStatus.FAILED)
        self.assertEqual(self.operation()["writes"]["connection"]["observed"], "failed")
        self.advance(SnapshotRunningStatus.FAILED)
        self.assertEqual([name for name, _ in self.puts()], ["conn"])
        previous_status = deepcopy(connection["status"])

        def save_same_configuration_without_new_history():
            self.encrypt_connection_write()
            connection["status"].pop("history_id")
            connection["status"]["start_time"] = "2026-11-01 00:02:00.000000000 UTC"

        self.on_put = save_same_configuration_without_new_history
        self.page_toggle()
        self.advance()
        self.assertEqual([name for name, _ in self.puts()], ["conn", "conn"])
        self.assertEqual(self.puts()[-1][1]["spec"]["conn_info"]["url"], callback)
        self.assertEqual(self.puts()[-1][1]["spec"]["conn_info"]["headers"]["Authorization"], self.system.base64_token)
        current_status = deepcopy(connection["status"])
        connection["status"] = previous_status
        self.advance()
        self.assertEqual([name for name, _ in self.puts()], ["conn", "conn"])
        connection["status"] = {**current_status, "phase": "Ok"}
        self.on_put = None
        self.advance()
        self.assertEqual([name for name, _ in self.puts()], ["conn", "conn", "source"])
        self.ready("source")
        self.advance(SnapshotRunningStatus.RUNNING)

    def test_restore_rejects_callback_connection_owned_by_another_local_snapshot(self):
        self.downstream_running()
        self.update_stopped_callback()
        Snapshot.objects.create(
            system_id=self.system.system_id,
            resource_type_id="other",
            bkbase_v4_resources={"data_conn": self.ref("DataConn", "conn")},
        )
        with self.assertRaisesMessage(BKBaseResourceMappingError, "another local writer"):
            self.page_toggle()
        self.assertEqual(self.puts(), [])

    def test_restore_never_updates_basic_shared_callback_connection(self):
        self.basic_collector()
        self.update_stopped_callback()
        with self.assertRaisesMessage(BKBaseResourceMappingError, "verified exclusive Basic DataConn"):
            self.page_toggle()
        self.assertEqual(self.puts(), [])

    def provisioned_basic(self):
        collector = self.basic_collector()
        collector.join_data_rt = self.snapshot.bkbase_table_id
        collector.save(update_fields=["join_data_rt"])
        self.binding.update(
            clean_role="existing",
            raw_data_id=self.snapshot.bkbase_data_id,
            source_provision={
                "operation_id": "original_operation",
                "stage": "ready",
                "source_name": "source",
                "conn_name": "conn",
                "accepted_source": self.binding["data_source"],
            },
        )
        self.resources["clean"]["spec"]["result_table_source"] = "existing"
        self.snapshot.bkbase_v4_resources = self.binding
        self.snapshot.save(update_fields=["bkbase_v4_resources"])

    def test_restore_updates_self_provisioned_basic_connection_and_preserves_existing_clean(self):
        self.provisioned_basic()
        Snapshot.objects.create(
            system_id=self.system.system_id,
            resource_type_id="table_owner",
            bkbase_v4_resources={"result_table": self.binding["result_table"], "clean_role": "owner"},
        )
        callback = self.update_stopped_callback()
        self.assertEqual(self.page_toggle()["status"], SnapshotRunningStatus.PREPARING)
        self.on_put = self.encrypt_connection_write
        self.advance()
        self.on_put = None
        [(name, payload)] = self.puts()
        self.assertEqual(name, "conn")
        self.assertEqual(payload["spec"]["conn_info"]["url"], callback)
        self.assertEqual(payload["spec"]["conn_info"]["headers"]["Authorization"], self.system.base64_token)
        self.advance()
        self.assertEqual([name for name, _ in self.puts()], ["conn"])
        self.ready("conn")
        self.advance()
        self.assertEqual([name for name, _ in self.puts()], ["conn", "source"])
        self.ready("source")
        self.advance(SnapshotRunningStatus.RUNNING)
        self.assertEqual(self.snapshot.bkbase_v4_resources["clean_role"], "existing")
        self.assertEqual(self.resources["clean"]["spec"]["result_table_source"], "existing")

    def test_running_refresh_rejects_basic_connection_without_ownership_evidence(self):
        self.basic_collector()
        self.ready("source")
        self.snapshot.status = SnapshotRunningStatus.RUNNING
        self.snapshot.save(update_fields=["status"])
        self.snapshot.storages.update(status=SnapshotRunningStatus.RUNNING)
        self.update_stopped_callback()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.RUNNING)
        self.assertIn("verified exclusive Basic DataConn", self.snapshot.status_msg)
        self.assertNotIn("source_replay", self.snapshot.bkbase_v4_resources)
        self.assertEqual(self.puts(), [])

    def test_restore_rejects_self_provisioned_basic_connection_with_local_binding(self):
        self.provisioned_basic()
        self.update_stopped_callback()
        Snapshot.objects.create(
            system_id=self.system.system_id,
            resource_type_id="other",
            bkbase_v4_resources={"data_conn": self.ref("DataConn", "conn")},
        )
        with self.assertRaisesMessage(BKBaseResourceMappingError, "another local writer"):
            self.page_toggle()
        self.assertEqual(self.puts(), [])

    def configure_running_basic(self):
        self.provisioned_basic()
        self.ready("source")
        self.snapshot.status = SnapshotRunningStatus.RUNNING
        self.snapshot.save(update_fields=["status"])
        self.snapshot.storages.update(status=SnapshotRunningStatus.RUNNING)
        callback = self.update_stopped_callback()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING, self.snapshot.status_msg)
        self.assertEqual(self.operation()["mode"], "configure")
        self.assertTrue(self.operation()["connection_required"])
        return callback

    def test_running_refresh_updates_self_provisioned_basic_connection(self):
        callback = self.configure_running_basic()
        self.on_put = self.encrypt_connection_write
        self.advance()
        self.on_put = None
        self.assertEqual([name for name, _ in self.puts()], ["conn"])
        self.assertEqual(self.puts()[0][1]["spec"]["conn_info"]["url"], callback)
        self.advance()
        self.assertEqual([name for name, _ in self.puts()], ["conn"])
        self.ready("conn")
        self.advance()
        self.assertEqual([name for name, _ in self.puts()], ["conn", "source"])
        self.ready("source")
        self.advance(SnapshotRunningStatus.RUNNING)
        self.assertEqual(self.snapshot.bkbase_v4_resources["clean_role"], "existing")

    def fail_running_basic_connection(self):
        self.configure_running_basic()
        self.on_put = self.encrypt_connection_write
        self.advance()
        self.on_put = None
        self.resources["conn"]["status"]["phase"] = "Failed"
        self.advance(SnapshotRunningStatus.FAILED)
        operation = self.operation()
        self.assertEqual(operation["connection_phase"], "Failed")
        self.assertTrue(operation["connection_accepted"])
        self.assertFalse(operation["attempted"])
        self.assertFalse(operation["outcome_unknown"])
        self.assertEqual([name for name, _ in self.puts()], ["conn"])
        return operation

    def test_enable_retries_confirmed_running_connection_failure_before_source_write(self):
        failed = self.fail_running_basic_connection()
        self.advance(SnapshotRunningStatus.FAILED)
        self.assertEqual([name for name, _ in self.puts()], ["conn"])
        old_status = deepcopy(self.resources["conn"]["status"])
        self.assertEqual(self.page_toggle()["status"], SnapshotRunningStatus.PREPARING)
        self.assertNotEqual(self.operation()["operation_id"], failed["operation_id"])
        self.assertEqual([name for name, _ in self.puts()], ["conn"])

        def encrypt_new_generation():
            self.encrypt_connection_write()
            self.resources["conn"]["status"].pop("history_id")
            self.resources["conn"]["status"]["start_time"] = "2026-11-01 00:02:00.000000000 UTC"

        self.on_put = encrypt_new_generation
        self.advance()
        self.on_put = None
        current_status = deepcopy(self.resources["conn"]["status"])
        self.assertEqual([name for name, _ in self.puts()], ["conn", "conn"])
        self.resources["conn"]["status"] = old_status
        self.advance()
        self.assertEqual([name for name, _ in self.puts()], ["conn", "conn"])
        self.resources["conn"]["status"] = {**current_status, "phase": "Ok"}
        self.advance()
        self.assertEqual([name for name, _ in self.puts()], ["conn", "conn", "source"])
        self.ready("source")
        self.advance(SnapshotRunningStatus.RUNNING)

    def test_enable_rejects_running_connection_retry_when_observed_generation_changed(self):
        failed = self.fail_running_basic_connection()
        self.resources["conn"]["status"]["history_id"] += 1
        with self.assertRaisesMessage(BKBaseResourceMappingError, "no longer matches the confirmed failure"):
            self.page_toggle()
        self.assertEqual(self.operation(), failed)
        self.assertEqual([name for name, _ in self.puts()], ["conn"])

    def test_queued_running_connection_retry_checks_local_ownership_again(self):
        self.fail_running_basic_connection()
        self.page_toggle()
        Snapshot.objects.create(
            system_id=self.system.system_id,
            resource_type_id="other",
            bkbase_v4_resources={"data_conn": self.ref("DataConn", "conn")},
        )
        self.advance(SnapshotRunningStatus.FAILED)
        self.assertEqual([name for name, _ in self.puts()], ["conn"])

    def test_enable_does_not_retry_running_connection_after_source_write(self):
        self.configure_running_basic()
        self.on_put = self.encrypt_connection_write
        self.advance()
        self.on_put = None
        self.ready("conn")
        self.advance()
        self.resources["conn"]["status"]["phase"] = "Failed"
        self.advance(SnapshotRunningStatus.FAILED)
        self.assertTrue(self.operation()["attempted"])
        self.page_toggle()
        self.advance(SnapshotRunningStatus.FAILED)
        self.assertEqual([name for name, _ in self.puts()], ["conn", "source"])

    def test_enable_does_not_retry_unknown_running_connection(self):
        self.configure_running_basic()
        self.on_put = self.encrypt_connection_write
        self.timeout = "conn"
        self.apply_then_timeout = True
        self.advance()
        self.ready("conn")
        with mock.patch.object(source, "BKBASE_V4_MAX_POLLS", 1):
            self.advance(SnapshotRunningStatus.FAILED)
        self.assertTrue(self.operation()["outcome_unknown"])
        with self.assertRaisesMessage(BKBaseResourceMappingError, "Previous Snapshot source write is unresolved"):
            self.page_toggle()
        self.assertEqual([name for name, _ in self.puts()], ["conn"])

    def test_running_page_saves_new_pull_type_only_after_source_get_confirms(self):
        self.downstream_running()
        self.ready("source")
        self.snapshot.status = SnapshotRunningStatus.RUNNING
        self.snapshot.save(update_fields=["status"])
        self.snapshot.storages.update(status=SnapshotRunningStatus.RUNNING)
        self.resources["source"]["spec"]["updated_by"] = "original_operator"
        self.resources["conn"]["spec"]["conn_info"]["headers"]["Authorization"] = "opaque-cipher"
        self.resources["conn"]["metadata"]["annotations"]["conn_info_encrypted"] = "true"
        old_connection = deepcopy(self.resources["conn"])
        self.assertEqual(self.page_toggle("full")["status"], SnapshotRunningStatus.PREPARING)
        self.assertEqual(self.snapshot.pull_type, "partial")
        self.assertEqual(self.operation()["mode"], "configure")
        self.assertEqual(self.snapshot.pull_type, "partial")
        self.on_put = lambda: self.resources["source"]["spec"].update(updated_by="new_operator")
        self.advance()
        [(name, payload)] = self.puts()
        self.assertEqual(name, "source")
        self.assertIn('"start_time": 0', payload["spec"]["report_config"]["body"])
        self.assertEqual(payload["spec"]["report_config"]["history_data"]["start_time"], "0")
        self.assertEqual(self.snapshot.pull_type, "partial")
        self.ready("source")
        self.resources["source"]["status"]["history_id"] = 22
        self.advance(SnapshotRunningStatus.RUNNING)
        self.assertEqual(self.snapshot.pull_type, "full")
        self.assertEqual(self.resources["conn"], old_connection)

    def configure_basic_collector_etl(self, collector):
        plugin_clean = self.ref("Clean", "plugin_clean")
        plugin_input = self.ref("DataId", "plugin_input")
        self.resources["plugin_clean"] = self.remote(
            "Clean",
            "plugin_clean",
            {
                "raw_data_id": 83,
                "data_id": plugin_input,
                "result_table_id": "81_log_actual",
                "result_table_source": "new",
                "desired_status": "Running",
                "current_status": "Running",
                "config_revision": 42,
                "deploy_revision": 42,
            },
        )
        CollectorPlugin.objects.get_or_create(
            collector_plugin_id=collector.collector_plugin_id,
            defaults={
                "namespace": "audit",
                "collector_plugin_name_en": "restore_test",
                "bkdata_biz_id": 1,
                "table_id": 1,
                "index_set_id": 1,
                "bkbase_v4_resources": {
                    "clean": plugin_clean,
                    "clean_role": "owner",
                    "data_id": plugin_input,
                    "source_raw_data_id": 83,
                    "result_table": collector.bkbase_v4_resources["result_table"],
                    "result_table_id": "81_log_actual",
                },
            },
        )
        return CollectorEtlResource().request(
            {**deepcopy(CREATE_COLLECTOR_ETL_DATA), "collector_config_id": collector.collector_config_id}
        )

    def test_basic_restores_unlinked_v4_collector_after_independent_clean_get(self):
        collector = self.basic_collector()
        before = deepcopy(self.resources["log_clean"])
        self.assertIsNone(collector.bkbase_table_id)
        self.assertEqual(self.enable_basic()["status"], SnapshotRunningStatus.PREPARING)
        self.assertEqual(self.puts(), [])
        self.advance()
        self.ready("source")
        self.advance()
        self.assertEqual([name for name, _ in self.puts()], ["source", "log_clean"])
        payload = self.puts()[-1][1]
        self.assertEqual(payload["metadata"], before["metadata"])
        spec = payload["spec"]
        self.assertGreater(spec["config_revision"], 42)
        self.assertEqual(spec["deploy_revision"], spec["config_revision"])
        self.assertEqual(spec["rules"], before["spec"]["rules"][:1])
        self.assertEqual(spec["join"][:-1], before["spec"]["join"])
        self.assertEqual(
            spec["join"][-1],
            {
                "result_table_id": "11_legacy_logical",
                "join_on": [
                    {"this_field": "instance_id", "target_field": "id"},
                    {"this_field": "resource_type_id", "target_field": "resource_type_id"},
                    {"this_field": "system_id", "target_field": "system_id"},
                ],
                "select": [
                    {"field_name": "data", "type": "text", "as": "snapshot_instance_data"},
                    {"field_name": "display_name", "type": "string", "as": "snapshot_instance_name"},
                ],
            },
        )
        self.advance()
        collector.refresh_from_db()
        self.assertIsNone(collector.join_data_rt)
        self.resources["log_clean"]["status"].update(phase="Pending", history_id=22)
        self.advance()
        collector.refresh_from_db()
        self.assertIsNone(collector.join_data_rt)
        self.resources["log_clean"]["status"].update(phase="Ok", history_id=23)
        self.advance(SnapshotRunningStatus.RUNNING)
        collector.refresh_from_db()
        self.assertEqual(collector.join_data_rt, "11_legacy_logical")
        self.assertIsNone(collector.bkbase_table_id)
        self.assertEqual([name for name, _ in self.puts()], ["source", "log_clean"])

    def test_basic_unknown_clean_put_never_reuses_old_running_state_or_resends(self):
        collector = self.basic_collector()
        self.enable_basic()
        self.advance()
        self.ready("source")
        self.timeout = "log_clean"
        self.advance()
        self.advance()
        collector.refresh_from_db()
        self.assertIsNone(collector.join_data_rt)
        self.assertEqual([name for name, _ in self.puts()], ["source", "log_clean"])
        self.assertTrue(self.operation()["outcome_unknown"])

    def test_basic_confirms_applied_unknown_clean_write_without_resending(self):
        collector = self.basic_collector()
        self.enable_basic()
        self.advance()
        self.ready("source")
        self.timeout = "log_clean"
        self.apply_then_timeout = True
        self.advance()
        self.assertTrue(self.operation()["outcome_unknown"])
        self.resources["log_clean"]["status"]["phase"] = "Ok"
        self.advance(SnapshotRunningStatus.RUNNING)
        collector.refresh_from_db()
        self.assertEqual(collector.join_data_rt, "11_legacy_logical")
        self.assertEqual([name for name, _ in self.puts()], ["source", "log_clean"])
        self.assertFalse(self.operation()["outcome_unknown"])

    def test_basic_adopts_an_existing_matching_join_without_republishing(self):
        collector = self.basic_collector()
        existing = JoinConfig("11_legacy_logical").config
        existing["join_on"] = existing["join_on"][1:] + existing["join_on"][:1]
        spec = self.resources["log_clean"]["spec"]
        spec["join"].append(existing)
        spec["rules"] = spec["rules"][:1]
        self.enable_basic()
        self.advance()
        self.ready("source")
        self.advance(SnapshotRunningStatus.RUNNING)
        collector.refresh_from_db()
        self.assertEqual(collector.join_data_rt, "11_legacy_logical")
        self.assertEqual([name for name, _ in self.puts()], ["source"])
        self.assertEqual(self.resources["log_clean"]["spec"]["join"][-1], existing)

    def test_basic_redeploys_matching_join_when_redis_key_order_differs(self):
        collector = self.basic_collector()
        existing = {**JoinConfig("11_legacy_logical").config, "extra_config": "preserved"}
        spec = self.resources["log_clean"]["spec"]
        spec["join"].append(existing)
        spec["rules"] = spec["rules"][:1]
        old_storage = deepcopy(self.resources["redis"])
        self.enable_basic()
        self.advance()
        self.ready("source")
        self.advance()
        name, payload = self.puts()[-1]
        self.assertEqual(name, "log_clean")
        actual = payload["spec"]["join"][-1]
        self.assertEqual(actual, {**existing, "join_on": existing["join_on"][1:] + existing["join_on"][:1]})
        self.assertGreater(payload["spec"]["config_revision"], 42)
        self.assertEqual(payload["spec"]["config_revision"], payload["spec"]["deploy_revision"])
        collector.refresh_from_db()
        self.assertIsNone(collector.join_data_rt)
        self.resources["log_clean"]["status"]["phase"] = "Ok"
        self.advance(SnapshotRunningStatus.RUNNING)
        collector.refresh_from_db()
        self.assertEqual(collector.join_data_rt, "11_legacy_logical")
        self.assertEqual(self.resources["redis"], old_storage)

    def test_basic_removes_known_default_output_when_existing_join_order_already_matches(self):
        collector = self.basic_collector()
        existing = JoinConfig("11_legacy_logical").config
        existing["join_on"] = existing["join_on"][1:] + existing["join_on"][:1]
        old_spec = deepcopy(self.resources["log_clean"]["spec"])
        self.resources["log_clean"]["spec"]["join"].append(existing)
        self.enable_basic()
        self.advance()
        self.ready("source")
        self.advance()
        spec = self.puts()[-1][1]["spec"]
        self.assertEqual(spec["join"], [*old_spec["join"], existing])
        self.assertEqual(spec["rules"], old_spec["rules"][:1])
        self.resources["log_clean"]["status"]["phase"] = "Ok"
        self.advance(SnapshotRunningStatus.RUNNING)
        collector.refresh_from_db()
        self.assertEqual(collector.join_data_rt, "11_legacy_logical")

    def collector_linked_to_other_snapshot(self, clean_ref):
        return CollectorConfig.objects.create(
            system_id=self.system.system_id,
            bkbase_table_id="other_log_output",
            join_data_rt="different_snapshot",
            bk_biz_id=1,
            bk_data_id=82,
            collector_config_id=2,
            collector_plugin_id=1,
            bkbase_v4_resources={"clean": clean_ref},
        )

    def test_basic_skips_an_independently_linked_collector_in_the_same_system(self):
        unlinked = self.basic_collector()
        other = self.collector_linked_to_other_snapshot(self.ref("Clean", "other_clean"))
        self.enable_basic()
        self.advance()
        self.ready("source")
        self.advance()
        self.resources["log_clean"]["status"]["phase"] = "Ok"
        self.advance(SnapshotRunningStatus.RUNNING)
        unlinked.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(unlinked.join_data_rt, "11_legacy_logical")
        self.assertEqual(other.join_data_rt, "different_snapshot")
        self.assertEqual([name for name, _ in self.puts()], ["source", "log_clean"])
        self.assertFalse(any(name == "other_clean" for _, name, _ in self.requests))

    def test_basic_refuses_to_update_clean_also_bound_to_a_different_collector(self):
        collector = self.basic_collector()
        ref = {**collector.bkbase_v4_resources["clean"], "binding_note": "legacy metadata"}
        other = self.collector_linked_to_other_snapshot(ref)
        with self.assertRaisesMessage(BKBaseResourceMappingError, "another local writer"):
            self.enable_basic()
        other.refresh_from_db()
        self.assertEqual(other.join_data_rt, "different_snapshot")
        self.assertEqual(self.puts(), [])

    def add_basic_collector(self, first):
        second_clean = deepcopy(self.initial_log_clean)
        second_clean["metadata"]["name"] = "second_clean"
        second_clean["spec"].update(raw_data_id=82, data_id=self.ref("DataId", "second_input"))
        self.resources["second_clean"] = second_clean
        return CollectorConfig.objects.create(
            system_id=self.system.system_id,
            collector_config_name_en="second",
            bk_biz_id=1,
            bk_data_id=82,
            collector_config_id=2,
            collector_plugin_id=1,
            bkbase_v4_resources={
                **first.bkbase_v4_resources,
                "clean": self.ref("Clean", "second_clean"),
                "data_id": second_clean["spec"]["data_id"],
                "source_raw_data_id": 82,
            },
        )

    def test_basic_waits_for_all_collectors_and_blocks_etl_until_finished(self):
        first = self.basic_collector()
        second = self.add_basic_collector(first)
        self.enable_basic()
        self.advance()
        self.ready("source")
        self.advance()
        self.resources["log_clean"]["status"]["phase"] = "Ok"
        self.advance()
        first.refresh_from_db()
        self.assertEqual(first.join_data_rt, "11_legacy_logical")
        with self.assertRaises(SnapshotPreparingException):
            self.configure_basic_collector_etl(first)
        self.advance()
        self.resources["second_clean"]["status"]["phase"] = "Ok"
        self.advance(SnapshotRunningStatus.RUNNING)
        second.refresh_from_db()
        self.assertEqual(second.join_data_rt, "11_legacy_logical")
        self.assertEqual([name for name, _ in self.puts()], ["source", "log_clean", "second_clean"])

    def test_basic_resumes_unknown_clean_before_adding_new_collector_without_replaying_source(self):
        first = self.basic_collector()
        self.enable_basic()
        self.advance()
        self.ready("source")
        self.timeout = "log_clean"
        self.apply_then_timeout = True
        self.advance()
        with mock.patch.object(snapshot_restore, "BKBASE_V4_MAX_POLLS", 1):
            self.advance(SnapshotRunningStatus.FAILED)
        second = self.add_basic_collector(first)
        self.enable_basic()
        self.advance()
        self.assertTrue(self.operation()["outcome_unknown"])
        self.assertEqual([name for name, _ in self.puts()], ["source", "log_clean"])
        self.resources["log_clean"]["status"]["phase"] = "Ok"
        self.advance()
        first.refresh_from_db()
        self.assertEqual(first.join_data_rt, "11_legacy_logical")
        self.finish_added_collector(second)

    def finish_added_collector(self, collector):
        self.advance()
        self.advance()
        self.resources["second_clean"]["status"]["phase"] = "Ok"
        self.advance(SnapshotRunningStatus.RUNNING)
        collector.refresh_from_db()
        self.assertEqual(collector.join_data_rt, "11_legacy_logical")
        self.assertEqual([name for name, _ in self.puts()], ["source", "log_clean", "second_clean"])

    def test_basic_observes_unknown_source_before_adding_new_collector(self):
        first = self.basic_collector()
        self.enable_basic()
        self.timeout = "source"
        self.apply_then_timeout = True
        self.advance()
        self.assertTrue(self.operation()["outcome_unknown"])
        second = self.add_basic_collector(first)
        self.advance()
        self.assertEqual([name for name, _ in self.puts()], ["source"])
        self.ready("source")
        self.advance()
        self.resources["log_clean"]["status"]["phase"] = "Ok"
        self.advance()
        self.finish_added_collector(second)

    def test_basic_retries_added_collector_preflight_without_replaying_source(self):
        first = self.basic_collector()
        self.enable_basic()
        self.advance()
        self.ready("source")
        self.advance()
        second = self.add_basic_collector(first)
        self.resources["second_clean"]["spec"]["raw_data_id"] = 99
        self.resources["log_clean"]["status"]["phase"] = "Ok"
        self.advance()
        self.advance(SnapshotRunningStatus.FAILED)
        self.assertEqual([name for name, _ in self.puts()], ["source", "log_clean"])
        self.resources["second_clean"]["spec"]["raw_data_id"] = 82
        self.enable_basic()
        self.finish_added_collector(second)

    def test_basic_final_cas_detects_collector_added_during_confirmation_get(self):
        first = self.basic_collector()
        self.enable_basic()
        self.advance()
        self.ready("source")
        self.advance()
        self.resources["log_clean"]["status"]["phase"] = "Ok"
        clean_gets, added = [], []

        def add_during_confirm(name):
            if name == "log_clean":
                clean_gets.append(name)
                if len(clean_gets) == 2:
                    added.append(self.add_basic_collector(first))

        self.on_get = add_during_confirm
        self.advance()
        self.on_get = None
        self.assertEqual(len(added), 1)
        first.refresh_from_db()
        self.assertEqual(first.join_data_rt, "11_legacy_logical")
        self.finish_added_collector(added[0])

    def test_basic_reentry_observes_old_source_and_replans_unclaimed_collector_after_etl(self):
        collector = self.basic_collector()
        self.enable_basic()
        self.timeout = "source"
        self.apply_then_timeout = True
        self.advance()
        self.configure_basic_collector_etl(collector)
        edited = deepcopy(self.resources["log_clean"]["spec"]["rules"])
        with mock.patch.object(snapshot_restore, "BKBASE_V4_MAX_POLLS", 1):
            self.advance(SnapshotRunningStatus.FAILED)
        self.ready("source")
        self.resources["log_clean"]["status"]["phase"] = "Ok"
        self.enable_basic()
        self.advance()
        payload = self.puts()[-1][1]["spec"]
        self.assertEqual(self.operation()["writes"]["data_source"]["observed"], "running")
        self.assertTrue(all(rule in edited for rule in payload["rules"]))
        self.assertEqual(payload["join"][-1]["result_table_id"], "11_legacy_logical")
        self.resources["log_clean"]["status"]["phase"] = "Ok"
        self.advance(SnapshotRunningStatus.RUNNING)
        self.assertEqual([name for name, _ in self.puts()], ["source", "log_clean", "log_clean"])
        self.assertEqual(self.puts()[0][1]["spec"]["report_config"]["history_data"]["start_time"], "0")

    def test_basic_reentry_replans_failed_added_clean_and_retires_completed_etl(self):
        first = self.basic_collector()
        self.enable_basic()
        self.advance()
        self.ready("source")
        self.advance()
        second = self.add_basic_collector(first)
        self.resources["log_clean"]["status"]["phase"] = "Ok"
        self.advance()
        self.advance()
        self.advance()
        self.resources["second_clean"]["status"]["phase"] = "Failed"
        self.advance(SnapshotRunningStatus.FAILED)
        self.configure_basic_collector_etl(first)
        self.configure_basic_collector_etl(second)
        edited = deepcopy(self.resources["second_clean"]["spec"]["rules"])
        self.resources["log_clean"]["status"]["phase"] = "Ok"
        self.resources["second_clean"]["status"]["phase"] = "Ok"
        before = len(self.puts())
        self.enable_basic()
        self.advance()
        new_writes = self.puts()[before:]
        self.assertEqual([name for name, _ in new_writes], ["second_clean"])
        self.assertTrue(all(rule in edited for rule in new_writes[0][1]["spec"]["rules"]))
        self.resources["second_clean"]["status"]["phase"] = "Ok"
        self.advance(SnapshotRunningStatus.RUNNING)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.join_data_rt, "11_legacy_logical")
        self.assertEqual(second.join_data_rt, "11_legacy_logical")
        self.assertEqual([name for name, _ in self.puts()].count("source"), 1)

    def test_basic_matching_clean_target_failure_is_not_hidden_by_a_new_latest_history(self):
        self.basic_collector()
        self.enable_basic()
        self.advance()
        self.ready("source")
        self.advance()
        self.resources["log_clean"]["status"].update(phase="Failed", history_id=22)
        self.advance(SnapshotRunningStatus.FAILED)
        self.assertEqual([name for name, _ in self.puts()], ["source", "log_clean"])

    def test_basic_unattributed_clean_failure_remains_observe_only_after_reentry(self):
        self.basic_collector()
        old = deepcopy(self.resources["log_clean"])
        self.enable_basic()
        self.advance()
        self.ready("source")
        self.advance()
        target = deepcopy(self.resources["log_clean"])
        for value, phase, history_id in ((old, "Failed", 10), (target, "Terminating", 11)):
            with self.subTest(phase=phase, history_id=history_id, spec=value["spec"]["config_revision"]):
                self.resources["log_clean"] = deepcopy(value)
                self.resources["log_clean"]["status"].update(phase=phase, history_id=history_id)
                self.advance()
                self.assertEqual([name for name, _ in self.puts()], ["source", "log_clean"])
        with mock.patch.object(snapshot_restore, "BKBASE_V4_MAX_POLLS", 1):
            self.advance(SnapshotRunningStatus.FAILED)
        self.enable_basic()
        self.advance()
        self.assertEqual([name for name, _ in self.puts()], ["source", "log_clean"])

    def test_basic_persists_source_observation_before_rejecting_changed_collector_identity(self):
        collector = self.basic_collector()
        self.enable_basic()
        self.advance()
        self.ready("source")
        CollectorConfig.objects.filter(pk=collector.pk).update(
            bk_data_id=82, bkbase_v4_resources={**collector.bkbase_v4_resources, "source_raw_data_id": 82}
        )
        self.resources["log_clean"]["spec"]["raw_data_id"] = 82
        self.advance(SnapshotRunningStatus.FAILED)
        self.assertEqual(self.operation()["writes"]["data_source"]["observed"], "running")
        self.assertEqual([name for name, _ in self.puts()], ["source"])

    def test_basic_completed_stop_and_enable_replays_source_again(self):
        self.basic_collector()
        self.enable_basic()
        self.advance()
        self.ready("source")
        self.advance()
        self.resources["log_clean"]["status"]["phase"] = "Ok"
        self.advance(SnapshotRunningStatus.RUNNING)
        self.enable(is_enabled=False, join_data_type="basic", storage_type=["redis"])
        self.resources["source"]["spec"]["current_status"] = "Stopped"
        self.resources["source"]["status"]["phase"] = "Ok"
        source.poll_source_operations()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.CLOSED)
        self.enable_basic()
        self.advance()
        source_writes = [payload["spec"] for name, payload in self.puts() if name == "source"]
        self.assertEqual(len(source_writes), 3)
        self.assertEqual(source_writes[1]["desired_status"], "Stopped")
        self.assertEqual(source_writes[2]["report_config"]["history_data"]["start_time"], "0")

    def test_restore_ignores_soft_deleted_snapshot_with_same_writer(self):
        Snapshot.objects.create(
            system_id=self.system.system_id,
            resource_type_id="deleted",
            is_deleted=True,
            bkbase_v4_resources={"clean": self.binding["clean"]},
        )
        self.assertEqual(self.enable()["status"], SnapshotRunningStatus.PREPARING)
        self.assertEqual(self.puts(), [])

    def test_basic_does_not_commit_link_after_collector_etl_input_changes(self):
        collector = self.basic_collector()
        self.enable_basic()
        self.advance()
        self.ready("source")
        self.advance()
        CollectorConfig.objects.filter(pk=collector.pk).update(etl_params={"changed": True})
        self.resources["log_clean"]["status"]["phase"] = "Ok"
        self.advance(SnapshotRunningStatus.FAILED)
        collector.refresh_from_db()
        self.assertIsNone(collector.join_data_rt)
        self.assertEqual([name for name, _ in self.puts()], ["source", "log_clean"])

    def test_basic_conflicting_join_target_stops_preflight_before_any_put(self):
        collector = self.basic_collector()
        select = self.resources["log_clean"]["spec"]["join"][0]["select"]
        select[0]["as"] = "snapshot_instance_data"
        with self.assertRaises(BKBaseResourceMappingError):
            self.enable_basic()
        collector.refresh_from_db()
        self.assertIsNone(collector.join_data_rt)
        self.assertEqual(self.puts(), [])

    def test_basic_requires_redis_join_before_any_put(self):
        self.basic_collector()
        self.resources["redis"]["spec"]["tableInfo"]["storage_type"] = "kv"
        with self.assertRaises(BKBaseResourceMappingError):
            self.enable_basic()
        self.assertEqual(self.puts(), [])

    def test_basic_accepts_default_redis_join_mode(self):
        self.basic_collector()
        self.resources["redis"]["spec"]["tableInfo"].pop("storage_type")
        self.assertEqual(self.enable_basic()["status"], SnapshotRunningStatus.PREPARING)
        self.assertEqual(self.puts(), [])

    def test_basic_does_not_commit_link_when_deletion_begins_during_confirmation(self):
        collector = self.basic_collector()
        self.enable_basic()
        self.advance()
        self.ready("source")
        self.advance()
        self.resources["log_clean"]["status"]["phase"] = "Ok"
        clean_gets = []

        def mark_pending_delete(name):
            if name != "log_clean":
                return
            clean_gets.append(name)
            if len(clean_gets) == 2:
                CollectorConfig.objects.filter(pk=collector.pk).update(
                    bkbase_v4_resources={**collector.bkbase_v4_resources, "pending_action": "delete"}
                )

        self.on_get = mark_pending_delete
        self.advance(SnapshotRunningStatus.FAILED)
        collector.refresh_from_db()
        self.assertIsNone(collector.join_data_rt)
        self.assertEqual(collector.bkbase_v4_resources["pending_action"], "delete")

    def test_storage_change_task_keeps_link_and_refs_saved_after_refresh(self):
        collector = self.basic_collector()
        CollectorConfig.objects.filter(pk=collector.pk).update(storage_changed=True)
        original_refresh = CollectorConfig.refresh_from_db
        new_binding = {**collector.bkbase_v4_resources, "retained": "new binding"}

        def refresh_then_restore(instance, *args, **kwargs):
            original_refresh(instance, *args, **kwargs)
            CollectorConfig.objects.filter(pk=instance.pk).update(
                join_data_rt="11_legacy_logical", bkbase_v4_resources=new_binding
            )

        with mock.patch.object(tasks.EtlClean, "get_instance", return_value=mock.Mock()), mock.patch.object(
            CollectorConfig, "refresh_from_db", autospec=True, side_effect=refresh_then_restore
        ):
            tasks.change_storage_cluster.run()
        collector.refresh_from_db()
        self.assertEqual(collector.join_data_rt, "11_legacy_logical")
        self.assertEqual(collector.bkbase_v4_resources, new_binding)
        self.assertFalse(collector.storage_changed)

    def test_v4_etl_cannot_overwrite_an_unconfirmed_basic_clean_write(self):
        collector = self.basic_collector()
        self.enable_basic()
        self.advance()
        self.ready("source")
        self.advance()
        with self.assertRaises(SnapshotPreparingException):
            self.configure_basic_collector_etl(collector)
        collector.refresh_from_db()
        self.assertIsNone(collector.join_data_rt)
        self.assertEqual([name for name, _ in self.puts()], ["source", "log_clean"])

    def test_v4_etl_reloads_link_under_clean_lock_and_keeps_redis_order(self):
        collector = self.basic_collector()
        logical_id = self.snapshot.bkbase_table_id
        deployed = JoinConfig(logical_id).config
        deployed["join_on"] = deployed["join_on"][1:] + deployed["join_on"][:1]
        acquire = RedisLock.acquire

        def restore_just_before_lock(lock, *args):
            CollectorConfig.objects.filter(pk=collector.pk).update(join_data_rt=logical_id)
            self.resources["log_clean"]["spec"]["join"] = [deepcopy(deployed)]
            return acquire(lock, *args)

        with mock.patch.object(RedisLock, "acquire", autospec=True, side_effect=restore_just_before_lock):
            self.configure_basic_collector_etl(collector)

        collector.refresh_from_db()
        self.assertEqual(collector.join_data_rt, logical_id)
        joins = self.puts()[-1][1]["spec"]["join"]
        self.assertEqual([join for join in joins if join["result_table_id"] == logical_id], [deployed])

    def test_basic_requires_trusted_collector_links(self):
        self.snapshot.join_data_type = "basic"
        self.snapshot.save(update_fields=["join_data_type"])
        collector = CollectorConfig.objects.create(
            system_id=self.system.system_id,
            bkbase_table_id="other_clean",
            collector_config_name_en="unlinked",
            bk_biz_id=1,
            collector_config_id=1,
            collector_plugin_id=1,
        )
        for link in (None, ""):
            with self.subTest(link=link):
                CollectorConfig.objects.filter(pk=collector.pk).update(join_data_rt=link)
                with self.assertRaises(BKBaseResourceMappingError):
                    self.enable(join_data_type="basic")
        CollectorConfig.objects.filter(pk=collector.pk).update(
            bkbase_table_id=None, bkbase_v4_resources={"clean": self.ref("Clean", "other_clean")}, join_data_rt=None
        )
        with self.assertRaises(BKBaseResourceMappingError):
            self.enable(join_data_type="basic")
        self.assertEqual(self.puts(), [])
        self.pre_check.assert_not_called()
        CollectorConfig.objects.filter(pk=collector.pk).update(join_data_rt=self.snapshot.bkbase_table_id)
        self.downstream_running()
        self.enable(join_data_type="basic")
        self.advance()
        self.ready("source")
        self.advance(SnapshotRunningStatus.RUNNING)

    def test_invalid_preparing_snapshot_does_not_break_restoration_batch(self):
        bad = Snapshot.objects.create(
            system_id=self.system.system_id,
            resource_type_id="bad",
            status=SnapshotRunningStatus.PREPARING,
            bkbase_v4_resources=["invalid"],
        )
        self.enable()
        self.advance()
        bad.refresh_from_db()
        self.assertEqual(bad.status, SnapshotRunningStatus.FAILED)
        self.assertEqual([key for key, _ in self.puts()], ["clean"])

    def test_restore_accepts_server_rewritten_source_updater(self):
        self.downstream_running()
        self.resources["source"]["spec"]["updated_by"] = "initial_operator"
        self.enable()
        self.on_put = lambda: self.resources["source"]["spec"].update(updated_by="restore_operator")
        self.advance()
        self.ready("source")
        self.advance(SnapshotRunningStatus.RUNNING)

    def test_restore_still_detects_changed_nested_source_field(self):
        self.downstream_running()
        self.resources["source"]["spec"]["report_config"]["updated_by"] = "business_value"
        self.enable()
        self.advance()
        self.ready("source")
        self.resources["source"]["spec"]["report_config"]["updated_by"] = "changed_value"
        self.advance(SnapshotRunningStatus.FAILED)

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_toggle_and_task_retain_legacy_storage_start(self):
        self.assertEqual(self.enable()["status"], SnapshotRunningStatus.PREPARING)
        with mock.patch.object(tasks.AssetHandler, "start", return_value=True) as start:
            self.advance(SnapshotRunningStatus.RUNNING)
        self.assertEqual(start.call_args_list, [mock.call(multiple_storage=True)] * 2)
        self.assertEqual(self.requests, [])

    def test_same_running_source_configuration_still_submits_replay_once(self):
        self.downstream_running()
        self.ready("source")
        self.resources["source"]["spec"]["report_config"]["history_data"]["start_time"] = "0"
        self.enable()
        baseline_status = deepcopy(self.resources["source"]["status"])
        self.advance()
        self.assertEqual([key for key, _ in self.puts()], ["source"])
        updated_status = self.resources["source"]["status"]
        self.resources["source"]["status"] = baseline_status
        self.advance()
        self.resources["source"]["status"] = updated_status
        self.ready("source")
        self.advance(SnapshotRunningStatus.RUNNING)
        self.assertEqual(len(self.puts()), 1)

    def test_unknown_same_configuration_replay_is_not_inferred_from_old_running_source(self):
        self.downstream_running()
        self.ready("source")
        self.resources["source"]["spec"]["report_config"]["history_data"]["start_time"] = "0"
        self.timeout = "source"
        self.enable()
        self.advance()
        self.advance()
        self.assertEqual([key for key, _ in self.puts()], ["source"])
        self.assertTrue(self.operation()["outcome_unknown"])

    def test_independent_clean_consumer_of_same_data_id_does_not_block_restore(self):
        Snapshot.objects.create(
            system_id="read_only_system",
            resource_type_id="downstream",
            bkbase_data_id=self.snapshot.bkbase_data_id,
            bkbase_v4_resources={"data_id": self.binding["data_id"], "clean": self.ref("Clean", "different")},
        )
        self.downstream_running()
        self.enable()
        self.advance()
        self.assertEqual([key for key, _ in self.puts()], ["source"])

    def test_explicit_retry_preserves_accepted_but_unconfirmed_replay(self):
        self.downstream_running()
        self.ready("source")
        self.resources["source"]["spec"]["report_config"]["history_data"]["start_time"] = "0"
        self.enable()
        self.advance()
        with mock.patch.object(snapshot_restore, "BKBASE_V4_MAX_POLLS", 1):
            self.advance(SnapshotRunningStatus.FAILED)
        self.assertFalse(self.operation()["outcome_unknown"])
        self.enable()
        self.ready("source")
        self.advance(SnapshotRunningStatus.RUNNING)
        self.assertEqual([key for key, _ in self.puts()], ["source"])

    def test_new_v4_asset_restore_without_legacy_pid_preserves_existing_resources(self):
        self.snapshot.bkbase_processing_id = None
        self.snapshot.save(update_fields=["bkbase_processing_id"])
        self.resources["clean"]["metadata"]["labels"] = {}
        self.downstream_running()
        original_clean = deepcopy(self.resources["clean"])
        self.assertEqual(self.enable()["status"], SnapshotRunningStatus.PREPARING)
        self.assertEqual(self.puts(), [])
        self.advance()
        self.assertEqual([name for name, _ in self.puts()], ["source"])
        self.ready("source")
        self.advance(SnapshotRunningStatus.RUNNING)
        self.advance(SnapshotRunningStatus.RUNNING)
        self.assertEqual([name for name, _ in self.puts()], ["source"])
        self.assertEqual(self.resources["clean"], original_clean)
        self.assertIsNone(self.snapshot.bkbase_processing_id)

    def test_new_v4_basic_replay_with_empty_legacy_pid_writes_only_source_once(self):
        self.basic_collector()
        self.snapshot.bkbase_processing_id = ""
        self.snapshot.status = SnapshotRunningStatus.RUNNING
        self.snapshot.save(update_fields=["bkbase_processing_id", "status"])
        self.snapshot.storages.update(status=SnapshotRunningStatus.RUNNING)
        self.resources["clean"]["metadata"]["labels"] = {}
        self.ready("source")
        resource_type = ResourceType.objects.get(system_id=self.system.system_id, resource_type_id="asset")
        handler = HttpPullHandler(self.system, resource_type, self.snapshot, "basic")
        self.assertTrue(source.prepare_snapshot_replay(self.snapshot, handler.config))
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)
        self.assertEqual(self.puts(), [])
        self.advance()
        self.assertEqual([name for name, _ in self.puts()], ["source"])
        self.ready("source")
        self.advance(SnapshotRunningStatus.RUNNING)
        self.advance(SnapshotRunningStatus.RUNNING)
        self.assertEqual([name for name, _ in self.puts()], ["source"])
        self.assertEqual(self.snapshot.bkbase_processing_id, "")

    def test_new_v4_basic_restore_without_legacy_pid_still_confirms_collector_join(self):
        collector = self.basic_collector()
        self.snapshot.bkbase_processing_id = None
        self.snapshot.save(update_fields=["bkbase_processing_id"])
        self.resources["clean"]["metadata"]["labels"] = {}
        self.assertEqual(self.enable_basic()["status"], SnapshotRunningStatus.PREPARING)
        self.assertEqual(self.puts(), [])
        self.advance()
        self.ready("source")
        self.advance()
        self.assertEqual([name for name, _ in self.puts()], ["source", "log_clean"])
        collector.refresh_from_db()
        self.assertIsNone(collector.join_data_rt)
        self.ready("log_clean")
        self.advance(SnapshotRunningStatus.RUNNING)
        collector.refresh_from_db()
        self.assertEqual(collector.join_data_rt, "11_legacy_logical")
        self.assertIsNone(self.snapshot.bkbase_processing_id)
        self.assertEqual([name for name, _ in self.puts()], ["source", "log_clean"])

    def test_new_v4_restore_conflicting_clean_identity_labels_refuse_without_writes(self):
        self.snapshot.bkbase_processing_id = None
        self.snapshot.save(update_fields=["bkbase_processing_id"])
        original = Snapshot.objects.values().get(pk=self.snapshot.pk)
        for labels in ({"raw_data_id": "72"}, {"result_table_id": "other_rt"}, {"raw_data_id": 71}):
            with self.subTest(labels=labels):
                self.resources["clean"]["metadata"]["labels"] = labels
                with self.assertRaises(BKBaseResourceMappingError):
                    self.enable()
                self.assertEqual(self.puts(), [])
                self.assertEqual(Snapshot.objects.values().get(pk=self.snapshot.pk), original)

    def test_restore_known_legacy_pid_requires_matching_label_before_any_write(self):
        original = Snapshot.objects.values().get(pk=self.snapshot.pk)
        for labels in ({}, {"processing_id": "other"}):
            with self.subTest(labels=labels):
                self.resources["clean"]["metadata"]["labels"] = labels
                with self.assertRaises(BKBaseResourceMappingError):
                    self.enable()
                self.assertEqual(self.puts(), [])
                self.assertEqual(Snapshot.objects.values().get(pk=self.snapshot.pk), original)

    def test_new_v4_restore_pending_clean_create_refuses_without_claim_or_write(self):
        self.snapshot.bkbase_processing_id = None
        self.snapshot.bkbase_v4_resources["clean_pending_create"] = True
        self.snapshot.save(update_fields=["bkbase_processing_id", "bkbase_v4_resources"])
        self.resources["clean"]["metadata"]["labels"] = {}
        original = Snapshot.objects.values().get(pk=self.snapshot.pk)
        with self.assertRaises(BKBaseResourceMappingError):
            self.enable()
        self.assertEqual(self.puts(), [])
        self.assertEqual(Snapshot.objects.values().get(pk=self.snapshot.pk), original)

    def test_new_v4_basic_replay_unknown_write_reentry_never_resends(self):
        self.basic_collector()
        self.snapshot.bkbase_processing_id = None
        self.snapshot.status = SnapshotRunningStatus.RUNNING
        self.snapshot.save(update_fields=["bkbase_processing_id", "status"])
        self.snapshot.storages.update(status=SnapshotRunningStatus.RUNNING)
        self.resources["clean"]["metadata"]["labels"] = {}
        self.ready("source")
        resource_type = ResourceType.objects.get(system_id=self.system.system_id, resource_type_id="asset")
        handler = HttpPullHandler(self.system, resource_type, self.snapshot, "basic")
        self.assertTrue(source.prepare_snapshot_replay(self.snapshot, handler.config))
        self.timeout = "source"
        self.advance()
        operation_id = self.operation()["operation_id"]
        self.assertTrue(self.operation()["outcome_unknown"])
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertFalse(source.prepare_snapshot_replay(self.snapshot, handler.config))
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertEqual([name for name, _ in self.puts()], ["source"])
        self.assertEqual(self.operation()["operation_id"], operation_id)
        self.assertTrue(self.operation()["outcome_unknown"])
        self.assertIsNone(self.operation()["accepted"])
        self.assertIsNone(self.operation()["data_completed"])
        self.assertIsNone(self.snapshot.bkbase_processing_id)

    def test_new_v4_basic_replay_target_drift_refuses_without_write_or_fallback(self):
        self.basic_collector()
        self.snapshot.bkbase_processing_id = None
        self.snapshot.status = SnapshotRunningStatus.RUNNING
        self.snapshot.save(update_fields=["bkbase_processing_id", "status"])
        self.snapshot.storages.update(status=SnapshotRunningStatus.RUNNING)
        self.resources["clean"]["metadata"]["labels"] = {}
        self.ready("source")
        resource_type = ResourceType.objects.get(system_id=self.system.system_id, resource_type_id="asset")
        handler = HttpPullHandler(self.system, resource_type, self.snapshot, "basic")
        self.assertTrue(source.prepare_snapshot_replay(self.snapshot, handler.config))
        self.resources["redis"]["spec"]["tableInfo"]["expire"] = 99
        self.advance(SnapshotRunningStatus.FAILED)
        self.assertEqual(self.puts(), [])
        self.assertIsNone(self.snapshot.bkbase_processing_id)
        self.assertFalse(self.operation()["active"])
        self.assertEqual(self.snapshot.bkbase_v4_resources["clean"], self.binding["clean"])

    def test_new_v4_restore_unknown_write_explicit_reentry_only_observes(self):
        self.snapshot.bkbase_processing_id = None
        self.snapshot.save(update_fields=["bkbase_processing_id"])
        self.resources["clean"]["metadata"]["labels"] = {}
        self.downstream_running()
        self.enable()
        self.timeout = "source"
        self.advance()
        self.assertTrue(self.operation()["outcome_unknown"])
        with mock.patch.object(snapshot_restore, "BKBASE_V4_MAX_POLLS", 1):
            self.advance(SnapshotRunningStatus.FAILED)
        self.assertTrue(self.operation()["outcome_unknown"])
        self.enable()
        self.advance()
        self.assertEqual([name for name, _ in self.puts()], ["source"])
        self.assertTrue(self.operation()["outcome_unknown"])
        self.assertIsNone(self.snapshot.bkbase_processing_id)

    def test_new_v4_restore_target_drift_refuses_without_write_or_fallback(self):
        self.snapshot.bkbase_processing_id = None
        self.snapshot.save(update_fields=["bkbase_processing_id"])
        self.resources["clean"]["metadata"]["labels"] = {}
        self.enable()
        self.resources["doris"]["spec"]["tableInfo"]["expire"] = 99
        self.advance(SnapshotRunningStatus.FAILED)
        self.assertEqual(self.puts(), [])
        self.assertIsNone(self.snapshot.bkbase_processing_id)
        self.assertFalse(self.operation()["active"])
        self.assertEqual(self.snapshot.bkbase_v4_resources["clean"], self.binding["clean"])
