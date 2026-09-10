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


def create_intent_message(testcase, query_text="看审计中心近七天 hermit 的操作记录", scope_extra=None):
    """构造 PROCESSING 状态的 USER_INTENT 消息与其执行上下文。

    scope_extra：场景过滤参数（{scope_type, scope_id}），同时写入输入与上下文快照，
    模拟前端发起对话时携带左上角场景过滤器当前选择；缺省 cross_system
    （宽松语义，单元测试不关心具体场景）。
    """
    scope = scope_extra or {"scope_type": "cross_system"}
    input_data = {"query_text": query_text, "auto_execute": True}
    input_data.update(scope)
    context_data = {"username": testcase.user, "namespace": "bkaudit"}
    context_data.update(scope)
    message = Message.objects.create(
        conversation=testcase.conversation,
        parent_message=None,
        message_type=MessageType.USER_INTENT,
        status=ExecutionStatus.PROCESSING,
        task_id="task-1",
        input_data=input_data,
        context_data=context_data,
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
            # session scope 校验：建 SELECTION 时 system_id 必须在 scope 候选内
            f"{HANDLERS_MODULE}.SearchLogPermission.get_scope_auth_systems",
            return_value=[TARGET_SYSTEM_ID],
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
            payload=IntentPayload(
                intent="select_system", system_id=TARGET_SYSTEM_ID, need_search=True, message="已为您选择审计中心"
            ),
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
            payload=IntentPayload(
                intent="select_system", system_id=TARGET_SYSTEM_ID, need_search=True, message="继续在审计中心查询"
            ),
        )

        self.assertEqual(self._selection_count(), 1)
        self.assertEqual(output.selection_message_uid, str(selection.uid))
        self.assertIsNotNone(output.condition)

    def test_pure_switch_without_search(self):
        """报障回归：纯切换（"切换到 test0907"，need_search=false）——不调条件解析、不续链检索、无报错。

        修复前：纯切换被强绑条件解析，「切换到X」类语句必然解析失败并误报
        「未能理解检索需求」（切换其实已成功）；修复后切换即本轮终点。
        """

        message, output, mock_delay = self._run(
            payload=IntentPayload(intent="select_system", system_id=TARGET_SYSTEM_ID, need_search=False),
        )

        self.assertEqual(output.intent, "select_system")
        self.assertEqual(output.system_id, TARGET_SYSTEM_ID)
        # 切换成功：无 error、无检索条件、文案面向用户
        self.assertIsNone(output.error)
        self.assertIsNone(output.condition)
        self.assertIn("已为您切换到 审计中心", output.message)
        # 仅 1 条 SELECTION（切换生效）、0 条 LOG_SEARCH（不追加检索）
        self.assertEqual(self._selection_count(), 1)
        self.assertFalse(
            Message.objects.filter(conversation=self.conversation, message_type=MessageType.LOG_SEARCH).exists()
        )
        self.assertTrue(output.selection_message_uid)
        # 意图成功仍派发标题
        mock_delay.assert_called_once()

    def test_condition_transient_failure_raises_for_retry(self):
        """[review P2] 条件识别暂态故障（超时/服务异常/超预算解析失败）冒泡收敛 FAILED：
        MessageService.retry 仅接受 FAILED——SUCCESS+error 协议会让用户无法重试这类
        可恢复失败；确定性业务失败（未识别/输出非法）才走 SUCCESS+error。"""

        from services.web.query.ai_assistant.exceptions import AITimeoutError

        selection = self.create_selection_message()
        with self.assertRaises(AITimeoutError):
            self._run(
                payload=IntentPayload(intent="log_search", system_id="", need_search=True, message="好的"),
                convert=AITimeoutError(),
            )
        # 暂态失败不产生结构化 error 输出（任务由平台收敛 FAILED，重试接口可用）
        self.assertEqual(self._selection_count(), 1)

    def test_select_system_with_search_condition_not_recognized(self):
        """切换并检索（need_search=true）但条件识别失败：切换结果不被掩盖，文案前置切换成功事实"""

        from services.web.query.ai_assistant.exceptions import QueryNotRecognizedError

        message, output, mock_delay = self._run(
            payload=IntentPayload(
                intent="select_system", system_id=TARGET_SYSTEM_ID, need_search=True, message="已为您切换"
            ),
            convert=QueryNotRecognizedError(),
        )

        self.assertEqual(output.intent, "select_system")
        self.assertEqual(output.system_id, TARGET_SYSTEM_ID)
        self.assertIsNone(output.condition)
        self.assertEqual(output.error.error_code, QueryNotRecognizedError().error_code)
        # 兜底文案：检索失败不掩盖切换成功（修复前整句"未能理解检索需求"误导用户）
        self.assertIn("已为您切换到 审计中心", output.error.error_message)
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
                input_data=handler.input_model(query_text="查日志", scope_type="cross_system"),
            )

    def test_scope_input_validation(self):
        """scope 双层校验：schema 层宽松（历史快照兼容）+ prepare 层必填；scene/system 必填 scope_id"""

        from pydantic import ValidationError as PydanticValidationError

        from services.web.ai_assistant.exceptions import ScopeContextRequired

        handler = message_handler_registry.require(MessageType.USER_INTENT)
        # schema 层宽松：不传 scope_type 可解析（历史消息快照兼容，读取/重试不报错）
        legacy_parsed = handler.input_model(query_text="查日志")
        self.assertIsNone(legacy_parsed.scope_type)
        # prepare 层强约束：外部创建不传 scope_type → 400（ScopeContextRequired）
        with self.assertRaises(ScopeContextRequired):
            handler.prepare(
                user=self.user,
                conversation=self.conversation,
                parent_message=None,
                input_data=legacy_parsed,
            )
        # scene 缺 scope_id 拒绝（schema 层）
        with self.assertRaises(PydanticValidationError):
            handler.input_model(query_text="查日志", scope_type="scene")
        # system 缺 scope_id 拒绝（schema 层）
        with self.assertRaises(PydanticValidationError):
            handler.input_model(query_text="查日志", scope_type="system")
        # 非法 scope_type 拒绝（schema 层）
        with self.assertRaises(PydanticValidationError):
            handler.input_model(query_text="查日志", scope_type="hack_scope")
        # 合法组合：prepare 将 scope 固化到上下文（重试/编辑复用同一 scope 语义）
        preparation = handler.prepare(
            user=self.user,
            conversation=self.conversation,
            parent_message=None,
            input_data=handler.input_model(query_text="查日志", scope_type="scene", scope_id="1"),
        )
        self.assertEqual(preparation.context_data.scope_type, "scene")
        self.assertEqual(preparation.context_data.scope_id, "1")
        # cross_scene 无需 scope_id
        preparation_cross = handler.prepare(
            user=self.user,
            conversation=self.conversation,
            parent_message=None,
            input_data=handler.input_model(query_text="查日志", scope_type="cross_scene"),
        )
        self.assertEqual(preparation_cross.context_data.scope_type, "cross_scene")
        self.assertEqual(preparation_cross.context_data.scope_id, "")

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


class UserIntentScopeFilterTest(AIAssistantPlatformTestCase):
    """场景过滤（scope）：候选收窄 + scope 外当前系统失效 + 空候选引导

    前端发起对话时携带左上角场景过滤器当前选择（scope_type/scope_id），
    意图识别的候选系统与检索页同口径收窄，AI 无法路由到场景外系统。
    """

    SCOPE = {"scope_type": "scene", "scope_id": "1"}

    def _run_with_scope(self, payload, candidates, with_selection=False):
        """带 scope 上下文执行意图任务，返回 (message, output, load_candidates_mock)。"""

        if with_selection:
            self.create_selection_message()
        message, execution = create_intent_message(
            self,
            query_text="看下最近的操作日志",
            scope_extra=self.SCOPE,
        )
        load_candidates_mock = mock.MagicMock(return_value=candidates)
        with mock.patch(
            "services.web.query.ai_assistant.services.intent.IntentRecognitionService.load_candidates",
            load_candidates_mock,
        ), mock.patch(
            "services.web.query.ai_assistant.services.intent.IntentRecognitionService.recognize",
            mock.MagicMock(return_value=payload),
        ), mock.patch(
            CONVERT_MOCK, mock.MagicMock(return_value=make_condition())
        ), mock.patch(
            f"{HANDLERS_MODULE}.LogSearchService.search", return_value=make_log_search_output()
        ), mock.patch(
            f"{HANDLERS_MODULE}.FieldContextService.build_selection", return_value=make_selection_output()
        ), mock.patch(
            f"{HANDLERS_MODULE}.OperationContextService.build", return_value=([], [])
        ), mock.patch(
            # session scope 校验：建 SELECTION 时 system_id 必须在 scope 候选内
            f"{HANDLERS_MODULE}.SearchLogPermission.get_scope_auth_systems",
            return_value=[c["system_id"] for c in candidates] or [TARGET_SYSTEM_ID],
        ), mock.patch(
            TITLE_DELAY
        ):
            output = execute_user_intent.run(execution)
        return message, output, load_candidates_mock

    def test_scope_passed_to_load_candidates(self):
        """scope 透传候选组装：与检索页场景过滤同口径"""

        _, _, load_mock = self._run_with_scope(
            payload=IntentPayload(intent="log_search", system_id="", message="好的，为您检索"),
            candidates=[{"system_id": TARGET_SYSTEM_ID, "name": "审计中心"}],
        )
        load_mock.assert_called_once_with("bkaudit", self.user, scope_type="scene", scope_id="1")

    def test_scope_out_current_selection_invalidated(self):
        """scope 外当前系统失效：log_search 不复用旧系统，走 SYSTEM_REQUIRED 引导场景内重选"""

        selection = self.create_selection_message()
        _, output, _ = self._run_with_scope(
            payload=IntentPayload(intent="log_search", system_id="", message="好的，为您检索"),
            # scope 候选不含当前会话系统（TARGET_SYSTEM_ID）
            candidates=[{"system_id": "other-system", "name": "其他系统"}],
        )

        self.assertEqual(output.intent, "log_search")
        self.assertIsNone(output.condition)
        self.assertEqual(output.error.error_code, "SYSTEM_REQUIRED")
        self.assertEqual(output.error.candidates, [{"system_id": "other-system", "name": "其他系统"}])
        # 不新建选择、不复用 scope 外选择
        self.assertEqual(self._selection_count(), 1)
        self.assertNotEqual(output.selection_message_uid, str(selection.uid))
        self.assertFalse(output.selection_message_uid)

    def test_scope_in_current_selection_reused(self):
        """scope 内当前系统：正常复用不失效"""

        selection = self.create_selection_message()
        _, output, _ = self._run_with_scope(
            payload=IntentPayload(intent="log_search", system_id="", message="好的，为您检索"),
            candidates=[{"system_id": TARGET_SYSTEM_ID, "name": "审计中心"}],
        )

        self.assertIsNotNone(output.condition)
        self.assertEqual(output.selection_message_uid, str(selection.uid))
        self.assertEqual(self._selection_count(), 1)

    def test_scope_empty_candidates_message(self):
        """场景内无授权系统：SYSTEM_REQUIRED 专属文案 + 空候选清单"""

        _, output, _ = self._run_with_scope(
            payload=IntentPayload(intent="log_search", system_id="", message="好的，为您检索"),
            candidates=[],
        )

        self.assertEqual(output.error.error_code, "SYSTEM_REQUIRED")
        self.assertIn("暂无可检索的系统", output.error.error_message)
        self.assertEqual(output.error.candidates, [])

    def test_scope_out_select_system_rebuilds_selection(self):
        """scope 外当前系统 + select_system：按 scope 候选重建选择（不命中旧系统）"""

        self.create_selection_message()
        _, output, _ = self._run_with_scope(
            payload=IntentPayload(intent="select_system", system_id="other-system", need_search=True, message="已为您切换"),
            candidates=[{"system_id": "other-system", "name": "其他系统"}],
        )

        self.assertEqual(output.intent, "select_system")
        self.assertEqual(output.system_id, "other-system")
        # 重建选择：旧（scope 外）+ 新（scope 内）各一条
        self.assertEqual(self._selection_count(), 2)
        self.assertIsNotNone(output.condition)
        # 新建的 SELECTION 子消息透传 session scope（续链继承同一场景）
        new_selection = (
            Message.objects.filter(conversation=self.conversation, message_type=MessageType.SYSTEM_SELECTION)
            .order_by("-id")
            .first()
        )
        self.assertEqual((new_selection.context_data or {}).get("scope_type"), self.SCOPE["scope_type"])
        self.assertEqual((new_selection.context_data or {}).get("scope_id"), self.SCOPE["scope_id"])

    def _selection_count(self):
        return Message.objects.filter(conversation=self.conversation, message_type=MessageType.SYSTEM_SELECTION).count()
