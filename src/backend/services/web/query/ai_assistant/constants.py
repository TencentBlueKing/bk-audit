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
either express or implied. See the License for the specific language governing
permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.

AI 助手日志检索组件常量

决策点（D1-D4，详见设计文档 §17.5）默认实现对应的开关/模板集中在此，
方案确认后只需调整本文件即可切换。
"""

from django.utils.translation import gettext_lazy

# ---------------------------------------------------------------------------
# F1 字段上下文
# ---------------------------------------------------------------------------

# GlobalMetaConfig 配置键（L1 人工配置，运行时写入立即生效）
# 结构: {
#   "systems": {
#     "{system_id}": {
#       "fields": {"{raw_name}": {"nl_name": ..., "description": ..., "sample_value": ...}},
#       "extension_fields": [
#           {"raw_name": ..., "keys": [...], "display_name": ..., "nl_name": ...,
#            "description": ..., "allow_operators": [...], "sample_value": ...}
#       ],
#     }
#   }
# }
AI_ASSISTANT_FIELD_META_CONFIG_KEY = "ai_assistant_field_meta"

# L2 采样开关（默认开启：sample_value 采样回填 + 拓展字段动态发现；此为 settings 缺失时的兜底值，
# 实际取值走 config/default.py 的 BKAPP_AI_ASSISTANT_FIELD_SAMPLE_ENABLED）
AI_ASSISTANT_FIELD_SAMPLE_ENABLED = True
# L2 采样回看窗口（天）：分区裁剪与性能兜底
FIELD_SAMPLE_LOOKBACK_DAYS = 30
# L2 采样条数：单条日志的拓展子键覆盖不全，采样多条按时间倒序融合发现更多拓展字段
# （同一 (容器, 子键) 保留最新一行的采样值）；standard_fields 的 sample_value 仍取最新一条
AI_ASSISTANT_FIELD_SAMPLE_ROWS = 50

# 拓展字段 nl_name 前缀（D-G：拓展字段 nl_name 带 extend. 前缀，与注入 AI 的字段上下文同源）
EXTENSION_NL_NAME_PREFIX = "extend."

# 拓展字段默认允许的操作符（一期拓展字段恒 string；采样发现与用户显式指定的子键共用，
# field_context 缺省值与 nl2json 校验同源引用，防止两处漂移）
EXTENSION_FIELD_DEFAULT_OPERATORS = ("eq", "neq", "include", "exclude", "like")

# ---------------------------------------------------------------------------
# F3 检索快照
# ---------------------------------------------------------------------------

# 快照条数上限（协议：最多 100 条样例，固化 page=1 + 最新排序）
LOG_SEARCH_SNAPSHOT_PAGE_SIZE = 100
# 快照单值截断长度（待冻结 #3，按真实环境校准）
LOG_SEARCH_SNAPSHOT_VALUE_MAX_LENGTH = 1024
# system_info 快照裁剪键（仅保留展示必要键）
SYSTEM_INFO_SNAPSHOT_KEYS = ("system_id", "name")
# 快照显式剔除的内部存储字段（columns 裁剪之外的第二道保险）
SNAPSHOT_EXCLUDED_FIELDS = ("__shard_key__", "__ext", "bk_data_id", "collector_config_id")

# 快照默认列（产品需求 2026-08-14：9 个固定展示字段，display_name 用产品文案）
# 注意：extend_data 为 dict 值，快照原样保留（前端格式化展示），单值截断只作用于 str 值
SNAPSHOT_DEFAULT_COLUMNS = (
    ("start_time", "操作起始时间"),
    ("username", "操作人"),
    ("system_id", "来源系统(ID)"),
    ("action_id", "操作事件名(ID)"),
    ("resource_type_id", "资源类型(ID)"),
    ("instance_id", "资源实例(ID)"),
    ("result_code", "操作结果(Code)"),
    ("extend_data", "拓展数据"),
    ("log", "操作（完整日志）"),
)

# ---------------------------------------------------------------------------
# F2 NL2JSON
# ---------------------------------------------------------------------------

# AIDev 调用超时（秒），对齐联调指南静默处理阈值
AI_NL2JSON_AGENT_TIMEOUT = 10
# thread_id 前缀（AIDev 会话标识）
AI_NL2JSON_THREAD_ID_PREFIX = "ai-log-search"
# D2 默认实现：AI 未输出时间时后端补最近 N 天窗口
DEFAULT_SEARCH_WINDOW_DAYS = 7
# AI 输出中禁止出现的时间字段（出现后端剔除并告警，时间由后端统一管理）
AI_FORBIDDEN_TIME_FIELDS = ("thedate", "dtEventTimeStamp")
# AI 输出中禁止出现的条件字段（后端剔除并告警）：
# - 时间字段：时间由后端统一管理（start_time/end_time 顶层协议）
# - system_id：检索范围由 scope_id 唯一决定并做权限注入，AI 偷带该条件会与注入条件
#   AND 组合——值不一致时恒假零命中（用户侧表现为"静默查空"），冗余时污染条件回显
AI_FORBIDDEN_CONDITION_FIELDS = AI_FORBIDDEN_TIME_FIELDS + ("system_id",)

# ---------------------------------------------------------------------------
# F4 导出
# ---------------------------------------------------------------------------

# D4 默认实现：后端生成全量导出任务名，{prefix} 为 message_uid 前 8 位
AI_EXPORT_TASK_NAME_TEMPLATE = gettext_lazy("AI助手检索导出-%s")
