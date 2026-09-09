# -*- coding: utf-8 -*-
"""协议升级历史快照兼容性测试：scope 协议（2026-09-08）升级前落库的消息不得因新必填校验而读取失败。

双层校验语义：
- schema 层 scope_type 可选（None）：历史消息快照的读取/重试宽松通过（v1 兜底行为）
- Handler.prepare 层必填：外部创建/编辑不传 scope_type → 400（ScopeContextRequired）
"""

from unittest import mock

from services.web.ai_assistant.constants import ExecutionStatus, MessageType
from services.web.ai_assistant.exceptions import ScopeContextRequired
from services.web.ai_assistant.handlers import message_handler_registry
from services.web.ai_assistant.models import Message
from services.web.ai_assistant.schemas import parse_snapshot
from services.web.ai_assistant.schemas.audit_search import (
    SystemSelectionInputSchema,
    UserIntentInputSchema,
)
from services.web.ai_assistant.serializers.message import MessageResponseSerializer
from services.web.ai_assistant.services.message_execution import MessageExecution
from services.web.ai_assistant.tasks.audit_search import execute_user_intent
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


class MessageDurationTest(AIAssistantPlatformTestCase):
    """消息响应耗时字段：duration_seconds = finished_at - created_at（端到端，含排队与 LLM 编排）。"""

    def _create_message(self, status: str) -> Message:
        return Message.objects.create(
            conversation=self.conversation,
            parent_message=None,
            message_type=MessageType.USER_INTENT,
            status=status,
            task_id="" if status == ExecutionStatus.SUCCESS else "task-1",
            input_data={"query_text": "查日志", "auto_execute": True, "scope_type": "cross_system"},
            context_data={"username": self.user, "namespace": "bkaudit", "scope_type": "cross_system"},
            output_data=(
                {
                    "intent": "log_search",
                    "error": {"error_code": "SYSTEM_REQUIRED", "error_message": "x", "candidates": []},
                }
                if status == ExecutionStatus.SUCCESS
                else None
            ),
            created_by=self.user,
            updated_by=self.user,
        )

    def test_duration_seconds_on_success(self):
        from datetime import timedelta

        from django.utils import timezone

        message = self._create_message(ExecutionStatus.SUCCESS)
        created = timezone.now() - timedelta(seconds=12.34)
        finished = created + timedelta(seconds=12.34)
        Message.objects.filter(id=message.id).update(created_at=created, queued_at=created, finished_at=finished)
        message.refresh_from_db()

        data = MessageResponseSerializer(message).data
        # 端到端耗时（保留 1 位小数），含排队与 LLM 编排全过程
        self.assertEqual(data["duration_seconds"], 12.3)
        self.assertIsNotNone(data["finished_at"])
        self.assertIsNotNone(data["queued_at"])

    def test_duration_seconds_null_on_processing(self):
        message = self._create_message(ExecutionStatus.PROCESSING)

        data = MessageResponseSerializer(message).data
        self.assertIsNone(data["duration_seconds"])
        self.assertIsNone(data["finished_at"])

    """历史 input_data（无 scope 字段）的 schema 层宽松解析。"""

    def test_legacy_user_intent_input_parses(self):
        legacy = {"query_text": "看下审计中心近七天的操作记录", "auto_execute": True}
        parsed = parse_snapshot(UserIntentInputSchema, legacy, field_name="input_data")
        self.assertEqual(parsed.query_text, legacy["query_text"])
        self.assertIsNone(parsed.scope_type)

    def test_legacy_selection_input_parses(self):
        legacy = {"system_ids": [TARGET_SYSTEM_ID]}
        parsed = parse_snapshot(SystemSelectionInputSchema, legacy, field_name="input_data")
        self.assertEqual(parsed.system_ids, [TARGET_SYSTEM_ID])
        self.assertIsNone(parsed.scope_type)

    def test_prepare_rejects_missing_scope_for_external_creation(self):
        """外部创建/编辑路径强约束：schema 宽松解析出的 None 在 prepare 拒绝（400）。"""

        for handler_type in (MessageType.USER_INTENT, MessageType.SYSTEM_SELECTION):
            handler = message_handler_registry.require(handler_type)
            if handler_type == MessageType.USER_INTENT:
                input_data = handler.input_model(query_text="查日志")
            else:
                input_data = handler.input_model(system_ids=[TARGET_SYSTEM_ID])
            with self.assertRaises(ScopeContextRequired):
                handler.prepare(
                    user=self.user,
                    conversation=self.conversation,
                    parent_message=None,
                    input_data=input_data,
                )


class LegacyMessageResponseTest(AIAssistantPlatformTestCase):
    """历史消息的消息响应序列化（列表/详情读取路径）不得因协议升级报错。"""

    def _create_legacy_message(self, message_type: str, input_data: dict, output_data: dict) -> Message:
        return Message.objects.create(
            conversation=self.conversation,
            parent_message=None,
            message_type=message_type,
            status=ExecutionStatus.SUCCESS,
            input_data=input_data,
            context_data={"username": self.user, "namespace": "bkaudit"},
            output_data=output_data,
            created_by=self.user,
            updated_by=self.user,
        )

    def test_legacy_selection_message_serializes(self):
        message = self._create_legacy_message(
            MessageType.SYSTEM_SELECTION,
            {"system_ids": [TARGET_SYSTEM_ID]},
            make_selection_output().model_dump(mode="json"),
        )
        data = MessageResponseSerializer(message).data
        self.assertEqual(data["message_type"], str(MessageType.SYSTEM_SELECTION))
        # 宽松序列化：scope_type 为 None 不炸，其余字段完整
        self.assertEqual(data["input_data"]["system_ids"], [TARGET_SYSTEM_ID])

    def test_legacy_user_intent_message_serializes(self):
        message = self._create_legacy_message(
            MessageType.USER_INTENT,
            {"query_text": "看下审计中心近七天的操作记录", "auto_execute": True},
            # 历史 USER_INTENT 成功消息输出：SYSTEM_REQUIRED 结构化错误形态
            {
                "intent": "log_search",
                "error": {"error_code": "SYSTEM_REQUIRED", "error_message": "请先选择系统", "candidates": []},
            },
        )
        data = MessageResponseSerializer(message).data
        self.assertEqual(data["message_type"], str(MessageType.USER_INTENT))
        self.assertEqual(data["input_data"]["query_text"], "看下审计中心近七天的操作记录")


class LegacyIntentRetryTest(AIAssistantPlatformTestCase):
    """历史 USER_INTENT 消息（context 无 scope）重试：建 SELECTION 补 cross_system 宽口径兜底（v1 行为）。"""

    def test_retry_without_scope_rebuilds_selection_with_fallback(self):
        message = Message.objects.create(
            conversation=self.conversation,
            parent_message=None,
            message_type=MessageType.USER_INTENT,
            status=ExecutionStatus.PROCESSING,
            task_id="task-1",
            # 历史快照：input_data 无 scope，context_data 无 scope
            input_data={"query_text": "看下审计中心的操作记录", "auto_execute": True},
            context_data={"username": self.user, "namespace": "bkaudit"},
            created_by=self.user,
            updated_by=self.user,
        )
        handler = message_handler_registry.require(MessageType.USER_INTENT)
        execution = MessageExecution(
            message=message,
            input_data=parse_snapshot(handler.input_model, message.input_data, field_name="input_data"),
            context_data=parse_snapshot(handler.context_model, message.context_data, field_name="context_data"),
        )

        from services.web.query.ai_assistant.schemas import IntentPayload

        with mock.patch(
            "services.web.query.ai_assistant.services.intent.IntentRecognitionService.load_candidates",
            return_value=[{"system_id": TARGET_SYSTEM_ID, "name": "审计中心"}],
        ), mock.patch(
            "services.web.query.ai_assistant.services.intent.IntentRecognitionService.recognize",
            mock.MagicMock(
                return_value=IntentPayload(intent="select_system", system_id=TARGET_SYSTEM_ID, message="ok")
            ),
        ), mock.patch(
            CONVERT_MOCK, mock.MagicMock(return_value=make_condition())
        ), mock.patch(
            f"{HANDLERS_MODULE}.LogSearchService.search", return_value=make_log_search_output()
        ), mock.patch(
            f"{HANDLERS_MODULE}.FieldContextService.build_selection", return_value=make_selection_output()
        ), mock.patch(
            f"{HANDLERS_MODULE}.OperationContextService.build", return_value=([], [])
        ), mock.patch(
            f"{HANDLERS_MODULE}.SearchLogPermission.get_scope_auth_systems",
            return_value=[TARGET_SYSTEM_ID],
        ), mock.patch(
            TITLE_DELAY
        ):
            output = execute_user_intent.run(execution)

        # v1 兜底：无 scope 时系统路由仍成功，SELECTION 以 cross_system 宽口径建链
        self.assertEqual(output.intent, "select_system")
        self.assertEqual(output.system_id, TARGET_SYSTEM_ID)
        self.assertIsNotNone(output.condition)
        new_selection = (
            Message.objects.filter(conversation=self.conversation, message_type=MessageType.SYSTEM_SELECTION)
            .order_by("-id")
            .first()
        )
        self.assertIsNotNone(new_selection)
        self.assertEqual((new_selection.context_data or {}).get("scope_type"), "cross_system")
