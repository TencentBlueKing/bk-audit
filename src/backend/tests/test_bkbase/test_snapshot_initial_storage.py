"""实际 Toggle→后台 tick 验证首次快照入库、Source 激活及失败重入。"""
import json
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

import requests
from bk_resource import api
from django.conf import settings
from django.db import connection
from django.test import TransactionTestCase, override_settings

from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from services.web.bkbase.constants import BKBASE_V4_STORAGE_CLUSTER_MAP
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus import tasks
from services.web.databus.collector.resources import ToggleJoinDataResource
from services.web.databus.constants import (
    DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
    SnapshotRunningStatus,
)
from services.web.databus.models import CollectorConfig
from services.web.databus.storage.handler.redis import RedisHandler
from tests.test_bkbase.test_snapshot_clean_provision import (
    SnapshotCleanProvisionFixture,
)


@override_settings(
    BKBASE_API_VERSION="v4",
    BKBASE_V4_TENANT="default",
    BKBASE_V4_NAMESPACE="project_a",
    HIGH_RISK_PORTS=[],
    ASSET_RT_STORAGE_CLUSTER="legacy_hdfs",
    ASSET_RT_EXPIRE_TIME="7d",
)
class SnapshotInitialStorageTests(SnapshotCleanProvisionFixture, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.timeout_storage = False
        self.persist_lost_storage = False
        self.on_storage_post = None
        self.on_source_put = None
        self.timeout_source = False
        self.enterContext(
            mock.patch.object(RedisHandler, "pick_redis", return_value=SimpleNamespace(redis_name_en="legacy_redis"))
        )
        for key, value in (
            (
                BKBASE_V4_STORAGE_CLUSTER_MAP,
                {
                    kind: {legacy: self.ref(cluster, kind + "_cluster")}
                    for kind, legacy, cluster in (
                        ("hdfs", "legacy_hdfs", "Hdfs"),
                        ("doris", "legacy_doris", "Doris"),
                        ("redis", "legacy_redis", "Redis"),
                    )
                },
            ),
            (DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY, {"bkbase_cluster_id": "legacy_doris"}),
        ):
            GlobalMetaConfig.set(key, value, config_level=ConfigLevelChoices.NAMESPACE.value, instance_key="audit")
        # Asset Handler 既有副写配置从默认命名空间取值。
        GlobalMetaConfig.set(
            DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
            {"bkbase_cluster_id": "legacy_doris"},
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key=settings.DEFAULT_NAMESPACE,
        )

    @staticmethod
    def ref(kind, name):
        return {"kind": kind, "tenant": "default", "namespace": "project_a", "name": name}

    def transport(self, method, url, **kwargs):
        if (method == "POST" and "/datastorages/" in url) or method == "PUT":
            self.assertFalse(connection.in_atomic_block)
            payload = deepcopy(kwargs["json"])
            self.requests.append((method, url, payload))
            kind = "DataStorage" if "/datastorages/" in url else "DataSource" if "/datasources/" in url else "Clean"
            value = self.remote(payload["metadata"], kind, payload["spec"], phase="Pending")
            name = value["metadata"]["name"]
            if kind == "DataStorage":
                if self.on_storage_post:
                    self.on_storage_post()
                if self.timeout_storage and not self.persist_lost_storage:
                    raise requests.Timeout("synthetic storage response lost")
            if kind == "DataSource":
                if self.on_source_put:
                    self.on_source_put()
                if self.timeout_source:
                    raise requests.Timeout("synthetic source response lost")
            self.resources[name] = value
            if kind == "DataStorage" and self.timeout_storage:
                raise requests.Timeout("synthetic storage response lost")
            response = requests.Response()
            response.status_code = 200
            response.url = url
            response.request = requests.Request(method, url).prepare()
            response._content = json.dumps({"result": True, "code": "00", "data": value}).encode()
            return response
        response = super().transport(method, url, **kwargs)
        if method == "GET" and "/v4/result_tables/" in url:
            value = response.json()["data"]
            value["kind"] = "ResultTable"
            value["status"]["phase"] = "Ok"
            self.resources[value["metadata"]["name"]] = value
        return response

    def ready_clean(self, *, join_data_type="asset"):
        self.start(join_data_type=join_data_type)
        tasks.start_snapshot.run()
        (post,) = self.clean_posts()
        value = self.resources[post["metadata"]["name"]]
        value["status"]["phase"] = "Ok"
        value["spec"]["current_status"] = "Running"
        tasks.start_snapshot.run()
        self.assertEqual(self.snapshot().status, SnapshotRunningStatus.PREPARING, self.snapshot().status_msg)
        self.assertEqual(self.snapshot().bkbase_table_id, post["spec"]["result_table_id"])

    def storage_posts(self):
        return [
            (url, payload) for method, url, payload in self.requests if method == "POST" and "/datastorages/" in url
        ]

    def source_puts(self):
        return [payload for method, url, payload in self.requests if method == "PUT" and "/datasources/" in url]

    def reconcile_storages(self):
        for value in self.resources.values():
            if value["kind"] == "DataStorage":
                value["status"]["phase"] = "Ok"

    def tick(self, count=1):
        for _ in range(count):
            tasks.start_snapshot.run()

    def test_asset_waits_for_every_storage_get_then_starts_source_preserving_first_window(self):
        self.ready_clean()
        ref = self.snapshot().bkbase_v4_resources["data_source"]
        before = deepcopy(self.resources[ref["name"]]["spec"]["report_config"])
        self.tick(5)
        self.assertEqual(len(self.storage_posts()), 2)
        self.assertFalse(self.source_puts())
        self.assertEqual(self.snapshot().status, SnapshotRunningStatus.PREPARING, self.snapshot().status_msg)
        self.reconcile_storages()
        self.tick(8)
        (put,) = self.source_puts()
        self.assertEqual(put["spec"]["report_config"], before)
        self.assertEqual(self.snapshot().status, SnapshotRunningStatus.PREPARING)
        self.resources[ref["name"]]["status"]["phase"] = "Ok"
        self.resources[ref["name"]]["spec"].update(current_status="Running", desired_status="Running")
        self.tick(2)
        self.assertEqual(self.snapshot().status, SnapshotRunningStatus.RUNNING, self.snapshot().status_msg)
        self.assertEqual(
            set(self.snapshot().storages.values_list("status", flat=True)), {SnapshotRunningStatus.RUNNING}
        )
        self.assertEqual(len(self.clean_posts()), 1)
        self.assertEqual(
            len(self.source_puts()),
            1,
            (self.snapshot().status_msg, self.snapshot().bkbase_v4_resources.get("source_provision", {}).get("stage")),
        )

    def test_unknown_storage_post_is_observed_without_repost_or_source_activation(self):
        self.ready_clean()
        self.timeout_storage = True
        self.tick(4)
        self.assertEqual(len(self.storage_posts()), 1)
        self.assertFalse(self.source_puts())
        self.assertEqual(self.snapshot().status, SnapshotRunningStatus.PREPARING, self.snapshot().status_msg)

    def test_lost_storage_receipt_can_converge_from_exact_get(self):
        self.ready_clean(join_data_type="basic")
        self.timeout_storage = self.persist_lost_storage = True
        self.tick()
        self.timeout_storage = False
        self.reconcile_storages()
        self.tick(6)
        self.assertEqual(len(self.storage_posts()), 1)
        self.assertEqual(
            len(self.source_puts()),
            1,
            (self.snapshot().status_msg, self.snapshot().bkbase_v4_resources.get("source_provision", {}).get("stage")),
        )

    def test_configuration_drift_after_storage_post_prevents_source_activation(self):
        self.ready_clean()
        self.tick()
        snapshot = self.snapshot()
        snapshot.custom_config = {"changed": True}
        snapshot.save(update_fields=["custom_config"])
        self.reconcile_storages()
        self.tick(3)
        self.assertFalse(self.source_puts())
        self.assertEqual(self.snapshot().status, SnapshotRunningStatus.FAILED)

    def test_source_receipt_is_not_running_and_unknown_put_is_not_repeated(self):
        self.ready_clean(join_data_type="basic")
        self.tick()
        self.reconcile_storages()
        self.timeout_source = True
        self.tick(8)
        self.assertEqual(
            len(self.source_puts()),
            1,
            (self.snapshot().status_msg, self.snapshot().bkbase_v4_resources.get("source_provision", {}).get("stage")),
        )
        self.assertEqual(self.snapshot().status, SnapshotRunningStatus.PREPARING, self.snapshot().status_msg)

    def test_explicit_retry_of_timed_out_initial_storage_only_observes_previous_claim(self):
        self.ready_clean(join_data_type="basic")
        self.timeout_storage = True
        self.tick()
        with mock.patch("services.web.bkbase.snapshot_clean_provision.BKBASE_V4_MAX_POLLS", 2):
            self.tick(3)
        self.assertEqual(self.snapshot().status, SnapshotRunningStatus.FAILED)
        result = ToggleJoinDataResource().request(
            {
                "system_id": self.system.system_id,
                "resource_type_id": self.resource_type.resource_type_id,
                "is_enabled": True,
            }
        )
        self.assertEqual(result["status"], SnapshotRunningStatus.PREPARING)
        self.tick(2)
        self.assertEqual(len(self.storage_posts()), 1)
        self.assertFalse(self.source_puts())

    def enable_again(self):
        return ToggleJoinDataResource().request(
            {
                "system_id": self.system.system_id,
                "resource_type_id": self.resource_type.resource_type_id,
                "is_enabled": True,
            }
        )

    def run_basic_source(self):
        self.ready_clean(join_data_type="basic")
        self.tick()
        self.reconcile_storages()
        self.tick(5)
        self.assertEqual(len(self.source_puts()), 1, self.snapshot().status_msg)
        ref = self.snapshot().bkbase_v4_resources["data_source"]
        self.resources[ref["name"]]["status"]["phase"] = "Ok"
        self.resources[ref["name"]]["spec"].update(current_status="Running", desired_status="Running")
        return ref

    def add_collector(self):
        binding = {
            "clean": self.ref("Clean", "collector_clean"),
            "clean_role": "existing",
            "data_id": self.ref("DataId", "collector_input"),
            "source_raw_data_id": 81,
            "result_table": self.ref("ResultTable", "collector_rt"),
            "clean_ready": True,
            "result_table_id": "81_collector_rt",
        }
        collector = CollectorConfig.objects.create(
            system_id=self.system.system_id,
            collector_config_name_en="snapshot_join",
            bk_biz_id=1,
            bk_data_id=81,
            collector_config_id=1,
            collector_plugin_id=1,
            bkbase_v4_resources=binding,
        )
        self.resources["collector_rt"] = self.remote(
            self.ref("ResultTable", "collector_rt"),
            "ResultTable",
            {
                "predefiendResultTableId": "81_collector_rt",
                "fields": [
                    {"field_name": "snapshot_instance_data"},
                    {"field_name": "snapshot_instance_name"},
                ],
            },
        )
        self.resources["collector_clean"] = self.remote(
            self.ref("Clean", "collector_clean"),
            "Clean",
            {
                "raw_data_id": 81,
                "data_id": binding["data_id"],
                "result_table_id": "81_collector_rt",
                "result_table_source": "existing",
                "desired_status": "Running",
                "current_status": "Running",
                "config_revision": 42,
                "deploy_revision": 42,
                "rules": [],
                "join": [],
            },
        )
        return collector

    def test_basic_waits_for_actual_collector_clean_get_before_committing_link(self):
        collector = self.add_collector()
        self.run_basic_source()
        self.tick(3)
        collector.refresh_from_db()
        self.assertIsNone(collector.join_data_rt)
        self.assertEqual(self.snapshot().status, SnapshotRunningStatus.PREPARING, self.snapshot().status_msg)
        writes = [payload for method, url, payload in self.requests if method == "PUT" and "/cleans/" in url]
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0]["spec"]["join"][-1]["result_table_id"], self.snapshot().bkbase_table_id)
        # 写回包 Pending 且延迟完成，不能用运行中的旧配置提前提交本地关联。
        self.tick(2)
        collector.refresh_from_db()
        self.assertIsNone(collector.join_data_rt)
        self.resources["collector_clean"]["status"]["phase"] = "Ok"
        self.tick(2)
        collector.refresh_from_db()
        self.assertEqual(collector.join_data_rt, self.snapshot().bkbase_table_id)
        self.assertEqual(self.snapshot().status, SnapshotRunningStatus.RUNNING, self.snapshot().status_msg)
        self.assertTrue(self.snapshot().bkbase_v4_resources["source_provision"]["completed"])
        self.assertEqual(len(self.source_puts()), 1)

    def test_failed_storage_explicit_retry_updates_only_that_claim_and_waits_for_new_get(self):
        self.ready_clean(join_data_type="basic")
        self.tick()
        name = self.storage_posts()[0][1]["metadata"]["name"]
        self.resources[name]["status"]["phase"] = "Failed"
        self.tick()
        self.assertEqual(self.snapshot().status, SnapshotRunningStatus.FAILED)
        self.assertEqual(self.enable_again()["status"], SnapshotRunningStatus.PREPARING)
        self.tick()
        updates = [payload for method, url, payload in self.requests if method == "PUT" and "/datastorages/" in url]
        self.assertEqual(len(updates), 1)
        self.assertFalse(self.source_puts())
        self.tick()  # 独立观察新 Pending，随后才可接受当前代次 Ok。
        self.resources[name]["status"]["phase"] = "Ok"
        self.tick(5)
        self.assertEqual(len(self.storage_posts()), 1)
        self.assertEqual(len(self.source_puts()), 1, self.snapshot().status_msg)

    def test_stale_storage_response_does_not_restore_any_local_binding(self):
        self.ready_clean(join_data_type="basic")
        snapshot = self.snapshot()

        def supersede():
            current = self.snapshot()
            current.bkbase_v4_resources["source_provision"]["operation_id"] = "new_generation"
            current.save(update_fields=["bkbase_v4_resources"])

        self.on_storage_post = supersede
        self.tick()
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.bkbase_v4_resources["source_provision"]["operation_id"], "new_generation")
        self.assertFalse(snapshot.bkbase_v4_resources.get("storages"))
        self.assertIsNone(snapshot.bkbase_v4_resources["source_provision"]["storage_steps"]["redis"]["accepted"])
        self.assertFalse(self.source_puts())

    def test_reentrant_tick_during_storage_post_never_repeats_create(self):
        self.ready_clean(join_data_type="basic")
        self.on_storage_post = lambda: self.tick()
        self.tick()
        self.assertEqual(len(self.storage_posts()), 1)
        self.reconcile_storages()
        self.on_storage_post = None
        self.tick(5)
        self.assertEqual(len(self.storage_posts()), 1)
        self.assertEqual(len(self.source_puts()), 1, self.snapshot().status_msg)

    def test_storage_remote_target_conflict_never_activates_source(self):
        self.ready_clean(join_data_type="basic")
        self.tick()
        name = self.storage_posts()[0][1]["metadata"]["name"]
        self.resources[name]["spec"]["tableInfo"]["source"]["name"] = "unrelated_rt"
        self.reconcile_storages()
        self.tick(3)
        self.assertEqual(self.snapshot().status, SnapshotRunningStatus.FAILED)
        self.assertFalse(self.source_puts())
        self.assertEqual(len(self.storage_posts()), 1)

    def test_failed_initial_source_is_retried_by_explicit_enable_without_history_replay(self):
        self.ready_clean(join_data_type="basic")
        self.tick()
        self.reconcile_storages()
        self.tick(5)
        ref = self.snapshot().bkbase_v4_resources["data_source"]
        value = self.resources[ref["name"]]
        original_report = deepcopy(value["spec"]["report_config"])
        value["status"]["phase"] = "Failed"
        self.tick()
        self.assertEqual(self.snapshot().status, SnapshotRunningStatus.FAILED)
        self.assertEqual(self.enable_again()["status"], SnapshotRunningStatus.PREPARING)
        self.tick()
        self.assertEqual(len(self.source_puts()), 2)
        self.assertEqual(self.source_puts()[-1]["spec"]["report_config"], original_report)
        self.tick()
        value = self.resources[ref["name"]]
        value["status"]["phase"] = "Ok"
        value["spec"].update(current_status="Running", desired_status="Running")
        self.tick(2)
        self.assertEqual(self.snapshot().status, SnapshotRunningStatus.RUNNING, self.snapshot().status_msg)

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_toggle_and_tick_keep_the_existing_source_clean_storage_chain(self):
        with mock.patch.object(
            api.bk_base, "create_deploy_plan", return_value={"raw_data_id": 71}
        ) as source_post, mock.patch.object(
            api.bk_base,
            "databus_cleans_post",
            return_value={"result_table_id": "71_legacy_snapshot", "processing_id": "legacy_clean"},
        ) as clean_post, mock.patch.object(
            api.bk_base, "databus_storages_post", return_value={}
        ) as storage_post, mock.patch(
            "services.web.databus.collector.snapshot.join.etl_storage.start_bkbase_clean"
        ):
            result = ToggleJoinDataResource().request(
                {
                    "system_id": self.system.system_id,
                    "resource_type_id": self.resource_type.resource_type_id,
                    "is_enabled": True,
                    "join_data_type": "basic",
                    "storage_type": ["redis"],
                }
            )
            self.assertEqual(result["status"], SnapshotRunningStatus.PREPARING)
            self.tick()
        snapshot = self.snapshot()
        self.assertEqual(snapshot.status, SnapshotRunningStatus.RUNNING, snapshot.status_msg)
        self.assertEqual(snapshot.bkbase_data_id, 71)
        self.assertEqual(snapshot.bkbase_table_id, "71_legacy_snapshot")
        self.assertFalse(snapshot.bkbase_v4_resources)
        source_post.assert_called_once()
        clean_post.assert_called_once()
        storage_post.assert_called_once()
        self.assertFalse(self.requests)

    def test_unknown_initial_source_can_be_explicitly_observed_after_timeout_without_second_put(self):
        self.ready_clean(join_data_type="basic")
        self.tick()
        self.reconcile_storages()
        self.timeout_source = True
        self.tick(5)
        with mock.patch("services.web.bkbase.snapshot_restore.BKBASE_V4_MAX_POLLS", 1):
            self.tick()
        self.assertEqual(self.snapshot().status, SnapshotRunningStatus.FAILED)
        self.assertEqual(self.enable_again()["status"], SnapshotRunningStatus.PREPARING)
        self.tick(3)
        self.assertEqual(len(self.source_puts()), 1)
        self.assertTrue(self.snapshot().bkbase_v4_resources["source_replay"]["initial_start"])
        self.assertTrue(self.snapshot().bkbase_v4_resources["source_replay"]["outcome_unknown"])

    def test_stale_initial_source_callback_cannot_complete_a_new_provision_generation(self):
        self.ready_clean(join_data_type="basic")
        self.tick()
        self.reconcile_storages()

        def supersede():
            current = self.snapshot()
            current.bkbase_v4_resources["source_provision"]["operation_id"] = "superseding_initial_generation"
            current.save(update_fields=["bkbase_v4_resources"])

        self.on_source_put = supersede
        self.tick(5)
        ref = self.snapshot().bkbase_v4_resources["data_source"]
        self.resources[ref["name"]]["status"]["phase"] = "Ok"
        self.resources[ref["name"]]["spec"].update(current_status="Running", desired_status="Running")
        self.tick(2)
        binding = self.snapshot().bkbase_v4_resources
        self.assertEqual(binding["source_provision"]["operation_id"], "superseding_initial_generation")
        self.assertFalse(binding["source_provision"].get("completed"))
        self.assertIsNone(binding["source_replay"]["writes"]["data_source"]["accepted"])
        self.assertEqual(self.snapshot().status, SnapshotRunningStatus.PREPARING)

    def test_failed_initial_source_retry_rejects_changed_callback_configuration(self):
        self.ready_clean(join_data_type="basic")
        self.tick()
        self.reconcile_storages()
        self.tick(5)
        ref = self.snapshot().bkbase_v4_resources["data_source"]
        self.resources[ref["name"]]["status"]["phase"] = "Failed"
        self.tick()
        self.system.callback_url = "https://changed-source.test"
        self.system.save(update_fields=["callback_url"])
        before = len(self.requests)
        with self.assertRaises(BKBaseResourceMappingError):
            self.enable_again()
        self.assertEqual(len(self.requests), before)
        self.assertEqual(self.snapshot().status, SnapshotRunningStatus.FAILED)

    def test_malformed_storage_steps_fail_only_the_current_snapshot(self):
        self.ready_clean(join_data_type="basic")
        original = deepcopy(self.snapshot().bkbase_v4_resources)
        for malformed in (["redis"], {"redis": ["invalid"]}):
            with self.subTest(malformed=malformed):
                snapshot = self.snapshot()
                binding = deepcopy(original)
                binding["source_provision"]["storage_steps"] = malformed
                snapshot.bkbase_v4_resources = binding
                snapshot.status = SnapshotRunningStatus.PREPARING
                snapshot.save(update_fields=["bkbase_v4_resources", "status"])
                self.tick()
                self.assertEqual(self.snapshot().status, SnapshotRunningStatus.FAILED)
                self.assertFalse(self.storage_posts())
                self.assertFalse(self.source_puts())

    def test_toggle_rejects_malformed_provision_instead_of_failing_with_attribute_error(self):
        self.ready_clean(join_data_type="basic")
        snapshot = self.snapshot()
        snapshot.status = SnapshotRunningStatus.FAILED
        snapshot.bkbase_v4_resources["source_provision"] = ["invalid"]
        snapshot.save(update_fields=["status", "bkbase_v4_resources"])
        with self.assertRaises(BKBaseResourceMappingError):
            self.enable_again()
        self.assertFalse(self.storage_posts())
        self.assertFalse(self.source_puts())
