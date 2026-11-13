"""真实工具权限入口先核负责人，再以平台身份 Query；外部传输全部模拟。"""
import json
from unittest import mock

import requests
from bk_resource.exceptions import APIRequestError, ValidateException
from django.test import SimpleTestCase, override_settings

from core.sql.parser.praser import SqlQueryAnalysis
from services.web.bkbase import permissions
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.tool.constants import DataSearchConfigTypeEnum, ToolTypeEnum
from services.web.tool.exceptions import DataSearchTablePermission
from services.web.tool.executor.tool import SqlDataSearchExecutor
from services.web.tool.models import DataSearchToolConfig, Tool
from services.web.tool.resources import (
    SqlAnalyseResource,
    SqlAnalyseWithToolResource,
    ToolExecuteDebug,
    UserQueryTableAuthCheck,
)


@override_settings(
    BKBASE_API_VERSION="v4",
    BKBASE_V4_TENANT="tenant_a",
    BKBASE_V4_NAMESPACE="audit",
    APP_CODE="synthetic_app",
    SECRET_KEY="synthetic_secret",
    BK_RESOURCE={
        "PLATFORM_AUTH_ENABLED": True,
        "PLATFORM_AUTH_ACCESS_USERNAME": "platform_user",
        "PLATFORM_AUTH_ACCESS_TOKEN": "synthetic-platform-token",
    },
)
class OwnerQueryPermissionTests(SimpleTestCase):
    sql = "SELECT a.id FROM `7_alpha` a JOIN `8_beta` b ON a.id = b.id"

    def setUp(self):
        self.rows = [{"resource_id": name, "allowed": True} for name in ("7_alpha", "8_beta")]
        self.failure = None
        self.metadata_modes = {}
        self.diagnostics = {}
        self.calls = []
        self.tool = Tool(
            uid="synthetic_tool",
            namespace="audit",
            name="Synthetic",
            tool_type=ToolTypeEnum.DATA_SEARCH,
            permission_owner="owner",
            config={"sql": self.sql, "referenced_tables": [], "input_variable": [], "output_fields": []},
        )
        self.tool.data_search_config = DataSearchToolConfig(
            sql=self.sql, data_search_config_type=DataSearchConfigTypeEnum.SQL
        )
        self.enterContext(mock.patch("requests.sessions.Session.request", side_effect=self.transport))
        self.enterContext(mock.patch("services.web.tool.executor.tool.get_request_username", return_value="caller"))
        self.enterContext(mock.patch("services.web.tool.resources.get_request_username", return_value="caller"))
        self.scene = self.enterContext(
            mock.patch.object(SqlDataSearchExecutor, "_get_tool_scene_id", return_value=None)
        )
        self.enterContext(mock.patch.object(permissions, "list_user_rts", side_effect=AssertionError("Wrong identity")))

    def transport(self, method, url, **kwargs):
        self.calls.append((url, kwargs))
        status_code = 200
        if url.endswith("/v4/auth/users/direct_auth_by_resources/"):
            self.assertEqual(method, "POST")
            if self.failure:
                raise self.failure
            payload = {"result": True, "code": "00", "data": self.rows}
            payload.update(self.diagnostics)
        elif "/v4/result_tables/" in url:
            self.assertEqual(method, "GET")
            logical_id = url.rstrip("/").rsplit("/", 1)[1]
            mode = self.metadata_modes.get(logical_id)
            if mode == "timeout":
                raise requests.Timeout("synthetic metadata timeout")
            resource = {
                "kind": "ResultTable",
                "metadata": {"tenant": "tenant_a", "namespace": "inputs", "name": "native_" + logical_id},
                "spec": {"predefiendResultTableId": logical_id},
            }
            if mode == "wrong_tenant":
                resource["metadata"]["tenant"] = "tenant_b"
            elif mode == "wrong_logical_id":
                resource["spec"]["predefiendResultTableId"] = "9_other"
            elif mode == "wrong_kind":
                resource["kind"] = "DataSource"
            payload = {"result": True, "code": "00", "data": resource}
            if mode in ("missing", "missing_envelope", "denied"):
                status_code = {"missing": 404, "missing_envelope": 200, "denied": 403}[mode]
                payload = {"result": False, "code": "1558025" if mode != "denied" else "1500001", "data": None}
        else:
            self.assertEqual(method, "POST")
            self.assertTrue(url.endswith("/v4/queryengine/user/query_sync/"), url)
            is_count = "COUNT(" in kwargs["json"]["sql"].upper()
            payload = {"result": True, "code": "00", "data": {"list": [{"count": 1}] if is_count else [{"id": 1}]}}
        response = requests.Response()
        response.status_code = status_code
        response.url = url
        response.request = requests.Request(method, url).prepare()
        response._content = json.dumps(payload).encode()
        return response

    def execute(self):
        return SqlDataSearchExecutor(self.tool, SqlQueryAnalysis).execute({"tool_variables": [], "page_size": 10})

    def auth_calls(self):
        return [call for call in self.calls if "/direct_auth_by_resources/" in call[0]]

    def query_calls(self):
        return [call for call in self.calls if "/query_sync/" in call[0]]

    def metadata_calls(self):
        return [call for call in self.calls if "/v4/result_tables/" in call[0]]

    def test_owner_same_or_different_from_caller_uses_same_check_then_platform_query(self):
        for owner in ("caller", "owner", "admin"):
            with self.subTest(owner=owner):
                self.calls.clear()
                self.tool.permission_owner = owner
                self.rows.reverse()  # 响应顺序不能决定 RT 授权映射。
                result = self.execute()
                self.assertEqual(result.results, [{"id": 1}])
                self.assertEqual(result.total, 1)
                self.assertEqual(len(self.auth_calls()), 1)
                _, check = self.auth_calls()[0]
                self.assertEqual(check["json"]["user_id"], owner)
                self.assertEqual(set(check["json"]["resource_ids"]), {"7_alpha", "8_beta"})
                auth = json.loads(check["headers"]["x-bkapi-authorization"])
                self.assertEqual(auth, {"bk_app_code": "synthetic_app", "bk_app_secret": "synthetic_secret"})
                self.assertIsNone(check["json"]["parent_resource_id"])
                self.assertEqual(len(self.metadata_calls()), 2)
                self.assertEqual(
                    {url.rstrip("/").rsplit("/", 1)[1] for url, _ in self.metadata_calls()}, {"7_alpha", "8_beta"}
                )
                for _, metadata_call in self.metadata_calls():
                    self.assertEqual(metadata_call["headers"]["X-Bk-Tenant-Id"], "tenant_a")
                self.assertEqual(len(self.query_calls()), 2)
                for _, query in self.metadata_calls() + self.query_calls():
                    identity = json.loads(query["headers"]["x-bkapi-authorization"])
                    self.assertEqual(identity["bk_username"], "platform_user")
                    self.assertEqual(identity["access_token"], "synthetic-platform-token")
                self.assertIn("/direct_auth_by_resources/", self.calls[0][0])

    def test_authorized_admin_with_missing_invalid_or_unreadable_rt_never_queries(self):
        self.tool.permission_owner = "admin"
        for mode in (
            "missing",
            "missing_envelope",
            "denied",
            "timeout",
            "wrong_tenant",
            "wrong_logical_id",
            "wrong_kind",
        ):
            self.calls.clear()
            self.metadata_modes = {"7_alpha": mode}
            with self.subTest(mode=mode), self.assertRaises((APIRequestError, BKBaseResourceMappingError)):
                self.execute()
            self.assertEqual(len(self.auth_calls()), 1)
            self.assertEqual(self.query_calls(), [])

    def test_one_missing_table_after_other_table_exists_blocks_both_queries(self):
        self.metadata_modes = {"8_beta": "missing"}
        with self.assertRaises(APIRequestError):
            self.execute()
        self.assertEqual(len(self.metadata_calls()), 2)
        self.assertEqual(self.query_calls(), [])

    def test_unsaved_preview_requires_rt_existence_before_platform_query(self):
        self.metadata_modes = {"8_beta": "missing"}
        with self.assertRaises(APIRequestError):
            ToolExecuteDebug().request(
                tool_type=ToolTypeEnum.DATA_SEARCH,
                config=self.tool.config,
                params={"tool_variables": [], "page_size": 10},
            )
        self.assertEqual(self.auth_calls()[0][1]["json"]["user_id"], "caller")
        self.assertEqual(self.query_calls(), [])

    def test_duplicate_resources_are_checked_once_without_losing_response_order(self):
        self.rows = [{"resource_id": "7_alpha", "allowed": True}]
        result = UserQueryTableAuthCheck().request(tables=["7_alpha", "7_alpha"], username="owner")
        self.assertEqual(result, [{"user_id": "owner", "object_id": "7_alpha", "result": True}] * 2)
        self.assertEqual(len(self.metadata_calls()), 1)
        self.assertEqual(self.query_calls(), [])

    def test_metadata_existence_is_rechecked_on_each_separate_call(self):
        self.execute()
        self.calls.clear()
        self.metadata_modes = {"7_alpha": "missing"}
        with self.assertRaises(APIRequestError):
            self.execute()
        self.assertEqual(len(self.metadata_calls()), 1)
        self.assertEqual(self.query_calls(), [])

    def test_denial_partial_denial_missing_and_empty_results_prevent_all_query(self):
        for rows in (
            [{"resource_id": "7_alpha", "allowed": False}, {"resource_id": "8_beta", "allowed": False}],
            [{"resource_id": "7_alpha", "allowed": True}, {"resource_id": "8_beta", "allowed": False}],
            [{"resource_id": "7_alpha", "allowed": True}],
            [],
        ):
            with self.subTest(rows=rows):
                self.calls.clear()
                self.rows = rows
                with self.assertRaises(DataSearchTablePermission) as caught:
                    self.execute()
                self.assertIn("owner", str(caught.exception))
                self.assertEqual(self.query_calls(), [])
                expected_metadata = {row["resource_id"] for row in rows if row["allowed"] is True}
                self.assertEqual(
                    {url.rstrip("/").rsplit("/", 1)[1] for url, _ in self.metadata_calls()}, expected_metadata
                )

    def test_api_failure_invalid_and_ambiguous_rows_never_reach_query(self):
        for rows in (
            [{"resource_id": "7_alpha", "allowed": "true"}],
            [{"resource_id": "7_alpha", "allowed": True}, {"resource_id": "7_alpha", "allowed": False}],
            [{"resource_id": "unexpected", "allowed": True}],
            None,
        ):
            with self.subTest(rows=rows):
                self.calls.clear()
                self.rows = rows
                with self.assertRaises((ValidateException, BKBaseResourceMappingError)):
                    self.execute()
                self.assertEqual(self.query_calls(), [])
        self.failure = requests.Timeout("synthetic authorization timeout")
        self.calls.clear()
        with self.assertRaises(APIRequestError):
            self.execute()
        self.assertEqual(self.query_calls(), [])

    def test_existing_scene_exemption_filters_only_authorized_tables(self):
        self.scene.return_value = 123
        self.rows = [{"resource_id": "8_beta", "allowed": True}]
        with mock.patch("services.web.tool.executor.tool.SceneDataFilter.get_table_ids", return_value=["7_alpha"]):
            self.execute()
        self.assertEqual(self.auth_calls()[0][1]["json"]["resource_ids"], ["8_beta"])
        self.assertEqual(len(self.metadata_calls()), 1)
        self.assertTrue(self.metadata_calls()[0][0].endswith("/8_beta/"))
        self.assertEqual(len(self.query_calls()), 2)
        self.rows = [{"resource_id": "8_beta", "allowed": False}]
        self.calls.clear()
        with mock.patch("services.web.tool.executor.tool.SceneDataFilter.get_table_ids", return_value=["7_alpha"]):
            with self.assertRaises(DataSearchTablePermission):
                self.execute()
        self.assertEqual(self.query_calls(), [])

    def test_conflicting_success_diagnostics_prevent_query(self):
        for diagnostics in ({"message": "failure"}, {"errors": {}}, {"messages": {}}):
            with self.subTest(diagnostics=diagnostics):
                self.calls.clear()
                self.diagnostics = diagnostics
                with self.assertRaises(APIRequestError):
                    self.execute()
                self.assertEqual(self.query_calls(), [])

    def test_all_scene_tables_and_legitimate_empty_check_sets_remain_exempt(self):
        self.scene.return_value = 123
        with mock.patch(
            "services.web.tool.executor.tool.SceneDataFilter.get_table_ids", return_value=["7_alpha", "8_beta"]
        ):
            self.execute()
        self.assertEqual(self.auth_calls(), [])
        self.assertEqual(self.metadata_calls(), [])
        self.assertEqual(len(self.query_calls()), 2)
        self.calls.clear()
        self.assertEqual(UserQueryTableAuthCheck().request(tables=[], username="owner"), [])
        self.assertEqual(self.calls, [])
        self.tool.config["sql"] = "SELECT 1 AS id"
        self.execute()
        self.assertEqual(self.auth_calls(), [])
        self.assertEqual(len(self.query_calls()), 2)

    def test_user_check_and_save_edit_analysis_keep_original_response_and_owner_choice(self):
        expected = [{"user_id": "owner", "object_id": "7_alpha", "result": True}]
        self.rows = [{"resource_id": "7_alpha", "allowed": True}]
        self.assertEqual(UserQueryTableAuthCheck().request(tables=["7_alpha"], username="owner"), expected)
        for endpoint in (SqlAnalyseResource(), SqlAnalyseWithToolResource()):
            with self.subTest(endpoint=type(endpoint).__name__), mock.patch.object(
                Tool, "last_version_tool", return_value=self.tool
            ):
                self.calls.clear()
                result = endpoint.request(sql="SELECT id FROM `7_alpha`", uid=self.tool.uid, with_permission=True)
                owner = "owner" if isinstance(endpoint, SqlAnalyseWithToolResource) else "caller"
                self.assertEqual(result["referenced_tables"][0]["permission"], {**expected[0], "user_id": owner})
                self.assertEqual(self.auth_calls()[0][1]["json"]["user_id"], owner)
                self.assertEqual(self.query_calls(), [])

    def test_v3_batch_check_remains_an_unchanged_delegation(self):
        request = {
            "permissions": [{"user_id": "owner", "object_id": "legacy_rt", "action_id": "result_table.query_data"}]
        }
        legacy = [{"user_id": "owner", "object_id": "legacy_rt", "result": True}]
        with override_settings(BKBASE_API_VERSION="v3"), mock.patch.object(
            permissions.api.bk_base, "user_auth_batch_check", return_value=legacy
        ) as check:
            self.assertEqual(permissions.user_auth_batch_check(request), legacy)
        check.assert_called_once_with(**request)
        self.assertEqual(self.calls, [])

    def test_background_batch_groups_owners_and_preserves_input_order_and_duplicates(self):
        request = [
            {"user_id": owner, "object_id": table, "action_id": "result_table.query_data"}
            for owner, table in (
                ("owner_a", "7_alpha"),
                ("owner_b", "8_beta"),
                ("owner_a", "7_alpha"),
                ("owner_b", "7_alpha"),
            )
        ]
        with mock.patch.object(
            permissions.api.bk_base_v4,
            "direct_auth_by_resources",
            side_effect=lambda **params: [{"resource_id": rt_id, "allowed": True} for rt_id in params["resource_ids"]],
        ) as check:
            result = permissions.check_owner_result_tables({"request": None, "tenant": "tenant_a"}, permissions=request)
        self.assertEqual(
            result, [{"user_id": row["user_id"], "object_id": row["object_id"], "result": True} for row in request]
        )
        self.assertEqual(check.call_count, 2)
        self.assertEqual(check.call_args_list[0].kwargs["resource_ids"], ["7_alpha"])
        self.assertEqual(len(self.metadata_calls()), 2)
        self.assertEqual(self.query_calls(), [])

    def test_invalid_owner_action_or_resource_does_not_create_an_empty_permission_bypass(self):
        for request in (
            None,
            [None],
            [{"user_id": "", "object_id": "7_alpha"}],
            [{"user_id": "owner", "object_id": "*"}],
            [{"user_id": "owner", "object_id": "7_alpha|other"}],
            [{"user_id": "owner", "object_id": "7_alpha", "action_id": "edit_dataset"}],
        ):
            with self.subTest(request=request), self.assertRaises(BKBaseResourceMappingError):
                permissions.check_owner_result_tables({}, permissions=request)
        self.assertEqual(self.calls, [])

    def test_preview_without_saved_tool_checks_caller_before_platform_query(self):
        endpoint = ToolExecuteDebug()
        request = {
            "tool_type": ToolTypeEnum.DATA_SEARCH,
            "config": self.tool.config,
            "params": {"tool_variables": [], "page_size": 10},
        }
        result = endpoint.request(request)
        self.assertEqual(result["data"]["results"], [{"id": 1}])
        self.assertEqual(self.auth_calls()[0][1]["json"]["user_id"], "caller")
        self.assertEqual(len(self.query_calls()), 2)
        self.rows = []
        self.calls.clear()
        with self.assertRaises(DataSearchTablePermission):
            endpoint.request(request)
        self.assertEqual(self.query_calls(), [])

    def test_edit_with_new_table_keeps_v3_choice_of_current_editor_as_owner(self):
        self.rows = [{"resource_id": "9_new", "allowed": True}]
        with mock.patch.object(Tool, "last_version_tool", return_value=self.tool):
            result = SqlAnalyseWithToolResource().request(
                sql="SELECT id FROM `9_new`", uid=self.tool.uid, with_permission=True
            )
        self.assertEqual(self.auth_calls()[0][1]["json"]["user_id"], "caller")
        self.assertEqual(result["referenced_tables"][0]["permission"]["user_id"], "caller")
        self.assertEqual(self.query_calls(), [])
