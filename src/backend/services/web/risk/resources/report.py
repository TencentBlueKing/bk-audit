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

from celery.result import AsyncResult
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy

from apps.audit.resources import AuditMixinResource
from services.web.risk.models import Risk
from services.web.risk.serializers import (
    AIPreviewRequestSerializer,
    AsyncTaskResponseSerializer,
    TaskResultRequestSerializer,
    TaskResultResponseSerializer,
)
from services.web.risk.tasks import render_ai_variable


class RiskReportMeta(AuditMixinResource, abc.ABC):
    """风险报告 Resource 基类"""

    tags = ["RiskReport"]


class AIPreview(RiskReportMeta):
    """AI 智能体预览

    提交异步任务，传入 AI 变量配置，返回 AI 渲染结果。
    用于单独预览 AI 变量的输出。
    """

    name = gettext_lazy("AI智能体预览")
    RequestSerializer = AIPreviewRequestSerializer
    ResponseSerializer = AsyncTaskResponseSerializer

    def perform_request(self, validated_request_data):
        risk_id = validated_request_data["risk_id"]
        ai_variables = validated_request_data["ai_variables"]

        # 验证风险单存在
        risk = get_object_or_404(Risk, risk_id=risk_id)

        # 提交异步任务
        task = render_ai_variable.delay(risk_id=risk.risk_id, ai_variables=ai_variables)

        return {"task_id": task.id, "status": "PENDING"}


class GetTaskResult(RiskReportMeta):
    """查询任务结果

    查询异步任务的执行结果，用于轮询获取 AI 预览的结果。
    """

    name = gettext_lazy("查询任务结果")
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

        # 获取任务结果
        async_result = AsyncResult(task_id)
        celery_status = async_result.status
        status = self.STATUS_MAP.get(celery_status, "PENDING")

        response = {"task_id": task_id, "status": status, "result": None}

        if status == "SUCCESS":
            response["result"] = async_result.result
        elif status == "FAILURE":
            # 获取异常信息
            error_msg = str(async_result.result) if async_result.result else "Unknown error"
            response["result"] = {"error": error_msg}

        return response
