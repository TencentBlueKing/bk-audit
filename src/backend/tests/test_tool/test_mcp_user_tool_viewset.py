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
from services.web.tool.exceptions import ToolNotPublished
from services.web.tool.models import Tool
from services.web.tool.permissions import UseToolByNamePermission
from services.web.tool.views import MCPUserToolViewSet
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

    def test_execute_uses_user_state_resource(self):
        route = next(route for route in MCPUserToolViewSet.resource_routes if route.endpoint == "execute")

        self.assertEqual(route.resource_class.__name__, "ExecuteTool")

    def test_detail_by_name_uses_mcp_namespace_resource(self):
        route = next(route for route in MCPUserToolViewSet.resource_routes if route.endpoint == "detail_by_name")

        self.assertEqual(route.resource_class.__name__, "GetMCPToolDetailByName")


class TestUseToolByNamePermission(SimpleTestCase):
    def test_missing_tool_reaches_resource_for_existing_not_found_error(self):
        request = SimpleNamespace(
            data={},
            query_params={"name": "missing"},
            parser_context={"kwargs": {"namespace": "target-ns"}},
        )
        view = SimpleNamespace()
        permission = UseToolByNamePermission()

        with mock.patch("services.web.tool.permissions.Tool.all_latest_tools") as all_latest_tools:
            all_latest_tools.return_value.filter.return_value.first.return_value = None
            self.assertTrue(permission.has_permission(request, view))

        all_latest_tools.return_value.filter.assert_called_once_with(namespace="target-ns", name="missing")

    def test_unpublished_tool_reaches_resource_for_not_published_error(self):
        request = SimpleNamespace(
            data={},
            query_params={"name": "unpublished"},
            parser_context={"kwargs": {"namespace": "target-ns"}},
        )
        view = SimpleNamespace()
        permission = UseToolByNamePermission()
        tool = SimpleNamespace(uid="tool-1", status=PanelStatus.UNPUBLISHED)

        with (
            mock.patch("services.web.tool.permissions.Tool.all_latest_tools") as all_latest_tools,
            mock.patch.object(UseToolByNamePermission.__mro__[1], "has_permission") as parent_has_permission,
        ):
            all_latest_tools.return_value.filter.return_value.first.return_value = tool

            self.assertTrue(permission.has_permission(request, view))

        parent_has_permission.assert_not_called()
        all_latest_tools.return_value.filter.assert_called_once_with(namespace="target-ns", name="unpublished")

    def test_lookup_uses_path_namespace(self):
        request = SimpleNamespace(
            data={},
            query_params={"name": "same-name"},
            parser_context={"kwargs": {"namespace": "target-ns"}},
        )
        view = SimpleNamespace()
        permission = UseToolByNamePermission()
        tool = SimpleNamespace(uid="target-tool", status=PanelStatus.PUBLISHED)

        with (
            mock.patch("services.web.tool.permissions.Tool.all_latest_tools") as all_latest_tools,
            mock.patch.object(UseToolByNamePermission.__mro__[1], "has_permission", return_value=True),
        ):
            all_latest_tools.return_value.filter.return_value.first.return_value = tool

            self.assertTrue(permission.has_permission(request, view))

        all_latest_tools.return_value.filter.assert_called_once_with(namespace="target-ns", name="same-name")

    def test_legacy_tool_not_published_contract_is_unchanged(self):
        self.assertEqual(ToolNotPublished.STATUS_CODE, 400)
        self.assertEqual(str(ToolNotPublished.MESSAGE), "工具未发布")


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

        with (
            mock.patch("core.permissions.get_app_info"),
            mock.patch("services.web.tool.resources.get_app_info"),
        ):
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
            mock.patch("services.web.tool.resources.get_app_info"),
            mock.patch("services.web.tool.views.UseToolByNamePermission.has_permission", return_value=True),
        ):
            response = view(request, namespace="other")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["uid"], "other-tool-uid")
        self.assertEqual(response.data["namespace"], "other")
