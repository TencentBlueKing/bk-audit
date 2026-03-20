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
    - PDF: Markdown → HTML → PDF (使用 mistune 库)
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

    def _export_pdf(self, report):
        """导出为 PDF 文件

        Markdown → HTML → PDF 转换链
        使用 mistune 库将 Markdown 转为 HTML，然后使用 weasyprint 生成 PDF。
        如果 weasyprint 不可用，回退为纯 HTML 导出。
        """
        import mistune

        html_content = mistune.html(report.content)

        full_html = (
            "<!DOCTYPE html>"
            "<html><head><meta charset='utf-8'>"
            f"<title>{report.title}</title>"
            "<style>"
            "body{font-family:sans-serif;margin:40px;line-height:1.6;}"
            "h1{border-bottom:2px solid #333;padding-bottom:10px;}"
            ".meta{color:#666;font-size:14px;margin-bottom:20px;}"
            "table{border-collapse:collapse;width:100%;}"
            "th,td{border:1px solid #ddd;padding:8px;text-align:left;}"
            "th{background-color:#f2f2f2;}"
            "pre{background:#f5f5f5;padding:12px;border-radius:4px;overflow-x:auto;}"
            "code{background:#f5f5f5;padding:2px 4px;border-radius:3px;}"
            "</style></head><body>"
            f"<h1>{report.title}</h1>"
            f'<div class="meta">'
            f"报告类型: {report.get_report_type_display()} | "
            f"分析范围: {report.analysis_scope} | "
            f"关联风险: {report.risk_count} 条 | "
            f"生成人: {report.created_by} | "
            f"生成时间: {report.created_at.strftime('%Y-%m-%d %H:%M') if report.created_at else ''}"
            "</div>"
            f"{html_content}"
            "</body></html>"
        )

        try:
            from weasyprint import HTML as WeasyprintHTML

            pdf_bytes = WeasyprintHTML(string=full_html).write_pdf()
            response = HttpResponse(pdf_bytes, content_type="application/pdf")
        except ImportError:
            # weasyprint 不可用时回退为 HTML 导出
            response = HttpResponse(full_html, content_type="text/html; charset=utf-8")

        filename = f"{report.title}.pdf"
        response["Content-Disposition"] = f'attachment; filename="{quote(filename)}"'
        return response


class ListAnalyseReportRisk(AnalyseReportMeta):
    """报告关联风险列表"""

    name = gettext_lazy("报告关联风险列表")
    RequestSerializer = ListAnalyseReportRiskRequestSerializer

    def perform_request(self, validated_request_data):
        report_id = validated_request_data["report_id"]
        risk_ids = list(AnalyseReportRisk.objects.filter(report_id=report_id).values_list("risk_id", flat=True))
        return risk_ids


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
