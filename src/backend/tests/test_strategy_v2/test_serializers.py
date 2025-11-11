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
