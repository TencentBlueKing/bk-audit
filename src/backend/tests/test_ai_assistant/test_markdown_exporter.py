from unittest import mock

from django.conf import settings
from django.test import TestCase, override_settings

from core.exporter.markdown import render_ai_markdown
from services.web.ai_assistant.constants import AttachmentExportFormat
from services.web.ai_assistant.exceptions import (
    AttachmentContentTooLarge,
    AttachmentExportFailed,
)
from services.web.ai_assistant.exporters.markdown import MarkdownDocumentExporter


class MarkdownDocumentExporterTest(TestCase):
    def test_markdown_export_returns_exact_utf8_content_and_safe_filename(self):
        exporter = MarkdownDocumentExporter(title=" / AI\\分析\x00 ", markdown="中文内容\n")

        result = exporter.export(AttachmentExportFormat.MARKDOWN)

        self.assertEqual(result.content, "中文内容\n".encode("utf-8"))
        self.assertEqual(result.content_type, "text/markdown; charset=utf-8")
        self.assertTrue(result.filename.startswith("AI分析_"))
        self.assertTrue(result.filename.endswith(".md"))
        self.assertNotIn("/", result.filename)
        self.assertNotIn("\\", result.filename)
        self.assertNotIn("\x00", result.filename)

    def test_pdf_export_creates_real_pdf_with_cjk_text(self):
        exporter = MarkdownDocumentExporter(title="AI 分析", markdown="# 中文标题\n\n这是正文。")

        result = exporter.export(AttachmentExportFormat.PDF)

        self.assertEqual(result.content_type, "application/pdf")
        self.assertTrue(result.filename.endswith(".pdf"))
        self.assertTrue(result.content.startswith(b"%PDF"))

    @override_settings(AI_ASSISTANT_ATTACHMENT_MARKDOWN_MAX_BYTES=5)
    def test_export_rejects_content_over_utf8_byte_limit(self):
        exporter = MarkdownDocumentExporter(title="AI 分析", markdown="你好")

        with self.assertRaises(AttachmentContentTooLarge):
            exporter.export(AttachmentExportFormat.MARKDOWN)

    def test_markdown_renderer_escapes_raw_html_and_supports_tables(self):
        html = render_ai_markdown("<script>alert(1)</script>\n\n| 名称 | 值 |\n| --- | --- |\n| A | B |")

        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)
        self.assertIn("<table>", html)

    def test_pdf_resource_allows_configured_font_and_safe_data_images(self):
        exporter = MarkdownDocumentExporter(title="AI 分析", markdown="正文")
        safe_image = "data:image/png;base64,iVBORw0KGgo="

        self.assertEqual(exporter._resolve_pdf_resource(settings.PDF_CJK_FONT_PATH, None), settings.PDF_CJK_FONT_PATH)
        self.assertEqual(exporter._resolve_pdf_resource(safe_image, None), safe_image)

    def test_pdf_resource_blocks_http_https_local_file_svg_and_invalid_data(self):
        exporter = MarkdownDocumentExporter(title="AI 分析", markdown="正文")

        for resource in (
            "https://example.com/image.png",
            "http://127.0.0.1/image.png",
            "/etc/passwd",
            "file:///etc/passwd",
            "data:image/svg+xml;base64,PHN2Zz4=",
            "data:image/png;base64,not-base64",
        ):
            with self.subTest(resource=resource):
                self.assertEqual(
                    exporter._resolve_pdf_resource(resource, None),
                    exporter._BLOCKED_PDF_RESOURCE_URI,
                )

    def test_pdf_failure_raises_attachment_export_failed_without_html_fallback(self):
        markdown = "私密 Markdown 内容"
        exporter = MarkdownDocumentExporter(title="AI 分析", markdown=markdown)

        with mock.patch("services.web.ai_assistant.exporters.markdown.logger") as logger:
            with mock.patch.object(exporter, "_create_pdf", side_effect=RuntimeError("renderer failed")):
                with self.assertRaises(AttachmentExportFailed):
                    exporter.export(AttachmentExportFormat.PDF)

        self.assertNotIn(markdown, str(logger.exception.call_args))
