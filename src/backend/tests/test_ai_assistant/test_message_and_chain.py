# -*- coding: utf-8 -*-
"""消息服务集成与 NL 续链测试（子消息创建与执行生命周期解耦）。"""

from unittest import mock

from services.web.ai_assistant.constants import ExecutionStatus, MessageType
from services.web.ai_assistant.models import Message
from services.web.ai_assistant.services.message import MessageService
from services.web.ai_assistant.services.message_execution import load_message_execution
from services.web.ai_assistant.tasks.audit_search import execute_log_search
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
        """一期全异步化：创建即落库 PROCESSING 并派发任务（终态由任务收敛，前端轮询）。"""

        with self.patch_field_context(), self.patch_operation_context(), mock.patch(
            "services.web.ai_assistant.handlers.audit_search.SearchLogPermission.get_scope_auth_systems",
            return_value=[TARGET_SYSTEM_ID],
        ):
            message = MessageService(user=self.user).create(
                conversation=self.conversation,
                message_type=MessageType.SYSTEM_SELECTION,
                input_data={
                    "system_ids": [TARGET_SYSTEM_ID],
                    "scope_type": self.default_scope_type,
                    "scope_id": self.default_scope_id,
                },
            )
        self.assertEqual(message.status, ExecutionStatus.PROCESSING)
        self.assertIsNone(message.parent_message)
        self.assertTrue(message.task_id)
        # session scope 固化到消息快照（后续链路继承）
        self.assertEqual((message.context_data or {}).get("scope_type"), self.default_scope_type)

    def test_create_log_search_failure_no_message(self):
        """异步化后创建即落库 PROCESSING；检索失败由任务收敛 FAILED（不再同步冒泡不落库）。"""

        self.create_selection_message()
        before = Message.objects.count()
        with mock.patch(
            "services.web.ai_assistant.handlers.audit_search.LogSearchService.search",
            side_effect=AIOutputInvalidError(),
        ):
            message = MessageService(user=self.user).create(
                conversation=self.conversation,
                message_type=MessageType.LOG_SEARCH,
                input_data={"condition": make_condition().model_dump(mode="json")},
            )
        self.assertEqual(message.status, ExecutionStatus.PROCESSING)
        self.assertEqual(Message.objects.count(), before + 1)

    def test_create_log_search_binds_latest_selection(self):
        """未传 parent 时创建的检索消息自动绑定最新成功选择（异步化不影响绑定）。"""

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
        self.assertEqual(message.status, ExecutionStatus.PROCESSING)
        self.assertEqual(message.parent_message.id, latest.id)

    def test_edit_log_search_reexecutes_and_replaces_same_message(self):
        """编辑日志检索消息：重建上下文并重置 PROCESSING，任务执行后输出替换原消息。"""

        parent = self.create_selection_message()
        message = self.create_log_search_message(parent=parent)
        Message.objects.filter(pk=message.pk).update(context_data={"obsolete": True})
        condition = make_condition()
        condition.conditions[0].filters = ["bob"]
        with mock.patch.object(execute_log_search, "apply_async"):
            with self.captureOnCommitCallbacks(execute=True):
                updated = MessageService(user=self.user).update(
                    message_uid=str(message.uid),
                    input_data={"condition": condition.model_dump(mode="json")},
                )
        self.assertEqual(updated.uid, message.uid)
        self.assertEqual(updated.status, ExecutionStatus.PROCESSING)
        self.assertEqual(updated.input_data["condition"]["conditions"][0]["filters"], ["bob"])
        self.assertEqual(updated.context_data["system_id"], TARGET_SYSTEM_ID)
        self.assertEqual(updated.context_data["source"], "field_condition")
        self.assertNotIn("obsolete", updated.context_data)
        # 任务执行收敛：输出替换原消息（编辑不新建消息）
        execution = load_message_execution(
            message_id=updated.id,
            task_id=updated.task_id,
            celery_task_id=updated.task_id,
        )
        with mock.patch(
            "services.web.ai_assistant.handlers.audit_search.LogSearchService.search",
            return_value=make_log_search_output(total=7),
        ):
            output = execute_log_search.run(execution)
            execute_log_search._finish_success(
                execution=execution,
                task_id=updated.task_id,
                output_data=output,
            )
        updated.refresh_from_db()
        self.assertEqual(updated.output_data["total"], 7)
        self.assertEqual(Message.objects.count(), 2)
