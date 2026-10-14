"""受控报告模板的 PDF 排版适配，不修改渲染库的全局实现。

xhtml2pdf 保留 HTML/CSS/图片解析；字符换行复用 ReportLab 的现行算法。
跨页时复用已经切分的行，避免旧段落实现重新换行导致布局失败。
"""

import io
from collections.abc import Callable

from reportlab.lib.units import cm
from reportlab.platypus import Frame
from reportlab.platypus.paragraph import cjkFragSplit
from xhtml2pdf.context import pisaContext
from xhtml2pdf.document import pisaStory
from xhtml2pdf.files import cleanFiles
from xhtml2pdf.reportlab_paragraph import _handleBulletWidth
from xhtml2pdf.xhtml2pdf_reportlab import (
    PmlBaseDoc,
    PmlPageTemplate,
    PmlParagraph,
    PmlParagraphAndImage,
)


class _ReportParagraph(PmlParagraph):
    """保留原段落的样式与绘制，修正字符换行和跨页重复排版。"""

    def breakLinesCJK(self, width):
        """复用现行字符换行；已切页的段落使用原布局，不再次重排。"""
        if getattr(self, "_splitpara", False) and hasattr(self, "blPara"):
            return self.blPara
        widths = width if isinstance(width, (list, tuple)) else [width]
        _handleBulletWidth(self.bulletText, self.style, widths)
        for fragment in self.frags:
            # 新算法使用 us_lines 区分装饰样式，旧绘制器仍读取 underline/strike。
            fragment.us_lines = (getattr(fragment, "underline", False), getattr(fragment, "strike", False))
        auto_leading = getattr(self, "autoLeading", getattr(self.style, "autoLeading", ""))
        return cjkFragSplit(self.frags, widths, auto_leading not in {"", "off"})


def _adapt_paragraph(paragraph: PmlParagraph) -> _ReportParagraph:
    """复制本次解析生成的段落属性，不替换第三方类或影响并发导出。"""
    adapted = _ReportParagraph(None, paragraph.style, frags=paragraph.frags)
    adapted.__dict__.update(paragraph.__dict__)
    return adapted


class _ReportContext(pisaContext):
    """在解析段落（含表格单元格）进入当前文档时使用局部适配。"""

    def addStory(self, data):
        """保留现有图片与表格对象，仅适配其文本段落。"""
        if isinstance(data, PmlParagraph):
            data = _adapt_paragraph(data)
        elif isinstance(data, PmlParagraphAndImage):
            data.P = _adapt_paragraph(data.P)
        super().addStory(data)


def render_report_pdf(document: str, resource_callback: Callable[[str, str | None], str]) -> bytes:
    """将公共报告模板生成 PDF；保留原 1cm 页边距，解析/排版失败由业务层映射。

    仅接收后端的受控模板，不接收任意 @page、脚本或外部样式。
    """
    try:
        context = _ReportContext()
        # 已提供 context 时 pisaStory 不会设置回调，必须显式接入字体/图片资源策略。
        context.pathCallback = resource_callback
        context = pisaStory(document, context=context, encoding="utf-8")
        if context.err:
            raise RuntimeError("xhtml2pdf 解析失败")
        buffer = io.BytesIO()
        pdf = PmlBaseDoc(buffer, pagesize=context.pageSize, allowSplitting=1)
        width, height = context.pageSize
        frame = Frame(
            cm,
            cm,
            width - 2 * cm,
            height - 2 * cm,
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        )
        pdf.addPageTemplates(PmlPageTemplate(id="body", frames=[frame], pagesize=context.pageSize))
        pdf.build(context.story)
        return buffer.getvalue()
    finally:
        cleanFiles()
