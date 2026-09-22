"""通用消息规划评测 Provider 的生产协议一致性测试。"""

import importlib.util
import re
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
                                    filters=["eval_user_alpha"],
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
                {"config": {"username": "auth_eval_user", "max_attempts": 3}},
                {"vars": {"query": "你好"}},
            )

        self.assertEqual(planning.call_count, 2)
        self.assertEqual(result["metadata"]["attempt_count"], 2)
        self.assertEqual(planning.call_args.kwargs["agent_user"], "auth_eval_user")
        self.assertEqual(
            planning.call_args.kwargs["context"].conversation.username, self.provider.EVAL_CONTEXT_USERNAME
        )
        self.assertIn(self.provider.EVAL_CONTEXT_USERNAME, planning.call_args.kwargs["user_message"])
        self.assertNotIn('"username": "auth_eval_user"', planning.call_args.kwargs["user_message"])
        self.assertNotIn("scope_type", planning.call_args.kwargs["user_message"])
        self.assertNotIn("scope_id", planning.call_args.kwargs["user_message"])

    def test_explicit_empty_candidates_stay_empty(self):
        """显式空授权列表必须保留，不能回退到评测默认系统。"""

        self.assertEqual(self.provider._resolve_candidates([]), [])

    def test_default_common_fields_include_extension_container(self):
        """评测公共字段必须包含生产同源的拓展数据 JSON 容器。"""

        fields = {field.raw_name: field for field in self.provider._resolve_common_fields({})}

        self.assertIn("extend_data", fields)
        self.assertEqual(fields["extend_data"].field_type, "object")
        self.assertIn("eq", fields["extend_data"].allow_operators)

    def test_full_authorized_system_context_keeps_per_system_fields(self):
        """评测可以注入生产同构的完整系统字段快照。"""

        context = self.provider._resolve_system_context(
            {
                "authorized_systems": [
                    {
                        "system_id": "eval_audit_system",
                        "name": "示例审计系统",
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
                        "system_id": "eval_config_system",
                        "name": "示例配置系统",
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

        self.assertEqual(
            [system.system_id for system in context.systems],
            ["eval_audit_system", "eval_config_system"],
        )
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
                {"config": {"username": "auth_eval_user", "max_attempts": 3}},
                {"vars": {"query": "你好", "max_attempts": 1}},
            )

        self.assertEqual(planning.call_count, 1)
        self.assertEqual(result["metadata"]["attempt_count"], 1)
        self.assertIn('"status": "error"', result["output"])

    def test_invalid_max_attempts_returns_structured_error(self):
        """评测变量错误也必须形成单条结果，不能中断整批 Promptfoo。"""

        result = self.provider.call_api(
            "你好",
            {"config": {"username": "auth_eval_user", "max_attempts": "invalid"}},
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
                self.assertIn("current_time", variables)

    def test_promptfoo_covers_nested_extension_field_matrix(self):
        """正式评测必须覆盖嵌套路径的两种上下文形态和两种用户表达。"""

        eval_root = Path(__file__).parents[3] / "evals/intent-recognition"
        config = yaml.safe_load((eval_root / "promptfooconfig.yaml").read_text())
        fixture = "file://tests/nested-extension-fields.yaml"
        self.assertIn(fixture, config["tests"])

        cases = yaml.safe_load((eval_root / "tests/nested-extension-fields.yaml").read_text())
        self.assertEqual(len(cases), 4)
        expected_descriptions = {
            "嵌套字段-完整路径上下文-完整路径表达",
            "嵌套字段-完整路径上下文-父节点表达",
            "嵌套字段-父节点样例上下文-完整路径表达",
            "嵌套字段-父节点样例上下文-父节点表达",
        }
        self.assertEqual({case["description"] for case in cases}, expected_descriptions)

        for case in cases:
            with self.subTest(case=case["description"]):
                variables = case["vars"]
                self.assertEqual(variables["current_system_id"], "")
                self.assertEqual(variables["current_time"], "2026-09-20T10:00:00+08:00")
                self.assertIn("eval_user_nested", variables["query"])
                self.assertIn("scope_id", variables["query"])
                systems = variables["authorized_systems"]
                self.assertEqual(len(systems), 1)
                self.assertEqual(systems[0]["system_id"], "eval_audit_primary")
                self.assertEqual(systems[0]["standard_fields"][0]["raw_name"], "username")
                extension = systems[0]["extension_fields"][0]
                self.assertEqual(extension["raw_name"], "extend_data")
                if "完整路径上下文" in case["description"]:
                    self.assertEqual(extension["keys"], ["_request_url", "scope_id"])
                else:
                    self.assertEqual(extension["keys"], ["_request_url"])
                    self.assertIn("scope_id", str(extension["sample_value"]))

                assertion = case["assert"][0]
                self.assertEqual(assertion["type"], "javascript")
                for fragment in (
                    '["SYSTEM_SELECTION","LOG_SEARCH"]',
                    'c.field.raw_name === "username"',
                    'c.filters.includes("eval_user_nested")',
                    'c.field.raw_name === "extend_data"',
                    '["_request_url","scope_id"]',
                    'c.operator === "eq"',
                    'JSON.stringify(c.filters) === JSON.stringify(["49"])',
                    'd.condition.start_time.startsWith("2026-09-19T10:00:00")',
                    'd.condition.end_time.startsWith("2026-09-20T10:00:00")',
                ):
                    self.assertIn(fragment, assertion["value"])

    def test_nested_extension_context_shapes_pass_backend_validation(self):
        """四格用例的两种字段上下文都允许显式完整下钻路径通过确定性校验。"""

        fixture_path = Path(__file__).parents[3] / "evals/intent-recognition/tests/nested-extension-fields.yaml"
        cases = yaml.safe_load(fixture_path.read_text())
        plan = MessagePlan(
            outcome="dispatch",
            messages=[
                PlannedSystemSelectionMessage(
                    message_type="SYSTEM_SELECTION",
                    message_input=SystemSelectionInput(system_ids=["eval_audit_primary"]),
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
                                    filters=["eval_user_nested"],
                                ),
                                AIConditionItem(
                                    raw_name="extend_data",
                                    keys=["_request_url", "scope_id"],
                                    field_type="string",
                                    operator="eq",
                                    filters=["49"],
                                ),
                            ]
                        )
                    ),
                ),
            ],
        )

        for case in cases:
            with self.subTest(case=case["description"]):
                output = self.provider._materialize_output(
                    plan=plan,
                    system_context=self.provider._resolve_system_context(case["vars"]),
                    current_system_id="",
                    reference_time=self.reference_time,
                )
                self.assertEqual(
                    [message["message_type"] for message in output["messages"]],
                    ["SYSTEM_SELECTION", "LOG_SEARCH"],
                )
                nested = next(
                    condition
                    for condition in output["condition"]["conditions"]
                    if condition["field"]["raw_name"] == "extend_data"
                )
                self.assertEqual(nested["field"]["keys"], ["_request_url", "scope_id"])
                self.assertEqual(nested["filters"], ["49"])

    def test_eval_sources_do_not_contain_known_real_identifiers(self):
        """评测源文件仅保留合成人员和系统标识，不扫描本地忽略的历史输出。"""

        eval_root = Path(__file__).parents[3] / "evals/intent-recognition"
        source_files = [eval_root / "providers/provider.py", *sorted((eval_root / "tests").glob("*.yaml"))]
        forbidden = (
            "frodomei",
            "hermit",
            "zhangsan",
            "bk-audit",
            "iam_v4_bk-audit",
            "bk-ci",
            "bk_cmdb",
            "bk_monitorv3",
            "bk_userman",
            "bk_iam",
            "bk_nodeman",
            "bk_ops_base",
            "dry_test",
        )
        for source_file in source_files:
            content = source_file.read_text()
            with self.subTest(source_file=source_file.name):
                for identifier in forbidden:
                    self.assertNotIn(identifier, content)
                self.assertIsNone(re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", content, re.IGNORECASE))

        for fixture_path in sorted((eval_root / "tests").glob("*.yaml")):
            fixtures = yaml.safe_load(fixture_path.read_text())
            for case in fixtures:
                systems = case.get("vars", {}).get("authorized_systems") or case.get("vars", {}).get("candidates")
                if not isinstance(systems, list):
                    continue
                for system in systems:
                    if isinstance(system, dict) and "system_id" in system:
                        self.assertTrue(str(system["system_id"]).startswith("eval_"))
