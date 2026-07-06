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

from core.monitor import Event

__all__ = [
    "LostSceneDetectedEvent",
    "RiskReportRenderFailedEvent",
    "RiskReportContentQualityEvent",
    "RiskExportFailedEvent",
    "NL2RiskFilterFailedEvent",
    "AnalyseReportGenerateFailedEvent",
    "AssetSyncAnomalyEvent",
    "AssetSyncCheckAnomalyEvent",
]


class LostSceneDetectedEvent(Event):
    name = "lost_scene_detected"
    documentation = "丢失场景检测"
    labelnames = ["strategy_id", "control_id", "control_version", "strategy_name"]


class RiskReportRenderFailedEvent(Event):
    """风险报告渲染失败事件"""

    name = "risk_report_render_failed"
    documentation = "风险报告渲染失败"
    labelnames = ["risk_id", "task_id"]


class RiskReportContentQualityEvent(Event):
    """风险报告内容质量异常事件

    维度字段:
    - risk_id: 风险ID
    - issue_type: 质量问题类型 (empty/too_short/ai_error/ai_thinking/provider_error/render_error/event_query_failed)
    """

    name = "risk_report_content_quality"
    documentation = "风险报告内容质量异常"
    labelnames = ["risk_id", "issue_type"]


class RiskExportFailedEvent(Event):
    """风险异步导出失败事件

    维度字段:
    - username: 导出发起人
    - risk_count: 本次导出的风险单数量
    """

    name = "risk_export_failed"
    documentation = "风险异步导出失败"
    labelnames = ["username", "risk_count"]


class NL2RiskFilterFailedEvent(Event):
    """自然语言转风险筛选条件失败事件"""

    name = "nl2risk_filter_failed"
    documentation = "自然语言转风险筛选条件失败"
    labelnames = ["status", "scope_type", "error_type"]


class AnalyseReportGenerateFailedEvent(Event):
    """AI 分析报告最终生成失败事件"""

    name = "analyse_report_generate_failed"
    documentation = "AI 分析报告最终生成失败"
    labelnames = ["report_type", "has_scenario", "error_type"]


class AssetSyncAnomalyEvent(Event):
    """资产同步链路异常事件

    由 report_asset_sync_status 上报，关注同步链路本身的健康度。
    维度字段:
    - system_id: 系统ID
    - resource_type_id: 资源类型ID
    - join_data_type: 关联数据类型
    - reason: 异常原因 (status_failed/preparing_timeout)
    """

    name = "asset_sync_status_anomaly"
    documentation = "资产同步状态异常"
    labelnames = ["system_id", "resource_type_id", "join_data_type", "reason"]


class AssetSyncCheckAnomalyEvent(Event):
    """资产同步Check异常事件

    由 report_asset_sync_count 上报，关注源端量与存储量的数据一致性。
    维度字段:
    - system_id: 系统ID
    - resource_type_id: 资源类型ID
    - join_data_type: 关联数据类型
    - reason: 异常原因 (source_pull_failed/storage_query_failed)
    """

    name = "asset_sync_data_anomaly"
    documentation = "资产同步数据异常"
    labelnames = ["system_id", "resource_type_id", "join_data_type", "reason"]
