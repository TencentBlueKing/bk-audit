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

from blueapps.utils.logger import logger_celery
from django.conf import settings

from services.web.risk.models import AnalyseReport, AnalyseReportRisk
from services.web.risk.serializers import ListRiskRequestSerializer


def load_analyse_report_risk_ids(report: AnalyseReport, risk_limit: int) -> list[str]:
    """复用 ListRisk 的参数校验、权限过滤和检索分支，按报告创建人加载最终风险 ID。"""
    from services.web.risk.resources.risk import ListRisk

    list_risk = ListRisk()
    serializer = ListRiskRequestSerializer(data=report.prompt_params or {})
    serializer.is_valid(raise_exception=True)
    return list_risk.load_filter_risk_ids(
        dict(serializer.validated_data),
        username=report.created_by,
        risk_limit=risk_limit,
    )


def bind_risks_to_analyse_report(report: AnalyseReport) -> int:
    """
    根据报告 prompt_params 创建报告风险快照。

    返回本次快照命中的风险数量。重复调用不会创建重复关联。
    """
    if not report.created_by:
        logger_celery.warning("[BindRisksToAnalyseReport] Skip report without creator, report_id=%s", report.report_id)
        return 0

    risk_limit = int(getattr(settings, "ANALYSE_REPORT_RISK_LIMIT", 100))
    if risk_limit <= 0:
        logger_celery.info(
            "[BindRisksToAnalyseReport] Skip because risk limit is %s, report_id=%s",
            risk_limit,
            report.report_id,
        )
        return 0

    risk_ids = load_analyse_report_risk_ids(report, risk_limit)
    if not risk_ids:
        logger_celery.info(
            "[BindRisksToAnalyseReport] No risks found for report_id=%s, prompt_params=%s",
            report.report_id,
            report.prompt_params,
        )
        return 0

    report_risks = [AnalyseReportRisk(report=report, risk_id=rid) for rid in risk_ids]
    AnalyseReportRisk.objects.bulk_create(report_risks, ignore_conflicts=True)

    report.risk_count = len(risk_ids)
    report.save(update_fields=["risk_count"])

    logger_celery.info(
        "[BindRisksToAnalyseReport] Linked %d risks to report_id=%s",
        len(risk_ids),
        report.report_id,
    )
    return len(risk_ids)
