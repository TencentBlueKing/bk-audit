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
