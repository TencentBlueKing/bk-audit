"""风险报告与审计分析共用的正文渲染、Markdown/PDF 导出。

格式标识优先，旧正文仅在完整块级 HTML 时按富文本处理；混合 Markdown 仍走安全渲染。
HTML 的清洗和编辑器样式映射集中在此处，不改写保存的正文。
"""

import base64
import html
import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Doctype, Tag
from django.conf import settings
from django.db.models import TextChoices
from django.utils import timezone
from markdownify import markdownify

from core.exporter.markdown import render_ai_markdown
from core.sanitiers import Nh3Sanitizer


class ReportContentFormat(TextChoices):
    """报告正文格式；缺少标识的旧记录由读取端解析。"""

    MARKDOWN = "MARKDOWN", "Markdown"
    HTML = "HTML", "HTML"


_HTML_ROOT_TAGS = {
    "html",
    "body",
    "section",
    "article",
    "div",
    "p",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "table",
    "ul",
    "ol",
    "blockquote",
    "pre",
}
_REPORT_TAGS = _HTML_ROOT_TAGS | {
    "strong",
    "b",
    "em",
    "i",
    "u",
    "s",
    "del",
    "span",
    "br",
    "hr",
    "a",
    "code",
    "li",
    "thead",
    "tbody",
    "tfoot",
    "tr",
    "th",
    "td",
    "img",
    "sup",
    "sub",
}
_REPORT_STYLES = {
    "color",
    "background-color",
    "text-align",
    "text-decoration",
    "font-size",
    "font-weight",
    "font-style",
    "padding-left",
}


def _filter_report_attribute(tag: str, attribute: str, value: str) -> str | None:
    """data URI 仅用于图片，不让正文链接成为可执行下载地址。"""
    if attribute == "href" and value.lstrip().lower().startswith("data:"):
        return None
    return value


_REPORT_SANITIZER = Nh3Sanitizer(
    {
        "tags": _REPORT_TAGS,
        "attributes": {
            "*": {"style"},
            "a": {"href", "title"},
            "img": {"src", "alt", "width", "height"},
            "td": {"colspan", "rowspan"},
            "th": {"colspan", "rowspan"},
        },
        "url_schemes": {"http", "https", "mailto", "data"},
        "attribute_filter": _filter_report_attribute,
        "clean_content_tags": {"script", "style", "iframe", "object"},
        "filter_style_properties": _REPORT_STYLES,
        "strip_comments": True,
    }
)
_DATA_IMAGE_PATTERN = re.compile(r"^data:image/(?:png|jpeg|gif);base64,([A-Za-z0-9+/]*={0,2})$")
_CONTROL_OR_PATH = re.compile(r"[\x00-\x1f\x7f/\\]+")


def resolve_content_format(
    content: str, content_format: ReportContentFormat | str | None = None
) -> ReportContentFormat:
    """声明格式优先；自动识别忽略 DOCTYPE，正文仍须全部由 HTML 块组成。"""
    if content_format:
        return ReportContentFormat(content_format)
    if not content.lstrip().startswith("<"):
        return ReportContentFormat.MARKDOWN
    nodes = [
        node
        for node in BeautifulSoup(content, "html.parser").contents
        if not isinstance(node, Doctype) and str(node).strip()
    ]
    if nodes and all(isinstance(node, Tag) and node.name in _HTML_ROOT_TAGS for node in nodes):
        return ReportContentFormat.HTML
    return ReportContentFormat.MARKDOWN


def clean_report_html(content: str) -> str:
    """将 Quill 的样式/列表/代码转换为报告 HTML，并用报告专用白名单清洗。"""
    soup = BeautifulSoup(content, "html.parser")
    for node in soup.find_all(True):
        styles = [node.get("style", "")]
        for name in node.get("class", []):
            if name in {"ql-align-center", "ql-align-right", "ql-align-justify"}:
                styles.append(f"text-align:{name.removeprefix('ql-align-')}")
            elif name in {"ql-size-small", "ql-size-large", "ql-size-huge"}:
                styles.append(
                    f"font-size:{ {'ql-size-small':'10px','ql-size-large':'18px','ql-size-huge':'24px'}[name] }"
                )
            elif re.fullmatch(r"ql-indent-[1-8]", name):
                styles.append(f"padding-left:{int(name[-1]) * 24}px")
        if any(styles):
            node["style"] = ";".join(filter(None, styles))
    # Quill 2 将无序列表也保存在 ol 中，data-list 才是用户选择的列表类型。
    for ordered in list(soup.find_all("ol")):
        children = ordered.find_all("li", recursive=False)
        if children and any(child.has_attr("data-list") for child in children):
            groups = []
            for child in children:
                kind = "ul" if child.get("data-list") == "bullet" else "ol"
                if not groups or groups[-1].name != kind:
                    groups.append(soup.new_tag(kind))
                groups[-1].append(child.extract())
            ordered.replace_with(*groups)
    for code in list(soup.select(".ql-code-block-container")):
        lines = code.select(".ql-code-block")
        if lines:
            pre = soup.new_tag("pre")
            pre.string = "\n".join(line.get_text() for line in lines)
            code.replace_with(pre)
    return _REPORT_SANITIZER.sanitize(str(soup))


def render_report_html(content: str, content_format: ReportContentFormat | str | None = None) -> str:
    """把两类正文收敛为导出 HTML；Markdown 仍转义原始 HTML，HTML 单独清洗。"""
    if resolve_content_format(content, content_format) == ReportContentFormat.HTML:
        return clean_report_html(content)
    return render_ai_markdown(content)


@dataclass(frozen=True)
class ReportExportResult:
    """与 Web 框架无关的报告下载结果，由业务层构造响应。"""

    filename: str
    content_type: str
    content: bytes


class ReportExportError(RuntimeError):
    """报告 PDF 渲染失败；业务层负责映射自己的错误码。"""


class ReportDocumentExporter:
    """统一字体、段落、表格和资源策略的报告导出器，不写文件或改正文。"""

    _BLOCKED_PDF_RESOURCE_URI = "data:image/gif;base64,R0lGODlhAQABAAAAACw="
    _PDF_HTML_TEMPLATE = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
@font-face {{ font-family: 'ReportCJK'; src: url('{font_path}'); }}
/* 显式登记斜体的同字重字体，避免后注册的粗体覆盖渲染库回退映射。 */
@font-face {{ font-family: 'ReportCJK'; font-style: italic; src: url('{font_path}'); }}
{bold_font}
body {{ font-family: 'ReportCJK'; font-size: 12px; line-height: 1.8; color: #333; -pdf-word-wrap: CJK; }}
h1 {{ font-size: 20px; }} h2 {{ font-size: 16px; }} h3 {{ font-size: 14px; }}
p,li,td,th,h1,h2,h3,blockquote,code,pre {{ word-wrap: break-word; }}
code,pre {{ font-family: 'ReportCJK'; }}
table {{ width: 100%; border-collapse: collapse; table-layout: fixed; margin: 10px 0; }}
th,td {{ border: 1px solid #ccc; padding: 6px; vertical-align: top; }}
th {{ background-color: #f0f0f0; }}
/* pre 保留代码的硬换行，字符换行由公共 PDF 适配处理。 */
pre {{ white-space: pre; }}
</style></head><body>{content}</body></html>"""

    def __init__(
        self,
        *,
        title: str,
        content: str,
        content_format: ReportContentFormat | str | None = None,
        include_title: bool = False,
        allow_remote_images: bool = False,
    ):
        """固化正文与格式；标题拼接和远程图片仅按业务原有策略开启。"""
        self.title = title
        self.content = content
        self.content_format = resolve_content_format(content, content_format)
        self.include_title = include_title
        self.allow_remote_images = allow_remote_images

    def export(self, export_format: str) -> ReportExportResult:
        """生成 Markdown/PDF；HTML 仅在 Markdown 下载时转换，失败不回退成 HTML。"""
        export_format = export_format.upper()
        if export_format == "MARKDOWN":
            content = self.content
            if self.content_format == ReportContentFormat.HTML:
                content = markdownify(clean_report_html(content), heading_style="ATX")
            return ReportExportResult(
                self._build_filename(".md"), "text/markdown; charset=utf-8", content.encode("utf-8")
            )
        if export_format != "PDF":
            raise ValueError("不支持的报告导出格式")
        try:
            if not os.path.isfile(settings.PDF_CJK_FONT_PATH):
                raise FileNotFoundError("PDF 中文字体文件不存在")
            content = render_report_html(self.content, self.content_format)
            if self.include_title:
                content = f"<h1>{html.escape(self._normalized_title())}</h1>{content}"
            bold_path = settings.PDF_CJK_BOLD_FONT_PATH
            bold_font = ""
            if bold_path:
                if not os.path.isfile(bold_path):
                    raise FileNotFoundError("PDF 粗体字体文件不存在")
                escaped_bold_path = html.escape(bold_path, quote=True)
                bold_font = (
                    "@font-face { font-family: 'ReportCJK'; font-weight: bold; src: url('%s'); }"
                    "@font-face { font-family: 'ReportCJK'; font-weight: bold; font-style: italic; src: url('%s'); }"
                ) % (escaped_bold_path, escaped_bold_path)
            document = self._PDF_HTML_TEMPLATE.format(
                font_path=html.escape(settings.PDF_CJK_FONT_PATH, quote=True), bold_font=bold_font, content=content
            )
            return ReportExportResult(self._build_filename(".pdf"), "application/pdf", self._create_pdf(document))
        except Exception as error:
            raise ReportExportError("报告 PDF 导出失败") from error

    def _create_pdf(self, html_document: str) -> bytes:
        """按需加载 PDF 排版依赖，普通接口和 Markdown 下载不初始化渲染库。"""
        from core.exporter.pdf import render_report_pdf

        return render_report_pdf(html_document, self._resolve_pdf_resource)

    def _resolve_pdf_resource(self, uri: str, rel: str | None) -> str:
        """只读配置字体和有效内嵌图片；风险报告显式保留既有远程图片能力。"""
        uri = uri or ""
        font_paths = [settings.PDF_CJK_FONT_PATH, settings.PDF_CJK_BOLD_FONT_PATH]
        for path in filter(None, font_paths):
            if os.path.realpath(uri) == os.path.realpath(path):
                return path if os.path.isfile(path) else self._BLOCKED_PDF_RESOURCE_URI
        if self.allow_remote_images and urlparse(uri).scheme in {"http", "https"}:
            return uri
        match = _DATA_IMAGE_PATTERN.fullmatch(uri)
        if match:
            try:
                base64.b64decode(match[1], validate=True)
                return uri
            except ValueError:
                pass
        return self._BLOCKED_PDF_RESOURCE_URI

    def _normalized_title(self) -> str:
        return _CONTROL_OR_PATH.sub("", self.title).strip() or "分析报告"

    def _build_filename(self, extension: str) -> str:
        suffix = f"_{timezone.localtime().strftime('%Y%m%d%H%M%S')}{extension}"
        return self._normalized_title()[: 200 - len(suffix)] + suffix
