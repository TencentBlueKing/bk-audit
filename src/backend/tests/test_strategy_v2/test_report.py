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
"""

from services.web.strategy_v2.constants import RiskLevel
from services.web.strategy_v2.models import Strategy
from tests.base import TestCase


class TestRetrieveStrategy(TestCase):
    """测试获取策略详情接口"""

    def setUp(self):
        super().setUp()
        self.strategy = Strategy.objects.create(
            namespace="default",
            strategy_name="test-strategy-detail",
            risk_level=RiskLevel.HIGH.value,
            report_enabled=True,
            report_config={
                "template": "Test template {{ risk.title }}",
                "ai_variables": [
                    {
                        "name": "summary",
                        "prompt_template": "请总结风险",
                    }
                ],
            },
        )

    def test_retrieve_strategy(self):
        """测试获取策略详情"""
        result = self.resource.strategy_v2.retrieve_strategy({"strategy_id": self.strategy.strategy_id})

        self.assertEqual(result["strategy_id"], self.strategy.strategy_id)
        self.assertEqual(result["strategy_name"], self.strategy.strategy_name)
        self.assertTrue(result["report_enabled"])
        self.assertIn("template", result["report_config"])
        self.assertIn("ai_variables", result["report_config"])

    def test_retrieve_strategy_not_found(self):
        """测试获取不存在的策略"""
        from django.http import Http404

        with self.assertRaises(Http404):
            self.resource.strategy_v2.retrieve_strategy({"strategy_id": 99999})


class TestPreviewRiskReportSerializer(TestCase):
    """测试报告预览序列化器"""

    def test_preview_report_request_serializer_valid(self):
        """测试有效的预览请求"""
        from services.web.strategy_v2.serializers import PreviewReportRequestSerializer

        data = {
            "risk_id": "test-risk-id",
            "report_config": {
                "template": "Risk: {{ risk.title }}",
                "ai_variables": [
                    {
                        "name": "summary",
                        "prompt_template": "请总结",
                    }
                ],
            },
        }
        serializer = PreviewReportRequestSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_preview_report_request_serializer_invalid_config(self):
        """测试无效的配置"""
        from services.web.strategy_v2.serializers import PreviewReportRequestSerializer

        data = {
            "risk_id": "test-risk-id",
            "report_config": {
                "template": "test",
                "ai_variables": [{"prompt_template": "test"}],  # 缺少必填的 name
            },
        }
        serializer = PreviewReportRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("report_config", serializer.errors)

    def test_preview_report_response_serializer(self):
        """测试响应序列化器"""
        from services.web.strategy_v2.serializers import PreviewReportResponseSerializer

        data = {"task_id": "mock_task_123", "status": "PENDING"}
        serializer = PreviewReportResponseSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)


class TestListRiskVariables(TestCase):
    """测试获取报告风险变量列表接口"""

    def test_list_risk_variables(self):
        """测试获取风险变量列表"""
        result = self.resource.strategy_v2.list_risk_variables({})

        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0)

        # 验证返回的字段格式
        for var in result:
            self.assertIn("field", var)
            self.assertIn("name", var)

    def test_list_risk_variables_expected_fields(self):
        """测试风险变量列表包含预期的字段"""
        result = self.resource.strategy_v2.list_risk_variables({})

        # 按确认清单，预期的风险变量字段列表
        expected_fields = {
            "risk_id",
            "title",
            "risk_level",
            "event_time",
            "event_end_time",
            "operator",
            "risk_label",
            "strategy_id",
            "risk_hazard",
            "risk_guidance",
            "event_type",
            "current_operator",
            "notice_users",
            "last_operate_time",
            "created_at",
            "updated_at",
        }

        actual_fields = {var["field"] for var in result}
        self.assertEqual(actual_fields, expected_fields)


class TestListAggregationFunctions(TestCase):
    """测试获取聚合函数列表接口"""

    def test_list_aggregation_functions(self):
        """测试获取聚合函数列表"""
        result = self.resource.strategy_v2.list_aggregation_functions({})

        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0)

        # 验证返回的字段格式
        for func in result:
            self.assertIn("id", func)
            self.assertIn("name", func)
            self.assertIn("supported_field_types", func)


class TestPreviewRiskReport(TestCase):
    """测试报告预览接口"""

    def setUp(self):
        super().setUp()
        from django.utils import timezone

        from services.web.risk.models import Risk

        self.risk = Risk.objects.create(
            risk_id="test-risk-for-preview",
            title="测试风险",
            strategy_id=1,
            event_time=timezone.now(),
        )

    def test_preview_risk_report_success(self):
        """测试报告预览成功"""
        from unittest.mock import patch

        from services.web.risk.utils.renderer_client import renderer_client

        mock_result = {
            "task_id": "mock_task_123",
            "status": "PENDING",
        }

        with patch.object(renderer_client, "render_preview", return_value=mock_result) as mock_render:
            result = self.resource.strategy_v2.preview_risk_report(
                {
                    "risk_id": self.risk.risk_id,
                    "report_config": {
                        "template": "风险标题: {{ risk.title }}",
                        "ai_variables": [],
                    },
                }
            )

            self.assertEqual(result["task_id"], "mock_task_123")
            self.assertEqual(result["status"], "PENDING")

            # 验证渲染器被正确调用
            mock_render.assert_called_once()

    def test_preview_risk_report_risk_not_found(self):
        """测试预览不存在的风险"""
        from django.http import Http404

        with self.assertRaises(Http404):
            self.resource.strategy_v2.preview_risk_report(
                {
                    "risk_id": "non-existent-risk",
                    "report_config": {
                        "template": "test",
                        "ai_variables": [],
                    },
                }
            )
