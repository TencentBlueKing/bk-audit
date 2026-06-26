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
import io
import logging
import os
import uuid
from typing import Any
from urllib.parse import unquote, urlparse

from blueapps.utils.request_provider import get_request_username
from celery.result import AsyncResult
from django.conf import settings
from django.db import transaction
from django.db.models import Q, QuerySet
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.http import content_disposition_header
from django.utils.translation import gettext_lazy
from rest_framework import serializers as drf_serializers

from apps.audit.resources import AuditMixinResource
from core.utils.page import paginate_data
from services.web.risk.constants import AnalyseReportStatus, AnalyseReportType
from services.web.risk.models import (
    AnalyseReport,
    AnalyseReportErrorInfo,
    AnalyseReportExtraInfo,
    AnalyseReportRisk,
    AnalyseReportScenario,
    Risk,
)
from services.web.risk.report.analyse_report import bind_risks_to_analyse_report
from services.web.risk.report.markdown import render_ai_markdown
from services.web.risk.serializers import (
    DeleteAnalyseReportRequestSerializer,
    ExportAnalyseReportRequestSerializer,
    GenerateAnalyseReportRequestSerializer,
    GenerateAnalyseReportResponseSerializer,
    ListAnalyseReportByRiskRequestSerializer,
    ListAnalyseReportRequestSerializer,
    ListAnalyseReportResponseSerializer,
    ListAnalyseReportRiskPageResponseSerializer,
    ListAnalyseReportRiskRequestSerializer,
    ListAnalyseReportRiskResponseSerializer,
    ListAnalyseReportScenarioResponseSerializer,
    RetrieveAnalyseReportRequestSerializer,
    RetrieveAnalyseReportResponseSerializer,
    RetryAnalyseReportRequestSerializer,
    RetryAnalyseReportResponseSerializer,
    TaskResultRequestSerializer,
    TaskResultResponseSerializer,
    UpdateAnalyseReportRequestSerializer,
)
from services.web.risk.tasks import (
    generate_analyse_report,
    generate_analyse_report_title,
)


def _build_analyse_report_temp_title(scenario: AnalyseReportScenario | None) -> str:
    """构造 AI 标题生成完成前展示的临时标题。"""
    if scenario:
        title_prefix = scenario.name
    else:
        title_prefix = str(AnalyseReportType.CUSTOM.label)
    timestamp = timezone.localtime().strftime("%Y%m%d%H%M%S")
    return f"{title_prefix}_{timestamp}"


def _mark_analyse_report_submit_failed(report: AnalyseReport, exc: Exception) -> None:
    ended_at = timezone.now()
    report.status = AnalyseReportStatus.FAILED
    report.title_generating = False
    report.extra_info = AnalyseReportExtraInfo.build(
        started_at=ended_at,
        ended_at=ended_at,
        error=AnalyseReportErrorInfo(
            error_type=exc.__class__.__name__,
            error_message=str(exc),
            retry_count=0,
            max_retries=0,
        ),
    ).model_dump(exclude_none=True)
    report.save(update_fields=["status", "title_generating", "extra_info", "updated_at"])


class AnalyseReportMeta(AuditMixinResource, abc.ABC):
    """AI分析报告 Resource 基类"""

    tags = ["AnalyseReport"]

    def get_user_reports(self):
        return AnalyseReport.objects.filter(created_by=get_request_username())

    def get_user_report(self, report_id: int) -> AnalyseReport:
        return get_object_or_404(self.get_user_reports(), report_id=report_id)


class ListAnalyseReportScenario(AnalyseReportMeta):
    """获取AI报告场景列表"""

    name = gettext_lazy("获取AI报告场景列表")
    RequestSerializer = drf_serializers.Serializer
    ResponseSerializer = ListAnalyseReportScenarioResponseSerializer
    many_response_data = True

    def perform_request(self, validated_request_data: dict[str, Any]) -> QuerySet[AnalyseReportScenario]:
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
        generate_title = validated_request_data.get("generate_title", False)
        title = _build_analyse_report_temp_title(scenario) if generate_title else validated_request_data["title"]
        title_task_id = str(uuid.uuid4()) if generate_title else ""
        with transaction.atomic():
            report = AnalyseReport.objects.create(
                title=title,
                report_type=validated_request_data["report_type"],
                scenario=scenario,
                analysis_scope=validated_request_data.get("analysis_scope", ""),
                status=AnalyseReportStatus.GENERATING,
                title_generating=generate_title,
                title_task_id=title_task_id,
                prompt_params=prompt_params,
                custom_prompt=validated_request_data.get("custom_prompt", ""),
            )
            bind_risks_to_analyse_report(report)

        # 4. 提交 Celery 异步任务
        try:
            task = generate_analyse_report.delay(report_id=report.report_id)
        except Exception as exc:
            _mark_analyse_report_submit_failed(report, exc)
            logging.getLogger(__name__).exception(
                "[GenerateAnalyseReport] Submit task failed report_id=%s",
                report.report_id,
            )
            raise

        # 5. 更新 task_id
        report.task_id = task.id
        report.save(update_fields=["task_id"])

        title_task_status = ""
        if generate_title:
            generate_analyse_report_title.apply_async(kwargs={"report_id": report.report_id}, task_id=title_task_id)
            title_task_status = "PENDING"

        return {
            "report_id": report.report_id,
            "task_id": task.id,
            "status": "PENDING",
            "title_task_id": title_task_id,
            "title_task_status": title_task_status,
        }


class RetryAnalyseReport(AnalyseReportMeta):
    """重试 AI 分析报告"""

    name = gettext_lazy("重试AI分析报告")
    RequestSerializer = RetryAnalyseReportRequestSerializer
    ResponseSerializer = RetryAnalyseReportResponseSerializer

    def perform_request(self, validated_request_data):
        report_id = validated_request_data["report_id"]
        report = self.get_user_report(report_id)

        updated = AnalyseReport.objects.filter(
            report_id=report.report_id,
            status__in=[AnalyseReportStatus.SUCCESS, AnalyseReportStatus.FAILED],
        ).update(
            status=AnalyseReportStatus.GENERATING,
            content="",
            task_id="",
            extra_info={},
            updated_at=timezone.now(),
        )
        if not updated:
            raise drf_serializers.ValidationError({"status": gettext_lazy("报告生成中，不能重复重试")})

        report.refresh_from_db()
        try:
            task = generate_analyse_report.delay(report_id=report.report_id)
        except Exception as exc:
            _mark_analyse_report_submit_failed(report, exc)
            logging.getLogger(__name__).exception(
                "[RetryAnalyseReport] Submit task failed report_id=%s",
                report.report_id,
            )
            raise

        report.task_id = task.id
        report.save(update_fields=["task_id", "updated_at"])
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
        get_object_or_404(self.get_user_reports().filter(Q(task_id=task_id) | Q(title_task_id=task_id)))

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
        queryset = AnalyseReport.objects.filter(created_by=get_request_username())

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

        # status 筛选；不传时返回当前用户所有状态报告，由前端按需筛选
        status = validated_request_data.get("status")
        if status:
            queryset = queryset.filter(status=status)

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
        return self.get_user_report(report_id)


class UpdateAnalyseReport(AnalyseReportMeta):
    """编辑AI报告"""

    name = gettext_lazy("编辑AI报告")
    RequestSerializer = UpdateAnalyseReportRequestSerializer
    ResponseSerializer = RetrieveAnalyseReportResponseSerializer

    def perform_request(self, validated_request_data):
        report_id = validated_request_data["report_id"]
        report = self.get_user_report(report_id)

        if "title" in validated_request_data:
            if report.title_generating:
                raise drf_serializers.ValidationError({"title": gettext_lazy("标题生成中，暂不可编辑")})
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
        report = self.get_user_report(report_id)
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
        report = self.get_user_report(report_id)

        if export_format == "markdown":
            return self._export_markdown(report)
        elif export_format == "pdf":
            return self._export_pdf(report)

    def _export_markdown(self, report):
        """导出为 Markdown 文件"""
        response = HttpResponse(report.content, content_type="text/markdown; charset=utf-8")
        filename = self._build_export_filename(report.title, ".md")
        response["Content-Disposition"] = content_disposition_header(as_attachment=True, filename=filename)
        return response

    @staticmethod
    def _build_export_filename(title: str, extension: str) -> str:
        timestamp = timezone.localtime().strftime("%Y%m%d%H%M%S")
        return f"{title}_{timestamp}{extension}"

    # 项目内置中文字体路径（Noto Sans SC，SIL Open Font License）
    _CJK_FONT_PATH = os.path.normpath(
        os.path.join(os.path.dirname(__file__), os.pardir, "fonts", "NotoSansSC-Regular.ttf")
    )
    _BLOCKED_PDF_RESOURCE_URI = "data:image/gif;base64,R0lGODlhAQABAAAAACw="

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
    p, li {{
        -pdf-word-wrap: CJK;
        word-break: break-word;
        word-wrap: break-word;
        overflow-wrap: anywhere;
    }}
    h1, h2, h3, blockquote, code, pre {{
        -pdf-word-wrap: CJK;
        word-break: break-word;
        word-wrap: break-word;
        overflow-wrap: anywhere;
    }}
    table {{
        width: 100%;
        max-width: 100%;
        table-layout: fixed;
        border-collapse: collapse;
        margin: 10px 0;
        font-size: 11px;
    }}
    th, td {{
        border: 1px solid #ccc;
        padding: 6px 8px;
        text-align: left;
        vertical-align: top;
        -pdf-word-wrap: CJK;
        word-break: break-word;
        word-wrap: break-word;
        overflow-wrap: anywhere;
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
        white-space: pre-wrap;
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
    {content}
</body>
</html>"""

    def _export_pdf(self, report):
        """导出为 PDF 文件

        使用 xhtml2pdf 将 Markdown 内容渲染为 PDF：
        1. 先用 mistune 将 Markdown 转为 HTML
        2. 再用 xhtml2pdf 将 HTML 渲染为 PDF
        xhtml2pdf 基于 reportlab，支持表格、CSS 样式等复杂格式。
        使用项目内置的 Noto Sans SC 字体以支持中文渲染；
        如果 xhtml2pdf 不可用，回退为纯 HTML 导出。
        """
        # 将 Markdown 转为 HTML
        html_content = render_ai_markdown(report.content)

        # 渲染完整 HTML
        full_html = self._PDF_HTML_TEMPLATE.format(
            font_path=self._CJK_FONT_PATH,
            content=html_content,
        )

        logger = logging.getLogger(__name__)

        try:
            # 检查字体文件是否存在
            if not os.path.exists(self._CJK_FONT_PATH):
                logger.error("[ExportPDF] 中文字体文件不存在: %s", self._CJK_FONT_PATH)

            pdf_bytes = self._create_pdf(html=full_html)
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

        filename = self._build_export_filename(report.title, ext)
        response["Content-Disposition"] = content_disposition_header(as_attachment=True, filename=filename)
        return response

    @classmethod
    def _create_pdf(cls, html: str) -> bytes:
        """使用 xhtml2pdf 将 HTML 渲染为 PDF 字节。"""
        from xhtml2pdf import pisa

        pdf_buffer = io.BytesIO()
        pisa_status = pisa.CreatePDF(
            html,
            dest=pdf_buffer,
            encoding="utf-8",
            link_callback=cls._resolve_pdf_resource,
        )
        if pisa_status.err:
            raise RuntimeError(f"xhtml2pdf 渲染失败，错误数: {pisa_status.err}")
        return pdf_buffer.getvalue()

    @classmethod
    def _resolve_pdf_resource(cls, uri: str, rel: str | None) -> str | None:
        """限制 PDF 渲染读取服务器本地文件，仅允许远程资源和内置字体。"""
        if not uri:
            return cls._BLOCKED_PDF_RESOURCE_URI

        parsed_uri = urlparse(uri)
        if parsed_uri.scheme in {"http", "https", "data"}:
            return uri
        if parsed_uri.scheme == "file":
            candidate_path = unquote(parsed_uri.path)
        elif parsed_uri.scheme:
            return cls._BLOCKED_PDF_RESOURCE_URI
        elif os.path.isabs(uri):
            candidate_path = uri
        else:
            candidate_path = os.path.join(os.path.dirname(rel), uri) if rel else os.path.abspath(uri)

        builtin_font_path = os.path.realpath(cls._CJK_FONT_PATH)
        if os.path.realpath(candidate_path) == builtin_font_path:
            return cls._CJK_FONT_PATH
        return cls._BLOCKED_PDF_RESOURCE_URI


class AnalyseReportRiskListBase(AnalyseReportMeta):
    """报告关联风险列表基类。"""

    RequestSerializer = ListAnalyseReportRiskRequestSerializer
    ResponseSerializer = ListAnalyseReportRiskResponseSerializer
    many_response_data = True
    check_report_owner = True

    def perform_request(self, validated_request_data):
        report_id = validated_request_data["report_id"]
        if self.check_report_owner:
            self.get_user_report(report_id)

        queryset = self.get_report_risk_queryset(report_id)
        queryset = self.filter_report_risks(queryset, validated_request_data)
        if validated_request_data.get("with_detail", False):
            return self.attach_risk_detail(queryset)
        return queryset

    def get_report_risk_queryset(self, report_id: int):
        risk_ids = AnalyseReportRisk.objects.filter(report_id=report_id).values("risk_id")
        return Risk.objects.filter(risk_id__in=risk_ids).select_related("strategy")

    def filter_report_risks(self, queryset, params: dict):
        risk_ids = params.get("risk_id", [])
        if risk_ids:
            queryset = queryset.filter(risk_id__in=risk_ids)

        risk_levels = params.get("risk_level", [])
        if risk_levels:
            queryset = queryset.filter(strategy__risk_level__in=risk_levels)

        statuses = params.get("status", [])
        if statuses:
            queryset = queryset.filter(status__in=statuses)

        risk_labels = params.get("risk_label", [])
        if risk_labels:
            queryset = queryset.filter(risk_label__in=risk_labels)

        keyword = params.get("keyword")
        if keyword:
            queryset = queryset.filter(
                Q(risk_id__icontains=keyword) | Q(title__icontains=keyword) | Q(event_content__icontains=keyword)
            )

        return queryset.distinct()

    def attach_risk_detail(self, queryset):
        return ListAnalyseReportRiskResponseSerializer(queryset, many=True, context={"with_detail": True}).data


class ListAnalyseReportRisk(AnalyseReportRiskListBase):
    """报告关联风险列表"""

    name = gettext_lazy("报告关联风险列表")
    check_report_owner = True


class ListAnalyseReportRiskAPIGW(AnalyseReportRiskListBase):
    """报告关联风险列表(APIGW)"""

    name = gettext_lazy("报告关联风险列表(APIGW)")
    audit_action = None
    bind_request = True
    ResponseSerializer = ListAnalyseReportRiskPageResponseSerializer
    many_response_data = False

    @property
    def check_report_owner(self) -> bool:
        """部分测试环境暂不支持 APIGW 身份鉴权，上线后可通过环境变量开启报告归属校验。"""

        return settings.ANALYSE_REPORT_APIGW_CHECK_REPORT_OWNER

    def perform_request(self, validated_request_data):
        request = validated_request_data.pop("_request")
        with_detail = validated_request_data.get("with_detail", False)
        report_id = validated_request_data["report_id"]
        if self.check_report_owner:
            self.get_user_report(report_id)

        queryset = self.get_report_risk_queryset(report_id)
        queryset = self.filter_report_risks(queryset, validated_request_data)

        # ResourceViewSet 会先执行 resource 响应序列化，再处理 enable_paginate；这里需先分页再渲染详情。
        paged_queryset, page = paginate_data(queryset=queryset, request=request)
        data = ListAnalyseReportRiskResponseSerializer(
            paged_queryset,
            many=True,
            context={"with_detail": with_detail},
        ).data
        return page.get_paginated_response(data).data


class ListAnalyseReportByRisk(AnalyseReportMeta):
    """通过风险ID反查报告"""

    name = gettext_lazy("风险关联AI报告")
    RequestSerializer = ListAnalyseReportByRiskRequestSerializer
    ResponseSerializer = ListAnalyseReportResponseSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        risk_id = validated_request_data["risk_id"]
        report_ids = AnalyseReportRisk.objects.filter(risk_id=risk_id).values_list("report_id", flat=True)
        return self.get_user_reports().filter(report_id__in=report_ids, status=AnalyseReportStatus.SUCCESS)
