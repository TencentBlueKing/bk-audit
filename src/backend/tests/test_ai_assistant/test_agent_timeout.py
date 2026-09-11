# -*- coding: utf-8 -*-
"""智能体调用超时配置测试：单次 LLM 调用超时是链路总时长的实际闸门。"""

from django.conf import settings

from api.bk_plugins_ai_agent.default import AIAgentBase
from tests.base import TestCase


class AIAgentTimeoutTest(TestCase):
    def test_timeout_reads_from_settings(self):
        """TIMEOUT 类属性在 import 时从 settings 求值（环境变量 BKAPP_AI_AGENT_API_TIMEOUT_SECONDS）。"""

        self.assertEqual(AIAgentBase.TIMEOUT, settings.AI_AGENT_API_TIMEOUT_SECONDS)

    def test_default_timeout_keeps_legacy_behavior(self):
        """缺省 300 秒保持历史行为（不改变其他环境）。"""

        self.assertEqual(settings.AI_AGENT_API_TIMEOUT_SECONDS, 300)
