# -*- coding: utf-8 -*-
"""
strategy_v2 serializers 单测：覆盖复杂策略校验逻辑
"""
from services.web.analyze.constants import ControlTypeChoices
from services.web.analyze.models import Control, ControlVersion
from services.web.strategy_v2.constants import (
    RiskLevel,
    RuleAuditSourceType,
    StrategyAlgorithmOperator,
    StrategyOperator,
    StrategyType,
)
from services.web.strategy_v2.serializers import (
    CreateStrategyRequestSerializer,
    RuleAuditSerializer,
    UpdateStrategyRequestSerializer,
)
from tests.base import TestCase


class StrategySerializersTest(TestCase):
    def setUp(self):
        super().setUp()
        self.control = Control.objects.create(
            control_id="control-bkm",
            control_name="BKM Control",
            control_type_id=ControlTypeChoices.BKM.value,
        )
        ControlVersion.objects.create(control_id=self.control.control_id, control_version=1)

    def _build_model_strategy_payload(self):
        return {
            "namespace": self.namespace,
            "strategy_name": "model_strategy",
            "control_id": self.control.control_id,
            "control_version": 1,
            "strategy_type": StrategyType.MODEL.value,
            "configs": {
                "agg_condition": [
                    {
                        "key": "username",
                        "value": ["admin"],
                        "method": StrategyOperator.EQ.value,
                        "condition": "and",
                    }
                ],
                "agg_dimension": ["username"],
                "agg_interval": 60,
                "algorithms": [{"method": StrategyAlgorithmOperator.GT.value, "threshold": 1}],
                "detects": {"count": 1, "alert_window": 1},
            },
            "tags": ["test"],
            "notice_groups": [],
            "description": "",
            "risk_level": RiskLevel.HIGH.value,
            "risk_hazard": "",
            "risk_guidance": "",
            "risk_title": "risk",
            "processor_groups": [1],
            "event_basic_field_configs": [],
            "event_data_field_configs": [],
            "event_evidence_field_configs": [],
            "risk_meta_field_config": [],
        }

    def test_create_strategy_serializer_valid_model_strategy(self):
        serializer = CreateStrategyRequestSerializer(data=self._build_model_strategy_payload())
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["control_id"], self.control.control_id)
        # 模型策略不应强制配置联表字段
        self.assertIsNone(serializer.validated_data.get("link_table_uid"))

    def test_create_strategy_serializer_requires_control_version(self):
        payload = self._build_model_strategy_payload()
        payload.pop("control_version")
        serializer = CreateStrategyRequestSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("params_error", serializer.errors)

    def test_create_strategy_serializer_rejects_sql_for_model_strategy(self):
        payload = self._build_model_strategy_payload()
        payload["sql"] = "SELECT 1"
        serializer = CreateStrategyRequestSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("params_error", serializer.errors)

    def test_rule_audit_serializer_requires_schedule_for_batch_source(self):
        rule_data = {
            "config_type": "EventLog",
            "data_source": {
                "source_type": "batch",
                "rt_id": "table",
                "system_ids": ["bklog"],
            },
            "select": [
                {
                    "table": "table",
                    "raw_name": "field",
                    "display_name": "field",
                    "field_type": "string",
                    "aggregate": None,
                }
            ],
            "where": None,
        }
        serializer = RuleAuditSerializer(data=rule_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("batch", str(serializer.errors).lower())

    def test_rule_audit_serializer_normalizes_empty_where(self):
        rule_data = {
            "config_type": "EventLog",
            "data_source": {
                "source_type": RuleAuditSourceType.REALTIME.value,
                "rt_id": "table",
                "system_ids": ["bklog"],
            },
            "select": [
                {
                    "table": "table",
                    "raw_name": "field",
                    "display_name": "field",
                    "field_type": "string",
                    "aggregate": None,
                }
            ],
            "where": {"conditions": []},
        }
        serializer = RuleAuditSerializer(data=rule_data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIsNone(serializer.validated_data["where"])


class TestReportConfigValidation(TestCase):
    """测试报告配置校验逻辑"""

    def setUp(self):
        super().setUp()
        self.control = Control.objects.create(
            control_id="control-bkm",
            control_name="BKM Control",
            control_type_id=ControlTypeChoices.BKM.value,
        )
        ControlVersion.objects.create(control_id=self.control.control_id, control_version=1)

    def _build_base_payload(self):
        """构建基础策略 payload"""
        return {
            "namespace": self.namespace,
            "strategy_name": "test-strategy",
            "control_id": self.control.control_id,
            "control_version": 1,
            "strategy_type": StrategyType.MODEL.value,
            "configs": {
                "agg_condition": [
                    {
                        "key": "username",
                        "value": ["admin"],
                        "method": StrategyOperator.EQ.value,
                        "condition": "and",
                    }
                ],
                "agg_dimension": ["username"],
                "agg_interval": 60,
                "algorithms": [{"method": StrategyAlgorithmOperator.GT.value, "threshold": 1}],
                "detects": {"count": 1, "alert_window": 1},
            },
            "tags": [],
            "notice_groups": [],
            "description": "",
            "risk_level": RiskLevel.HIGH.value,
            "risk_hazard": "",
            "risk_guidance": "",
            "risk_title": "risk",
            "processor_groups": [1],
            "event_basic_field_configs": [],
            "event_data_field_configs": [],
            "event_evidence_field_configs": [],
            "risk_meta_field_config": [],
        }

    def test_create_strategy_report_enabled_with_config(self):
        """测试创建策略：report_enabled=True 且有 report_config -> 通过"""
        payload = self._build_base_payload()
        payload["report_enabled"] = True
        payload["report_config"] = {
            "template": "Test template {{ risk.title }}",
            "ai_variables": [
                {
                    "name": "ai.summary",
                    "prompt_template": "请总结风险",
                }
            ],
        }

        serializer = CreateStrategyRequestSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_create_strategy_report_enabled_without_config(self):
        """测试创建策略：report_enabled=True 但 report_config 为空 -> 失败"""
        payload = self._build_base_payload()
        payload["report_enabled"] = True
        payload["report_config"] = None

        serializer = CreateStrategyRequestSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("params_error", serializer.errors)
        # 检查错误信息包含 report_config
        error_msg = str(serializer.errors)
        self.assertIn("report_config", error_msg.lower())

    def test_create_strategy_report_disabled_without_config(self):
        """测试创建策略：report_enabled=False 且 report_config 为空 -> 通过"""
        payload = self._build_base_payload()
        payload["report_enabled"] = False
        payload["report_config"] = None

        serializer = CreateStrategyRequestSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_create_strategy_report_disabled_with_config(self):
        """测试创建策略：report_enabled=False 但有 report_config -> 通过（允许这种情况）"""
        payload = self._build_base_payload()
        payload["report_enabled"] = False
        payload["report_config"] = {
            "template": "Test template",
            "ai_variables": [],
        }

        serializer = CreateStrategyRequestSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_update_strategy_report_enabled_with_config(self):
        """测试更新策略：report_enabled=True 且有 report_config -> 通过"""
        from services.web.strategy_v2.models import Strategy

        strategy = Strategy.objects.create(
            namespace=self.namespace,
            strategy_name="existing-strategy",
            control_id=self.control.control_id,
            control_version=1,
            strategy_type=StrategyType.MODEL.value,
            risk_level=RiskLevel.HIGH.value,
            risk_title="risk",
        )

        payload = self._build_base_payload()
        payload["strategy_id"] = strategy.strategy_id
        payload["strategy_name"] = "updated-strategy"
        payload["report_enabled"] = True
        payload["report_config"] = {
            "template": "Updated template {{ risk.title }}",
            "ai_variables": [
                {
                    "name": "ai.summary",
                    "prompt_template": "请总结风险",
                }
            ],
        }

        serializer = UpdateStrategyRequestSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_update_strategy_report_enabled_without_config(self):
        """测试更新策略：report_enabled=True 但 report_config 为空 -> 失败"""
        from services.web.strategy_v2.models import Strategy

        strategy = Strategy.objects.create(
            namespace=self.namespace,
            strategy_name="existing-strategy",
            control_id=self.control.control_id,
            control_version=1,
            strategy_type=StrategyType.MODEL.value,
            risk_level=RiskLevel.HIGH.value,
            risk_title="risk",
        )

        payload = self._build_base_payload()
        payload["strategy_id"] = strategy.strategy_id
        payload["strategy_name"] = "updated-strategy"
        payload["report_enabled"] = True
        payload["report_config"] = None

        serializer = UpdateStrategyRequestSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("params_error", serializer.errors)
        # 检查错误信息包含 report_config
        error_msg = str(serializer.errors)
        self.assertIn("report_config", error_msg.lower())
