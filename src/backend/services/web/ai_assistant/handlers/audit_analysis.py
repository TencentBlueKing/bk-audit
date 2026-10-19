"""日志分析报告 Attachment Handler。

Handler 只负责校验 LOG_SEARCH 来源、构建最小快照与声明编辑/导出能力；
异步状态、流切换、任务重试和终态回写仍由附件平台统一处理。
"""

from django.conf import settings

from apps.meta.models import GlobalMetaConfig
from core.exporter.report import resolve_content_format
from services.web.ai.prompts.log_analysis import SYSTEM_PROMPT
from services.web.ai_assistant.constants import (
    AI_ASSISTANT_LOG_ANALYSIS_PROMPT_KEY,
    DEFAULT_AI_ANALYSIS_TITLE,
    AnalysisMode,
    AttachmentExportFormat,
    AttachmentType,
    ExecutionMode,
)
from services.web.ai_assistant.exceptions import (
    InvalidAttachmentPreparation,
    UnsupportedLogAnalysisCondition,
)
from services.web.ai_assistant.exporters import MarkdownDocumentExporter
from services.web.ai_assistant.handlers.attachment import (
    AttachmentExportResult,
    AttachmentPreparation,
    AttachmentTypeHandler,
)
from services.web.ai_assistant.handlers.log_search_source import (
    prepare_log_attachment,
    validate_log_search_consistency,
    validate_log_search_source,
)
from services.web.ai_assistant.handlers.registry import attachment_handler_registry
from services.web.ai_assistant.models import Attachment, Message
from services.web.ai_assistant.schemas.audit_analysis import (
    AIAnalysisContextSchema,
    AIAnalysisInputSchema,
    AIAnalysisOutputSchema,
    AIAnalysisQuerySummary,
)
from services.web.ai_assistant.tasks.audit_analysis import execute_log_analysis


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

        input_data, log_context, log_output, summary_matches = prepare_log_attachment(
            user=user,
            source_message=source_message,
            input_data=input_data,
            error_type=UnsupportedLogAnalysisCondition,
        )
        search_condition = input_data.condition

        effective_instruction = self._resolve_instruction(input_data)
        return AttachmentPreparation(
            title=DEFAULT_AI_ANALYSIS_TITLE,
            input_data=input_data,
            context_data=AIAnalysisContextSchema(
                system_prompt=SYSTEM_PROMPT,
                effective_instruction=effective_instruction,
                search_condition=search_condition,
                query_summary=AIAnalysisQuerySummary(
                    total=log_output.total,
                    took_ms=log_output.query_summary.took_ms,
                    executed_at=log_output.query_summary.executed_at,
                )
                if summary_matches
                else None,
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
        """替换正文并记录格式；旧客户端省略格式时按本次正文重新识别。"""

        return submitted_output.model_copy(
            update={
                "content_format": resolve_content_format(submitted_output.markdown, submitted_output.content_format)
            }
        )

    def export(
        self,
        *,
        attachment: Attachment,
        output_data: AIAnalysisOutputSchema,
        export_format: AttachmentExportFormat,
    ) -> AttachmentExportResult:
        """复用平台受限 Markdown/PDF 实时导出器。"""

        return MarkdownDocumentExporter(
            title=attachment.title, markdown=output_data.markdown, content_format=output_data.content_format
        ).export(export_format)

    _validate_source = staticmethod(validate_log_search_source)

    @staticmethod
    def _resolve_instruction(input_data: AIAnalysisInputSchema) -> str:
        if input_data.analysis_mode == AnalysisMode.CUSTOM:
            return input_data.instruction or ""
        instruction = GlobalMetaConfig.get(config_key=AI_ASSISTANT_LOG_ANALYSIS_PROMPT_KEY)
        if not isinstance(instruction, str) or not instruction.strip():
            raise InvalidAttachmentPreparation()
        return instruction.strip()

    _validate_snapshot_consistency = staticmethod(validate_log_search_consistency)


attachment_handler_registry.register(AIAnalysisHandler())
