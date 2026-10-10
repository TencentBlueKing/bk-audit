"""通用消息规划评测 Provider 的生产协议一致性测试。"""

import importlib.util
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

import yaml
from django.test import SimpleTestCase

from services.web.query.ai_assistant.exceptions import AIOutputInvalidError
from services.web.query.ai_assistant.schemas import (
    AIConditionItem,
    AIConditionPayload,
    MessagePlan,
    PlannedLogSearchInput,
    PlannedLogSearchMessage,
    PlannedSystemSelectionMessage,
    SystemSelectionInput,
)
from services.web.query.constants import COLLECT_SEARCH_CONFIG


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
        invalid_output = '{"outcome":"dispatch","messages":[]}'
        with mock.patch.object(
            self.provider.MessagePlanningService,
            "plan",
            side_effect=[
                AIOutputInvalidError(
                    extra={
                        "raw_output": invalid_output,
                        "validation_errors": [
                            {
                                "path": "messages",
                                "code": "value_error",
                                "message": "dispatch outcome requires messages",
                            }
                        ],
                    }
                ),
                plan,
            ],
        ) as planning:
            result = self.provider.call_api(
                "你好",
                {"config": {"username": "auth_eval_user", "max_attempts": 3}},
                {"vars": {"query": "你好"}},
            )

        self.assertEqual(planning.call_count, 2)
        self.assertEqual(result["metadata"]["attempt_count"], 2)
        self.assertEqual(planning.call_args.kwargs["agent_user"], "auth_eval_user")
        retry_feedback = planning.call_args.kwargs["retry_feedback"]
        self.assertEqual(retry_feedback.previous_output, invalid_output)
        self.assertEqual(retry_feedback.validation_errors[0]["path"], "messages")
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

    def test_default_common_fields_match_production_search_config(self):
        """评测默认字段的类型与操作符必须取自生产检索配置。"""

        fields = {field.raw_name: field for field in self.provider._resolve_common_fields({})}

        for raw_name, field in fields.items():
            with self.subTest(raw_name=raw_name):
                config = COLLECT_SEARCH_CONFIG.query_field_map[raw_name]
                self.assertEqual(field.field_type, config.field.field_type)
                self.assertEqual(field.allow_operators, [operator.value for operator in config.allow_operators])

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
            side_effect=[AIOutputInvalidError(), plan],
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
                    'd.condition.start_time.startsWith("2026-09-19T10:00:00")',
                    'd.condition.end_time.startsWith("2026-09-20T10:00:00")',
                ):
                    self.assertIn(fragment, assertion["value"])
                exact = case["assert"][1]
                self.assertEqual(exact["value"], "file://assertions/exact_conditions.js")
                expected = {
                    (item["raw_name"], tuple(item["keys"]), item["operator"], tuple(item["filters"]))
                    for item in variables["expected_conditions"]
                }
                self.assertEqual(
                    expected,
                    {
                        ("username", (), "eq", ("eval_user_nested",)),
                        ("extend_data", ("_request_url", "scope_id"), "eq", ("49",)),
                    },
                )

    def test_promptfoo_covers_invalid_condition_contract(self):
        """正式评测必须覆盖意图已识别但操作符不受支持的稳定业务错误。"""

        eval_root = Path(__file__).parents[3] / "evals/intent-recognition"
        config = yaml.safe_load((eval_root / "promptfooconfig.yaml").read_text())
        fixture = "file://tests/invalid-conditions.yaml"
        self.assertIn(fixture, config["tests"])

        cases = yaml.safe_load((eval_root / "tests/invalid-conditions.yaml").read_text())
        self.assertEqual(len(cases), 1)
        case = cases[0]
        self.assertIn("gt 操作符", case["vars"]["query"])
        self.assertIn("INVALID_CONDITION", case["assert"][0]["value"])

    def test_promptfoo_covers_extension_type_and_operator_inference(self):
        """正式评测覆盖采样提示与用户明确语义冲突及未知路径两类场景。"""

        eval_root = Path(__file__).parents[3] / "evals/intent-recognition"
        config = yaml.safe_load((eval_root / "promptfooconfig.yaml").read_text())
        fixture = "file://tests/extension-type-operators.yaml"
        self.assertIn(fixture, config["tests"])

        cases = yaml.safe_load((eval_root / "tests/extension-type-operators.yaml").read_text())
        self.assertEqual(len(cases), 3)
        self.assertTrue(all("eval_" in str(case["vars"]["authorized_systems"]) for case in cases))
        self.assertTrue(any("未知路径" in case["description"] for case in cases))
        self.assertTrue(any("数值比较" in case["description"] for case in cases))

    def test_numeric_expected_conditions_declare_field_type(self):
        """数值筛选值必须显式声明类型，断言不能信任待验证的 Agent 输出类型。"""

        tests_root = Path(__file__).parents[3] / "evals/intent-recognition/tests"
        result_code_conditions = []
        for fixture_path in tests_root.glob("*.yaml"):
            for case in yaml.safe_load(fixture_path.read_text()) or []:
                result_code_conditions.extend(
                    condition
                    for condition in case.get("vars", {}).get("expected_conditions", [])
                    if condition["raw_name"] == "result_code"
                )

        self.assertGreater(len(result_code_conditions), 0)
        self.assertTrue(all(condition.get("field_type") == "int" for condition in result_code_conditions))

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
