# -*- coding: utf-8 -*-
"""消息服务集成与 NL 续链测试（同步失败不创建 / 续链同步执行）。"""

from unittest import mock

from services.web.ai_assistant.constants import ExecutionStatus, MessageType
from services.web.ai_assistant.exceptions import SystemSelectionRequired
from services.web.ai_assistant.models import Message
from services.web.ai_assistant.schemas import parse_snapshot
from services.web.ai_assistant.services.message import MessageService
from services.web.ai_assistant.services.message_execution import MessageExecution
from services.web.ai_assistant.tasks.audit_search import execute_natural_language_search
from services.web.query.ai_assistant.exceptions import AIOutputInvalidError
from tests.test_ai_assistant.base import (
    TARGET_SYSTEM_ID,
    AIAssistantPlatformTestCase,
    make_condition,
    make_log_search_output,
)


class TestMessageCreation(AIAssistantPlatformTestCase):
    """MessageService 与 Handler 的集成行为。"""

    def test_create_system_selection_success(self):
        """SYNC 消息：服务全部 mock 成功后直接落库 SUCCESS。"""

        with self.patch_field_context(), self.patch_operation_context():
            message = MessageService(user=self.user).create(
                conversation=self.conversation,
                message_type=MessageType.SYSTEM_SELECTION,
                input_data={"system_ids": [TARGET_SYSTEM_ID]},
            )
        self.assertEqual(message.status, ExecutionStatus.SUCCESS)
        self.assertIsNone(message.parent_message)
        self.assertEqual(message.output_data["systems"][0]["system_id"], TARGET_SYSTEM_ID)
        self.assertEqual(message.output_data["common_operations"], [])

    def test_create_log_search_failure_no_message(self):
        """同步检索失败时消息不创建（异常冒泡，不落库）。"""

        self.create_selection_message()
        before = Message.objects.count()
        with mock.patch(
            "services.web.ai_assistant.handlers.audit_search.LogSearchService.search",
            side_effect=AIOutputInvalidError(),
        ):
            with self.assertRaises(AIOutputInvalidError):
                MessageService(user=self.user).create(
                    conversation=self.conversation,
                    message_type=MessageType.LOG_SEARCH,
                    input_data={"condition": make_condition().model_dump(mode="json")},
                )
        self.assertEqual(Message.objects.count(), before)

    def test_create_log_search_binds_latest_selection(self):
        """未传 parent 时创建的检索消息自动绑定最新成功选择。"""

        self.create_selection_message()
        latest = self.create_selection_message()
        with mock.patch(
            "services.web.ai_assistant.handlers.audit_search.LogSearchService.search",
            return_value=make_log_search_output(),
        ):
            message = MessageService(user=self.user).create(
                conversation=self.conversation,
                message_type=MessageType.LOG_SEARCH,
                input_data={"condition": make_condition().model_dump(mode="json")},
            )
        self.assertEqual(message.status, ExecutionStatus.SUCCESS)
        self.assertEqual(message.parent_message.id, latest.id)

    def test_create_nl_without_selection_raises(self):
        """无系统选择时创建自然语言消息直接稳定报错，不落库。"""

        with self.assertRaises(SystemSelectionRequired):
            MessageService(user=self.user).create(
                conversation=self.conversation,
                message_type=MessageType.NATURAL_LANGUAGE_SEARCH,
                input_data={"query_text": "查一下 admin 的日志"},
            )


class TestNLExecutionChain(AIAssistantPlatformTestCase):
    """NL 异步任务执行与续链（直接驱动 task 的 run/_finish_success）。"""

    def _create_processing_nl(self, auto_execute: bool = True):
        selection = self.create_selection_message()
        nl_message = self.create_nl_message(
            auto_execute=auto_execute,
            parent=selection,
            status=ExecutionStatus.PROCESSING,
        )
        # 复用平台解析函数构造类型化执行快照
        from services.web.ai_assistant.handlers import message_handler_registry

        nl_handler = message_handler_registry.require(MessageType.NATURAL_LANGUAGE_SEARCH)
        execution = MessageExecution(
            message=nl_message,
            input_data=parse_snapshot(nl_handler.input_model, nl_message.input_data, field_name="input_data"),
            context_data=parse_snapshot(nl_handler.context_model, nl_message.context_data, field_name="context_data"),
        )
        return nl_message, execution

    def test_nl_success_with_auto_log_search(self):
        """NL 成功后续链同步执行 LOG_SEARCH 子消息。"""

        nl_message, execution = self._create_processing_nl(auto_execute=True)
        condition = make_condition()
        with mock.patch(
            "services.web.ai_assistant.tasks.audit_search.NL2JSONService.convert",
            return_value=condition,
        ), mock.patch(
            "services.web.ai_assistant.handlers.audit_search.LogSearchService.search",
            return_value=make_log_search_output(total=5),
        ):
            output = execute_natural_language_search.run(execution)
            execute_natural_language_search._finish_success(
                execution=execution, task_id=nl_message.task_id, output_data=output
            )
        nl_message.refresh_from_db()
        self.assertEqual(nl_message.status, ExecutionStatus.SUCCESS)
        self.assertIsNotNone(nl_message.output_data)
        # 续链子消息：parent 为 NL，同步执行已 SUCCESS
        child = Message.objects.filter(parent_message=nl_message, message_type=MessageType.LOG_SEARCH).first()
        self.assertIsNotNone(child)
        self.assertEqual(child.status, ExecutionStatus.SUCCESS)
        self.assertEqual(child.output_data["total"], 5)
        self.assertEqual(child.context_data["source"], "natural_language")

    def test_auto_execute_false_skips_chain(self):
        """auto_execute=False 时不创建续链子消息。"""

        nl_message, execution = self._create_processing_nl(auto_execute=False)
        with mock.patch(
            "services.web.ai_assistant.tasks.audit_search.NL2JSONService.convert",
            return_value=make_condition(),
        ):
            output = execute_natural_language_search.run(execution)
            execute_natural_language_search._finish_success(
                execution=execution, task_id=nl_message.task_id, output_data=output
            )
        nl_message.refresh_from_db()
        self.assertEqual(nl_message.status, ExecutionStatus.SUCCESS)
        self.assertFalse(
            Message.objects.filter(parent_message=nl_message, message_type=MessageType.LOG_SEARCH).exists()
        )

    def test_chain_failure_keeps_nl_success(self):
        """续链失败不影响 NL 消息 SUCCESS（子消息不创建）。"""

        nl_message, execution = self._create_processing_nl(auto_execute=True)
        with mock.patch(
            "services.web.ai_assistant.tasks.audit_search.NL2JSONService.convert",
            return_value=make_condition(),
        ), mock.patch(
            "services.web.ai_assistant.handlers.audit_search.LogSearchService.search",
            side_effect=AIOutputInvalidError(),
        ):
            output = execute_natural_language_search.run(execution)
            execute_natural_language_search._finish_success(
                execution=execution, task_id=nl_message.task_id, output_data=output
            )
        nl_message.refresh_from_db()
        self.assertEqual(nl_message.status, ExecutionStatus.SUCCESS)
        self.assertFalse(
            Message.objects.filter(parent_message=nl_message, message_type=MessageType.LOG_SEARCH).exists()
        )
