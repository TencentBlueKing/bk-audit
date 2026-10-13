# -*- coding: utf-8 -*-
"""会话 scope 唯一来源为 Conversation，历史消息执行也不得回退到客户端或父消息快照。"""

from unittest import mock

from services.web.ai_assistant.constants import ExecutionStatus, MessageType
from services.web.ai_assistant.handlers import message_handler_registry
from services.web.ai_assistant.models import Message
from services.web.ai_assistant.schemas import parse_snapshot
from services.web.ai_assistant.schemas.audit_search import (
    LogSearchInputSchema,
    SystemSelectionInputSchema,
    UserIntentInputSchema,
    UserIntentOutputSchema,
)
from services.web.ai_assistant.serializers.message import MessageResponseSerializer
from services.web.ai_assistant.services.message_execution import (
    MessageExecution,
    load_message_execution,
)
from services.web.ai_assistant.tasks.audit_search import execute_user_intent
from services.web.query.ai_assistant.schemas import (
    AIConditionItem,
    AIConditionPayload,
    MessagePlan,
    PlannedLogSearchInput,
    PlannedLogSearchMessage,
    PlannedSystemSelectionMessage,
    SystemSelectionInput,
)
from tests.test_ai_assistant.base import (
    TARGET_SYSTEM_ID,
    AIAssistantPlatformTestCase,
    make_condition,
    make_log_search_output,
    make_selection_output,
)

HANDLERS_MODULE = "services.web.ai_assistant.handlers.audit_search"
TITLE_DELAY = "services.web.ai_assistant.tasks.conversation.generate_conversation_title.delay"


class MessageDurationTest(AIAssistantPlatformTestCase):
    """消息响应耗时字段：duration_seconds = finished_at - created_at（端到端，含排队与 LLM 编排）。"""

    def _create_message(self, status: str) -> Message:
        return Message.objects.create(
            conversation=self.conversation,
            parent_message=None,
            message_type=MessageType.USER_INTENT,
            status=status,
            task_id="" if status == ExecutionStatus.SUCCESS else "task-1",
            input_data={"query_text": "查日志", "auto_execute": True},
            context_data={
                "username": self.user,
                "namespace": "bkaudit",
                "scope_type": self.conversation.scope_type,
                "scope_id": self.conversation.scope_id,
            },
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

    def test_duration_seconds_clamped_on_timestamp_inversion(self):
        """历史时间戳微秒倒挂时钳位为 0.0。"""

        from datetime import timedelta

        from django.utils import timezone

        message = self._create_message(ExecutionStatus.SUCCESS)
        created = timezone.now()
        Message.objects.filter(id=message.id).update(
            created_at=created,
            queued_at=created,
            finished_at=created - timedelta(microseconds=400),  # 微秒级倒挂
        )
        message.refresh_from_db()

        data = MessageResponseSerializer(message).data
        # 不再出现 -0.0，钳位为 0.0
        self.assertEqual(data["duration_seconds"], 0.0)
        self.assertNotEqual(str(data["duration_seconds"]), "-0.0")

    """历史 input_data（无 scope 字段）的 schema 层宽松解析。"""

    def test_legacy_user_intent_input_parses(self):
        legacy = {"query_text": "看下审计中心近七天的操作记录", "auto_execute": True}
        parsed = parse_snapshot(UserIntentInputSchema, legacy, field_name="input_data")
        self.assertEqual(parsed.query_text, legacy["query_text"])
        self.assertEqual(parsed.model_dump(mode="json"), legacy)

    def test_legacy_selection_input_parses(self):
        legacy = {"system_ids": [TARGET_SYSTEM_ID]}
        parsed = parse_snapshot(SystemSelectionInputSchema, legacy, field_name="input_data")
        self.assertEqual(parsed.system_ids, [TARGET_SYSTEM_ID])
        self.assertEqual(parsed.model_dump(mode="json"), legacy)

    def test_prepare_derives_session_scope_from_conversation(self):
        """SYSTEM_SELECTION 与 USER_INTENT 不要求客户端提交会话 scope。"""

        for handler_type in (MessageType.USER_INTENT, MessageType.SYSTEM_SELECTION):
            handler = message_handler_registry.require(handler_type)
            if handler_type == MessageType.USER_INTENT:
                input_data = handler.input_model(query_text="查日志")
            else:
                input_data = handler.input_model(system_ids=[TARGET_SYSTEM_ID])
            preparation = handler.prepare(
                user=self.user,
                conversation=self.conversation,
                parent_message=None,
                input_data=input_data,
            )
            self.assertEqual(preparation.context_data.scope_type, self.conversation.scope_type)
            self.assertEqual(preparation.context_data.scope_id, self.conversation.scope_id)


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


class SessionScopePreparationTest(AIAssistantPlatformTestCase):
    def test_log_search_ignores_parent_context_scope_and_uses_conversation(self):
        parent = self.create_selection_message()
        parent.context_data = {
            "username": self.user,
            "namespace": "bkaudit",
            "scope_type": "system",
            "scope_id": "stale-system",
        }
        handler = message_handler_registry.require(MessageType.LOG_SEARCH)

        preparation = handler.prepare(
            user=self.user,
            conversation=self.conversation,
            parent_message=parent,
            input_data=LogSearchInputSchema(condition=make_condition()),
        )

        self.assertEqual(
            (preparation.context_data.session_scope_type, preparation.context_data.session_scope_id),
            (self.conversation.scope_type, self.conversation.scope_id),
        )

    def test_user_intent_execution_loads_conversation_with_message(self):
        message = Message.objects.create(
            conversation=self.conversation,
            message_type=MessageType.USER_INTENT,
            status=ExecutionStatus.PROCESSING,
            task_id="task-scope",
            input_data={"query_text": "查日志", "auto_execute": True},
            context_data={
                "username": self.user,
                "namespace": "bkaudit",
                "scope_type": self.conversation.scope_type,
                "scope_id": self.conversation.scope_id,
            },
            created_by=self.user,
            updated_by=self.user,
        )

        execution = load_message_execution(
            message_id=message.id,
            task_id="task-scope",
            celery_task_id="task-scope",
        )

        self.assertEqual(execution.message._state.fields_cache["conversation"].pk, self.conversation.pk)


class LegacyIntentRetryTest(AIAssistantPlatformTestCase):
    """历史 USER_INTENT 重试派生的业务消息使用 Conversation scope。"""

    def test_retry_binds_derived_messages_to_conversation_scope(self):
        message = Message.objects.create(
            conversation=self.conversation,
            parent_message=None,
            message_type=MessageType.USER_INTENT,
            status=ExecutionStatus.PROCESSING,
            task_id="task-1",
            # 上下文中的历史 scope 不是事实来源；派生消息必须使用 Conversation 的绑定。
            input_data={"query_text": "看下审计中心的操作记录", "auto_execute": True},
            context_data={
                "username": self.user,
                "namespace": "bkaudit",
                "scope_type": "system",
                "scope_id": "stale-system",
            },
            created_by=self.user,
            updated_by=self.user,
        )
        handler = message_handler_registry.require(MessageType.USER_INTENT)
        execution = MessageExecution(
            message=message,
            input_data=parse_snapshot(handler.input_model, message.input_data, field_name="input_data"),
            context_data=parse_snapshot(handler.context_model, message.context_data, field_name="context_data"),
        )

        with mock.patch(
            "services.web.ai_assistant.tasks.audit_search.MessagePlanningService.load_candidates",
            return_value=[{"system_id": TARGET_SYSTEM_ID, "name": "审计中心"}],
        ), mock.patch(
            "services.web.ai_assistant.tasks.audit_search.FieldContextService.build_common_fields",
            return_value=make_selection_output().systems[0].standard_fields,
        ), mock.patch(
            "services.web.ai_assistant.tasks.audit_search.FieldContextService.build_selection",
            return_value=make_selection_output(),
        ), mock.patch(
            "services.web.ai_assistant.tasks.audit_search.MessagePlanningService.plan",
            return_value=MessagePlan(
                outcome="dispatch",
                messages=[
                    PlannedSystemSelectionMessage(
                        message_type="SYSTEM_SELECTION",
                        message_input=SystemSelectionInput(system_ids=[TARGET_SYSTEM_ID]),
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
                                        filters=["admin"],
                                    )
                                ]
                            )
                        ),
                    ),
                ],
            ),
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
            resolved = execute_user_intent.run(execution)
            output = UserIntentOutputSchema.model_validate(
                execute_user_intent._finish_success(
                    execution=execution,
                    task_id=message.task_id,
                    output_data=resolved,
                )
            )

        self.assertEqual(output.intent, "select_system")
        self.assertEqual(output.system_id, TARGET_SYSTEM_ID)
        self.assertIsNone(output.condition)
        self.assertTrue(output.log_search_message_uid)
        new_selection = (
            Message.objects.filter(conversation=self.conversation, message_type=MessageType.SYSTEM_SELECTION)
            .order_by("-id")
            .first()
        )
        self.assertIsNotNone(new_selection)
        self.assertEqual(
            (
                (new_selection.context_data or {}).get("scope_type"),
                (new_selection.context_data or {}).get("scope_id"),
            ),
            (self.conversation.scope_type, self.conversation.scope_id),
        )
        self.assertNotIn("scope_type", new_selection.input_data)
        self.assertNotIn("scope_id", new_selection.input_data)
