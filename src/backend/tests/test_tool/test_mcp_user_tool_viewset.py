# -*- coding: utf-8 -*-
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, override_settings
from django.urls import resolve
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.permission.handlers.drf import AnyOfPermissions
from core.permissions import UserAPIGWPermission
from services.web.scene.constants import PanelStatus
from services.web.tool.constants import ToolTypeEnum
from services.web.tool.exceptions import (
    BkbaseApiRequestError,
    DataSearchTablePermission,
    ToolDoesNotExist,
    ToolNotPublished,
)
from services.web.tool.models import Tool
from services.web.tool.permissions import UseToolPermission
from services.web.tool.resources import (
    ExecuteTool,
    GetMCPToolDetailByName,
    MCPExecuteTool,
)
from services.web.tool.serializers import ExecuteToolRespSerializer
from services.web.tool.views import MCPUserToolViewSet, ToolViewSet
from tests.base import TestCase


@override_settings(ROOT_URLCONF="services.web.urls")
class TestMCPUserToolRouting(SimpleTestCase):
    def test_routes_resolve_to_user_viewset(self):
        self.assertIs(
            resolve("/api/v1/namespaces/default/mcp_user/tool/tool-1/execute/").func.cls,
            MCPUserToolViewSet,
        )
        self.assertIs(
            resolve("/api/v1/namespaces/default/mcp_user/tool/detail_by_name/").func.cls,
            MCPUserToolViewSet,
        )


class TestMCPUserToolViewSet(SimpleTestCase):
    def test_execute_keeps_caller_context_or_use_tool_permission(self):
        viewset = MCPUserToolViewSet()
        viewset.action = "execute"

        permissions = viewset.get_permissions()

        self.assertIsInstance(permissions[0], UserAPIGWPermission)
        self.assertIsInstance(permissions[1], AnyOfPermissions)

    def test_execute_uses_mcp_safe_response_resource(self):
        route = next(route for route in MCPUserToolViewSet.resource_routes if route.endpoint == "execute")

        self.assertEqual(route.resource_class.__name__, "MCPExecuteTool")

    def test_detail_by_name_uses_mcp_namespace_resource(self):
        route = next(route for route in MCPUserToolViewSet.resource_routes if route.endpoint == "detail_by_name")

        self.assertEqual(route.resource_class.__name__, "GetMCPToolDetailByName")

    def test_mcp_execute_uses_standard_response_serializer(self):
        self.assertIs(MCPExecuteTool.ResponseSerializer, ExecuteToolRespSerializer)

    @mock.patch.object(ExecuteTool, "perform_request")
    def test_mcp_execute_hides_data_search_sql(self, mock_perform_request):
        mock_perform_request.return_value = {
            "tool_type": ToolTypeEnum.DATA_SEARCH.value,
            "data": {
                "page": 1,
                "num_pages": 1,
                "total": 1,
                "results": [{"risk_id": "risk-1"}],
                "query_sql": "SELECT * FROM sensitive_table",
                "count_sql": "SELECT COUNT(*) FROM sensitive_table",
            },
        }
        response = MCPExecuteTool().perform_request({"uid": "tool-1", "params": {}})

        self.assertNotIn("query_sql", response["data"])
        self.assertNotIn("count_sql", response["data"])

    @mock.patch.object(ExecuteTool, "perform_request")
    def test_mcp_execute_hides_smart_page_rendered_sql(self, mock_perform_request):
        mock_perform_request.return_value = {
            "tool_type": ToolTypeEnum.SMART_PAGE.value,
            "data": {"result": {"rendered_sql": "SELECT * FROM sensitive_table", "results": []}},
        }
        response = MCPExecuteTool().perform_request({"uid": "tool-1", "params": {}})

        self.assertNotIn("rendered_sql", response["data"]["result"])

    def test_mcp_execute_keeps_bkbase_error_detail(self):
        with mock.patch.object(
            ExecuteTool,
            "perform_request",
            side_effect=BkbaseApiRequestError("SELECT * FROM sensitive_table"),
        ):
            with self.assertRaises(BkbaseApiRequestError) as ctx:
                MCPExecuteTool().perform_request({"uid": "tool-1", "params": {}})

        self.assertIn("SELECT * FROM sensitive_table", str(ctx.exception))

    def test_mcp_execute_keeps_table_permission_error_detail(self):
        with mock.patch.object(
            ExecuteTool,
            "perform_request",
            side_effect=DataSearchTablePermission("alice", "sensitive_table"),
        ):
            with self.assertRaises(DataSearchTablePermission) as ctx:
                MCPExecuteTool().perform_request({"uid": "tool-1", "params": {}})

        self.assertIn("alice", str(ctx.exception))
        self.assertIn("sensitive_table", str(ctx.exception))

    def test_detail_by_name_reuses_use_tool_permission(self):
        viewset = MCPUserToolViewSet()
        viewset.action = "detail_by_name"

        permissions = viewset.get_permissions()

        self.assertIsInstance(permissions[1], UseToolPermission)
        self.assertIs(type(permissions[1]), UseToolPermission)

    def test_tool_not_published_is_not_found(self):
        self.assertEqual(ToolNotPublished.STATUS_CODE, 404)
        self.assertEqual(str(ToolNotPublished.MESSAGE), "工具未上架")

    def test_detail_permission_finds_tool_by_namespace_and_name(self):
        viewset = MCPUserToolViewSet()
        viewset.request = SimpleNamespace(
            query_params={"name": "same-name"},
            data={},
            parser_context={"kwargs": {"namespace": "target-ns"}},
        )
        tool = SimpleNamespace(uid="target-tool", status=PanelStatus.PUBLISHED)

        with mock.patch("services.web.tool.views.Tool.all_latest_tools") as all_latest_tools:
            all_latest_tools.return_value.filter.return_value.first.return_value = tool
            self.assertEqual(viewset.get_tool_uid_by_name(), "target-tool")

        all_latest_tools.return_value.filter.assert_called_once_with(namespace="target-ns", name="same-name")

    def test_detail_permission_raises_standard_not_found_errors(self):
        viewset = MCPUserToolViewSet()
        viewset.request = SimpleNamespace(
            query_params={"name": "missing"},
            data={},
            parser_context={"kwargs": {"namespace": "target-ns"}},
        )
        with mock.patch("services.web.tool.views.Tool.all_latest_tools") as all_latest_tools:
            all_latest_tools.return_value.filter.return_value.first.return_value = None
            with self.assertRaises(ToolDoesNotExist):
                viewset.get_tool_uid_by_name()

        with mock.patch("services.web.tool.views.Tool.all_latest_tools") as all_latest_tools:
            all_latest_tools.return_value.filter.return_value.first.return_value = SimpleNamespace(
                uid="unpublished-tool", status=PanelStatus.UNPUBLISHED
            )
            with self.assertRaises(ToolNotPublished):
                viewset.get_tool_uid_by_name()


@override_settings(ROOT_URLCONF="services.web.urls")
class TestMCPUserToolDetailViewSet(TestCase):
    class User:
        username = "agent-user"
        is_authenticated = True

    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        Tool.objects.create(
            namespace="default",
            name="unpublished-tool",
            uid="unpublished-tool-uid",
            version=1,
            tool_type=ToolTypeEnum.BK_VISION.value,
            config={"uid": "vision-uid"},
            permission_owner="owner",
            status=PanelStatus.UNPUBLISHED,
        )

    def test_unpublished_tool_detail_returns_not_found(self):
        view = MCPUserToolViewSet.as_view({"get": "detail_by_name"})
        request = self.factory.get("/api/v1/namespaces/default/mcp_user/tool/detail_by_name/?name=unpublished-tool")
        force_authenticate(request, user=self.User())

        with mock.patch("core.permissions.get_app_info"):
            response = view(request, namespace="default")

        self.assertEqual(response.status_code, 404)
        self.assertIn("工具未上架", str(response.data))

    def test_tool_detail_honors_path_namespace(self):
        Tool.objects.create(
            namespace="other",
            name="same-name",
            uid="other-tool-uid",
            version=1,
            tool_type=ToolTypeEnum.BK_VISION.value,
            config={"uid": "other-vision-uid"},
            permission_owner="owner",
            status=PanelStatus.PUBLISHED,
        )
        Tool.objects.create(
            namespace="default",
            name="same-name",
            uid="default-tool-uid",
            version=1,
            tool_type=ToolTypeEnum.BK_VISION.value,
            config={"uid": "default-vision-uid"},
            permission_owner="owner",
            status=PanelStatus.PUBLISHED,
        )
        view = MCPUserToolViewSet.as_view({"get": "detail_by_name"})
        request = self.factory.get("/api/v1/namespaces/other/mcp_user/tool/detail_by_name/?name=same-name")
        force_authenticate(request, user=self.User())

        with (
            mock.patch("core.permissions.get_app_info"),
            mock.patch("services.web.tool.permissions.UseToolPermission.has_permission", return_value=True),
        ):
            response = view(request, namespace="other")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["uid"], "other-tool-uid")
        self.assertEqual(response.data["namespace"], "other")

    def test_mcp_tool_detail_never_returns_full_config(self):
        Tool.objects.create(
            namespace="default",
            name="safe-detail-tool",
            uid="safe-detail-tool-uid",
            version=1,
            tool_type=ToolTypeEnum.DATA_SEARCH.value,
            config={
                "sql": "SELECT * FROM sensitive_table",
                "referenced_tables": [{"table_name": "sensitive_table"}],
                "api_config": {
                    "url": "https://example.com/internal",
                    "headers": {"Authorization": "Bearer secret"},
                },
                "input_variable": [{"raw_name": "username", "default_value": "alice"}],
            },
            status=PanelStatus.PUBLISHED,
        )

        result = GetMCPToolDetailByName().request({"namespace": "default", "name": "safe-detail-tool"})

        self.assertNotIn("sql", result["config"])
        self.assertNotIn("referenced_tables", result["config"])
        self.assertNotIn("api_config", result["config"])


class TestJSONBodyValidation(TestCase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()

    def test_mcp_execute_rejects_json_string_body(self):
        view = MCPUserToolViewSet.as_view({"post": "execute"})
        request = self.factory.post(
            "/api/v1/namespaces/default/mcp_user/tool/tool-1/execute/",
            '"{\\"params\\": {}}"',
            content_type="application/json",
        )

        with mock.patch.object(MCPUserToolViewSet, "get_permissions", return_value=[]):
            response = view(request, namespace="default", uid="tool-1")

        self.assertEqual(response.status_code, 400)
        self.assertIn("请求体必须为 JSON 对象", str(response.data))

    def test_regular_execute_rejects_json_string_body(self):
        view = ToolViewSet.as_view({"post": "execute"})
        request = self.factory.post(
            "/api/v1/namespaces/default/tool/tool-1/execute/",
            '"{\\"params\\": {}}"',
            content_type="application/json",
        )

        with mock.patch.object(ToolViewSet, "get_permissions", return_value=[]):
            response = view(request, uid="tool-1")

        self.assertEqual(response.status_code, 400)
        self.assertIn("请求体必须为 JSON 对象", str(response.data))
