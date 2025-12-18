# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at https://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

from unittest import mock

from bk_resource import resource
from bk_resource.exceptions import ValidateException

from services.web.risk.constants import RiskStatus
from services.web.risk.models import Risk
from services.web.strategy_v2.models import Strategy
from tests.base import TestCase as BaseTestCase


class TestBulkCustomTransRisk(BaseTestCase):
    """测试批量人工转单功能"""

    def setUp(self):
        super().setUp()
        # 创建测试策略
        self.strategy = Strategy.objects.create(
            strategy_id=1,
            strategy_name="测试策略",
            strategy_type="model",
            namespace=self.namespace,
            status="running",
        )

        # 创建测试风险
        self.risk1 = Risk.objects.create(
            risk_id="test_risk_1",
            strategy=self.strategy,
            status=RiskStatus.NEW,
            event_time="2024-01-01T00:00:00Z",
            raw_event_id="event_1",
        )

        self.risk2 = Risk.objects.create(
            risk_id="test_risk_2",
            strategy=self.strategy,
            status=RiskStatus.NEW,
            event_time="2024-01-01T00:00:00Z",
            raw_event_id="event_2",
        )

        self.risk3 = Risk.objects.create(
            risk_id="test_risk_3",
            strategy=self.strategy,
            status=RiskStatus.NEW,
            event_time="2024-01-01T00:00:00Z",
            raw_event_id="event_3",
        )

    @mock.patch("services.web.risk.resources.risk.CustomTransRisk")
    def test_bulk_custom_trans_risk_success(self, mock_custom_trans_risk):
        """测试批量人工转单成功"""
        # 准备测试数据
        risk_ids = [self.risk1.risk_id, self.risk2.risk_id, self.risk3.risk_id]
        new_operators = ["user1", "user2"]
        description = "批量转单测试"

        # 模拟CustomTransRisk的bulk_request方法
        mock_custom_trans_risk.return_value.bulk_request.return_value = None

        # 执行批量转单
        result = resource.risk.bulk_custom_trans_risk(
            risk_ids=risk_ids, new_operators=new_operators, description=description
        )

        # 验证结果
        self.assertIsNone(result)

        # 验证CustomTransRisk.bulk_request被正确调用
        mock_custom_trans_risk.return_value.bulk_request.assert_called_once()

        # 验证调用参数
        call_args = mock_custom_trans_risk.return_value.bulk_request.call_args[0][0]
        self.assertEqual(len(call_args), 3)

        # 验证每个风险都被正确处理
        expected_params = [
            {
                "risk_id": self.risk1.risk_id,
                "new_operators": new_operators,
                "description": description,
            },
            {
                "risk_id": self.risk2.risk_id,
                "new_operators": new_operators,
                "description": description,
            },
            {
                "risk_id": self.risk3.risk_id,
                "new_operators": new_operators,
                "description": description,
            },
        ]

        for i, param in enumerate(call_args):
            self.assertEqual(param, expected_params[i])

    @mock.patch("services.web.risk.resources.risk.CustomTransRisk")
    def test_bulk_custom_trans_risk_with_duplicate_risk_ids(self, mock_custom_trans_risk):
        """测试包含重复风险ID的批量转单"""
        # 准备包含重复ID的测试数据
        risk_ids = [self.risk1.risk_id, self.risk2.risk_id, self.risk1.risk_id]  # 重复的risk_id
        new_operators = ["user1"]
        description = "重复ID测试"

        # 模拟CustomTransRisk的bulk_request方法
        mock_custom_trans_risk.return_value.bulk_request.return_value = None

        # 执行批量转单
        result = resource.risk.bulk_custom_trans_risk(
            risk_ids=risk_ids, new_operators=new_operators, description=description
        )

        # 验证结果
        self.assertIsNone(result)

        # 验证CustomTransRisk.bulk_request被调用
        mock_custom_trans_risk.return_value.bulk_request.assert_called_once()

        # 验证重复的risk_id被去重
        call_args = mock_custom_trans_risk.return_value.bulk_request.call_args[0][0]
        unique_risk_ids = {param["risk_id"] for param in call_args}
        self.assertEqual(len(unique_risk_ids), 2)

    @mock.patch("services.web.risk.resources.risk.CustomTransRisk")
    def test_bulk_custom_trans_risk_with_single_risk_id(self, mock_custom_trans_risk):
        """测试单个风险ID的批量转单"""
        # 准备单个风险ID
        risk_ids = [self.risk1.risk_id]
        new_operators = ["user1", "user2", "user3"]
        description = "单个风险测试"

        # 模拟CustomTransRisk的bulk_request方法
        mock_custom_trans_risk.return_value.bulk_request.return_value = None

        # 执行批量转单
        result = resource.risk.bulk_custom_trans_risk(
            risk_ids=risk_ids, new_operators=new_operators, description=description
        )

        # 验证结果
        self.assertIsNone(result)

        # 验证CustomTransRisk.bulk_request被正确调用
        mock_custom_trans_risk.return_value.bulk_request.assert_called_once()

        # 验证调用参数
        call_args = mock_custom_trans_risk.return_value.bulk_request.call_args[0][0]
        self.assertEqual(len(call_args), 1)
        self.assertEqual(call_args[0]["risk_id"], self.risk1.risk_id)
        self.assertEqual(call_args[0]["new_operators"], new_operators)
        self.assertEqual(call_args[0]["description"], description)

    def test_bulk_custom_trans_risk_serializer_validation(self):
        """测试批量转单序列化器验证"""
        # 测试空的风险ID列表
        with self.assertRaises(ValidateException):  # 应该抛出验证错误
            resource.risk.bulk_custom_trans_risk(risk_ids=[], new_operators=["user1"], description="测试")

        # 测试空的新处理人列表
        with self.assertRaises(ValidateException):  # 应该抛出验证错误
            resource.risk.bulk_custom_trans_risk(risk_ids=[self.risk1.risk_id], new_operators=[], description="测试")
