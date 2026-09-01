"""日志分析报告 Attachment Handler。

Handler 只负责校验 LOG_SEARCH 来源、构建最小快照与声明编辑/导出能力；
异步状态、流切换、任务重试和终态回写仍由附件平台统一处理。
"""

from django.conf import settings

from apps.meta.models import GlobalMetaConfig
from services.web.ai_assistant.constants import (
    AI_ASSISTANT_LOG_ANALYSIS_PROMPT_KEY,
    DEFAULT_AI_ANALYSIS_TITLE,
    AnalysisMode,
    AttachmentExportFormat,
    AttachmentType,
    ExecutionMode,
    ExecutionStatus,
    MessageType,
)
from services.web.ai_assistant.exceptions import (
    AttachmentSnapshotValidationError,
    InvalidAttachmentPreparation,
    InvalidAttachmentSource,
    UnsupportedLogAnalysisCondition,
)
from services.web.ai_assistant.exporters import MarkdownDocumentExporter
from services.web.ai_assistant.handlers.attachment import (
    AttachmentExportResult,
    AttachmentPreparation,
    AttachmentTypeHandler,
)
from services.web.ai_assistant.handlers.registry import attachment_handler_registry
from services.web.ai_assistant.models import Attachment, Message
from services.web.ai_assistant.schemas import parse_snapshot
from services.web.ai_assistant.schemas.audit_analysis import (
    AIAnalysisContextSchema,
    AIAnalysisInputSchema,
    AIAnalysisOutputSchema,
    AIAnalysisQuerySummary,
)
from services.web.ai_assistant.schemas.audit_search import (
    LogSearchContextSchema,
    LogSearchInputSchema,
    LogSearchOutputSchema,
)
from services.web.ai_assistant.tasks.audit_analysis import execute_log_analysis
from services.web.query.ai_assistant.log_tools.schemas import AgentSearchCondition


class AIAnalysisHandler(AttachmentTypeHandler[AIAnalysisInputSchema, AIAnalysisContextSchema, AIAnalysisOutputSchema]):
    """基于一条成功日志检索快照生成可编辑 Markdown 分析报告。"""

    attachment_type = AttachmentType.AI_ANALYSIS
    execution_mode = ExecutionMode.ASYNC
    input_model = AIAnalysisInputSchema
    context_model = AIAnalysisContextSchema
    output_model = AIAnalysisOutputSchema
    supports_feedback = True
    is_stream = True
    export_formats = (AttachmentExportFormat.MARKDOWN, AttachmentExportFormat.PDF)
    async_task = execute_log_analysis

    def prepare(
        self,
        *,
        user: str,
        source_message: Message,
        input_data: AIAnalysisInputSchema,
    ) -> AttachmentPreparation[AIAnalysisContextSchema]:
        """解析 LOG_SEARCH 类型化快照，并固化本次实际分析指令。"""

        self._validate_source(user=user, source_message=source_message)
        log_input = parse_snapshot(
            LogSearchInputSchema,
            source_message.input_data,
            field_name="source_message.input_data",
            error_type=AttachmentSnapshotValidationError,
        )
        log_context = parse_snapshot(
            LogSearchContextSchema,
            source_message.context_data,
            field_name="source_message.context_data",
            error_type=AttachmentSnapshotValidationError,
        )
        log_output = parse_snapshot(
            LogSearchOutputSchema,
            source_message.output_data,
            field_name="source_message.output_data",
            error_type=AttachmentSnapshotValidationError,
        )
        if log_context.username != user or log_context.system_id != log_input.condition.scope_id:
            raise InvalidAttachmentSource()
        self._validate_snapshot_consistency(
            log_input=log_input,
            log_context=log_context,
            log_output=log_output,
        )
        # LOG_SEARCH 可承载比 Agent 工具更宽的历史条件；分析创建前必须确认该快照可被工具重放。
        search_condition = parse_snapshot(
            AgentSearchCondition,
            log_input.condition.model_dump(mode="json"),
            field_name="source_message.input_data.condition",
            error_type=UnsupportedLogAnalysisCondition,
        )

        effective_instruction = self._resolve_instruction(input_data)
        return AttachmentPreparation(
            title=DEFAULT_AI_ANALYSIS_TITLE,
            context_data=AIAnalysisContextSchema(
                effective_instruction=effective_instruction,
                search_condition=search_condition,
                query_summary=AIAnalysisQuerySummary(
                    total=log_output.total,
                    took_ms=log_output.query_summary.took_ms,
                    executed_at=log_output.query_summary.executed_at,
                ),
                username=user,
                namespace=log_context.namespace,
                # 当前请求链路尚无可信用户偏好，先固化部署默认值；后续接入用户配置时只改此处。
                timezone=settings.TIME_ZONE,
                language=settings.LANGUAGE_CODE,
            ),
        )

    def edit_output(
        self,
        *,
        attachment: Attachment,
        current_output: AIAnalysisOutputSchema,
        submitted_output: AIAnalysisOutputSchema,
    ) -> AIAnalysisOutputSchema:
        """完整替换已由 output_model 校验的 Markdown，不改变来源与执行快照。"""

        return submitted_output

    def export(
        self,
        *,
        attachment: Attachment,
        output_data: AIAnalysisOutputSchema,
        export_format: AttachmentExportFormat,
    ) -> AttachmentExportResult:
        """复用平台受限 Markdown/PDF 实时导出器。"""

        return MarkdownDocumentExporter(title=attachment.title, markdown=output_data.markdown).export(export_format)

    @staticmethod
    def _validate_source(*, user: str, source_message: Message) -> None:
        """防御性校验来源业务类型与可见边界；Service 仍是公开创建入口的第一道校验。"""

        conversation = source_message.conversation
        if (
            source_message.message_type != MessageType.LOG_SEARCH
            or source_message.status != ExecutionStatus.SUCCESS
            or source_message.created_by != user
            or conversation.created_by != user
            or conversation.is_deleted
        ):
            raise InvalidAttachmentSource()

    @staticmethod
    def _resolve_instruction(input_data: AIAnalysisInputSchema) -> str:
        if input_data.analysis_mode == AnalysisMode.CUSTOM:
            return input_data.instruction or ""
        instruction = GlobalMetaConfig.get(config_key=AI_ASSISTANT_LOG_ANALYSIS_PROMPT_KEY)
        if not isinstance(instruction, str) or not instruction.strip():
            raise InvalidAttachmentPreparation()
        return instruction.strip()

    @staticmethod
    def _validate_snapshot_consistency(
        *,
        log_input: LogSearchInputSchema,
        log_context: LogSearchContextSchema,
        log_output: LogSearchOutputSchema,
    ) -> None:
        """校验三份快照来自同一次检索，避免拼接不相干的分析范围。

        日志检索会合并可归一的重复条件，因此输出条件数只校验合法区间，
        不依赖 ``LogSearchService`` 的私有归一实现。
        """

        condition = log_input.condition
        summary = log_output.query_summary
        expected_time_range = {
            "start_time": condition.start_time,
            "end_time": condition.end_time,
        }
        is_consistent = (
            summary.scope_type == condition.scope_type
            and summary.scope_id == condition.scope_id == log_context.system_id
            and summary.time_range == expected_time_range
            and summary.source == log_context.source
            and 0 <= summary.condition_count <= len(condition.conditions)
        )
        if not is_consistent:
            raise AttachmentSnapshotValidationError(data={"field_name": "source_message", "errors": []})


attachment_handler_registry.register(AIAnalysisHandler())
