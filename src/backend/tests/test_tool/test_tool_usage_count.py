# -*- coding: utf-8 -*-
"""工具被使用次数（按人隔离 Redis ZSet）与执行记录点位测试"""
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase

from services.web.tool.constants import ToolTypeEnum
from services.web.tool.models import Tool
from services.web.tool.tool import ToolUsageCountManager
from tests.base import TestCase


class TestToolUsageCountManager(SimpleTestCase):
    def setUp(self):
        super().setUp()
        self.manager = ToolUsageCountManager()
        self.manager.redis_client = mock.Mock()

    def test_incr_usage_builds_per_user_key(self):
        self.manager.incr_usage("alice", "tool-1")

        self.manager.redis_client.zincrby.assert_called_once_with("tool:usage_count:alice", 1, "tool-1")
        self.manager.redis_client.expire.assert_called_once_with("tool:usage_count:alice", settings.RECENT_USED_TTL)

    def test_incr_usage_ignores_empty_inputs(self):
        self.manager.incr_usage("", "tool-1")
        self.manager.incr_usage("alice", "")

        self.manager.redis_client.zincrby.assert_not_called()
        self.manager.redis_client.expire.assert_not_called()

    def test_get_usage_scores_returns_uid_score_map(self):
        self.manager.redis_client.zrange.return_value = [("tool-1", 10.0), ("tool-2", 2.0)]

        scores = self.manager.get_usage_scores("alice")

        self.manager.redis_client.zrange.assert_called_once_with("tool:usage_count:alice", 0, -1, withscores=True)
        self.assertEqual(scores, {"tool-1": 10.0, "tool-2": 2.0})


class TestExecuteToolUsageCount(TestCase):
    """执行工具时按人累计使用次数（用户态 ExecuteTool）"""

    def setUp(self):
        super().setUp()
        self.tool = Tool.objects.create(
            namespace="ns",
            name="usage_count_tool",
            uid="usage_count_tool_uid",
            version=1,
            tool_type=ToolTypeEnum.BK_VISION.value,
            config={"uid": "vision_uid"},
            permission_owner="owner",
        )

    def test_execute_tool_increments_per_user_usage_count(self):
        mock_executor = mock.Mock()
        mock_executor.execute.return_value = mock.Mock(model_dump=mock.Mock(return_value={"panel_id": "p1"}))

        with (
            mock.patch("services.web.tool.resources.get_request_username", return_value="alice"),
            mock.patch("services.web.tool.resources.should_skip_permission_from"),
            mock.patch("services.web.tool.resources.ToolExecutorFactory.create_from_tool", return_value=mock_executor),
            mock.patch("services.web.tool.resources.recent_tool_usage_manager.record_usage") as m_record,
            mock.patch("services.web.tool.resources.tool_usage_count_manager.incr_usage") as m_incr,
        ):
            result = self.resource.tool.execute_tool({"uid": self.tool.uid, "params": {}})

        self.assertEqual(result["data"], {"panel_id": "p1"})
        m_record.assert_called_once()
        self.assertEqual(m_incr.call_count, 1)
