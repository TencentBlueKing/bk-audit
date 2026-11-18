"""AI 附件导出适配：复用公共报告导出，只保留附件容量限制和异常映射。"""

import logging

from django.conf import settings

from core.exporter.report import (
    ReportContentFormat,
    ReportDocumentExporter,
    ReportExportError,
)
from services.web.ai_assistant.constants import AttachmentExportFormat
from services.web.ai_assistant.exceptions import (
    AttachmentContentTooLarge,
    AttachmentExportFailed,
    AttachmentExportNotSupported,
)
from services.web.ai_assistant.handlers import AttachmentExportResult

logger = logging.getLogger(__name__)


def validate_markdown_size(markdown: str) -> None:
    """按 UTF-8 字节限制报告正文，供生成、编辑和导出复用。"""
    if len(markdown.encode("utf-8")) > settings.AI_ASSISTANT_ATTACHMENT_MARKDOWN_MAX_BYTES:
        raise AttachmentContentTooLarge()


class MarkdownDocumentExporter(ReportDocumentExporter):
    """保留原调用入口与 markdown 参数，支持 HTML 和历史无格式报告。"""

    def __init__(self, *, title: str, markdown: str, content_format: ReportContentFormat | str | None = None):
        """兼容原参数名，将实际正文交给公共导出器识别或按标识渲染。"""
        self.markdown = markdown
        super().__init__(title=title, content=markdown, content_format=content_format, include_title=True)

    def export(self, export_format: AttachmentExportFormat) -> AttachmentExportResult:
        """映射公共下载结果与异常，PDF 失败仍使用附件平台错误码。"""
        validate_markdown_size(self.markdown)
        if export_format not in {AttachmentExportFormat.MARKDOWN, AttachmentExportFormat.PDF}:
            raise AttachmentExportNotSupported()
        try:
            result = super().export(export_format)
        except ReportExportError as error:
            logger.exception("AI 助手附件 PDF 导出失败: error=%s", type(error.__cause__).__name__)
            raise AttachmentExportFailed() from error
        return AttachmentExportResult(
            filename=result.filename, content_type=result.content_type, content=result.content
        )
