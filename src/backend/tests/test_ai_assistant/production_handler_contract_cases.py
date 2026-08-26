# -*- coding: utf-8 -*-
"""生产消息 Handler 的行为契约用例。

契约门禁（production_handler_contracts.MESSAGE_HANDLER_CONTRACTS）要求每个
生产消息 Handler 都有按执行模式约定的行为契约测试：
- SYNC：test_success_contract / test_invalid_output_contract
- ASYNC：test_success_contract / test_failure_contract / test_retry_contract / test_stale_task_contract

SYNC 契约复用 test_handlers 中与业务 Handler 同源的成功/非法输出用例；
ASYNC 的 retry/stale 契约走平台任务投递（与 MessageTaskTest.invoke 同一模式）。
"""

from unittest import mock

from celery.exceptions import Ignore, Retry

from services.web.ai_assistant.constants import ExecutionStatus, MessageType
from services.web.ai_assistant.handlers import message_handler_registry
from services.web.ai_assistant.handlers.audit_search import (
    LogSearchHandler,
    NaturalLanguageSearchHandler,
    SystemSelectionHandler,
)
from services.web.ai_assistant.models import Message
from services.web.ai_assistant.schemas.audit_search import (
    LogSearchInputSchema,
    NLSearchInputSchema,
)
from services.web.ai_assistant.tasks.audit_search import execute_natural_language_search
from tests.test_ai_assistant.base import (
    AIAssistantPlatformTestCase,
    ensure_business_handlers_registered,
    make_condition,
)
from tests.test_ai_assistant.handlers import EchoAsyncHandler, register_test_message_handler
from tests.test_ai_assistant.test_handlers import (
    TestLogSearchHandler,
    TestNaturalLanguageSearchHandler,
    TestSystemSelectionHandler,
)


class SystemSelectionHandlerContract(AIAssistantPlatformTestCase):
    """SYSTEM_SELECTION（SYNC）契约：成功执行 + 非正常输出收敛为稳定错误。"""

    def setUp(self):
        super().setUp()
        self.handler = SystemSelectionHandler()

    test_success_contract = TestSystemSelectionHandler.test_execute_assembles_fields_and_operations
    test_invalid_output_contract = TestSystemSelectionHandler.test_execute_permission_denied_converted


class LogSearchHandlerContract(AIAssistantPlatformTestCase):
    """LOG_SEARCH（SYNC）契约：成功检索 + 非法输入收敛为稳定错误。"""

    def setUp(self):
        super().setUp()
        self.handler = LogSearchHandler()

    def _prepare(self, parent=None, condition=None):
        """与 TestLogSearchHandler._prepare 同源，供契约别名方法复用。"""

        return self.handler.prepare(
            user=self.user,
            conversation=self.conversation,
            parent_message=parent,
            input_data=LogSearchInputSchema(condition=condition or make_condition()),
        )

    test_success_contract = TestLogSearchHandler.test_execute_calls_search_service
    test_invalid_output_contract = TestLogSearchHandler.test_prepare_rejects_scope_mismatch


class NaturalLanguageSearchHandlerContract(AIAssistantPlatformTestCase):
    """NATURAL_LANGUAGE_SEARCH（ASYNC）契约：prepare 成功/失败 + 平台任务重试/陈旧投递。"""

    def setUp(self):
        super().setUp()
        self.handler = NaturalLanguageSearchHandler()
        self.input = NLSearchInputSchema(query_text="查一下 admin 的日志")
        # retry/stale 契约走平台任务投递；Echo Handler 临时占用该消息类型提供快照恢复
        register_test_message_handler(EchoAsyncHandler())

    def tearDown(self):
        message_handler_registry.unregister(MessageType.NATURAL_LANGUAGE_SEARCH)
        ensure_business_handlers_registered()
        super().tearDown()

    test_success_contract = TestNaturalLanguageSearchHandler.test_prepare_resolves_latest_selection_without_parent
    test_failure_contract = TestNaturalLanguageSearchHandler.test_prepare_without_selection_raises

    def test_retry_contract(self):
        """业务 Retry 时消息保持 PROCESSING 并刷新平台活动时间。"""

        message = self.create_processing_message()
        with mock.patch.object(execute_natural_language_search, "run", side_effect=Retry("temporary retry")):
            with self.assertRaises(Retry):
                self.invoke(execute_natural_language_search, message=message)
        message.refresh_from_db()
        self.assertEqual(message.status, ExecutionStatus.PROCESSING)
        self.assertIsNotNone(message.last_activity_at)

    def test_stale_task_contract(self):
        """终态消息的陈旧投递被平台拦截为 Ignore。"""

        message = self.create_processing_message()
        Message.objects.filter(id=message.id).update(status=ExecutionStatus.SUCCESS)
        message.refresh_from_db()
        with self.assertRaises(Ignore):
            self.invoke(execute_natural_language_search, message=message)
        message.refresh_from_db()
        self.assertEqual(message.status, ExecutionStatus.SUCCESS)

    # ---------- 任务投递基础设施（与 MessageTaskTest.invoke 同一模式） ----------

    def create_processing_message(self, *, task_id: str = "task-contract") -> Message:
        return Message.objects.create(
            conversation=self.conversation,
            message_type=MessageType.NATURAL_LANGUAGE_SEARCH,
            status=ExecutionStatus.PROCESSING,
            task_id=task_id,
            input_data={"text": "hello"},
            context_data={"prefix": "async"},
            output_data=None,
            created_by=self.user,
            updated_by=self.user,
        )

    @staticmethod
    def invoke(task, *, message: Message):
        task_kwargs = {"message_id": message.id, "task_id": message.task_id}
        task.push_request(
            id=message.task_id,
            retries=0,
            called_directly=False,
            is_eager=True,
            args=(),
            kwargs=task_kwargs,
        )
        try:
            return task(**task_kwargs)
        finally:
            task.pop_request()
