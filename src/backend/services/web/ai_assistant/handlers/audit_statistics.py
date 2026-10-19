"""程序与 AI 统计附件接入。

只从成功 LOG_SEARCH 固化完整范围与服务端字段显示信息；执行阶段再鉴权。
程序统计异步轮询，AI 统计使用平台流式生命周期；均不引入报告编辑或导出。
"""

from django.conf import settings

from services.web.ai.prompts.log_statistics import SYSTEM_PROMPT
from services.web.ai_assistant.constants import AttachmentType, ExecutionMode
from services.web.ai_assistant.handlers.attachment import (
    AttachmentPreparation,
    AttachmentTypeHandler,
)
from services.web.ai_assistant.handlers.log_search_source import prepare_log_attachment
from services.web.ai_assistant.handlers.registry import attachment_handler_registry
from services.web.ai_assistant.models import Message
from services.web.ai_assistant.schemas.audit_statistics import (
    AIStatisticsAttachmentContext,
    AIStatisticsAttachmentInput,
    AIStatisticsAttachmentOutput,
    AIStatisticsQuerySummary,
    FieldStatisticsAttachmentContext,
    FieldStatisticsAttachmentInput,
    FieldStatisticsAttachmentOutput,
)
from services.web.ai_assistant.tasks.audit_statistics import (
    generate_ai_statistics,
    generate_field_statistics,
)
from services.web.query.ai_assistant.exceptions import UnsupportedFieldType
from services.web.query.ai_assistant.log_tools.schemas import (
    LOG_TOOL_NESTED_FIELD_NAMES,
    LogFieldRef,
)
from services.web.query.ai_assistant.log_tools.statistics import FieldStatisticsService


class FieldStatisticsAttachmentHandler(
    AttachmentTypeHandler[
        FieldStatisticsAttachmentInput, FieldStatisticsAttachmentContext, FieldStatisticsAttachmentOutput
    ]
):
    """完整来源范围上的固定统计包；失败后可原对象手动重试，再次生成则创建新附件。"""

    attachment_type = AttachmentType.FIELD_STATISTICS
    execution_mode = ExecutionMode.ASYNC
    input_model = FieldStatisticsAttachmentInput
    context_model = FieldStatisticsAttachmentContext
    output_model = FieldStatisticsAttachmentOutput
    async_task = generate_field_statistics

    def prepare(self, *, user: str, source_message: Message, input_data: FieldStatisticsAttachmentInput):
        """构造可信执行快照；不采样字段类型，JSON 路径的实际类型由最终查询判断。"""
        input_data, log_context, _, _ = prepare_log_attachment(
            user=user,
            source_message=source_message,
            input_data=input_data,
            fields=[input_data.field, LogFieldRef(raw_name="start_time")],
        )
        condition = input_data.condition
        field = LogFieldRef(raw_name=input_data.field.raw_name, keys=input_data.field.keys)
        if not field.keys and field.raw_name in LOG_TOOL_NESTED_FIELD_NAMES:
            raise UnsupportedFieldType()
        resolved_field = FieldStatisticsService._field(field)
        return AttachmentPreparation(
            title=f"{resolved_field.display_name}统计",
            input_data=input_data,
            context_data=FieldStatisticsAttachmentContext(
                search_condition=condition,
                field=resolved_field,
                interval=input_data.interval,
                username=user,
                namespace=log_context.namespace,
                timezone=settings.TIME_ZONE,
            ),
        )


attachment_handler_registry.register(FieldStatisticsAttachmentHandler())


class AIStatisticsAttachmentHandler(
    AttachmentTypeHandler[AIStatisticsAttachmentInput, AIStatisticsAttachmentContext, AIStatisticsAttachmentOutput]
):
    """提供独立流式原文统计能力，不继承分析报告编辑、导出或标题生成。"""

    attachment_type = AttachmentType.AI_STATISTICS
    execution_mode = ExecutionMode.ASYNC
    input_model = AIStatisticsAttachmentInput
    context_model = AIStatisticsAttachmentContext
    output_model = AIStatisticsAttachmentOutput
    async_task = generate_ai_statistics
    is_stream = True
    supports_feedback = True

    def prepare(self, *, user: str, source_message: Message, input_data: AIStatisticsAttachmentInput):
        """校验来源并固化初始范围；不把来源范围设置为 Agent 实际查询的限制。"""
        input_data, log_context, log_output, summary_matches = prepare_log_attachment(
            user=user,
            source_message=source_message,
            input_data=input_data,
        )
        condition = input_data.condition
        return AttachmentPreparation(
            title="AI 统计",
            input_data=input_data,
            context_data=AIStatisticsAttachmentContext(
                system_prompt=SYSTEM_PROMPT,
                instruction=input_data.instruction,
                initial_search_condition=condition,
                query_summary=AIStatisticsQuerySummary(
                    total=log_output.total,
                    executed_at=log_output.query_summary.executed_at,
                )
                if summary_matches
                else None,
                username=user,
                namespace=log_context.namespace,
                timezone=settings.TIME_ZONE,
                language=settings.LANGUAGE_CODE,
            ),
        )


attachment_handler_registry.register(AIStatisticsAttachmentHandler())
