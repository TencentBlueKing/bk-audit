"""AI 分析 Markdown/PDF 实时导出器，严格限制 PDF 渲染可读取的资源。"""

import base64
import html
import io
import logging
import os
import re

from django.conf import settings
from django.utils import timezone

from core.exporter.markdown import render_ai_markdown
from services.web.ai_assistant.constants import AttachmentExportFormat
from services.web.ai_assistant.exceptions import (
    AttachmentContentTooLarge,
    AttachmentExportFailed,
    AttachmentExportNotSupported,
)
from services.web.ai_assistant.handlers import AttachmentExportResult

logger = logging.getLogger(__name__)

_CONTROL_OR_PATH_CHARACTERS = re.compile(r"[\x00-\x1f\x7f/\\]+")
_DATA_IMAGE_PATTERN = re.compile(r"^data:image/(?:png|jpeg|gif);base64,([A-Za-z0-9+/]*={0,2})$")


def validate_markdown_size(markdown: str) -> None:
    """按 UTF-8 编码字节数限制 AI Markdown，供生成、编辑和导出共同复用。"""

    if len(markdown.encode("utf-8")) > settings.AI_ASSISTANT_ATTACHMENT_MARKDOWN_MAX_BYTES:
        raise AttachmentContentTooLarge()


class MarkdownDocumentExporter:
    """固定标题和 Markdown 的即时导出器，不写文件、不保存附件且不创建异步任务。"""

    _BLOCKED_PDF_RESOURCE_URI = "data:image/gif;base64,R0lGODlhAQABAAAAACw="
    _PDF_HTML_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
@font-face {{ font-family: 'NotoSansSC'; src: url('{font_path}'); }}
body {{ font-family: 'NotoSansSC'; font-size: 12px; line-height: 1.8; color: #333; }}
h1 {{ font-size: 20px; text-align: center; }}
h2 {{ font-size: 16px; }} h3 {{ font-size: 14px; }}
p, li, td, th, h1, h2, h3, blockquote, code, pre {{ -pdf-word-wrap: CJK; word-break: break-word; }}
table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
th, td {{ border: 1px solid #ccc; padding: 6px; vertical-align: top; }}
pre {{ white-space: pre-wrap; }}
</style></head><body><h1>{title}</h1>{content}</body></html>"""

    def __init__(self, *, title: str, markdown: str):
        self.title = title
        self.markdown = markdown

    def export(self, export_format: AttachmentExportFormat) -> AttachmentExportResult:
        """校验内容后生成指定格式；格式不在白名单时稳定拒绝。"""

        validate_markdown_size(self.markdown)
        if export_format == AttachmentExportFormat.MARKDOWN:
            return self._export_markdown()
        if export_format == AttachmentExportFormat.PDF:
            return self._export_pdf()
        raise AttachmentExportNotSupported()

    def _export_markdown(self) -> AttachmentExportResult:
        return AttachmentExportResult(
            filename=self._build_filename(".md"),
            content_type="text/markdown; charset=utf-8",
            content=self.markdown.encode("utf-8"),
        )

    def _export_pdf(self) -> AttachmentExportResult:
        font_path = settings.PDF_CJK_FONT_PATH
        try:
            if not os.path.isfile(font_path):
                raise FileNotFoundError("PDF CJK 字体文件不存在")
            html_document = self._PDF_HTML_TEMPLATE.format(
                font_path=html.escape(font_path, quote=True),
                title=html.escape(self._normalized_title()),
                content=render_ai_markdown(self.markdown),
            )
            return AttachmentExportResult(
                filename=self._build_filename(".pdf"),
                content_type="application/pdf",
                content=self._create_pdf(html_document),
            )
        except Exception as error:
            # 日志只含受控元信息，严禁记录可能携带敏感内容的 Markdown 或 HTML。
            logger.exception("AI 助手附件 PDF 导出失败: title=%s, error=%s", self._normalized_title(), type(error).__name__)
            raise AttachmentExportFailed() from error

    def _create_pdf(self, html_document: str) -> bytes:
        """调用 xhtml2pdf 并通过受限回调阻断网络和任意本地资源读取。"""

        from xhtml2pdf import pisa

        buffer = io.BytesIO()
        status = pisa.CreatePDF(
            html_document,
            dest=buffer,
            encoding="utf-8",
            link_callback=self._resolve_pdf_resource,
        )
        if status.err:
            raise RuntimeError("xhtml2pdf 渲染失败")
        return buffer.getvalue()

    @classmethod
    def _resolve_pdf_resource(cls, uri: str, rel: str | None) -> str:
        """仅放行配置字体或经过 Base64 校验的 PNG/JPEG/GIF data URI，其他资源替换占位图。"""

        if uri and os.path.realpath(uri) == os.path.realpath(settings.PDF_CJK_FONT_PATH):
            return (
                settings.PDF_CJK_FONT_PATH
                if os.path.isfile(settings.PDF_CJK_FONT_PATH)
                else cls._BLOCKED_PDF_RESOURCE_URI
            )
        match = _DATA_IMAGE_PATTERN.fullmatch(uri or "")
        if not match:
            return cls._BLOCKED_PDF_RESOURCE_URI
        try:
            base64.b64decode(match.group(1), validate=True)
        except ValueError:
            return cls._BLOCKED_PDF_RESOURCE_URI
        return uri

    def _build_filename(self, extension: str) -> str:
        timestamp = timezone.localtime().strftime("%Y%m%d%H%M%S")
        suffix = f"_{timestamp}{extension}"
        return f"{self._normalized_title()[: 200 - len(suffix)]}{suffix}"

    def _normalized_title(self) -> str:
        normalized = _CONTROL_OR_PATH_CHARACTERS.sub("", self.title).strip()
        return normalized or "AI分析报告"
