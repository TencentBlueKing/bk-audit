# -*- coding: utf-8 -*-
"""AI 助手平台测试基类与工厂。

平台测试需要真实数据库（消息/会话落库），query 业务组件全部 mock：
FieldContextService / NL2JSONService / LogSearchService / 导出服务。
"""

from unittest import mock

from services.web.ai_assistant.constants import ExecutionStatus, MessageType
from services.web.ai_assistant.handlers import message_handler_registry
from services.web.ai_assistant.handlers.audit_search import (
    LogSearchHandler,
    NaturalLanguageSearchHandler,
    SystemSelectionHandler,
)
from services.web.ai_assistant.models import Conversation, Message
from services.web.query.ai_assistant.schemas import (
    LogSearchOutput,
    QuerySummary,
    SearchCondition,
    SelectionFieldMeta,
    SelectionSystem,
    SystemSelectionOutput,
)
from tests.base import TestCase

BUSINESS_MESSAGE_HANDLERS = (SystemSelectionHandler, NaturalLanguageSearchHandler, LogSearchHandler)


def ensure_business_handlers_registered():
    """确保业务消息 Handler 已注册（前置机制测试可能用 Echo 覆盖后未还原）。"""

    registered_types = set(message_handler_registry.handlers)
    for handler_class in BUSINESS_MESSAGE_HANDLERS:
        if str(handler_class.message_type) not in registered_types:
            message_handler_registry.register(handler_class())

TARGET_SYSTEM_ID = "bk_log"


def make_selection_output(system_id: str = TARGET_SYSTEM_ID) -> SystemSelectionOutput:
    """构造单系统字段上下文（标准字段 + 拓展字段各一）。"""

    return SystemSelectionOutput(
        systems=[
            SelectionSystem(
                system_id=system_id,
                name="测试系统",
                standard_fields=[
                    SelectionFieldMeta(
                        raw_name="username",
                        keys=[],
                        display_name="操作人",
                        nl_name="操作人",
                        description="操作人账号",
                        allow_operators=["eq", "neq", "include", "exclude", "match_any", "match_all"],
                        sample_value="admin",
                    ),
                ],
                extension_fields=[
                    SelectionFieldMeta(
                        raw_name="extend_data",
                        keys=["ticket_id"],
                        display_name="工单ID",
                        nl_name="extend.工单ID",
                        description="工单编号",
                        allow_operators=["eq", "neq", "include", "exclude", "like"],
                        sample_value="TICKET-1",
                        system_id=system_id,
                    ),
                ],
            )
        ]
    )


def make_condition(system_id: str = TARGET_SYSTEM_ID) -> SearchCondition:
    """构造合法检索条件（与字段上下文一致）。"""

    return SearchCondition(
        scope_type="system",
        scope_id=system_id,
        start_time="2026-08-24T00:00:00+08:00",
        end_time="2026-08-24T23:59:59+08:00",
        conditions=[
            {
                "field": {"raw_name": "username", "keys": [], "field_type": "string"},
                "operator": "eq",
                "filters": ["admin"],
            }
        ],
    )


def make_log_search_output(total: int = 2) -> LogSearchOutput:
    """构造检索快照输出。"""

    columns = [
        {"raw_name": "start_time", "keys": [], "display_name": "操作起始时间", "description": ""},
        {"raw_name": "username", "keys": [], "display_name": "操作人", "description": ""},
    ]
    samples = [{"start_time": "2026-08-24 10:00:00", "username": "admin"} for _ in range(total)]
    return LogSearchOutput(
        total=total,
        columns=columns,
        samples=samples,
        query_summary=QuerySummary(
            scope_type="system",
            scope_id=TARGET_SYSTEM_ID,
            time_range={"start_time": "2026-08-24T00:00:00+08:00", "end_time": "2026-08-24T23:59:59+08:00"},
            condition_count=1,
            source="field_condition",
            took_ms=12,
            executed_at="2026-08-24T12:00:00+08:00",
        ),
    )


class AIAssistantPlatformTestCase(TestCase):
    """平台消息链路测试基类。"""

    namespace = "bkaudit"

    def setUp(self):
        ensure_business_handlers_registered()
        self.user = "tester"
        self.conversation = Conversation.objects.create(
            title="新对话",
            created_by=self.user,
            updated_by=self.user,
        )

    # ---------- 消息工厂 ----------

    def create_selection_message(self, output: SystemSelectionOutput | None = None) -> Message:
        """创建成功的系统选择消息（根消息）。"""

        selection = output or make_selection_output()
        return Message.objects.create(
            conversation=self.conversation,
            parent_message=None,
            message_type=MessageType.SYSTEM_SELECTION,
            status=ExecutionStatus.SUCCESS,
            input_data={"system_ids": [TARGET_SYSTEM_ID]},
            context_data={"username": self.user, "namespace": "bkaudit"},
            output_data=selection.model_dump(mode="json"),
            created_by=self.user,
            updated_by=self.user,
        )

    def create_nl_message(
        self,
        *,
        query_text: str = "查一下 admin 的日志",
        auto_execute: bool = True,
        parent: Message | None = None,
        status: str = ExecutionStatus.SUCCESS,
        selection: SystemSelectionOutput | None = None,
        condition: SearchCondition | None = None,
    ) -> Message:
        """创建自然语言消息（默认成功态，供历史操作与父消息场景使用）。"""

        snapshot_selection = selection or make_selection_output()
        input_data = {"query_text": query_text, "auto_execute": auto_execute}
        context_data = {
            "username": self.user,
            "namespace": "bkaudit",
            "scope_id": TARGET_SYSTEM_ID,
            "system_selection": snapshot_selection.model_dump(mode="json"),
        }
        output_data = None
        if condition is not None:
            output_data = {"condition": condition.model_dump(mode="json")}
        return Message.objects.create(
            conversation=self.conversation,
            parent_message=parent,
            message_type=MessageType.NATURAL_LANGUAGE_SEARCH,
            status=status,
            task_id="" if status == ExecutionStatus.SUCCESS else "task-1",
            input_data=input_data,
            context_data=context_data,
            output_data=output_data,
            created_by=self.user,
            updated_by=self.user,
        )

    def create_log_search_message(
        self,
        *,
        parent: Message | None = None,
        condition: SearchCondition | None = None,
        output: LogSearchOutput | None = None,
        source: str = "field_condition",
    ) -> Message:
        """创建成功的日志检索消息（含输入条件与输出快照）。"""

        snapshot_condition = condition or make_condition()
        snapshot_output = output or make_log_search_output()
        return Message.objects.create(
            conversation=self.conversation,
            parent_message=parent,
            message_type=MessageType.LOG_SEARCH,
            status=ExecutionStatus.SUCCESS,
            input_data={"condition": snapshot_condition.model_dump(mode="json")},
            context_data={
                "username": self.user,
                "namespace": "bkaudit",
                "system_id": snapshot_condition.scope_id,
                "source": source,
            },
            output_data=snapshot_output.model_dump(mode="json"),
            created_by=self.user,
            updated_by=self.user,
        )

    # ---------- 通用断言 ----------

    @staticmethod
    def patch_operation_context(return_common=(), return_historical=()):
        """屏蔽操作上下文的 Redis 与消息表查询。"""

        return mock.patch(
            "services.web.ai_assistant.handlers.audit_search.OperationContextService.build",
            return_value=(list(return_common), list(return_historical)),
        )

    @staticmethod
    def patch_field_context(selection: SystemSelectionOutput | None = None):
        return mock.patch(
            "services.web.ai_assistant.handlers.audit_search.FieldContextService.build_selection",
            return_value=selection or make_selection_output(),
        )
