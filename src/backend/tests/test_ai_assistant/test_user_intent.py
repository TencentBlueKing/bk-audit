# -*- coding: utf-8 -*-
"""USER_INTENT 单次 Agent 多消息规划与执行测试。"""

from contextlib import ExitStack
from datetime import timedelta
from unittest import mock

from django.utils import timezone

from services.web.ai_assistant.constants import ExecutionStatus, MessageType
from services.web.ai_assistant.exceptions import (
    InvalidParentMessage,
    ScopeContextRequired,
    StaleMessageTask,
)
from services.web.ai_assistant.handlers import message_handler_registry
from services.web.ai_assistant.models import Message
from services.web.ai_assistant.schemas import parse_snapshot
from services.web.ai_assistant.schemas.audit_search import UserIntentOutputSchema
from services.web.ai_assistant.services.message import MessageService
from services.web.ai_assistant.services.message_execution import MessageExecution
from services.web.ai_assistant.tasks.audit_search import execute_user_intent
from services.web.query.ai_assistant.exceptions import (
    AIOutputInvalidError,
    AITimeoutError,
)
from services.web.query.ai_assistant.schemas import (
    AIConditionItem,
    AIConditionPayload,
    MessagePlan,
    PlannedLogSearchInput,
    PlannedLogSearchMessage,
    PlannedSystemSelectionMessage,
    SelectionFieldMeta,
    SelectionSystem,
    SystemSelectionInput,
    SystemSelectionOutput,
)
from tests.test_ai_assistant.base import (
    TARGET_SYSTEM_ID,
    AIAssistantPlatformTestCase,
    make_log_search_output,
    make_selection_output,
)

HANDLERS_MODULE = "services.web.ai_assistant.handlers.audit_search"
TASK_MODULE = "services.web.ai_assistant.tasks.audit_search"
TITLE_DELAY = "services.web.ai_assistant.tasks.conversation.generate_conversation_title.delay"


def create_intent_message(testcase, query_text="看审计中心最近一天 admin 的操作记录", *, auto_execute=True, scope_extra=None):
    """构造 PROCESSING 的 USER_INTENT 消息和类型化执行快照。"""

    scope = scope_extra or {"scope_type": "cross_system"}
    input_data = {"query_text": query_text, "auto_execute": auto_execute, **scope}
    context_data = {"username": testcase.user, "namespace": "bkaudit", **scope}
    message = Message.objects.create(
        conversation=testcase.conversation,
        message_type=MessageType.USER_INTENT,
        status=ExecutionStatus.PROCESSING,
        task_id="task-1",
        input_data=input_data,
        context_data=context_data,
        created_by=testcase.user,
        updated_by=testcase.user,
    )
    return message, build_execution(message)


def build_execution(message):
    """从数据库快照重建 USER_INTENT 执行上下文，用于模拟 Worker 重投。"""

    message.refresh_from_db()
    handler = message_handler_registry.require(MessageType.USER_INTENT)
    return MessageExecution(
        message=message,
        input_data=parse_snapshot(handler.input_model, message.input_data, field_name="input_data"),
        context_data=parse_snapshot(handler.context_model, message.context_data, field_name="context_data"),
    )


def selection_plan(system_id=TARGET_SYSTEM_ID):
    return MessagePlan(
        outcome="dispatch",
        messages=[
            PlannedSystemSelectionMessage(
                message_type="SYSTEM_SELECTION",
                message_input=SystemSelectionInput(system_ids=[system_id]),
            )
        ],
    )


def log_message():
    return PlannedLogSearchMessage(
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
    )


def log_plan():
    return MessagePlan(outcome="dispatch", messages=[log_message()])


def selection_and_log_plan(system_id=TARGET_SYSTEM_ID):
    return MessagePlan(
        outcome="dispatch",
        messages=[selection_plan(system_id).messages[0], log_message()],
    )


class UserIntentExecutionTest(AIAssistantPlatformTestCase):
    """验证三种计划、失败边界、默认时间与 Worker 重投。"""

    def _run(
        self,
        plan,
        *,
        with_selection=False,
        auto_execute=True,
        finish=True,
        log_error=None,
        expected_planner_calls=1,
    ):
        if with_selection:
            current_selection = self.create_selection_message()
        else:
            current_selection = None
        message, execution = create_intent_message(self, auto_execute=auto_execute)
        planner = mock.MagicMock(return_value=plan)
        log_result = mock.MagicMock(return_value=make_log_search_output())
        if log_error is not None:
            log_result.side_effect = log_error
        with mock.patch(
            f"{TASK_MODULE}.IntentRecognitionService.load_candidates",
            return_value=[{"system_id": TARGET_SYSTEM_ID, "name": "测试系统"}],
        ), mock.patch(
            f"{TASK_MODULE}.FieldContextService.build_planning_context",
            return_value=make_selection_output(),
        ), mock.patch(
            f"{TASK_MODULE}.MessagePlanningService.plan",
            planner,
        ), mock.patch(
            "services.web.query.ai_assistant.services.nl2json.NL2JSONService.convert"
        ) as legacy_convert, mock.patch(
            f"{HANDLERS_MODULE}.FieldContextService.build_selection",
            return_value=make_selection_output(),
        ), mock.patch(
            f"{HANDLERS_MODULE}.OperationContextService.build",
            return_value=([], []),
        ), mock.patch(
            f"{HANDLERS_MODULE}.SearchLogPermission.get_scope_auth_systems",
            return_value=[TARGET_SYSTEM_ID],
        ), mock.patch(
            f"{HANDLERS_MODULE}.LogSearchService.search",
            log_result,
        ), mock.patch(
            TITLE_DELAY
        ) as title_delay:
            resolved = execute_user_intent.run(execution)
            self.assertFalse(Message.objects.filter(parent_message=message).exists())
            if finish:
                output = UserIntentOutputSchema.model_validate(
                    execute_user_intent._finish_success(
                        execution=execution,
                        task_id="task-1",
                        output_data=resolved,
                    )
                )
            else:
                output = resolved.output
        self.assertEqual(planner.call_count, expected_planner_calls)
        legacy_convert.assert_not_called()
        log_result.assert_not_called()
        return message, current_selection, output, title_delay

    def test_pure_system_selection_creates_visible_single_message(self):
        root, _, output, title_delay = self._run(selection_plan())

        derived = list(Message.objects.filter(parent_message=root).order_by("id"))
        self.assertEqual([item.message_type for item in derived], [MessageType.SYSTEM_SELECTION])
        self.assertTrue(derived[0].visible)
        self.assertEqual(derived[0].status, ExecutionStatus.PROCESSING)
        self.assertEqual(output.selection_message_uid, str(derived[0].uid))
        self.assertEqual(output.log_search_message_uid, "")
        self.assertEqual(len(output.derived_messages), 1)
        title_delay.assert_called_once()

    def test_planned_system_selection_can_be_edited_after_intent_finishes(self):
        """计划根成功后，用户仍可编辑可见的系统选择子消息。"""

        root, _, _, _ = self._run(selection_plan())
        root.refresh_from_db()
        self.assertEqual(root.status, ExecutionStatus.SUCCESS)
        selection = Message.objects.get(parent_message=root, message_type=MessageType.SYSTEM_SELECTION)
        Message.objects.filter(id=selection.id).update(
            status=ExecutionStatus.SUCCESS,
            output_data=make_selection_output().model_dump(mode="json"),
        )
        with mock.patch.object(
            message_handler_registry.require(MessageType.SYSTEM_SELECTION).async_task, "apply_async"
        ):
            with self.captureOnCommitCallbacks(execute=True):
                updated = MessageService(user=self.user).update(
                    message_uid=str(selection.uid),
                    input_data={
                        "system_ids": [TARGET_SYSTEM_ID],
                        "scope_type": self.default_scope_type,
                        "scope_id": self.default_scope_id,
                    },
                )

        self.assertEqual(updated.parent_message_id, root.id)
        self.assertEqual(updated.status, ExecutionStatus.PROCESSING)

    def test_current_system_log_search_is_intent_child_and_executes_async(self):
        root, current_selection, output, _ = self._run(log_plan(), with_selection=True)

        log_search = Message.objects.get(parent_message=root, message_type=MessageType.LOG_SEARCH)
        self.assertEqual(log_search.message_type, MessageType.LOG_SEARCH)
        self.assertNotEqual(log_search.parent_message_id, current_selection.id)
        self.assertEqual(log_search.status, ExecutionStatus.PROCESSING)
        self.assertEqual(log_search.context_data["source"], "natural_language")
        self.assertTrue(log_search.visible)
        self.assertEqual(output.log_search_message_uid, str(log_search.uid))
        self.assertFalse(Message.objects.filter(message_type=MessageType.NATURAL_LANGUAGE_SEARCH).exists())

    def test_switch_and_search_hides_selection_and_orders_summaries(self):
        root, _, output, _ = self._run(selection_and_log_plan())

        selection, log_search = list(Message.objects.filter(parent_message=root).order_by("id"))
        self.assertEqual(selection.message_type, MessageType.SYSTEM_SELECTION)
        self.assertFalse(selection.visible)
        self.assertEqual(selection.status, ExecutionStatus.PROCESSING)
        self.assertEqual(log_search.message_type, MessageType.LOG_SEARCH)
        self.assertTrue(log_search.visible)
        self.assertEqual(log_search.status, ExecutionStatus.PROCESSING)
        self.assertEqual(log_search.parent_message_id, root.id)
        self.assertEqual([item.message_type for item in output.derived_messages], ["SYSTEM_SELECTION", "LOG_SEARCH"])
        root.refresh_from_db()
        self.assertNotIn("plan_snapshot", root.context_data)
        self.assertNotIn("context_hash", root.context_data)
        self.assertNotIn("planning_attempt", root.context_data)
        self.assertEqual(root.context_data["agent_trace"]["status"], "success")
        self.assertEqual(root.context_data["agent_trace"]["attempt_count"], 1)
        self.assertEqual(
            root.context_data["agent_trace"]["plan"],
            selection_and_log_plan().model_dump(mode="json"),
        )
        self.assertTrue(root.context_data["agent_trace"]["system_prompt"])
        self.assertTrue(root.context_data["agent_trace"]["user_prompt"])
        self.assertEqual(root.context_data["agent_trace"]["agent_code"], "bp-ai-user-intent")
        self.assertEqual(
            log_search.context_data["extension_fields"][0]["keys"],
            ["ticket_id"],
        )

    def test_default_time_is_last_day_from_agent_reference_time(self):
        root, _, _, _ = self._run(selection_and_log_plan())
        log_search = Message.objects.get(parent_message=root, message_type=MessageType.LOG_SEARCH)
        start = datetime_from_iso(log_search.input_data["condition"]["start_time"])
        end = datetime_from_iso(log_search.input_data["condition"]["end_time"])
        self.assertEqual(end - start, timedelta(days=1))
        root.refresh_from_db()
        self.assertEqual(end, datetime_from_iso(root.context_data["agent_trace"]["reference_time"]))

    def test_auto_execute_false_keeps_condition_without_log_message(self):
        root, current_selection, output, _ = self._run(log_plan(), with_selection=True, auto_execute=False)

        self.assertIsNotNone(output.condition)
        self.assertEqual(output.condition.scope_id, TARGET_SYSTEM_ID)
        self.assertEqual(output.selection_message_uid, str(current_selection.uid))
        self.assertFalse(Message.objects.filter(parent_message=root).exists())

    def test_auto_execute_false_keeps_planned_selection_visible(self):
        root, _, output, _ = self._run(selection_and_log_plan(), auto_execute=False)

        selection = Message.objects.get(parent_message=root, message_type=MessageType.SYSTEM_SELECTION)
        self.assertTrue(selection.visible)
        self.assertEqual(output.condition.scope_id, TARGET_SYSTEM_ID)
        self.assertEqual([item.message_type for item in output.derived_messages], [MessageType.SYSTEM_SELECTION])
        self.assertFalse(Message.objects.filter(parent_message=root, message_type=MessageType.LOG_SEARCH).exists())

    def test_log_search_business_execution_is_not_part_of_intent_task(self):
        root, _, output, _ = self._run(
            selection_and_log_plan(),
            log_error=AIOutputInvalidError(extra={"reason": "private doris detail"}),
        )

        selection = Message.objects.get(parent_message=root, message_type=MessageType.SYSTEM_SELECTION)
        log_search = Message.objects.get(parent_message=root, message_type=MessageType.LOG_SEARCH)
        self.assertFalse(selection.visible)
        self.assertEqual(log_search.status, ExecutionStatus.PROCESSING)
        self.assertTrue(log_search.visible)
        self.assertEqual(log_search.parent_message_id, root.id)
        self.assertEqual(output.derived_messages[1].status, ExecutionStatus.PROCESSING)

    def test_unexpected_log_search_failure_does_not_delay_intent_planning(self):
        root, _, output, _ = self._run(selection_and_log_plan(), log_error=RuntimeError("program defect"))

        log_search = Message.objects.get(parent_message=root, message_type=MessageType.LOG_SEARCH)
        self.assertEqual(log_search.status, ExecutionStatus.PROCESSING)
        self.assertEqual(output.derived_messages[1].status, ExecutionStatus.PROCESSING)

    def test_stale_root_cannot_finish_or_create_derived_messages(self):
        root, execution = create_intent_message(self)

        def expire_root(**kwargs):
            Message.objects.filter(id=root.id).update(status=ExecutionStatus.FAILED)
            return selection_and_log_plan()

        with self._execution_dependencies(selection_and_log_plan()), mock.patch(
            f"{TASK_MODULE}.MessagePlanningService.plan",
            side_effect=expire_root,
        ):
            resolved = execute_user_intent.run(execution)
            with self.assertRaises(StaleMessageTask):
                execute_user_intent._finish_success(execution=execution, task_id="task-1", output_data=resolved)

        root.refresh_from_db()
        self.assertNotIn("plan_snapshot", root.context_data)
        self.assertFalse(Message.objects.filter(parent_message=root).exists())

    def test_error_plan_creates_no_derived_messages(self):
        plan = MessagePlan(outcome="error", messages=[], error_code="SYSTEM_REQUIRED")
        root, _, output, _ = self._run(plan)

        self.assertEqual(output.error.error_code, "SYSTEM_REQUIRED")
        self.assertTrue(output.error.candidates)
        self.assertFalse(Message.objects.filter(parent_message=root).exists())

    def test_system_required_conflicts_with_current_selection(self):
        plan = MessagePlan(outcome="error", messages=[], error_code="SYSTEM_REQUIRED")
        with mock.patch(f"{TASK_MODULE}.NL_PARSE_RETRY_INTERVAL_SECONDS", 0):
            root, _, output, _ = self._run(plan, with_selection=True, expected_planner_calls=3)

        self.assertEqual(output.error.error_code, "AI_OUTPUT_INVALID")
        self.assertFalse(Message.objects.filter(parent_message=root).exists())

    def test_system_required_without_candidates_maps_to_system_unavailable(self):
        plan = MessagePlan(outcome="error", messages=[], error_code="SYSTEM_REQUIRED")
        root, execution = create_intent_message(self)
        with mock.patch(f"{TASK_MODULE}.IntentRecognitionService.load_candidates", return_value=[],), mock.patch(
            f"{TASK_MODULE}.FieldContextService.build_planning_context",
            return_value=SystemSelectionOutput(systems=[]),
        ), mock.patch(f"{TASK_MODULE}.MessagePlanningService.plan", return_value=plan,) as planner, mock.patch(
            f"{TASK_MODULE}.NL_PARSE_RETRY_INTERVAL_SECONDS", 0
        ):
            output = execute_user_intent.run(execution).output

        self.assertEqual(planner.call_count, 3)
        self.assertEqual(output.error.error_code, "SYSTEM_UNAVAILABLE")
        self.assertEqual(output.error.candidates, [])
        self.assertFalse(Message.objects.filter(parent_message=root).exists())

    def test_transient_agent_failure_propagates(self):
        message, execution = create_intent_message(self)
        with mock.patch(
            f"{TASK_MODULE}.IntentRecognitionService.load_candidates",
            return_value=[{"system_id": TARGET_SYSTEM_ID, "name": "测试系统"}],
        ), mock.patch(
            f"{TASK_MODULE}.FieldContextService.build_planning_context",
            return_value=make_selection_output(),
        ), mock.patch(
            f"{TASK_MODULE}.MessagePlanningService.plan",
            side_effect=AITimeoutError(),
        ):
            with self.assertRaises(AITimeoutError):
                execute_user_intent.run(execution)
        self.assertFalse(Message.objects.filter(parent_message=message).exists())
        message.refresh_from_db()
        self.assertEqual(message.context_data["agent_trace"]["status"], "failed")
        self.assertEqual(message.context_data["agent_trace"]["attempt_count"], 1)

    def test_invalid_system_retries_then_returns_unavailable(self):
        invalid = selection_plan("outside-system")
        with mock.patch(f"{TASK_MODULE}.NL_PARSE_RETRY_INTERVAL_SECONDS", 0):
            root, _, output, _ = self._run(invalid, expected_planner_calls=3)

        self.assertEqual(output.error.error_code, "SYSTEM_UNAVAILABLE")
        self.assertFalse(Message.objects.filter(parent_message=root).exists())
        root.refresh_from_db()
        self.assertEqual(root.context_data["agent_trace"]["status"], "failed")
        self.assertEqual(root.context_data["agent_trace"]["attempt_count"], 3)
        self.assertEqual(root.context_data["agent_trace"]["reason"], "system_id not in candidates")

    def test_invalid_log_condition_keeps_valid_planned_selection(self):
        """复合计划的检索条件无效时，重试耗尽后仍创建已确定合法的系统选择。"""

        invalid_log = PlannedLogSearchMessage(
            message_type="LOG_SEARCH",
            message_input=PlannedLogSearchInput(
                condition=AIConditionPayload(
                    conditions=[
                        AIConditionItem(
                            raw_name="unknown_field",
                            field_type="string",
                            operator="eq",
                            filters=["admin"],
                        )
                    ]
                )
            ),
        )
        plan = MessagePlan(
            outcome="dispatch",
            messages=[selection_plan().messages[0], invalid_log],
        )
        with mock.patch(f"{TASK_MODULE}.NL_PARSE_RETRY_INTERVAL_SECONDS", 0):
            root, _, output, _ = self._run(plan, expected_planner_calls=3)

        self.assertEqual(output.error.error_code, "AI_OUTPUT_INVALID")
        derived = list(Message.objects.filter(parent_message=root).order_by("id"))
        self.assertEqual(len(derived), 1)
        self.assertEqual(derived[0].message_type, MessageType.SYSTEM_SELECTION)
        self.assertTrue(derived[0].visible)
        self.assertEqual(output.selection_message_uid, str(derived[0].uid))
        self.assertEqual(output.derived_messages[0].message_type, MessageType.SYSTEM_SELECTION)

    def test_finish_is_atomic_when_second_message_creation_fails(self):
        """派生消息批量落库中途失败时，已创建消息和入口终态必须一起回滚。"""

        root, execution = create_intent_message(self)
        with self._execution_dependencies(selection_and_log_plan()):
            resolved = execute_user_intent.run(execution)

        original = MessageService._create_prepared_locked
        calls = 0

        def create_then_fail(service, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("second message failed")
            return original(service, **kwargs)

        with mock.patch.object(
            MessageService,
            "_create_prepared_locked",
            autospec=True,
            side_effect=create_then_fail,
        ), self.assertRaises(RuntimeError):
            execute_user_intent._finish_success(
                execution=execution,
                task_id="task-1",
                output_data=resolved,
            )

        root.refresh_from_db()
        self.assertEqual(root.status, ExecutionStatus.PROCESSING)
        self.assertFalse(Message.objects.filter(parent_message=root).exists())

    def test_finished_intent_rejects_duplicate_finish(self):
        """入口和派生消息已原子提交后，重复投递由 task_id/status 栅栏拒绝。"""

        root, execution = create_intent_message(self)
        with self._execution_dependencies(selection_and_log_plan()):
            resolved = execute_user_intent.run(execution)
            execute_user_intent._finish_success(
                execution=execution,
                task_id="task-1",
                output_data=resolved,
            )

        with self.assertRaises(StaleMessageTask):
            execute_user_intent._finish_success(
                execution=execution,
                task_id="task-1",
                output_data=resolved,
            )
        self.assertEqual(Message.objects.filter(parent_message=root).count(), 2)

    def test_resolved_log_search_keeps_original_system_if_selection_changes_before_finish(self):
        """消息完整快照在规划阶段确定，收尾前的新系统选择不会改绑检索目标。"""

        self.create_selection_message()
        second_system = SelectionSystem(
            system_id="bcs",
            name="蓝盾",
            standard_fields=[SelectionFieldMeta(raw_name="username", field_type="string", allow_operators=["eq"])],
        )
        planning_context = make_selection_output()
        planning_context.systems.append(second_system)
        root, execution = create_intent_message(self)
        candidates = [
            {"system_id": TARGET_SYSTEM_ID, "name": "测试系统"},
            {"system_id": "bcs", "name": "蓝盾"},
        ]
        with mock.patch(
            f"{TASK_MODULE}.IntentRecognitionService.load_candidates",
            return_value=candidates,
        ), mock.patch(
            f"{TASK_MODULE}.FieldContextService.build_planning_context",
            return_value=planning_context,
        ), mock.patch(
            f"{TASK_MODULE}.MessagePlanningService.plan",
            return_value=log_plan(),
        ):
            resolved = execute_user_intent.run(execution)

        self.create_selection_message(output=SystemSelectionOutput(systems=[second_system]))
        execute_user_intent._finish_success(
            execution=execution,
            task_id="task-1",
            output_data=resolved,
        )

        log_search = Message.objects.get(parent_message=root, message_type=MessageType.LOG_SEARCH)
        self.assertEqual(log_search.input_data["condition"]["scope_id"], TARGET_SYSTEM_ID)
        self.assertEqual(log_search.context_data["system_id"], TARGET_SYSTEM_ID)

    def _execution_dependencies(self, plan):
        """返回执行 USER_INTENT 规划与标题派发所需的稳定依赖补丁栈。"""

        stack = ExitStack()
        stack.enter_context(
            mock.patch(
                f"{TASK_MODULE}.IntentRecognitionService.load_candidates",
                return_value=[{"system_id": TARGET_SYSTEM_ID, "name": "测试系统"}],
            )
        )
        stack.enter_context(
            mock.patch(
                f"{TASK_MODULE}.FieldContextService.build_planning_context",
                return_value=make_selection_output(),
            )
        )
        stack.enter_context(mock.patch(f"{TASK_MODULE}.MessagePlanningService.plan", return_value=plan))
        stack.enter_context(mock.patch(TITLE_DELAY))
        return stack


class UserIntentHandlerTest(AIAssistantPlatformTestCase):
    """USER_INTENT 入口消息的父消息与 scope 协议。"""

    def test_prepare_rejects_parent(self):
        selection = self.create_selection_message()
        handler = message_handler_registry.require(MessageType.USER_INTENT)
        with self.assertRaises(InvalidParentMessage):
            handler.prepare(
                user=self.user,
                conversation=self.conversation,
                parent_message=selection,
                input_data=handler.input_model(query_text="查日志", scope_type="cross_system"),
            )

    def test_prepare_requires_scope_and_persists_valid_scope(self):
        handler = message_handler_registry.require(MessageType.USER_INTENT)
        with self.assertRaises(ScopeContextRequired):
            handler.prepare(
                user=self.user,
                conversation=self.conversation,
                parent_message=None,
                input_data=handler.input_model(query_text="查日志"),
            )
        preparation = handler.prepare(
            user=self.user,
            conversation=self.conversation,
            parent_message=None,
            input_data=handler.input_model(query_text="查日志", scope_type="scene", scope_id="1"),
        )
        self.assertEqual(preparation.context_data.scope_type, "scene")
        self.assertEqual(preparation.context_data.scope_id, "1")


def datetime_from_iso(value):
    """解析测试中的带时区 ISO 时间。"""

    return timezone.datetime.fromisoformat(value)
