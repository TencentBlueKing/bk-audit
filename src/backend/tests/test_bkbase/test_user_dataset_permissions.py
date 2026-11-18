"""个人权限沿真实用户读取，业务项目菜单沿配置的平台账号读取。"""
import json
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock
from urllib.parse import urlparse

import requests
from bk_resource.exceptions import APIRequestError
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, SimpleTestCase, override_settings

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
    APP_CODE="synthetic_app",
    SECRET_KEY="synthetic_secret",
    BK_RESOURCE={
        "PLATFORM_AUTH_ENABLED": True,
        "PLATFORM_AUTH_ACCESS_USERNAME": "synthetic_admin",
        "PLATFORM_AUTH_ACCESS_TOKEN": "synthetic-platform-token",
    },
)
class UserDatasetPermissionTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get("/synthetic/")
        self.request.user = SimpleNamespace(bk_username="synthetic_user", is_authenticated=True)
        self.context = {
            "version": "v4",
            "tenant": "tenant_a",
            "namespace": "audit",
            "user": "synthetic_user",
            "request": self.request,
        }
        self.calls = []
        self.projects = [self.project("alpha"), self.project("beta"), self.project("deleted", phase="Terminating")]
        page = [
            self.row("7_alpha", "doris"),
            self.row("7_denied", query=False),
            self.row("7_missing", query=None),
            self.row("7_string", query="true"),
            self.row("8_beta", "hdfs"),
        ]
        page += [self.row(f"0_denied_{i}", query=False) for i in range(95)]
        self.pages = {
            ("alpha", 1): {"list": page, "total": 101, "pages_num": 101},
            ("alpha", 2): {"list": [self.row("7_alpha", "hdfs")], "total": 101, "pages_num": 101},
            ("beta", 1): {
                "list": [self.row("7_alpha", "redis"), self.row("9_gamma"), self.row("8_beta", "channel")],
                "total": 3,
                "pages_num": 3,
            },
        }
        self.enterContext(mock.patch("requests.sessions.Session.request", side_effect=self.transport))
        self.auth = self.enterContext(
            mock.patch.object(
                sdk.UserBkBaseV4Resource, "build_auth_args", return_value={"bk_token": "synthetic-user-token"}
            )
        )
        self.enterContext(mock.patch("services.web.bkbase.common.get_local_request", return_value=self.request))
        self.enterContext(mock.patch.object(table, "get_request_username", return_value="synthetic_user"))
        self.spaces = self.enterContext(
            mock.patch.object(
                table.resource.meta,
                "get_spaces_mine",
                return_value=[
                    {"id": "7", "name": "Business seven", "space_type_id": SpaceType.BIZ.value},
                    {"id": "8", "name": "Business eight", "space_type_id": SpaceType.BIZ.value},
                    {"id": "9", "name": "Business nine", "space_type_id": SpaceType.BIZ.value},
                    {"id": "10", "name": "No query table", "space_type_id": SpaceType.BIZ.value},
                ],
            )
        )
        for name in ("user_scopes", "user_result_tables", "user_check"):
            self.enterContext(
                mock.patch.object(permissions.api.bk_base_v4, name, side_effect=AssertionError("legacy MCP called"))
            )

    @staticmethod
    def project(name, *, phase="Ok"):
        return {
            "kind": "Namespace",
            "metadata": {"tenant": "tenant_a", "namespace": "bkbase", "name": name},
            "spec": {"name": name, "alias": "Project alias is not business name"},
            "status": {"phase": phase},
        }

    @staticmethod
    def row(logical, storage="doris", *, query=True):
        value = {
            "dataset_name": logical,
            "dataset_alias": "Synthetic " + logical,
            "storage_type": storage,
            "permissions": {"view": True},
        }
        if query is not None:
            value["permissions"]["query"] = query
        return value

    def transport(self, method, url, **kwargs):
        path = urlparse(url).path
        auth = json.loads(kwargs["headers"]["x-bkapi-authorization"])
        self.assertEqual(method, "GET")
        if auth.get("bk_username") == "synthetic_admin":
            self.assertEqual(auth["access_token"], "synthetic-platform-token")
            self.assertNotIn("bk_token", auth)
            self.assertNotIn("cookie", {key.lower() for key in kwargs["headers"]})
        else:
            self.assertEqual(auth["bk_username"], "synthetic_user")
            self.assertEqual(auth["bk_token"], "synthetic-user-token")
        self.assertEqual(kwargs["headers"]["X-Bk-Tenant-Id"], "tenant_a")
        self.assertNotIn("json", kwargs)
        params = kwargs.get("params", {})
        self.assertNotIn("_request", params)
        self.assertNotIn("tenant", params)
        self.calls.append({"path": path, "params": deepcopy(params)})
        if path.endswith("/v4/tenants/tenant_a/namespaces"):
            self.assertEqual(params, {})
            data = deepcopy(self.projects)
        elif "/v4/databus/dataset/" in path and path.endswith("/dataset_list/"):
            namespace = path.split("/dataset/", 1)[1].split("/", 1)[0]
            self.assertEqual(params["page_size"], 100)
            data = deepcopy(self.pages[(namespace, params["page"])])
            if isinstance(data, Exception):
                raise data
        else:
            self.fail("unexpected endpoint " + path)
        response = requests.Response()
        response.status_code = 200
        response.url = url
        response.request = requests.Request(method, url).prepare()
        response._content = json.dumps({"result": True, "code": "00", "data": data}).encode()
        return response

    def test_formal_sdk_user_identity_all_pages_deduplicate_and_filter_business(self):
        rows = permissions.list_user_rts(self.context)
        self.assertEqual([r["result_table_id"] for r in rows], ["7_alpha", "8_beta", "9_gamma"])
        self.assertEqual(set(rows[0]["storages"]), {"doris", "hdfs", "redis"})
        self.assertCountEqual([c["params"].get("page") for c in self.calls], [None, 1, 2, 1])
        self.assertEqual([c["params"]["page"] for c in self.calls if "/dataset/alpha/" in c["path"]], [1, 2])
        self.assertTrue(all(c.args[0] is self.request for c in self.auth.call_args_list))
        self.calls.clear()
        self.assertEqual(
            [r["result_table_id"] for r in permissions.list_user_rts(self.context, bk_biz_id=7)], ["7_alpha"]
        )
        self.assertEqual(len(self.calls), 4)

    def test_permission_check_requires_query_true_and_complete_traversal(self):
        self.assertTrue(permissions.check_user_rt(self.context, rt_id="7_alpha"))
        for logical in ("7_denied", "7_missing", "7_string", "7_absent"):
            with self.subTest(logical=logical):
                self.assertFalse(permissions.check_user_rt(self.context, rt_id=logical))
        self.pages[("alpha", 2)] = requests.Timeout("synthetic page failure")
        with self.assertRaises(BKBaseReadTimeout) as raised:
            permissions.check_user_rt(self.context, rt_id="7_alpha")
        self.assertEqual(raised.exception.STATUS_CODE, 504)

    def test_biz_menu_comes_from_queryable_tables_and_real_business_names(self):
        self.assertEqual(
            permissions.list_user_bizs(self.context),
            [
                {"bk_biz_id": 7, "bk_biz_name": "Business seven"},
                {"bk_biz_id": 8, "bk_biz_name": "Business eight"},
                {"bk_biz_id": 9, "bk_biz_name": "Business nine"},
            ],
        )
        self.assertNotIn("Project alias", str(permissions.list_user_bizs(self.context)))

    def test_real_list_tables_request_and_project_asset_menu_are_connected(self):
        with mock.patch.object(ListTables, "cache_type", None):
            menu = ListTables().request({"table_type": "MineBizRt", "bk_biz_id": 7})
        self.assertEqual(menu, [{"label": "Synthetic 7_alpha", "value": "7_alpha"}])
        with mock.patch.object(
            metadata,
            "get_result_table",
            side_effect=lambda logical, **kwargs: {
                "result_table_id": logical,
                "bk_biz_id": int(logical.split("_", 1)[0]),
                "result_table_name": "Synthetic " + logical,
                "storages": {"doris": {"storage_type": "doris"}},
            },
        ), mock.patch.object(
            metadata,
            "get_source_capabilities",
            side_effect=lambda rt_id, **kwargs: {
                "7_alpha": {"redis": True, "channel": False, "hdfs_dimensions": [True], "hdfs_unknown": False},
                "8_beta": {"redis": False, "channel": False, "hdfs_dimensions": [False], "hdfs_unknown": False},
                "9_gamma": {"redis": False, "channel": True, "hdfs_dimensions": [], "hdfs_unknown": False},
            }[rt_id],
        ):
            assets = table.BizAssetTableHandler("BizAsset").list_tables()
            with mock.patch.object(ListTables, "cache_type", None), mock.patch.object(
                table.BizRtTableHandler, "get_exclude_rt_ids", return_value=[]
            ):
                tables = ListTables().request({"table_type": "BizRt", "namespace": "audit"})
            self.assertEqual(
                [child["value"] for group in tables for child in group["children"]], ["7_alpha", "8_beta", "9_gamma"]
            )
        self.assertEqual([child["value"] for group in assets for child in group["children"]], ["7_alpha"])

    def test_invalid_project_scope_or_pagination_fails_without_partial_access(self):
        self.projects[0]["metadata"]["tenant"] = "tenant_other"
        with self.assertRaises(BKBaseResourceMappingError):
            permissions.list_user_rts(self.context)
        self.assertEqual(len(self.calls), 1)
        self.projects[0]["metadata"]["tenant"] = "tenant_a"
        self.pages[("alpha", 2)] = {"list": [], "pages_num": 101}
        with self.assertRaises(BKBaseResourceMappingError):
            permissions.check_user_rt(self.context, rt_id="7_alpha")

    def test_v4_actual_mine_menu_propagates_permission_and_http_failures(self):
        for error in (
            PermissionDenied("synthetic denied"),
            APIRequestError(module_name="bkbase_v4", url="/v4/tenants/", result="synthetic failure"),
        ):
            with self.subTest(error=type(error).__name__), mock.patch.object(
                permissions, "get_bizs_list", side_effect=error
            ):
                with self.assertRaises(type(error)):
                    table.MineBizRtTableHandler("MineBizRt").list_tables()
                with mock.patch.object(ListTables, "cache_type", None), self.assertRaises(type(error)):
                    ListTables().request({"table_type": "MineBizRt"})

    def test_no_request_or_mismatched_user_never_uses_platform(self):
        for context in (
            {**self.context, "user": "another_user"},
            {**self.context, "request": None},
            {**self.context, "user": None},
        ):
            with self.subTest(user=context["user"]), self.assertRaises(PermissionDenied):
                permissions.list_user_rts(context)
        self.assertFalse(self.calls)

    def test_owner_check_does_not_reuse_personal_project_or_dataset_listing(self):
        for owner in ("synthetic_user", "other_user"):
            with self.subTest(owner=owner), mock.patch.object(
                permissions.api.bk_base_v4, "direct_auth_by_resources", return_value=[]
            ) as check:
                self.assertEqual(
                    permissions.check_owner_result_tables(
                        self.context, permissions=[{"user_id": owner, "object_id": "7_alpha"}]
                    ),
                    [{"user_id": owner, "object_id": "7_alpha", "result": False}],
                )
                self.assertEqual(check.call_args.kwargs["user_id"], owner)
        self.assertFalse(self.calls)

    def test_empty_projects_and_missing_query_permission_never_select_a_table(self):
        self.projects = []
        self.assertEqual(permissions.list_user_rts(self.context), [])
        self.assertFalse(permissions.check_user_rt(self.context, rt_id="7_alpha"))
        self.assertTrue(all(call["path"].endswith("/namespaces") for call in self.calls))
        self.projects = [self.project("alpha")]
        rows = [self.row("7_one", query=None), self.row("7_two", query=1), self.row("7_three", query=False)]
        rows[0].pop("permissions")
        self.pages[("alpha", 1)] = {"list": rows, "total": 3, "pages_num": 3}
        self.assertEqual(permissions.list_user_rts(self.context), [])

    def test_non_query_action_cannot_reuse_query_permission(self):
        with self.assertRaises(BKBaseResourceMappingError):
            permissions.user_auth_check(user_id="synthetic_user", object_id="7_alpha", action_id="result_table.manage")
        self.assertFalse(self.calls)

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_wrappers_keep_original_apis_and_payloads(self):
        cases = [
            (permissions.get_bizs_list, "get_bizs_list", {"bk_username": "synthetic_user"}),
            (permissions.get_mine_result_tables, "get_mine_result_tables", {"bk_biz_id": 7}),
            (permissions.get_project_data, "get_project_data", {"project_id": 12, "extra_fields": True}),
            (permissions.user_auth_check, "user_auth_check", {"user_id": "synthetic_user", "object_id": "7_alpha"}),
        ]
        for call, name, payload in cases:
            with self.subTest(name=name), mock.patch.object(
                permissions.api.bk_base, name, return_value={"original": True}
            ) as legacy:
                self.assertEqual(call(**payload), {"original": True})
                legacy.assert_called_once_with(**payload)
        self.assertFalse(self.calls)

    def test_v4_selected_business_menu_enumerates_datasets_once_without_biz_list(self):
        with mock.patch.object(ListTables, "cache_type", None):
            result = ListTables().request({"table_type": "MineBizRt", "bk_biz_id": 7})
        self.assertEqual(result, [{"label": "Synthetic 7_alpha", "value": "7_alpha"}])
        self.assertCountEqual([call["params"].get("page") for call in self.calls], [None, 1, 2, 1])
        self.assertEqual(len({(call["path"], call["params"].get("page")) for call in self.calls}), 4)
        self.spaces.assert_not_called()
        self.assertTrue(all(call.args[0] is self.request for call in self.auth.call_args_list))

    def test_v4_selected_business_still_propagates_dataset_errors(self):
        error = APIRequestError(module_name="bkbase_v4", url="/v4/databus/dataset/", result="synthetic failure")
        self.pages[("alpha", 2)] = error
        with mock.patch.object(ListTables, "cache_type", None), self.assertRaises(APIRequestError):
            ListTables().request({"table_type": "MineBizRt", "bk_biz_id": 7})
        self.spaces.assert_not_called()

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_selected_business_keeps_biz_list_precheck_and_legacy_payload(self):
        rows = {"data": [{"result_table_id": "7_alpha", "result_table_name": "Legacy alpha"}]}
        with mock.patch.object(permissions, "get_bizs_list", return_value=[]) as bizs, mock.patch.object(
            permissions, "get_mine_result_tables", return_value=rows
        ) as tables, mock.patch.object(ListTables, "cache_type", None):
            self.assertEqual(
                ListTables().request({"table_type": "MineBizRt", "bk_biz_id": 7}),
                [{"label": "Legacy alpha", "value": "7_alpha"}],
            )
        bizs.assert_called_once_with(
            bk_username="synthetic_user",
            action_id=table.UserAuthActionEnum.RT_QUERY,
            dimension=table.AUTH_DIMENSION_BIZ,
        )
        tables.assert_called_once_with(
            {"bk_username": "synthetic_user", "action_id": table.UserAuthActionEnum.RT_QUERY.value, "bk_biz_id": "7"}
        )
        self.assertFalse(self.calls)

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_selected_business_keeps_invalid_biz_list_and_error_empty_response(self):
        for value in (None, {"data": []}, PermissionDenied("synthetic denied")):
            with self.subTest(value=type(value).__name__), mock.patch.object(
                permissions,
                "get_bizs_list",
                **({"side_effect": value} if isinstance(value, Exception) else {"return_value": value}),
            ), mock.patch.object(permissions, "get_mine_result_tables") as tables, mock.patch.object(
                ListTables, "cache_type", None
            ):
                self.assertEqual(ListTables().request({"table_type": "MineBizRt", "bk_biz_id": 7}), [])
                tables.assert_not_called()
        self.assertFalse(self.calls)
