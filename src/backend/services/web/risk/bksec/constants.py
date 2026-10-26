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
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

from django.utils.translation import gettext_lazy

from core.choices import TextChoices

# SOPS 插件「审计中心WeSec发单」(v1.0.0) 入参契约：
# 插件 Inputs 共 15 个参数；
# 其中 ${action}（执行模式 callback/poll）是 SOPS 模板的节点输入
# 由模板分支节点按当前状态配置——首单走 callback 节点，后续重发走 poll 节点（周期检查 event_end_time，有新事件则更新工单）
# 审计侧实际传入 14 个入参，按取值形态分两类：

# ① 风险字段映射（field 形态，9 个）：
#    配方 {"field": 风险字段名, "value": ""}，AutoProcess 运行时 getattr(risk, field) 平铺取值；
#    dict/list 字段（如 event_type/event_data）统一序列化为 JSON 串。
BKSEC_PLUGIN_STANDARD_FIELDS = {
    "${risk_id}": "risk_id",
    "${event_content}": "event_content",
    "${event_evidence}": "event_evidence",
    "${event_type}": "event_type",
    "${event_data}": "event_data",
    "${event_time}": "event_time",
    "${event_source}": "event_source",
    "${strategy_id}": "strategy_id",
    "${raw_event_id}": "raw_event_id",
}

# ② 特殊来源入参（value 形态，5 个）：
# 在策略配置页配置，支持文字+变量混排
BKSEC_PARAM_RISK_TYPE_EXTRA = "${risk_type_extra}"
BKSEC_PARAM_OPERATOR = "${operator}"
BKSEC_PARAM_TARGET_TYPE = "${target_type}"
BKSEC_PARAM_TARGET = "${target}"
# 测试单once_task=yes,正式单once_task=no
BKSEC_PARAM_ONCE_TASK = "${once_task}"

# 插件控制参数默认值
BKSEC_ONCE_TASK_DEFAULT = "no"
BKSEC_ONCE_TASK_TEST = "yes"
# 责任人脏值：渲染上下文中可能出现字符串 "None"/"null"（上游数据质量问题），序列化前需剔除
BKSEC_INVALID_PERSON_VALUES = frozenset({"none", "null", "undefined", "nan"})


# 预置处理套餐
BKSEC_PRESET_PA_NAME = gettext_lazy("【内置】BKSEC安全工单发单")
BKSEC_PRESET_PA_DESCRIPTION = gettext_lazy("策略 BKSEC 安全工单发单内置套餐，由系统维护，请勿删除或停用")

# 自动规则保留优先级段（结构性保证：启用 BKSEC 的发单规则恒高于一切手动规则，与创建先后无关）：
#   [BKSEC_RULE_PRIORITY_BASE, +∞) 专属自动规则；手动规则的优先级来源须排除本段（创建时 max 只统计段下值）
BKSEC_RULE_PRIORITY_BASE = 9000

# 自动创建的处理规则
BKSEC_AUTO_RULE_NAME = gettext_lazy("【自动】策略 %s BKSEC发单")

BKSEC_FIELD_RISK_ASSET = "target"
BKSEC_FIELD_INITIAL_OWNER = "operator"
BKSEC_FIELD_TARGET_TYPE = "target_type"

# 必填字段白名单：仅上述三个独立入参必填，风险类型的其余字段一律非必填。
# BKSEC risk_access 接口不返回 required，此处为审计中心侧的判定口径，
# 与 BkSecConfig.validate_for_submit 的提交校验保持同源。
BKSEC_REQUIRED_FIELD_KEYS = (BKSEC_FIELD_RISK_ASSET, BKSEC_FIELD_TARGET_TYPE, BKSEC_FIELD_INITIAL_OWNER)


class BkSecConfigSyncStage(TextChoices):
    """BKSEC 插件配置同步场景（BkSecConfigSyncFailedEvent 的 stage 维度）"""

    STRATEGY_SAVE = "strategy_save", gettext_lazy("保存策略")
    TEST_SEND = "test_send", gettext_lazy("测试发送")


class BkSecConfigSyncFailReason(TextChoices):
    """BKSEC 插件配置同步失败原因（BkSecConfigSyncFailedEvent 的 fail_reason 维度）"""

    API_URL_MISSING = "api_url_missing", gettext_lazy("插件配置地址未配置")
    TOKEN_MISSING = "token_missing", gettext_lazy("risk_access 未返回对应 token")
    TOKEN_FETCH_FAILED = "token_fetch_failed", gettext_lazy("获取 token 失败")
    UPSERT_REJECTED = "upsert_rejected", gettext_lazy("插件拒绝写入 Config")
    API_UNREACHABLE = "api_unreachable", gettext_lazy("插件配置接口不可达")


# 查询类接口缓存（只读展示场景，容忍短暂陈旧；token 等凭证查找不走缓存）
BKSEC_RISK_TYPES_CACHE_KEY = "bksec:risk_access:list"
BKSEC_CACHE_TIMEOUT = 300

# risk_access 列表翻页参数：响应为分页结构（count/results），单页取会截断
# （token 漏匹配、下拉缺项），统一循环翻页取全量
BKSEC_RISK_ACCESS_PAGE_SIZE = 100
BKSEC_RISK_ACCESS_MAX_PAGES = 50

# 渲染上下文加载事件的上限（预览与发单共用）
BKSEC_RENDER_EVENT_LIMIT = 100

# 测试节点状态回写时扫描的最近节点数：
# process_result 中 task_id 的类型取决于 SOPS 返回（int/str），JSONField 路径查询类型敏感，
# 直接按字符串过滤会漏匹配，需取最近节点逐个比对
BKSEC_TEST_NODE_SCAN_LIMIT = 50
