"""审计日志检索的业务 Celery 任务。

用户意图、系统选择和日志检索都是异步消息；
常见操作缓存刷新为声明式周期任务（对齐上游 periodic_task 惯例，beat 自动调度）。
"""

import logging
import time

from blueapps.contrib.celery_tools.periodic import periodic_task
from blueapps.core.celery import celery_app
from celery.schedules import crontab
from django.utils import timezone

from services.web.ai_assistant.constants import (
    NL_PARSE_MAX_RETRIES,
    NL_PARSE_RETRY_INTERVAL_SECONDS,
    NL_PARSE_RETRY_TIMEOUT_SECONDS,
    MessageType,
    UserIntentErrorCode,
)
from services.web.ai_assistant.schemas.audit_search import (
    LogSearchOutputSchema,
    SystemSelectionOutputSchema,
    UserIntentAgentTraceSchema,
    UserIntentOutputSchema,
)
from services.web.ai_assistant.services.message_execution import MessageExecution
from services.web.ai_assistant.services.message_plan import (
    MessagePlanExecutionService,
    ResolvedIntentPlan,
)
from services.web.ai_assistant.services.operation import OperationContextService
from services.web.ai_assistant.tasks.message import MessageExecutionTask
from services.web.query.ai_assistant.exceptions import (
    AIAssistantError,
    AIOutputInvalidError,
    AIOutputParseFailedError,
    AIPermissionDeniedError,
    AIServiceError,
    AITimeoutError,
    InvalidConditionError,
    QueryNotRecognizedError,
)
from services.web.query.ai_assistant.schemas import (
    SelectionSystem,
    SystemSelectionOutput,
)
from services.web.query.ai_assistant.services.field_context import FieldContextService
from services.web.query.ai_assistant.services.intent import MessagePlanningService

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, base=MessageExecutionTask)
def execute_system_selection(self, execution: MessageExecution) -> SystemSelectionOutputSchema:  # noqa: N805
    """系统选择消息任务（一期全异步化）：构建字段上下文与操作上下文（原 SYNC execute 原样移入）。"""

    from services.web.ai_assistant.handlers import message_handler_registry

    handler = message_handler_registry.require(MessageType.SYSTEM_SELECTION)
    return handler.execute(input_data=execution.input_data, context_data=execution.context_data)


@celery_app.task(bind=True, base=MessageExecutionTask)
def execute_log_search(self, execution: MessageExecution) -> LogSearchOutputSchema:  # noqa: N805
    """日志检索消息任务（一期全异步化）：执行检索并产出快照（原 SYNC execute 原样移入）。

    执行失败直接抛出异常（平台收敛 FAILED，用户可重试），与原同步语义一致；
    成功后平台自动收敛 SUCCESS。
    """

    from services.web.ai_assistant.handlers import message_handler_registry

    handler = message_handler_registry.require(MessageType.LOG_SEARCH)
    return handler.execute(input_data=execution.input_data, context_data=execution.context_data)


class UserIntentExecutionTask(MessageExecutionTask):
    """单次 Agent 消息规划任务；成功收尾时原子创建全部独立业务消息。"""

    abstract = True

    def _finish_success(self, *, execution: MessageExecution, task_id: str, output_data: ResolvedIntentPlan) -> dict:
        result = MessagePlanExecutionService.finish(
            execution=execution,
            task_id=task_id,
            resolved=output_data,
        )
        output = UserIntentOutputSchema.model_validate(result)
        if output.error is None or output.error.error_code != UserIntentErrorCode.UNRECOGNIZED_INTENT:
            _dispatch_title_generation(execution=execution, log_prefix="[UserIntentExecutionTask]")
        return result


def _dispatch_title_generation(*, execution: MessageExecution, log_prefix: str) -> None:
    """消息成功后异步生成会话标题（NL 与意图识别链路共用；失败静默不阻塞消息终态）。"""

    try:
        # 延迟导入：避免 tasks ↔ services 加载期循环依赖
        from services.web.ai_assistant.tasks.conversation import (
            generate_conversation_title,
        )

        generate_conversation_title.delay(
            conversation_id=execution.message.conversation_id,
            query_text=execution.input_data.query_text,
            source_message_id=execution.message.id,
            source_message_task_id=execution.message.task_id or "",
        )
    except Exception:
        logger.exception(
            "%s dispatch title generation failed, message_id=%s",
            log_prefix,
            execution.message.id,
        )


def _planning_error_output(*, error: AIAssistantError, system_context) -> UserIntentOutputSchema:
    """把内部异常收敛为 USER_INTENT 稳定公开错误。"""

    reason = str(error.extra.get("reason") or "")
    if reason == "system required":
        error_code = UserIntentErrorCode.SYSTEM_REQUIRED
    elif reason in {"system_id not in candidates", "current system not in candidates"}:
        error_code = UserIntentErrorCode.SYSTEM_UNAVAILABLE
    elif isinstance(error, InvalidConditionError):
        error_code = UserIntentErrorCode.INVALID_CONDITION
    elif isinstance(error, QueryNotRecognizedError):
        error_code = UserIntentErrorCode.UNRECOGNIZED_INTENT
    elif isinstance(error, AIPermissionDeniedError):
        error_code = UserIntentErrorCode.PERMISSION_DENIED
    else:
        error_code = UserIntentErrorCode.AI_OUTPUT_INVALID
    return MessagePlanExecutionService.build_error_output(
        error_code=error_code,
        system_context=system_context,
    )


@celery_app.task(bind=True, base=UserIntentExecutionTask)
def execute_user_intent(self, execution: MessageExecution) -> ResolvedIntentPlan:  # noqa: N805
    """用一次通用 Agent 调用解析一至两条完整业务消息，落库交给成功收尾事务。"""

    context_data = execution.context_data
    candidates = MessagePlanningService.load_candidates(
        context_data.namespace,
        context_data.username,
        scope_type=context_data.scope_type,
        scope_id=context_data.scope_id,
    )
    candidate_context = SystemSelectionOutput(
        systems=[
            SelectionSystem(
                system_id=candidate["system_id"],
                name=candidate.get("name", ""),
                description=candidate.get("description", ""),
            )
            for candidate in candidates
        ]
    )
    candidate_system_ids = {candidate["system_id"] for candidate in candidates}
    current_selection = MessagePlanExecutionService.load_current_selection(
        execution=execution,
        candidate_system_ids=candidate_system_ids,
    )
    current_system_id = MessagePlanExecutionService.selection_system_id(current_selection)
    system_context_cache: dict[str, SystemSelectionOutput] = {}
    current_system = None
    if current_selection is not None:
        current_system_context = MessagePlanExecutionService.selection_system_context(current_selection)
        system_context_cache[current_system_id] = current_system_context
        current_system = current_system_context.systems[0]
    common_fields = FieldContextService.build_common_fields(namespace=context_data.namespace)
    reference_time = timezone.localtime()
    agent_context = MessagePlanningService.build_context(
        query_text=execution.input_data.query_text,
        candidates=candidates,
        common_fields=common_fields,
        current_system=current_system,
        username=context_data.username,
        reference_time=reference_time,
    )
    planning_context = MessagePlanningService.build_user_message(agent_context)
    agent_trace = UserIntentAgentTraceSchema(
        status="processing",
        agent_code=str(MessagePlanningService.agent_code.value),
        system_prompt=MessagePlanningService.system_prompt,
        user_prompt=planning_context,
        reference_time=reference_time.isoformat(),
    )
    MessagePlanExecutionService.persist_agent_trace(execution=execution, agent_trace=agent_trace)

    if not candidates:
        unavailable_output = MessagePlanExecutionService.build_error_output(
            error_code=UserIntentErrorCode.SYSTEM_UNAVAILABLE,
            system_context=candidate_context,
        )
        unavailable_trace = agent_trace.model_copy(
            update={
                "status": "failed",
                "error_code": str(UserIntentErrorCode.SYSTEM_UNAVAILABLE),
                "error_message": unavailable_output.error.error_message,
                "reason": "no authorized systems",
            }
        )
        return ResolvedIntentPlan(
            output=unavailable_output,
            messages=(),
            agent_trace=unavailable_trace,
        )

    planning_started_at = time.monotonic()
    deadline = planning_started_at + NL_PARSE_RETRY_TIMEOUT_SECONDS
    planning_error = None
    planning_attempt_count = 0
    plan = None
    retry_feedback = None
    for attempt in range(NL_PARSE_MAX_RETRIES + 1):
        planning_attempt_count = attempt + 1
        plan = None
        try:
            plan = MessagePlanningService.plan(
                context=agent_context,
                user_message=planning_context,
                retry_feedback=retry_feedback,
            )
            validation_context = candidate_context
            if plan.outcome == "dispatch" and any(
                item.message_type == MessageType.LOG_SEARCH for item in plan.messages
            ):
                target_system_id = MessagePlanExecutionService.target_system_id(
                    plan=plan,
                    current_selection=current_selection,
                )
                if target_system_id not in candidate_system_ids:
                    validation_context = candidate_context
                else:
                    if target_system_id not in system_context_cache:
                        system_context_cache[target_system_id] = FieldContextService.build_selection(
                            namespace=context_data.namespace,
                            system_ids=[target_system_id],
                            username=context_data.username,
                        )
                    validation_context = system_context_cache[target_system_id]
            validated = MessagePlanExecutionService.validate(
                plan=plan,
                system_context=validation_context,
                reference_time=reference_time,
                current_selection=current_selection,
            )
        except (
            AIOutputParseFailedError,
            AIOutputInvalidError,
            InvalidConditionError,
            QueryNotRecognizedError,
        ) as error:
            if (
                attempt >= NL_PARSE_MAX_RETRIES
                or time.monotonic() >= deadline
                or time.monotonic() + NL_PARSE_RETRY_INTERVAL_SECONDS >= deadline
            ):
                planning_error = error
                logger.error(
                    "[execute_user_intent] planning retry budget exhausted, message_id=%s, attempt=%s",
                    execution.message.id,
                    attempt + 1,
                    extra={"raw_output": error.extra.get("raw_output", "")},
                )
                break
            retry_feedback = MessagePlanningService.build_retry_feedback(error=error, plan=plan)
            attempt_duration_ms = int((time.monotonic() - planning_started_at) * 1000)
            logger.warning(
                "[execute_user_intent] planning attempt rejected, "
                "message_id=%s, attempt=%s, duration_ms=%s, error_code=%s",
                execution.message.id,
                attempt + 1,
                attempt_duration_ms,
                error.error_code,
                extra={
                    "message_id": execution.message.id,
                    "attempt": attempt + 1,
                    "duration_ms": attempt_duration_ms,
                    "error_code": str(error.error_code),
                    "reason": str(error.extra.get("reason") or ""),
                    "raw_output": str(error.extra.get("raw_output") or ""),
                },
            )
            time.sleep(NL_PARSE_RETRY_INTERVAL_SECONDS)
        except AIPermissionDeniedError as error:
            # 候选加载后权限可能发生变化；这是可展示的确定性业务错误，无需重试 Agent。
            planning_error = error
            break
        except (AITimeoutError, AIServiceError) as error:
            duration_ms = int((time.monotonic() - planning_started_at) * 1000)
            if (
                attempt >= NL_PARSE_MAX_RETRIES
                or time.monotonic() >= deadline
                or time.monotonic() + NL_PARSE_RETRY_INTERVAL_SECONDS >= deadline
            ):
                failed_trace = agent_trace.model_copy(
                    update={
                        "status": "failed",
                        "attempt_count": planning_attempt_count,
                        "duration_ms": duration_ms,
                        "error_code": str(error.error_code),
                        "error_message": str(error.message),
                        "reason": str(error.extra.get("reason") or ""),
                        "raw_output": str(error.extra.get("raw_output") or ""),
                    }
                )
                MessagePlanExecutionService.persist_agent_trace(
                    execution=execution,
                    agent_trace=failed_trace,
                )
                logger.warning(
                    "[execute_user_intent] planning service retry budget exhausted, "
                    "message_id=%s, attempt=%s, duration_ms=%s, error_code=%s",
                    execution.message.id,
                    planning_attempt_count,
                    duration_ms,
                    error.error_code,
                )
                raise
            logger.warning(
                "[execute_user_intent] planning service failed, retrying, "
                "message_id=%s, attempt=%s, duration_ms=%s, error_code=%s",
                execution.message.id,
                planning_attempt_count,
                duration_ms,
                error.error_code,
            )
            time.sleep(NL_PARSE_RETRY_INTERVAL_SECONDS)
        else:
            break

    duration_ms = int((time.monotonic() - planning_started_at) * 1000)
    if planning_error is not None:
        failed_trace = agent_trace.model_copy(
            update={
                "status": "failed",
                "plan": plan,
                "attempt_count": planning_attempt_count,
                "duration_ms": duration_ms,
                "error_code": str(planning_error.error_code),
                "error_message": str(planning_error.message),
                "reason": str(planning_error.extra.get("reason") or ""),
                "raw_output": str(planning_error.extra.get("raw_output") or ""),
            }
        )
        logger.warning(
            "[execute_user_intent] planning rejected, message_id=%s, attempt=%s, duration_ms=%s, error_code=%s",
            execution.message.id,
            planning_attempt_count,
            duration_ms,
            planning_error.error_code,
        )
        error_output = _planning_error_output(error=planning_error, system_context=candidate_context)
        selection_fallback = None
        if not isinstance(planning_error, AIPermissionDeniedError):
            selection_fallback = MessagePlanExecutionService.resolve_valid_selection_fallback(
                execution=execution,
                plan=plan,
                system_context=candidate_context,
                reference_time=reference_time,
                current_selection=current_selection,
                error_output=error_output,
                agent_trace=failed_trace,
            )
        if selection_fallback is not None:
            return selection_fallback
        return ResolvedIntentPlan(
            output=error_output,
            messages=(),
            agent_trace=failed_trace,
        )

    success_trace = agent_trace.model_copy(
        update={
            "status": "success",
            "plan": plan,
            "attempt_count": planning_attempt_count,
            "duration_ms": duration_ms,
        }
    )
    logger.info(
        "[execute_user_intent] planning completed, message_id=%s, attempt=%s, duration_ms=%s, outcome=%s",
        execution.message.id,
        planning_attempt_count,
        duration_ms,
        plan.outcome,
    )
    return MessagePlanExecutionService.resolve(
        execution=execution,
        validated=validated,
        agent_trace=success_trace,
    )


@periodic_task(run_every=crontab(hour="*/1"))
def refresh_common_queries() -> dict:
    """每小时聚合最近成功自然语言消息，按系统刷新常见操作 Redis 缓存。

    周期随代码声明（blueapps periodic_task，对齐上游 query/tasks.py 惯例），
    由 beat 自动调度，无需在 django_celery_beat 后台手动配置；
    任务幂等，重复执行只会覆盖为相同数据。
    """

    return OperationContextService.refresh_common_queries()
