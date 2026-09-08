# -*- coding: utf-8 -*-
"""用户意图识别服务测试（一期 v6）：IntentPayload 契约 + schema 注入 + 候选白名单。"""

import json
from unittest import mock

from requests.exceptions import Timeout

from services.web.query.ai_assistant.exceptions import (
    AIOutputInvalidError,
    AIOutputParseFailedError,
    AIServiceError,
    AITimeoutError,
)
from services.web.query.ai_assistant.services.intent import IntentRecognitionService
from tests.test_query.test_ai_assistant.base import AIAssistantTestCase

INTENT_MODULE = "services.web.query.ai_assistant.services.intent"

CANDIDATES = [
    {"system_id": "bk-audit", "name": "审计中心"},
    {"system_id": "bcs", "name": "蓝盾"},
]


@mock.patch(f"{INTENT_MODULE}.api.bk_plugins_ai_agent.chat_completion")
class IntentRecognitionServiceTest(AIAssistantTestCase):
    """意图识别：schema 注入 + 三类意图 + 候选白名单 + 异常映射"""

    def _recognize(self, current_system_id="", candidates=CANDIDATES):
        return IntentRecognitionService.recognize(
            query_text="我要看审计中心近七天 hermit 的操作记录",
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
        self.assertEqual(kwargs["user"], self.username)
        self.assertFalse(kwargs["execute_kwargs"]["stream"])

    def test_recognize_log_search(self, mock_chat):
        """当前系统检索意图：system_id 留空"""

        mock_chat.return_value = json.dumps({"intent": "log_search", "system_id": "", "message": "好的，为您检索"})
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

    def test_parse_fenced_json(self, mock_chat):
        """代码块包裹输出：三级递进提取（复用 NL2JSON 闸门）"""

        raw = {"intent": "log_search", "system_id": "", "message": "ok"}
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
        """select_system 但 system_id 为空：不合法"""

        mock_chat.return_value = json.dumps({"intent": "select_system", "system_id": "", "message": "x"})
        with self.assertRaises(AIOutputInvalidError):
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
        self.assertEqual(candidates, [{"system_id": "bk-audit", "name": "审计中心"}])
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
