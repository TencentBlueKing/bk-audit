"""验证系统手工刷新沿真实PULL更新调用链维护Source。

复用合成存量资源和HTTP边界，不预塞refs、不mock绑定/维护Service。
资产独占DataConn按正式全量更新；受理、未知结果和新配置观察分别断言。
"""
import json
from copy import deepcopy
from unittest import mock

import requests
from django.test import TestCase, override_settings

from services.web.bkbase import source
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus import tasks
from services.web.databus.collector.snapshot.join.http_pull import HttpPullHandler
from services.web.databus.constants import (
    JoinDataPullType,
    JoinDataType,
    SnapshotRunningStatus,
)
from services.web.databus.models import Snapshot
from tests.test_bkbase import test_snapshot_binding_ingestion as binding_fixture


@override_settings(
    BKBASE_API_VERSION="v4",
    BKBASE_V4_TENANT="default",
    BKBASE_V4_NAMESPACE="project_a",
    HTTP_PULL_REDIS_TIMEOUT="10d",
    HIGH_RISK_PORTS=[],
    APP_CODE="synthetic_app",
    SECRET_KEY="synthetic_secret",
    BK_RESOURCE={
        "PLATFORM_AUTH_ENABLED": True,
        "PLATFORM_AUTH_ACCESS_USERNAME": "synthetic_platform",
        "PLATFORM_AUTH_ACCESS_TOKEN": "synthetic_token",
    },
)
class SnapshotConfigurationTests(TestCase):
    ref = binding_fixture.SnapshotBindingIngestionTests.ref
    remote = binding_fixture.SnapshotBindingIngestionTests.remote

    def setUp(self):
        binding_fixture.SnapshotBindingIngestionTests.setUp(self)
        self.resources["source_a"]["spec"]["custom_future"] = {"keep": 1}
        self.resources["source_a"]["spec"]["report_config"]["pagination"]["future"] = "keep"
        self.resources["source_a"]["spec"]["report_config"]["history_data"] = {"end_time": "retained"}
        self.resources["connection_a"]["spec"]["future"] = "keep"
        self.put_timeout = False
        self.timeout_applies = False

    def transport(self, method, url, **kwargs):
        if method.upper() == "PUT" and "/dataconns/" in url:
            self.requests.append(("PUT", url, {}, deepcopy(kwargs["json"])))
            self.assertTrue(url.endswith("/dataconns/connection_a/"))
            self.assertIsNone(kwargs["json"]["status"])
            if getattr(self, "connection_failure", False) and not getattr(self, "connection_timeout_applies", False):
                raise requests.Timeout("synthetic connection write outcome unknown")
            self.resources["connection_a"]["metadata"] = deepcopy(kwargs["json"]["metadata"])
            self.resources["connection_a"]["spec"] = deepcopy(kwargs["json"]["spec"])
            self.resources["connection_a"]["metadata"].setdefault("annotations", {})["conn_info_encrypted"] = "true"
            self.resources["connection_a"]["spec"]["conn_info"]["headers"]["Authorization"] = getattr(
                self, "connection_saved_cipher", "synthetic_updated_cipher"
            )
            self.resources["connection_a"]["status"] = {"phase": "Pending", "history_id": 22}
            if getattr(self, "connection_failure", False):
                raise requests.Timeout("synthetic connection write outcome unknown")
            response = requests.Response()
            response.status_code = 200
            response._content = json.dumps(
                {"result": True, "code": "00", "data": self.resources["connection_a"]}
            ).encode()
            return response
        before = deepcopy(self.resources["source_a"]["spec"])
        response = binding_fixture.SnapshotBindingIngestionTests.transport(self, method, url, **kwargs)
        if method.upper() == "PUT" and getattr(self, "server_source_updated_at", None):
            self.resources["source_a"]["spec"]["updated_at"] = self.server_source_updated_at
            payload = json.loads(response.content)
            payload["data"]["spec"]["updated_at"] = self.server_source_updated_at
            response._content = json.dumps(payload).encode()
        if method.upper() == "PUT" and self.put_timeout:
            if not self.timeout_applies:
                self.resources["source_a"]["spec"] = before
            raise requests.Timeout("synthetic outcome unknown")
        return response

    def configure(self):
        tasks.refresh_system_snapshots.run(self.system.system_id)
        self.snapshot.refresh_from_db()

    def confirm_connection(self):
        self.resources["connection_a"]["status"]["phase"] = "Ok"
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()

    def configure_double_update_with_server_clock(self):
        """模拟正式平台在Source PUT后更新自己的顶层时间，仍走实际维护任务。"""
        self.resources["source_a"]["spec"]["updated_at"] = "2026-01-01 10:00:00"
        self.server_source_updated_at = "2026-01-01 10:01:00"
        self.system.callback_url = "https://other.test"
        self.system.save(update_fields=["callback_url"])
        self.configure()
        tasks.start_snapshot.run()
        self.confirm_connection()
        self.assertTrue(self.snapshot.bkbase_v4_resources["source_replay"]["accepted"])
        self.assertEqual(len([r for r in self.requests if r[0] == "PUT"]), 2)

    def test_server_source_updated_at_does_not_block_completed_double_update(self):
        self.configure_double_update_with_server_clock()
        source_put = [r for r in self.requests if r[0] == "PUT" and "/datasources/" in r[1]][0]
        self.assertEqual(source_put[3]["spec"]["updated_at"], "2026-01-01 10:00:00")
        self.assertEqual(self.resources["source_a"]["spec"]["updated_at"], self.server_source_updated_at)
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.RUNNING)
        self.assertTrue(self.snapshot.bkbase_v4_resources["source_replay"]["config_observed"])
        self.assertFalse(self.snapshot.bkbase_v4_resources["source_replay"]["active"])
        self.assertEqual(len([r for r in self.requests if r[0] == "PUT"]), 2)

    def test_changed_report_config_period_is_not_accepted_as_applied(self):
        self.configure_double_update_with_server_clock()
        self.resources["source_a"]["spec"]["report_config"]["period"] = 99
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)
        self.assertFalse(self.snapshot.bkbase_v4_resources["source_replay"]["config_observed"])
        self.assertEqual(len([r for r in self.requests if r[0] == "PUT"]), 2)

    def test_nested_report_config_updated_at_remains_a_business_field(self):
        self.resources["source_a"]["spec"]["report_config"]["updated_at"] = "business_cursor_a"
        self.configure_double_update_with_server_clock()
        self.resources["source_a"]["spec"]["report_config"]["updated_at"] = "business_cursor_b"
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)
        self.assertFalse(self.snapshot.bkbase_v4_resources["source_replay"]["config_observed"])
        self.assertEqual(len([r for r in self.requests if r[0] == "PUT"]), 2)

    def test_system_refresh_discovers_and_queues_changed_source_configuration(self):
        Snapshot.objects.filter(pk=self.snapshot.pk).update(pull_config={"period": 3, "limit": 50})
        self.resource_type.path = "/v2/resources"
        self.resource_type.save(update_fields=["path"])
        self.configure()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)
        self.assertEqual(self.snapshot.bkbase_v4_resources.get("data_source"), self.expected["data_source"])
        operation = self.snapshot.bkbase_v4_resources.get("source_replay", {})
        self.assertEqual(operation.get("mode"), "configure")
        self.assertFalse(operation["attempted"])
        self.assertIsNone(operation["accepted"])
        self.assertFalse(any(r[0] != "GET" for r in self.requests))
        old = deepcopy(self.resources["source_a"])
        old_connection = deepcopy(self.resources["connection_a"])
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        writes = [r for r in self.requests if r[0] == "PUT"]
        self.assertEqual(len(writes), 1)
        payload = writes[0][3]
        self.assertEqual(payload["metadata"], old["metadata"])
        self.assertEqual(payload["spec"]["custom_future"], {"keep": 1})
        report = payload["spec"]["report_config"]
        self.assertEqual(report["path"], "/v2/resources")
        self.assertEqual(report["period"], 3)
        self.assertEqual(report["period_unit"], "minute")
        self.assertEqual(
            report["pagination"], {"start_offset": 0, "limit": 50, "total_path": "data.count", "future": "keep"}
        )
        self.assertEqual(report["increment_field"], {"type": "time", "time_format": "Unix Time Stamp(milliseconds)"})
        self.assertEqual(report["history_data"], {"start_time": "0", "end_time": "retained"})
        self.assertEqual(self.resources["connection_a"], old_connection)
        self.assertIs(self.snapshot.bkbase_v4_resources["source_replay"]["accepted"], True)
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.RUNNING)
        self.assertIsNone(self.snapshot.bkbase_v4_resources["source_replay"]["data_completed"])

    def test_asset_authentication_update_writes_connection_then_source(self):
        self.system.auth_token = "changed_synthetic_token"
        self.system.save(update_fields=["auth_token"])
        self.configure()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        writes = [r for r in self.requests if r[0] == "PUT"]
        self.assertEqual(len(writes), 1)
        self.assertIn("/dataconns/connection_a/", writes[0][1])
        self.assertEqual(
            writes[0][3]["spec"]["conn_info"]["headers"]["Authorization"],
            type(self.system).objects.get(pk=self.system.pk).base64_token,
        )
        self.assertEqual(writes[0][3]["spec"]["future"], "keep")
        self.assertTrue(self.snapshot.bkbase_v4_resources["source_replay"]["connection_accepted"])
        self.assertFalse(self.snapshot.bkbase_v4_resources["source_replay"]["attempted"])
        tasks.start_snapshot.run()
        self.assertEqual(len([r for r in self.requests if r[0] == "PUT"]), 1)
        self.resources["connection_a"]["status"] = {"phase": "Ok", "history_id": 21}
        tasks.start_snapshot.run()
        self.assertEqual(len([r for r in self.requests if r[0] == "PUT"]), 1)
        self.resources["connection_a"]["status"]["history_id"] = 22
        self.confirm_connection()
        self.assertIn("/datasources/source_a/", [r for r in self.requests if r[0] == "PUT"][1][1])
        self.assertTrue(self.snapshot.bkbase_v4_resources["source_replay"]["accepted"])
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.RUNNING)

    def test_asset_origin_change_preserves_full_connection_metadata(self):
        self.resources["connection_a"]["metadata"]["annotations"] = {"conn_info_encrypted": "true", "retain": "yes"}
        self.resources["connection_a"]["metadata"]["labels"] = {"retain": "label"}
        self.system.callback_url = "https://other.test"
        self.system.save(update_fields=["callback_url"])
        self.configure()
        tasks.start_snapshot.run()
        self.confirm_connection()
        writes = [r for r in self.requests if r[0] == "PUT"]
        self.assertEqual(len(writes), 2)
        self.assertEqual(writes[0][3]["spec"]["conn_info"]["url"], "https://other.test")
        self.assertEqual(writes[0][3]["metadata"], self.resources["connection_a"]["metadata"])
        self.assertEqual(writes[1][3]["spec"]["report_config"]["path"], "/resources")

    def test_connection_failure_does_not_write_source_or_report_overall_success(self):
        self.system.callback_url = "https://other.test"
        self.system.save(update_fields=["callback_url"])
        self.configure()
        self.connection_failure = True
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        writes = [r for r in self.requests if r[0] == "PUT"]
        self.assertEqual(len(writes), 1)
        self.assertIn("/dataconns/", writes[0][1])
        operation = self.snapshot.bkbase_v4_resources["source_replay"]
        self.assertIsNone(operation["accepted"])
        self.assertTrue(operation["outcome_unknown"])
        self.assertIn("DataConn", operation["message"])

    def test_lost_connection_receipt_with_target_get_does_not_write_source_or_retry(self):
        self.system.callback_url = "https://other.test"
        self.system.save(update_fields=["callback_url"])
        self.configure()
        self.connection_failure = self.connection_timeout_applies = True
        tasks.start_snapshot.run()
        self.confirm_connection()
        tasks.start_snapshot.run()
        writes = [r for r in self.requests if r[0] == "PUT"]
        self.assertEqual(len(writes), 1)
        self.assertIn("/dataconns/", writes[0][1])
        operation = self.snapshot.bkbase_v4_resources["source_replay"]
        self.assertFalse(operation["attempted"])
        self.assertTrue(operation["outcome_unknown"])

    def test_source_failure_records_connection_accepted_without_overall_success(self):
        self.system.callback_url = "https://other.test"
        self.system.save(update_fields=["callback_url"])
        self.configure()
        self.put_timeout = True
        tasks.start_snapshot.run()
        self.confirm_connection()
        operation = self.snapshot.bkbase_v4_resources["source_replay"]
        self.assertIs(operation["connection_accepted"], True)
        self.assertIsNone(operation["accepted"])
        self.assertIn("DataSource", operation["message"])
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)

    def test_same_connection_saved_cipher_is_not_used_as_new_plaintext(self):
        self.connection_saved_cipher = "synthetic_saved_cipher"
        conn = self.resources["connection_a"]
        conn["metadata"]["annotations"] = {"conn_info_encrypted": "true"}
        conn["spec"]["conn_info"]["headers"].update(Authorization=self.connection_saved_cipher, Future="retain")
        Snapshot.objects.filter(pk=self.snapshot.pk).update(pull_config={"period": 3})
        self.configure()
        tasks.start_snapshot.run()
        writes = [r for r in self.requests if r[0] == "PUT"]
        self.assertEqual(len(writes), 1)
        headers = writes[0][3]["spec"]["conn_info"]["headers"]
        self.assertEqual(headers["Authorization"], self.system.base64_token)
        self.assertNotEqual(headers["Authorization"], self.connection_saved_cipher)
        self.assertEqual(headers["Future"], "retain")
        self.assertEqual(
            self.resources["connection_a"]["spec"]["conn_info"]["headers"]["Authorization"],
            self.connection_saved_cipher,
        )
        self.confirm_connection()
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.RUNNING)
        self.assertEqual(len([r for r in self.requests if r[0] == "PUT"]), 2)

    def test_source_running_does_not_hide_pending_or_failed_connection_update(self):
        self.system.callback_url = "https://other.test"
        self.system.save(update_fields=["callback_url"])
        self.configure()
        tasks.start_snapshot.run()
        for phase, expected in (("Pending", SnapshotRunningStatus.PREPARING), ("Failed", SnapshotRunningStatus.FAILED)):
            with self.subTest(phase=phase):
                self.resources["connection_a"]["status"]["phase"] = phase
                tasks.start_snapshot.run()
                self.snapshot.refresh_from_db()
                self.assertEqual(self.snapshot.status, expected)
                if phase == "Failed":
                    self.assertIn("DataConn", self.snapshot.status_msg)
        self.assertEqual(len([r for r in self.requests if r[0] == "PUT"]), 1)

    def test_preserves_existing_pagination_path_spelling_and_data_path(self):
        self.resources["source_a"]["spec"]["report_config"]["pagination"]["total_path"] = ".data.count"
        self.resources["source_a"]["spec"]["report_config"]["data_path"] = ".data.results"
        Snapshot.objects.filter(pk=self.snapshot.pk).update(pull_config={"limit": 30})
        self.configure()
        tasks.start_snapshot.run()
        writes = [r for r in self.requests if r[0] == "PUT"]
        self.assertEqual(len(writes), 1)
        report = writes[0][3]["spec"]["report_config"]
        self.assertEqual(report["pagination"]["total_path"], ".data.count")
        self.assertEqual(report["data_path"], ".data.results")

    def test_encoded_target_change_is_rejected_without_normalizing_url(self):
        self.resource_type.path = "/resources%2Fv2"
        self.resource_type.save(update_fields=["path"])
        self.configure()
        self.assertNotIn("source_replay", self.snapshot.bkbase_v4_resources)
        self.assertFalse(any(r[0] != "GET" for r in self.requests))

    def test_existing_encoded_target_is_preserved_when_only_period_changes(self):
        self.resource_type.path = "/resources%2Fv2"
        self.resource_type.save(update_fields=["path"])
        self.resources["source_a"]["spec"]["report_config"]["path"] = "/resources%2Fv2"
        Snapshot.objects.filter(pk=self.snapshot.pk).update(pull_config={"period": 3})
        self.configure()
        tasks.start_snapshot.run()
        writes = [r for r in self.requests if r[0] == "PUT"]
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0][3]["spec"]["report_config"]["path"], "/resources%2Fv2")

    def test_lost_configuration_response_does_not_accept_old_running_as_new_config(self):
        Snapshot.objects.filter(pk=self.snapshot.pk).update(pull_config={"period": 3})
        self.configure()
        self.put_timeout = True
        tasks.start_snapshot.run()
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        operation = self.snapshot.bkbase_v4_resources["source_replay"]
        self.assertIsNone(operation["accepted"])
        self.assertTrue(operation["outcome_unknown"])
        self.assertFalse(operation["config_observed"])
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)
        self.configure()
        tasks.start_snapshot.run()
        self.assertEqual(len([r for r in self.requests if r[0] == "PUT"]), 1)

    def test_lost_response_with_observed_new_config_keeps_acceptance_unknown(self):
        Snapshot.objects.filter(pk=self.snapshot.pk).update(pull_config={"period": 3})
        self.configure()
        self.put_timeout = True
        self.timeout_applies = True
        tasks.start_snapshot.run()
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        operation = self.snapshot.bkbase_v4_resources["source_replay"]
        self.assertIsNone(operation["accepted"])
        self.assertTrue(operation["outcome_unknown"])
        self.assertTrue(operation["config_observed"])
        self.assertIsNone(operation["data_completed"])
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.RUNNING)
        self.configure()
        self.assertEqual(len([r for r in self.requests if r[0] == "PUT"]), 1)

    def test_full_pull_body_is_updated_with_documented_variables(self):
        Snapshot.objects.filter(pk=self.snapshot.pk).update(pull_type=JoinDataPullType.FULL)
        self.configure()
        tasks.start_snapshot.run()
        report = [r for r in self.requests if r[0] == "PUT"][0][3]["spec"]["report_config"]
        self.assertIn('"start_time": 0', report["body"])
        self.assertIn('<end>', report["body"])
        self.assertIn('<offset>', report["body"])
        self.assertIn('<limit>', report["body"])
        self.assertEqual(report["period"], 1440)

    def test_local_configuration_change_before_write_cancels_old_operation(self):
        Snapshot.objects.filter(pk=self.snapshot.pk).update(pull_config={"period": 3})
        self.configure()
        self.read_hook = lambda: Snapshot.objects.filter(pk=self.snapshot.pk).update(pull_config={"period": 4})
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.pull_config, {"period": 4})
        self.assertFalse(any(r[0] != "GET" for r in self.requests))

    def test_new_operation_during_observation_is_not_overwritten(self):
        self.configure()

        def replace_operation():
            value = Snapshot.objects.get(pk=self.snapshot.pk)
            value.bkbase_v4_resources["source_replay"]["operation_id"] = "new_operation"
            value.save(update_fields=["bkbase_v4_resources"])

        self.read_hook = replace_operation
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.bkbase_v4_resources["source_replay"]["operation_id"], "new_operation")
        self.assertFalse(any(r[0] != "GET" for r in self.requests))

    def test_connection_drift_after_queue_prevents_source_write(self):
        self.configure()
        self.resources["connection_a"]["spec"]["future"] = "concurrent_change"
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertFalse(any(r[0] != "GET" for r in self.requests))
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.FAILED)

    def test_unknown_downstream_retains_ingestion_but_does_not_queue_configuration(self):
        self.resources["doris_task"]["status"]["phase"] = "Pending"
        self.configure()
        self.assertEqual(self.snapshot.bkbase_v4_resources, self.expected)
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.RUNNING)
        self.assertFalse(any(r[0] != "GET" for r in self.requests))

    def test_running_downstream_with_empty_message_can_queue_without_writes(self):
        self.resources["doris_task"]["status"]["message"] = ""
        self.configure()
        self.assertTrue(self.snapshot.bkbase_v4_resources["source_replay"]["active"])
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)
        self.assertFalse(any(r[0] != "GET" for r in self.requests))

    def test_active_operation_is_not_replaced_by_manual_update(self):
        self.configure()
        original = deepcopy(self.snapshot.bkbase_v4_resources)
        calls = len(self.requests)
        self.configure()
        self.assertEqual(self.snapshot.bkbase_v4_resources, original)
        self.assertEqual(len(self.requests), calls)

    def test_unqueued_unknown_operation_is_rejected_by_real_handler_and_task(self):
        binding = {"source_replay": {"active": False, "outcome_unknown": True, "operation_id": "old_unknown"}}
        Snapshot.objects.filter(pk=self.snapshot.pk).update(
            bkbase_v4_resources=binding, status_msg="previous request outcome unknown"
        )
        self.snapshot.refresh_from_db()
        with self.assertRaises(BKBaseResourceMappingError):
            HttpPullHandler(self.system, self.resource_type, self.snapshot, JoinDataType.ASSET).update_or_create()
        self.configure()
        self.assertEqual(self.snapshot.bkbase_v4_resources, binding)
        self.assertEqual(self.snapshot.status_msg, "previous request outcome unknown")
        self.assertEqual(self.requests, [])

    def test_stop_intent_is_not_overridden(self):
        Snapshot.objects.filter(pk=self.snapshot.pk).update(bkbase_v4_resources={"pending_action": "stop"})
        self.configure()
        self.assertEqual(self.snapshot.bkbase_v4_resources, {"pending_action": "stop"})
        self.assertEqual(self.requests, [])

    def test_old_rejection_cannot_replace_later_configuration_feedback(self):
        self.system.auth_token = "changed_synthetic_token"
        self.system.save(update_fields=["auth_token"])
        self.read_hook = lambda: Snapshot.objects.filter(pk=self.snapshot.pk).update(
            pull_config={"period": 7}, status_msg="later configuration"
        )
        self.configure()
        self.assertEqual(self.snapshot.pull_config, {"period": 7})
        self.assertEqual(self.snapshot.status_msg, "later configuration")
        self.assertEqual(self.snapshot.bkbase_v4_resources, {})
        self.assertFalse(any(r[0] != "GET" for r in self.requests))

    def test_unused_legacy_delay_does_not_block_source_update_or_enter_v4_payload(self):
        Snapshot.objects.filter(pk=self.snapshot.pk).update(pull_config={"delay": 5, "period": 3})
        self.configure()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)
        tasks.start_snapshot.run()
        writes = [r for r in self.requests if r[0] == "PUT"]
        self.assertEqual(len(writes), 1)
        spec = writes[0][3]["spec"]
        self.assertEqual(spec["report_config"]["period"], 3)
        self.assertNotIn("delay", spec)
        self.assertNotIn("delay", spec["report_config"])
        self.assertNotIn("delay", spec["report_config"]["increment_field"])
        self.assertNotIn("delay", spec["report_config"]["body"])

    def test_running_basic_enters_source_only_manual_maintenance(self):
        Snapshot.objects.filter(pk=self.snapshot.pk).update(join_data_type=JoinDataType.BASIC)
        self.configure()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)
        self.assertEqual(self.snapshot.bkbase_v4_resources["source_replay"]["mode"], "configure")
        self.assertEqual(self.snapshot.bkbase_v4_resources["clean_role"], "owner")
        self.assertFalse(any(request[0] != "GET" for request in self.requests))

    @override_settings(BKBASE_V4_TENANT="other_tenant")
    def test_other_tenant_is_rejected_before_discovery(self):
        self.configure()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.RUNNING)
        self.assertEqual(self.requests, [])

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_system_refresh_retains_bulk_preparing_behavior(self):
        self.configure()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)
        self.assertEqual(self.snapshot.bkbase_v4_resources, {})
        self.assertEqual(self.requests, [])

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_handler_does_not_leak_snapshot_keyword_to_sdk(self):
        self.snapshot.pull_config = {"delay": 7}
        self.snapshot.save(update_fields=["pull_config"])
        with mock.patch.object(source.api.bk_base, "update_deploy_plan", return_value={}) as legacy:
            self.assertEqual(
                HttpPullHandler(self.system, self.resource_type, self.snapshot, JoinDataType.ASSET).update_or_create(),
                11,
            )
        self.assertNotIn("snapshot", legacy.call_args.kwargs)
        self.assertEqual(
            legacy.call_args.kwargs["access_conf_info"]["resource"]["scope"][0]["body"]["time"]["delay"],
            {"unit": "minute", "value": 7},
        )
