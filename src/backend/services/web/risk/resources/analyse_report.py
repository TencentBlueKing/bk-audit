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
import logging
import uuid
from typing import Any

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
from core.exporter.report import (
    ReportDocumentExporter,
    ReportExportError,
    resolve_content_format,
)
from core.utils.page import paginate_data
from services.web.risk.constants import AnalyseReportStatus, AnalyseReportType
from services.web.risk.exceptions import AnalyseReportExportFailed
from services.web.risk.models import (
    AnalyseReport,
    AnalyseReportErrorInfo,
    AnalyseReportExtraInfo,
    AnalyseReportRisk,
    AnalyseReportScenario,
    Risk,
)
from services.web.risk.report.analyse_report import bind_risks_to_analyse_report
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
    SEARCH_FILTERS = {
        "title": "title__icontains",
        "analysis_scope": "analysis_scope__icontains",
    }

    def perform_request(self, validated_request_data):
        # 默认按当前用户过滤，只返回自己创建的报告
        queryset = AnalyseReport.objects.filter(created_by=get_request_username())

        # keyword 模糊搜索
        keyword = validated_request_data.get("keyword")
        if keyword:
            queryset = queryset.filter(
                Q(title__icontains=keyword) | Q(analysis_scope__icontains=keyword) | Q(created_by__icontains=keyword)
            )

        for request_field, lookup in self.SEARCH_FILTERS.items():
            value = validated_request_data.get(request_field)
            if value:
                queryset = queryset.filter(**{lookup: value})

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
    """编辑报告标题或完整正文，保留 Markdown/HTML 原文。

    富文本保存示例：{"content":"<h1>报告</h1><p>编辑正文</p>","content_format":"HTML"}。
    省略格式时识别本次正文；详情返回 content_format，旧内容无需重新保存。
    单独修改标题不改变正文或格式；格式标识只能与正文一同提交。
    """

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
            report.extra_info = {
                **report.extra_info,
                "content_format": resolve_content_format(report.content, validated_request_data.get("content_format")),
            }

        update_fields = []
        if "title" in validated_request_data:
            update_fields.append("title")
        if "content" in validated_request_data:
            update_fields.append("content")
            update_fields.append("extra_info")

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
    """复用公共 Markdown/HTML 报告导出；格式由正文标识或历史识别决定。

    Markdown 下载对 HTML 仅作即时转换；PDF 失败稳定报错，不改正文或回退 HTML。
    export_format 仍为 markdown/pdf，读取当前保存正文；两种正文均可导出，
    HTML 下载为 Markdown 时仅文件格式降级，原 HTML 和 PDF 不作转换。
    """

    name = gettext_lazy("导出AI报告")
    RequestSerializer = ExportAnalyseReportRequestSerializer

    def perform_request(self, validated_request_data):
        report = self.get_user_report(validated_request_data["report_id"])
        try:
            result = ReportDocumentExporter(
                title=report.title,
                content=report.content,
                content_format=report.extra_info.get("content_format"),
                allow_remote_images=True,
            ).export(validated_request_data["export_format"])
        except ReportExportError as error:
            logging.getLogger(__name__).exception("风险报告导出失败: report_id=%s", report.report_id)
            raise AnalyseReportExportFailed() from error
        response = HttpResponse(result.content, content_type=result.content_type)
        response["Content-Disposition"] = content_disposition_header(as_attachment=True, filename=result.filename)
        return response


class AnalyseReportRiskListBase(AnalyseReportMeta):
    """报告关联风险列表基类。"""

    RequestSerializer = ListAnalyseReportRiskRequestSerializer
    ResponseSerializer = ListAnalyseReportRiskResponseSerializer
    many_response_data = True
    check_report_owner = True

    def perform_request(self, validated_request_data):
        self.with_detail = validated_request_data.get("with_detail", False)
        report_id = validated_request_data["report_id"]
        if self.check_report_owner:
            self.get_user_report(report_id)

        queryset = self.get_report_risk_queryset(report_id)
        queryset = self.filter_report_risks(queryset, validated_request_data)
        return queryset

    def validate_response_data(self, response_data):
        if isinstance(response_data, QuerySet):
            response_serializer = self.ResponseSerializer(
                response_data,
                many=True,
                context={"with_detail": getattr(self, "with_detail", False)},
            )
            self._response_serializer = response_serializer
            return response_serializer.data
        return super().validate_response_data(response_data)

    def get_report_risk_queryset(self, report_id: int):
        risk_ids = AnalyseReportRisk.objects.filter(report_id=report_id).values("risk_id")
        return Risk.objects.filter(risk_id__in=risk_ids).select_related("strategy")

    def filter_report_risks(self, queryset, params: dict):
        risk_ids = params.get("risk_id", [])
        if risk_ids:
            queryset = queryset.filter(risk_id__in=risk_ids)

        risk_levels = params.get("risk_level", [])
        if risk_levels:
            queryset = queryset.filter(risk_level__in=risk_levels)

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
        paged_queryset, page = paginate_data(queryset=queryset, request=request)
        data = ListAnalyseReportRiskResponseSerializer(
            paged_queryset,
            many=True,
            context={"with_detail": with_detail},
        ).data
        return page.get_paginated_response(data).data


class MCPListAnalyseReportRisk(ListAnalyseReportRiskAPIGW):
    """MCP 报告关联风险列表，复用 APIGW 分页与响应契约。"""

    name = gettext_lazy("报告关联风险列表(MCP)")

    @property
    def check_report_owner(self) -> bool:
        """MCP 使用真实用户身份，必须校验报告归属。"""
        return True


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
