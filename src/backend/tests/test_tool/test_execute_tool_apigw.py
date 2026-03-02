# -*- coding: utf-8 -*-
from unittest import mock

from core.exceptions import AppPermissionDenied
from services.web.tool.constants import ToolTypeEnum
from services.web.tool.models import Tool

from ..base import TestCase


class TestExecuteToolAPIGWResource(TestCase):
    def test_execute_tool_apigw_calls_app_auth(self):
        tool = Tool.objects.create(
            namespace="ns",
            name="apigw_tool",
            uid="tool_uid",
            version=1,
            tool_type=ToolTypeEnum.BK_VISION.value,
            config={"uid": "vision_uid"},
            permission_owner="owner",
        )
        mock_executor = mock.Mock()
        mock_executor.execute.return_value = mock.Mock(model_dump=mock.Mock(return_value={"ok": True}))
        with (
            mock.patch("tool.resources.get_app_info") as mock_get_app_info,
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
        mock_get_app_info.assert_called_once()
        mock_create_executor.assert_called_once_with(tool)
        mock_record_usage.assert_called_once_with("admin", tool.uid)
        mock_skip_permission.assert_not_called()

    def test_execute_tool_apigw_denied_without_app(self):
        with (
            mock.patch("tool.resources.get_app_info", side_effect=AppPermissionDenied()),
            mock.patch("tool.resources.recent_tool_usage_manager.record_usage") as mock_record_usage,
        ):
            with self.assertRaises(AppPermissionDenied):
                self.resource.tool.execute_tool_apigw({"uid": "tool_uid", "params": {}})
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
        )

    def test_get_tool_detail_by_name_lite_mode_true(self):
        """测试 lite_mode=True 时只返回 input_variable"""
        with mock.patch("core.utils.tools.get_app_info"):
            result = self.resource.tool.get_tool_detail_by_name_apigw(
                {
                    "name": "test_tool_by_name",
                    "lite_mode": True,
                }
            )

        self.assertEqual(result["uid"], "tool_uid_by_name")
        self.assertEqual(result["name"], "test_tool_by_name")
        self.assertEqual(result["tool_type"], "data_search")
        self.assertEqual(result["version"], 1)
        self.assertEqual(result["description"], "测试工具描述")
        self.assertEqual(result["namespace"], "ns")
        # lite_mode=True 时，config 只包含 input_variable
        self.assertIn("input_variable", result["config"])
        self.assertNotIn("sql", result["config"])
        self.assertNotIn("output_fields", result["config"])
        self.assertNotIn("referenced_tables", result["config"])

    def test_get_tool_detail_by_name_lite_mode_false(self):
        """测试 lite_mode=False 时返回完整配置"""
        with mock.patch("core.utils.tools.get_app_info"):
            result = self.resource.tool.get_tool_detail_by_name_apigw(
                {
                    "name": "test_tool_by_name",
                    "lite_mode": False,
                }
            )

        self.assertEqual(result["uid"], "tool_uid_by_name")
        # lite_mode=False 时，config 包含完整内容
        self.assertIn("input_variable", result["config"])
        self.assertIn("sql", result["config"])
        self.assertIn("output_fields", result["config"])
        self.assertIn("referenced_tables", result["config"])

    def test_get_tool_detail_by_name_default_lite_mode(self):
        """测试默认 lite_mode=True"""
        with mock.patch("core.utils.tools.get_app_info"):
            result = self.resource.tool.get_tool_detail_by_name_apigw(
                {
                    "name": "test_tool_by_name",
                }
            )

        # 默认 lite_mode=True，config 只包含 input_variable
        self.assertIn("input_variable", result["config"])
        self.assertNotIn("sql", result["config"])

    def test_get_tool_detail_by_name_tool_not_exist(self):
        """测试工具不存在时抛出异常"""
        from services.web.tool.exceptions import ToolDoesNotExist

        with mock.patch("core.utils.tools.get_app_info"):
            with self.assertRaises(ToolDoesNotExist):
                self.resource.tool.get_tool_detail_by_name_apigw(
                    {
                        "name": "non_existent_tool",
                        "lite_mode": True,
                    }
                )

    def test_get_tool_detail_by_name_denied_without_app(self):
        """测试没有应用权限时抛出异常"""
        with mock.patch("core.utils.tools.get_app_info", side_effect=AppPermissionDenied()):
            with self.assertRaises(AppPermissionDenied):
                self.resource.tool.get_tool_detail_by_name_apigw(
                    {
                        "name": "test_tool_by_name",
                        "lite_mode": True,
                    }
                )
