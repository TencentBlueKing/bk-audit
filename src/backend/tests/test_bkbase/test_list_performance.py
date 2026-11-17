"""经真实列表/SDK组合路径核对调用数量、分页和个人权限边界。"""
import json
import threading
import time
from collections import Counter
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock
from urllib.parse import urlparse

import requests
from bk_resource.exceptions import APIRequestError
from django.test import RequestFactory, SimpleTestCase, override_settings
from urllib3.exceptions import ReadTimeoutError

from api.bk_base_v4 import default as sdk
from apps.meta.constants import SpaceType
from services.web.bkbase import metadata, permissions
from services.web.bkbase.exceptions import BKBaseReadTimeout, BKBaseResourceMappingError
from services.web.strategy_v2.resources import ListTables
from services.web.strategy_v2.utils import table


@override_settings(
    BKBASE_API_VERSION="v4",
    BKBASE_V4_TENANT="tenant_a",
    BKBASE_V4_NAMESPACE="audit",
    BKBASE_V4_RESULT_TABLE_NAMESPACES={},
    APP_CODE="synthetic_app",
    SECRET_KEY="synthetic_secret",
    PLATFORM_AUTH_ACCESS_USERNAME="synthetic_admin",
)
class ListPerformanceTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get("/synthetic/")
        self.request.user = SimpleNamespace(bk_username="user_a", is_authenticated=True)
        self.calls = []
        self.lock = threading.Lock()
        self.projects = ["project_999", "shared"] + [f"empty_{i:03}" for i in range(120)]
        self.rows = {
            "project_999": [self.row(i) for i in range(101)],
            "shared": [self.row(i) for i in range(101, 152)]
            + [self.row(0, storage="hdfs"), self.row(200, query=False), self.row(201, query="true")],
        }
        self.enterContext(mock.patch("services.web.bkbase.common.get_local_request", return_value=self.request))
        self.enterContext(mock.patch.object(permissions, "get_request_username", return_value="user_a"))
        self.enterContext(mock.patch.object(table, "get_request_username", return_value="user_a"))
        self.enterContext(mock.patch.object(ListTables, "cache_type", None))
        self.enterContext(mock.patch.object(table.BizRtTableHandler, "get_exclude_rt_ids", return_value=set()))
        self.enterContext(
            mock.patch.object(
                table.resource.meta,
                "get_spaces_mine",
                return_value=[{"id": "47", "name": "Synthetic", "space_type_id": SpaceType.BIZ.value}],
            )
        )
        self.auth = self.enterContext(
            mock.patch.object(sdk.UserBkBaseV4Resource, "build_auth_args", return_value={"bk_token": "synthetic"})
        )
        self.enterContext(mock.patch("requests.sessions.Session.request", side_effect=self.transport))

    @staticmethod
    def rt_id(index):
        return f"47_data_{index:03}"

    def row(self, index, *, storage="doris", query=True):
        return {
            "dataset_name": self.rt_id(index),
            "dataset_alias": f"Alias {index}",
            "storage_type": storage,
            "permissions": {"query": query},
        }

    def result_table(self, index):
        ref = {"kind": "ResultTable", "tenant": "tenant_a", "namespace": f"native_{index % 4}", "name": f"r_{index}"}
        bindings = []
        if index % 2 == 0:
            bindings.append(
                {
                    "kind": "RedisBinding",
                    "metadata": {"tenant": "tenant_a", "namespace": "storage", "name": f"redis_{index}"},
                    "spec": {"data": ref},
                    "status": {"phase": "Ok"},
                }
            )
        if index == 0:
            bindings.append(
                {
                    "kind": "HdfsBinding",
                    "metadata": {"tenant": "tenant_a", "namespace": "storage", "name": "hdfs_0"},
                    "spec": {"data": ref, "storageConfig": {"paimon": {"dimensionTable": False}}},
                    "status": {"phase": "Ok"},
                }
            )
        return {
            "kind": "ResultTable",
            "metadata": {key: ref[key] for key in ("tenant", "namespace", "name")},
            "spec": {"predefiendResultTableId": self.rt_id(index), "bizId": 47},
            "status": {"related": bindings},
        }

    def transport(self, method, url, **kwargs):
        self.assertEqual(method, "GET")
        path = urlparse(url).path
        params = kwargs.get("params", {})
        auth = json.loads(kwargs["headers"]["x-bkapi-authorization"])
        self.assertEqual(kwargs["headers"]["X-Bk-Tenant-Id"], "tenant_a")
        if path.endswith("/namespaces"):
            kind = "UserNamespacesList"
            data = [
                {
                    "kind": "Namespace",
                    "metadata": {"tenant": "tenant_a", "namespace": "bkbase", "name": name},
                    "spec": {"name": name},
                    "status": {"phase": "Ok"},
                }
                for name in self.projects
            ]
        elif path.endswith("/dataset_list/"):
            if params.get("dataset_name"):
                kind = "DatasetList"
                data = {"total": 1, "list": [{"dataset_name": params["dataset_name"], "storage_type": "doris"}]}
            else:
                kind = "UserDatasetList"
                namespace = path.split("/dataset/", 1)[1].split("/", 1)[0]
                rows = deepcopy(self.rows.get(namespace, []))
                if auth["bk_username"] == "user_b":
                    for row in rows:
                        row["permissions"]["query"] = False
                page, size = params["page"], params["page_size"]
                data = {"total": len(rows), "list": rows[(page - 1) * size : page * size]}
        elif "/detail/" in path:
            rt = path.rsplit("/detail/", 1)[1].strip("/")
            index = int(rt.rsplit("_", 1)[1])
            kind = "ChannelDetail" if params.get("storage_type") == "channel" else "DatasetDetail"
            data = {
                "dataset_name": rt,
                "dataset_alias": f"Alias {index}",
                "data_set_type": "result_table",
                "fields": [],
                "kind": "ChannelBinding" if index < 62 else "DorisBinding",
                "storage_type": "channel" if index < 62 else "doris",
            }
        elif "/v4/result_tables/" in path:
            kind = "ResultTableInfo"
            data = self.result_table(int(path.rstrip("/").rsplit("_", 1)[1]))
        else:
            self.fail("Unexpected endpoint " + path)
        if kind.startswith("User"):
            self.assertEqual(auth["bk_username"], self.request.user.bk_username)
            self.assertEqual(auth["bk_token"], "synthetic")
        with self.lock:
            deadline = getattr(sdk, "READ_DEADLINE", None)
            self.calls.append(
                {
                    "kind": kind,
                    "path": path,
                    "params": deepcopy(params),
                    "timeout": kwargs["timeout"],
                    "deadline": deadline.get() if deadline is not None else None,
                }
            )
        response = requests.Response()
        response.status_code = 200
        response.url = url
        response.request = requests.Request(method, url).prepare()
        response._content = json.dumps({"result": True, "code": "00", "data": data}).encode()
        return response

    def test_actual_biz_rt_combination_avoids_duplicate_rt_and_unused_storage_reads(self):
        result = ListTables().request({"table_type": "BizRt", "namespace": "audit"})
        self.assertEqual(
            result,
            [
                {
                    "label": "Synthetic(47)",
                    "value": "47",
                    "children": [{"label": f"Alias {i}", "value": self.rt_id(i)} for i in range(62)],
                }
            ],
        )
        counts = Counter(row["kind"] for row in self.calls)
        self.assertEqual(
            counts,
            {
                "UserNamespacesList": 1,
                "UserDatasetList": 123,
                "ResultTableInfo": 152,
                "DatasetDetail": 152,
                "ChannelDetail": 152,
            },
        )
        self.assertEqual(len(self.calls), 580)
        self.assertEqual(len({row["deadline"] for row in self.calls}), 1)
        self.assertTrue(all(0 < row["timeout"].total <= 10 for row in self.calls))
        self.assertTrue(all(call.args[0] is self.request for call in self.auth.call_args_list))

    def test_mine_keeps_all_projects_pages_and_strict_query_permissions(self):
        result = ListTables().request({"table_type": "MineBizRt", "bk_biz_id": 47})
        self.assertEqual([row["value"] for row in result], [self.rt_id(i) for i in range(152)])
        self.assertEqual(Counter(row["kind"] for row in self.calls), {"UserNamespacesList": 1, "UserDatasetList": 123})
        self.assertTrue(any("project_999" in row["path"] and row["params"].get("page") == 2 for row in self.calls))

    def test_biz_rt_keeps_formal_detail_alias_when_personal_listing_alias_differs(self):
        self.projects = ["project_999"]
        self.rows["project_999"] = [self.row(0)]
        self.rows["project_999"][0]["dataset_alias"] = "Personal listing alias"
        result = ListTables().request({"table_type": "BizRt", "namespace": "audit"})
        self.assertEqual(result[0]["children"], [{"label": "Alias 0", "value": self.rt_id(0)}])

    def test_parallel_project_reads_keep_user_request_and_bound_concurrency(self):
        self.projects = ["project_999", "shared"]
        barrier = threading.Barrier(2)
        active, peak = 0, 0
        original = self.transport

        def concurrent(method, url, **kwargs):
            nonlocal active, peak
            if url.endswith("/dataset_list/") and kwargs.get("params", {}).get("page") == 1:
                with self.lock:
                    active += 1
                    peak = max(peak, active)
                try:
                    barrier.wait(timeout=2)
                    return original(method, url, **kwargs)
                finally:
                    with self.lock:
                        active -= 1
            return original(method, url, **kwargs)

        with mock.patch.object(metadata, "LIST_READ_WORKERS", 2), mock.patch(
            "requests.sessions.Session.request", side_effect=concurrent
        ):
            result = ListTables().request({"table_type": "MineBizRt", "bk_biz_id": 47})
        self.assertEqual(len(result), 152)
        self.assertEqual(peak, 2)
        self.assertTrue(all(call.args[0] is self.request for call in self.auth.call_args_list))

    def test_deadline_is_transport_timeout_and_fails_without_partial_rows(self):
        original = self.transport
        timeouts = []

        def slow(method, url, **kwargs):
            timeouts.append(kwargs["timeout"].total)
            time.sleep(0.07)
            return original(method, url, **kwargs)

        with mock.patch.object(metadata, "LIST_READ_BUDGET_SECONDS", 0.05), mock.patch(
            "requests.sessions.Session.request", side_effect=slow
        ), self.assertRaises(BKBaseReadTimeout) as raised:
            ListTables().request({"table_type": "MineBizRt", "bk_biz_id": 47})
        self.assertEqual(raised.exception.STATUS_CODE, 504)
        self.assertTrue(all(0 < timeout <= 0.05 for timeout in timeouts))
        self.assertEqual([row["kind"] for row in self.calls], ["UserNamespacesList"])
        self.assertIsNone(sdk.READ_DEADLINE.get())

    def test_single_http_timeout_is_a_clear_gateway_timeout(self):
        with mock.patch("requests.sessions.Session.request", side_effect=requests.Timeout("Synthetic timeout")):
            with self.assertRaises(BKBaseReadTimeout) as raised:
                ListTables().request({"table_type": "MineBizRt", "bk_biz_id": 47})
        self.assertEqual(raised.exception.STATUS_CODE, 504)
        self.assertIsNone(sdk.READ_DEADLINE.get())

    def test_response_body_read_timeout_is_a_clear_gateway_timeout(self):
        for endpoint in ("/namespaces", "/dataset_list/"):
            with self.subTest(endpoint=endpoint):
                timeout = ReadTimeoutError(None, "/synthetic/", "Synthetic response body timeout")
                original = self.transport

                def body_timeout(method, url, **kwargs):
                    if not url.endswith(endpoint):
                        return original(method, url, **kwargs)
                    self.assertGreater(sdk.READ_DEADLINE.get() - time.monotonic(), 1)
                    response = requests.Response()
                    response.status_code = 200
                    response.raw = SimpleNamespace(stream=mock.Mock(side_effect=timeout))
                    # Session.request 在非 stream 模式下也会读取该真实属性。
                    response.content

                with mock.patch("requests.sessions.Session.request", side_effect=body_timeout):
                    with self.assertRaises(BKBaseReadTimeout) as raised:
                        ListTables().request({"table_type": "MineBizRt", "bk_biz_id": 47})
                self.assertEqual(raised.exception.STATUS_CODE, 504)
                api_error = raised.exception.__cause__
                self.assertIsInstance(api_error, APIRequestError)
                connection_error = api_error.__cause__
                self.assertIsInstance(connection_error, requests.ConnectionError)
                self.assertIs(connection_error.args[0], timeout)
                self.assertIsNone(sdk.READ_DEADLINE.get())
                self.assertFalse(any(thread.name.startswith("bkbase-list") for thread in threading.enumerate()))

    def test_plain_connection_error_keeps_original_api_error_and_cause(self):
        failure = requests.ConnectionError("Synthetic connection refused")
        with mock.patch("requests.sessions.Session.request", side_effect=failure):
            with self.assertRaises(APIRequestError) as raised:
                ListTables().request({"table_type": "MineBizRt", "bk_biz_id": 47})
        self.assertIs(raised.exception.__cause__, failure)
        self.assertIsNone(sdk.READ_DEADLINE.get())

    def test_nested_timeout_cause_is_mapped_without_replacing_its_chain(self):
        timeout = requests.Timeout("Synthetic nested timeout")
        wrapper = RuntimeError("Synthetic SDK wrapper")
        wrapper.__cause__ = timeout
        with mock.patch("requests.sessions.Session.request", side_effect=wrapper):
            with self.assertRaises(BKBaseReadTimeout) as raised:
                ListTables().request({"table_type": "MineBizRt", "bk_biz_id": 47})
        self.assertIsInstance(raised.exception.__cause__, APIRequestError)
        self.assertIs(raised.exception.__cause__.__cause__, wrapper)
        self.assertIs(wrapper.__cause__, timeout)
        self.assertIsNone(sdk.READ_DEADLINE.get())

    def test_deadline_during_parallel_pages_joins_workers_without_dispatching_rest(self):
        self.projects = [f"budget_{i}" for i in range(8)]
        barrier = threading.Barrier(2)
        entered, timeouts = [], []
        original = self.transport

        def slow_pages(method, url, **kwargs):
            if url.endswith("/dataset_list/"):
                entered.append(url)
                timeouts.append(kwargs["timeout"].total)
                barrier.wait(timeout=2)
                time.sleep(kwargs["timeout"].total + 0.01)
                raise requests.Timeout("Synthetic deadline-bound read")
            return original(method, url, **kwargs)

        with mock.patch.object(metadata, "LIST_READ_BUDGET_SECONDS", 0.2), mock.patch.object(
            metadata, "LIST_READ_WORKERS", 2
        ), mock.patch("requests.sessions.Session.request", side_effect=slow_pages):
            with self.assertRaises(BKBaseReadTimeout):
                ListTables().request({"table_type": "MineBizRt", "bk_biz_id": 47})
        self.assertEqual(len(entered), 2)
        self.assertTrue(all(0 < timeout <= 0.2 for timeout in timeouts))
        self.assertFalse(any(thread.name.startswith("bkbase-list") for thread in threading.enumerate()))
        self.assertIsNone(sdk.READ_DEADLINE.get())

    def test_failed_page_cancels_undispatched_work_and_joins_inflight_reads(self):
        self.projects = [f"failure_{i}" for i in range(8)]
        barrier = threading.Barrier(2)
        entered = []
        original = self.transport

        def failing(method, url, **kwargs):
            if url.endswith("/dataset_list/"):
                namespace = url.split("/dataset/", 1)[1].split("/", 1)[0]
                entered.append(namespace)
                barrier.wait(timeout=2)
                if namespace == "failure_0":
                    raise requests.ConnectionError("Synthetic transport failure")
                time.sleep(0.02)
            return original(method, url, **kwargs)

        with mock.patch.object(metadata, "LIST_READ_WORKERS", 2), mock.patch(
            "requests.sessions.Session.request", side_effect=failing
        ), self.assertRaises(APIRequestError):
            ListTables().request({"table_type": "MineBizRt", "bk_biz_id": 47})
        self.assertEqual(set(entered), {"failure_0", "failure_1"})
        self.assertFalse(any(thread.name.startswith("bkbase-list") for thread in threading.enumerate()))
        self.assertIsNone(sdk.READ_DEADLINE.get())

    def test_duplicate_candidate_ids_expand_metadata_once_and_keep_input_order(self):
        rows = metadata.get_result_tables_with_capabilities([self.rt_id(0), self.rt_id(0), self.rt_id(1)])
        self.assertEqual([rt["result_table_id"] for rt, _ in rows], [self.rt_id(0), self.rt_id(1)])
        self.assertEqual(
            Counter(row["kind"] for row in self.calls),
            {
                "ResultTableInfo": 2,
                "DatasetDetail": 2,
                "ChannelDetail": 2,
            },
        )

    def test_actual_unknown_bindings_are_not_promoted_to_rt_or_asset_candidates(self):
        self.projects = ["project_999"]
        self.rows["project_999"] = [self.row(70)]
        original = self.result_table

        def unknown(index):
            result = original(index)
            result["status"] = {}
            return result

        with mock.patch.object(self, "result_table", side_effect=unknown):
            for kind in ("BizRt", "BizAsset"):
                with self.subTest(kind=kind):
                    result = (
                        ListTables().request({"table_type": kind, "namespace": "audit"})
                        if kind == "BizRt"
                        else table.BizAssetTableHandler(kind).list_tables()
                    )
                    self.assertEqual(result, [{"label": "Synthetic(47)", "value": "47", "children": []}])

    def test_next_user_does_not_reuse_permission_rows(self):
        first = ListTables().request({"table_type": "MineBizRt", "bk_biz_id": 47})
        self.request.user.bk_username = "user_b"
        with mock.patch.object(permissions, "get_request_username", return_value="user_b"), mock.patch.object(
            table, "get_request_username", return_value="user_b"
        ):
            second = ListTables().request({"table_type": "MineBizRt", "bk_biz_id": 47})
        self.assertEqual(len(first), 152)
        self.assertEqual(second, [])
        self.assertEqual(Counter(row["kind"] for row in self.calls)["UserNamespacesList"], 2)

    def test_incomplete_personal_page_fails_instead_of_partial_success(self):
        original = self.transport

        def truncated(method, url, **kwargs):
            response = original(method, url, **kwargs)
            if "project_999" in url and kwargs.get("params", {}).get("page") == 2:
                response._content = json.dumps(
                    {"result": True, "code": "00", "data": {"total": 101, "list": []}}
                ).encode()
            return response

        with mock.patch("requests.sessions.Session.request", side_effect=truncated):
            with self.assertRaises(BKBaseResourceMappingError):
                ListTables().request({"table_type": "MineBizRt", "bk_biz_id": 47})
