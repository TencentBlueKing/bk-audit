"""审计日志检索的业务 Celery 任务。

自然语言检索为异步消息（调 AIDev 耗时长）；
常见操作缓存刷新为声明式周期任务（对齐上游 periodic_task 惯例，beat 自动调度）。
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from blueapps.contrib.celery_tools.periodic import periodic_task
from blueapps.core.celery import celery_app
from celery.schedules import crontab

from services.web.ai_assistant.constants import (
    NL_PARSE_MAX_RETRIES,
    NL_PARSE_RETRY_INTERVAL_SECONDS,
    NL_PARSE_RETRY_TIMEOUT_SECONDS,
    ExecutionStatus,
    MessageType,
)
from services.web.ai_assistant.models import Message
from services.web.ai_assistant.schemas.audit_search import (
    LogSearchOutputSchema,
    NLSearchErrorSchema,
    NLSearchOutputSchema,
    SystemSelectionOutputSchema,
    UserIntentErrorSchema,
    UserIntentOutputSchema,
)

# 多条续链共用 MessageService，统一导入以免局部导入漏掉分支，静默丢失子消息。
# AIAssistantConfig.ready() 从 handlers 入口完成初始化，避免 Worker 从 tasks 反向触发注册。
from services.web.ai_assistant.services.message import MessageService
from services.web.ai_assistant.tasks.message import MessageExecutionTask
from services.web.query.ai_assistant.exceptions import (
    AIAssistantError,
    AIOutputInvalidError,
    AIOutputParseFailedError,
    AIServiceError,
    AITimeoutError,
)
from services.web.query.ai_assistant.services.intent import IntentRecognitionService
from services.web.query.ai_assistant.services.nl2json import NL2JSONService

if TYPE_CHECKING:
    from services.web.ai_assistant.services.message_execution import MessageExecution

logger = logging.getLogger(__name__)


class NLSearchExecutionTask(MessageExecutionTask):
    """自然语言检索任务：消息成功后按 auto_execute 续链同步执行 LOG_SEARCH。

    预期内识别失败时消息同样收敛 SUCCESS（output_data 携带结构化 error 协议），
    无 condition 不续链；续链的日志检索为同步消息——在 Worker 线程内直接执行，
    成功即创建 SUCCESS 子消息；失败则子消息不创建，自然语言消息本身
    保留 SUCCESS 和 condition，前端可基于该消息重新发起检索。
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
        """以自然语言消息为父消息同步创建日志检索子消息（失败不创建）。"""

        message = execution.message
        if not execution.input_data.auto_execute:
            return
        if output_data.condition is None:
            # 识别失败（结构化 error 协议）无检索条件，不续链
            return
        MessageService(user=message.created_by).create_executed(
            conversation=message.conversation,
            message_type=MessageType.LOG_SEARCH,
            input_data={"condition": output_data.condition.model_dump(mode="json")},
            parent_message=message,
            # 时间线起点=用户发问时刻（NL 消息创建即用户发问）：duration 为全链真实耗时
            timeline_started_at=message.created_at,
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
    """用户意图识别任务：意图识别 → 按意图建/复用系统选择 → 条件识别 → 续链检索。

    预期内失败（unrecognized / SYSTEM_REQUIRED / 条件识别失败）同样收敛 SUCCESS
    并携带结构化 error 协议（error_message 由 AI 动态生成或后端拼接候选引导）；
    条件识别成功且 auto_execute 时续链 LOG_SEARCH（失败不影响终态，对齐 NL 模式）；
    unrecognized（闲聊类话语）不派发标题生成。
    """

    abstract = True

    def _finish_success(
        self, *, execution: MessageExecution, task_id: str, output_data: UserIntentOutputSchema
    ) -> dict:
        result = super()._finish_success(execution=execution, task_id=task_id, output_data=output_data)
        if output_data.condition is not None:
            try:
                self._create_log_search(execution=execution, output_data=output_data)
            except Exception:
                # 续链失败不回滚消息终态（识别成功保留 condition，子消息不创建）
                logger.exception(
                    "[UserIntentExecutionTask] auto log search failed, message_id=%s, task_id=%s",
                    execution.message.id,
                    task_id,
                )
        if output_data.intent != "unrecognized":
            _dispatch_title_generation(execution=execution, log_prefix="[UserIntentExecutionTask]")
        return result

    @staticmethod
    def _create_log_search(*, execution: MessageExecution, output_data: UserIntentOutputSchema) -> None:
        """以意图识别消息为父消息同步创建日志检索子消息（复用 NL 续链模式）。"""

        message = execution.message
        if not execution.input_data.auto_execute:
            return
        MessageService(user=message.created_by).create_executed(
            conversation=message.conversation,
            message_type=MessageType.LOG_SEARCH,
            input_data={"condition": output_data.condition.model_dump(mode="json")},
            parent_message=message,
            # 时间线起点=用户发问时刻：检索结果消息的 duration_seconds 为全链真实耗时
            timeline_started_at=message.created_at,
        )
        logger.info(
            "[UserIntentExecutionTask] auto log search created, parent_message_id=%s",
            message.id,
        )


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


@celery_app.task(bind=True, base=UserIntentExecutionTask)
def execute_user_intent(self, execution: MessageExecution) -> UserIntentOutputSchema:  # noqa: N805
    """用户意图识别：意图（选系统/日志检索/无法识别）→ 按需系统选择 → 条件识别 → 结构化输出。

    解析失败（非合法 JSON / 形态不合契约）预算内自动重试（次数 + 总时长双约束），
    超限冒泡收敛 FAILED（手动重试恢复预算）；越权 system_id 与 AIDev 暂态故障直接冒泡；
    unrecognized（AI 判定无法归类）与 SYSTEM_REQUIRED（检索意图明确但会话无系统，
    平台守门）收敛 SUCCESS + 结构化 error（error_message 动态）。
    """

    # 延迟导入：handlers 依赖本模块的任务函数，反向引用需运行期加载
    from services.web.ai_assistant.handlers.audit_search import load_selection_snapshot

    context_data = execution.context_data
    query_text = execution.input_data.query_text
    candidates = IntentRecognitionService.load_candidates(
        context_data.namespace,
        context_data.username,
        scope_type=context_data.scope_type,
        scope_id=context_data.scope_id,
    )
    # 会话当前系统 = 最新成功 SYSTEM_SELECTION（切换/复用判定依据）
    current_selection = (
        Message.objects.filter(
            conversation=execution.message.conversation,
            created_by=context_data.username,
            message_type=MessageType.SYSTEM_SELECTION,
            status=ExecutionStatus.SUCCESS,
        )
        .order_by("-id")
        .first()
    )
    current_system_id = ""
    if current_selection is not None:
        systems = (current_selection.output_data or {}).get("systems") or []
        current_system_id = str((systems[0] or {}).get("system_id") or "") if systems else ""
    # 场景过滤守门：会话当前系统不在当前 scope 候选内时视为未选系统（防跨场景复用，
    # 如用户切换左上角场景后继续对话）；select_system 将按候选重建选择、log_search 走 SYSTEM_REQUIRED
    if context_data.scope_type and current_system_id:
        if current_system_id not in {candidate["system_id"] for candidate in candidates}:
            current_selection = None
            current_system_id = ""
    # ① 意图识别（解析失败预算重试，超限转结构化错误协议；越权/暂态冒泡 FAILED）
    deadline = time.monotonic() + NL_PARSE_RETRY_TIMEOUT_SECONDS
    intent_error: AIAssistantError | None = None
    try:
        for attempt in range(NL_PARSE_MAX_RETRIES + 1):
            try:
                payload = IntentRecognitionService.recognize(
                    query_text=query_text,
                    candidates=candidates,
                    current_system_id=current_system_id,
                    username=context_data.username,
                )
            except AIOutputParseFailedError as error:
                # 解析失败具随机性：预算内自动重试（超次数/超时长/含 sleep 后即超
                # 预算的前置检查——防 19s 失败 + 2s 等待后仍发起突破 20s 预算的下一轮）
                if (
                    attempt >= NL_PARSE_MAX_RETRIES
                    or time.monotonic() >= deadline
                    or time.monotonic() + NL_PARSE_RETRY_INTERVAL_SECONDS >= deadline
                ):
                    logger.error(
                        "[execute_user_intent] intent parse retry budget exhausted, message_id=%s, attempt=%s",
                        execution.message.id,
                        attempt + 1,
                        # raw_output 进结构化日志 extra：定位失败形态（嵌套引号未转义 vs 输出截断）的唯一直接证据
                        extra={"raw_output": error.extra.get("raw_output", "")},
                    )
                    # 解析失败超预算 = 确定性失败（模型能力边界，重试同输入大概率仍失败）：
                    # 收敛 SUCCESS + 结构化 error（前端错误卡有现成渲染，用户有反馈），
                    # 不收敛 FAILED——FAILED 仅保留给可恢复的暂态故障（重试才有意义）
                    intent_error = error
                    break
                time.sleep(NL_PARSE_RETRY_INTERVAL_SECONDS)
            else:
                break
    except (AITimeoutError, AIServiceError, AIOutputInvalidError):
        logger.exception("[execute_user_intent] intent recognition failed, message_id=%s", execution.message.id)
        raise
    if intent_error is not None:
        return UserIntentOutputSchema(
            intent="unrecognized",
            error=UserIntentErrorSchema(
                error_code=intent_error.error_code,
                error_message="AI 返回内容解析失败，请稍后重试或换一种描述",
            ),
        )
    # ② 无法识别：AI 动态说明为什么不行
    if payload.intent == "unrecognized":
        return UserIntentOutputSchema(
            intent="unrecognized",
            error=UserIntentErrorSchema(
                error_code="UNRECOGNIZED_INTENT",
                error_message=payload.message or "未能理解您的需求，请描述要查询的系统或日志内容",
            ),
        )
    # ③ 系统路由：select_system → 无条件创建新 SELECTION（产品决策：通用性优先，
    #    不做「命中当前系统则复用」的特殊分支）——每次切换都有新消息/新卡片，
    #    对话语义简单通用（复用分支曾引发重复切换「AI 回应消失」问题，复盘见
    #    mydocs 重复切换系统消息消失问题复盘_2026-09-10）；log_search 校验会话
    #    已有系统（平台守门）
    selection_message = current_selection
    system_id = current_system_id
    if payload.intent == "select_system":
        system_id = payload.system_id
        selection_message = MessageService(user=context_data.username).create_executed(
            conversation=execution.message.conversation,
            message_type=MessageType.SYSTEM_SELECTION,
            # 透传 session scope（前端左上角场景过滤器当前选择）：
            # 子消息继承同一 scope，使 NL/LOG_SEARCH 续链仍按 session 收窄；
            # 历史消息重试（scope 为空，协议升级前快照）补 cross_system 宽口径兜底（v1 行为）
            input_data={
                "system_ids": [system_id],
                "scope_type": context_data.scope_type or "cross_system",
                "scope_id": context_data.scope_id,
            },
            # 消息卡片可见性（通用显隐协议）：纯切换（need_search=false）SELECTION 是
            # 本轮唯一产出，卡片必须展示；复合意图（切系统+检索）仅展示日志检索消息
            # （设计侧要求）——visible 随消息持久化，刷新后前端按顶层 visible 字段恢复
            visible=not payload.need_search,
            # 时间线起点=用户发问时刻：duration_seconds 表达真实等待耗时（含意图识别 LLM）
            timeline_started_at=execution.message.created_at,
        )
        if not payload.need_search:
            # 纯切换（无检索诉求）：不调条件解析、不续链检索——切换即本轮终点。
            # 若强行把「切换到X」类语句交给条件解析必然失败，曾误报
            # 「未能理解检索需求」让用户以为切换失败（阶段一报障修复；
            # 通用 message_type+message_input 分发架构见迭代方案，届时由 LLM 直接决定是否派发检索）
            candidate_name = next(
                (str(candidate["name"]) for candidate in candidates if str(candidate.get("system_id")) == system_id),
                system_id,
            )
            # 对话不变式：每轮 SUCCESS 必有面向用户的非空 message（前端渲染的可见载体）；
            # 本轮已无条件新建 SELECTION（真切换），LLM 切换话术语义成立
            message = payload.message or f"已为您切换到 {candidate_name}，如需检索日志请继续描述"
            return UserIntentOutputSchema(
                intent="select_system",
                system_id=system_id,
                message=message,
                selection_message_uid=str(selection_message.uid) if selection_message is not None else "",
            )
    elif not current_system_id:
        # 检索意图明确但缺会话系统状态（非识别失败）：AI 动态引导 + 候选清单
        if candidates:
            error_message = "请先告诉我要查哪个系统的日志，您有权限的系统：" + "、".join(candidate["name"] for candidate in candidates)
        else:
            # 场景过滤后无任何可检索系统（如切换到未授权场景）：引导切换场景/申请权限
            error_message = "当前场景下您暂无可检索的系统，请切换场景或联系管理员开通系统权限"
        return UserIntentOutputSchema(
            intent="log_search",
            error=UserIntentErrorSchema(
                error_code="SYSTEM_REQUIRED",
                error_message=error_message,
                candidates=candidates,
            ),
        )
    # ④ 条件识别（field_context 来自目标系统选择快照；解析失败预算内重试、超限转
    #    结构化 error；暂态故障冒泡 FAILED 保留重试接口；确定性失败走结构化 error，
    #    SELECTION 已建则保留——系统切换不被检索失败阻塞）
    selection = load_selection_snapshot(selection_message)
    deadline = time.monotonic() + NL_PARSE_RETRY_TIMEOUT_SECONDS
    condition = None
    condition_error: AIAssistantError | None = None
    try:
        for attempt in range(NL_PARSE_MAX_RETRIES + 1):
            try:
                condition = NL2JSONService.convert(
                    query_text=query_text,
                    selection=selection,
                    scope_id=system_id,
                    username=context_data.username,
                )
            except AIOutputParseFailedError as error:
                # 解析失败具随机性：预算内自动重试（超次数/超时长/含 sleep 后即超
                # 预算的前置检查）；超限为确定性失败（模型能力边界，重试同输入大概率
                # 仍失败）——转结构化 error 协议而非冒泡：SUCCESS+error 前端错误卡有
                # 现成渲染（曾收敛 FAILED 致续链不发生、前端轮询子消息永远空、
                # 用户无任何反馈，2026-09-11 修复），FAILED 仅保留给可恢复暂态故障
                if (
                    attempt >= NL_PARSE_MAX_RETRIES
                    or time.monotonic() >= deadline
                    or time.monotonic() + NL_PARSE_RETRY_INTERVAL_SECONDS >= deadline
                ):
                    logger.error(
                        "[execute_user_intent] condition parse retry budget exhausted, message_id=%s, attempt=%s",
                        execution.message.id,
                        attempt + 1,
                        # raw_output 进结构化日志 extra：定位失败形态（嵌套引号未转义 vs 输出截断）的唯一直接证据
                        extra={"raw_output": error.extra.get("raw_output", "")},
                    )
                    condition_error = error
                    break
                time.sleep(NL_PARSE_RETRY_INTERVAL_SECONDS)
            else:
                break
    except (AITimeoutError, AIServiceError):
        # 暂态基础设施故障：冒泡收敛 FAILED（MessageService.retry 仅接受 FAILED，
        # 可恢复故障必须保留重试接口），对齐 NL 任务语义
        logger.exception(
            "[execute_user_intent] condition recognition transient failure, message_id=%s",
            execution.message.id,
        )
        raise
    except AIAssistantError as error:
        # 确定性业务失败（未识别/输出非法/权限拒绝）：SUCCESS + 结构化 error
        # （重试同输入仍会失败，引导调整问法）
        condition_error = error
    if condition_error is not None:
        logger.warning(
            "[execute_user_intent] condition not recognized, message_id=%s, error_code=%s",
            execution.message.id,
            condition_error.error_code,
        )
        # 本轮发生系统切换（select_system 恒新建 SELECTION）时，检索条件识别失败
        # 不得掩盖切换结果：文案前置切换成功事实，防整句「未能理解检索需求」
        # 让用户误以为切换也失败了（need_search 误判时的兜底）
        error_message = condition_error.message
        if payload.intent == "select_system":
            candidate_name = next(
                (str(candidate["name"]) for candidate in candidates if str(candidate.get("system_id")) == system_id),
                system_id,
            )
            error_message = f"已为您切换到 {candidate_name}，{condition_error.message}"
        return UserIntentOutputSchema(
            intent=payload.intent,
            system_id=system_id,
            error=UserIntentErrorSchema(error_code=condition_error.error_code, error_message=error_message),
            # 本轮 SELECTION 已建（select_system 恒新建）：透传 uid 供前端定位切换消息，
            # 检索失败不应丢失切换上下文（曾漏传致 output.selection_message_uid 恒空）
            selection_message_uid=str(selection_message.uid) if selection_message is not None else "",
        )
    return UserIntentOutputSchema(
        intent=payload.intent,
        system_id=system_id,
        message=payload.message,
        condition=condition,
        selection_message_uid=str(selection_message.uid) if selection_message is not None else "",
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

    # 同上，避免周期任务模块导入阶段提前初始化业务 Service 包。
    from services.web.ai_assistant.services.operation import OperationContextService

    return OperationContextService.refresh_common_queries()
