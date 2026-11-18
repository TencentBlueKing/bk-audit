import io
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, override_settings
from pypdf import PdfReader

from core.exporter.markdown import render_ai_markdown
from services.web.ai_assistant.constants import AttachmentExportFormat
from services.web.ai_assistant.exceptions import (
    AttachmentContentTooLarge,
    AttachmentExportFailed,
)
from services.web.ai_assistant.exporters.markdown import MarkdownDocumentExporter


class MarkdownDocumentExporterTest(SimpleTestCase):
    @staticmethod
    def _pdf_text(result):
        """读取实际 PDF 的正文，验证缺字和分页时的内容完整性。"""
        return "".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(result.content)).pages)

    def test_legacy_html_pdf_renders_report_instead_of_literal_tags(self):
        report = '<h1>历史报告</h1><p>完整正文</p><table><tr><td>表格内容</td></tr></table>'
        result = MarkdownDocumentExporter(title="报告", markdown=report).export(AttachmentExportFormat.PDF)
        text = self._pdf_text(result)
        self.assertIn("历史报告", text)
        self.assertIn("完整正文", text)
        self.assertIn("表格内容", text)
        self.assertNotIn("<h1>", text)
        self.assertNotIn("<table>", text)

    def test_html_markdown_download_converts_only_the_download(self):
        report = '<h1>历史报告</h1><p><strong>完整正文</strong></p>'
        exporter = MarkdownDocumentExporter(title="报告", markdown=report)
        result = exporter.export(AttachmentExportFormat.MARKDOWN)
        self.assertIn("# 历史报告", result.content.decode())
        self.assertIn("**完整正文**", result.content.decode())
        self.assertEqual(exporter.markdown, report)

    def test_pdf_preserves_chinese_inline_code_and_code_block(self):
        report = '`中文代码字段`\n\n```\n中文代码块字段\n```'
        result = MarkdownDocumentExporter(title="报告", markdown=report).export(AttachmentExportFormat.PDF)
        text = self._pdf_text(result)
        self.assertIn("中文代码字段", text)
        self.assertIn("中文代码块字段", text)

    def test_long_mixed_markdown_pdf_preserves_all_content_across_pages(self):
        report = '# 正文\n\n开始标记 ' + ('中文 `a<b>&c` 后续内容 ' * 650) + ' 结束标记'
        result = MarkdownDocumentExporter(title="报告", markdown=report).export(AttachmentExportFormat.PDF)
        text = ''.join(self._pdf_text(result).split())
        self.assertIn("开始标记", text)
        self.assertIn("结束标记", text)
        self.assertEqual(text.count("a<b>&c"), 650)
        self.assertEqual(text.count("后续内容"), 650)

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
