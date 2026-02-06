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
