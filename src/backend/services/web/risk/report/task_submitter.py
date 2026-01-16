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

from typing import Any

from celery.result import AsyncResult

from services.web.risk.models import Risk
from services.web.risk.report.providers import AIProvider, EventProvider
from services.web.risk.report.renderer import render_template
from services.web.risk.report.serializers import ReportRiskVariableSerializer
from services.web.risk.report_config import ReportConfig


def submit_render_task(
    risk: Risk,
    report_config: ReportConfig,
) -> AsyncResult:
    """
    提交渲染任务（简化版）

    封装 Provider 构建逻辑，调用 render_template.delay()

    Args:
        risk: 风险对象
        report_config: 报告配置（包含 template 和 ai_variables）

    Returns:
        Celery AsyncResult 对象
    """
    # 获取风险数据
    risk_data = ReportRiskVariableSerializer(risk).data

    # 将 AIVariableConfig 转换为 dict 格式（AIProvider 需要）
    ai_variables_config = [
        {
            "name": f"ai.{var.name}" if not var.name.startswith("ai.") else var.name,
            "prompt_template": var.prompt_template,
        }
        for var in report_config.ai_variables
    ]

    # 构建 Providers
    providers = [
        AIProvider(
            context={"risk_id": risk.risk_id},
            ai_variables_config=ai_variables_config,
        ),
        # EventProvider 用于处理 count(event.field) 等聚合函数
        EventProvider(risk_id=risk.risk_id),
    ]

    # 构建普通变量
    variables: dict[str, Any] = {"risk": risk_data}

    # 提交异步任务
    return render_template.delay(
        template=report_config.template,
        providers=providers,
        variables=variables,
    )
