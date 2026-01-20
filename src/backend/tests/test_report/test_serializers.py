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
from datetime import timezone as dt_timezone
from unittest.mock import MagicMock

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
            "status",
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
        self.assertEqual(len(definitions), 17)  # 共 17 个字段（新增 status）

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
            "status",
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


class TestReportRiskVariableSerializerFriendlyDisplay:
    """测试 ReportRiskVariableSerializer 用户友好显示（无数据库依赖）"""

    def test_risk_label_displays_chinese_label(self):
        """测试 risk_label 显示中文标签"""
        risk = MagicMock()
        risk.risk_id = "20250119210000123456"
        risk.title = "测试风险"
        risk.risk_label = "normal"
        risk.status = "new"
        risk.event_time = datetime.datetime(2025, 1, 19, 13, 0, 0, tzinfo=dt_timezone.utc)
        risk.event_end_time = None
        risk.operator = []
        risk.event_type = []
        risk.current_operator = []
        risk.notice_users = []
        risk.last_operate_time = datetime.datetime(2025, 1, 19, 14, 0, 0, tzinfo=dt_timezone.utc)
        risk.created_at = datetime.datetime(2025, 1, 19, 12, 0, 0, tzinfo=dt_timezone.utc)
        risk.updated_at = datetime.datetime(2025, 1, 19, 14, 0, 0, tzinfo=dt_timezone.utc)
        risk.strategy = MagicMock()
        risk.strategy.strategy_id = 1
        risk.strategy.risk_level = "HIGH"
        risk.strategy.risk_hazard = "危害描述"
        risk.strategy.risk_guidance = "处理指引"

        serializer = ReportRiskVariableSerializer(risk)
        data = serializer.data

        # 验证枚举字段翻译
        assert data["risk_label"] == "正常"
        assert data["risk_level"] == "高"
        assert data["status"] == "新"

    def test_datetime_fields_display_cst_format(self):
        """测试时间字段显示 +8 时区标准格式"""
        risk = MagicMock()
        risk.risk_id = "20250119210000123456"
        risk.title = "测试风险"
        risk.risk_label = "normal"
        risk.status = "new"
        risk.event_time = datetime.datetime(2025, 1, 19, 13, 0, 0, tzinfo=dt_timezone.utc)
        risk.event_end_time = datetime.datetime(2025, 1, 19, 14, 30, 0, tzinfo=dt_timezone.utc)
        risk.operator = []
        risk.event_type = []
        risk.current_operator = []
        risk.notice_users = []
        risk.last_operate_time = datetime.datetime(2025, 1, 19, 15, 0, 0, tzinfo=dt_timezone.utc)
        risk.created_at = datetime.datetime(2025, 1, 19, 12, 0, 0, tzinfo=dt_timezone.utc)
        risk.updated_at = datetime.datetime(2025, 1, 19, 16, 0, 0, tzinfo=dt_timezone.utc)
        risk.strategy = MagicMock()
        risk.strategy.strategy_id = 1
        risk.strategy.risk_level = "MIDDLE"
        risk.strategy.risk_hazard = "危害描述"
        risk.strategy.risk_guidance = "处理指引"

        serializer = ReportRiskVariableSerializer(risk)
        data = serializer.data

        # 验证时间格式 (UTC+8)
        assert data["event_time"] == "2025-01-19 21:00:00"
        assert data["event_end_time"] == "2025-01-19 22:30:00"
        assert data["last_operate_time"] == "2025-01-19 23:00:00"
        assert data["created_at"] == "2025-01-19 20:00:00"
        assert data["updated_at"] == "2025-01-20 00:00:00"
