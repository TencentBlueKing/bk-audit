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

# 模拟事件数据
MOCK_EVENTS = [
    {
        "event_id": "evt001",
        "account": "game_admin_001",
        "username": "zhangsan",
        "amount": 100000,
        "event_time": "2025-12-17 04:57:25",
    },
    {
        "event_id": "evt002",
        "account": "game_admin_002",
        "username": "lisi",
        "amount": 150000,
        "event_time": "2025-12-17 05:10:30",
    },
    {
        "event_id": "evt003",
        "account": "game_admin_001",
        "username": "zhangsan",
        "amount": 250000,
        "event_time": "2025-12-17 05:30:00",
    },
]

# 模拟风险数据
MOCK_RISK = {
    "risk_id": "20251217045725640665",
    "strategy_name": "虚拟资源发放异常检测",
    "operator": "张三",
    "risk_level": "高危",
    "event_time": "2025-12-17 04:57:25",
}

# 测试模板
TEST_TEMPLATE = """# {{ risk.strategy_name }}：{{ risk.operator }} 存在疑似违规事件

## 一、事件概述
{{ ai.summary }}

## 二、事件主体信息
| 项目 | 内容 |
|------|------|
| 涉事账号 | {{ first(event.account) }} |
| 涉事人员 | {{ risk.operator }} |
| 涉事金额 | ¥{{ sum(event.amount) }} |
| 事件数量 | {{ count(event.event_id) }} |
| 首次发现 | {{ risk.event_time }} |

### 涉事人员列表
{{ unique_list(event.username) }}

## 三、发现策略
- 策略名称：{{ risk.strategy_name }}
- 风险等级：{{ risk.risk_level }}
"""

# 简单模板（仅普通变量）
SIMPLE_TEMPLATE = """# {{ risk.strategy_name }}

风险等级：{{ risk.risk_level }}
操作人：{{ risk.operator }}
"""

# 仅事件聚合函数模板
EVENT_ONLY_TEMPLATE = """事件数量：{{ count(event.event_id) }}
第一个账号：{{ first(event.account) }}
最后一个账号：{{ last(event.account) }}
总金额：{{ sum(event.amount) }}
唯一用户：{{ unique_list(event.username) }}
"""

# AI变量配置
MOCK_AI_VARIABLES_CONFIG = [
    {
        "name": "ai.summary",
        "prompt_template": "请基于以下风险信息，用2-3句话概述事件情况",
    },
    {
        "name": "ai.suggestion",
        "prompt_template": "请给出处置建议",
    },
]

# 模拟AI响应
MOCK_AI_RESPONSE = {
    "content": "2025年12月17日，审计系统检测到XX游戏账号存在异常虚拟资源发放行为。",
}
