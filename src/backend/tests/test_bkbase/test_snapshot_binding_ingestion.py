"""从仅有旧ID的Asset周期入口验证正式绑定摄入。

只替换HTTP和锁边界，保留SDK序列化、发现、持久化及重放消费者。
合成资源名与逻辑ID不同，绑定成功也不代表下游运行或数据补齐。
"""
import datetime
import json
from copy import deepcopy
from unittest import mock
from urllib.parse import urlparse

import requests
from django.db import connection
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.meta.models import ResourceType, System
from services.web.bkbase import source
from services.web.databus import tasks
from services.web.databus.collector.snapshot.join.http_pull import HttpPullHandler
from services.web.databus.constants import JoinDataType, SnapshotRunningStatus
from services.web.databus.models import Snapshot, SnapshotStorage


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
class SnapshotBindingIngestionTests(TestCase):
    def setUp(self):
        self.system = System.objects.create(
            system_id="binding_system",
            namespace="audit_namespace",
            callback_url="https://source.test",
            auth_token="test",
        )
        self.resource_type = ResourceType.objects.create(
            system_id=self.system.system_id,
            resource_type_id="asset",
            unique_id="binding_system:asset",
            path="/resources",
        )
        self.snapshot = Snapshot.objects.create(
            system_id=self.system.system_id,
            resource_type_id="asset",
            join_data_type=JoinDataType.ASSET,
            status=SnapshotRunningStatus.RUNNING,
            bkbase_data_id=11,
            bkbase_processing_id="old_processing",
            bkbase_table_id="11_logical_rt",
        )
        for kind in ("hdfs", "doris"):
            SnapshotStorage.objects.create(
                snapshot=self.snapshot, storage_type=kind, status=SnapshotRunningStatus.RUNNING
            )
        self.expected = {
            "raw_data_id": 11,
            "data_source": self.ref("DataSource", "source_a"),
            "data_id": self.ref("DataId", "data_a", "source_project"),
            "clean": self.ref("Clean", "clean_a"),
            "clean_role": "owner",
            "result_table_id": "11_logical_rt",
            "result_table": self.ref("ResultTable", "actual_rt", "table_project"),
            "storages": {"hdfs": self.ref("DataStorage", "hdfs_task"), "doris": self.ref("DataStorage", "doris_task")},
        }
        params = HttpPullHandler(self.system, self.resource_type, self.snapshot, JoinDataType.ASSET).config
        scope = params["access_conf_info"]["resource"]["scope"][0]
        self.resources = {
            "source_a": self.remote(
                "DataSource",
                "source_a",
                {
                    "data_id": self.expected["data_id"],
                    "data_conn": self.ref("DataConn", "connection_a"),
                    "desired_status": "Running",
                    "current_status": "Running",
                    "report_config": {
                        "type": "rest_api",
                        "http_mode": "PULL",
                        "data_conn_name": "connection_a",
                        "method": "post",
                        "path": "/resources",
                        "body": scope["body"]["content"],
                        "period": 1,
                        "period_unit": "minute",
                        "increment_field": {"type": "time", "time_format": "Unix Time Stamp(milliseconds)"},
                        "pagination": {
                            "start_offset": 0,
                            "limit": scope["body"]["page"]["limit"],
                            "total_path": "data.count",
                        },
                    },
                },
                labels={"raw_data_id": "11"},
            ),
            "data_a": self.remote("DataId", "data_a", {}, namespace="source_project"),
            "connection_a": self.remote(
                "DataConn",
                "connection_a",
                {"conn_info": {"type": "rest_api", "url": "https://source.test", "headers": scope["headers"]}},
            ),
            "clean_a": self.remote(
                "Clean",
                "clean_a",
                {
                    "data_id": self.expected["data_id"],
                    "raw_data_id": 11,
                    "result_table_id": "11_logical_rt",
                    "result_table_source": "new",
                    "desired_status": "Running",
                    "current_status": "Running",
                    "config_revision": 7,
                    "deploy_revision": 7,
                    "rules": [],
                },
                labels={"raw_data_id": "11", "result_table_id": "11_logical_rt", "processing_id": "old_processing"},
            ),
            "actual_rt": self.remote(
                "ResultTable", "actual_rt", {}, namespace="table_project", labels={"result_table_id": "11_logical_rt"}
            ),
        }
        for name, kind in (("hdfs_task", "Hdfs"), ("doris_task", "Doris")):
            self.resources[name] = self.remote(
                "DataStorage",
                name,
                {
                    "tableInfo": {
                        "source": self.expected["result_table"],
                        "storage": self.ref(kind, name + "_cluster", "infra"),
                    }
                },
                labels={"result_table_id": "11_logical_rt"},
            )
            self.resources[name]["status"]["message"] = "running"
        self.lists = {"datasources": ["source_a"], "cleans": ["clean_a"], "datastorages": ["hdfs_task", "doris_task"]}
        self.requests = []
        self.read_hook = None
        self.atomic_depth = len(connection.atomic_blocks)
        self.enterContext(mock.patch("requests.sessions.Session.request", side_effect=self.transport))
        self.enterContext(mock.patch.object(source, "resource_lock"))
        self.enterContext(mock.patch("core.lock.CacheLock.locked", new_callable=mock.PropertyMock, return_value=False))
        self.enterContext(mock.patch("core.lock.CacheLock.release", return_value=True))

    def ref(self, kind, name, namespace="project_a"):
        return {"kind": kind, "tenant": "default", "namespace": namespace, "name": name}

    def remote(self, kind, name, spec, *, namespace="project_a", labels=None):
        return {
            "kind": kind,
            "metadata": {
                "tenant": "default",
                "namespace": namespace,
                "name": name,
                "labels": labels or {},
                "annotations": {},
            },
            "spec": spec,
            "status": {"phase": "Ok"},
        }

    def transport(self, method, url, **kwargs):
        self.assertEqual(len(connection.atomic_blocks), self.atomic_depth, "HTTP inside binding-save transaction")
        path = urlparse(url).path
        name = path.rstrip("/").rsplit("/", 1)[-1]
        self.requests.append((method.upper(), path, deepcopy(kwargs.get("params", {})), deepcopy(kwargs.get("json"))))
        auth = json.loads(kwargs["headers"]["x-bkapi-authorization"])
        self.assertEqual(auth["bk_username"], "synthetic_platform")
        self.assertEqual(auth["access_token"], "synthetic_token")
        if method.upper() == "GET":
            if self.read_hook:
                hook, self.read_hook = self.read_hook, None
                hook()
            if name in self.lists:
                self.assertIn("/tenants/default/namespaces/project_a/", path)
                selector = kwargs.get("params", {}).get("label_selector", "")
                terms = dict(term.split("=", 1) for term in selector.split(",") if term)
                value = [
                    deepcopy(self.resources[key])
                    for key in self.lists[name]
                    if all(self.resources[key]["metadata"]["labels"].get(k) == v for k, v in terms.items())
                ]
            else:
                self.assertIn(name, self.resources, "unexpected or V3 request")
                self.assertFalse(kwargs.get("params"), "GET path keys or undocumented selector leaked into query")
                value = deepcopy(self.resources[name])
        else:
            self.assertEqual((method.upper(), name), ("PUT", "source_a"), "only existing Source may be written")
            self.resources[name]["spec"] = deepcopy(kwargs["json"]["spec"])
            value = deepcopy(self.resources[name])
            value["status"]["phase"] = "Pending"
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

    def test_periodic_ingests_old_ids_then_consumes_replay(self):
        self.assertEqual(self.snapshot.bkbase_v4_resources, {})
        self.schedule()
        for key, value in self.expected.items():
            self.assertEqual(self.snapshot.bkbase_v4_resources.get(key), value)
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)
        tasks.start_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertIs(self.snapshot.bkbase_v4_resources["source_replay"]["accepted"], True)
        self.assertEqual(len([r for r in self.requests if r[0] == "PUT"]), 1)
        self.assertEqual(self.snapshot.bkbase_processing_id, "old_processing")
        self.assertEqual(self.snapshot.bkbase_table_id, "11_logical_rt")

    def assert_pending_binding(self):
        for key, value in self.expected.items():
            self.assertEqual(self.snapshot.bkbase_v4_resources.get(key), value)
        self.assertIs(type(self.snapshot.bkbase_v4_resources["raw_data_id"]), int)
        self.assertEqual(self.snapshot.bkbase_processing_id, "old_processing")
        self.assertEqual(self.snapshot.bkbase_table_id, "11_logical_rt")
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.RUNNING)
        self.assertFalse(any(r[0] != "GET" for r in self.requests))
        self.assertFalse((self.snapshot.bkbase_v4_resources.get("source_replay") or {}).get("active"))

    def test_binding_persists_without_downstream_running_evidence(self):
        self.resources["doris_task"]["status"]["phase"] = "Pending"
        self.schedule()
        self.assert_pending_binding()

    def assert_discovery_rejected(self, expected=None):
        self.schedule()
        self.assertEqual(self.snapshot.bkbase_v4_resources, expected or {})
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.RUNNING)
        self.assertFalse(any(r[0] != "GET" for r in self.requests))

    def test_multiple_sources_are_not_resolved_by_first_match(self):
        self.resources["source_b"] = deepcopy(self.resources["source_a"])
        self.resources["source_b"]["metadata"]["name"] = "source_b"
        self.lists["datasources"].append("source_b")
        self.assert_discovery_rejected()

    def test_multiple_cleans_are_rejected(self):
        self.resources["clean_b"] = deepcopy(self.resources["clean_a"])
        self.resources["clean_b"]["metadata"]["name"] = "clean_b"
        self.lists["cleans"].append("clean_b")
        self.assert_discovery_rejected()

    def test_multiple_same_kind_storage_tasks_are_rejected(self):
        self.resources["other_doris"] = deepcopy(self.resources["doris_task"])
        self.resources["other_doris"]["metadata"]["name"] = "other_doris"
        self.resources["other_doris"]["spec"]["tableInfo"]["storage"]["name"] = "another_cluster"
        self.lists["datastorages"].append("other_doris")
        self.assert_discovery_rejected()

    def test_missing_required_storage_does_not_save_partial_bundle(self):
        self.lists["datastorages"].remove("doris_task")
        self.assert_discovery_rejected()

    def test_missing_source_label_is_pending_discovery_not_dataid_fallback(self):
        self.resources["source_a"]["metadata"]["labels"] = {}
        self.assert_discovery_rejected()
        self.assertEqual(len(self.requests), 1)

    def test_wrong_source_tenant_is_rejected(self):
        self.resources["source_a"]["metadata"]["tenant"] = "other_tenant"
        self.assert_discovery_rejected()

    def test_list_scope_cannot_fall_back_to_audit_namespace(self):
        self.resources["source_a"]["metadata"]["namespace"] = "audit_namespace"
        self.assert_discovery_rejected()

    def test_formal_rt_get_wrong_tenant_is_rejected(self):
        self.resources["actual_rt"]["metadata"]["tenant"] = "other_tenant"
        self.assert_discovery_rejected()

    def test_formal_rt_get_logical_label_must_match_old_id(self):
        self.resources["actual_rt"]["metadata"]["labels"]["result_table_id"] = "11_other_rt"
        self.assert_discovery_rejected()

    def test_storage_labels_and_annotations_cannot_disagree(self):
        self.resources["doris_task"]["metadata"]["annotations"]["result_table_id"] = "11_other_rt"
        self.assert_discovery_rejected()

    def test_storages_cannot_reference_different_formal_result_tables(self):
        self.resources["doris_task"]["spec"]["tableInfo"]["source"]["name"] = "other_rt"
        self.assert_discovery_rejected()

    def test_clean_processing_id_is_not_inferred_from_raw_id(self):
        self.resources["clean_a"]["metadata"]["labels"]["processing_id"] = "other_processing"
        self.assert_discovery_rejected()

    def test_clean_spec_raw_id_is_cross_checked_after_label_selection(self):
        self.resources["clean_a"]["spec"]["raw_data_id"] = 12
        self.assert_discovery_rejected()

    def test_clean_dataid_reference_must_equal_source_dataid(self):
        self.resources["clean_a"]["spec"]["data_id"]["name"] = "another_dataid"
        self.assert_discovery_rejected()

    def test_asset_owner_role_cannot_adopt_existing_shared_clean(self):
        self.resources["clean_a"]["spec"]["result_table_source"] = "existing"
        self.assert_discovery_rejected()

    def test_compatible_partial_binding_is_completed_without_losing_other_keys(self):
        partial = {
            "data_source": self.expected["data_source"],
            "storages": {"hdfs": self.expected["storages"]["hdfs"]},
            "retained": {"value": 1},
        }
        Snapshot.objects.filter(pk=self.snapshot.pk).update(bkbase_v4_resources=partial)
        self.resources["doris_task"]["status"]["phase"] = "Pending"
        self.schedule()
        self.assert_pending_binding()
        self.assertEqual(self.snapshot.bkbase_v4_resources["retained"], {"value": 1})

    def test_conflicting_partial_binding_is_not_overwritten(self):
        partial = {"data_source": self.ref("DataSource", "other_source"), "retained": {"value": 1}}
        Snapshot.objects.filter(pk=self.snapshot.pk).update(bkbase_v4_resources=partial)
        self.assert_discovery_rejected(partial)

    def test_compatible_decimal_raw_id_in_partial_binding_is_normalized(self):
        Snapshot.objects.filter(pk=self.snapshot.pk).update(bkbase_v4_resources={"raw_data_id": "11"})
        self.resources["doris_task"]["status"]["phase"] = "Pending"
        self.schedule()
        self.assert_pending_binding()

    def test_conflicting_partial_storage_is_not_overwritten(self):
        partial = {"storages": {"hdfs": self.ref("DataStorage", "other_hdfs")}}
        Snapshot.objects.filter(pk=self.snapshot.pk).update(bkbase_v4_resources=partial)
        self.assert_discovery_rejected(partial)

    def test_configuration_change_during_http_preserves_new_configuration(self):
        self.read_hook = lambda: Snapshot.objects.filter(pk=self.snapshot.pk).update(custom_config={"new": "config"})
        self.assert_discovery_rejected()
        self.assertEqual(self.snapshot.custom_config, {"new": "config"})

    def test_endpoint_change_during_http_rejects_old_discovery(self):
        self.read_hook = lambda: System.objects.filter(pk=self.system.pk).update(callback_url="https://new.test")
        self.assert_discovery_rejected()

    def test_old_identity_change_during_http_is_preserved(self):
        self.read_hook = lambda: Snapshot.objects.filter(pk=self.snapshot.pk).update(
            bkbase_processing_id="new_processing"
        )
        self.assert_discovery_rejected()
        self.assertEqual(self.snapshot.bkbase_processing_id, "new_processing")

    def test_required_storage_change_during_http_rejects_old_discovery(self):
        self.read_hook = lambda: SnapshotStorage.objects.create(snapshot=self.snapshot, storage_type="redis")
        self.assert_discovery_rejected()
        self.assertEqual(self.snapshot.storages.count(), 3)

    def test_operation_change_during_http_is_not_overwritten(self):
        intent = {"source_replay": {"active": True, "operation_id": "new_operation"}}
        self.read_hook = lambda: Snapshot.objects.filter(pk=self.snapshot.pk).update(bkbase_v4_resources=intent)
        self.assert_discovery_rejected(intent)

    def test_stop_intent_during_http_is_not_overwritten(self):
        intent = {"pending_action": "stop"}
        self.read_hook = lambda: Snapshot.objects.filter(pk=self.snapshot.pk).update(bkbase_v4_resources=intent)
        self.assert_discovery_rejected(intent)

    def test_new_binding_during_http_is_not_merged_or_replaced(self):
        newer = {"data_source": self.expected["data_source"], "new_binding": True}
        self.read_hook = lambda: Snapshot.objects.filter(pk=self.snapshot.pk).update(bkbase_v4_resources=newer)
        self.assert_discovery_rejected(newer)

    def test_unknown_write_outcome_prevents_discovery(self):
        intent = {"source_replay": {"active": False, "outcome_unknown": True}}
        Snapshot.objects.filter(pk=self.snapshot.pk).update(bkbase_v4_resources=intent)
        self.assert_discovery_rejected(intent)
        self.assertEqual(self.requests, [])

    def test_malformed_existing_operation_is_rejected_without_overwriting_it(self):
        invalid = {"source_replay": "not_an_operation"}
        Snapshot.objects.filter(pk=self.snapshot.pk).update(bkbase_v4_resources=invalid)
        self.assert_discovery_rejected(invalid)
        self.assertEqual(self.requests, [])

    @override_settings(BKBASE_V4_TENANT="other_tenant")
    def test_other_tenant_has_no_guessed_generic_resource_route(self):
        self.assert_discovery_rejected()
        self.assertEqual(self.requests, [])

    @override_settings(BKBASE_V4_NAMESPACE="")
    def test_missing_configured_bkbase_project_does_not_use_system_namespace(self):
        self.assert_discovery_rejected()
        self.assertEqual(self.requests, [])

    def test_recent_asset_not_selected_by_existing_refresh_ratio(self):
        tasks.refresh_snapshot.run()
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.bkbase_v4_resources, {})
        self.assertEqual(self.requests, [])

    def test_running_basic_uses_shared_identity_discovery_with_actual_storages(self):
        Snapshot.objects.filter(pk=self.snapshot.pk).update(join_data_type=JoinDataType.BASIC)
        self.schedule()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)
        self.assertEqual(self.snapshot.bkbase_v4_resources["clean_role"], "owner")
        self.assertEqual(self.snapshot.bkbase_v4_resources["storages"], self.expected["storages"])
        self.assertFalse(any(request[0] != "GET" for request in self.requests))

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_refresh_retains_legacy_scheduling_without_discovery(self):
        self.schedule()
        self.assertEqual(self.snapshot.status, SnapshotRunningStatus.PREPARING)
        self.assertEqual(self.snapshot.bkbase_v4_resources, {})
        self.assertEqual(self.requests, [])
