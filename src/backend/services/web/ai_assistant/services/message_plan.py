"""把 USER_INTENT 的类型化计划解析为可独立执行的业务消息。

Agent 调用和确定性校验均在事务外完成；最终只锁定一次会话和入口消息，
在同一事务中创建全部派生消息并收敛入口消息。父消息只保留来源追踪关系，
派生消息执行只依赖自己的 input/context 快照。
"""

from dataclasses import dataclass
from datetime import datetime

from django.db import transaction
from django.utils import timezone

from services.web.ai_assistant.constants import (
    ExecutionMode,
    ExecutionStatus,
    MessageType,
    UserIntentErrorCode,
)
from services.web.ai_assistant.exceptions import StaleMessageTask
from services.web.ai_assistant.models import Message
from services.web.ai_assistant.schemas.audit_search import (
    DerivedMessageSummarySchema,
    LogSearchContextSchema,
    LogSearchInputSchema,
    SystemSelectionContextSchema,
    SystemSelectionInputSchema,
    UserIntentAgentTraceSchema,
    UserIntentErrorSchema,
    UserIntentOutputSchema,
)
from services.web.ai_assistant.services.message import MessageService, PreparedMessage
from services.web.ai_assistant.services.message_execution import (
    MessageExecution,
    finish_message_success,
)
from services.web.query.ai_assistant.exceptions import AIOutputInvalidError
from services.web.query.ai_assistant.schemas import (
    MessagePlan,
    SearchCondition,
    SystemSelectionOutput,
)
from services.web.query.ai_assistant.services.nl2json import NL2JSONService


@dataclass(frozen=True, slots=True)
class ValidatedMessagePlan:
    """完成权限、字段和时间校验后的整份 Agent 计划。"""

    plan: MessagePlan
    target_system_id: str
    current_selection: Message | None
    condition: SearchCondition | None
    system_context: SystemSelectionOutput


@dataclass(frozen=True, slots=True)
class ResolvedIntentPlan:
    """可在一个事务中落库的入口输出和完整派生消息快照。"""

    output: UserIntentOutputSchema
    messages: tuple[PreparedMessage, ...]
    agent_trace: UserIntentAgentTraceSchema


class MessagePlanExecutionService:
    """校验 Agent 计划、构造独立消息快照，并原子完成本轮规划。"""

    @classmethod
    def validate(
        cls,
        *,
        plan: MessagePlan,
        system_context: SystemSelectionOutput,
        reference_time: datetime,
        current_selection: Message | None,
    ) -> ValidatedMessagePlan:
        """在创建任何派生消息前完成整份计划的确定性校验。"""

        if plan.outcome == "error":
            if plan.error_code == UserIntentErrorCode.SYSTEM_REQUIRED:
                if current_selection is not None:
                    raise AIOutputInvalidError(extra={"reason": "SYSTEM_REQUIRED conflicts with current selection"})
                if not system_context.systems:
                    raise AIOutputInvalidError(extra={"reason": "system_id not in candidates"})
            return ValidatedMessagePlan(
                plan=plan,
                target_system_id="",
                current_selection=current_selection,
                condition=None,
                system_context=system_context,
            )

        selection_item = next(
            (item for item in plan.messages if item.message_type == MessageType.SYSTEM_SELECTION),
            None,
        )
        log_item = next((item for item in plan.messages if item.message_type == MessageType.LOG_SEARCH), None)
        target_system_id = (
            selection_item.message_input.system_ids[0]
            if selection_item is not None
            else cls.selection_system_id(current_selection)
        )
        candidate_map = {system.system_id: system for system in system_context.systems}
        if not target_system_id:
            raise AIOutputInvalidError(extra={"reason": "system required"})
        if target_system_id not in candidate_map:
            raise AIOutputInvalidError(extra={"reason": "system_id not in candidates", "system_id": target_system_id})

        condition = None
        if log_item is not None:
            condition = NL2JSONService.validate_and_assemble(
                payload=log_item.message_input.condition,
                selection=SystemSelectionOutput(systems=[candidate_map[target_system_id]]),
                scope_id=target_system_id,
                reference_time=reference_time,
                allow_empty=True,
            )
        return ValidatedMessagePlan(
            plan=plan,
            target_system_id=target_system_id,
            current_selection=current_selection,
            condition=condition,
            system_context=system_context,
        )

    @classmethod
    def resolve(
        cls,
        *,
        execution: MessageExecution,
        validated: ValidatedMessagePlan,
        agent_trace: UserIntentAgentTraceSchema,
    ) -> ResolvedIntentPlan:
        """把已校验计划转换成不再读取其他消息内容的完整派生消息快照。"""

        if validated.plan.outcome == "error":
            return ResolvedIntentPlan(
                output=cls.build_error_output(
                    error_code=validated.plan.error_code,
                    system_context=validated.system_context,
                ),
                messages=(),
                agent_trace=agent_trace,
            )

        selection_item = next(
            (item for item in validated.plan.messages if item.message_type == MessageType.SYSTEM_SELECTION),
            None,
        )
        log_item = next(
            (item for item in validated.plan.messages if item.message_type == MessageType.LOG_SEARCH),
            None,
        )
        target_system = next(
            system for system in validated.system_context.systems if system.system_id == validated.target_system_id
        )
        session_scope_type = execution.context_data.scope_type or "cross_system"
        messages: list[PreparedMessage] = []
        if selection_item is not None:
            selection_input = SystemSelectionInputSchema(
                system_ids=[validated.target_system_id],
                scope_type=session_scope_type,
                scope_id=execution.context_data.scope_id,
            )
            selection_context = SystemSelectionContextSchema(
                username=execution.context_data.username,
                namespace=execution.context_data.namespace,
                scope_type=session_scope_type,
                scope_id=execution.context_data.scope_id,
            )
            messages.append(
                PreparedMessage(
                    message_type=MessageType.SYSTEM_SELECTION,
                    execution_mode=ExecutionMode.ASYNC,
                    parent_message=execution.message,
                    input_data=selection_input.model_dump(mode="json"),
                    context_data=selection_context.model_dump(mode="json"),
                    output_data=None,
                    visible=log_item is None or not execution.input_data.auto_execute,
                    timeline_started_at=execution.message.created_at,
                )
            )

        if log_item is not None and execution.input_data.auto_execute:
            if validated.condition is None:
                raise AIOutputInvalidError(extra={"reason": "log search has no valid condition"})
            log_input = LogSearchInputSchema(condition=validated.condition)
            log_context = LogSearchContextSchema(
                username=execution.context_data.username,
                namespace=execution.context_data.namespace,
                system_id=validated.target_system_id,
                source="natural_language",
                session_scope_type=session_scope_type,
                session_scope_id=execution.context_data.scope_id,
                extension_fields=target_system.extension_fields,
            )
            messages.append(
                PreparedMessage(
                    message_type=MessageType.LOG_SEARCH,
                    execution_mode=ExecutionMode.ASYNC,
                    parent_message=execution.message,
                    input_data=log_input.model_dump(mode="json"),
                    context_data=log_context.model_dump(mode="json"),
                    output_data=None,
                    timeline_started_at=execution.message.created_at,
                )
            )

        output = UserIntentOutputSchema(
            intent="select_system" if selection_item is not None else "log_search",
            system_id=validated.target_system_id,
            condition=validated.condition if log_item is not None and not execution.input_data.auto_execute else None,
            selection_message_uid=(
                str(validated.current_selection.uid)
                if selection_item is None and validated.current_selection is not None
                else ""
            ),
        )
        return ResolvedIntentPlan(output=output, messages=tuple(messages), agent_trace=agent_trace)

    @classmethod
    def resolve_valid_selection_fallback(
        cls,
        *,
        execution: MessageExecution,
        plan: MessagePlan | None,
        system_context: SystemSelectionOutput,
        reference_time: datetime,
        current_selection: Message | None,
        error_output: UserIntentOutputSchema,
        agent_trace: UserIntentAgentTraceSchema,
    ) -> ResolvedIntentPlan | None:
        """复合计划的检索条件无效时，保留可独立成立的系统选择消息。

        仅接受恰好由系统选择和日志检索组成的计划。系统选择仍走完整权限校验；
        校验失败时返回 ``None``，调用方继续使用原来的整体错误结果。
        """

        if plan is None or plan.outcome != "dispatch" or len(plan.messages) != 2:
            return None
        selection = next(
            (item for item in plan.messages if item.message_type == MessageType.SYSTEM_SELECTION),
            None,
        )
        log_search = next(
            (item for item in plan.messages if item.message_type == MessageType.LOG_SEARCH),
            None,
        )
        if selection is None or log_search is None:
            return None
        selection_plan = MessagePlan(outcome="dispatch", messages=[selection])
        try:
            validated = cls.validate(
                plan=selection_plan,
                system_context=system_context,
                reference_time=reference_time,
                current_selection=current_selection,
            )
        except AIOutputInvalidError:
            return None
        resolved = cls.resolve(
            execution=execution,
            validated=validated,
            agent_trace=agent_trace,
        )
        return ResolvedIntentPlan(
            output=resolved.output.model_copy(update={"error": error_output.error}),
            messages=resolved.messages,
            agent_trace=agent_trace,
        )

    @classmethod
    def finish(
        cls,
        *,
        execution: MessageExecution,
        task_id: str,
        resolved: ResolvedIntentPlan,
    ) -> dict:
        """一次事务创建全部派生消息并把 USER_INTENT 收敛为 SUCCESS。"""

        service = MessageService(user=execution.message.created_by)
        conversation = execution.message.conversation
        with transaction.atomic():
            service.lock_active_conversation(conversation=conversation)
            locked = (
                Message.objects.select_for_update()
                .filter(
                    id=execution.message.id,
                    conversation=conversation,
                    created_by=execution.message.created_by,
                    message_type=MessageType.USER_INTENT,
                    status=ExecutionStatus.PROCESSING,
                    task_id=task_id,
                )
                .first()
            )
            if locked is None:
                raise StaleMessageTask()

            context_data = execution.context_data.model_copy(update={"agent_trace": resolved.agent_trace}).model_dump(
                mode="json"
            )
            Message.objects.filter(id=locked.id).update(context_data=context_data)
            execution.message.context_data = context_data

            created = service.create_prepared_batch_locked(
                conversation=conversation,
                messages=resolved.messages,
            )
            selection_message = next(
                (message for message in created if message.message_type == MessageType.SYSTEM_SELECTION),
                None,
            )
            log_message = next(
                (message for message in created if message.message_type == MessageType.LOG_SEARCH),
                None,
            )
            output = resolved.output.model_copy(
                update={
                    "selection_message_uid": (
                        str(selection_message.uid)
                        if selection_message is not None
                        else resolved.output.selection_message_uid
                    ),
                    "log_search_message_uid": str(log_message.uid) if log_message is not None else "",
                    "derived_messages": [
                        DerivedMessageSummarySchema(
                            message_uid=str(message.uid),
                            message_type=message.message_type,
                            status=message.status,
                            visible=message.visible,
                        )
                        for message in created
                    ],
                }
            )
            return finish_message_success(execution=execution, task_id=task_id, output_data=output)

    @staticmethod
    def persist_agent_trace(
        *,
        execution: MessageExecution,
        agent_trace: UserIntentAgentTraceSchema,
    ) -> None:
        """在 Agent 调用前或基础设施失败时保存可复现请求，并保留任务栅栏。"""

        context_data = execution.context_data.model_copy(update={"agent_trace": agent_trace}).model_dump(mode="json")
        now = timezone.now()
        updated = Message.objects.filter(
            id=execution.message.id,
            status=ExecutionStatus.PROCESSING,
            task_id=execution.message.task_id,
        ).update(
            context_data=context_data,
            last_activity_at=now,
            updated_by=execution.message.created_by,
            updated_at=now,
        )
        if updated != 1:
            raise StaleMessageTask()
        execution.message.context_data = context_data

    @staticmethod
    def load_current_selection(
        *,
        execution: MessageExecution,
        system_context: SystemSelectionOutput,
    ) -> Message | None:
        """读取当前范围内最新成功系统选择；范围外历史选择视为无选择。"""

        selection = (
            Message.objects.filter(
                conversation=execution.message.conversation,
                created_by=execution.message.created_by,
                message_type=MessageType.SYSTEM_SELECTION,
                status=ExecutionStatus.SUCCESS,
            )
            .order_by("-id")
            .first()
        )
        if selection is None:
            return None
        if MessagePlanExecutionService.selection_system_id(selection) not in {
            system.system_id for system in system_context.systems
        }:
            return None
        return selection

    @staticmethod
    def selection_system_id(selection: Message | None) -> str:
        """从系统选择输出快照提取唯一系统 ID。"""

        if selection is None:
            return ""
        systems = (selection.output_data or {}).get("systems") or []
        return str((systems[0] or {}).get("system_id") or "") if systems else ""

    @staticmethod
    def build_error_output(*, error_code: str, system_context: SystemSelectionOutput | None) -> UserIntentOutputSchema:
        """将稳定计划错误码转换为前端可直接展示的业务错误。"""

        candidates = []
        if system_context is not None:
            candidates = [{"system_id": system.system_id, "name": system.name} for system in system_context.systems]
        messages = {
            UserIntentErrorCode.UNRECOGNIZED_INTENT: "未能理解您的需求，请描述要查询的系统或日志内容",
            UserIntentErrorCode.SYSTEM_REQUIRED: "请先告诉我要查哪个系统的日志",
            UserIntentErrorCode.SYSTEM_UNAVAILABLE: "目标系统不在当前可用系统范围内，请重新选择系统",
        }
        return UserIntentOutputSchema(
            intent="unrecognized" if error_code == UserIntentErrorCode.UNRECOGNIZED_INTENT else "log_search",
            error=UserIntentErrorSchema(
                error_code=str(error_code),
                error_message=messages.get(error_code, "未能生成可执行的消息，请换一种描述"),
                candidates=candidates,
            ),
        )
