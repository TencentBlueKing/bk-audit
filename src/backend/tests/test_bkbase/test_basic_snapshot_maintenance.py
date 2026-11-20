"""已有Basic的真实手工与周期消费者Source-only维护。

仅模拟外部HTTP、队列和锁；两个入口从旧ID发现正式资源，不预塞完整绑定。
保留显式Clean角色、共享RT配置及实例真实存储集合。
"""
import datetime
from copy import deepcopy
from unittest import mock

from django.core.exceptions import ObjectDoesNotExist
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.meta.resources import UpdateSystem
from services.web.databus import tasks
from services.web.databus.collector.resources import SnapshotStatusResource
from services.web.databus.constants import (
    JoinDataPullType,
    JoinDataType,
    SnapshotRunningStatus,
)
from services.web.databus.models import Snapshot, SnapshotStorage
from tests.test_bkbase import test_snapshot_binding_ingestion as binding_fixture
from tests.test_bkbase import test_snapshot_configuration as configuration_fixture


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
class BasicSnapshotMaintenanceTests(TestCase):
    ref = binding_fixture.SnapshotBindingIngestionTests.ref
    remote = binding_fixture.SnapshotBindingIngestionTests.remote
    transport = configuration_fixture.SnapshotConfigurationTests.transport

    def setUp(self):
        binding_fixture.SnapshotBindingIngestionTests.setUp(self)
        self.snapshot.join_data_type = JoinDataType.BASIC
        self.snapshot.save(update_fields=["join_data_type"])
        self.snapshot.storages.all().delete()
        SnapshotStorage.objects.create(
            snapshot=self.snapshot, storage_type="redis", status=SnapshotRunningStatus.RUNNING
        )
        self.expected["storages"] = {"redis": self.ref("DataStorage", "redis_task")}
        self.resources["redis_task"] = self.remote(
            "DataStorage",
            "redis_task",
            {
                "tableInfo": {
                    "source": self.expected["result_table"],
                    "storage": self.ref("Redis", "redis_cluster", "infra"),
                }
            },
            labels={"result_table_id": "11_logical_rt"},
        )
        self.resources["redis_task"]["status"]["message"] = "running"
        self.lists["datastorages"] = ["redis_task"]
        self.resources["source_a"]["spec"]["custom_future"] = {"retained": 1}
        self.resources["source_a"]["spec"]["report_config"]["data_path"] = ".data.results"
        self.put_timeout = False
        self.timeout_applies = False
        self.enterContext(
            mock.patch.object(tasks.BasicJoinHandler, "start", side_effect=AssertionError("old Basic start"))
        )
        self.enterContext(mock.patch.object(tasks.AssetHandler, "start", side_effect=AssertionError("old Asset start")))

    def set_role(self, role):
        self.resources["clean_a"]["spec"]["result_table_source"] = role
        self.expected["clean_role"] = {"new": "owner", "existing": "existing"}.get(role)

    def configure(self):
        with mock.patch.object(
            tasks.refresh_system_snapshots,
            "delay",
            side_effect=lambda **params: tasks.refresh_system_snapshots.run(**params),
        ):
            self.system.update_join_data()
        self.snapshot.refresh_from_db()

    def schedule(self):
        Snapshot.objects.filter(pk=self.snapshot.pk).update(updated_at=timezone.now() - datetime.timedelta(days=20))
        tasks.refresh_snapshot.run()
        self.snapshot.refresh_from_db()

    def writes(self):
        return [request for request in self.requests if request[0] != "GET"]

    def assert_binding(self):
        self.snapshot.refresh_from_db()
        for key, value in self.expected.items():
            self.assertEqual(self.snapshot.bkbase_v4_resources.get(key), value)
        paths = [request[1] for request in self.requests]
        for fragment in ("/datasources/", "/cleans/", "/datastorages/", "/actual_rt/", "/data_a/"):
            self.assertTrue(any(fragment in path for path in paths), fragment)

    def test_manual_system_consumer_discovers_new_role_without_prefilled_refs(self):
        self.assertEqual(self.snapshot.bkbase_v4_resources, {})
        before = deepcopy({key: value for key, value in self.resources.items() if key != "source_a"})
        Snapshot.objects.filter(pk=self.snapshot.pk).update(pull_config={"period": 3, "limit": 30})
        self.configure()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)
        self.assert_binding()
        self.assertEqual(self.snapshot.bkbase_v4_resources["source_replay"]["mode"], "configure")
        self.assertEqual(self.writes(), [])
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertTrue(self.snapshot.bkbase_v4_resources["source_replay"]["accepted"])
        report = self.writes()[0][3]["spec"]["report_config"]
        self.assertEqual(report["period"], 3)
        self.assertEqual(report["pagination"]["limit"], 30)
        self.assertEqual(report["history_data"]["start_time"], "0")
        self.assertEqual(report["data_path"], ".data.results")
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.RUNNING)
        self.assertEqual(len(self.writes()), 1)
        self.assertEqual(before, {key: value for key, value in self.resources.items() if key != "source_a"})

    def test_periodic_consumer_discovers_existing_role_and_only_updates_source(self):
        self.set_role("existing")
        self.assertEqual(self.snapshot.bkbase_v4_resources, {})
        downstream = deepcopy({key: value for key, value in self.resources.items() if key != "source_a"})
        self.schedule()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)
        self.assert_binding()
        self.assertEqual(set(self.snapshot.bkbase_v4_resources["storages"]), {"redis"})
        tasks.start_snapshot.run()
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.RUNNING)
        self.assertIsNone(self.snapshot.bkbase_v4_resources["source_replay"]["data_completed"])
        self.assertEqual(len(self.writes()), 1)
        self.assertEqual(downstream, {key: value for key, value in self.resources.items() if key != "source_a"})

    def test_manual_existing_role_and_periodic_new_role_are_both_supported(self):
        self.set_role("existing")
        self.configure()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)
        self.assert_binding()
        tasks.start_snapshot.run()
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.RUNNING)
        self.set_role("new")
        Snapshot.objects.filter(pk=self.snapshot.pk).update(bkbase_v4_resources={})
        self.schedule()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)
        self.assert_binding()

    def test_missing_or_unknown_clean_role_is_rejected_before_ingestion(self):
        for role in (None, "unknown"):
            with self.subTest(role=role):
                if role is None:
                    self.resources["clean_a"]["spec"].pop("result_table_source", None)
                else:
                    self.set_role(role)
                self.configure()
                self.assertEqual(self.snapshot.bkbase_v4_resources, {})
                self.assertEqual(self.snapshot.status, SnapshotRunningStatus.RUNNING)
                self.assertIn("未应用", self.snapshot.status_msg or "")
                self.assertEqual(self.writes(), [])

    def test_wrong_clean_input_does_not_save_or_write_any_resource(self):
        self.resources["clean_a"]["spec"]["data_id"] = self.ref("DataId", "other_data")
        self.schedule()
        self.assertEqual(self.snapshot.bkbase_v4_resources, {})
        self.assertEqual(self.writes(), [])
        self.assertTrue(any("/cleans/" in request[1] for request in self.requests))

    def test_unknown_configuration_receipt_is_observed_without_repeat_write(self):
        self.set_role("existing")
        Snapshot.objects.filter(pk=self.snapshot.pk).update(pull_config={"period": 4})
        self.configure()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)
        self.put_timeout = True
        tasks.start_snapshot.run()
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        operation = self.snapshot.bkbase_v4_resources["source_replay"]
        self.assertTrue(operation["outcome_unknown"])
        self.assertFalse(operation["config_observed"])
        self.configure()
        tasks.start_snapshot.run()
        self.assertEqual(len(self.writes()), 1)

    def test_old_processing_id_change_cancels_queued_maintenance_before_put(self):
        self.configure()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)
        Snapshot.objects.filter(pk=self.snapshot.pk).update(bkbase_processing_id="newer_processing")
        tasks.start_snapshot.run()
        self.assertEqual(self.writes(), [])

    def test_prefilled_binding_cannot_default_missing_actual_clean_role(self):
        self.snapshot.bkbase_v4_resources = deepcopy(self.expected)
        self.snapshot.save(update_fields=["bkbase_v4_resources"])
        self.resources["clean_a"]["spec"].pop("result_table_source")
        self.configure()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.RUNNING)
        self.assertEqual(self.writes(), [])
        self.assertNotIn("source_replay", self.snapshot.bkbase_v4_resources)
        self.assertTrue(any("/clean_a/" in request[1] for request in self.requests))

    def test_update_system_request_reaches_basic_source_maintenance(self):
        self.set_role("existing")
        with mock.patch.object(
            tasks.refresh_system_snapshots,
            "delay",
            side_effect=lambda **params: tasks.refresh_system_snapshots.run(**params),
        ):
            UpdateSystem().request(
                {
                    "system_id": self.system.system_id,
                    "namespace": self.system.namespace,
                    "callback_url": "https://source.test/v2",
                }
            )
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)
        self.assert_binding()
        tasks.start_snapshot.run()
        self.assertEqual(self.writes()[0][3]["spec"]["report_config"]["path"], "/v2/resources")

    def test_basic_callback_path_keeps_marked_ciphertext_on_existing_connection(self):
        self.set_role("existing")
        connection = self.resources["connection_a"]
        connection["spec"]["conn_info"]["headers"]["Authorization"] = "opaque_cipher"
        connection["metadata"].setdefault("annotations", {})["conn_info_encrypted"] = "true"
        baseline = deepcopy(connection)
        with mock.patch.object(
            tasks.refresh_system_snapshots,
            "delay",
            side_effect=lambda **params: tasks.refresh_system_snapshots.run(**params),
        ):
            UpdateSystem().request(
                system_id=self.system.system_id,
                namespace=self.system.namespace,
                callback_url="https://source.test/v2",
            )
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING, self.snapshot.status_msg)
        tasks.start_snapshot.run()
        tasks.start_snapshot.run()
        [(method, url, _, payload)] = self.writes()
        self.assertEqual(method, "PUT")
        self.assertIn("/datasources/", url)
        self.assertEqual(payload["spec"]["report_config"]["path"], "/v2/resources")
        self.assertEqual(connection, baseline)

    def test_basic_callback_path_rejects_unmarked_mismatched_authorization(self):
        self.resources["connection_a"]["spec"]["conn_info"]["headers"]["Authorization"] = "unmarked_opaque"
        self.system.callback_url = "https://source.test/v2"
        self.system.save(update_fields=["callback_url"])
        self.configure()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.RUNNING)
        self.assertNotIn("source_replay", self.snapshot.bkbase_v4_resources)
        self.assertEqual(self.writes(), [])

    def test_required_storage_set_is_instance_specific_not_asset_defaults(self):
        SnapshotStorage.objects.create(
            snapshot=self.snapshot, storage_type="doris", status=SnapshotRunningStatus.RUNNING
        )
        self.lists["datastorages"].append("doris_task")
        self.expected["storages"]["doris"] = self.ref("DataStorage", "doris_task")
        self.schedule()
        self.assert_binding()
        self.assertEqual(set(self.snapshot.bkbase_v4_resources["storages"]), {"redis", "doris"})
        tasks.start_snapshot.run()
        self.assertEqual(len(self.writes()), 1)

    def test_multiple_source_or_same_type_storage_candidates_are_rejected(self):
        for resource_name, collection, duplicate in (
            ("source_a", "datasources", "other_source"),
            ("redis_task", "datastorages", "other_redis"),
        ):
            with self.subTest(collection=collection):
                self.resources[duplicate] = deepcopy(self.resources[resource_name])
                self.resources[duplicate]["metadata"]["name"] = duplicate
                self.lists[collection].append(duplicate)
                self.configure()
                self.assertEqual(self.snapshot.bkbase_v4_resources, {})
                self.assertIn("未应用", self.snapshot.status_msg or "")
                self.assertEqual(self.writes(), [])
                self.lists[collection].remove(duplicate)

    def test_wrong_tenant_rt_reference_or_logical_label_is_rejected(self):
        original = deepcopy(self.resources)
        mutations = (
            lambda: self.resources["source_a"]["metadata"].update(tenant="other_tenant"),
            lambda: self.resources["redis_task"]["spec"]["tableInfo"].update(
                source=self.ref("ResultTable", "wrong_rt")
            ),
            lambda: self.resources["actual_rt"]["metadata"]["labels"].update(result_table_id="different_logical"),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self.resources = deepcopy(original)
                mutate()
                self.configure()
                self.assertEqual(self.snapshot.bkbase_v4_resources, {})
                self.assertEqual(self.writes(), [])

    def test_cross_storage_rt_disagreement_is_rejected(self):
        SnapshotStorage.objects.create(
            snapshot=self.snapshot, storage_type="doris", status=SnapshotRunningStatus.RUNNING
        )
        self.lists["datastorages"].append("doris_task")
        self.resources["doris_task"]["spec"]["tableInfo"]["source"] = self.ref("ResultTable", "other_rt")
        self.configure()
        self.assertEqual(self.snapshot.bkbase_v4_resources, {})
        self.assertEqual(self.writes(), [])

    def test_auth_or_base_url_change_is_c17_and_never_writes_connection(self):
        self.system.auth_token = "new_synthetic_token"
        self.system.save(update_fields=["auth_token"])
        self.configure()
        self.assert_binding()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.RUNNING)
        self.assertIn("DataConn", self.snapshot.status_msg)
        visible = SnapshotStatusResource().request(system_id=self.system.system_id, resource_type_ids="asset")
        self.assertEqual(visible["asset"]["status_msg"], self.snapshot.status_msg)
        self.assertEqual(self.writes(), [])
        self.system.callback_url = "https://different.test"
        self.system.save(update_fields=["callback_url"])
        self.configure()
        self.assertEqual(self.writes(), [])

    def test_ok_storage_with_empty_message_allows_existing_source_maintenance(self):
        self.resources["redis_task"]["status"].pop("message")
        self.configure()
        self.assert_binding()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)
        self.assertEqual(self.snapshot.bkbase_v4_resources["source_replay"]["mode"], "configure")
        self.assertEqual(self.writes(), [])

    def test_config_drift_during_discovery_cannot_persist_stale_binding(self):
        self.read_hook = lambda: Snapshot.objects.filter(pk=self.snapshot.pk).update(pull_config={"limit": 29})
        self.configure()
        self.assertEqual(self.snapshot.bkbase_v4_resources, {})
        self.assertEqual(self.writes(), [])

    def test_queued_raw_id_or_logical_id_change_prevents_put(self):
        self.configure()
        Snapshot.objects.filter(pk=self.snapshot.pk).update(bkbase_data_id=12, bkbase_table_id="new_logical")
        tasks.start_snapshot.run()
        self.assertEqual(self.writes(), [])

    def test_full_pull_uses_instance_body_without_clean_rule_conversion(self):
        Snapshot.objects.filter(pk=self.snapshot.pk).update(pull_type=JoinDataPullType.FULL, pull_config={"period": 5})
        self.configure()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)
        tasks.start_snapshot.run()
        report = self.writes()[0][3]["spec"]["report_config"]
        self.assertIn('"start_time": 0', report["body"])
        self.assertNotIn("<start>", report["body"])
        self.assertIn("<end>", report["body"])
        self.assertEqual(report["period"], 5)

    def test_known_shared_source_is_not_inferred_safe_from_shared_rt_role(self):
        Snapshot.objects.create(
            system_id="other_local_system",
            resource_type_id="other_type",
            join_data_type=JoinDataType.BASIC,
            status=SnapshotRunningStatus.RUNNING,
            bkbase_data_id=11,
        )
        self.set_role("existing")
        self.configure()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.RUNNING)
        self.assertNotIn("source_replay", self.snapshot.bkbase_v4_resources)
        self.assertIn("shared", self.snapshot.status_msg)
        self.assertEqual(self.writes(), [])

    def test_failed_or_closed_snapshot_is_not_recovered_by_maintenance(self):
        for status in (SnapshotRunningStatus.FAILED, SnapshotRunningStatus.CLOSED):
            with self.subTest(status=status):
                Snapshot.objects.filter(pk=self.snapshot.pk).update(status=status)
                self.configure()
                self.schedule()
                self.assertEqual(self.snapshot.status, status)
                self.assertEqual(self.snapshot.bkbase_v4_resources, {})
                self.assertEqual(self.writes(), [])

    def test_prefilled_basic_rechecks_actual_data_id_identity(self):
        self.snapshot.bkbase_v4_resources = deepcopy(self.expected)
        self.snapshot.save(update_fields=["bkbase_v4_resources"])
        self.resources["data_a"]["metadata"]["tenant"] = "other_tenant"
        self.configure()
        self.assertNotIn("source_replay", self.snapshot.bkbase_v4_resources)
        self.assertEqual(self.writes(), [])

    def test_prefilled_legacy_anchor_cannot_be_whitespace(self):
        self.snapshot.bkbase_processing_id = " "
        self.snapshot.bkbase_v4_resources = deepcopy(self.expected)
        self.snapshot.save(update_fields=["bkbase_processing_id", "bkbase_v4_resources"])
        self.resources["clean_a"]["metadata"]["labels"]["processing_id"] = " "
        self.configure()
        self.assertNotIn("source_replay", self.snapshot.bkbase_v4_resources)
        self.assertEqual(self.writes(), [])

    def test_basic_does_not_default_missing_clean_desired_state_to_running(self):
        self.resources["clean_a"]["spec"].pop("desired_status")
        self.configure()
        self.assert_binding()
        self.assertNotIn("source_replay", self.snapshot.bkbase_v4_resources)
        self.assertEqual(self.writes(), [])

    def test_prefilled_basic_cannot_escape_configured_source_project(self):
        self.snapshot.bkbase_v4_resources = deepcopy(self.expected)
        self.snapshot.bkbase_v4_resources["data_source"]["namespace"] = "unverified_project"
        self.snapshot.save(update_fields=["bkbase_v4_resources"])
        self.resources["source_a"]["metadata"]["namespace"] = "unverified_project"
        self.configure()
        self.assertNotIn("source_replay", self.snapshot.bkbase_v4_resources)
        self.assertEqual(self.requests, [])

    def test_one_basic_missing_local_configuration_does_not_abort_periodic_batch(self):
        orphan = Snapshot.objects.create(
            system_id="missing_system",
            resource_type_id="missing_type",
            join_data_type=JoinDataType.BASIC,
            status=SnapshotRunningStatus.RUNNING,
            bkbase_data_id=22,
        )
        Snapshot.objects.filter(pk=orphan.pk).update(updated_at=timezone.now() - datetime.timedelta(days=30))
        try:
            self.schedule()
        except ObjectDoesNotExist as error:
            self.fail(f"单个Basic配置缺失不应中断后续实际快照消费者: {error}")
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)
        self.assert_binding()
        orphan.refresh_from_db()
        self.assertEqual(orphan.status, SnapshotRunningStatus.RUNNING)
        self.assertEqual(orphan.bkbase_v4_resources, {})
        self.assertEqual(self.writes(), [])

    def test_complete_storage_binding_still_checks_logical_labels_and_annotations(self):
        original = deepcopy(self.resources["redis_task"]["metadata"])
        for labels, annotations in (
            ({"result_table_id": "other_logical"}, {}),
            ({}, {}),
            ({"result_table_id": "11_logical_rt"}, {"result_table_id": "conflicting_logical"}),
        ):
            with self.subTest(labels=labels, annotations=annotations):
                Snapshot.objects.filter(pk=self.snapshot.pk).update(
                    status=SnapshotRunningStatus.RUNNING, status_msg=None, bkbase_v4_resources=deepcopy(self.expected)
                )
                self.resources["redis_task"]["metadata"] = {
                    **deepcopy(original),
                    "labels": labels,
                    "annotations": annotations,
                }
                self.configure()
                self.assertNotIn("source_replay", self.snapshot.bkbase_v4_resources)
                self.assertIn("未应用", self.snapshot.status_msg or "")
                self.assertEqual(self.writes(), [])

    def test_storage_logical_label_drift_after_discovery_prevents_source_put(self):
        self.set_role("existing")
        self.configure()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)
        self.assert_binding()
        self.resources["redis_task"]["metadata"]["labels"]["result_table_id"] = "changed_after_ingestion"
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.writes(), [])
        self.assertFalse(self.snapshot.bkbase_v4_resources["source_replay"]["attempted"])
