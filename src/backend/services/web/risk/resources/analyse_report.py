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
    - PDF: 使用 fpdf2 直接将 Markdown 渲染为 PDF（纯 Python，零系统依赖）
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

    # 项目内置中文字体路径（Noto Sans CJK SC，SIL Open Font License）
    _CJK_FONT_PATH = os.path.join(os.path.dirname(__file__), os.pardir, "fonts", "NotoSansSC-Regular.ttf")

    def _export_pdf(self, report):
        """导出为 PDF 文件

        使用 fpdf2 直接将 Markdown 内容渲染为 PDF。
        fpdf2 是纯 Python 库，零系统依赖，pip 安装即用。
        使用项目内置的 Noto Sans CJK SC 字体以支持中文渲染；
        如果 fpdf2 不可用，回退为纯 HTML 导出。
        """
        try:
            from fpdf import FPDF

            pdf = FPDF()
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)

            # 注册项目内置的 CJK 字体以支持中文
            font_family = "NotoSansSC"
            for style in ("", "B", "I", "BI"):
                pdf.add_font(font_family, style=style, fname=self._CJK_FONT_PATH)

            pdf.set_font(font_family, size=16)
            pdf.cell(text=report.title, new_x="LEFT", new_y="NEXT")
            pdf.ln(4)

            # 元信息
            pdf.set_font(font_family, size=9)
            meta_text = (
                f"报告类型: {report.get_report_type_display()} | "
                f"分析范围: {report.analysis_scope} | "
                f"关联风险: {report.risk_count} 条 | "
                f"生成人: {report.created_by} | "
                f"生成时间: {report.created_at.strftime('%Y-%m-%d %H:%M') if report.created_at else ''}"
            )
            pdf.multi_cell(w=0, text=meta_text)
            pdf.ln(6)

            # 使用 fpdf2 内置的 markdown 支持渲染正文
            pdf.set_font(font_family, size=11)
            pdf.multi_cell(w=0, text=report.content, markdown=True)

            pdf_bytes = pdf.output()
            response = HttpResponse(pdf_bytes, content_type="application/pdf")
            ext = ".pdf"
        except ImportError:
            # fpdf2 不可用时回退为 HTML 导出
            import mistune

            html_content = mistune.html(report.content)
            full_html = (
                "<!DOCTYPE html>"
                "<html><head><meta charset='utf-8'>"
                f"<title>{report.title}</title>"
                "<style>"
                "body{font-family:sans-serif;margin:40px;line-height:1.6;}"
                "h1{border-bottom:2px solid #333;padding-bottom:10px;}"
                "</style></head><body>"
                f"<h1>{report.title}</h1>"
                f"{html_content}"
                "</body></html>"
            )
            response = HttpResponse(full_html, content_type="text/html; charset=utf-8")
            ext = ".html"
        except Exception:
            # PDF 生成失败时回退为 HTML 导出
            import mistune

            html_content = mistune.html(report.content)
            full_html = (
                "<!DOCTYPE html>"
                "<html><head><meta charset='utf-8'>"
                f"<title>{report.title}</title>"
                "<style>"
                "body{font-family:sans-serif;margin:40px;line-height:1.6;}"
                "h1{border-bottom:2px solid #333;padding-bottom:10px;}"
                "</style></head><body>"
                f"<h1>{report.title}</h1>"
                f"{html_content}"
                "</body></html>"
            )
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
