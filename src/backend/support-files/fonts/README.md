# 报告 PDF 字体

风险报告和 AI 日志分析报告共用以下字体：

| 文件 | 用途 |
| --- | --- |
| `TencentSans-W3.ttf` | 正文、代码，W3 字重 300 |
| `TencentSans-W7.ttf` | 标题、加粗文本、表头，W7 字重 700 |

两份字体仅规范文件名，保留原始字形、字体名称和元数据。
通过 `BKAPP_PDF_CJK_FONT_PATH`、`BKAPP_PDF_CJK_BOLD_FONT_PATH` 可覆盖路径；
粗体路径显式设为空时使用普通字体。

旧 `NotoSansSC-Regular.ttf` 及其许可证保留，用于兼容已有路径配置。
