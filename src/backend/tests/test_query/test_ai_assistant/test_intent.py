# -*- coding: utf-8 -*-
"""用户意图识别服务测试（一期 v6）：IntentPayload 契约 + schema 注入 + 候选白名单。"""

import json
from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from pydantic import ValidationError

from api.constants import AIAgentCode
from services.web.query.ai_assistant.exceptions import (
    AIOutputInvalidError,
    InvalidConditionError,
)
from services.web.query.ai_assistant.schemas import (
    MessagePlan,
    SelectionFieldMeta,
    SelectionSystem,
)
from services.web.query.ai_assistant.services.intent import (
    MessagePlanningService,
    PlanningRetryFeedback,
    resolve_intent_agent_code,
)
from tests.test_query.test_ai_assistant.base import AIAssistantTestCase

INTENT_MODULE = "services.web.query.ai_assistant.services.intent"

CANDIDATES = [
    {"system_id": "bk-audit", "name": "审计中心", "description": ""},
    {"system_id": "bcs", "name": "蓝盾", "description": ""},
]


class MessagePlanSchemaTest(AIAssistantTestCase):
    """通用消息规划输出必须收敛为一期允许的三种有序序列。"""

    def test_supported_dispatch_sequences(self):
        cases = (
            [{"message_type": "SYSTEM_SELECTION", "message_input": {"system_ids": ["bk-audit"]}}],
            [{"message_type": "LOG_SEARCH", "message_input": {"condition": {"conditions": []}}}],
            [
                {"message_type": "SYSTEM_SELECTION", "message_input": {"system_ids": ["bk-audit"]}},
                {"message_type": "LOG_SEARCH", "message_input": {"condition": {"conditions": []}}},
            ],
        )

        for messages in cases:
            with self.subTest(messages=messages):
                plan = MessagePlan.model_validate({"outcome": "dispatch", "messages": messages})
                self.assertEqual(len(plan.messages), len(messages))
                self.assertIsNone(plan.error_code)

    def test_reversed_or_duplicate_sequence_is_rejected(self):
        invalid_cases = (
            [
                {"message_type": "LOG_SEARCH", "message_input": {"condition": {"conditions": []}}},
                {"message_type": "SYSTEM_SELECTION", "message_input": {"system_ids": ["bk-audit"]}},
            ],
            [
                {"message_type": "SYSTEM_SELECTION", "message_input": {"system_ids": ["bk-audit"]}},
                {"message_type": "SYSTEM_SELECTION", "message_input": {"system_ids": ["bcs"]}},
            ],
        )

        for messages in invalid_cases:
            with self.subTest(messages=messages), self.assertRaises(ValidationError):
                MessagePlan.model_validate({"outcome": "dispatch", "messages": messages})

    def test_error_outcome_requires_code_and_empty_messages(self):
        plan = MessagePlan.model_validate({"outcome": "error", "messages": [], "error_code": "UNRECOGNIZED_INTENT"})
        self.assertEqual(plan.error_code, "UNRECOGNIZED_INTENT")

        with self.assertRaises(ValidationError):
            MessagePlan.model_validate({"outcome": "error", "messages": []})
        with self.assertRaises(ValidationError):
            MessagePlan.model_validate(
                {
                    "outcome": "error",
                    "messages": [{"message_type": "SYSTEM_SELECTION", "message_input": {"system_ids": ["bk-audit"]}}],
                    "error_code": "SYSTEM_REQUIRED",
                }
            )

    def test_invalid_condition_is_a_supported_business_error(self):
        """已识别检索意图但条件无法表达时，Schema 提供稳定业务分支。"""

        plan = MessagePlan.model_validate({"outcome": "error", "messages": [], "error_code": "INVALID_CONDITION"})

        self.assertEqual(plan.error_code, "INVALID_CONDITION")
        schema = MessagePlan.model_json_schema()
        error_description = schema["properties"]["error_code"]["description"]
        self.assertIn("INVALID_CONDITION", error_description)
        self.assertIn("字段、操作符或条件值", error_description)

    def test_condition_schema_exposes_query_type_and_operator_enums(self):
        """Agent 输出只使用查询执行层支持的稳定类型和操作符。"""

        schema = MessagePlan.model_json_schema()

        self.assertEqual(
            schema["$defs"]["FieldType"]["enum"],
            ["string", "double", "int", "long", "text", "timestamp", "float"],
        )
        self.assertIn("gt", schema["$defs"]["Operator"]["enum"])
        field_type = schema["$defs"]["AIConditionItem"]["properties"]["field_type"]
        self.assertEqual(field_type["default"], "string")


@mock.patch(f"{INTENT_MODULE}.api.bk_plugins_ai_agent.chat_completion")
class MessagePlanningContextTest(AIAssistantTestCase):
    """通用规划请求只携带当前决策需要的动态上下文。"""

    def _build_context(self):
        """构造不依赖接口返回的最小规划上下文。"""

        return MessagePlanningService.build_context(
            query_text="查审计中心日志",
            candidates=[{"system_id": "bk-audit", "name": "审计中心", "description": "合成系统"}],
            common_fields=[SelectionFieldMeta(raw_name="username", field_type="string", allow_operators=["eq"])],
            current_system=SelectionSystem(system_id="bk-audit", name="审计中心"),
            username=self.username,
            reference_time=datetime(2026, 9, 20, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        )

    def test_retry_feedback_is_sent_after_original_exchange(self, mock_chat):
        """纠错调用携带上一轮输出和归一化校验错误。"""

        previous_output = '{"outcome":"dispatch","messages":[]}'
        feedback = PlanningRetryFeedback(
            previous_output=previous_output,
            validation_errors=(
                {
                    "path": "messages",
                    "code": "value_error",
                    "message": "dispatch outcome requires messages",
                },
            ),
        )
        mock_chat.return_value = json.dumps({"outcome": "error", "messages": [], "error_code": "INVALID_CONDITION"})

        MessagePlanningService.plan(context=self._build_context(), retry_feedback=feedback)

        history = mock_chat.call_args.kwargs["chat_history"]
        self.assertEqual([item["role"] for item in history], ["role", "user", "assistant", "user"])
        self.assertEqual(history[2]["content"], previous_output)
        self.assertIn("dispatch outcome requires messages", history[3]["content"])

    def test_scope_validation_failure_keeps_full_agent_output_for_retry(self, mock_chat):
        """plan 内部范围校验失败时也必须保留可纠正的上一轮完整输出。"""

        raw_output = json.dumps(
            {
                "outcome": "dispatch",
                "messages": [
                    {
                        "message_type": "SYSTEM_SELECTION",
                        "message_input": {"system_ids": ["outside-system"]},
                    }
                ],
            }
        )
        mock_chat.return_value = raw_output

        with self.assertRaises(AIOutputInvalidError) as ctx:
            MessagePlanningService.plan(context=self._build_context())

        feedback = MessagePlanningService.build_retry_feedback(error=ctx.exception, plan=None)
        self.assertEqual(feedback.previous_output, raw_output)
        self.assertEqual(feedback.validation_errors[0]["code"], "system_id not in candidates")

    def test_schema_validation_retry_uses_full_output_without_expanding_log_extra(self, mock_chat):
        """纠错使用完整响应，异常日志仍只保留受控长度的摘要。"""

        raw_output = json.dumps(
            {
                "outcome": "dispatch",
                "messages": [
                    {
                        "message_type": "LOG_SEARCH",
                        "message_input": {
                            "condition": {
                                "conditions": [
                                    {
                                        "raw_name": "username",
                                        "field_type": "string",
                                        "operator": "unsupported",
                                        "filters": ["user_a"],
                                    }
                                ]
                            }
                        },
                    }
                ],
                "ignored_padding": "x" * 3000,
            }
        )

        with self.assertRaises(InvalidConditionError) as ctx:
            MessagePlanningService._parse_and_validate(raw_output)

        feedback = MessagePlanningService.build_retry_feedback(error=ctx.exception, plan=None)
        self.assertEqual(len(ctx.exception.extra["raw_output"]), 2048)
        self.assertEqual(feedback.previous_output, raw_output)

    def test_mixed_schema_errors_are_classified_as_output_invalid(self, mock_chat):
        """顶层协议错误不能被同一响应中的条件错误掩盖。"""

        raw_output = json.dumps(
            {
                "outcome": "unsupported",
                "messages": [
                    {
                        "message_type": "LOG_SEARCH",
                        "message_input": {
                            "condition": {
                                "conditions": [
                                    {
                                        "raw_name": "username",
                                        "field_type": "string",
                                        "operator": "unsupported",
                                        "filters": ["user_a"],
                                    }
                                ]
                            }
                        },
                    }
                ],
            }
        )

        with self.assertRaises(AIOutputInvalidError) as ctx:
            MessagePlanningService._parse_and_validate(raw_output)

        error_paths = {item["path"] for item in ctx.exception.extra["validation_errors"]}
        self.assertIn("outcome", error_paths)
        self.assertTrue(any("conditions" in path for path in error_paths))

    def test_plan_separates_stable_rules_from_runtime_context(self, mock_chat):
        mock_chat.return_value = json.dumps(
            {
                "outcome": "dispatch",
                "messages": [
                    {
                        "message_type": "SYSTEM_SELECTION",
                        "message_input": {"system_ids": ["bk-audit"]},
                    },
                    {
                        "message_type": "LOG_SEARCH",
                        "message_input": {
                            "condition": {
                                "conditions": [],
                                "start_time": "2026-09-19T10:00:00+08:00",
                                "end_time": "2026-09-20T10:00:00+08:00",
                            }
                        },
                    },
                ],
            }
        )
        context = MessagePlanningService.build_context(
            query_text="查审计中心昨天失败的操作",
            candidates=[
                {"system_id": "bk-audit", "name": "审计中心", "description": "审计日志检索"},
                {"system_id": "bcs", "name": "蓝盾", "description": "研发流水线"},
            ],
            common_fields=[SelectionFieldMeta(raw_name="username", display_name="操作人")],
            current_system=SelectionSystem(
                system_id="bk-audit",
                name="审计中心",
                description="审计日志检索",
                standard_fields=[
                    SelectionFieldMeta(
                        raw_name="action_id",
                        display_name="操作事件名(ID)",
                        sample_value="delete",
                        sample_value_display="删除",
                    )
                ],
            ),
            username=self.username,
            reference_time=datetime(2026, 9, 20, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        )

        plan = MessagePlanningService.plan(context=context)

        self.assertEqual([message.message_type for message in plan.messages], ["LOG_SEARCH"])
        request = mock_chat.call_args.kwargs
        self.assertNotIn("input", request)
        system_prompt = request["chat_history"][0]["content"]
        self.assertEqual(system_prompt, MessagePlanningService.system_prompt)
        self.assertEqual(request["chat_history"][1]["role"], "user")
        self.assertTrue(request["execute_kwargs"]["thread_id"].startswith("intent-planning-"))
        user_message = request["chat_history"][1]["content"]
        self.assertIn("# 本轮用户输入", user_message)
        self.assertIn("# 当前会话状态", user_message)
        self.assertIn("# 当前场景可选的已接入审计系统（按选择优先级排序）", user_message)
        self.assertIn("# 日志检索公共字段", user_message)
        self.assertIn("# 当前已选系统字段上下文", user_message)
        self.assertIn('"system_id": "bk-audit"', user_message)
        self.assertIn('"system_id": "bcs"', user_message)
        self.assertIn('"raw_name": "action_id"', user_message)
        self.assertNotIn("sample_value_display", user_message)
        self.assertIn('"current_system_id": "bk-audit"', user_message)
        self.assertIn('"has_selected_system": true', user_message)
        self.assertIn('"phase": "SYSTEM_SELECTED"', user_message)
        self.assertIn('"username":', user_message)
        self.assertIn('"timezone": "Asia/Shanghai"', user_message)
        self.assertIn('"previous_week_start": "2026-09-07T00:00:00+08:00"', user_message)
        self.assertIn('"previous_week_end": "2026-09-14T00:00:00+08:00"', user_message)
        self.assertNotIn("scope_type", user_message)
        self.assertNotIn("scope_id", user_message)
        self.assertNotIn("# 输出 JSON Schema", user_message)
        self.assertNotIn("# 业务规则", user_message)
        self.assertIn("# MessagePlan 输出 Schema", system_prompt)
        self.assertIn('"PlannedLogSearchMessage"', system_prompt)
        self.assertIn("SYSTEM_UNSELECTED", system_prompt)
        self.assertIn("SYSTEM_SELECTED", system_prompt)
        self.assertIn("error_code=SYSTEM_REQUIRED、messages=[]", system_prompt)
        self.assertIn("候选系统的数量不改变这条规则", system_prompt)
        self.assertIn('"error_code":"SYSTEM_REQUIRED"', system_prompt)
        self.assertIn("顺序最靠前", system_prompt)
        self.assertIn("即使当前只有一个候选，也不得自动选择", system_prompt)
        self.assertIn("未指定时间时默认最近一天", system_prompt)
        self.assertIn("raw_name 固定为 extend_data", system_prompt)
        self.assertIn("每个检索条件都必须完整保留", system_prompt)
        self.assertIn("INVALID_CONDITION", system_prompt)

    def test_system_prompt_is_generic_message_planner(self, mock_chat):
        self.assertIn("消息决策", MessagePlanningService.system_prompt)
        self.assertIn("username 仅表示当前请求用户身份", MessagePlanningService.system_prompt)
        self.assertIn("当前可选系统", MessagePlanningService.system_prompt)
        self.assertNotIn(
            "你的任务是把用户的自然语言检索需求转换成结构化的日志检索条件 JSON",
            MessagePlanningService.system_prompt,
        )

    def test_current_system_must_be_an_authorized_candidate(self, mock_chat):
        """当前系统详情不能绕过本轮授权候选集合进入 Agent 上下文。"""

        with self.assertRaises(ValidationError):
            MessagePlanningService.build_context(
                query_text="查询当前系统日志",
                candidates=[{"system_id": "bcs", "name": "蓝盾", "description": "研发流水线"}],
                common_fields=[],
                current_system=SelectionSystem(system_id="bk-audit", name="审计中心"),
                username=self.username,
                reference_time=datetime(2026, 9, 20, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            )

    def test_planning_context_only_summarizes_extension_samples(self, mock_chat):
        """普通字段不携带运行时样例，只有路径探索需要的拓展样例进入上下文。"""

        context = MessagePlanningService.build_context(
            query_text="查日志",
            candidates=[{"system_id": "bk-audit", "name": "审计中心", "description": "描" * 300}],
            common_fields=[
                SelectionFieldMeta(raw_name="long_text"),
                SelectionFieldMeta(raw_name="nested"),
            ],
            current_system=SelectionSystem(
                system_id="bk-audit",
                name="审计中心",
                description="描" * 300,
                standard_fields=[
                    SelectionFieldMeta(raw_name="long_text", sample_value="x" * 200),
                ],
                extension_fields=[
                    SelectionFieldMeta(
                        raw_name="extend_data",
                        keys=["request_data"],
                        sample_value={"level1": {"level2": {"secret": "value"}}},
                    )
                ],
            ),
            username=self.username,
            reference_time=datetime(2026, 9, 20, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        )

        user_message = MessagePlanningService.build_user_message(context)
        current_json = user_message.split("<current_system_detail>\n", 1)[1].split("\n</current_system_detail>", 1)[0]
        current_system = json.loads(current_json)
        extension = current_system["extension_fields"][0]

        self.assertEqual(len(current_system["description"]), 256)
        self.assertEqual(current_system["field_overrides"], [])
        self.assertNotIn("field_samples", current_system)
        self.assertNotIn("x" * 128, user_message)
        self.assertEqual(
            extension["sample_value"]["level1"]["level2"],
            {"truncated": True, "original_type": "object", "item_count": 1},
        )
        self.assertTrue(extension["sample_value_meta"]["truncated"])

    def test_current_system_detail_only_keeps_differences_from_common_fields(self, mock_chat):
        context = MessagePlanningService.build_context(
            query_text="查日志",
            candidates=[{"system_id": "bk-audit", "name": "审计中心"}],
            common_fields=[SelectionFieldMeta(raw_name="username", nl_name="操作人")],
            current_system=SelectionSystem(
                system_id="bk-audit",
                name="审计中心",
                standard_fields=[SelectionFieldMeta(raw_name="username", nl_name="执行人", sample_value="user_a")],
            ),
            username=self.username,
            reference_time=datetime(2026, 9, 20, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
        user_message = MessagePlanningService.build_user_message(context)
        current_json = user_message.split("<current_system_detail>\n", 1)[1].split("\n</current_system_detail>", 1)[0]
        current_system = json.loads(current_json)

        self.assertEqual(current_system["field_overrides"][0]["raw_name"], "username")
        self.assertEqual(current_system["field_overrides"][0]["nl_name"], "执行人")
        self.assertNotIn("field_samples", current_system)
        self.assertNotIn("user_a", user_message)


class LoadCandidatesTest(AIAssistantTestCase):
    """候选组装：当前范围权限 ∩ 已接入审计系统。"""

    def test_load_candidates_filters_by_permission(self):
        all_systems = [
            {"id": "bk-audit", "name": "审计中心", "audit_status": "accessed"},
            {"id": "bcs", "name": "蓝盾", "audit_status": "accessed"},
            {"id": "other", "name": "无权限系统", "audit_status": "accessed"},
        ]
        with mock.patch(
            "apps.meta.permissions.SearchLogPermission.get_auth_systems_by_username",
            return_value=(all_systems, ["bk-audit", "bcs"]),
        ):
            candidates = MessagePlanningService.load_candidates("bkaudit", self.username)
        self.assertEqual(candidates, CANDIDATES)

    def test_load_candidates_excludes_authorized_but_not_accessed_system(self):
        """有场景权限但尚未接入审计的系统不能暴露给 Agent。"""

        all_systems = [
            {"id": "bk-audit", "name": "审计中心", "audit_status": "accessed"},
            {"id": "pending-system", "name": "待接入系统", "audit_status": "pending"},
        ]
        with mock.patch(
            "apps.meta.permissions.SearchLogPermission.get_auth_systems_by_username",
            return_value=(all_systems, ["bk-audit", "pending-system"]),
        ):
            candidates = MessagePlanningService.load_candidates("bkaudit", self.username)

        self.assertEqual([candidate["system_id"] for candidate in candidates], ["bk-audit"])

    def test_load_candidates_preserves_given_priority_order(self):
        """候选顺序是同等匹配时的产品优先级，意图识别层不得重新排序。"""

        all_systems = [
            {"id": "iam_v4_bk-audit", "name": "审计中心", "audit_status": "accessed"},
            {"id": "bk-audit", "name": "审计中心", "audit_status": "accessed"},
            {"id": "bcs", "name": "蓝盾", "audit_status": "accessed"},
        ]
        with mock.patch(
            "apps.meta.permissions.SearchLogPermission.get_auth_systems_by_username",
            return_value=(all_systems, ["iam_v4_bk-audit", "bk-audit", "bcs"]),
        ):
            candidates = MessagePlanningService.load_candidates("bkaudit", self.username)

        self.assertEqual(
            [candidate["system_id"] for candidate in candidates],
            ["iam_v4_bk-audit", "bk-audit", "bcs"],
        )

    def test_load_candidates_with_scope(self):
        """传 scope：候选与检索页场景过滤同口径（get_scope_auth_systems），仅保留场景授权系统"""

        all_systems = [
            {"id": "bk-audit", "name": "审计中心", "audit_status": "accessed"},
            {"id": "bcs", "name": "蓝盾", "audit_status": "accessed"},
        ]
        with mock.patch(
            "apps.meta.permissions.SearchLogPermission.get_scope_auth_systems",
            return_value=["bk-audit"],
        ) as mock_scope, mock.patch(
            f"{INTENT_MODULE}.resource.meta.system_list_all",
            return_value=all_systems,
        ) as mock_list:
            candidates = MessagePlanningService.load_candidates(
                "bkaudit", self.username, scope_type="scene", scope_id="1"
            )
        self.assertEqual(candidates, [{"system_id": "bk-audit", "name": "审计中心", "description": ""}])
        mock_scope.assert_called_once_with("scene", "1", self.username)
        mock_list.assert_called_once_with(namespace="bkaudit", audit_status__in="accessed")

    def test_load_candidates_with_scope_no_permission(self):
        """scope 无权限：get_scope_auth_systems 的 [""] 兜底（ES filter 语义）被剔除，候选为空"""

        with mock.patch(
            "apps.meta.permissions.SearchLogPermission.get_scope_auth_systems",
            return_value=[""],
        ), mock.patch(
            f"{INTENT_MODULE}.resource.meta.system_list_all",
            return_value=[{"id": "bk-audit", "name": "审计中心", "audit_status": "accessed"}],
        ):
            candidates = MessagePlanningService.load_candidates(
                "bkaudit", self.username, scope_type="scene", scope_id="1"
            )
        self.assertEqual(candidates, [])

    def test_load_candidates_without_scope_keeps_legacy(self):
        """不传 scope：保持既有并集口径（旧前端兼容），不走场景过滤分支"""

        all_systems = [{"id": "bk-audit", "name": "审计中心", "audit_status": "accessed"}]
        with mock.patch(
            "apps.meta.permissions.SearchLogPermission.get_auth_systems_by_username",
            return_value=(all_systems, ["bk-audit"]),
        ), mock.patch(
            "apps.meta.permissions.SearchLogPermission.get_scope_auth_systems",
        ) as mock_scope:
            candidates = MessagePlanningService.load_candidates("bkaudit", self.username)
        self.assertEqual(candidates, CANDIDATES[:1])
        mock_scope.assert_not_called()


class IntentAgentRoutingTest(AIAssistantTestCase):
    """意图识别智能体环境路由开关（默认专属 / 应急切共享）。

    定案（2026-09-15 确认）：默认专属智能体 bp-ai-user-intent——生产（上云）
    BK_API_URL_TMPL 独立域名模板默认链路直接跑通；bkop 统一域名模板下该网关未注册
    （2026-09-14 线上 404 事故），经 BKAPP_AI_USER_INTENT_API_URL 直连独立域名解决
    （第 1 层优先级）。
    """

    def test_default_routes_to_dedicated_agent(self):
        """默认：路由到 USER_INTENT 专属智能体（生产默认链路零额外配置）"""

        self.assertEqual(MessagePlanningService.agent_code, AIAgentCode.USER_INTENT)
        self.assertEqual(resolve_intent_agent_code(), AIAgentCode.USER_INTENT)

    @override_settings(AI_USER_INTENT_AGENT_CODE="RISK_SEARCH")
    def test_switch_routes_to_other_agent(self):
        """应急口：BKAPP_AI_USER_INTENT_AGENT_CODE 可覆盖路由到其他智能体（枚举名任意）"""

        self.assertEqual(resolve_intent_agent_code(), AIAgentCode.RISK_SEARCH)

    @override_settings(AI_USER_INTENT_AGENT_CODE="NOT_EXIST")
    def test_invalid_switch_fails_fast(self):
        """非法枚举名：启动即快速失败（ImproperlyConfigured），防静默走错智能体"""

        with self.assertRaises(ImproperlyConfigured):
            resolve_intent_agent_code()
