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

from core.monitor import Event, Metric, MetricDimension, MetricField

__all__ = [
    "LostSceneDetectedEvent",
    "RiskReportRenderFailedEvent",
    "RiskReportContentQualityEvent",
    "RiskExportFailedEvent",
    "NL2RiskFilterFailedEvent",
    "AnalyseReportGenerateFailedEvent",
    "AssetSyncAnomalyEvent",
    "AssetSyncCheckAnomalyEvent",
    "ScenePermissionGrantFailedEvent",
    "BkSecConfigSyncFailedEvent",
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


class ScenePermissionGrantFailedEvent(Event):
    """场景权限申请审批通过但授权失败事件
    维度字段:
    - application_id: 申请单ID
    - applicant: 申请人
    - scene_id: 场景ID
    - role: 申请角色
    - grant_error: 授权失败原因
    """

    name = "scene_permission_grant_failed"
    documentation = "场景权限申请审批通过但授权失败（重试已达上限）"
    labelnames = ["application_id", "applicant", "scene_id", "role", "grant_error"]


class BkSecConfigSyncFailedEvent(Event):
    """BKSEC 插件配置同步失败事件

    保存策略/测试发送时插件 Config 同步失败时上报

    维度字段:
    - strategy_id: 策略 ID
    - stage: 同步场景
        - strategy_save: 保存策略时的同步（失败会阻断策略保存）
        - test_send: 测试发送时的同步
        - rule_sync: 同步处理规则时需要根据 bksec_config 生成处理套餐参数，但发现发单配置解析不了/不合法，或者规则同步失败
    - fail_reason: 失败原因
        - api_url_missing: 插件配置地址未配置（BKSEC_PLUGIN_CONFIG_API_URL 为空）
        - risk_type_forbidden: 该 risk_type_id 不在当前用户可见范围内（越权，阻断）
        - risk_type_check_failed: 调用 risk_access 列表做可见性校验时异常
        - token_missing: risk_access 列表未返回该 risk_type_id 的 token
        - token_fetch_failed: 调用 risk_access 列表接口异常
        - upsert_rejected: 插件返回 result=false，拒绝写入 Config
        - api_unreachable: 调用插件 Config 同步接口异常（含 5xx）
        - rule_activation_failed: 策略已确认 RUNNING，但启动后同步发单规则失败

    """

    name = "bksec_config_sync_failed"
    documentation = "BKSEC 插件配置同步失败"
    labelnames = ["strategy_id", "stage", "fail_reason"]


class LogCollectFlowMetric(Metric):
    """审计日志接入链路（BK Log -> Doris）水位与可信度指标。

    两类记录（不可合并）：
    - 源端记录：每个合格采集项 1 条，包含 ``source_*``；``age`` 只出现在这里，
      避免将来多存储时按存储数重复计数；
    - 存储记录：首轮每个采集项 1 条 Doris 记录，携带 ``storage_*`` 与 ``lag``，
      ``storage_type`` 维度保留，后续扩展存储不改任务结构。
    """

    documentation = "审计日志接入链路水位、Doris 延迟、源端停滞与查询可信度"

    metric_fields = {
        "log_collect_source_receive_time": MetricField(
            documentation="源端最大有效 origin.time（BK Log 已收日志的上报时间，Unix 秒）", unit="s"
        ),
        "log_collect_source_age_seconds": MetricField(documentation="源端停滞秒数 = 当前时间 - 源端水位", unit="s"),
        "log_collect_source_query_ok": MetricField(documentation="本轮源端 tail 查询结果：1 成功（含成功但无有效水位），0 失败", unit="count"),
        "log_collect_storage_receive_time": MetricField(
            documentation="Doris max(bk_receive_time)（采集插件结果表的上报时间，Unix 秒）", unit="s"
        ),
        "log_collect_storage_query_ok": MetricField(documentation="本轮 Doris 查询结果：1 成功（含成功但无水位），0 失败", unit="count"),
        "log_collect_storage_has_watermark": MetricField(
            documentation="最近 7 个 thedate 分区日内是否有水位：1 有，0 无", unit="count"
        ),
        "log_collect_lag_seconds": MetricField(documentation="Doris 延迟 = 源端水位 - Doris 水位；两侧均有水位才算，负值原样上报", unit="s"),
        "log_collect_lag_source_receive_time": MetricField(documentation="算出该延迟所用的源端水位，用于事后校验口径", unit="s"),
        "log_collect_check_heartbeat": MetricField(documentation="一轮采样结束的心跳样本，固定为 1；缺失代表任务未运行", unit="count"),
        "log_collect_check_duration_seconds": MetricField(documentation="本轮任务总耗时", unit="s"),
        "log_collect_collector_total": MetricField(documentation="本轮纳入采样的合格采集项数量（log + otlp_log）", unit="count"),
        "log_collect_collector_failed": MetricField(documentation="本轮采样抛异常被跳过的采集项数量", unit="count"),
    }

    dimension_fields = {
        "system_id": MetricDimension(documentation="审计系统 ID，来自 CollectorConfig.system_id"),
        "collector_config_id": MetricDimension(documentation="BK Log 采集项 ID，定位到具体采集项"),
        "bk_data_id": MetricDimension(documentation="BkBase RawData 入口 ID，未接入时为空字符串"),
        "storage_type": MetricDimension(documentation="存储类型：首轮固定 doris；源端记录不带该维度"),
        "stage": MetricDimension(documentation="上报阶段：round 为整轮心跳，其余为空"),
    }
