# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.

测试 submit_render_task 适配层函数
"""
import datetime
from unittest.mock import MagicMock, patch

from celery.result import AsyncResult

from services.web.risk.models import Risk
from services.web.risk.report.providers import AIProvider, EventProvider
from services.web.risk.report_config import AIVariableConfig, ReportConfig
from services.web.strategy_v2.models import Strategy
from tests.base import TestCase


class TestSubmitRenderTask(TestCase):
    """测试 submit_render_task 函数"""

    def setUp(self):
        super().setUp()
        self.strategy = Strategy.objects.create(
            strategy_id=100,
            strategy_name="Test Strategy",
            report_enabled=True,
            report_config={"template": "default"},
        )
        self.risk = Risk.objects.create(
            risk_id="risk_submit_001",
            strategy=self.strategy,
            raw_event_id="evt_submit_001",
            event_time=datetime.datetime.now(tz=datetime.timezone.utc),
            title="测试风险标题",
        )

    @patch("services.web.risk.report.task_submitter.render_template")
    def test_submit_render_task_returns_async_result(self, mock_task):
        """测试 submit_render_task 返回 AsyncResult"""
        from services.web.risk.report.task_submitter import submit_render_task

        mock_async_result = MagicMock(spec=AsyncResult)
        mock_async_result.id = "test_task_id_123"
        mock_task.delay.return_value = mock_async_result

        report_config = ReportConfig(
            template="{{ ai.summary }}",
            ai_variables=[AIVariableConfig(name="ai.summary", prompt_template="请总结风险")],
        )

        result = submit_render_task(risk=self.risk, report_config=report_config)

        self.assertIsInstance(result, MagicMock)
        self.assertEqual(result.id, "test_task_id_123")
        mock_task.delay.assert_called_once()

    @patch("services.web.risk.report.task_submitter.render_template")
    def test_submit_render_task_with_empty_ai_variables(self, mock_task):
        """测试 submit_render_task 空 AI 变量"""
        from services.web.risk.report.task_submitter import submit_render_task

        mock_task.delay.return_value = MagicMock()

        report_config = ReportConfig(template="无 AI 变量的模板", ai_variables=[])

        submit_render_task(risk=self.risk, report_config=report_config)

        call_kwargs = mock_task.delay.call_args[1]
        providers = call_kwargs["providers"]
        # 应该有 AIProvider 和 EventProvider
        self.assertEqual(len(providers), 2)
        provider_types = {type(p) for p in providers}
        self.assertIn(AIProvider, provider_types)
        self.assertIn(EventProvider, provider_types)

    @patch("services.web.risk.report.task_submitter.render_template")
    def test_submit_render_task_ai_variable_prefix_handling(self, mock_task):
        """测试 AI 变量名称前缀处理（自动添加和避免重复）"""
        from services.web.risk.report.task_submitter import submit_render_task

        mock_task.delay.return_value = MagicMock()

        # 两个都有 ai. 前缀
        report_config = ReportConfig(
            template="{{ ai.summary }}{{ ai.recommendation }}",
            ai_variables=[
                AIVariableConfig(name="ai.summary", prompt_template="总结..."),
                AIVariableConfig(name="ai.recommendation", prompt_template="建议..."),
            ],
        )

        submit_render_task(risk=self.risk, report_config=report_config)

        call_kwargs = mock_task.delay.call_args[1]
        providers = call_kwargs["providers"]
        ai_provider = providers[0]

        # AIProvider 内部将 list 转为 dict，key 为变量名
        var_names = list(ai_provider.ai_variables_config.keys())
        self.assertIn("ai.summary", var_names)
        self.assertIn("ai.recommendation", var_names)
        # 确保没有重复前缀
        self.assertNotIn("ai.ai.recommendation", var_names)

    @patch("services.web.risk.report.task_submitter.render_template")
    def test_submit_render_task_full_params_assertion(self, mock_task):
        """测试完整参数传递的精确校验"""
        from services.web.risk.report.serializers import ReportRiskVariableSerializer
        from services.web.risk.report.task_submitter import submit_render_task

        mock_task.delay.return_value = MagicMock()

        report_config = ReportConfig(
            template="# 风险报告\n\n{{ risk.title }}\n\n{{ ai.summary }}",
            ai_variables=[
                AIVariableConfig(name="ai.summary", prompt_template="请总结该风险的要点"),
            ],
        )

        submit_render_task(risk=self.risk, report_config=report_config)

        # 获取实际调用参数
        call_kwargs = mock_task.delay.call_args[1]

        # 1. 验证 template
        self.assertEqual(call_kwargs["template"], "# 风险报告\n\n{{ risk.title }}\n\n{{ ai.summary }}")

        # 2. 验证 providers（应该有 AIProvider 和 EventProvider）
        self.assertEqual(len(call_kwargs["providers"]), 2)
        ai_provider = next(p for p in call_kwargs["providers"] if isinstance(p, AIProvider))
        self.assertIsInstance(ai_provider, AIProvider)
        self.assertEqual(ai_provider.context, {"risk_id": self.risk.risk_id})
        # AIProvider 内部将 list 转为 dict 格式
        self.assertEqual(
            ai_provider.ai_variables_config,
            {"ai.summary": {"name": "ai.summary", "prompt_template": "请总结该风险的要点"}},
        )

        # 3. 验证 variables 中的 risk 数据
        variables = call_kwargs["variables"]
        self.assertIn("risk", variables)
        risk_data = variables["risk"]

        # 验证 ReportRiskVariableSerializer 中定义的所有字段都在 risk_data 中
        field_definitions = ReportRiskVariableSerializer.get_field_definitions()
        for field_def in field_definitions:
            field_name = field_def["field"]
            self.assertIn(
                field_name,
                risk_data,
                f"ReportRiskVariableSerializer 中定义的字段 '{field_name}' 在 risk_data 中不存在",
            )

        # 校验具体字段值
        self.assertEqual(risk_data["risk_id"], self.risk.risk_id)
        self.assertEqual(risk_data["title"], "测试风险标题")
        self.assertEqual(risk_data["strategy_id"], self.strategy.strategy_id)
