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

测试 ReportRiskVariableSerializer
"""
import datetime

from services.web.risk.models import Risk
from services.web.risk.report.serializers import ReportRiskVariableSerializer
from services.web.strategy_v2.models import Strategy
from tests.base import TestCase


class TestReportRiskVariableSerializer(TestCase):
    """测试 ReportRiskVariableSerializer"""

    def setUp(self):
        super().setUp()
        self.strategy = Strategy.objects.create(
            strategy_id=200,
            strategy_name="Test Strategy",
            risk_level="high",
            risk_hazard="测试风险危害",
            risk_guidance="测试处理指引",
        )
        self.risk = Risk.objects.create(
            risk_id="risk_serializer_001",
            strategy=self.strategy,
            raw_event_id="evt_serializer_001",
            event_time=datetime.datetime.now(tz=datetime.timezone.utc),
            title="测试风险标题",
            operator=["user1", "user2"],
            current_operator=["user1"],
            notice_users=["user3"],
            event_type=["login", "access"],
        )

    def test_serialize_risk_contains_all_fields(self):
        """测试序列化包含所有定义的字段"""
        data = ReportRiskVariableSerializer(self.risk).data

        expected_fields = [
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
        ]

        for field in expected_fields:
            self.assertIn(field, data, f"缺少字段: {field}")

    def test_serialize_strategy_derived_fields(self):
        """测试来自 Strategy 的字段正确序列化"""
        data = ReportRiskVariableSerializer(self.risk).data

        self.assertEqual(data["risk_level"], "high")
        self.assertEqual(data["risk_hazard"], "测试风险危害")
        self.assertEqual(data["risk_guidance"], "测试处理指引")

    def test_get_field_definitions_returns_all_fields(self):
        """测试 get_field_definitions 返回所有字段定义"""
        definitions = ReportRiskVariableSerializer.get_field_definitions()

        self.assertIsInstance(definitions, list)
        self.assertEqual(len(definitions), 16)  # 共 16 个字段

        # 验证每个定义包含必要的键
        for field_def in definitions:
            self.assertIn("field", field_def)
            self.assertIn("name", field_def)
            self.assertIn("description", field_def)

    def test_get_field_definitions_field_order(self):
        """测试字段定义的顺序与 Meta.fields 一致"""
        definitions = ReportRiskVariableSerializer.get_field_definitions()
        fields = [d["field"] for d in definitions]

        expected_order = [
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
        ]

        self.assertEqual(fields, expected_order)
