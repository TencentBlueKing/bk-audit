"""本轮五项当前正式协议及实际消费者的回归；外部IO在边界替换。"""
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from api.bk_base_v4.default import DatasetDetail, DatasetList
from apps.exceptions import SnapshotPreparingException
from apps.meta.models import ResourceType, System
from services.web.bkbase import flow, metadata, source, storage
from services.web.bkbase.constants import BKBASE_V4_MAX_POLLS
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.collector.resources import ToggleJoinDataResource
from services.web.databus.collector.snapshot.join.base import AssetHandler
from services.web.databus.collector.snapshot.join.etl_storage import (
    AssetEtlStorageHandler,
    JoinDataEtlStorageHandler,
)
from services.web.databus.constants import JoinDataType, SnapshotRunningStatus
from services.web.databus.models import Snapshot, SnapshotStorage


class DocumentedStorageTests(SimpleTestCase):
    def test_primary_update_removes_stale_ordinary_indexes(self):
        prior = {
            "tableInfo": {"data_model": "primary_table", "expire": 7},
            "taskFieldSetting": {"key_fields": ["id", "resource_type_id", "system_id"], "index_fields": ["id"]},
            "retained": True,
        }
        result = storage._merge_spec(prior, {"tableInfo": {"data_model": "primary_table", "expire": 14}})
        self.assertNotIn("index_fields", result["taskFieldSetting"])
        self.assertEqual(result["taskFieldSetting"]["key_fields"], ["id", "resource_type_id", "system_id"])
        self.assertEqual(result["tableInfo"]["expire"], 14)
        self.assertTrue(result["retained"])
        self.assertEqual(prior["taskFieldSetting"]["index_fields"], ["id"])

    @override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit")
    def test_asset_storage_consumer_reaches_v4_service_with_owner_and_three_keys(self):
        owner = SimpleNamespace(
            namespace="audit",
            bkbase_v4_resources={
                "result_table": {"kind": "ResultTable", "tenant": "tenant_a", "namespace": "audit", "name": "asset_rt"}
            },
        )
        handler = AssetEtlStorageHandler(
            11,
            SimpleNamespace(system_id="system_a"),
            SimpleNamespace(resource_type_id="asset"),
            "doris",
            snapshot=owner,
        )
        cluster = {"kind": "Doris", "tenant": "tenant_a", "namespace": "clusters", "name": "doris_a"}
        sent = []

        def create(**payload):
            sent.append(deepcopy(payload))
            return {"metadata": payload["metadata"], "spec": payload["spec"], "status": {"phase": "Pending"}}

        with mock.patch.object(
            JoinDataEtlStorageHandler,
            "storage_config",
            new_callable=mock.PropertyMock,
            return_value={"fields": [], "storage_type": "doris", "storage_cluster": 1},
        ), mock.patch.object(
            storage.GlobalMetaConfig, "get", return_value={"doris": {"1": cluster}}
        ), mock.patch.object(
            storage, "resource_lock"
        ), mock.patch.object(
            storage, "get_resource_or_none", return_value=None
        ), mock.patch.object(
            storage, "update_owner_binding", side_effect=lambda target, patch: target.bkbase_v4_resources.update(patch)
        ), mock.patch.object(
            storage.api.bk_base_v4, "data_storage_create", side_effect=create
        ):
            observed = handler.create_storage()
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]["spec"]["tableInfo"]["data_model"], "primary_table")
        self.assertEqual(sent[0]["spec"]["taskFieldSetting"], {"key_fields": ["id", "resource_type_id", "system_id"]})
        self.assertEqual(sent[0]["spec"]["tableInfo"]["storage"], cluster)
        self.assertIsNone(sent[0]["status"])
        self.assertIsNone(observed["task_state"])
        self.assertIn("doris", owner.bkbase_v4_resources["storages"])
        self.assertNotIn("main", owner.bkbase_v4_resources["storages"])

    def test_plugin_model_stays_snake_case_and_primary_keeps_partition_and_keys(self):
        self.assertEqual(
            storage.convert_storage_config({"config": {"data_model": "duplicate_table"}})["tableInfo"],
            {"data_model": "duplicate_table"},
        )
        params = {
            "config": {"data_model": "primary_table", "unique_partition_table": True},
            "key_fields": ["id", "resource_type_id", "system_id"],
            "index_fields": [{"index": 0, "physical_field": "id"}],
            "fields": [{"field_name": "id", "is_key": True, "is_index": True}],
        }
        before = deepcopy(params)
        result = storage.convert_storage_config(params)
        self.assertEqual(result["tableInfo"], {"data_model": "primary_table", "unique_partition_table": True})
        self.assertEqual(result["taskFieldSetting"], {"key_fields": ["id", "resource_type_id", "system_id"]})
        self.assertEqual(params, before)

    @override_settings(BKBASE_API_VERSION="v4")
    def test_actual_asset_config_uses_three_keys_without_ordinary_indexes(self):
        handler = AssetEtlStorageHandler(
            11, SimpleNamespace(system_id="system_a"), SimpleNamespace(resource_type_id="asset"), "doris"
        )
        with mock.patch.object(
            JoinDataEtlStorageHandler, "storage_config", new_callable=mock.PropertyMock, return_value={"fields": []}
        ):
            params = handler.storage_config
        result = storage.convert_storage_config(params)
        self.assertEqual(result["tableInfo"]["data_model"], "primary_table")
        self.assertEqual(result["taskFieldSetting"]["key_fields"], ["id", "resource_type_id", "system_id"])
        self.assertNotIn("index_fields", result["taskFieldSetting"])

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_asset_index_descriptors_remain_unchanged(self):
        handler = AssetEtlStorageHandler(
            11, SimpleNamespace(system_id="system_a"), SimpleNamespace(resource_type_id="asset"), "doris"
        )
        with mock.patch.object(
            JoinDataEtlStorageHandler, "storage_config", new_callable=mock.PropertyMock, return_value={"fields": []}
        ):
            params = handler.storage_config
        self.assertEqual(
            params["index_fields"],
            [
                {"index": 0, "physical_field": "id"},
                {"index": 0, "physical_field": "resource_type_id"},
                {"index": 0, "physical_field": "system_id"},
            ],
        )

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_asset_storage_keeps_legacy_sdk_call(self):
        handler = AssetEtlStorageHandler(
            11, SimpleNamespace(system_id="system_a"), SimpleNamespace(resource_type_id="asset"), "doris"
        )
        with mock.patch.object(
            JoinDataEtlStorageHandler, "storage_config", new_callable=mock.PropertyMock, return_value={"fields": []}
        ), mock.patch.object(storage.api.bk_base, "databus_storages_post", return_value={}) as legacy:
            handler.create_storage()
        self.assertEqual(
            legacy.call_args.kwargs["index_fields"],
            [
                {"index": 0, "physical_field": "id"},
                {"index": 0, "physical_field": "resource_type_id"},
                {"index": 0, "physical_field": "system_id"},
            ],
        )


@override_settings(BKBASE_API_VERSION="v4")
class DatasetContractTests(SimpleTestCase):
    def test_three_levels_project_without_fabricating_members(self):
        context = {"version": "v4", "tenant": "tenant_a", "rt_namespaces": {"11_rt": "source_project"}}
        for level in ("public", "private", "confidential"):
            with self.subTest(level=level), mock.patch.object(
                metadata.api.bk_base_v4, "dataset_detail", return_value={"sensitivity": level}
            ) as api:
                self.assertEqual(metadata.get_rt_sensitivity(context, "11_rt"), {"level": level})
                self.assertEqual(
                    api.call_args.kwargs, {"tenant": "tenant_a", "namespace": "source_project", "dataset_name": "11_rt"}
                )

    def test_missing_unknown_or_object_level_is_not_assumed_private(self):
        context = {"version": "v4", "tenant": "tenant_a", "rt_namespaces": {"11_rt": "source_project"}}
        for value in (None, "", "unknown", {"level": "private"}):
            with self.subTest(value=value), mock.patch.object(
                metadata.api.bk_base_v4, "dataset_detail", return_value={"sensitivity": value}
            ):
                with self.assertRaises(BKBaseResourceMappingError):
                    metadata.get_rt_sensitivity(context, "11_rt")

    def test_missing_trusted_tenant_refuses_before_api(self):
        with mock.patch.object(metadata.api.bk_base_v4, "dataset_detail") as api:
            with self.assertRaises(BKBaseResourceMappingError):
                metadata.get_rt_sensitivity({"rt_namespaces": {"11_rt": "source_project"}}, "11_rt")
        api.assert_not_called()

    def test_detail_and_list_put_validated_tenant_in_header_only(self):
        for cls, params in (
            (DatasetDetail, {"tenant": "tenant_a", "namespace": "source_project", "dataset_name": "11_rt"}),
            (DatasetList, {"tenant": "tenant_a", "namespace": "source_project"}),
        ):
            resource = cls()
            response = mock.Mock(status_code=200)
            response.json.return_value = {"result": True, "code": "00", "data": {"sensitivity": "private"}}
            response.raise_for_status.return_value = None
            with mock.patch(
                "bk_resource.contrib.bk_api.BkApiResource.build_header", return_value={"auth": "synthetic"}
            ), mock.patch.object(resource.session, "request", return_value=response) as http:
                resource.request({**params, "headers": {"X-Bk-Tenant-Id": "untrusted_tenant"}})
            sent = http.call_args.kwargs
            self.assertEqual(sent["headers"], {"auth": "synthetic", "X-Bk-Tenant-Id": "tenant_a"})
            self.assertNotIn("tenant", sent["params"])
            self.assertNotIn("headers", sent["params"])


class HdfsConfigTests(SimpleTestCase):
    def test_default_and_legacy_explicit_profiles_use_data_type_contract(self):
        ref = {"kind": "Hdfs", "tenant": "tenant_a", "namespace": "clusters", "name": "hdfs_a"}
        strategy = SimpleNamespace(namespace="audit", strategy_id=1)
        for profile, other in (
            ({}, {"dataType": "parquet"}),
            (
                {"hdfs_storage_config": {"other": {"data_type": "parquet", "retained": 1}}},
                {"dataType": "parquet", "retained": 1},
            ),
        ):
            before = deepcopy(profile)
            with mock.patch.object(flow.storage_service, "resolve_storage_cluster", return_value=ref):
                result = flow._storage_node(
                    {"tenant": "tenant_a"},
                    strategy,
                    {"node_type": "hdfs_storage", "cluster": 1, "expires": "7d"},
                    profile,
                )
            self.assertEqual(result["storage_config"]["other"], other)
            self.assertEqual(result["storage"], ref)
            self.assertEqual(profile, before)


@override_settings(BKBASE_API_VERSION="v4")
class RawDataIdTests(SimpleTestCase):
    def resource(self, value):
        return {
            "kind": "DataSource",
            "metadata": {
                "tenant": "tenant_a",
                "namespace": "audit",
                "name": "source",
                "labels": {"raw_data_id": value},
            },
            "spec": {"basic_info": {"bk_biz_id": 11, "data_source_name": "source"}},
        }

    def test_unready_and_illegal_ids_are_not_projected(self):
        for value in (None, "", "bad", "-1", "0", "1.1", " 11 ", True, [], "１２"):
            with self.subTest(value=value), self.assertRaises(BKBaseResourceMappingError):
                source._legacy_source(self.resource(value))
        self.assertEqual(source._legacy_source(self.resource("11"))["id"], 11)

    def test_personal_list_skips_unready_or_illegal_items_and_counts_valid_rows(self):
        rows = [self.resource(x) for x in (None, "", "bad", "11", "12")]
        with mock.patch.object(source, "get_bkbase_context", return_value={"tenant": "tenant_a"}), mock.patch.object(
            source, "list_user_sources", return_value=rows
        ):
            result = source.get_my_rawdata_list(page=2, page_size=1)
        self.assertEqual(result["count"], 2)
        self.assertEqual([x["id"] for x in result["results"]], [12])

    def test_plugin_lookup_skips_unready_named_siblings(self):
        rows = [self.resource(x) for x in ("", "bad", "11")]
        with mock.patch.object(
            source, "get_bkbase_context", return_value={"tenant": "tenant_a", "namespace": "audit"}
        ), mock.patch.object(source.api.bk_base_v4, "data_source_list", return_value=rows):
            result = source.get_rawdata_list(raw_data_name__icontains="source")
        self.assertEqual([x["id"] for x in result], [11])


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit")
class SnapshotStopEntryTests(TestCase):
    def setUp(self):
        System.objects.create(system_id="stop_system", namespace="audit")
        ResourceType.objects.create(system_id="stop_system", resource_type_id="asset", unique_id="stop_system:asset")

    def test_no_storage_does_not_silently_close_source_without_stop(self):
        snapshot = Snapshot.objects.create(
            system_id="stop_system",
            resource_type_id="asset",
            status=SnapshotRunningStatus.RUNNING,
            bkbase_data_id=11,
            join_data_type=JoinDataType.ASSET,
        )
        ref = {"kind": "DataSource", "tenant": "tenant_a", "namespace": "audit", "name": "source_a"}
        snapshot.bkbase_v4_resources = {"data_source": ref}
        snapshot.save(update_fields=["bkbase_v4_resources"])
        with mock.patch.object(
            source, "stop_source", return_value={"ref": ref, "task_state": None, "accepted": True, "message": ""}
        ) as stop:
            response = ToggleJoinDataResource().request(
                {"system_id": "stop_system", "resource_type_id": "asset", "is_enabled": False}
            )
        self.assertEqual(stop.call_count, 1)
        self.assertEqual(response["status"], SnapshotRunningStatus.RUNNING)
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.bkbase_v4_resources["pending_action"], "stop")

    def test_multiple_storages_issue_only_one_source_stop(self):
        snapshot = Snapshot.objects.create(
            system_id="stop_system",
            resource_type_id="asset",
            status=SnapshotRunningStatus.RUNNING,
            bkbase_data_id=11,
            join_data_type=JoinDataType.ASSET,
        )
        for kind in ("doris", "hdfs"):
            SnapshotStorage.objects.create(snapshot=snapshot, storage_type=kind)
        ref = {"kind": "DataSource", "tenant": "tenant_a", "namespace": "audit", "name": "source_a"}
        snapshot.bkbase_v4_resources = {"data_source": ref}
        snapshot.save(update_fields=["bkbase_v4_resources"])
        with mock.patch.object(
            source,
            "stop_source",
            return_value={"ref": ref, "task_state": "stopped", "accepted": True, "message": ""},
        ) as stop:
            response = ToggleJoinDataResource().request(
                {"system_id": "stop_system", "resource_type_id": "asset", "is_enabled": False}
            )
        self.assertEqual(stop.call_count, 1)
        self.assertEqual(response["status"], SnapshotRunningStatus.CLOSED)

    def test_known_failed_stop_marks_failed_without_pending_poll(self):
        snapshot = Snapshot.objects.create(
            system_id="stop_system", resource_type_id="asset", status=SnapshotRunningStatus.RUNNING, bkbase_data_id=11
        )
        ref = {"kind": "DataSource", "tenant": "tenant_a", "namespace": "audit", "name": "source_a"}
        snapshot.bkbase_v4_resources = {"data_source": ref}
        snapshot.save(update_fields=["bkbase_v4_resources"])
        with mock.patch.object(
            source,
            "stop_source",
            return_value={"ref": ref, "task_state": "failed", "accepted": True, "message": "source failed"},
        ):
            self.assertFalse(source.stop_snapshot(snapshot, {"bkbase_data_id": 11}))
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.status, SnapshotRunningStatus.FAILED)
        self.assertEqual(snapshot.status_msg, "source failed")
        self.assertIsNone(snapshot.bkbase_v4_resources["pending_action"])

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_stop_retains_legacy_per_storage_calls(self):
        snapshot = Snapshot.objects.create(
            system_id="stop_system",
            resource_type_id="asset",
            status=SnapshotRunningStatus.RUNNING,
            bkbase_data_id=11,
            join_data_type=JoinDataType.ASSET,
        )
        for kind in ("doris", "hdfs"):
            SnapshotStorage.objects.create(snapshot=snapshot, storage_type=kind)
        with mock.patch.object(source.api.bk_base, "stop_collector", return_value={}) as legacy:
            response = ToggleJoinDataResource().request(
                {"system_id": "stop_system", "resource_type_id": "asset", "is_enabled": False}
            )
        self.assertEqual(legacy.call_count, 2)
        self.assertEqual(response["status"], SnapshotRunningStatus.CLOSED)


@override_settings(BKBASE_API_VERSION="v4")
class SnapshotStorageConsumerReviewTests(TestCase):
    def setUp(self):
        System.objects.create(system_id="storage_review", namespace="audit")
        ResourceType.objects.create(
            system_id="storage_review", resource_type_id="asset", unique_id="storage_review:asset"
        )
        self.snapshot = Snapshot.objects.create(
            system_id="storage_review",
            resource_type_id="asset",
            bkbase_data_id=11,
            status=SnapshotRunningStatus.PREPARING,
        )
        self.local_storage = SnapshotStorage.objects.create(snapshot=self.snapshot, storage_type="doris")
        self.handler = AssetHandler("storage_review", "asset", "doris")
        self.enterContext(mock.patch.object(self.handler, "create_data_id"))
        self.enterContext(mock.patch.object(self.handler, "create_data_etl"))
        self.link = self.enterContext(mock.patch.object(self.handler, "update_log_clean_link"))
        self.enterContext(mock.patch("services.web.databus.collector.snapshot.join.base.ErrorMsgHandler.send"))
        self.enterContext(
            mock.patch.object(
                AssetEtlStorageHandler,
                "storage_config",
                new_callable=mock.PropertyMock,
                return_value={"config": {"data_model": "primary_table"}},
            )
        )

    def run_start(self, state, *, multiple_storage=False):
        result = {
            "accepted": True,
            "task_state": state,
            "resource_phase": "Pending" if state is None else "Ok",
            "message": "storage failed" if state == "failed" else "",
        }
        with mock.patch.object(storage, "configure_storage", return_value=result):
            started = self.handler.start(multiple_storage=multiple_storage)
        self.snapshot.refresh_from_db()
        self.local_storage.refresh_from_db()
        return started

    def test_pending_doris_blocks_real_start_and_link_update(self):
        self.assertFalse(self.run_start(None))
        self.assertEqual(self.local_storage.status, SnapshotRunningStatus.PREPARING)
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)
        self.link.assert_not_called()

    def test_local_running_flag_does_not_replace_v4_task_observation(self):
        self.local_storage.status = SnapshotRunningStatus.RUNNING
        self.local_storage.save(update_fields=["status"])
        self.assertFalse(self.run_start(None, multiple_storage=True))
        self.assertEqual(self.local_storage.status, SnapshotRunningStatus.PREPARING)
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)
        self.link.assert_not_called()

    def test_failed_doris_marks_storage_and_snapshot_failed(self):
        self.assertFalse(self.run_start("failed"))
        self.assertEqual(self.local_storage.status, SnapshotRunningStatus.FAILED)
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.FAILED)
        self.assertIn("storage failed", self.snapshot.status_msg)
        self.link.assert_not_called()

    def test_explicit_running_allows_real_start(self):
        self.assertTrue(self.run_start("running"))
        self.assertEqual(self.local_storage.status, SnapshotRunningStatus.RUNNING)
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.RUNNING)
        self.link.assert_called_once()

    def test_direct_create_data_storage_reports_pending(self):
        with mock.patch.object(storage, "configure_storage", return_value={"task_state": None, "accepted": True}):
            self.assertFalse(self.handler.create_data_storage())
        self.local_storage.refresh_from_db()
        self.assertEqual(self.local_storage.status, SnapshotRunningStatus.PREPARING)

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_none_return_keeps_original_synchronous_start(self):
        with mock.patch.object(storage.api.bk_base, "databus_storages_post", return_value=None) as legacy:
            self.assertTrue(self.handler.start())
        self.local_storage.refresh_from_db()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.local_storage.status, SnapshotRunningStatus.RUNNING)
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.RUNNING)
        legacy.assert_called_once()


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit")
class PendingStopEnableReviewTests(TestCase):
    def setUp(self):
        System.objects.create(system_id="stop_review", namespace="audit")
        ResourceType.objects.create(system_id="stop_review", resource_type_id="asset", unique_id="stop_review:asset")
        self.ref = {"kind": "DataSource", "tenant": "tenant_a", "namespace": "audit", "name": "review_source"}
        self.params = {"system_id": "stop_review", "resource_type_id": "asset"}
        self.snapshot = Snapshot.objects.create(**self.params, status=SnapshotRunningStatus.RUNNING, bkbase_data_id=11)
        self.snapshot.bkbase_v4_resources = {"data_source": self.ref}
        self.snapshot.save(update_fields=["bkbase_v4_resources"])
        with mock.patch.object(
            source,
            "stop_source",
            return_value={"ref": self.ref, "task_state": None, "accepted": True, "message": ""},
        ):
            ToggleJoinDataResource().request({**self.params, "is_enabled": False})

    def test_enable_refuses_pending_stop_before_precheck_or_local_write(self):
        before = Snapshot.objects.filter(pk=self.snapshot.pk).values().get()
        with mock.patch.object(ToggleJoinDataResource, "pre_check", return_value=None) as precheck:
            with self.assertRaises(SnapshotPreparingException):
                ToggleJoinDataResource().request({**self.params, "is_enabled": True})
        self.assertEqual(Snapshot.objects.filter(pk=self.snapshot.pk).values().get(), before)
        self.assertFalse(self.snapshot.storages.exists())
        precheck.assert_not_called()

    def test_poll_terminal_state_and_stop_marker_are_saved_together(self):
        observed = {"spec": {"desired_status": "Stopped", "current_status": "Stopped"}, "status": {"phase": "Ok"}}
        real_save = Snapshot.save
        changes = []

        def capture(instance, *args, **kwargs):
            if instance.pk == self.snapshot.pk and "bkbase_v4_resources" in kwargs.get("update_fields", []):
                changes.append(set(kwargs["update_fields"]))
            return real_save(instance, *args, **kwargs)

        with mock.patch.object(
            source, "get_bkbase_context", return_value={"tenant": "tenant_a", "namespace": "audit"}
        ), mock.patch.object(source.api.bk_base_v4, "data_source_get", return_value=observed), mock.patch.object(
            Snapshot, "save", capture
        ):
            source.poll_source_operations()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.CLOSED)
        self.assertIsNone(self.snapshot.bkbase_v4_resources["pending_action"])
        self.assertTrue(any({"status", "bkbase_v4_resources"}.issubset(fields) for fields in changes))
        with mock.patch.object(ToggleJoinDataResource, "pre_check") as precheck:
            with self.assertRaises(BKBaseResourceMappingError):
                ToggleJoinDataResource().request({**self.params, "is_enabled": True})
        precheck.assert_not_called()

    def test_stopped_failed_and_timeout_clear_marker_but_restore_requires_bindings(self):
        for phase, state, count, expected in (
            ("Ok", "Stopped", 0, SnapshotRunningStatus.CLOSED),
            ("Failed", "Running", 0, SnapshotRunningStatus.FAILED),
            ("Pending", "Running", BKBASE_V4_MAX_POLLS - 1, SnapshotRunningStatus.FAILED),
        ):
            with self.subTest(phase=phase):
                Snapshot.objects.filter(pk=self.snapshot.pk).update(
                    status=SnapshotRunningStatus.RUNNING,
                    bkbase_v4_resources={"data_source": self.ref, "pending_action": "stop", "source_poll_count": count},
                )
                with mock.patch.object(ToggleJoinDataResource, "pre_check", return_value=None):
                    with self.assertRaises(SnapshotPreparingException):
                        ToggleJoinDataResource().request({**self.params, "is_enabled": True})
                observed = {
                    "spec": {"desired_status": "Stopped", "current_status": state},
                    "status": {"phase": phase, "message": "observed"},
                }
                with mock.patch.object(
                    source, "get_bkbase_context", return_value={"tenant": "tenant_a", "namespace": "audit"}
                ), mock.patch.object(source.api.bk_base_v4, "data_source_get", return_value=observed):
                    source.poll_source_operations()
                self.snapshot.refresh_from_db()
                self.assertEqual(self.snapshot.status, expected)
                self.assertIsNone(self.snapshot.bkbase_v4_resources["pending_action"])
                with mock.patch.object(ToggleJoinDataResource, "pre_check") as precheck:
                    with self.assertRaises(BKBaseResourceMappingError):
                        ToggleJoinDataResource().request({**self.params, "is_enabled": True})
                precheck.assert_not_called()
                self.snapshot.refresh_from_db()
                self.assertEqual(self.snapshot.status, expected)

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_does_not_apply_v4_pending_stop_guard(self):
        with mock.patch.object(ToggleJoinDataResource, "pre_check", return_value=None):
            response = ToggleJoinDataResource().request({**self.params, "is_enabled": True})
        self.assertEqual(response["status"], SnapshotRunningStatus.PREPARING)
