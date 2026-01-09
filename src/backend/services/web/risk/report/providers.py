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

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Type

from jinja2 import nodes
from jinja2.nodes import Expr


@dataclass
class ProviderMatchResult:
    """Provider匹配结果"""

    matched: bool  # 是否匹配
    original_expr: Optional[str] = None  # 原始表达式，如 first(event.account) 或 ai.summary
    node_type: Optional[Type[Expr]] = None  # 匹配到的节点类型
    provider: "Provider" = None  # 匹配到的Provider实例
    # 额外的调用参数，由Provider.match时填充，Provider.get时使用
    call_args: dict = field(default_factory=dict)


class Provider(abc.ABC):
    """Provider基类，用于提供模板渲染所需的数据"""

    # Provider的唯一标识key
    key: str = None

    @abc.abstractmethod
    def match(self, node: nodes.Node, **kwargs) -> ProviderMatchResult:
        """判断AST节点是否由该Provider处理

        Args:
            node: Jinja2 AST节点
            **kwargs: 额外参数

        Returns:
            ProviderMatchResult: 匹配结果，包含matched、original_expr和provider实例
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get(self, **kwargs) -> Any:
        """获取数据的统一接口

        Args:
            **kwargs: 不同类型的Provider有不同的参数

        Returns:
            获取到的数据
        """
        raise NotImplementedError


class AIProvider(Provider):
    """AI变量Provider

    用于处理AI变量，如 ai.summary, ai.suggestion 等
    调用AI Agent生成内容
    """

    def __init__(
        self,
        context: dict[str, Any],
        ai_variables_config: list[dict] = None,
        ai_executor: Callable = None,
        key: str = "ai",
    ):
        """初始化AI Provider

        Args:
            context: 上下文信息，包含 risk_id 等
            ai_variables_config: AI变量配置列表，包含 name 和 prompt_template
            ai_executor: 自定义的AI执行器，用于测试时注入mock
            key: Provider的key，默认为 ai
        """
        self.context = context
        self.ai_variables_config = {var["name"]: var for var in (ai_variables_config or [])}
        self._ai_executor = ai_executor
        self.key = key

    def match(self, node: nodes.Node, **kwargs) -> ProviderMatchResult:
        """判断是否是AI变量访问

        匹配形如 ai.summary 的属性访问：
        - node 是 Getattr 节点
        - node.node 是基础名（Name节点），且等于该Provider的key

        Args:
            node: Jinja2 AST节点

        Returns:
            ProviderMatchResult: 匹配结果
        """
        # 只处理属性访问节点
        if not isinstance(node, nodes.Getattr):
            return ProviderMatchResult(matched=False)

        # 检查是否是简单的属性访问（基础是Name节点）
        if not isinstance(node.node, nodes.Name):
            return ProviderMatchResult(matched=False)

        base_name = node.node.name

        # 检查base_name是否匹配
        if base_name != self.key:
            return ProviderMatchResult(matched=False)

        field_name = node.attr
        original_expr = f"{self.key}.{field_name}"

        return ProviderMatchResult(
            matched=True,
            original_expr=original_expr,
            provider=self,
            node_type=nodes.Getattr,
            call_args={"name": original_expr},  # 使用完整的变量表达式，如 ai.summary
        )

    def get(self, prompt: str = None, name: str = None, **kwargs) -> str:
        """获取AI生成的内容

        Args:
            prompt: AI提示词（可选，如果提供则直接使用）
            name: AI变量名，如 summary, suggestion（用于从配置中查找prompt）

        Returns:
            AI生成的内容
        """
        # 如果没有提供prompt，从配置中查找
        if not prompt and name:
            var_key = f"ai.{name}" if not name.startswith("ai.") else name
            config = self.ai_variables_config.get(var_key, {})
            prompt = config.get("prompt_template") or config.get("prompt")

        if not prompt:
            return f"[AI变量 {name} 未配置prompt]"

        # 调用AI Agent生成内容
        return self._execute_ai_agent(prompt)

    def _execute_ai_agent(self, prompt: str) -> str:
        """执行AI Agent生成内容

        Args:
            prompt: 提示词

        Returns:
            AI生成的内容
        """
        # 如果提供了自定义执行器，使用它
        if self._ai_executor:
            return self._ai_executor(prompt)

        # 调用ai-audit-report服务的chat_completion接口
        from bk_resource import api

        try:
            result = api.bk_plugins_ai_audit_report.chat_completion(
                user=self.context.get("user", "admin"),  # 会话用户名，通过 X-BKAIDEV-USER 请求头传递
                input=f'当前分析的Risk ID是{self.context["risk_id"]}\n' + prompt,
                chat_history=[],
                execute_kwargs={"stream": False},
            )
            return result.get("content", "")
        except Exception as e:
            return f"[AI生成失败: {e}]"


class EventProvider(Provider):
    """事件数据Provider

    用于处理事件相关的聚合函数，如 first(event.account), count(event.event_id) 等

    注意：具体实现由其他同事完成，这里只定义接口规范
    """

    # Provider的唯一标识key
    key: str = "event"

    def __init__(self, risk_id: str = None, **kwargs):
        """初始化事件Provider

        Args:
            risk_id: 风险ID，用于获取关联的事件数据
            **kwargs: 其他参数
        """
        self.risk_id = risk_id

    def match(self, node: nodes.Node, **kwargs) -> ProviderMatchResult:
        """判断是否是事件聚合函数调用

        由子类实现具体的匹配逻辑
        """
        raise NotImplementedError

    def get(self, function: str = None, args: list = None, kwargs: dict = None, **extra) -> Any:
        """获取事件聚合数据

        由子类实现具体的数据获取逻辑

        Args:
            function: 聚合函数名，如 first, count, sum 等
            args: 位置参数列表
            kwargs: 关键字参数字典
        """
        raise NotImplementedError
