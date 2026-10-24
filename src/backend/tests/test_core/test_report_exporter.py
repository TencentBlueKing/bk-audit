"""实际报告格式、安全清洗与 PDF 内容回归，不依赖业务私有模板。"""

import io
from unittest import mock

from bs4 import BeautifulSoup
from django.test import SimpleTestCase, override_settings
from pypdf import PdfReader

from core.exporter.report import (
    ReportContentFormat,
    ReportDocumentExporter,
    ReportExportError,
    clean_report_html,
    render_report_html,
    resolve_content_format,
)


class ReportExporterTest(SimpleTestCase):
    def test_pdf_embeds_tencent_regular_and_bold_for_both_content_formats(self):
        cases = [
            (
                '# 章节标题\n\n普通正文\n\n**加粗正文**\n\n*斜体正文*\n\n***加粗斜体***\n\n`中文代码`',
                ReportContentFormat.MARKDOWN,
            ),
            (
                '<h1>章节标题</h1><p>普通正文</p><p><strong>加粗正文</strong></p>'
                '<p><em>斜体正文</em></p><p><strong><em>加粗斜体</em></strong></p><p><code>中文代码</code></p>',
                ReportContentFormat.HTML,
            ),
        ]
        for source, content_format in cases:
            with self.subTest(content_format=content_format):
                result = ReportDocumentExporter(title='报告', content=source, content_format=content_format).export('PDF')
                text_fonts = {}

                def collect_font(text, cm, tm, font, font_size):
                    """读取实际文本使用的嵌入字体，避免仅验证配置路径。"""
                    if text.strip():
                        text_fonts[text.strip()] = str(font['/BaseFont'])

                for page in PdfReader(io.BytesIO(result.content)).pages:
                    page.extract_text(visitor_text=collect_font)
                for text, font_name in [
                    ('章节标题', 'TencentSansW7'),
                    ('加粗正文', 'TencentSansW7'),
                    ('普通正文', 'TencentSansW3'),
                    ('斜体正文', 'TencentSansW3'),
                    ('加粗斜体', 'TencentSansW7'),
                    ('中文代码', 'TencentSansW3'),
                ]:
                    self.assertTrue(text_fonts[text].endswith(font_name), text_fonts[text])

    def test_pdf_build_uses_resource_policy_for_font_and_remote_image(self):
        exporter = ReportDocumentExporter(title='报告', content='<p>正文<img src="https://example.test/image.png"></p>')
        with mock.patch.object(exporter, '_resolve_pdf_resource', wraps=exporter._resolve_pdf_resource) as callback:
            result = exporter.export('PDF')
        self.assertTrue(result.content.startswith(b'%PDF-'))
        uris = [call.args[0] for call in callback.call_args_list]
        self.assertIn('https://example.test/image.png', uris)
        self.assertGreater(len(uris), 1)  # 除图片外，字体也须经过同一个资源策略。

    def test_unbroken_chinese_paragraphs_and_code_wrap_across_pages(self):
        body = '中文长文本' * 1500
        cases = [
            (body, ReportContentFormat.MARKDOWN),
            (f'<p>{body}</p>', ReportContentFormat.HTML),
            (f'```\n{body}\n结束代码\n```', ReportContentFormat.MARKDOWN),
            (f'<pre>{body}\n结束代码</pre>', ReportContentFormat.HTML),
            (f'- {body}', ReportContentFormat.MARKDOWN),
            (f'<ul><li>{body}</li></ul>', ReportContentFormat.HTML),
        ]
        for source, content_format in cases:
            with self.subTest(source_type=source[:5], content_format=content_format):
                result = ReportDocumentExporter(title='报告', content=source, content_format=content_format).export('PDF')
                pdf = PdfReader(io.BytesIO(result.content))
                # 不能只检查可提取文本：横向溢出的 PDF 仍能提取出全部文字。
                self.assertGreater(len(pdf.pages), 1)
                text = ''.join(''.join(page.extract_text().split()) for page in pdf.pages)
                self.assertEqual(text.count('中文长文本'), 1500)

    def test_cleaning_allows_data_images_but_not_data_links(self):
        source = '<a href="data:text/html,active-content">链接</a>' '<img src="data:image/png;base64,aGVsbG8=" alt="图片">'
        clean = clean_report_html(source)
        soup = BeautifulSoup(clean, 'html.parser')
        self.assertNotIn('href', soup.a.attrs)
        self.assertEqual(soup.img['src'], 'data:image/png;base64,aGVsbG8=')

    def test_format_marker_and_legacy_detection(self):
        cases = [
            ('<p>HTML报告</p>', None, ReportContentFormat.HTML),
            ('<!DOCTYPE html><html><body><h1>报告</h1></body></html>', None, ReportContentFormat.HTML),
            (' \n<!doctype html>\n<p>HTML报告</p>', None, ReportContentFormat.HTML),
            ('<!DOCTYPE html>', None, ReportContentFormat.MARKDOWN),
            ('<!DOCTYPE html><p>段落</p>\n# 另一标题', None, ReportContentFormat.MARKDOWN),
            ('```html\n<!DOCTYPE html><p>代码</p>\n```', None, ReportContentFormat.MARKDOWN),
            ('<!DOCTYPE html><p>HTML样例</p>', ReportContentFormat.MARKDOWN, ReportContentFormat.MARKDOWN),
            ('<p>HTML样例</p>', ReportContentFormat.MARKDOWN, ReportContentFormat.MARKDOWN),
            ('# 标题\n\n<div>混合标签</div>', None, ReportContentFormat.MARKDOWN),
            ('```html\n<p>代码</p>\n```', None, ReportContentFormat.MARKDOWN),
            ('<span>行内样例</span>普通文字', None, ReportContentFormat.MARKDOWN),
            ('<p>段落</p>\n# 另一标题', None, ReportContentFormat.MARKDOWN),
        ]
        for text, marker, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(resolve_content_format(text, marker), expected)

    def test_doctype_html_exports_content_without_source_tags(self):
        """未声明格式的完整 HTML 应转换正文，不能把标签打印到 MD/PDF。"""
        source = '<!DOCTYPE html><html><body><h1>审计报告</h1><p>完整正文</p></body></html>'
        exporter = ReportDocumentExporter(title='报告', content=source)
        markdown = exporter.export('MARKDOWN').content.decode()
        self.assertEqual(markdown.strip(), '# 审计报告\n\n完整正文')
        pdf = PdfReader(io.BytesIO(exporter.export('PDF').content))
        text = ''.join(page.extract_text() for page in pdf.pages)
        self.assertIn('审计报告', text)
        self.assertIn('完整正文', text)
        self.assertNotIn('<', text)

    def test_html_cleaning_preserves_report_styles_and_rejects_executable_content(self):
        source = (
            '<p class="ql-align-center" style="color:red;background-color:yellow;'
            'background-image:url(https://example.com);font-family:Unexpected" onclick="bad()">'
            '正文<strong>强调</strong></p><script>danger()</script>'
            '<table><tr><td colspan="2">单元格</td></tr></table><a href="javascript:bad()">链接</a>'
        )
        clean = clean_report_html(source)
        parsed = BeautifulSoup(clean, 'html.parser')
        self.assertIn('text-align:center', parsed.p['style'].replace(' ', ''))
        self.assertIn('color:red', parsed.p['style'].replace(' ', ''))
        self.assertEqual(parsed.td['colspan'], '2')
        self.assertEqual(parsed.strong.text, '强调')
        self.assertNotIn('onclick', clean)
        self.assertNotIn('danger()', clean)
        self.assertNotIn('javascript:', clean)
        self.assertNotIn('background-image', clean)
        self.assertNotIn('Unexpected', clean)

    def test_quill_mixed_bullet_ordered_lists_preserve_their_kinds(self):
        clean = clean_report_html(
            '<ol><li data-list="bullet">无序</li><li data-list="ordered">有序</li><li data-list="bullet">第二无序</li></ol>'
        )
        parsed = BeautifulSoup(clean, 'html.parser')
        self.assertEqual([x.name for x in parsed.find_all(['ol', 'ul'])], ['ul', 'ol', 'ul'])
        self.assertEqual([x.get_text() for x in parsed.find_all('li')], ['无序', '有序', '第二无序'])

    def test_quill_code_block_keeps_line_breaks(self):
        clean = clean_report_html(
            '<div class="ql-code-block-container"><div class="ql-code-block">第一行 &lt;x&gt;</div>'
            '<div class="ql-code-block">第二行</div></div>'
        )
        self.assertEqual(BeautifulSoup(clean, 'html.parser').pre.text, '第一行 <x>\n第二行')

    def test_pdf_keeps_code_block_lines_in_both_formats(self):
        cases = [
            ('<pre>第一行代码\n第二行代码</pre>', ReportContentFormat.HTML),
            ('```\n第一行代码\n第二行代码\n```', ReportContentFormat.MARKDOWN),
        ]
        for source, content_format in cases:
            with self.subTest(content_format=content_format):
                result = ReportDocumentExporter(title='报告', content=source, content_format=content_format).export('PDF')
                text = ''.join(page.extract_text() for page in PdfReader(io.BytesIO(result.content)).pages)
                self.assertIn('第一行代码\n第二行代码', text)

    def test_explicit_markdown_still_escapes_raw_html(self):
        content = render_report_html('<p>标签示例</p>', ReportContentFormat.MARKDOWN)
        self.assertIn('&lt;p&gt;', content)
        self.assertNotIn('<p>标签示例</p>', content)

    def test_html_pdf_preserves_table_code_styles_and_text(self):
        source = (
            '<h1>历史报告</h1><p style="text-align:center;color:red">居中正文</p><pre>中文代码</pre>'
            '<table><tr><th>列名</th></tr><tr><td>数据完整</td></tr></table>'
        )
        result = ReportDocumentExporter(title='报告', content=source).export('PDF')
        text = ''.join(p.extract_text() for p in PdfReader(io.BytesIO(result.content)).pages)
        for value in ['历史报告', '居中正文', '中文代码', '列名', '数据完整']:
            self.assertIn(value, text)
        self.assertNotIn('<h1>', text)

    def test_long_chinese_table_cells_and_paragraphs_do_not_lose_text(self):
        source = (
            '开始标记\n\n'
            + ('中文正文' * 2000)
            + '\n\n| 字段 | 值 |\n| --- | --- |\n'
            + ''.join(f'| 第{i}行 | 中文单元格内容{i} |\n' for i in range(90))
            + '\n结束标记'
        )
        result = ReportDocumentExporter(title='报告', content=source).export('PDF')
        pdf = PdfReader(io.BytesIO(result.content))
        text = ''.join(''.join(page.extract_text().split()) for page in pdf.pages)
        self.assertGreater(len(pdf.pages), 1)
        self.assertIn('开始标记', text)
        self.assertIn('结束标记', text)
        self.assertEqual(text.count('中文正文'), 2000)
        for i in range(90):
            self.assertIn(f'中文单元格内容{i}', text)

    def test_resource_policy_blocks_local_files_and_preserves_risk_remote_images(self):
        ai = ReportDocumentExporter(title='报告', content='正文')
        risk = ReportDocumentExporter(title='报告', content='正文', allow_remote_images=True)
        for uri in [
            '/etc/passwd',
            'file:///etc/passwd',
            'C:\\Windows\\font.ttf',
            'data:image/svg+xml;base64,AAAA',
            'https://example.com/image.png',
        ]:
            self.assertNotEqual(ai._resolve_pdf_resource(uri, None), uri)
        self.assertEqual(
            risk._resolve_pdf_resource('https://example.com/image.png', None), 'https://example.com/image.png'
        )
        self.assertNotEqual(risk._resolve_pdf_resource('/etc/passwd', None), '/etc/passwd')

    @override_settings(PDF_CJK_FONT_PATH='/missing/report-font.ttf')
    def test_missing_font_is_a_failure_not_html_fallback(self):
        with self.assertRaises(ReportExportError):
            ReportDocumentExporter(title='报告', content='正文').export('PDF')
