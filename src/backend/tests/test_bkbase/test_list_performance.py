"""经真实列表/SDK组合路径核对调用数量、分页和个人权限边界。"""
import json
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock
from urllib.parse import urlparse

import requests
from bk_resource.exceptions import APIRequestError
from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory, SimpleTestCase, override_settings
from urllib3.exceptions import ReadTimeoutError

from api.bk_base.default import GetMineResultTables
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
    BK_RESOURCE={
        "PLATFORM_AUTH_ENABLED": True,
        "PLATFORM_AUTH_ACCESS_USERNAME": "synthetic_admin",
        "PLATFORM_AUTH_ACCESS_TOKEN": "synthetic_platform_token",
    },
)
class ListPerformanceTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get("/synthetic/")
        self.request.user = SimpleNamespace(bk_username="user_a", is_authenticated=True)
        self.request.COOKIES["bk_token"] = "synthetic_caller_cookie"
        self.denied_for_all_users = set()
        self.calls = []
        self.lock = threading.Lock()
        self.projects = ["project_999", "shared"] + [f"empty_{i:03}" for i in range(120)]
        self.rows = {
            "project_999": [self.row(i) for i in range(101)],
            "shared": [self.row(i) for i in range(101, 152)]
            + [self.row(0, storage="hdfs"), self.row(200, query=False), self.row(201, query="true")],
        }
        self.enterContext(mock.patch("services.web.bkbase.common.get_local_request", return_value=self.request))
        self.enterContext(mock.patch("blueapps.utils.request_provider.get_local_request", return_value=self.request))
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
        platform = auth.get("bk_username") == "synthetic_admin"
        if platform:
            self.assertEqual(
                auth,
                {
                    "bk_app_code": "synthetic_app",
                    "bk_app_secret": "synthetic_secret",
                    "bk_username": "synthetic_admin",
                    "access_token": "synthetic_platform_token",
                },
            )
            self.assertNotIn("cookie", {key.lower() for key in kwargs["headers"]})
        if path.endswith("/namespaces"):
            kind = "NamespacesList" if platform else "UserNamespacesList"
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
            if platform and params.get("dataset_name"):
                kind = "DatasetList"
                data = {"total": 1, "list": [{"dataset_name": params["dataset_name"], "storage_type": "doris"}]}
            else:
                kind = "DatasetList" if platform else "UserDatasetList"
                namespace = path.split("/dataset/", 1)[1].split("/", 1)[0]
                rows = deepcopy(self.rows.get(namespace, []))
                for row in rows:
                    if not platform and (
                        auth["bk_username"] == "user_b" or row["dataset_name"] in self.denied_for_all_users
                    ):
                        row["permissions"]["query"] = False
                if params.get("dataset_name"):
                    rows = [row for row in rows if params["dataset_name"] in row["dataset_name"]]
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
                "NamespacesList": 1,
                "DatasetList": 123,
                "ResultTableInfo": 152,
                "DatasetDetail": 152,
                "ChannelDetail": 152,
            },
        )
        self.assertEqual(len(self.calls), 580)
        self.assertEqual(len({row["deadline"] for row in self.calls}), 1)
        self.assertTrue(all(0 < row["timeout"].total <= 30 for row in self.calls))
        self.assertTrue(all(call.args[0] is self.request for call in self.auth.call_args_list))

    def test_biz_rt_uses_same_platform_tables_for_different_callers_while_mine_is_personal(self):
        self.denied_for_all_users = {self.rt_id(0)}
        expected = [
            {
                "label": "Synthetic(47)",
                "value": "47",
                "children": [{"label": f"Alias {i}", "value": self.rt_id(i)} for i in range(62)],
            }
        ]
        for user, personal_ids in (("user_a", [self.rt_id(i) for i in range(1, 152)]), ("user_b", [])):
            self.request.user.bk_username = user
            with mock.patch.object(table, "get_request_username", return_value=user):
                self.assertEqual(ListTables().request({"table_type": "BizRt", "namespace": "audit"}), expected)
                self.assertEqual(
                    [row["value"] for row in ListTables().request({"table_type": "MineBizRt", "bk_biz_id": 47})],
                    personal_ids,
                )
        self.assertEqual(len(permissions.get_project_data(project_id=999, bk_username="spoofed")), 152)

    def test_platform_listing_rejects_disabled_or_missing_platform_credentials(self):
        for enabled, account, token in (
            (False, "synthetic_admin", "synthetic_platform_token"),
            (False, None, "synthetic_platform_token"),
            (True, None, None),
            (True, "", ""),
            (True, "  ", "\t"),
        ):
            with self.subTest(enabled=enabled, account=account, token=token), override_settings(
                BK_RESOURCE={
                    "PLATFORM_AUTH_ENABLED": enabled,
                    "PLATFORM_AUTH_ACCESS_USERNAME": account,
                    "PLATFORM_AUTH_ACCESS_TOKEN": token,
                }
            ):
                self.calls.clear()
                with self.assertRaises(ImproperlyConfigured):
                    ListTables().request({"table_type": "BizRt", "namespace": "audit"})
                self.assertEqual(self.calls, [])
                personal = ListTables().request({"table_type": "MineBizRt", "bk_biz_id": 47})
                self.assertEqual([row["value"] for row in personal], [self.rt_id(i) for i in range(152)])

    def test_platform_auth_modes_never_borrow_caller_cookie_or_token(self):
        modes = (
            ("synthetic_admin", None, {"bk_username": "synthetic_admin"}),
            (None, "synthetic_platform_token", {"access_token": "synthetic_platform_token"}),
            (
                "synthetic_admin",
                "synthetic_platform_token",
                {
                    "bk_username": "synthetic_admin",
                    "access_token": "synthetic_platform_token",
                },
            ),
            ("  ", "synthetic_platform_token", {"access_token": "synthetic_platform_token"}),
            ("synthetic_admin", "\t", {"bk_username": "synthetic_admin"}),
        )
        for account, token, expected in modes:
            with self.subTest(account=account, token=token):

                def send(method, url, **kwargs):
                    self.assertEqual(method, "GET")
                    self.assertEqual(
                        json.loads(kwargs["headers"]["x-bkapi-authorization"]),
                        {
                            "bk_app_code": "synthetic_app",
                            "bk_app_secret": "synthetic_secret",
                            **expected,
                        },
                    )
                    self.assertNotIn("cookie", {key.lower() for key in kwargs["headers"]})
                    if url.endswith("/v4/tenants/tenant_a/namespaces"):
                        data = []
                    else:
                        self.assertTrue(url.endswith("/v4/databus/dataset/project_999/dataset_list/"))
                        data = {"total": 0, "list": []}
                    response = requests.Response()
                    response.status_code = 200
                    response._content = json.dumps({"result": True, "code": "00", "data": data}).encode()
                    return response

                with override_settings(
                    BK_RESOURCE={
                        "PLATFORM_AUTH_ENABLED": True,
                        "PLATFORM_AUTH_ACCESS_USERNAME": account,
                        "PLATFORM_AUTH_ACCESS_TOKEN": token,
                    }
                ), mock.patch("requests.sessions.Session.request", side_effect=send), mock.patch.object(
                    sdk.BkBaseV4Resource, "build_auth_args", side_effect=AssertionError("caller auth read")
                ):
                    self.assertEqual(
                        sdk.NamespacesList().request(tenant="tenant_a", _request=self.request, bk_username="user_b"), []
                    )
                    self.assertEqual(
                        sdk.DatasetList().request(
                            tenant="tenant_a", namespace="project_999", _request=self.request, bk_username="user_b"
                        ),
                        {"total": 0, "list": []},
                    )

    def test_platform_incomplete_last_page_never_returns_partial_tables(self):
        self.projects = ["project_999"]
        original = self.transport
        for last_page, total in (([], 101), ([self.row(100)], 102)):
            with self.subTest(last_page_count=len(last_page), total=total):

                def incomplete(method, url, **kwargs):
                    response = original(method, url, **kwargs)
                    if url.endswith("/dataset_list/"):
                        payload = response.json()
                        payload["data"]["total"] = total
                        if kwargs["params"]["page"] == 2:
                            payload["data"]["list"] = last_page
                        response._content = json.dumps(payload).encode()
                    return response

                with mock.patch("requests.sessions.Session.request", side_effect=incomplete):
                    with self.assertRaises(BKBaseResourceMappingError):
                        permissions.get_project_data(project_id=999)

    def test_biz_rt_excludes_snapshot_and_plugin_before_capability_reads(self):
        with mock.patch.object(
            table.BizRtTableHandler, "get_exclude_rt_ids", return_value={self.rt_id(0), self.rt_id(1)}
        ):
            result = ListTables().request({"table_type": "BizRt", "namespace": "audit"})
        self.assertEqual([row["value"] for row in result[0]["children"]], [self.rt_id(i) for i in range(2, 62)])
        self.assertFalse(
            any(
                row['kind'] == 'ResultTableInfo'
                and row['path'].rstrip('/').rsplit('/', 1)[1] in {self.rt_id(0), self.rt_id(1)}
                for row in self.calls
            )
        )

    def test_mine_keeps_all_projects_pages_and_strict_query_permissions(self):
        # 过滤前要多读两页；147_也匹配47_，必须继续按业务号精确剔除。
        unrelated = [{**self.row(i), "dataset_name": f"48_other_{i}"} for i in range(201)]
        self.rows["project_999"] = unrelated + self.rows["project_999"]
        self.rows["shared"].append({**self.row(300), "dataset_name": "147_other_300"})
        result = ListTables().request({"table_type": "MineBizRt", "bk_biz_id": 47})
        self.assertEqual([row["value"] for row in result], [self.rt_id(i) for i in range(152)])
        self.assertEqual(Counter(row["kind"] for row in self.calls), {"UserNamespacesList": 1, "UserDatasetList": 123})
        self.assertTrue(any("project_999" in row["path"] and row["params"].get("page") == 2 for row in self.calls))

    def test_unselected_business_keeps_other_business_tables(self):
        self.rows["shared"].append({**self.row(300), "dataset_name": "147_other_300"})
        result = permissions.get_mine_result_tables(bk_username="user_a")
        self.assertEqual(
            [row["result_table_id"] for row in result],
            [self.rt_id(i) for i in range(152)] + ["147_other_300"],
        )

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_mine_keeps_legacy_endpoint_and_response(self):
        expected = [{"result_table_id": "47_legacy", "result_table_name": "Legacy", "bk_biz_id": 47}]

        def legacy(method, url, **kwargs):
            self.assertEqual(method, "GET")
            self.assertTrue(url.endswith("/v3/meta/result_tables/mine/"))
            self.assertEqual(kwargs["params"]["bk_biz_id"], 47)
            self.assertEqual(kwargs["params"]["bk_username"], "user_a")
            self.assertNotIn("dataset_name", kwargs["params"])
            response = requests.Response()
            response.status_code = 200
            response.url = url
            response.request = requests.Request(method, url).prepare()
            response._content = json.dumps({"result": True, "code": "00", "data": expected}).encode()
            return response

        with mock.patch("requests.sessions.Session.request", side_effect=legacy), mock.patch.object(
            GetMineResultTables, "build_auth_args", return_value={"bk_token": "synthetic"}
        ):
            self.assertEqual(permissions.get_mine_result_tables(bk_username="user_a", bk_biz_id=47), expected)

    def test_successful_map_keeps_input_order_and_default_concurrency_limit(self):
        barrier = threading.Barrier(16)
        last_ready = threading.Event()
        active, peak = 0, 0
        completed = []

        def worker(index):
            nonlocal active, peak
            with self.lock:
                active += 1
                peak = max(peak, active)
            try:
                if index < 16:
                    barrier.wait(timeout=2)
                    if index == 0:
                        self.assertTrue(last_ready.wait(timeout=2))
                with self.lock:
                    completed.append(index)
                if index == 15:
                    last_ready.set()
                return index * 2
            finally:
                with self.lock:
                    active -= 1

        self.assertEqual(metadata.bounded_read_map(worker, range(20)), list(range(0, 40, 2)))
        self.assertEqual(peak, 16)
        self.assertLess(completed.index(15), completed.index(0))
        self.assertFalse(any(thread.name.startswith("bkbase-list") for thread in threading.enumerate()))
        self.assertIsNone(sdk.READ_DEADLINE.get())

    def test_long_project_pages_share_global_16_or_32_slots_and_keep_complete_order(self):
        self.projects = ["hot_a", "hot_b"] + [f"mid_{i}" for i in range(7)] + [f"empty_{i}" for i in range(25)]
        self.rows = {
            "hot_a": [self.row(i) for i in range(899)],
            "hot_b": [self.row(i) for i in range(1000, 2751)],
            **{f"mid_{i}": [self.row(j) for j in range(3000 + i * 101, 3101 + i * 101)] for i in range(7)},
        }
        expected = sorted(
            [self.rt_id(i) for i in range(899)]
            + [self.rt_id(i) for i in range(1000, 2751)]
            + [self.rt_id(i) for i in range(3000, 3707)]
        )
        original = self.transport
        for limit in (16, 32):
            with self.subTest(limit=limit):
                self.calls.clear()
                barriers = {1: threading.Barrier(limit), 2: threading.Barrier(limit)}
                started = Counter()
                active, peak = 0, 0
                per_project, project_peak = Counter(), Counter()

                def parallel_pages(method, url, **kwargs):
                    nonlocal active, peak
                    if not url.endswith("/dataset_list/"):
                        return original(method, url, **kwargs)
                    page = kwargs["params"]["page"]
                    namespace = url.split("/dataset/", 1)[1].split("/", 1)[0]
                    phase = 1 if page == 1 else 2
                    with self.lock:
                        active += 1
                        peak = max(peak, active)
                        per_project[namespace] += 1
                        project_peak[namespace] = max(project_peak[namespace], per_project[namespace])
                        started[phase] += 1
                        ticket = started[phase]
                    try:
                        if ticket <= limit:
                            barriers[phase].wait(timeout=2)
                        return original(method, url, **kwargs)
                    finally:
                        with self.lock:
                            active -= 1
                            per_project[namespace] -= 1

                with override_settings(BKBASE_V4_LIST_READ_WORKERS=limit), mock.patch(
                    "requests.sessions.Session.request", side_effect=parallel_pages
                ):
                    result = permissions.get_project_data(project_id=1)
                self.assertEqual([row["result_table_id"] for row in result], expected)
                self.assertEqual(peak, limit)
                self.assertGreater(project_peak["hot_a"], 1)
                self.assertGreater(project_peak["hot_b"], 1)
                self.assertEqual(started, {1: 34, 2: 32})
                self.assertEqual(len({row["deadline"] for row in self.calls}), 1)
                self.assertFalse(any(thread.name.startswith("bkbase-list") for thread in threading.enumerate()))

    def test_later_page_failure_cancels_rest_and_preserves_cause_after_join(self):
        self.projects = ["long"]
        self.rows["long"] = [self.row(i) for i in range(899)]
        barrier = threading.Barrier(2)
        failed, joining = threading.Event(), threading.Event()
        entered, exited = [], []
        clock_offset = [0]
        failure = requests.ConnectionError("Synthetic later-page failure")
        original = self.transport

        class JoiningExecutor(ThreadPoolExecutor):
            def shutdown(executor, *args, **kwargs):
                if failed.is_set():
                    clock_offset[0] = 51
                    joining.set()
                return super().shutdown(*args, **kwargs)

        def later_failure(method, url, **kwargs):
            if not url.endswith("/dataset_list/") or kwargs["params"]["page"] == 1:
                return original(method, url, **kwargs)
            page = kwargs["params"]["page"]
            entered.append(page)
            try:
                barrier.wait(timeout=2)
                if page == 2:
                    failed.set()
                    raise failure
                self.assertTrue(joining.wait(timeout=2))
                return original(method, url, **kwargs)
            finally:
                exited.append(page)

        with override_settings(BKBASE_V4_LIST_READ_WORKERS=2), mock.patch.object(
            metadata, "ThreadPoolExecutor", JoiningExecutor
        ), mock.patch.object(metadata, "monotonic", side_effect=lambda: time.monotonic() + clock_offset[0]), mock.patch(
            "requests.sessions.Session.request", side_effect=later_failure
        ), self.assertRaises(
            APIRequestError
        ) as raised:
            permissions.get_project_data(project_id=1)
        self.assertIs(raised.exception.__cause__, failure)
        self.assertEqual(sorted(entered), [2, 3])
        self.assertCountEqual(exited, entered)
        self.assertFalse(any(thread.name.startswith("bkbase-list") for thread in threading.enumerate()))
        self.assertIsNone(sdk.READ_DEADLINE.get())

    def test_out_of_order_pages_keep_requested_namespace_and_page_order(self):
        self.rows["beta"] = [self.row(i) for i in range(201)]
        self.rows["alpha"] = [self.row(i) for i in range(300, 401)]
        page_three_ready = threading.Event()
        completed = []
        original = self.transport

        def reordered(method, url, **kwargs):
            page = kwargs["params"]["page"]
            namespace = url.split("/dataset/", 1)[1].split("/", 1)[0]
            if namespace == "beta" and page == 2:
                self.assertTrue(page_three_ready.wait(timeout=2))
            response = original(method, url, **kwargs)
            completed.append((namespace, page))
            if namespace == "beta" and page == 3:
                page_three_ready.set()
            return response

        with mock.patch("requests.sessions.Session.request", side_effect=reordered):
            result = metadata.list_project_datasets({"tenant": "tenant_a"}, ["beta", "alpha"])
        self.assertEqual(result, [self.rows["beta"], self.rows["alpha"]])
        self.assertLess(completed.index(("beta", 3)), completed.index(("beta", 2)))

    def test_later_pages_wait_until_all_project_first_pages_finish(self):
        self.projects = ["hot", "late"]
        self.rows["hot"] = [self.row(i) for i in range(201)]
        late_started, release_late, later_page_started = (threading.Event() for _ in range(3))
        original = self.transport

        def staged(method, url, **kwargs):
            if url.endswith("/dataset_list/"):
                namespace = url.split("/dataset/", 1)[1].split("/", 1)[0]
                if namespace == "late" and kwargs["params"]["page"] == 1:
                    late_started.set()
                    self.assertTrue(release_late.wait(timeout=2))
                if kwargs["params"]["page"] > 1:
                    later_page_started.set()
            return original(method, url, **kwargs)

        with override_settings(BKBASE_V4_LIST_READ_WORKERS=2), mock.patch(
            "requests.sessions.Session.request", side_effect=staged
        ), ThreadPoolExecutor(max_workers=1) as caller:
            pending = caller.submit(permissions.get_project_data, project_id=1)
            try:
                self.assertTrue(late_started.wait(timeout=2))
                self.assertFalse(later_page_started.wait(timeout=0.1))
            finally:
                release_late.set()
            result = pending.result(timeout=3)
        self.assertTrue(later_page_started.is_set())
        self.assertEqual([row["result_table_id"] for row in result], [self.rt_id(i) for i in range(201)])

    def test_environment_concurrency_limit_bounds_all_inflight_reads(self):
        two_started, exceeded_limit, release = (threading.Event() for _ in range(3))
        started = []

        def read(index):
            with self.lock:
                started.append(index)
                if len(started) == 2:
                    two_started.set()
                if len(started) > 2 and not release.is_set():
                    exceeded_limit.set()
            self.assertTrue(release.wait(timeout=2))
            return index

        with override_settings(BKBASE_V4_LIST_READ_WORKERS=2), ThreadPoolExecutor(max_workers=1) as caller:
            pending = caller.submit(metadata.bounded_read_map, read, range(4))
            try:
                self.assertTrue(two_started.wait(timeout=2))
                self.assertFalse(exceeded_limit.wait(timeout=0.1))
            finally:
                release.set()
            self.assertEqual(pending.result(timeout=3), [0, 1, 2, 3])

    def test_invalid_concurrency_configuration_fails_before_dispatch(self):
        for limit in (0, -1, True):
            with self.subTest(limit=limit), override_settings(BKBASE_V4_LIST_READ_WORKERS=limit):
                with self.assertRaises(ImproperlyConfigured):
                    metadata.bounded_read_map(lambda value: value, [1])

    def test_get_can_use_30_seconds_inside_unchanged_50_second_total_budget(self):
        permissions.get_project_data(project_id=1)
        self.assertTrue(self.calls)
        self.assertTrue(all(29 < row["timeout"].total <= 30 for row in self.calls))
        deadlines = {row["deadline"] for row in self.calls}
        self.assertEqual(len(deadlines), 1)
        self.assertTrue(45 < deadlines.pop() - time.monotonic() <= 50)

    def test_changed_total_or_repeated_page_fails_without_partial_tables(self):
        self.projects = ["long"]
        self.rows["long"] = [self.row(i) for i in range(201)]
        original = self.transport
        for fault in ("changed_total", "repeated_page"):
            with self.subTest(fault=fault):

                def invalid_page(method, url, **kwargs):
                    response = original(method, url, **kwargs)
                    if url.endswith("/dataset_list/") and kwargs["params"]["page"] == 2:
                        payload = response.json()
                        if fault == "changed_total":
                            payload["data"]["total"] = 101
                        else:
                            payload["data"]["list"] = [self.row(i) for i in range(100)]
                        response._content = json.dumps(payload).encode()
                    return response

                with mock.patch("requests.sessions.Session.request", side_effect=invalid_page):
                    with self.assertRaises(BKBaseResourceMappingError):
                        permissions.get_project_data(project_id=1)

    def test_failed_paginated_read_stops_new_pages_and_preserves_first_error(self):
        for deadline_during_join in (False, True):
            with self.subTest(deadline_during_join=deadline_during_join):
                self.projects = [f"failure_{i}" for i in range(8)]
                self.rows["failure_1"] = [self.row(i) for i in range(201)]
                barrier = threading.Barrier(2)
                joining = threading.Event()
                entered, exited = [], []
                clock_offset = [0]
                failure = requests.ConnectionError("Synthetic first error")
                original = self.transport

                class JoiningExecutor(ThreadPoolExecutor):
                    def shutdown(executor, *args, **kwargs):
                        # 仅控制在途响应何时返回，不替换生产调度/分页逻辑。
                        if deadline_during_join:
                            clock_offset[0] = 51
                        joining.set()
                        return super().shutdown(*args, **kwargs)

                def paginated(method, url, **kwargs):
                    if not url.endswith("/dataset_list/"):
                        return original(method, url, **kwargs)
                    namespace = url.split("/dataset/", 1)[1].split("/", 1)[0]
                    page = kwargs["params"]["page"]
                    entered.append((namespace, page))
                    try:
                        if page == 1:
                            barrier.wait(timeout=2)
                            if namespace == "failure_0":
                                raise failure
                            self.assertTrue(joining.wait(timeout=2))
                        return original(method, url, **kwargs)
                    finally:
                        exited.append((namespace, page))

                with override_settings(BKBASE_V4_LIST_READ_WORKERS=2), mock.patch.object(
                    metadata, "ThreadPoolExecutor", JoiningExecutor
                ), mock.patch.object(
                    metadata, "monotonic", side_effect=lambda: time.monotonic() + clock_offset[0]
                ), mock.patch(
                    "requests.sessions.Session.request", side_effect=paginated
                ), self.assertRaises(
                    APIRequestError
                ) as raised:
                    ListTables().request({"table_type": "MineBizRt", "bk_biz_id": 47})
                self.assertIs(raised.exception.__cause__, failure)
                self.assertEqual(sorted(entered), [("failure_0", 1), ("failure_1", 1)])
                self.assertCountEqual(exited, entered)
                self.assertFalse(any(thread.name.startswith("bkbase-list") for thread in threading.enumerate()))
                self.assertIsNone(sdk.READ_DEADLINE.get())

    def test_failed_scope_does_not_cancel_concurrent_or_next_request(self):
        barrier = threading.Barrier(2)
        failed = threading.Event()
        original = self.transport
        self.rows["success"] = [self.row(i) for i in range(201)]

        def isolated(method, url, **kwargs):
            namespace = url.split("/dataset/", 1)[1].split("/", 1)[0]
            if kwargs["params"]["page"] == 1:
                barrier.wait(timeout=2)
                if namespace == "failure":
                    raise requests.ConnectionError("Synthetic isolated failure")
                self.assertTrue(failed.wait(timeout=2))
            return original(method, url, **kwargs)

        def read(namespace):
            try:
                return metadata.bounded_read_map(
                    lambda ns: metadata.list_datasets(
                        {"tenant": "tenant_a", "namespace": ns}, user_request=self.request
                    ),
                    [namespace],
                )[0]
            finally:
                if namespace == "failure":
                    failed.set()

        with mock.patch("requests.sessions.Session.request", side_effect=isolated), ThreadPoolExecutor(2) as executor:
            bad, good = executor.submit(read, "failure"), executor.submit(read, "success")
            with self.assertRaises(APIRequestError):
                bad.result(timeout=3)
            self.assertEqual(
                [row["dataset_name"] for row in good.result(timeout=3)], [self.rt_id(i) for i in range(201)]
            )
        self.assertEqual(len(permissions.get_mine_result_tables(bk_username="user_a")), 152)
        self.assertIsNone(sdk.READ_DEADLINE.get())

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

        with override_settings(BKBASE_V4_LIST_READ_WORKERS=2), mock.patch(
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

        with mock.patch.object(metadata, "LIST_READ_BUDGET_SECONDS", 0.2), override_settings(
            BKBASE_V4_LIST_READ_WORKERS=2
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

        with override_settings(BKBASE_V4_LIST_READ_WORKERS=2), mock.patch(
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
        with mock.patch.object(table, "get_request_username", return_value="user_b"):
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
