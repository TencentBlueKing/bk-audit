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

import datetime
from unittest import mock

from django.conf import settings

from services.web.risk.constants import RiskStatus
from services.web.risk.models import Risk
from services.web.risk.resources.risk import RetrieveRiskStrategyInfoAPIGW
from services.web.strategy_v2.constants import RiskLevel
from services.web.strategy_v2.models import Strategy
from tests.base import TestCase


class TestRetrieveRiskStrategyInfoAPIGW(TestCase):
    """
    测试 RetrieveRiskStrategyInfoAPIGW 接口
    """

    def setUp(self):
        super().setUp()
        # 创建策略，包含 enum_mappings 和 drill_config 配置
        self.strategy = Strategy.objects.create(
            namespace=settings.DEFAULT_NAMESPACE,
            strategy_name="test_strategy_for_apigw",
            risk_level=RiskLevel.HIGH.value,
            risk_hazard="测试风险危害",
            risk_guidance="测试处理指引",
            event_basic_field_configs=[
                {
                    "field_name": "event_id",
                    "display_name": "事件ID",
                    "is_priority": True,
                    "description": "事件唯一标识",
                    "enum_mappings": None,
                    "drill_config": [{"tool": {"uid": "test-tool", "version": 1}, "config": [], "drill_name": "测试工具"}],
                    "is_show": True,
                    "duplicate_field": False,
                    "field_type": "string",
                }
            ],
            event_data_field_configs=[
                {
                    "field_name": "operator",
                    "display_name": "操作人",
                    "is_priority": True,
                    "description": "执行操作的用户",
                    "enum_mappings": {
                        "related_type": "strategy",
                        "related_object_id": "strategy_id",
                        "collection_id": "user_mapping",
                        "mappings": [{"source_key": "admin", "target_value": "管理员"}],
                    },
                    "drill_config": [{"tool": {"uid": "user-tool", "version": 1}, "config": [], "drill_name": "用户工具"}],
                    "is_show": True,
                    "duplicate_field": False,
                    "field_type": "string",
                },
                {
                    "field_name": "ip_address",
                    "display_name": "IP地址",
                    "is_priority": False,
                    "description": "来源IP地址",
                    "enum_mappings": None,
                    "drill_config": [],
                    "is_show": True,
                    "duplicate_field": False,
                    "field_type": "string",
                },
            ],
            event_evidence_field_configs=[],
            risk_meta_field_config=[],
        )

        # 创建风险
        self.risk = Risk.objects.create(
            risk_id="test-risk-strategy-info-apigw",
            raw_event_id="raw_event_123",
            strategy=self.strategy,
            status=RiskStatus.NEW,
            title="测试风险",
            event_time=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
        )

    def tearDown(self):
        Risk.objects.filter(risk_id=self.risk.risk_id).delete()
        Strategy.objects.filter(strategy_id=self.strategy.strategy_id).delete()
        super().tearDown()

    @mock.patch("core.utils.tools.get_app_info")
    def test_retrieve_risk_strategy_info_apigw_returns_data(self, mock_get_app_info):
        """
        测试接口能够正常返回策略信息
        """
        mock_get_app_info.return_value = {"app_code": "test_app"}

        result = RetrieveRiskStrategyInfoAPIGW().perform_request({"risk_id": self.risk.risk_id, "lite_mode": False})

        self.assertIsInstance(result, dict)
        self.assertEqual(result["risk_level"], RiskLevel.HIGH.value)
        self.assertEqual(result["risk_hazard"], "测试风险危害")
        self.assertEqual(result["risk_guidance"], "测试处理指引")
        self.assertIn("event_basic_field_configs", result)
        self.assertIn("event_data_field_configs", result)

    @mock.patch("core.utils.tools.get_app_info")
    def test_retrieve_risk_strategy_info_apigw_with_enum_mappings(self, mock_get_app_info):
        """
        测试 lite_mode=False 时返回 enum_mappings 字段
        """
        mock_get_app_info.return_value = {"app_code": "test_app"}

        result = RetrieveRiskStrategyInfoAPIGW().perform_request({"risk_id": self.risk.risk_id, "lite_mode": False})

        # 验证 event_data_field_configs 中包含 enum_mappings
        event_data_configs = result.get("event_data_field_configs", [])
        self.assertTrue(len(event_data_configs) > 0)

        # 找到有 enum_mappings 的字段
        operator_field = next((f for f in event_data_configs if f["field_name"] == "operator"), None)
        self.assertIsNotNone(operator_field)
        self.assertIn("enum_mappings", operator_field)
        self.assertIsNotNone(operator_field["enum_mappings"])

    @mock.patch("core.utils.tools.get_app_info")
    def test_retrieve_risk_strategy_info_apigw_lite_mode(self, mock_get_app_info):
        """
        测试 lite_mode=True 时不返回 enum_mappings 字段，且只保留有 drill_config 的字段
        """
        mock_get_app_info.return_value = {"app_code": "test_app"}

        result = RetrieveRiskStrategyInfoAPIGW().perform_request({"risk_id": self.risk.risk_id, "lite_mode": True})

        # 验证所有字段配置中都不包含 enum_mappings
        for field_key in [
            "event_basic_field_configs",
            "event_data_field_configs",
            "event_evidence_field_configs",
            "risk_meta_field_config",
        ]:
            for field_config in result.get(field_key, []):
                self.assertNotIn(
                    "enum_mappings",
                    field_config,
                    f"字段 {field_config.get('field_name')} 不应包含 enum_mappings",
                )

        # 验证 lite_mode=True 时只保留有 drill_config 的字段
        # event_data_field_configs 中只有 operator 有 drill_config，ip_address 没有
        event_data_configs = result.get("event_data_field_configs", [])
        field_names = [f["field_name"] for f in event_data_configs]
        self.assertIn("operator", field_names)
        self.assertNotIn("ip_address", field_names)

    @mock.patch("core.utils.tools.get_app_info")
    def test_retrieve_risk_strategy_info_apigw_default_lite_mode(self, mock_get_app_info):
        """
        测试 lite_mode 默认值为 True，不返回 enum_mappings
        """
        mock_get_app_info.return_value = {"app_code": "test_app"}

        result = RetrieveRiskStrategyInfoAPIGW().perform_request({"risk_id": self.risk.risk_id})

        for field_key in [
            "event_basic_field_configs",
            "event_data_field_configs",
            "event_evidence_field_configs",
            "risk_meta_field_config",
        ]:
            for field_config in result.get(field_key, []):
                self.assertNotIn(
                    "enum_mappings",
                    field_config,
                    f"字段 {field_config.get('field_name')} 不应包含 enum_mappings",
                )

    @mock.patch("core.utils.tools.get_app_info")
    def test_retrieve_risk_strategy_info_apigw_calls_get_app_info(self, mock_get_app_info):
        """
        测试接口调用 get_app_info 进行 app_code 鉴权
        """
        mock_get_app_info.return_value = {"app_code": "test_app"}

        RetrieveRiskStrategyInfoAPIGW().perform_request({"risk_id": self.risk.risk_id, "lite_mode": False})

        # 验证 get_app_info 被调用
        mock_get_app_info.assert_called_once()

    @mock.patch("core.utils.tools.get_app_info")
    def test_retrieve_risk_strategy_info_apigw_risk_not_found(self, mock_get_app_info):
        """
        测试风险不存在时返回 404
        """
        mock_get_app_info.return_value = {"app_code": "test_app"}

        from django.http import Http404

        with self.assertRaises(Http404):
            RetrieveRiskStrategyInfoAPIGW().perform_request({"risk_id": "non_existent_risk_id", "lite_mode": False})

    @mock.patch("core.utils.tools.get_app_info")
    def test_retrieve_risk_strategy_info_apigw_strategy_not_found(self, mock_get_app_info):
        """
        测试策略不存在时返回空字典
        """
        mock_get_app_info.return_value = {"app_code": "test_app"}

        # 创建一个没有关联策略的风险
        risk_without_strategy = Risk.objects.create(
            risk_id="test-risk-no-strategy",
            raw_event_id="raw_event_456",
            strategy_id=99999,  # 不存在的策略ID
            status=RiskStatus.NEW,
            title="测试风险无策略",
            event_time=datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc),
        )

        try:
            result = RetrieveRiskStrategyInfoAPIGW().perform_request(
                {"risk_id": risk_without_strategy.risk_id, "lite_mode": False}
            )

            self.assertEqual(result, {})
        finally:
            Risk.objects.filter(risk_id=risk_without_strategy.risk_id).delete()


class TestRetrieveRiskStrategyInfoAPIGWResponseSerializer(TestCase):
    """
    测试 RetrieveRiskStrategyInfoAPIGWResponseSerializer 序列化器
    """

    def setUp(self):
        super().setUp()
        self.strategy = Strategy.objects.create(
            namespace=settings.DEFAULT_NAMESPACE,
            strategy_name="test_strategy_serializer",
            risk_level=RiskLevel.MIDDLE.value,
            risk_hazard="序列化器测试风险危害",
            risk_guidance="序列化器测试处理指引",
            event_basic_field_configs=[
                {
                    "field_name": "basic_field",
                    "display_name": "基础字段",
                    "is_priority": True,
                    "description": "基础字段描述",
                    "enum_mappings": {
                        "related_type": "strategy",
                        "related_object_id": "strategy_id",
                        "collection_id": "basic_mapping",
                        "mappings": [],
                    },
                    "drill_config": [{"tool": {"uid": "basic-tool", "version": 1}, "config": [], "drill_name": "基础工具"}],
                    "is_show": True,
                    "duplicate_field": False,
                    "field_type": "string",
                }
            ],
            event_data_field_configs=[
                {
                    "field_name": "data_field",
                    "display_name": "数据字段",
                    "is_priority": False,
                    "description": "数据字段描述",
                    "enum_mappings": {
                        "related_type": "strategy",
                        "related_object_id": "strategy_id",
                        "collection_id": "data_mapping",
                        "mappings": [],
                    },
                    "drill_config": [{"tool": {"uid": "data-tool", "version": 1}, "config": [], "drill_name": "数据工具"}],
                    "is_show": True,
                    "duplicate_field": False,
                    "field_type": "string",
                }
            ],
            event_evidence_field_configs=[
                {
                    "field_name": "evidence_field",
                    "display_name": "证据字段",
                    "is_priority": False,
                    "description": "证据字段描述",
                    "enum_mappings": {
                        "related_type": "strategy",
                        "related_object_id": "strategy_id",
                        "collection_id": "evidence_mapping",
                        "mappings": [],
                    },
                    "drill_config": [
                        {"tool": {"uid": "evidence-tool", "version": 1}, "config": [], "drill_name": "证据工具"}
                    ],
                    "is_show": True,
                    "duplicate_field": False,
                    "field_type": "string",
                }
            ],
            risk_meta_field_config=[
                {
                    "field_name": "meta_field",
                    "display_name": "元字段",
                    "is_priority": False,
                    "description": "元字段描述",
                    "enum_mappings": {
                        "related_type": "strategy",
                        "related_object_id": "strategy_id",
                        "collection_id": "meta_mapping",
                        "mappings": [],
                    },
                    "drill_config": [{"tool": {"uid": "meta-tool", "version": 1}, "config": [], "drill_name": "元工具"}],
                    "is_show": True,
                    "duplicate_field": False,
                    "field_type": "string",
                }
            ],
        )

    def tearDown(self):
        Strategy.objects.filter(strategy_id=self.strategy.strategy_id).delete()
        super().tearDown()

    def test_serializer_with_enum_mappings(self):
        """
        测试序列化器 lite_mode=False 时包含 enum_mappings
        """
        from services.web.risk.serializers import (
            RetrieveRiskStrategyInfoAPIGWResponseSerializer,
        )

        serializer = RetrieveRiskStrategyInfoAPIGWResponseSerializer(self.strategy, lite_mode=False)
        data = serializer.data

        # 验证所有字段配置都包含 enum_mappings
        for field_key in [
            "event_basic_field_configs",
            "event_data_field_configs",
            "event_evidence_field_configs",
            "risk_meta_field_config",
        ]:
            for field_config in data.get(field_key, []):
                self.assertIn("enum_mappings", field_config)

    def test_serializer_lite_mode(self):
        """
        测试序列化器 lite_mode=True 时移除 enum_mappings
        """
        from services.web.risk.serializers import (
            RetrieveRiskStrategyInfoAPIGWResponseSerializer,
        )

        serializer = RetrieveRiskStrategyInfoAPIGWResponseSerializer(self.strategy, lite_mode=True)
        data = serializer.data

        # 验证所有字段配置都不包含 enum_mappings
        for field_key in [
            "event_basic_field_configs",
            "event_data_field_configs",
            "event_evidence_field_configs",
            "risk_meta_field_config",
        ]:
            for field_config in data.get(field_key, []):
                self.assertNotIn(
                    "enum_mappings",
                    field_config,
                    f"字段 {field_config.get('field_name')} 不应包含 enum_mappings",
                )

    def test_serializer_preserves_other_fields(self):
        """
        测试序列化器在移除 enum_mappings 时保留其他字段
        """
        from services.web.risk.serializers import (
            RetrieveRiskStrategyInfoAPIGWResponseSerializer,
        )

        serializer = RetrieveRiskStrategyInfoAPIGWResponseSerializer(self.strategy, lite_mode=True)
        data = serializer.data

        # 验证基本字段存在
        self.assertEqual(data["risk_level"], RiskLevel.MIDDLE.value)
        self.assertEqual(data["risk_hazard"], "序列化器测试风险危害")
        self.assertEqual(data["risk_guidance"], "序列化器测试处理指引")

        # 验证其他字段配置字段保留
        basic_field = data["event_basic_field_configs"][0]
        self.assertEqual(basic_field["field_name"], "basic_field")
        self.assertEqual(basic_field["is_priority"], True)
        self.assertEqual(basic_field["is_show"], True)
        self.assertIn("drill_config", basic_field)
