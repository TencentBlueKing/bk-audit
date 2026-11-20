"""通过周期任务和真实SDK验证已有Asset快照纯重放。

配置、绑定及任务意图使用隔离测试库；外部HTTP与资源锁受控。
不创建平台资源，不把源任务Running当成重放数据补完。
"""
import datetime
import json
from copy import deepcopy
from unittest import mock

import requests
from django.db import connection
from django.test import TestCase, override_settings
from django.utils import timezone

from api.bk_base_v4.default import BkBaseV4Resource
from apps.meta.models import ResourceType, System
from services.web.bkbase import source
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus import tasks
from services.web.databus.collector.resources import ToggleJoinDataResource
from services.web.databus.collector.snapshot.join.http_pull import HttpPullHandler
from services.web.databus.constants import JoinDataType, SnapshotRunningStatus
from services.web.databus.models import Snapshot, SnapshotStorage


@override_settings(
    BKBASE_API_VERSION="v4",
    BKBASE_V4_TENANT="tenant_a",
    BKBASE_V4_NAMESPACE="audit",
    HTTP_PULL_REDIS_TIMEOUT="10d",
    HIGH_RISK_PORTS=[],
)
class SnapshotReplayTests(TestCase):
    def setUp(self):
        self.system = System.objects.create(
            system_id="synthetic_system", namespace="audit", callback_url="https://source.test", auth_token="synthetic"
        )
        self.resource_type = ResourceType.objects.create(
            system_id=self.system.system_id,
            resource_type_id="asset",
            unique_id="synthetic_system:asset",
            name="asset",
            path="/resources",
        )
        self.binding = {
            "data_source": self.ref("DataSource", "source_a"),
            "data_id": self.ref("DataId", "data_a"),
            "clean": self.ref("Clean", "clean_a"),
            "clean_role": "owner",
            "result_table_id": "1_logical",
            "result_table": self.ref("ResultTable", "actual_rt"),
            "storages": {"hdfs": self.ref("DataStorage", "hdfs_task"), "doris": self.ref("DataStorage", "doris_task")},
            "retained": {"value": 1},
        }
        self.snapshot = Snapshot.objects.create(
            system_id=self.system.system_id,
            resource_type_id="asset",
            join_data_type=JoinDataType.ASSET,
            status=SnapshotRunningStatus.RUNNING,
            bkbase_data_id=11,
            bkbase_processing_id="legacy_clean",
            bkbase_table_id="legacy_rt",
            bkbase_v4_resources=deepcopy(self.binding),
        )
        for kind in ("hdfs", "doris"):
            SnapshotStorage.objects.create(
                snapshot=self.snapshot, storage_type=kind, status=SnapshotRunningStatus.RUNNING
            )
        params = self.handler().config
        scope = params["access_conf_info"]["resource"]["scope"][0]
        report = {
            "type": "rest_api",
            "http_mode": "PULL",
            "data_conn_name": "connection_a",
            "method": "post",
            "path": "/resources",
            "body": scope["body"]["content"],
            "period": 1,
            "period_unit": "minute",
            "increment_field": {"type": "time", "time_format": "Unix Time Stamp(milliseconds)"},
            "pagination": {"start_offset": 0, "limit": 1000, "total_path": "data.count"},
            "data_path": None,
            "retained": "keep",
        }
        report["pagination"]["limit"] = scope["body"]["page"]["limit"]
        self.resources = {
            "source_a": self.remote(
                "DataSource",
                "source_a",
                {
                    "data_id": self.binding["data_id"],
                    "data_conn": self.ref("DataConn", "connection_a"),
                    "report_config": report,
                    "desired_status": "Running",
                    "current_status": "Running",
                    "basic_info": {"data_source_name": "source_a"},
                    "preserve": {"value": 1},
                },
            ),
            "connection_a": self.remote(
                "DataConn",
                "connection_a",
                {"conn_info": {"type": "rest_api", "url": "https://source.test", "headers": scope["headers"]}},
            ),
            "clean_a": self.remote(
                "Clean",
                "clean_a",
                {
                    "data_id": self.binding["data_id"],
                    "raw_data_id": 11,
                    "result_table_id": "1_logical",
                    "result_table_source": "new",
                    "current_status": "Running",
                    "rules": [],
                },
            ),
        }
        self.resources["source_a"]["metadata"]["labels"] = {"raw_data_id": "11"}
        for key, kind in (("hdfs_task", "Hdfs"), ("doris_task", "Doris")):
            self.resources[key] = self.remote(
                "DataStorage",
                key,
                {"tableInfo": {"source": self.binding["result_table"], "storage": self.ref(kind, key + "_cluster")}},
            )
            self.resources[key]["status"]["message"] = "running"
        self.requests = []
        self.put_timeout = False
        self.put_hook = None
        self.read_hook = None
        self.read_timeout = False
        self.atomic_depth = len(connection.atomic_blocks)
        self.enterContext(mock.patch("requests.sessions.Session.request", side_effect=self.transport))
        self.enterContext(mock.patch.object(BkBaseV4Resource, "build_header", return_value={}))
        self.enterContext(mock.patch.object(source, "resource_lock"))
        self.enterContext(mock.patch("core.lock.CacheLock.locked", new_callable=mock.PropertyMock, return_value=False))
        self.enterContext(mock.patch("core.lock.CacheLock.release", return_value=True))
        self.enterContext(
            mock.patch.object(tasks.BasicJoinHandler, "start", side_effect=AssertionError("V3 Basic path"))
        )
        self.enterContext(mock.patch.object(tasks.AssetHandler, "start", side_effect=AssertionError("V3 Asset path")))

    def ref(self, kind, name):
        return {"kind": kind, "tenant": "tenant_a", "namespace": "audit", "name": name}

    def remote(self, kind, name, spec):
        return {
            "kind": kind,
            "metadata": {"tenant": "tenant_a", "namespace": "audit", "name": name, "annotations": {"keep": "value"}},
            "spec": spec,
            "status": {"phase": "Ok"},
        }

    def handler(self):
        self.snapshot.refresh_from_db()
        return HttpPullHandler(self.system, self.resource_type, self.snapshot, JoinDataType.ASSET)

    def transport(self, method, url, **kwargs):
        self.assertEqual(len(connection.atomic_blocks), self.atomic_depth, "HTTP inside an additional DB transaction")
        name = url.rstrip("/").rsplit("/", 1)[-1]
        self.assertIn(name, self.resources, "unexpected resource or V3 request")
        self.assertIn("/v4/tenants/tenant_a/", url)
        if method.upper() == "GET":
            self.assertFalse({"tenant", "namespace", "name"}.intersection(kwargs.get("params", {})))
        self.requests.append((method, url, deepcopy(kwargs.get("json"))))
        if method.upper() == "GET":
            if self.read_hook:
                hook, self.read_hook = self.read_hook, None
                hook()
            if self.read_timeout:
                raise requests.Timeout("synthetic read timeout")
        if method.upper() == "PUT":
            self.assertEqual(name, "source_a", "only the source may be written")
            if self.put_hook:
                self.put_hook()
            if self.put_timeout:
                raise requests.Timeout("synthetic lost response")
            self.resources[name]["metadata"] = deepcopy(kwargs["json"]["metadata"])
            self.resources[name]["spec"] = deepcopy(kwargs["json"]["spec"])
            value = deepcopy(self.resources[name])
            value["status"]["phase"] = "Pending"
        else:
            self.assertEqual(method.upper(), "GET")
            value = deepcopy(self.resources[name])
        response = requests.Response()
        response.status_code = 200
        response.url = url
        response.request = requests.Request(method, url).prepare()
        response._content = json.dumps({"result": True, "code": "00", "data": value}).encode()
        return response

    def schedule(self):
        Snapshot.objects.filter(pk=self.snapshot.pk).update(updated_at=timezone.now() - datetime.timedelta(days=20))
        tasks.refresh_snapshot.run()
        self.snapshot.refresh_from_db()

    def puts(self):
        return [item for item in self.requests if item[0].upper() == "PUT"]

    def assert_replay_failed(self):
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.FAILED)
        self.assertFalse(self.snapshot.bkbase_v4_resources["source_replay"]["active"])
        self.assertTrue(self.snapshot.status_msg)

    def test_periodic_refresh_reaches_sdk_once_for_multiple_storages(self):
        old = deepcopy(self.resources["source_a"])
        self.schedule()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)
        self.assertIn("source_replay", self.snapshot.bkbase_v4_resources)
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertEqual(len(self.puts()), 1)
        payload = self.puts()[0][2]
        expected = deepcopy(old)
        expected["spec"]["report_config"]["history_data"] = {"start_time": "0"}
        self.assertEqual(payload, {"metadata": expected["metadata"], "spec": expected["spec"], "status": None})
        operation = self.snapshot.bkbase_v4_resources["source_replay"]
        self.assertIs(operation["accepted"], True)
        self.assertIsNone(operation["data_completed"])
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.RUNNING)
        self.assertEqual(len(self.puts()), 1)
        self.assertEqual(self.snapshot.bkbase_data_id, 11)
        self.assertEqual(self.snapshot.bkbase_processing_id, "legacy_clean")
        self.assertEqual(self.snapshot.bkbase_table_id, "legacy_rt")
        self.assertEqual(self.snapshot.bkbase_v4_resources["storages"], self.binding["storages"])
        self.assertEqual(self.snapshot.bkbase_v4_resources["retained"], {"value": 1})
        operation_id = operation["operation_id"]
        tasks.refresh_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.bkbase_v4_resources["source_replay"]["operation_id"], operation_id)
        self.assertEqual(len(self.puts()), 1)

    def test_lost_response_is_unknown_and_never_blindly_retried(self):
        self.schedule()
        self.put_timeout = True
        tasks.start_snapshot.run()
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        operation = self.snapshot.bkbase_v4_resources["source_replay"]
        self.assertIsNone(operation["accepted"])
        self.assertTrue(operation["outcome_unknown"])
        self.assertIsNone(operation["data_completed"])
        self.assertEqual(len(self.puts()), 1)
        self.schedule()
        tasks.start_snapshot.run()
        self.assertEqual(len(self.puts()), 1)

    def test_downstream_drift_after_queue_is_rejected_before_source_write(self):
        self.schedule()
        self.resources["hdfs_task"]["spec"]["tableInfo"]["expire"] = 99
        tasks.start_snapshot.run()
        self.assertEqual(self.puts(), [])
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.FAILED)

    def test_missing_or_changed_binding_and_basic_are_not_scheduled(self):
        for patch in (
            {"data_source": None},
            {"data_source": [self.binding["data_source"]]},
            {"data_source": self.ref("Clean", "source_a")},
            {"data_source": {**self.binding["data_source"], "tenant": "other"}},
            {"data_id": self.ref("DataId", "other")},
        ):
            with self.subTest(patch=patch):
                self.snapshot.bkbase_v4_resources = {**deepcopy(self.binding), **patch}
                self.snapshot.status = SnapshotRunningStatus.RUNNING
                self.snapshot.save()
                self.schedule()
                self.assertNotIn("source_replay", self.snapshot.bkbase_v4_resources)
        self.snapshot.bkbase_v4_resources = deepcopy(self.binding)
        self.snapshot.join_data_type = JoinDataType.BASIC
        self.snapshot.save()
        self.schedule()
        self.assertNotIn("source_replay", self.snapshot.bkbase_v4_resources)
        self.assertEqual(self.puts(), [])

    def test_binding_raw_id_cannot_override_snapshot_identity(self):
        self.snapshot.bkbase_v4_resources["raw_data_id"] = 22
        self.snapshot.save(update_fields=["bkbase_v4_resources"])
        before = deepcopy(self.snapshot.bkbase_v4_resources)
        self.resources["source_a"]["metadata"]["labels"]["raw_data_id"] = "22"
        self.resources["clean_a"]["spec"]["raw_data_id"] = 22
        self.schedule()
        self.assertNotIn("source_replay", self.snapshot.bkbase_v4_resources)
        self.assertEqual(self.snapshot.bkbase_data_id, 11)
        self.assertEqual(self.snapshot.bkbase_v4_resources, before)
        self.assertEqual(self.puts(), [])

    def test_decimal_raw_id_text_is_compared_without_rewriting_binding(self):
        self.snapshot.bkbase_v4_resources["raw_data_id"] = "11"
        self.snapshot.save(update_fields=["bkbase_v4_resources"])
        self.resources["clean_a"]["spec"]["raw_data_id"] = "11"
        self.schedule()
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertEqual(len(self.puts()), 1)
        self.assertEqual(self.snapshot.bkbase_data_id, 11)
        self.assertEqual(self.snapshot.bkbase_v4_resources["raw_data_id"], "11")

    def test_new_storage_after_queue_is_rejected_before_write(self):
        self.schedule()
        SnapshotStorage.objects.create(
            snapshot=self.snapshot, storage_type="redis", status=SnapshotRunningStatus.RUNNING
        )
        tasks.start_snapshot.run()
        self.assertEqual(self.puts(), [])
        self.assert_replay_failed()
        self.assertTrue(self.snapshot.storages.filter(storage_type="redis").exists())

    def test_old_generation_cannot_overwrite_new_intent(self):
        self.schedule()

        def replace_intent():
            current = Snapshot.objects.get(pk=self.snapshot.pk)
            current.bkbase_v4_resources["source_replay"]["operation_id"] = "new_generation"
            current.bkbase_v4_resources["source_replay"]["accepted"] = None
            current.save(update_fields=["bkbase_v4_resources"])

        self.put_hook = replace_intent
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.bkbase_v4_resources["source_replay"]["operation_id"], "new_generation")
        self.assertIsNone(self.snapshot.bkbase_v4_resources["source_replay"]["accepted"])

    def test_endpoint_edit_during_preflight_fences_old_request(self):
        self.schedule()
        self.read_hook = lambda: System.objects.filter(pk=self.system.pk).update(callback_url="https://changed.test")
        tasks.start_snapshot.run()
        self.assertEqual(self.puts(), [])
        self.assert_replay_failed()
        self.assertEqual(System.objects.get(pk=self.system.pk).callback_url, "https://changed.test")

    def test_pull_config_drift_ends_same_operation_and_keeps_new_configuration(self):
        self.schedule()
        operation_id = self.snapshot.bkbase_v4_resources["source_replay"]["operation_id"]
        Snapshot.objects.filter(pk=self.snapshot.pk).update(pull_config={"period": 2}, custom_config={"latest": True})
        tasks.start_snapshot.run()
        self.assert_replay_failed()
        self.assertEqual(self.snapshot.bkbase_v4_resources["source_replay"]["operation_id"], operation_id)
        self.assertEqual(self.snapshot.pull_config, {"period": 2})
        self.assertEqual(self.snapshot.custom_config, {"latest": True})
        self.assertEqual(self.snapshot.bkbase_v4_resources["retained"], {"value": 1})
        self.assertEqual(self.puts(), [])

    def test_input_drift_after_unknown_write_preserves_unknown_outcome(self):
        self.schedule()
        self.put_timeout = True
        tasks.start_snapshot.run()
        Snapshot.objects.filter(pk=self.snapshot.pk).update(pull_config={"period": 2})
        tasks.start_snapshot.run()
        self.assert_replay_failed()
        operation = self.snapshot.bkbase_v4_resources["source_replay"]
        self.assertTrue(operation["attempted"])
        self.assertTrue(operation["outcome_unknown"])
        self.assertIsNone(operation["accepted"])
        self.assertIsNone(operation["data_completed"])
        self.assertEqual(len(self.puts()), 1)

    def test_missing_runtime_context_ends_current_replay_without_write(self):
        self.schedule()
        with override_settings(BKBASE_V4_TENANT=""):
            tasks.start_snapshot.run()
        self.assert_replay_failed()
        self.assertEqual(self.puts(), [])

    def test_invalid_local_endpoint_ends_current_replay_without_write(self):
        self.schedule()
        System.objects.filter(pk=self.system.pk).update(callback_url="ftp://changed.test")
        tasks.start_snapshot.run()
        self.assert_replay_failed()
        self.assertEqual(self.puts(), [])

    def test_missing_resource_type_ends_current_replay_without_write(self):
        self.schedule()
        ResourceType.objects.filter(pk=self.resource_type.pk).update(resource_type_id="removed_asset")
        tasks.start_snapshot.run()
        self.assert_replay_failed()
        self.assertEqual(self.puts(), [])

    def test_invalid_runtime_configuration_ends_current_replay_without_write(self):
        self.schedule()
        with override_settings(BKBASE_V4_RESULT_TABLE_NAMESPACES="{"):
            tasks.start_snapshot.run()
        self.assert_replay_failed()
        self.assertEqual(self.puts(), [])

    def test_cancellation_does_not_override_closed_state(self):
        self.schedule()
        operation_id = self.snapshot.bkbase_v4_resources["source_replay"]["operation_id"]
        Snapshot.objects.filter(pk=self.snapshot.pk).update(
            status=SnapshotRunningStatus.CLOSED, status_msg="stop owns state"
        )
        self.assertFalse(
            source.fail_snapshot_replay(self.snapshot, operation_id=operation_id, message="old cancellation")
        )
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.CLOSED)
        self.assertEqual(self.snapshot.status_msg, "stop owns state")

    def test_new_generation_during_preflight_prevents_old_write(self):
        self.schedule()

        def replace_intent():
            current = Snapshot.objects.get(pk=self.snapshot.pk)
            current.bkbase_v4_resources["source_replay"]["operation_id"] = "new_generation"
            current.save(update_fields=["bkbase_v4_resources"])

        self.read_hook = replace_intent
        tasks.start_snapshot.run()
        self.assertEqual(self.puts(), [])

    def test_read_failures_have_bounded_observation_without_put(self):
        self.schedule()
        self.read_timeout = True
        with mock.patch.object(source, "BKBASE_V4_MAX_POLLS", 2):
            tasks.start_snapshot.run()
            tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.FAILED)
        self.assertEqual(self.puts(), [])

    def test_pending_then_failed_source_is_not_reported_running(self):
        self.schedule()
        tasks.start_snapshot.run()
        self.resources["source_a"]["status"]["phase"] = "Pending"
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)
        self.resources["source_a"]["status"]["phase"] = "Failed"
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.FAILED)
        self.assertEqual(len(self.puts()), 1)
        self.assertIsNone(self.snapshot.bkbase_v4_resources["source_replay"]["data_completed"])

    def test_history_update_preserves_other_nested_options(self):
        self.resources["source_a"]["spec"]["report_config"]["history_data"] = {"start_time": "1", "retained": "keep"}
        self.schedule()
        tasks.start_snapshot.run()
        self.assertEqual(
            self.puts()[0][2]["spec"]["report_config"]["history_data"], {"start_time": "0", "retained": "keep"}
        )

    def test_connection_reference_and_headers_are_checked_before_queue(self):
        original = deepcopy(self.resources)
        for change in ("missing_namespace", "changed_headers"):
            with self.subTest(change=change):
                self.resources = deepcopy(original)
                if change == "missing_namespace":
                    self.resources["source_a"]["spec"]["data_conn"].pop("namespace")
                else:
                    self.resources["connection_a"]["spec"]["conn_info"]["headers"]["Authorization"] = "changed"
                self.schedule()
                self.assertNotIn("source_replay", self.snapshot.bkbase_v4_resources)
                self.assertEqual(self.puts(), [])

    def encrypted_connection(self):
        """模拟正式 GET 返回的加密标记和值，不使用真实凭据。"""
        connection = self.resources["connection_a"]
        connection["metadata"]["annotations"] = {"conn_info_encrypted": "true"}
        connection["spec"]["conn_info"]["headers"]["Authorization"] = "synthetic-ciphertext"
        return connection

    def test_pure_replay_preflight_preserves_formally_encrypted_connection(self):
        original = deepcopy(self.encrypted_connection())
        _, desired, _, changed_connection, observed_connection = source._replay_preflight(
            self.snapshot, self.handler().config, source.get_bkbase_context()
        )
        self.assertIsNone(changed_connection)
        self.assertEqual(observed_connection, original)
        self.assertEqual(desired["spec"]["report_config"]["history_data"]["start_time"], "0")
        self.assertEqual(self.puts(), [])

    def test_periodic_replay_with_encrypted_auth_only_writes_existing_source(self):
        original = deepcopy(self.encrypted_connection())
        self.schedule()
        self.assertIn("source_replay", self.snapshot.bkbase_v4_resources)
        tasks.start_snapshot.run()
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.RUNNING)
        [(method, url, payload)] = self.puts()
        self.assertEqual(method, "PUT")
        self.assertTrue(url.endswith("/datasources/source_a/"))
        self.assertEqual(payload["spec"]["report_config"]["history_data"]["start_time"], "0")
        self.assertEqual(self.resources["connection_a"], original)

    def test_encrypted_replay_still_requires_marker_value_and_matching_request(self):
        baseline = deepcopy(self.encrypted_connection())
        original_report = deepcopy(self.resources["source_a"]["spec"]["report_config"])
        for change in ("no_marker", "boolean_marker", "empty", "null", "header", "endpoint", "path"):
            with self.subTest(change=change):
                self.resources["connection_a"] = deepcopy(baseline)
                self.resources["source_a"]["spec"]["report_config"] = deepcopy(original_report)
                connection = self.resources["connection_a"]
                if change == "no_marker":
                    connection["metadata"]["annotations"].pop("conn_info_encrypted")
                elif change == "boolean_marker":
                    connection["metadata"]["annotations"]["conn_info_encrypted"] = True
                elif change in ("empty", "null"):
                    connection["spec"]["conn_info"]["headers"]["Authorization"] = "" if change == "empty" else None
                elif change == "header":
                    connection["spec"]["conn_info"]["headers"]["Content-type"] = "text/plain"
                elif change == "endpoint":
                    connection["spec"]["conn_info"]["url"] = "https://other.test"
                else:
                    self.resources["source_a"]["spec"]["report_config"]["path"] = "/other"
                with self.assertRaises(BKBaseResourceMappingError):
                    source._replay_preflight(self.snapshot, self.handler().config, source.get_bkbase_context())
        self.assertEqual(self.puts(), [])

    def test_encrypted_replay_does_not_bypass_formal_resource_identity(self):
        self.encrypted_connection()
        original = deepcopy(self.resources)
        for change in ("source_tenant", "clean_data_id", "logical_table"):
            with self.subTest(change=change):
                self.resources = deepcopy(original)
                if change == "source_tenant":
                    self.resources["source_a"]["metadata"]["tenant"] = "other_tenant"
                elif change == "clean_data_id":
                    self.resources["clean_a"]["spec"]["data_id"]["name"] = "other_data"
                else:
                    self.resources["clean_a"]["spec"]["result_table_id"] = "1_other"
                with self.assertRaises(BKBaseResourceMappingError):
                    source._replay_preflight(self.snapshot, self.handler().config, source.get_bkbase_context())
        self.assertEqual(self.puts(), [])

    def test_configure_changed_connection_cannot_use_encrypted_auth_preservation(self):
        self.encrypted_connection()

        def change_connection(snapshot, params, context, current, connection, conn_ref):
            desired_connection = deepcopy(connection)
            desired_connection["spec"]["conn_info"]["headers"]["Authorization"] = "different-ciphertext"
            return current, desired_connection

        with mock.patch.object(source, "_configure_replay_pull", side_effect=change_connection):
            with self.assertRaises(BKBaseResourceMappingError):
                source._replay_preflight(
                    self.snapshot, self.handler().config, source.get_bkbase_context(), configure=True
                )
        self.assertEqual(self.puts(), [])

    def test_encrypted_replay_unknown_receipt_only_observes_and_never_resends(self):
        original = deepcopy(self.encrypted_connection())
        self.schedule()
        self.assertIn("source_replay", self.snapshot.bkbase_v4_resources)
        self.put_timeout = True
        tasks.start_snapshot.run()
        tasks.start_snapshot.run()
        self.schedule()
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        operation = self.snapshot.bkbase_v4_resources["source_replay"]
        self.assertIsNone(operation["accepted"])
        self.assertTrue(operation["outcome_unknown"])
        self.assertIsNone(operation["data_completed"])
        self.assertEqual(len(self.puts()), 1)
        self.assertTrue(self.puts()[0][1].endswith("/datasources/source_a/"))
        self.assertEqual(self.resources["connection_a"], original)

    def test_unpublished_clean_configuration_is_not_a_ready_baseline(self):
        self.resources["clean_a"]["spec"].update(config_revision=10, deploy_revision=9)
        self.schedule()
        self.assertNotIn("source_replay", self.snapshot.bkbase_v4_resources)
        self.assertEqual(self.puts(), [])

    def test_dataconn_get_uses_formal_connection_namespace(self):
        self.resources["source_a"]["spec"]["data_conn"]["namespace"] = "connections"
        self.resources["connection_a"]["metadata"]["namespace"] = "connections"
        self.schedule()
        self.assertTrue(
            any(
                method == "GET" and url.endswith("/namespaces/connections/dataconns/connection_a/")
                for method, url, _ in self.requests
            )
        )
        operation = json.dumps(self.snapshot.bkbase_v4_resources["source_replay"])
        self.assertNotIn(
            self.handler().config["access_conf_info"]["resource"]["scope"][0]["headers"]["Authorization"], operation
        )

    def test_non_replay_v4_preparing_does_not_enter_legacy_loop(self):
        self.snapshot.status = SnapshotRunningStatus.PREPARING
        self.snapshot.save(update_fields=["status"])
        tasks.start_snapshot.run()
        self.assertEqual(self.requests, [])
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.FAILED)
        self.assertTrue(self.snapshot.status_msg)

    def test_system_refresh_other_tenant_does_not_schedule_legacy_work(self):
        original = deepcopy(self.snapshot.bkbase_v4_resources)
        tasks.refresh_system_snapshots.run(self.system.system_id)
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.RUNNING)
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.RUNNING)
        self.assertEqual(self.snapshot.bkbase_v4_resources, original)
        self.assertEqual(self.requests, [])

    def test_running_toggle_without_configuration_change_is_idempotent(self):
        with mock.patch.object(ToggleJoinDataResource, "pre_check", return_value=None):
            ToggleJoinDataResource().request(system_id=self.system.system_id, resource_type_id="asset", is_enabled=True)
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.RUNNING)
        self.assertNotIn("source_replay", self.snapshot.bkbase_v4_resources)
        self.assertEqual(self.requests, [])

    def test_first_enable_from_unconfigured_placeholder_uses_default_storage(self):
        Snapshot.objects.filter(pk=self.snapshot.pk).update(
            status=SnapshotRunningStatus.CLOSED,
            bkbase_data_id=None,
            bkbase_processing_id=None,
            bkbase_table_id=None,
            bkbase_v4_resources={},
        )
        self.snapshot.storages.all().delete()
        with mock.patch.object(ToggleJoinDataResource, "pre_check", return_value=None):
            result = ToggleJoinDataResource().request(
                system_id=self.system.system_id, resource_type_id="asset", is_enabled=True, pull_type="partial"
            )
        self.assertEqual(result["status"], SnapshotRunningStatus.PREPARING)
        self.assertEqual(set(result["storage_type"]), {"doris", "hdfs"})
        self.assertEqual(self.requests, [])

    def test_ended_replay_intent_cannot_leave_new_preparing_entry_hanging(self):
        self.schedule()
        self.snapshot.bkbase_v4_resources["source_replay"]["active"] = False
        self.snapshot.save(update_fields=["bkbase_v4_resources"])
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.FAILED)
        self.assertTrue(self.snapshot.status_msg)
        self.assertEqual(self.puts(), [])

    def test_unsupported_rejection_does_not_override_newly_queued_intent(self):
        self.snapshot.status = SnapshotRunningStatus.PREPARING
        self.snapshot.save(update_fields=["status"])
        original = source.fail_snapshot_replay

        def queue_before_rejection(snapshot, **kwargs):
            current = Snapshot.objects.get(pk=snapshot.pk)
            current.bkbase_v4_resources["source_replay"] = {"operation_id": "new_generation", "active": True}
            current.save(update_fields=["bkbase_v4_resources"])
            return original(snapshot, **kwargs)

        with mock.patch.object(source, "fail_snapshot_replay", side_effect=queue_before_rejection):
            tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)
        self.assertEqual(
            self.snapshot.bkbase_v4_resources["source_replay"], {"operation_id": "new_generation", "active": True}
        )
        self.assertEqual(self.requests, [])

    def test_unsupported_rejection_does_not_take_over_pending_stop(self):
        self.snapshot.status = SnapshotRunningStatus.PREPARING
        self.snapshot.status_msg = "stop owns state"
        self.snapshot.bkbase_v4_resources["pending_action"] = "stop"
        self.snapshot.save(update_fields=["status", "status_msg", "bkbase_v4_resources"])
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)
        self.assertEqual(self.snapshot.status_msg, "stop owns state")
        self.assertEqual(self.requests, [])

    def test_pending_observation_timeout_never_repeats_put(self):
        self.schedule()
        tasks.start_snapshot.run()
        self.resources["source_a"]["status"]["phase"] = "Pending"
        with mock.patch.object(source, "BKBASE_V4_MAX_POLLS", 2):
            tasks.start_snapshot.run()
            tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.FAILED)
        self.assertEqual(len(self.puts()), 1)

    def test_interrupted_claim_recovers_as_unknown_without_resending(self):
        self.schedule()

        def interrupt():
            raise SystemExit("synthetic interruption")

        self.put_hook = interrupt
        with self.assertRaises(SystemExit):
            tasks.start_snapshot.run()
        self.put_hook = None
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        operation = self.snapshot.bkbase_v4_resources["source_replay"]
        self.assertTrue(operation["attempted"])
        self.assertTrue(operation["outcome_unknown"])
        self.assertIsNone(operation["accepted"])
        self.assertEqual(len(self.puts()), 1)

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_periodic_refresh_keeps_original_storage_loop(self):
        self.schedule()
        with mock.patch.object(tasks.AssetHandler, "start", return_value=True) as start:
            tasks.start_snapshot.run()
        self.assertEqual(start.call_count, 2)
        self.assertEqual(self.requests, [])
