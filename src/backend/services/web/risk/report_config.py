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

from typing import Dict, List

from drf_pydantic import BaseModel
from pydantic import Field


class AIVariableConfig(BaseModel):
    """
    AI 变量配置

    用于配置 AI 生成的变量。
    """

    name: str = Field(..., description="变量名，用于 {{ ai.xxx }} 模板引用，同时也作为前端展示名")
    prompt_template: str = Field("", description="AI 提示词模板")


class ReportConfig(BaseModel):
    """
    报告配置

    包含三类变量：
    1. 风险变量：不需要配置，直接用 risk.* 引用
    2. 事件变量：不需要单独配置，模板中直接使用 {{ count(event.event_id) }} 语法
    3. AI 变量：需要配置，由 AI 服务生成

    模板语法示例：
    - 风险变量：{{ risk.risk_id }}、{{ risk.title }}
    - 事件变量：{{ count(event.event_id) }}、{{ list_distinct(event.username) }}
    - AI 变量：{{ ai.summary }}
    """

    template: str = Field("", description="Jinja2 模板内容")
    frontend_template: str = Field("", description="前端报告模板，仅用于前端存储展示")
    ai_variables: List[AIVariableConfig] = Field(default_factory=list, description="AI 变量配置列表")

    def get_ai_var_names(self) -> Dict[str, AIVariableConfig]:
        """
        获取 AI 变量名称映射

        Returns:
            {"summary": AIVariableConfig, ...}  # key 是 name
        """
        return {var.name: var for var in self.ai_variables}
