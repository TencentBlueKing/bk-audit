# -*- coding: utf-8 -*-
"""最近使用记录来源分场景测试：广场点击/执行参与排序，下钻/MCP/接口仅记录"""
from unittest import mock

from django.test import SimpleTestCase

from services.web.scene.constants import PanelStatus
from services.web.tool.constants import ToolTypeEnum
from services.web.tool.models import Tool
from services.web.tool.resources import ExecuteTool, ExecuteToolAPIGW, MCPExecuteTool
from services.web.tool.tool import RecentToolUsageManager
from tests.base import TestCase


class TestRecentToolUsageManager(SimpleTestCase):
    def setUp(self):
        super().setUp()
        self.manager = RecentToolUsageManager()
        self.manager.redis_client = mock.Mock()

    def test_record_square_usage_writes_square_key(self):
        self.manager.record_usage("alice", "tool-1")

        key = self.manager.redis_client.zadd.call_args.args[0]
        self.assertEqual(key, "tool:recently_used_square:alice")

    def test_record_other_usage_not_recorded(self):
        """下钻/MCP/接口不再记录最近使用（无实际意义）"""
        self.manager.record_usage("alice", "tool-1", for_square=False)

        self.manager.redis_client.zadd.assert_not_called()

    def test_get_recent_uids_reads_square_key_only(self):
        self.manager.redis_client.zrevrange.return_value = ["tool-1"]

        self.manager.get_recent_uids("alice")

        self.manager.redis_client.zrevrange.assert_called_once_with("tool:recently_used_square:alice", 0, -1)

    def test_get_all_recent_uids_merges_square_and_legacy(self):
        """最近使用标签合并广场新 key 与旧版历史 key（保留历史）"""

        def fake_zrange(key, start, end, withscores):
            if key == "tool:recently_used_square:alice":
                return [("tool-1", 100.0)]
            # 旧版历史 key（含早期下钻/MCP 记录）
            return [("tool-1", 200.0), ("tool-2", 150.0)]

        self.manager.redis_client.zrange.side_effect = fake_zrange

        result = self.manager.get_all_recent_uids("alice")

        # tool-1 取最新时间 200，tool-2 为 150 → 按时间倒序
        self.assertEqual(result, ["tool-1", "tool-2"])


class TestExecuteToolUsageSource(TestCase):
    """执行记录按来源分流：广场执行参与排序，下钻/MCP/接口仅记录不参与排序"""

    def setUp(self):
        super().setUp()
        self.tool = Tool.objects.create(
            namespace="ns",
            name="usage_source_tool",
            uid="usage_source_tool_uid",
            version=1,
            tool_type=ToolTypeEnum.BK_VISION.value,
            config={"uid": "vision_uid"},
            permission_owner="owner",
            status=PanelStatus.PUBLISHED,
        )

    def _execute(self, resource_cls, extra=None):
        """直接实例化 resource 调用（避免 bk_resource 代理短路径模块导致 patch 不生效）"""
        mock_executor = mock.Mock()
        mock_executor.execute.return_value = mock.Mock(model_dump=mock.Mock(return_value={"panel_id": "p1"}))
        with (
            mock.patch("services.web.tool.resources.get_request_username", return_value="alice"),
            mock.patch("services.web.tool.resources.should_skip_permission_from"),
            mock.patch("services.web.tool.resources.ToolExecutorFactory.create_from_tool", return_value=mock_executor),
            mock.patch("services.web.tool.resources.recent_tool_usage_manager.record_usage") as m_record,
        ):
            payload = {"uid": self.tool.uid, "params": {}}
            payload.update(extra or {})
            resource_cls().request(payload)
        return m_record

    def test_square_execute_records_for_square(self):
        m_record = self._execute(ExecuteTool)

        args, kwargs = m_record.call_args
        self.assertEqual(args, ("alice", self.tool.uid))
        self.assertEqual(kwargs, {"for_square": True})

    def test_drill_execute_records_other(self):
        m_record = self._execute(ExecuteTool, {"caller_resource_type": "risk", "caller_resource_id": "R1"})

        args, kwargs = m_record.call_args
        self.assertEqual(args, ("alice", self.tool.uid))
        self.assertEqual(kwargs, {"for_square": False})

    def test_mcp_execute_records_other(self):
        m_record = self._execute(MCPExecuteTool)

        args, kwargs = m_record.call_args
        self.assertEqual(args, ("alice", self.tool.uid))
        self.assertEqual(kwargs, {"for_square": False})

    def test_apigw_execute_records_other(self):
        m_record = self._execute(ExecuteToolAPIGW)

        args, kwargs = m_record.call_args
        self.assertEqual(args, ("admin", self.tool.uid))
        self.assertEqual(kwargs, {"for_square": False})
