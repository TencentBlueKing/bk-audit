# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import abc
import json
import logging
import os
from urllib.parse import quote

from blueapps.utils.request_provider import get_request_username
from celery.result import AsyncResult
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy
from rest_framework import serializers as drf_serializers

from apps.audit.resources import AuditMixinResource
from services.web.risk.constants import AnalyseReportStatus
from services.web.risk.models import (
    AnalyseReport,
    AnalyseReportRisk,
    AnalyseReportScenario,
    Risk,
)
from services.web.risk.serializers import (
    DeleteAnalyseReportRequestSerializer,
    ExportAnalyseReportRequestSerializer,
    GenerateAnalyseReportRequestSerializer,
    GenerateAnalyseReportResponseSerializer,
    ListAnalyseReportByRiskRequestSerializer,
    ListAnalyseReportRequestSerializer,
    ListAnalyseReportResponseSerializer,
    ListAnalyseReportRiskRequestSerializer,
    ListAnalyseReportRiskResponseSerializer,
    ListAnalyseReportScenarioResponseSerializer,
    RetrieveAnalyseReportRequestSerializer,
    RetrieveAnalyseReportResponseSerializer,
    TaskResultRequestSerializer,
    TaskResultResponseSerializer,
    UpdateAnalyseReportRequestSerializer,
)
from services.web.risk.tasks import generate_analyse_report


class AnalyseReportMeta(AuditMixinResource, abc.ABC):
    """AI分析报告 Resource 基类"""

    tags = ["AnalyseReport"]


class ListAnalyseReportScenario(AnalyseReportMeta):
    """获取AI报告场景列表"""

    name = gettext_lazy("获取AI报告场景列表")
    RequestSerializer = drf_serializers.Serializer
    ResponseSerializer = ListAnalyseReportScenarioResponseSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        return AnalyseReportScenario.objects.filter(is_enabled=True)


class GenerateAnalyseReport(AnalyseReportMeta):
    """生成AI分析报告（异步）"""

    name = gettext_lazy("生成AI分析报告")
    RequestSerializer = GenerateAnalyseReportRequestSerializer
    ResponseSerializer = GenerateAnalyseReportResponseSerializer

    def perform_request(self, validated_request_data):
        # 1. 获取场景配置（如果有 scenario_key）
        scenario = None
        scenario_key = validated_request_data.get("scenario_key")
        if scenario_key:
            scenario = AnalyseReportScenario.objects.filter(scenario_key=scenario_key, is_enabled=True).first()

        # 2. 获取风险过滤参数，直接存入 prompt_params
        prompt_params = validated_request_data.get("target_risks_filter") or {}

        # 3. 创建 AnalyseReport 记录
        report = AnalyseReport.objects.create(
            title=validated_request_data["title"],
            report_type=validated_request_data["report_type"],
            scenario=scenario,
            analysis_scope=validated_request_data.get("analysis_scope", ""),
            status=AnalyseReportStatus.GENERATING,
            prompt_params=prompt_params,
            custom_prompt=validated_request_data.get("custom_prompt", ""),
        )

        # 4. 提交 Celery 异步任务
        task = generate_analyse_report.delay(report_id=report.report_id)

        # 5. 更新 task_id
        report.task_id = task.id
        report.save(update_fields=["task_id"])

        return {
            "report_id": report.report_id,
            "task_id": task.id,
            "status": "PENDING",
        }


class GetAnalyseReportTaskResult(AnalyseReportMeta):
    """查询AI报告任务结果"""

    name = gettext_lazy("查询AI报告任务结果")
    RequestSerializer = TaskResultRequestSerializer
    ResponseSerializer = TaskResultResponseSerializer

    # Celery 任务状态映射
    STATUS_MAP = {
        "PENDING": "PENDING",
        "STARTED": "RUNNING",
        "PROGRESS": "RUNNING",
        "SUCCESS": "SUCCESS",
        "FAILURE": "FAILURE",
        "REVOKED": "FAILURE",
        "RETRY": "RUNNING",
    }

    def perform_request(self, validated_request_data):
        task_id = validated_request_data["task_id"]

        async_result = AsyncResult(task_id)
        celery_status = async_result.status
        status = self.STATUS_MAP.get(celery_status, "PENDING")

        response = {"task_id": task_id, "status": status, "result": None}

        if status == "SUCCESS":
            response["result"] = async_result.result
        elif status == "FAILURE":
            error_msg = str(async_result.result) if async_result.result else "Unknown error"
            response["result"] = {"error": error_msg}

        return response


class ListAnalyseReport(AnalyseReportMeta):
    """历史分析报告列表"""

    name = gettext_lazy("历史分析报告列表")
    RequestSerializer = ListAnalyseReportRequestSerializer
    ResponseSerializer = ListAnalyseReportResponseSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        # 默认按当前用户过滤，只返回自己创建的报告
        queryset = AnalyseReport.objects.filter(
            status=AnalyseReportStatus.SUCCESS,
            created_by=get_request_username(),
        )

        # keyword 模糊搜索
        keyword = validated_request_data.get("keyword")
        if keyword:
            queryset = queryset.filter(
                Q(title__icontains=keyword) | Q(analysis_scope__icontains=keyword) | Q(created_by__icontains=keyword)
            )

        # report_type 筛选
        report_type = validated_request_data.get("report_type")
        if report_type:
            queryset = queryset.filter(report_type=report_type)

        # 排序
        sort = validated_request_data.get("sort", ["-created_at"])
        if sort:
            queryset = queryset.order_by(*sort)

        return queryset


class RetrieveAnalyseReport(AnalyseReportMeta):
    """AI报告详情"""

    name = gettext_lazy("AI报告详情")
    RequestSerializer = RetrieveAnalyseReportRequestSerializer
    ResponseSerializer = RetrieveAnalyseReportResponseSerializer

    def perform_request(self, validated_request_data):
        report_id = validated_request_data["report_id"]
        return get_object_or_404(AnalyseReport, report_id=report_id)


class UpdateAnalyseReport(AnalyseReportMeta):
    """编辑AI报告"""

    name = gettext_lazy("编辑AI报告")
    RequestSerializer = UpdateAnalyseReportRequestSerializer
    ResponseSerializer = RetrieveAnalyseReportResponseSerializer

    def perform_request(self, validated_request_data):
        report_id = validated_request_data["report_id"]
        report = get_object_or_404(AnalyseReport, report_id=report_id)

        if "title" in validated_request_data:
            report.title = validated_request_data["title"]
        if "content" in validated_request_data:
            report.content = validated_request_data["content"]

        update_fields = []
        if "title" in validated_request_data:
            update_fields.append("title")
        if "content" in validated_request_data:
            update_fields.append("content")

        if update_fields:
            report.save(update_fields=update_fields)

        return report


class DeleteAnalyseReport(AnalyseReportMeta):
    """删除AI报告"""

    name = gettext_lazy("删除AI报告")
    RequestSerializer = DeleteAnalyseReportRequestSerializer

    def perform_request(self, validated_request_data):
        report_id = validated_request_data["report_id"]
        report = get_object_or_404(AnalyseReport, report_id=report_id)
        # 级联删除关联关系
        report.delete()
        return {}


class ExportAnalyseReport(AnalyseReportMeta):
    """导出AI报告

    支持 Markdown 和 PDF 两种格式。
    - Markdown: 直接输出 content 文本
    - PDF: 使用 xhtml2pdf 将 Markdown → HTML → PDF，支持表格、样式等复杂格式
    """

    name = gettext_lazy("导出AI报告")
    RequestSerializer = ExportAnalyseReportRequestSerializer

    def perform_request(self, validated_request_data):
        report_id = validated_request_data["report_id"]
        export_format = validated_request_data["export_format"]
        report = get_object_or_404(AnalyseReport, report_id=report_id)

        if export_format == "markdown":
            return self._export_markdown(report)
        elif export_format == "pdf":
            return self._export_pdf(report)

    def _export_markdown(self, report):
        """导出为 Markdown 文件"""
        response = HttpResponse(report.content, content_type="text/markdown; charset=utf-8")
        filename = f"{report.title}.md"
        response["Content-Disposition"] = f'attachment; filename="{quote(filename)}"'
        return response

    # 项目内置中文字体路径（Noto Sans SC，SIL Open Font License）
    _CJK_FONT_PATH = os.path.normpath(
        os.path.join(os.path.dirname(__file__), os.pardir, "fonts", "NotoSansSC-Regular.ttf")
    )

    # PDF 报告的 HTML 模板，使用 @font-face 注册项目内置中文字体
    _PDF_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    @font-face {{
        font-family: 'NotoSansSC';
        src: url('{font_path}');
    }}
    body {{
        font-family: 'NotoSansSC';
        font-size: 12px;
        line-height: 1.8;
        color: #333;
        margin: 0;
        padding: 0;
    }}
    h1 {{
        font-size: 20px;
        text-align: center;
        border-bottom: 2px solid #333;
        padding-bottom: 10px;
        margin-bottom: 6px;
    }}
    .meta {{
        font-size: 10px;
        color: #666;
        text-align: center;
        margin-bottom: 20px;
        padding-bottom: 10px;
        border-bottom: 1px solid #ddd;
    }}
    h2 {{
        font-size: 16px;
        margin-top: 18px;
        margin-bottom: 8px;
        border-bottom: 1px solid #eee;
        padding-bottom: 4px;
    }}
    h3 {{
        font-size: 14px;
        margin-top: 14px;
        margin-bottom: 6px;
    }}
    p {{
        margin: 6px 0;
        text-align: justify;
    }}
    table {{
        width: 100%;
        border-collapse: collapse;
        margin: 10px 0;
        font-size: 11px;
    }}
    th, td {{
        border: 1px solid #ccc;
        padding: 6px 8px;
        text-align: left;
    }}
    th {{
        background-color: #f0f0f0;
        font-weight: bold;
    }}
    tr:nth-child(even) td {{
        background-color: #fafafa;
    }}
    ul, ol {{
        margin: 6px 0;
        padding-left: 24px;
    }}
    li {{
        margin: 3px 0;
    }}
    code {{
        background-color: #f5f5f5;
        padding: 1px 4px;
        font-size: 11px;
    }}
    pre {{
        background-color: #f5f5f5;
        padding: 10px;
        font-size: 10px;
        overflow-x: auto;
    }}
    blockquote {{
        border-left: 3px solid #ccc;
        margin: 10px 0;
        padding: 6px 12px;
        color: #666;
    }}
</style>
</head>
<body>
    <h1>{title}</h1>
    <div class="meta">{meta}</div>
    {content}
</body>
</html>"""

    @staticmethod
    def _format_analysis_scope(scope_raw: str) -> str:
        """将 analysis_scope 的 JSON 格式转为可读文本。

        输入示例:
            [{"label":"首次发现时间","value":["2025-09-26","2026-03-27"]},{"label":"责任人","value":["ziminggao"]}]
        输出示例:
            首次发现时间: 2025-09-26 ~ 2026-03-27, 责任人: ziminggao
        如果解析失败则原样返回。
        """
        if not scope_raw:
            return ""
        try:
            items = json.loads(scope_raw)
            if not isinstance(items, list):
                return scope_raw
        except (json.JSONDecodeError, TypeError):
            return scope_raw

        parts = []
        for item in items:
            label = item.get("label", "")
            value = item.get("value", "")
            if isinstance(value, list):
                # 两个元素的列表视为范围（如时间范围），用 ~ 连接；否则用逗号
                if len(value) == 2:
                    display_value = f"{value[0]} ~ {value[1]}"
                else:
                    display_value = ", ".join(str(v) for v in value)
            else:
                display_value = str(value)
            if label:
                parts.append(f"{label}: {display_value}")
            else:
                parts.append(display_value)
        return ", ".join(parts) if parts else scope_raw

    def _export_pdf(self, report):
        """导出为 PDF 文件

        使用 xhtml2pdf 将 Markdown 内容渲染为 PDF：
        1. 先用 mistune 将 Markdown 转为 HTML
        2. 再用 xhtml2pdf 将 HTML 渲染为 PDF
        xhtml2pdf 基于 reportlab，支持表格、CSS 样式等复杂格式。
        使用项目内置的 Noto Sans SC 字体以支持中文渲染；
        如果 xhtml2pdf 不可用，回退为纯 HTML 导出。
        """
        import io

        import mistune

        # 将 Markdown 转为 HTML
        html_content = mistune.html(report.content)

        # 构建元信息
        scope_display = self._format_analysis_scope(report.analysis_scope)
        meta_text = (
            f"报告类型: {report.get_report_type_display()} &nbsp;|&nbsp; "
            f"分析范围: {scope_display} &nbsp;|&nbsp; "
            f"关联风险: {report.risk_count} 条 &nbsp;|&nbsp; "
            f"生成人: {report.created_by} &nbsp;|&nbsp; "
            f"生成时间: {report.created_at.strftime('%Y-%m-%d %H:%M') if report.created_at else ''}"
        )

        # 渲染完整 HTML
        full_html = self._PDF_HTML_TEMPLATE.format(
            font_path=self._CJK_FONT_PATH,
            title=report.title,
            meta=meta_text,
            content=html_content,
        )

        logger = logging.getLogger(__name__)

        try:
            from xhtml2pdf import pisa

            # 检查字体文件是否存在
            if not os.path.exists(self._CJK_FONT_PATH):
                logger.error("[ExportPDF] 中文字体文件不存在: %s", self._CJK_FONT_PATH)

            # xhtml2pdf 通过 @font-face CSS 自动加载字体并注册到 reportlab
            pdf_buffer = io.BytesIO()
            pisa_status = pisa.CreatePDF(full_html, dest=pdf_buffer, encoding="utf-8")

            if pisa_status.err:
                logger.error("[ExportPDF] xhtml2pdf 渲染失败，错误数: %d", pisa_status.err)
                raise RuntimeError(f"xhtml2pdf 渲染失败，错误数: {pisa_status.err}")

            pdf_bytes = pdf_buffer.getvalue()
            response = HttpResponse(pdf_bytes, content_type="application/pdf")
            ext = ".pdf"
        except ImportError:
            logger.exception("[ExportPDF] xhtml2pdf 或 reportlab 未安装，回退为 HTML 导出")
            response = HttpResponse(full_html, content_type="text/html; charset=utf-8")
            ext = ".html"
        except Exception:
            logger.exception("[ExportPDF] PDF 生成失败，回退为 HTML 导出")
            response = HttpResponse(full_html, content_type="text/html; charset=utf-8")
            ext = ".html"

        filename = f"{report.title}{ext}"
        response["Content-Disposition"] = f'attachment; filename="{quote(filename)}"'
        return response


class ListAnalyseReportRisk(AnalyseReportMeta):
    """报告关联风险列表"""

    name = gettext_lazy("报告关联风险列表")
    RequestSerializer = ListAnalyseReportRiskRequestSerializer
    ResponseSerializer = ListAnalyseReportRiskResponseSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        report_id = validated_request_data["report_id"]
        risk_ids = list(AnalyseReportRisk.objects.filter(report_id=report_id).values_list("risk_id", flat=True))
        return Risk.objects.filter(risk_id__in=risk_ids).select_related("strategy")


class ListAnalyseReportByRisk(AnalyseReportMeta):
    """通过风险ID反查报告"""

    name = gettext_lazy("风险关联AI报告")
    RequestSerializer = ListAnalyseReportByRiskRequestSerializer
    ResponseSerializer = ListAnalyseReportResponseSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        risk_id = validated_request_data["risk_id"]
        report_ids = AnalyseReportRisk.objects.filter(risk_id=risk_id).values_list("report_id", flat=True)
        return AnalyseReport.objects.filter(report_id__in=report_ids, status=AnalyseReportStatus.SUCCESS)
