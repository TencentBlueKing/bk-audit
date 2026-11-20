"""真实资产 Handler 到 V4 HDFS SDK 的调用方和就绪边界。"""
import json
from copy import deepcopy
from unittest import mock

import requests
from bk_resource import api, resource
from bk_resource.exceptions import APIRequestError
from django.db import connection
from django.test import TestCase, override_settings

from api.bk_base_v4.default import BkBaseV4Resource
from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig, ResourceType, System
from services.web.bkbase import storage
from services.web.bkbase.constants import BKBASE_V4_STORAGE_CLUSTER_MAP
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.collector.snapshot.join.base import AssetHandler
from services.web.databus.constants import JoinDataType, SnapshotRunningStatus
from services.web.databus.models import Snapshot, SnapshotStorage


@override_settings(
    BKBASE_API_VERSION="v4",
    BKBASE_V4_TENANT="default",
    BKBASE_V4_NAMESPACE="audit",
    ASSET_RT_STORAGE_CLUSTER="legacy_hdfs",
    ASSET_RT_EXPIRE_TIME="1d",
)
class AssetHdfsStorageTests(TestCase):
    def setUp(self):
        self.system = System.objects.create(
            system_id="hdfs_asset", namespace="audit", callback_url="https://source.invalid"
        )
        self.resource_type = ResourceType.objects.create(
            system_id=self.system.system_id, resource_type_id="asset", unique_id="hdfs_asset:asset"
        )
        self.rt_ref = self.ref("ResultTable", "asset_rt")
        self.cluster = self.ref("Hdfs", "hdfs_cluster")
        self.store_ref = self.ref("DataStorage", "hdfs_task")
        self.snapshot = Snapshot.objects.create(
            system_id=self.system.system_id,
            resource_type_id="asset",
            join_data_type=JoinDataType.ASSET,
            status=SnapshotRunningStatus.PREPARING,
            bkbase_data_id=11,
            bkbase_table_id="11_asset",
            bkbase_v4_resources={
                "data_source": self.ref("DataSource", "source"),
                "data_id": self.ref("DataId", "data"),
                "raw_data_id": 11,
                "source_raw_data_id": 11,
                "clean": self.ref("Clean", "clean"),
                "clean_role": "owner",
                "clean_ready": True,
                "result_table": self.rt_ref,
                "result_table_id": "11_asset",
                "storages": {"hdfs": self.store_ref},
            },
        )
        self.local_store = SnapshotStorage.objects.create(
            snapshot=self.snapshot, storage_type="hdfs", status=SnapshotRunningStatus.CLOSED
        )
        GlobalMetaConfig.set(
            BKBASE_V4_STORAGE_CLUSTER_MAP,
            {"hdfs": {"legacy_hdfs": self.cluster}},
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key="audit",
        )
        self.remote = None
        self.created_phase = "Pending"
        self.read_status = None
        self.requests = []
        self.atomic_depth = len(connection.atomic_blocks)
        self.enterContext(
            mock.patch.object(
                resource.meta,
                "resource_type_schema",
                return_value=[{"id": "extra", "type": "string", "description": "Synthetic", "is_index": True}],
            )
        )
        self.enterContext(mock.patch.object(storage, "resource_lock"))
        self.enterContext(mock.patch.object(BkBaseV4Resource, "build_header", return_value={}))
        self.enterContext(mock.patch("requests.sessions.Session.request", side_effect=self.transport))
        self.handler = AssetHandler(self.system.system_id, "asset", "hdfs")

    @staticmethod
    def ref(kind, name):
        return {"kind": kind, "tenant": "default", "namespace": "audit", "name": name}

    def transport(self, method, url, **kwargs):
        self.assertEqual(len(connection.atomic_blocks), self.atomic_depth, "HTTP inside an additional transaction")
        self.assertIn("/v4/tenants/default/namespaces/audit/datastorages/", url)
        name = url.rstrip("/").rsplit("/", 1)[-1]
        payload = deepcopy(kwargs.get("json"))
        self.requests.append((method.upper(), payload))
        status = 200
        if method.upper() == "GET":
            self.assertEqual(name, self.store_ref["name"])
            if self.read_status is not None:
                status, body = self.read_status, {"result": False, "code": "denied", "data": {}}
            elif self.remote is None:
                status, body = 404, {"result": False, "code": "1558025", "data": {}}
            else:
                body = {"result": True, "code": "00", "data": deepcopy(self.remote)}
        else:
            self.assertIn(method.upper(), ("POST", "PUT"))
            self.assertIsNone(payload["status"])
            self.remote = {
                "kind": "DataStorage",
                "metadata": deepcopy(payload["metadata"]),
                "spec": deepcopy(payload["spec"]),
                "status": {"phase": self.created_phase},
            }
            body = {"result": True, "code": "00", "data": deepcopy(self.remote)}
        response = requests.Response()
        response.status_code = status
        response.url = url
        response.request = requests.Request(method, url).prepare()
        response._content = json.dumps(body).encode()
        return response

    def writes(self):
        return [(method, body) for method, body in self.requests if method in ("POST", "PUT")]

    def expected_spec(self):
        return {
            "tableInfo": {"dimension_table": True, "expire": 1, "source": self.rt_ref, "storage": self.cluster},
            "taskFieldSetting": {
                "key_fields": ["id", "resource_type_id", "system_id"],
                "json_fields": [],
                "original_json_fields": [],
            },
        }

    def seed_ready(self):
        self.remote = {
            "kind": "DataStorage",
            "metadata": deepcopy(self.store_ref),
            "spec": self.expected_spec(),
            "status": {"phase": "Ok"},
        }

    def prepare_new_storage(self):
        """新建用例只有 RT 与集群绑定，不预填已存在的入库引用。"""
        self.snapshot.bkbase_v4_resources.pop("storages")
        self.snapshot.save(update_fields=["bkbase_v4_resources"])
        self.handler.snapshot.refresh_from_db()
        self.store_ref = storage.storage_ref(
            {"tenant": "default", "namespace": "audit"},
            self.snapshot,
            rt_ref=self.rt_ref,
            cluster_ref=self.cluster,
            purpose="hdfs",
        )

    def test_actual_handler_creates_hdfs_v4_and_waits_for_independent_get(self):
        self.prepare_new_storage()
        result = self.handler.create_data_storage()
        self.assertIs(result, False)
        self.local_store.refresh_from_db()
        self.assertEqual(self.local_store.status, SnapshotRunningStatus.PREPARING)
        [(method, payload)] = self.writes()
        self.assertEqual(method, "POST")
        self.assertEqual(payload["metadata"], {key: self.store_ref[key] for key in ("tenant", "namespace", "name")})
        self.assertEqual(payload["spec"], self.expected_spec())
        self.assertNotIn("index_fields", payload["spec"]["taskFieldSetting"])
        self.assertIs(self.handler.create_data_storage(), False)
        self.assertEqual(len(self.writes()), 1)
        self.remote["status"]["phase"] = "Ok"
        self.assertIs(self.handler.create_data_storage(), True)
        self.local_store.refresh_from_db()
        self.assertEqual(self.local_store.status, SnapshotRunningStatus.RUNNING)
        self.assertEqual(len(self.writes()), 1)
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)
        self.assertEqual(self.snapshot.bkbase_v4_resources["result_table"], self.rt_ref)

    def test_even_ok_create_receipt_is_not_local_running_before_get(self):
        self.prepare_new_storage()
        self.created_phase = "Ok"
        self.assertIs(self.handler.create_data_storage(), False)
        self.local_store.refresh_from_db()
        self.assertEqual(self.local_store.status, SnapshotRunningStatus.PREPARING)
        self.assertIs(self.handler.create_data_storage(), True)
        self.assertEqual(len(self.writes()), 1)

    def test_missing_established_hdfs_is_not_recreated(self):
        with self.assertRaisesRegex(BKBaseResourceMappingError, "established V4 DataStorage is missing"):
            self.handler.create_data_storage()
        self.assertEqual(self.writes(), [])
        self.local_store.refresh_from_db()
        self.assertEqual(self.local_store.status, SnapshotRunningStatus.FAILED)

    def test_existing_ready_hdfs_is_observed_without_writes(self):
        self.seed_ready()
        before = deepcopy(self.remote)
        self.assertIs(self.handler.create_data_storage(), True)
        self.assertEqual(self.writes(), [])
        self.assertEqual(self.remote, before)

    def test_existing_hdfs_update_preserves_unmanaged_values_and_waits(self):
        self.seed_ready()
        self.remote["spec"]["tableInfo"].update(expire=7, external_option="retain")
        self.remote["spec"]["alias"] = "retain_alias"
        self.remote["metadata"]["annotations"] = {"retain": "value"}
        self.created_phase = "Ok"
        self.assertIs(self.handler.create_data_storage(), False)
        [(method, payload)] = self.writes()
        self.assertEqual(method, "PUT")
        expected = self.expected_spec()
        expected["tableInfo"]["external_option"] = "retain"
        expected["alias"] = "retain_alias"
        self.assertEqual(payload["spec"], expected)
        self.assertEqual(payload["metadata"]["annotations"], {"retain": "value"})
        self.assertIs(self.handler.create_data_storage(), True)
        self.assertEqual(len(self.writes()), 1)

    def test_existing_source_or_cluster_conflict_is_not_overwritten(self):
        for field, value in (
            ("source", self.ref("ResultTable", "foreign_rt")),
            ("storage", self.ref("Hdfs", "foreign_cluster")),
        ):
            self.seed_ready()
            self.remote["spec"]["tableInfo"][field] = value
            before = deepcopy(self.remote)
            with self.subTest(field=field), self.assertRaises(BKBaseResourceMappingError):
                self.handler.create_data_storage()
            self.assertEqual(self.writes(), [])
            self.assertEqual(self.remote, before)
            self.snapshot.refresh_from_db()
            self.assertEqual(self.snapshot.bkbase_v4_resources["storages"]["hdfs"], self.store_ref)

    def test_missing_or_cross_tenant_rt_binding_refuses_without_storage_request(self):
        original = deepcopy(self.snapshot.bkbase_v4_resources)
        for ref in (
            None,
            {"kind": "ResultTable", "tenant": "default", "namespace": "audit"},
            {**self.rt_ref, "tenant": "other"},
        ):
            self.handler.snapshot.bkbase_v4_resources = {**original, "result_table": ref}
            self.handler.snapshot.save(update_fields=["bkbase_v4_resources"])
            with self.subTest(ref=ref), self.assertRaises(BKBaseResourceMappingError):
                self.handler.create_data_storage()
            self.assertEqual(self.requests, [])

    def test_missing_hdfs_cluster_mapping_is_not_guessed(self):
        GlobalMetaConfig.set(
            BKBASE_V4_STORAGE_CLUSTER_MAP, {}, config_level=ConfigLevelChoices.NAMESPACE.value, instance_key="audit"
        )
        with self.assertRaises(BKBaseResourceMappingError):
            self.handler.create_data_storage()
        self.assertEqual(self.requests, [])

    def test_denied_get_does_not_turn_into_create(self):
        self.read_status = 403
        with self.assertRaises(APIRequestError):
            self.handler.create_data_storage()
        self.assertEqual(self.writes(), [])
        self.local_store.refresh_from_db()
        self.assertEqual(self.local_store.status, SnapshotRunningStatus.FAILED)

    def test_failed_hdfs_never_becomes_local_running(self):
        self.seed_ready()
        self.remote["status"]["phase"] = "Failed"
        with self.assertRaises(BKBaseResourceMappingError):
            self.handler.create_data_storage()
        self.assertEqual(self.writes(), [])
        self.local_store.refresh_from_db()
        self.assertEqual(self.local_store.status, SnapshotRunningStatus.FAILED)

    def test_stopped_hdfs_never_becomes_local_running(self):
        self.seed_ready()
        self.remote["metadata"]["annotations"] = {"task_stopped": "true"}
        self.assertIs(self.handler.create_data_storage(), False)
        self.assertEqual(self.writes(), [])
        self.local_store.refresh_from_db()
        self.assertEqual(self.local_store.status, SnapshotRunningStatus.PREPARING)

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_handler_keeps_legacy_storage_payload_and_sync_status(self):
        sent = []
        with mock.patch.object(
            api.bk_base, "databus_storages_post", side_effect=lambda **params: sent.append(deepcopy(params))
        ):
            self.handler.create_data_storage()
        [params] = sent
        self.assertEqual(
            [field["physical_field"] for field in params["index_fields"]], ["id", "resource_type_id", "system_id"]
        )
        self.assertNotIn("key_fields", params)
        self.local_store.refresh_from_db()
        self.assertEqual(self.local_store.status, SnapshotRunningStatus.RUNNING)
        self.assertEqual(self.requests, [])
