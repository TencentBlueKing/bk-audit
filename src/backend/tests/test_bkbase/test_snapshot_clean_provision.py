"""通过 Toggle 和定时任务验证新 Source 与 Clean 的接力，正式 SDK 只模拟 HTTP。"""
import json
from copy import deepcopy
from unittest import mock

import requests
from bk_resource.exceptions import APIRequestError
from django.db import connection
from django.test import TransactionTestCase, override_settings

from api.bk_base_v4.default import BkBaseV4Resource
from apps.meta.models import ResourceType, System
from services.web.bkbase import clean, source
from services.web.databus import tasks
from services.web.databus.collector.resources import ToggleJoinDataResource
from services.web.databus.collector.snapshot.join.etl_storage import (
    AssetEtlStorageHandler,
)
from services.web.databus.constants import SnapshotRunningStatus
from services.web.databus.models import Snapshot


class SnapshotCleanProvisionFixture:
    def setUp(self):
        self.system = System.objects.create(
            system_id="provision_clean",
            instance_id="provision_clean",
            namespace="audit",
            callback_url="https://source.test",
            auth_token="synthetic",
        )
        self.resource_type = ResourceType.objects.create(
            system_id=self.system.system_id,
            resource_type_id="resource_a",
            unique_id="provision_clean:resource_a",
            name="resource",
            path="/resources",
        )
        self.resources = {
            "data_a": self.remote({"name": "data_a", "tenant": "default", "namespace": "project_a"}, "DataId", {})
        }
        self.requests = []
        self.on_post_clean = None
        self.on_get_clean = None
        self.timeout_clean = False
        self.persist_lost_clean = False
        self.enterContext(mock.patch.object(BkBaseV4Resource, "build_header", return_value={}))
        self.enterContext(mock.patch("requests.sessions.Session.request", side_effect=self.transport))
        self.enterContext(mock.patch.object(ToggleJoinDataResource, "pre_check"))
        self.enterContext(
            mock.patch.object(
                AssetEtlStorageHandler,
                "schema_fields",
                new_callable=mock.PropertyMock,
                return_value=[
                    {
                        "field_name": "custom_text",
                        "field_type": "string",
                        "field_alias": "field",
                        "is_dimension": False,
                        "is_key": False,
                        "field_index": 0,
                        "is_json": False,
                        "is_original_json": False,
                        "is_index": False,
                    }
                ],
            )
        )
        self.enterContext(mock.patch("core.lock.CacheLock._init", return_value=True))
        self.enterContext(mock.patch("core.lock.CacheLock.release", return_value=True))
        # 本组验证业务状态转移；真实 Redis 租约由锁专项验证。
        self.enterContext(mock.patch("core.utils.lock.RedisLock.acquire", return_value=True))
        self.enterContext(mock.patch("core.utils.lock.RedisLock.release", return_value=True))

    @staticmethod
    def remote(metadata, kind, spec, *, phase="Ok"):
        return {"kind": kind, "metadata": deepcopy(metadata), "spec": deepcopy(spec), "status": {"phase": phase}}

    def transport(self, method, url, **kwargs):
        self.assertFalse(connection.in_atomic_block, "official HTTP must run outside the DB transaction")
        endpoint = url.rstrip("/").split("/")[-1]
        payload = deepcopy(kwargs.get("json"))
        self.requests.append((method, url, payload))
        status = 200
        if method == "POST":
            kind = {"dataconns": "DataConn", "datasources": "DataSource", "cleans": "Clean"}[endpoint]
            self.assertIsNone(payload["status"])
            name = payload["metadata"]["name"]
            value = self.remote(payload["metadata"], kind, payload["spec"])
            if kind == "DataSource":
                value["metadata"]["labels"] = {"raw_data_id": "71"}
                value["spec"]["current_status"] = "Stopped"
                value["spec"]["data_id"] = {
                    "kind": "DataId",
                    "tenant": "default",
                    "namespace": "project_a",
                    "name": "data_a",
                }
                value["spec"]["basic_info"]["access_channel"] = "bkbase"
                value["spec"]["report_config"]["server_default"] = None
                value["spec"]["report_config"]["pagination"]["server_default"] = None
            if kind == "Clean":
                if self.on_post_clean:
                    self.on_post_clean()
                value["status"] = {"phase": "Pending", "history_id": 27}
                value["spec"]["current_status"] = "Stopped"
                if self.timeout_clean:
                    if self.persist_lost_clean:
                        self.resources[name] = value
                    raise requests.Timeout("synthetic lost Clean receipt")
            self.resources[name] = value
        elif method == "GET":
            if self.on_get_clean and "/cleans/" in url:
                self.on_get_clean()
            value = deepcopy(self.resources.get(endpoint))
            if "/v4/result_tables/" in url:
                value = {
                    "metadata": {"tenant": "default", "namespace": "project_a", "name": "actual_snapshot_rt"},
                    "spec": {"predefiendResultTableId": endpoint},
                    "status": {"related": []},
                }
            if value is None:
                status, value = 404, {}
        else:
            self.fail(f"unexpected write {method} {url}")
        response = requests.Response()
        response.status_code = status
        response.url = url
        response.request = requests.Request(method, url).prepare()
        response._content = json.dumps({"result": status == 200, "code": "00", "data": value}).encode()
        return response

    def snapshot(self):
        return Snapshot.objects.get(
            system_id=self.system.system_id, resource_type_id=self.resource_type.resource_type_id
        )

    def prepare(self, *, join_data_type="asset"):
        response = ToggleJoinDataResource().request(
            {
                "system_id": self.system.system_id,
                "resource_type_id": self.resource_type.resource_type_id,
                "is_enabled": True,
                "join_data_type": join_data_type,
                "storage_type": ["redis"] if join_data_type == "basic" else ["hdfs", "doris"],
            }
        )
        self.assertEqual(response["status"], SnapshotRunningStatus.PREPARING)
        for _ in range(2):
            tasks.start_snapshot.run()
        self.assertEqual(self.snapshot().bkbase_v4_resources["source_provision"]["stage"], "source_accepted")

    def start(self, *, join_data_type="asset"):
        self.prepare(join_data_type=join_data_type)
        tasks.start_snapshot.run()
        snapshot = self.snapshot()
        self.assertEqual(snapshot.bkbase_data_id, 71)
        self.assertEqual(snapshot.status, SnapshotRunningStatus.PREPARING, snapshot.status_msg)
        self.assertEqual(snapshot.bkbase_v4_resources["source_provision"]["stage"], "ready")
        self.assertFalse(self.clean_posts())

    def clean_posts(self):
        return [payload for method, url, payload in self.requests if method == "POST" and url.endswith("/cleans/")]

    def assert_no_storage_or_source_update(self):
        self.assertFalse(any("/datastorages/" in url for _, url, _ in self.requests))
        self.assertFalse(any(method == "PUT" and "/datasources/" in url for method, url, _ in self.requests))


@override_settings(
    BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="default", BKBASE_V4_NAMESPACE="project_a", HIGH_RISK_PORTS=[]
)
class SnapshotCleanProvisionTests(SnapshotCleanProvisionFixture, TransactionTestCase):
    def test_latest_clean_history_can_change_when_the_declared_revision_becomes_running(self):
        self.start()
        tasks.start_snapshot.run()
        (post,) = self.clean_posts()
        remote = self.resources[post["metadata"]["name"]]
        remote["status"].update(phase="Ok", history_id=28)
        remote["spec"]["current_status"] = "Running"
        tasks.start_snapshot.run()
        snapshot = self.snapshot()
        self.assertTrue(snapshot.bkbase_v4_resources.get("clean_ready"), snapshot.status_msg)
        self.assertEqual(snapshot.bkbase_table_id, post["spec"]["result_table_id"])
        self.assertEqual(snapshot.bkbase_v4_resources["source_provision"]["clean_step"]["history_id"], 27)
        self.assertEqual(len(self.clean_posts()), 1)
        self.assert_no_storage_or_source_update()

    def test_changed_revision_is_not_confirmed_even_when_new_history_is_running(self):
        self.start()
        tasks.start_snapshot.run()
        (post,) = self.clean_posts()
        remote = self.resources[post["metadata"]["name"]]
        remote["status"].update(phase="Ok", history_id=28)
        remote["spec"].update(current_status="Running", deploy_revision=post["spec"]["deploy_revision"] + 1)
        tasks.start_snapshot.run()
        self.assertEqual(self.snapshot().status, SnapshotRunningStatus.FAILED)
        self.assertFalse(self.snapshot().bkbase_v4_resources.get("clean_ready"))
        self.assertEqual(len(self.clean_posts()), 1)
        self.assert_no_storage_or_source_update()

    def test_new_local_operation_cannot_be_bound_by_an_old_running_history_response(self):
        self.start()
        tasks.start_snapshot.run()
        (post,) = self.clean_posts()
        remote = self.resources[post["metadata"]["name"]]
        remote["status"].update(phase="Ok", history_id=28)
        remote["spec"]["current_status"] = "Running"

        def replace_operation():
            snapshot = self.snapshot()
            snapshot.bkbase_v4_resources["source_provision"]["operation_id"] = "new_local_operation"
            snapshot.save(update_fields=["bkbase_v4_resources"])

        self.on_get_clean = replace_operation
        tasks.start_snapshot.run()
        snapshot = self.snapshot()
        self.assertEqual(snapshot.bkbase_v4_resources["source_provision"]["operation_id"], "new_local_operation")
        self.assertFalse(snapshot.bkbase_v4_resources.get("clean_ready"))
        self.assertEqual(len(self.clean_posts()), 1)
        self.assert_no_storage_or_source_update()

    def test_accepted_legacy_list_source_keeps_its_clean_pair_after_new_default_changes(self):
        builder = source.build_pull_report_config

        def legacy_report(*args, **kwargs):
            report = builder(*args, **kwargs)
            report["data_path"] = ".data.results"
            return report

        with mock.patch.object(source, "build_pull_report_config", side_effect=legacy_report):
            self.prepare()
        tasks.start_snapshot.run()
        self.assertEqual(self.snapshot().bkbase_v4_resources["source_provision"]["stage"], "ready")
        tasks.start_snapshot.run()
        [posted] = self.clean_posts()
        self.assertEqual(len([r for r in posted["spec"]["rules"] if r["operator"]["type"] == "json_de"]), 1)
        self.assertFalse(any(method == "PUT" and "/datasources/" in url for method, url, _ in self.requests))

    def test_source_shape_drift_after_clean_claim_does_not_reinterpret_saved_plan(self):
        self.start()
        tasks.start_snapshot.run()
        [posted] = self.clean_posts()
        snapshot = self.snapshot()
        source_ref = snapshot.bkbase_v4_resources["data_source"]
        self.resources[source_ref["name"]]["spec"]["report_config"]["data_path"] = ".data.results"
        remote = self.resources[posted["metadata"]["name"]]
        remote["status"]["phase"] = "Ok"
        remote["spec"]["current_status"] = "Running"
        tasks.start_snapshot.run()
        self.assertFalse(self.snapshot().bkbase_v4_resources.get("clean_ready"))
        self.assertIn("input shape", self.snapshot().status_msg)
        self.assertEqual(len(self.clean_posts()), 1)
        self.assert_no_storage_or_source_update()

    def test_asset_clean_resolves_and_persists_ref_but_keeps_source_stopped_until_storage_is_provisioned(self):
        self.start()

        def inspect_claim():
            operation = self.snapshot().bkbase_v4_resources["source_provision"]
            self.assertIsNone(operation["clean_step"]["accepted"])
            tasks.start_snapshot.run()
            self.assertEqual(len(self.clean_posts()), 1)

        self.on_post_clean = inspect_claim
        tasks.start_snapshot.run()
        (post,) = self.clean_posts()
        spec = post["spec"]
        self.assertEqual(spec["raw_data_id"], 71)
        self.assertEqual(spec["result_table_source"], "new")
        self.assertEqual(spec["desired_status"], "Running")
        self.assertEqual(spec["config_revision"], spec["deploy_revision"])
        self.assertTrue(spec["rules"])
        self.assertEqual(len([r for r in spec["rules"] if r["operator"]["type"] == "json_de"]), 2)
        self.assertEqual(self.snapshot().status, SnapshotRunningStatus.PREPARING)
        tasks.start_snapshot.run()
        self.assertEqual(self.snapshot().status, SnapshotRunningStatus.PREPARING)
        remote = self.resources[post["metadata"]["name"]]
        remote["status"]["phase"] = "Ok"
        remote["spec"]["current_status"] = "Running"
        tasks.start_snapshot.run()
        snapshot = self.snapshot()
        self.assertEqual(snapshot.status, SnapshotRunningStatus.PREPARING, snapshot.status_msg)
        self.assertEqual(snapshot.bkbase_table_id, spec["result_table_id"])
        self.assertTrue(snapshot.bkbase_v4_resources["clean_ready"])
        self.assertEqual(snapshot.bkbase_v4_resources["result_table_id"], spec["result_table_id"])
        self.assertEqual(
            snapshot.bkbase_v4_resources["result_table"],
            {"kind": "ResultTable", "tenant": "default", "namespace": "project_a", "name": "actual_snapshot_rt"},
        )
        self.assertTrue(any("/v4/result_tables/" in url for _, url, _ in self.requests))
        self.assertEqual(len(self.clean_posts()), 1)
        self.assert_no_storage_or_source_update()

    def test_lost_clean_response_then_not_found_is_never_reposted(self):
        self.start(join_data_type="basic")
        self.timeout_clean = True
        tasks.start_snapshot.run()
        self.assertEqual(len(self.clean_posts()), 1)
        self.timeout_clean = False
        tasks.start_snapshot.run()
        tasks.start_snapshot.run()
        self.assertEqual(len(self.clean_posts()), 1)
        self.assertIsNone(self.snapshot().bkbase_v4_resources["source_provision"]["clean_step"]["accepted"])
        self.assert_no_storage_or_source_update()

    def test_lost_receipt_can_be_confirmed_by_exact_new_running_clean_get(self):
        self.start(join_data_type="basic")
        self.timeout_clean = self.persist_lost_clean = True
        tasks.start_snapshot.run()
        (post,) = self.clean_posts()
        remote = self.resources[post["metadata"]["name"]]
        remote["status"]["phase"] = "Ok"
        remote["spec"]["current_status"] = "Running"
        tasks.start_snapshot.run()
        self.assertTrue(self.snapshot().bkbase_v4_resources["clean_ready"])
        self.assertEqual(len(self.clean_posts()), 1)
        self.assert_no_storage_or_source_update()

    def test_lookup_failure_keeps_source_stopped_and_does_not_attach_ref(self):
        self.start()
        tasks.start_snapshot.run()
        (post,) = self.clean_posts()
        remote = self.resources[post["metadata"]["name"]]
        remote["status"]["phase"] = "Ok"
        remote["spec"]["current_status"] = "Running"
        error = APIRequestError(module_name="bkbase_v4", url="/v4/result_tables/", result="synthetic lookup failure")
        with mock.patch.object(clean.api.bk_base_v4, "result_table_info", side_effect=error):
            tasks.start_snapshot.run()
        snapshot = self.snapshot()
        self.assertEqual(snapshot.status, SnapshotRunningStatus.PREPARING)
        self.assertNotIn("result_table", snapshot.bkbase_v4_resources)
        self.assertFalse(snapshot.bkbase_v4_resources.get("clean_ready"))
        self.assertEqual(len(self.clean_posts()), 1)
        self.assert_no_storage_or_source_update()

    def test_cross_tenant_lookup_cannot_confirm_clean_ready_or_activate_source(self):
        self.start()
        tasks.start_snapshot.run()
        (post,) = self.clean_posts()
        remote = self.resources[post["metadata"]["name"]]
        remote["status"]["phase"] = "Ok"
        remote["status"]["history_id"] = 28
        remote["spec"]["current_status"] = "Running"
        with mock.patch.object(
            clean.api.bk_base_v4,
            "result_table_info",
            return_value={
                "metadata": {"tenant": "another_tenant", "namespace": "project_a", "name": "actual_snapshot_rt"},
                "spec": {"predefiendResultTableId": post["spec"]["result_table_id"]},
            },
        ):
            tasks.start_snapshot.run()
        snapshot = self.snapshot()
        self.assertEqual(snapshot.status, SnapshotRunningStatus.FAILED)
        self.assertNotIn("result_table", snapshot.bkbase_v4_resources)
        self.assertFalse(snapshot.bkbase_v4_resources.get("clean_ready"))
        self.assertEqual(len(self.clean_posts()), 1)
        self.assert_no_storage_or_source_update()

    def test_failed_clean_is_reported_without_binding_or_repost(self):
        self.start()
        tasks.start_snapshot.run()
        (post,) = self.clean_posts()
        self.resources[post["metadata"]["name"]]["status"].update(phase="Failed", history_id=28)
        tasks.start_snapshot.run()
        tasks.start_snapshot.run()
        snapshot = self.snapshot()
        self.assertEqual(snapshot.status, SnapshotRunningStatus.FAILED)
        self.assertEqual(snapshot.status_msg, "Snapshot Clean failed")
        self.assertNotIn("clean", snapshot.bkbase_v4_resources)
        self.assertEqual(len(self.clean_posts()), 1)
        self.assert_no_storage_or_source_update()

    def test_local_config_change_between_clean_lookup_and_claim_prevents_post(self):
        self.start()
        snapshot_id = self.snapshot().pk
        self.on_get_clean = lambda: Snapshot.objects.filter(pk=snapshot_id).update(custom_config={"new": "local"})
        tasks.start_snapshot.run()
        snapshot = self.snapshot()
        self.assertEqual(snapshot.status, SnapshotRunningStatus.FAILED)
        self.assertEqual(snapshot.custom_config, {"new": "local"})
        self.assertFalse(self.clean_posts())
        self.assert_no_storage_or_source_update()

    def test_source_data_id_drift_prevents_any_clean_request(self):
        self.start()
        source_ref = self.snapshot().bkbase_v4_resources["data_source"]
        self.resources[source_ref["name"]]["spec"]["data_id"]["name"] = "changed"
        tasks.start_snapshot.run()
        self.assertEqual(self.snapshot().status, SnapshotRunningStatus.FAILED)
        self.assertFalse(any("/cleans/" in url for _, url, _ in self.requests))
        self.assert_no_storage_or_source_update()

    def test_stopped_source_path_drift_before_ready_is_rejected(self):
        self.prepare()
        binding = self.snapshot().bkbase_v4_resources
        ref = binding["data_source"]
        self.resources[ref["name"]]["spec"]["report_config"]["path"] = "/changed"

        tasks.start_snapshot.run()
        tasks.start_snapshot.run()

        snapshot = self.snapshot()
        self.assertEqual(snapshot.status, SnapshotRunningStatus.FAILED)
        self.assertIn("PULL report configuration drifted", snapshot.status_msg)
        self.assertIsNone(snapshot.bkbase_data_id)
        self.assertEqual(snapshot.bkbase_v4_resources["data_source"], ref)
        self.assertFalse(any("/cleans/" in url for _, url, _ in self.requests))
        self.assert_no_storage_or_source_update()

    def test_ready_source_path_drift_prevents_clean_claim(self):
        self.start()
        ref = self.snapshot().bkbase_v4_resources["data_source"]
        self.resources[ref["name"]]["spec"]["report_config"]["path"] = "/changed"

        tasks.start_snapshot.run()

        snapshot = self.snapshot()
        self.assertEqual(snapshot.status, SnapshotRunningStatus.FAILED)
        self.assertIn("PULL report configuration drifted", snapshot.status_msg)
        self.assertNotIn("clean_step", snapshot.bkbase_v4_resources["source_provision"])
        self.assertFalse(any("/cleans/" in url for _, url, _ in self.requests))
        self.assert_no_storage_or_source_update()

    def test_source_body_drift_after_clean_post_prevents_ready(self):
        self.start()
        tasks.start_snapshot.run()
        (post,) = self.clean_posts()
        remote = self.resources[post["metadata"]["name"]]
        remote["status"]["phase"] = "Ok"
        remote["spec"]["current_status"] = "Running"
        ref = self.snapshot().bkbase_v4_resources["data_source"]
        self.resources[ref["name"]]["spec"]["report_config"]["body"] = '{"changed": true}'

        tasks.start_snapshot.run()
        tasks.start_snapshot.run()

        snapshot = self.snapshot()
        self.assertEqual(snapshot.status, SnapshotRunningStatus.FAILED)
        self.assertIn("PULL report configuration drifted", snapshot.status_msg)
        self.assertNotIn("clean_ready", snapshot.bkbase_v4_resources)
        self.assertEqual(len(self.clean_posts()), 1)
        self.assert_no_storage_or_source_update()
