# -*- coding: utf-8 -*-
"""USER_INTENT 意图识别任务测试：三类场景路由 + 平台守门 + 续链与标题。"""

from unittest import mock

from services.web.ai_assistant.constants import ExecutionStatus, MessageType
from services.web.ai_assistant.handlers import message_handler_registry
from services.web.ai_assistant.models import Message
from services.web.ai_assistant.schemas import parse_snapshot
from services.web.ai_assistant.services.message_execution import MessageExecution
from services.web.ai_assistant.tasks.audit_search import execute_user_intent
from services.web.query.ai_assistant.schemas import IntentPayload
from tests.test_ai_assistant.base import (
    TARGET_SYSTEM_ID,
    AIAssistantPlatformTestCase,
    make_condition,
    make_log_search_output,
    make_selection_output,
)

HANDLERS_MODULE = "services.web.ai_assistant.handlers.audit_search"
TITLE_DELAY = "services.web.ai_assistant.tasks.conversation.generate_conversation_title.delay"
CONVERT_MOCK = "services.web.query.ai_assistant.services.nl2json.NL2JSONService.convert"


def create_intent_message(testcase, query_text="看审计中心近七天 hermit 的操作记录"):
    """构造 PROCESSING 状态的 USER_INTENT 消息与其执行上下文。"""
    message = Message.objects.create(
        conversation=testcase.conversation,
        parent_message=None,
        message_type=MessageType.USER_INTENT,
        status=ExecutionStatus.PROCESSING,
        task_id="task-1",
        input_data={"query_text": query_text, "auto_execute": True},
        context_data={"username": testcase.user, "namespace": "bkaudit"},
        created_by=testcase.user,
        updated_by=testcase.user,
    )
    handler = message_handler_registry.require(MessageType.USER_INTENT)
    execution = MessageExecution(
        message=message,
        input_data=parse_snapshot(handler.input_model, message.input_data, field_name="input_data"),
        context_data=parse_snapshot(handler.context_model, message.context_data, field_name="context_data"),
    )
    return message, execution


class UserIntentExecutionTest(AIAssistantPlatformTestCase):
    """意图路由三类场景 + SYSTEM_REQUIRED 守门 + 复用/续链/标题"""

    def _create_intent_message(self, query_text="看审计中心近七天 hermit 的操作记录"):
        return create_intent_message(self, query_text)

    def _run(self, payload, with_selection=False, convert=None):
        """mock 意图/条件识别后执行任务，返回 (message, output, mock_delay)。"""
        if with_selection:
            self.create_selection_message()
        message, execution = self._create_intent_message()
        convert_mock = mock.MagicMock(return_value=convert or make_condition())
        if convert is not None and isinstance(convert, Exception):
            convert_mock.side_effect = convert
        with mock.patch(
            "services.web.query.ai_assistant.services.intent.IntentRecognitionService.load_candidates",
            return_value=[{"system_id": TARGET_SYSTEM_ID, "name": "审计中心"}],
        ), mock.patch(
            "services.web.query.ai_assistant.services.intent.IntentRecognitionService.recognize",
            mock.MagicMock(return_value=payload),
        ), mock.patch(
            CONVERT_MOCK, convert_mock
        ), mock.patch(
            f"{HANDLERS_MODULE}.LogSearchService.search", return_value=make_log_search_output()
        ), mock.patch(
            f"{HANDLERS_MODULE}.FieldContextService.build_selection", return_value=make_selection_output()
        ), mock.patch(
            f"{HANDLERS_MODULE}.OperationContextService.build", return_value=([], [])
        ), mock.patch(
            TITLE_DELAY
        ) as mock_delay:
            output = execute_user_intent.run(execution)
            # 完整执行链：run 产出 output 后由平台收敛终态并续链/派发标题
            execute_user_intent._finish_success(execution=execution, task_id="task-1", output_data=output)
        return message, output, mock_delay

    def _selection_count(self):
        return Message.objects.filter(conversation=self.conversation, message_type=MessageType.SYSTEM_SELECTION).count()

    def test_select_system_and_search(self):
        """场景③ 选系统+检索：建 SELECTION → 条件识别 → 续链 LOG_SEARCH（父=意图消息）→ 派发标题"""

        message, output, mock_delay = self._run(
            payload=IntentPayload(intent="select_system", system_id=TARGET_SYSTEM_ID, message="已为您选择审计中心"),
        )

        self.assertEqual(output.intent, "select_system")
        self.assertEqual(output.system_id, TARGET_SYSTEM_ID)
        self.assertIsNotNone(output.condition)
        self.assertIsNone(output.error)
        selection = Message.objects.filter(
            conversation=self.conversation, message_type=MessageType.SYSTEM_SELECTION
        ).first()
        self.assertIsNotNone(selection)
        self.assertIsNone(selection.parent_message)
        log_search = Message.objects.filter(
            conversation=self.conversation, message_type=MessageType.LOG_SEARCH, parent_message=message
        ).first()
        self.assertIsNotNone(log_search)
        self.assertEqual(output.selection_message_uid, str(selection.uid))
        mock_delay.assert_called_once_with(conversation_id=self.conversation.id, query_text="看审计中心近七天 hermit 的操作记录")

    def test_log_search_with_current_selection(self):
        """场景② 纯检索（已有系统）：复用当前 SELECTION 不新建，直接条件识别续链"""

        selection = self.create_selection_message()
        message, output, _ = self._run(
            payload=IntentPayload(intent="log_search", system_id="", message="好的，为您检索"),
        )

        self.assertEqual(output.intent, "log_search")
        self.assertIsNotNone(output.condition)
        self.assertEqual(self._selection_count(), 1)
        self.assertEqual(output.selection_message_uid, str(selection.uid))
        # 续链产物必须真实存在：_create_log_search 的异常会被 _finish_success
        # 静默吞掉（续链失败不回滚终态），不断言子消息则该调用点破损无法被发现
        log_search = Message.objects.filter(
            conversation=self.conversation, message_type=MessageType.LOG_SEARCH, parent_message=message
        ).first()
        self.assertIsNotNone(log_search)

    def test_log_search_without_selection_requires_system(self):
        """场景②无系统变体：SYSTEM_REQUIRED 守门（AI 动态引导 + 候选清单），不建子消息不派发标题"""

        message, output, mock_delay = self._run(
            payload=IntentPayload(intent="log_search", system_id="", message="好的，为您检索"),
        )

        self.assertEqual(output.intent, "log_search")
        self.assertIsNone(output.condition)
        self.assertEqual(output.error.error_code, "SYSTEM_REQUIRED")
        self.assertIn("审计中心", output.error.error_message)
        self.assertEqual(output.error.candidates, [{"system_id": TARGET_SYSTEM_ID, "name": "审计中心"}])
        self.assertEqual(self._selection_count(), 0)
        self.assertFalse(
            Message.objects.filter(conversation=self.conversation, message_type=MessageType.LOG_SEARCH).exists()
        )
        # 检索意图明确（log_search）：仍派发标题（与 unrecognized 闲聊不同）
        mock_delay.assert_called_once()

    def test_select_system_hit_current_reuses(self):
        """select_system 命中当前系统：复用 SELECTION 不重建，仍续条件识别"""

        selection = self.create_selection_message()
        message, output, _ = self._run(
            payload=IntentPayload(intent="select_system", system_id=TARGET_SYSTEM_ID, message="继续在审计中心查询"),
        )

        self.assertEqual(self._selection_count(), 1)
        self.assertEqual(output.selection_message_uid, str(selection.uid))
        self.assertIsNotNone(output.condition)

    def test_pure_select_system_condition_not_recognized(self):
        """场景① 纯选系统（"切到蓝盾"）：SELECTION 保留切换生效，条件识别失败走结构化 error"""

        from services.web.query.ai_assistant.exceptions import QueryNotRecognizedError

        message, output, mock_delay = self._run(
            payload=IntentPayload(intent="select_system", system_id=TARGET_SYSTEM_ID, message="已为您切换"),
            convert=QueryNotRecognizedError(),
        )

        self.assertEqual(output.intent, "select_system")
        self.assertEqual(output.system_id, TARGET_SYSTEM_ID)
        self.assertIsNone(output.condition)
        self.assertEqual(output.error.error_code, QueryNotRecognizedError().error_code)
        # SELECTION 已建保留（切换不被检索失败阻塞），无 LOG_SEARCH 子消息
        self.assertEqual(self._selection_count(), 1)
        self.assertFalse(
            Message.objects.filter(conversation=self.conversation, message_type=MessageType.LOG_SEARCH).exists()
        )
        # 意图成功仍派发标题
        mock_delay.assert_called_once()

    def test_unrecognized_returns_ai_message(self):
        """unrecognized：AI 动态说明为什么不行，不派发标题"""

        message, output, mock_delay = self._run(
            payload=IntentPayload(intent="unrecognized", system_id="", message="没理解您的需求，想查哪个系统的日志？"),
        )

        self.assertEqual(output.intent, "unrecognized")
        self.assertEqual(output.error.error_code, "UNRECOGNIZED_INTENT")
        self.assertIn("没理解", output.error.error_message)
        self.assertEqual(self._selection_count(), 0)
        mock_delay.assert_not_called()


class UserIntentHandlerTest(AIAssistantPlatformTestCase):
    """Handler prepare：入口消息无父校验 + 输入与 NL 同构"""

    def test_prepare_rejects_parent(self):
        from services.web.ai_assistant.exceptions import InvalidParentMessage

        selection = self.create_selection_message()
        handler = message_handler_registry.require(MessageType.USER_INTENT)
        with self.assertRaises(InvalidParentMessage):
            handler.prepare(
                user=self.user,
                conversation=self.conversation,
                parent_message=selection,
                input_data=handler.input_model(query_text="查日志"),
            )

    def test_log_search_parent_whitelist_accepts_user_intent(self):
        """LOG_SEARCH 父消息白名单接受 USER_INTENT（续链合法性：父须已成功）"""

        message, _ = create_intent_message(self)
        # 生产路径续链发生在 _finish_success 收敛 SUCCESS 之后，此处同步置成功并落路由结果再校验白名单
        Message.objects.filter(id=message.id).update(
            status=ExecutionStatus.SUCCESS, output_data={"system_id": TARGET_SYSTEM_ID}
        )
        message.refresh_from_db()
        from services.web.ai_assistant.services.message import MessageService

        with mock.patch(
            "services.web.ai_assistant.handlers.audit_search.LogSearchService.search",
            return_value=make_log_search_output(),
        ):
            child = MessageService(user=self.user).create(
                conversation=self.conversation,
                message_type=MessageType.LOG_SEARCH,
                input_data={"condition": make_condition().model_dump(mode="json")},
                parent_message_uid=str(message.uid),
            )
        self.assertEqual(child.parent_message.id, message.id)
