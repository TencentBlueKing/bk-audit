"""审计日志检索的业务 Celery 任务。

自然语言检索为异步消息（调 AIDev 耗时长）；
常见操作缓存刷新为声明式周期任务（对齐上游 periodic_task 惯例，beat 自动调度）。
"""

import logging
import time
from uuid import uuid4

from blueapps.contrib.celery_tools.periodic import periodic_task
from blueapps.core.celery import celery_app
from celery.schedules import crontab
from django.db import transaction
from django.utils import timezone

from services.web.ai_assistant.constants import (
    NL_PARSE_MAX_RETRIES,
    NL_PARSE_RETRY_INTERVAL_SECONDS,
    NL_PARSE_RETRY_TIMEOUT_SECONDS,
    ExecutionStatus,
    MessageErrorCode,
    MessageType,
    UserIntentErrorCode,
)
from services.web.ai_assistant.models import Message
from services.web.ai_assistant.schemas.audit_search import (
    LogSearchContextSchema,
    LogSearchOutputSchema,
    NLSearchErrorSchema,
    NLSearchOutputSchema,
    SystemSelectionOutputSchema,
    UserIntentAgentTraceSchema,
    UserIntentOutputSchema,
)

# 导入契约：MessageService 必须保持模块级导入，禁止改成延迟导入——曾发生"仅给部分
# 调用点补局部导入"的事故（漏改 _create_log_search 与 execute_user_intent 的
# select_system 分支），产生 NameError / flake8 F821，且前者位于 _finish_success
# 的静默兜底内极难察觉（续链子消息悄悄不创建）。若确需规避循环依赖，应在引入反向
# 依赖的一侧（services/handlers 对本模块的引用）做函数内延迟导入，
# 写法对齐 services/message.py 的标题派发延迟导入。
from services.web.ai_assistant.services.message import MessageService
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
from services.web.query.ai_assistant.services.intent import (
    IntentRecognitionService,
    MessagePlanningService,
)
from services.web.query.ai_assistant.services.nl2json import NL2JSONService

logger = logging.getLogger(__name__)


def _create_log_search_with_fallback(
    *,
    execution: MessageExecution,
    condition,
    log_prefix: str,
) -> None:
    """续链 LOG_SEARCH；创建前置失败时固化可见、可重试的失败消息。"""

    message = execution.message
    try:
        MessageService(user=message.created_by).create(
            conversation=message.conversation,
            message_type=MessageType.LOG_SEARCH,
            input_data={"condition": condition.model_dump(mode="json")},
            parent_message_uid=str(message.uid),
            timeline_started_at=message.created_at,
        )
    except Exception:
        logger.exception(
            "%s auto log search creation failed, parent_message_id=%s",
            log_prefix,
            message.id,
        )
        service = MessageService(user=message.created_by)
        with transaction.atomic():
            service.lock_active_conversation(conversation=message.conversation)
            if Message.objects.filter(parent_message=message, message_type=MessageType.LOG_SEARCH).exists():
                return
            target_system = next(
                (
                    system
                    for system in execution.context_data.system_selection.systems
                    if system.system_id == condition.scope_id
                ),
                None,
            )
            context = LogSearchContextSchema(
                username=execution.context_data.username,
                namespace=execution.context_data.namespace,
                system_id=condition.scope_id,
                source="natural_language",
                session_scope_type=execution.context_data.session_scope_type,
                session_scope_id=execution.context_data.session_scope_id,
                extension_fields=target_system.extension_fields if target_system is not None else [],
            )
            now = timezone.now()
            fallback = Message.objects.create(
                conversation=message.conversation,
                parent_message=message,
                message_type=MessageType.LOG_SEARCH,
                status=ExecutionStatus.FAILED,
                task_id=str(uuid4()),
                input_data={"condition": condition.model_dump(mode="json")},
                context_data=context.model_dump(mode="json"),
                output_data=None,
                error_code=str(MessageErrorCode.TASK_EXECUTION_FAILED),
                error_message="日志检索消息创建失败，请重试",
                last_activity_at=now,
                finished_at=now,
                created_by=message.created_by,
                updated_by=message.created_by,
            )
            Message.objects.filter(id=fallback.id).update(created_at=message.created_at, updated_at=now)


class NLSearchExecutionTask(MessageExecutionTask):
    """自然语言检索任务：消息成功后按 auto_execute 创建 LOG_SEARCH。

    预期内识别失败时消息同样收敛 SUCCESS（output_data 携带结构化 error 协议），
    无 condition 不续链；续链消息先持久化为 PROCESSING，再由独立任务执行并收敛终态。
    创建失败不回滚自然语言消息，业务执行失败保留可见、可重试的 FAILED 子消息。
    """

    abstract = True

    def _finish_success(self, *, execution: MessageExecution, task_id: str, output_data: NLSearchOutputSchema) -> dict:
        result = super()._finish_success(execution=execution, task_id=task_id, output_data=output_data)
        try:
            self._create_auto_log_search(execution=execution, output_data=output_data)
        except Exception:
            # 续链失败不回滚自然语言消息终态（识别成功保留 condition，子消息不创建）
            logger.exception(
                "[NLSearchExecutionTask] auto log search failed, message_id=%s, task_id=%s",
                execution.message.id,
                task_id,
            )
        _dispatch_title_generation(execution=execution, log_prefix="[NLSearchExecutionTask]")
        return result

    @staticmethod
    def _create_auto_log_search(*, execution: MessageExecution, output_data: NLSearchOutputSchema) -> None:
        """以自然语言消息为父消息创建独立执行的日志检索消息。"""

        message = execution.message
        if not execution.input_data.auto_execute:
            return
        if output_data.condition is None:
            # 识别失败（结构化 error 协议）无检索条件，不续链
            return
        _create_log_search_with_fallback(
            execution=execution,
            condition=output_data.condition,
            log_prefix="[NLSearchExecutionTask]",
        )
        logger.info(
            "[NLSearchExecutionTask] auto log search created, parent_message_id=%s",
            message.id,
        )


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
    candidates = IntentRecognitionService.load_candidates(
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


@celery_app.task(bind=True, base=NLSearchExecutionTask)
def execute_natural_language_search(self, execution: MessageExecution) -> NLSearchOutputSchema:  # noqa: N805
    """识别自然语言并产出受控检索条件（薄代理：调用 query 模块 NL2JSON 服务）。

    解析失败（AI 返回内容不合格，具随机性）任务内自动重试：受次数上限与
    总时长上限双约束，任一超限即结束并冒泡收敛 FAILED（手动重试重新获得预算）。
    暂态故障（AIDev 超时 / 服务异常）直接冒泡：平台收敛为 FAILED，
    用户可通过消息重试接口重跑（重试可恢复的故障必须保留 FAILED 语义）。
    确定性识别失败（未识别 / 输出非法 / 权限拒绝）不抛出：消息收敛 SUCCESS
    并携带结构化 error 协议供前端展示（重试同输入仍会失败，引导调整问法）；
    其余非预期异常继续冒泡，由平台收敛为 FAILED。
    """

    context_data = execution.context_data
    deadline = time.monotonic() + NL_PARSE_RETRY_TIMEOUT_SECONDS
    try:
        for attempt in range(NL_PARSE_MAX_RETRIES + 1):
            try:
                condition = NL2JSONService.convert(
                    query_text=execution.input_data.query_text,
                    selection=context_data.system_selection,
                    scope_id=context_data.scope_id,
                    username=context_data.username,
                )
            except AIOutputParseFailedError:
                # 解析失败具随机性：预算内自动重试；超次数或超时长（含 sleep 后即超
                # 预算的前置检查——防失败 + 等待后仍发起突破预算的下一轮）即结束并冒泡 FAILED
                if (
                    attempt >= NL_PARSE_MAX_RETRIES
                    or time.monotonic() >= deadline
                    or time.monotonic() + NL_PARSE_RETRY_INTERVAL_SECONDS >= deadline
                ):
                    logger.error(
                        "[execute_natural_language_search] nl2json parse retry budget exhausted, "
                        "message_id=%s, attempt=%s",
                        execution.message.id,
                        attempt + 1,
                    )
                    raise
                logger.warning(
                    "[execute_natural_language_search] nl2json parse failed, retrying, " "message_id=%s, attempt=%s",
                    execution.message.id,
                    attempt + 1,
                )
                time.sleep(NL_PARSE_RETRY_INTERVAL_SECONDS)
            else:
                break
    except (AITimeoutError, AIServiceError, AIOutputParseFailedError):
        # 暂态基础设施故障 + 超预算解析失败：冒泡收敛 FAILED 保留重试接口可用性，
        # 不与确定性识别失败（SUCCESS + error 协议）混同恢复语义
        logger.exception(
            "[execute_natural_language_search] nl2json transient failure, message_id=%s",
            execution.message.id,
        )
        raise
    except AIAssistantError as error:
        # 确定性业务失败：query 侧业务异常自带稳定 error_code 与脱敏 message
        logger.warning(
            "[execute_natural_language_search] nl2json recognized failure, message_id=%s, error_code=%s",
            execution.message.id,
            error.error_code,
        )
        return NLSearchOutputSchema(
            error=NLSearchErrorSchema(error_code=error.error_code, error_message=error.message),
        )
    return NLSearchOutputSchema(condition=condition)


@periodic_task(run_every=crontab(hour="*/1"))
def refresh_common_queries() -> dict:
    """每小时聚合最近成功自然语言消息，按系统刷新常见操作 Redis 缓存。

    周期随代码声明（blueapps periodic_task，对齐上游 query/tasks.py 惯例），
    由 beat 自动调度，无需在 django_celery_beat 后台手动配置；
    任务幂等，重复执行只会覆盖为相同数据。
    """

    return OperationContextService.refresh_common_queries()
