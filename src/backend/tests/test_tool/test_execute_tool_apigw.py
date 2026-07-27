# -*- coding: utf-8 -*-
from unittest import mock

from rest_framework.test import APIRequestFactory

from core.permissions import APIGWPermission
from services.web.scene.constants import PanelStatus
from services.web.tool.constants import ToolTypeEnum
from services.web.tool.exceptions import ToolNotPublished
from services.web.tool.models import Tool
from services.web.tool.views import ToolAPIGWViewSet

from ..base import TestCase


class TestExecuteToolAPIGWResource(TestCase):
    def test_execute_tool_apigw_executes_without_resource_level_app_auth(self):
        tool = Tool.objects.create(
            namespace="ns",
            name="apigw_tool",
            uid="tool_uid",
            version=1,
            tool_type=ToolTypeEnum.BK_VISION.value,
            config={"uid": "vision_uid"},
            permission_owner="owner",
            status=PanelStatus.PUBLISHED,
        )
        mock_executor = mock.Mock()
        mock_executor.execute.return_value = mock.Mock(model_dump=mock.Mock(return_value={"ok": True}))
        with (
            mock.patch(
                "tool.resources.ToolExecutorFactory.create_from_tool",
                return_value=mock_executor,
            ) as mock_create_executor,
            mock.patch("tool.resources.recent_tool_usage_manager.record_usage") as mock_record_usage,
            mock.patch("tool.resources.should_skip_permission_from") as mock_skip_permission,
        ):
            result = self.resource.tool.execute_tool_apigw({"uid": "tool_uid", "params": {}})
        self.assertEqual(result["tool_type"], ToolTypeEnum.BK_VISION.value)
        self.assertEqual(result["data"], {"ok": True})
        mock_create_executor.assert_called_once_with(tool)
        mock_record_usage.assert_called_once_with("admin", tool.uid)
        mock_skip_permission.assert_not_called()

    def test_execute_tool_apigw_denies_unpublished_tool(self):
        Tool.objects.create(
            namespace="ns",
            name="draft_apigw_tool",
            uid="draft_tool_uid",
            version=1,
            tool_type=ToolTypeEnum.BK_VISION.value,
            config={"uid": "vision_uid"},
            permission_owner="owner",
            status=PanelStatus.UNPUBLISHED,
        )

        with (
            mock.patch("tool.resources.ToolExecutorFactory.create_from_tool") as mock_create_executor,
            mock.patch("tool.resources.recent_tool_usage_manager.record_usage") as mock_record_usage,
        ):
            with self.assertRaises(ToolNotPublished):
                self.resource.tool.execute_tool_apigw({"uid": "draft_tool_uid", "params": {}})
        mock_create_executor.assert_not_called()
        mock_record_usage.assert_not_called()


class TestToolNameNotUnique(TestCase):
    """测试工具名称不再全局唯一"""

    def test_tool_name_duplicate_allowed(self):
        """相同 name 不同 uid/version 允许共存"""
        from services.web.tool.constants import ToolTypeEnum
        from services.web.tool.models import Tool

        Tool.objects.create(
            namespace="ns",
            name="duplicate_tool_name",
            uid="tool_uid_1",
            version=1,
            tool_type=ToolTypeEnum.BK_VISION.value,
            config={"uid": "vision_uid"},
        )

        Tool.objects.create(
            namespace="ns",
            name="duplicate_tool_name",
            uid="tool_uid_2",
            version=1,
            tool_type=ToolTypeEnum.BK_VISION.value,
            config={"uid": "vision_uid_2"},
        )

        Tool.objects.create(
            namespace="ns",
            name="duplicate_tool_name",
            uid="tool_uid_1",
            version=2,
            tool_type=ToolTypeEnum.BK_VISION.value,
            config={"uid": "vision_uid_3"},
        )

    def test_tool_uid_version_name_unique(self):
        """相同 uid+version+name 仍应保持唯一"""
        from django.db import IntegrityError

        from services.web.tool.constants import ToolTypeEnum
        from services.web.tool.models import Tool

        Tool.objects.create(
            namespace="ns",
            name="tool_v1",
            uid="tool_uid_unique",
            version=1,
            tool_type=ToolTypeEnum.BK_VISION.value,
            config={"uid": "vision_uid"},
        )

        with self.assertRaises(IntegrityError):
            Tool.objects.create(
                namespace="ns",
                name="tool_v1",
                uid="tool_uid_unique",
                version=1,
                tool_type=ToolTypeEnum.BK_VISION.value,
                config={"uid": "vision_uid_2"},
            )


class TestGetToolDetailByNameAPIGWResource(TestCase):
    """测试通过名称获取工具详情接口(APIGW)"""

    def setUp(self):
        from services.web.tool.constants import ToolTypeEnum
        from services.web.tool.models import Tool

        self.tool = Tool.objects.create(
            namespace="ns",
            name="test_tool_by_name",
            uid="tool_uid_by_name",
            version=1,
            tool_type=ToolTypeEnum.DATA_SEARCH.value,
            config={
                "sql": "SELECT 1",
                "input_variable": [{"raw_name": "param1", "display_name": "参数1", "required": True}],
                "output_fields": [{"raw_name": "field1", "display_name": "字段1"}],
                "referenced_tables": [{"table_name": "test_table"}],
            },
            description="测试工具描述",
            status=PanelStatus.PUBLISHED,
        )

    def test_get_tool_detail_by_name_returns_safe_calling_contract(self):
        """工具详情只返回 Agent 执行所需的安全调用契约。"""
        result = self.resource.tool.get_tool_detail_by_name_apigw({"name": "test_tool_by_name"})

        self.assertEqual(result["uid"], "tool_uid_by_name")
        self.assertEqual(result["name"], "test_tool_by_name")
        self.assertEqual(result["tool_type"], "data_search")
        self.assertEqual(result["version"], 1)
        self.assertEqual(result["description"], "测试工具描述")
        self.assertEqual(result["namespace"], "ns")
        self.assertIn("input_variable", result["config"])
        self.assertNotIn("sql", result["config"])
        self.assertIn("output_fields", result["config"])
        self.assertNotIn("referenced_tables", result["config"])

    def test_get_tool_detail_by_name_tool_not_exist(self):
        """测试工具不存在时抛出异常"""
        from services.web.tool.exceptions import ToolDoesNotExist

        with self.assertRaises(ToolDoesNotExist):
            self.resource.tool.get_tool_detail_by_name_apigw({"name": "non_existent_tool"})

    def test_tool_apigw_uses_viewset_app_permission(self):
        """应用态鉴权由 APIGW ViewSet 统一承担，Resource 不重复校验。"""
        request = APIRequestFactory().get("/api/v1/namespaces/ns/tool_apigw/detail_by_name/")
        view = ToolAPIGWViewSet()
        view.request = request

        permissions = view.get_permissions()

        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], APIGWPermission)

    def test_get_tool_detail_by_name_apigw_denies_unpublished_tool(self):
        self.tool.status = PanelStatus.UNPUBLISHED
        self.tool.save(update_fields=["status"])

        with self.assertRaises(ToolNotPublished):
            self.resource.tool.get_tool_detail_by_name_apigw({"name": "test_tool_by_name"})
