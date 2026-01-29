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

import re
from typing import ClassVar, Dict, List, Type

from drf_pydantic import BaseModel
from pydantic import Field, field_validator
from rest_framework import serializers

# Jinja 变量名正则: 必须以字母、下划线或中文开头，只能包含字母、数字、下划线和中文
JINJA_VAR_NAME_PATTERN = re.compile(r"^[a-zA-Z_\u4e00-\u9fa5][a-zA-Z0-9_\u4e00-\u9fa5]*$")


class AIVariableConfig(BaseModel):
    """
    AI 变量配置

    用于配置 AI 生成的变量。
    """

    PREDEFINED_PROMPT_TEMPLATE: ClassVar[
        str
    ] = """
!!!请严格遵循以下规则：!!!
1. 思考过程保持简洁。
2. 工具调用失败最多只重试一次。
4. 若调用下钻工具，必须先根据风险ID获取策略配置中的下钻工具配置；
   调用 execute_drill_tool（或 MCP 中的 execute_tool 变体）时，确保 tool_variables 的 raw_name
   与下钻配置中的 source_field 一致，且需要传的参数都传齐。
5. 调用 MCP 工具时务必附带 path_param 或 query_param，且参数准确。
6. 输出必须为 Markdown，内容简洁明了，不得虚构事实。
!!!调用 MCP 工具时务必附带 path_param 或 query_param，且参数准确。!!!
"""

    # 缓存生成的 DRF 序列化器类
    _drf_serializer_class: ClassVar[Type[serializers.Serializer]] = None

    name: str = Field(..., description="变量名，用于 {{ ai.xxx }} 模板引用，同时也作为前端展示名")
    prompt_template: str = Field("", description="AI 提示词模板")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """验证 AI 变量名必须以 ai. 开头，且符合 Jinja 变量名规范"""
        if not value.startswith("ai."):
            raise ValueError("AI变量名必须以 'ai.' 开头")

        # 提取 ai. 后面的变量名部分进行 Jinja 变量名规范验证
        var_name = value[3:]  # 去掉 'ai.' 前缀
        if not var_name:
            raise ValueError("AI变量名不能只有 'ai.' 前缀")

        if not JINJA_VAR_NAME_PATTERN.match(var_name):
            raise ValueError("AI变量名必须符合 Jinja 变量名规范：以字母、下划线或中文开头，只能包含字母、数字、下划线和中文")

        return value

    @field_validator("prompt_template")
    @classmethod
    def validate_prompt_template(cls, value: str) -> str:
        """将预定义的 prompt 模板添加到用户传入的 prompt 前面"""
        return cls.PREDEFINED_PROMPT_TEMPLATE + '\n' + value

    @classmethod
    def drf_serializer_with_validation(cls) -> Type[serializers.Serializer]:
        """
        返回带有验证方法的 DRF 序列化器类

        drf_pydantic 的 drf_serializer() 只会映射字段，不会继承 pydantic 的 field_validator。
        这个方法返回一个扩展的序列化器类，添加了 DRF 的验证方法。
        """
        if cls._drf_serializer_class is not None:
            return cls._drf_serializer_class

        # 获取 drf_pydantic 生成的基础序列化器类
        base_serializer = type(cls.drf_serializer())

        # 创建验证方法的闭包，引用 cls 的常量
        predefined_template = cls.PREDEFINED_PROMPT_TEMPLATE
        var_pattern = JINJA_VAR_NAME_PATTERN

        class AIVariableConfigSerializerWithValidation(base_serializer):
            """带有验证方法的 AIVariableConfig 序列化器"""

            def validate_name(self, value: str) -> str:
                """验证 AI 变量名必须以 ai. 开头，且符合 Jinja 变量名规范"""
                if not value.startswith("ai."):
                    raise serializers.ValidationError("AI变量名必须以 'ai.' 开头")

                # 提取 ai. 后面的变量名部分进行 Jinja 变量名规范验证
                var_name = value[3:]  # 去掉 'ai.' 前缀
                if not var_name:
                    raise serializers.ValidationError("AI变量名不能只有 'ai.' 前缀")

                if not var_pattern.match(var_name):
                    raise serializers.ValidationError("AI变量名必须符合 Jinja 变量名规范：以字母、下划线或中文开头，只能包含字母、数字、下划线和中文")

                return value

            def validate_prompt_template(self, value: str) -> str:
                """将预定义的 prompt 模板添加到用户传入的 prompt 前面"""
                return predefined_template + '\n' + value

        cls._drf_serializer_class = AIVariableConfigSerializerWithValidation
        return cls._drf_serializer_class


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
