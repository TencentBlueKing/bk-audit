# -*- coding: utf-8 -*-
"""用户意图识别服务测试（一期 v6）：IntentPayload 契约 + schema 注入 + 候选白名单。"""

import json
from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from pydantic import ValidationError
from requests.exceptions import Timeout

from api.constants import AIAgentCode
from services.web.query.ai_assistant.exceptions import (
    AIOutputInvalidError,
    AIOutputParseFailedError,
    AIServiceError,
    AITimeoutError,
)
from services.web.query.ai_assistant.schemas import (
    MessagePlan,
    SelectionFieldMeta,
    SelectionSystem,
)
from services.web.query.ai_assistant.services.intent import (
    IntentRecognitionService,
    MessagePlanningService,
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


@mock.patch(f"{INTENT_MODULE}.api.bk_plugins_ai_agent.chat_completion")
class MessagePlanningContextTest(AIAssistantTestCase):
    """通用规划请求只携带当前决策需要的动态上下文。"""

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
        self.assertIn("# 用户原话", user_message)
        self.assertIn("# 会话状态", user_message)
        self.assertIn("# 授权系统摘要", user_message)
        self.assertIn("# 公共标准字段", user_message)
        self.assertIn("# 当前系统详情", user_message)
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
        self.assertIn("唯一候选", system_prompt)
        self.assertIn("未指定时间时默认最近一天", system_prompt)
        self.assertIn("raw_name 固定为 extend_data", system_prompt)
        self.assertIn("每个检索条件都必须完整保留", system_prompt)

    def test_system_prompt_is_generic_message_planner(self, mock_chat):
        self.assertIn("消息决策", MessagePlanningService.system_prompt)
        self.assertIn("username 仅表示当前请求用户身份", MessagePlanningService.system_prompt)
        self.assertIn("授权系统摘要", MessagePlanningService.system_prompt)
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

    def test_planning_context_deterministically_summarizes_large_samples(self, mock_chat):
        """规划上下文限制描述和样例体积，并为每次裁剪保留可诊断元数据。"""

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
                    SelectionFieldMeta(
                        raw_name="nested",
                        sample_value={"level1": {"level2": {"secret": "value"}}},
                    ),
                ],
            ),
            username=self.username,
            reference_time=datetime(2026, 9, 20, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
        )

        user_message = MessagePlanningService.build_user_message(context)
        current_json = user_message.split("<current_system_detail>\n", 1)[1].split("\n</current_system_detail>", 1)[0]
        current_system = json.loads(current_json)
        samples = {item["raw_name"]: item for item in current_system["field_samples"]}
        long_text = samples["long_text"]
        nested = samples["nested"]

        self.assertEqual(len(current_system["description"]), 256)
        self.assertEqual(current_system["field_overrides"], [])
        self.assertEqual(len(long_text["sample_value"]), 128)
        self.assertEqual(
            long_text["sample_value_meta"],
            {"truncated": True, "original_type": "string", "original_length": 200},
        )
        self.assertEqual(
            nested["sample_value"]["level1"]["level2"],
            {"truncated": True, "original_type": "object", "item_count": 1},
        )
        self.assertTrue(nested["sample_value_meta"]["truncated"])

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
        self.assertEqual(current_system["field_samples"][0]["sample_value"], "user_a")


@mock.patch(f"{INTENT_MODULE}.api.bk_plugins_ai_agent.chat_completion")
class IntentRecognitionServiceTest(AIAssistantTestCase):
    """意图识别：schema 注入 + 三类意图 + 候选白名单 + 异常映射"""

    def _recognize(self, current_system_id="", candidates=CANDIDATES):
        return IntentRecognitionService.recognize(
            query_text="我要看审计中心近七天 eval_user_alpha 的操作记录",
            candidates=candidates,
            current_system_id=current_system_id,
            username=self.username,
        )

    def test_recognize_select_system(self, mock_chat):
        """选系统意图：AI 输出契约解析 + User Message 注入 schema 与候选"""

        mock_chat.return_value = json.dumps(
            {"intent": "select_system", "system_id": "bk-audit", "message": "已为您选择审计中心"}
        )

        payload = self._recognize()

        self.assertEqual(payload.intent, "select_system")
        self.assertEqual(payload.system_id, "bk-audit")
        self.assertEqual(payload.message, "已为您选择审计中心")
        _, kwargs = mock_chat.call_args
        user_message = kwargs["input"]
        self.assertIn('"intent"', user_message)
        self.assertIn("意图分类：选系统（含同时要检索）", user_message)
        self.assertIn("bk-audit", user_message)
        self.assertIn("审计中心", user_message)
        self.assertEqual(kwargs["agent_code"], IntentRecognitionService.agent_code)
        # 意图识别路由专属生产 agent（bp-ai-user-intent，与 NL2JSON 的检索 agent 解耦）——
        # 硬断言防误回退到共享检索 agent（提示词冲突的已知权衡曾因此存在）；
        # bkop 地址差异由 BKAPP_AI_USER_INTENT_API_URL 直连解决（2026-09-14 线上 404 事故定案）
        self.assertEqual(kwargs["agent_code"], AIAgentCode.USER_INTENT)
        self.assertEqual(kwargs["user"], self.username)
        self.assertFalse(kwargs["execute_kwargs"]["stream"])

    def test_recognize_log_search(self, mock_chat):
        """当前系统检索意图：system_id 留空"""

        mock_chat.return_value = json.dumps(
            {"intent": "log_search", "system_id": "", "need_search": True, "message": "好的，为您检索"}
        )
        payload = self._recognize(current_system_id="bk-audit")
        self.assertEqual(payload.intent, "log_search")
        self.assertEqual(payload.system_id, "")

    def test_recognize_unrecognized(self, mock_chat):
        """无法识别：intent=unrecognized，message 为 AI 动态引导话术"""

        mock_chat.return_value = json.dumps(
            {"intent": "unrecognized", "system_id": "", "message": "抱歉，没理解您的需求，可以说要查哪个系统的日志"}
        )
        payload = self._recognize()
        self.assertEqual(payload.intent, "unrecognized")
        self.assertIn("没理解", payload.message)

    def test_recognize_condition_only_query_prompt_rule(self, mock_chat):
        """回归：纯条件罗列（无检索动词）必须判为检索诉求——prompt 注入条件描述判定规则。

        线上报障：用户输入「extend.request_data为{...}，extend._request_url为http://...」
        通篇无检索动词与系统指向，意图被误判 unrecognized（"未能理解当前意图"）。
        修复：意图规则明确「字段为/=/是 + 值」类条件描述本身即日志检索需求，
        即使无检索动词也判 log_search；含条件描述的话语不得判 unrecognized。
        """

        mock_chat.return_value = json.dumps(
            {"intent": "log_search", "system_id": "", "need_search": True, "message": "好的，为您检索"}
        )
        payload = IntentRecognitionService.recognize(
            query_text=(
                'extend.request_data为{"id":"20260910204720871773","pk":"20260910204720871773"},'
                "extend._request_url为http://bkaudit-api.example.com/api/v1/risks/20260910204720871773/"
            ),
            candidates=CANDIDATES,
            current_system_id="bk-audit",
            username=self.username,
        )
        self.assertEqual(payload.intent, "log_search")
        self.assertEqual(payload.system_id, "")
        # User Message 注入条件描述判定规则与用户原话（URL 用 example.com 占位避免敏感扫描）
        _, kwargs = mock_chat.call_args
        user_message = kwargs["input"]
        self.assertIn("字段为值", user_message)
        self.assertIn("检索条件描述", user_message)
        self.assertIn("不得判 unrecognized", user_message)
        self.assertIn("extend.request_data", user_message)

    def test_parse_fenced_json(self, mock_chat):
        """代码块包裹输出：三级递进提取（复用 NL2JSON 闸门）"""

        raw = {"intent": "log_search", "system_id": "", "need_search": True, "message": "ok"}
        mock_chat.return_value = f"识别结果如下：\n```json\n{json.dumps(raw)}\n```"
        payload = self._recognize()
        self.assertEqual(payload.intent, "log_search")

    def test_parse_failed(self, mock_chat):
        """非合法 JSON：AIOutputParseFailedError（触发调用方预算重试）"""

        mock_chat.return_value = "这不是 JSON"
        with self.assertRaises(AIOutputParseFailedError):
            self._recognize()

    def test_schema_validation_failed(self, mock_chat):
        """缺 intent 字段：形态不合契约"""

        mock_chat.return_value = json.dumps({"system_id": "bk-audit"})
        with self.assertRaises(AIOutputParseFailedError):
            self._recognize()

    def test_invalid_intent_value_rejected(self, mock_chat):
        """intent 非法枚举值：契约校验拒绝"""

        mock_chat.return_value = json.dumps({"intent": "hack_intent", "system_id": "", "message": "x"})
        with self.assertRaises(AIOutputParseFailedError):
            self._recognize()

    def test_system_not_in_candidates_rejected(self, mock_chat):
        """越权 system_id（不在候选内）：AIOutputInvalidError（防幻觉越权）"""

        mock_chat.return_value = json.dumps({"intent": "select_system", "system_id": "no-perm-system", "message": "x"})
        with self.assertRaises(AIOutputInvalidError):
            self._recognize()

    def test_select_system_empty_system_id_rejected(self, mock_chat):
        """select_system 但 system_id 为空：组合契约在 schema 阶段拒绝。"""

        mock_chat.return_value = json.dumps({"intent": "select_system", "system_id": "", "message": "x"})
        with self.assertRaises(AIOutputParseFailedError):
            self._recognize()

    def test_log_search_requires_need_search_and_empty_system_id(self, mock_chat):
        """log_search 必须明确检索且不得携带系统，防止下游按矛盾字段续链。"""

        invalid_payloads = [
            {"intent": "log_search", "system_id": "", "need_search": False, "message": "x"},
            {"intent": "log_search", "system_id": "bk-audit", "need_search": True, "message": "x"},
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                mock_chat.return_value = json.dumps(payload)
                with self.assertRaises(AIOutputParseFailedError):
                    self._recognize(current_system_id="bk-audit")

    def test_unrecognized_rejects_system_and_search_flags(self, mock_chat):
        """unrecognized 不得夹带确定的系统或检索续链标记。"""

        mock_chat.return_value = json.dumps(
            {"intent": "unrecognized", "system_id": "bk-audit", "need_search": True, "message": "x"}
        )
        with self.assertRaises(AIOutputParseFailedError):
            self._recognize()

    def test_timeout_and_service_error(self, mock_chat):
        """AIDev 超时 / 服务异常：稳定异常映射（触发调用方重试）"""

        mock_chat.side_effect = Timeout("t")
        with self.assertRaises(AITimeoutError):
            self._recognize()
        mock_chat.side_effect = RuntimeError("down")
        with self.assertRaises(AIServiceError):
            self._recognize()


class LoadCandidatesTest(AIAssistantTestCase):
    """候选组装：全量系统 ∩ 用户检索权限"""

    def test_load_candidates_filters_by_permission(self):
        all_systems = [
            {"id": "bk-audit", "name": "审计中心"},
            {"id": "bcs", "name": "蓝盾"},
            {"id": "other", "name": "无权限系统"},
        ]
        with mock.patch(
            "apps.meta.permissions.SearchLogPermission.get_auth_systems_by_username",
            return_value=(all_systems, ["bk-audit", "bcs"]),
        ):
            candidates = IntentRecognitionService.load_candidates("bkaudit", self.username)
        self.assertEqual(candidates, CANDIDATES)

    def test_load_candidates_with_scope(self):
        """传 scope：候选与检索页场景过滤同口径（get_scope_auth_systems），仅保留场景授权系统"""

        all_systems = [
            {"id": "bk-audit", "name": "审计中心"},
            {"id": "bcs", "name": "蓝盾"},
        ]
        with mock.patch(
            "apps.meta.permissions.SearchLogPermission.get_scope_auth_systems",
            return_value=["bk-audit"],
        ) as mock_scope, mock.patch(
            f"{INTENT_MODULE}.resource.meta.system_list_all",
            return_value=all_systems,
        ) as mock_list:
            candidates = IntentRecognitionService.load_candidates(
                "bkaudit", self.username, scope_type="scene", scope_id="1"
            )
        self.assertEqual(candidates, [{"system_id": "bk-audit", "name": "审计中心", "description": ""}])
        mock_scope.assert_called_once_with("scene", "1", self.username)
        mock_list.assert_called_once_with(namespace="bkaudit")

    def test_load_candidates_with_scope_no_permission(self):
        """scope 无权限：get_scope_auth_systems 的 [""] 兜底（ES filter 语义）被剔除，候选为空"""

        with mock.patch(
            "apps.meta.permissions.SearchLogPermission.get_scope_auth_systems",
            return_value=[""],
        ), mock.patch(
            f"{INTENT_MODULE}.resource.meta.system_list_all",
            return_value=[{"id": "bk-audit", "name": "审计中心"}],
        ):
            candidates = IntentRecognitionService.load_candidates(
                "bkaudit", self.username, scope_type="scene", scope_id="1"
            )
        self.assertEqual(candidates, [])

    def test_load_candidates_without_scope_keeps_legacy(self):
        """不传 scope：保持既有并集口径（旧前端兼容），不走场景过滤分支"""

        all_systems = [{"id": "bk-audit", "name": "审计中心"}]
        with mock.patch(
            "apps.meta.permissions.SearchLogPermission.get_auth_systems_by_username",
            return_value=(all_systems, ["bk-audit"]),
        ), mock.patch(
            "apps.meta.permissions.SearchLogPermission.get_scope_auth_systems",
        ) as mock_scope:
            candidates = IntentRecognitionService.load_candidates("bkaudit", self.username)
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

        self.assertEqual(IntentRecognitionService.agent_code, AIAgentCode.USER_INTENT)
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
