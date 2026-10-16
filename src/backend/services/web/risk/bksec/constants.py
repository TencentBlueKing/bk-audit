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

# SOPS 插件「审计中心WeSec发单」(v1.0.0) 入参契约：
# 插件 Inputs 共 15 个参数；
# 其中 ${action}（执行模式 callback/poll）是 SOPS 模板的节点输入
# 由模板分支节点按当前状态配置——首单走 callback 节点（发单后等办结回调），后续重发走 poll 节点（周期检查 event_end_time，有更新则重发）
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
BKSEC_OPERATOR_TEMPLATE = '{{ (risk.operator or risk.security_person or "").split(";") | tojson }}'

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
BKSEC_REQUIRED_FIELDS = [BKSEC_FIELD_RISK_ASSET, BKSEC_FIELD_INITIAL_OWNER]

# 事件体附加字段
BKSEC_EVENT_FIELD_RISK_TYPE = "risk_type"
BKSEC_EVENT_FIELD_FIELDS = "fields"
BKSEC_EVENT_FIELD_RISK_ID = "risk_id"
BKSEC_EVENT_FIELD_SOURCE = "source"
BKSEC_EVENT_SOURCE_VALUE = "bk-audit"
BKSEC_EVENT_FIELD_IS_TEST = "is_test"
BKSEC_EVENT_FIELD_TEST_OPERATOR = "test_operator"

# 查询类接口缓存
BKSEC_RISK_TYPES_CACHE_KEY = "bksec:risk_access:list"
BKSEC_RISK_TYPE_CACHE_KEY = "bksec:risk_access:{risk_type_id}"
BKSEC_CACHE_TIMEOUT = 300

# 渲染上下文加载事件的上限（预览与发单共用）
BKSEC_RENDER_EVENT_LIMIT = 100
