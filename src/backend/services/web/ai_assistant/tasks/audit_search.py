"""审计日志检索的业务 Celery 任务。

自然语言检索为异步消息（调 AIDev 耗时长）；
常见操作缓存刷新为声明式周期任务（对齐上游 periodic_task 惯例，beat 自动调度）。
"""

from __future__ import annotations

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
    NLSearchErrorSchema,
    NLSearchOutputSchema,
    SystemSelectionOutputSchema,
    UserIntentAgentTraceSchema,
    UserIntentErrorSchema,
    UserIntentOutputSchema,
)

# 多条续链共用 MessageService，统一导入以免局部导入漏掉分支，静默丢失子消息。
# AIAssistantConfig.ready() 从 handlers 入口完成初始化，避免 Worker 从 tasks 反向触发注册。
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
    AIServiceError,
    AITimeoutError,
    QueryNotRecognizedError,
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
    """复用统一消息创建链路续链 LOG_SEARCH；实际检索由消息任务异步执行。"""

    message = execution.message
    try:
        MessageService(user=message.created_by).create(
            conversation=message.conversation,
            message_type=MessageType.LOG_SEARCH,
            input_data={"condition": condition.model_dump(mode="json")},
            parent_message_uid=str(message.uid),
        )
    except Exception:
        logger.exception(
            "%s auto log search creation failed, parent_message_id=%s",
            log_prefix,
            message.id,
        )
        raise


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
        )
    except Exception:
        logger.exception(
            "%s dispatch title generation failed, message_id=%s",
            log_prefix,
            execution.message.id,
        )


def _planning_error_output(*, error: AIAssistantError, system_context) -> UserIntentOutputSchema:
    """把计划或条件校验失败映射为稳定业务错误，保留字段类错误的具体错误码。"""

    reason = str(error.extra.get("reason") or "")
    if reason == "system required":
        error_code = UserIntentErrorCode.SYSTEM_REQUIRED
    elif reason in {"system_id not in candidates", "current system not in candidates"}:
        error_code = UserIntentErrorCode.SYSTEM_UNAVAILABLE
    else:
        candidates = [{"system_id": system.system_id, "name": system.name} for system in system_context.systems]
        return UserIntentOutputSchema(
            intent="unrecognized",
            error=UserIntentErrorSchema(
                error_code=error.error_code,
                error_message=error.message or "AI 返回内容解析失败，请稍后重试或换一种描述",
                candidates=candidates if isinstance(error, AIOutputInvalidError) else [],
            ),
        )
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
    system_context = FieldContextService.build_planning_context(
        namespace=context_data.namespace,
        system_ids=[candidate["system_id"] for candidate in candidates],
        username=context_data.username,
    )
    current_selection = MessagePlanExecutionService.load_current_selection(
        execution=execution,
        system_context=system_context,
    )
    current_system_id = MessagePlanExecutionService.selection_system_id(current_selection)
    reference_time = timezone.localtime()
    planning_context = MessagePlanningService.build_user_message(
        query_text=execution.input_data.query_text,
        system_context=system_context,
        current_system_id=current_system_id,
        username=context_data.username,
        scope_type=context_data.scope_type,
        scope_id=context_data.scope_id,
        reference_time=reference_time,
    )
    agent_trace = UserIntentAgentTraceSchema(
        status="processing",
        agent_code=str(MessagePlanningService.agent_code.value),
        system_prompt=MessagePlanningService.system_prompt,
        user_prompt=planning_context,
        reference_time=reference_time.isoformat(),
    )
    MessagePlanExecutionService.persist_agent_trace(execution=execution, agent_trace=agent_trace)

    planning_started_at = time.monotonic()
    deadline = planning_started_at + NL_PARSE_RETRY_TIMEOUT_SECONDS
    planning_error = None
    planning_attempt_count = 0
    plan = None
    for attempt in range(NL_PARSE_MAX_RETRIES + 1):
        planning_attempt_count = attempt + 1
        try:
            plan = MessagePlanningService.plan(
                query_text=execution.input_data.query_text,
                system_context=system_context,
                current_system_id=current_system_id,
                username=context_data.username,
                scope_type=context_data.scope_type,
                scope_id=context_data.scope_id,
                reference_time=reference_time,
                user_message=planning_context,
            )
            validated = MessagePlanExecutionService.validate(
                plan=plan,
                system_context=system_context,
                reference_time=reference_time,
                current_selection=current_selection,
            )
        except (AIOutputParseFailedError, AIOutputInvalidError, QueryNotRecognizedError) as error:
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
            time.sleep(NL_PARSE_RETRY_INTERVAL_SECONDS)
        except (AITimeoutError, AIServiceError) as error:
            duration_ms = int((time.monotonic() - planning_started_at) * 1000)
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
                "[execute_user_intent] planning service failed, "
                "message_id=%s, attempt=%s, duration_ms=%s, error_code=%s",
                execution.message.id,
                planning_attempt_count,
                duration_ms,
                error.error_code,
            )
            raise
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
        return ResolvedIntentPlan(
            output=_planning_error_output(error=planning_error, system_context=system_context),
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
