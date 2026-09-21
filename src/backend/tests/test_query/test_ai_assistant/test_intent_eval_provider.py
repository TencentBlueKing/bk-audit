"""通用消息规划评测 Provider 的生产协议一致性测试。"""

import importlib.util
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

import yaml
from django.test import SimpleTestCase

from services.web.query.ai_assistant.exceptions import AIOutputParseFailedError
from services.web.query.ai_assistant.schemas import (
    AIConditionItem,
    AIConditionPayload,
    MessagePlan,
    PlannedLogSearchInput,
    PlannedLogSearchMessage,
    PlannedSystemSelectionMessage,
    SystemSelectionInput,
)


def load_provider_module():
    """从带连字符的评测目录加载 Provider。"""

    provider_path = Path(__file__).parents[3] / "evals/intent-recognition/providers/provider.py"
    spec = importlib.util.spec_from_file_location("intent_recognition_eval_provider", provider_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class IntentEvalProviderTest(SimpleTestCase):
    def setUp(self):
        self.provider = load_provider_module()
        self.reference_time = datetime.fromisoformat("2026-09-20T10:00:00+08:00")
        self.system_context = self.provider._build_system_context(self.provider.CANDIDATES)

    def test_materialize_composite_plan_uses_backend_default_day(self):
        plan = MessagePlan(
            outcome="dispatch",
            messages=[
                PlannedSystemSelectionMessage(
                    message_type="SYSTEM_SELECTION",
                    message_input=SystemSelectionInput(system_ids=["eval_audit_system"]),
                ),
                PlannedLogSearchMessage(
                    message_type="LOG_SEARCH",
                    message_input=PlannedLogSearchInput(
                        condition=AIConditionPayload(
                            conditions=[
                                AIConditionItem(
                                    raw_name="username",
                                    field_type="string",
                                    operator="eq",
                                    filters=["张三"],
                                )
                            ]
                        )
                    ),
                ),
            ],
        )

        output = self.provider._materialize_output(
            plan=plan,
            system_context=self.system_context,
            current_system_id="",
            reference_time=self.reference_time,
        )

        self.assertEqual(output["outcome"], "dispatch")
        self.assertEqual([item["message_type"] for item in output["messages"]], ["SYSTEM_SELECTION", "LOG_SEARCH"])
        self.assertEqual(output["system_id"], "eval_audit_system")
        start_time = datetime.fromisoformat(output["condition"]["start_time"])
        end_time = datetime.fromisoformat(output["condition"]["end_time"])
        self.assertEqual(end_time, self.reference_time)
        self.assertEqual(end_time - start_time, timedelta(days=1))

    def test_materialize_error_plan_exposes_stable_code(self):
        output = self.provider._materialize_output(
            plan=MessagePlan(outcome="error", error_code="SYSTEM_REQUIRED"),
            system_context=self.system_context,
            current_system_id="",
            reference_time=self.reference_time,
        )

        self.assertEqual(output["outcome"], "error")
        self.assertEqual(output["error_code"], "SYSTEM_REQUIRED")
        self.assertEqual(output["messages"], [])

    def test_call_api_retries_contract_failure_with_production_budget(self):
        plan = MessagePlan(outcome="error", error_code="UNRECOGNIZED_INTENT")
        with mock.patch.object(
            self.provider.MessagePlanningService,
            "plan",
            side_effect=[AIOutputParseFailedError(), plan],
        ) as planning:
            result = self.provider.call_api(
                "你好",
                {"config": {"username": "alice", "max_attempts": 3}},
                {"vars": {"query": "你好"}},
            )

        self.assertEqual(planning.call_count, 2)
        self.assertEqual(result["metadata"]["attempt_count"], 2)

    def test_explicit_empty_candidates_stay_empty(self):
        """显式空授权列表必须保留，不能回退到评测默认系统。"""

        self.assertEqual(self.provider._resolve_candidates([]), [])

    def test_full_authorized_system_context_keeps_per_system_fields(self):
        """评测可以注入生产同构的完整系统字段快照。"""

        context = self.provider._resolve_system_context(
            {
                "authorized_systems": [
                    {
                        "system_id": "audit",
                        "name": "审计中心",
                        "description": "审计日志",
                        "standard_fields": [
                            {
                                "raw_name": "username",
                                "field_type": "string",
                                "allow_operators": ["eq"],
                            }
                        ],
                        "extension_fields": [],
                    },
                    {
                        "system_id": "cmdb",
                        "name": "配置平台",
                        "description": "配置数据",
                        "standard_fields": [],
                        "extension_fields": [
                            {
                                "raw_name": "extend_data",
                                "keys": ["biz_id"],
                                "field_type": "integer",
                                "allow_operators": ["eq"],
                            }
                        ],
                    },
                ]
            }
        )

        self.assertEqual([system.system_id for system in context.systems], ["audit", "cmdb"])
        self.assertEqual(context.systems[0].standard_fields[0].raw_name, "username")
        self.assertEqual(context.systems[1].extension_fields[0].keys, ["biz_id"])

    def test_case_max_attempts_overrides_production_retry_budget(self):
        """首轮能力 profile 可以把单个用例限制为一次 Agent 调用。"""

        plan = MessagePlan(outcome="error", error_code="UNRECOGNIZED_INTENT")
        with mock.patch.object(
            self.provider.MessagePlanningService,
            "plan",
            side_effect=[AIOutputParseFailedError(), plan],
        ) as planning:
            result = self.provider.call_api(
                "你好",
                {"config": {"username": "alice", "max_attempts": 3}},
                {"vars": {"query": "你好", "max_attempts": 1}},
            )

        self.assertEqual(planning.call_count, 1)
        self.assertEqual(result["metadata"]["attempt_count"], 1)
        self.assertIn('"status": "error"', result["output"])

    def test_invalid_max_attempts_returns_structured_error(self):
        """评测变量错误也必须形成单条结果，不能中断整批 Promptfoo。"""

        result = self.provider.call_api(
            "你好",
            {"config": {"username": "alice", "max_attempts": "invalid"}},
            {"vars": {"query": "你好"}},
        )

        self.assertNotIn("error", result)
        self.assertEqual(result["metadata"]["attempt_count"], 0)
        self.assertIn('"status": "error"', result["output"])
        self.assertIn('"error_code": "UNEXPECTED_ERROR"', result["output"])

    def test_promptfoo_executes_real_context_cases(self):
        """真实上下文场景必须由 Promptfoo 配置直接加载，而非只做静态 fixture 检查。"""

        eval_root = Path(__file__).parents[3] / "evals/intent-recognition"
        config = yaml.safe_load((eval_root / "promptfooconfig.yaml").read_text())
        self.assertIn("file://tests/context-boundaries.yaml", config["tests"])

        cases = yaml.safe_load((eval_root / "tests/context-boundaries.yaml").read_text())
        self.assertGreaterEqual(len(cases), 5)
        for case in cases:
            with self.subTest(case=case["description"]):
                variables = case["vars"]
                self.assertIn("authorized_systems", variables)
                self.assertIn("scope_type", variables)
                self.assertIn("scope_id", variables)
                self.assertIn("current_time", variables)
