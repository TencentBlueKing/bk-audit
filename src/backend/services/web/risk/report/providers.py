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
from functools import cached_property
from typing import Any, Callable, Dict, Optional, Type

from bk_resource import api
from bk_resource.utils.cache import CacheTypeItem, using_cache
from blueapps.utils.logger import logger
from django.conf import settings
from django.db.models import Max
from jinja2 import nodes
from jinja2.nodes import Expr

from core.sql.constants import AggregateType, FieldType
from services.web.risk.constants import (
    AGGREGATION_FUNCTION_TO_SQL_TYPE,
    AI_ERROR_PREFIX,
    AI_ERROR_SUFFIX,
    DEFAULT_FIELD_TYPE_BY_AGGREGATE,
    EVENT_QUERY_FAILED,
    AggregationFunction,
)
from services.web.risk.handlers.event_provider_sql import (
    EventFieldConfig,
    RiskEventAggregateSqlBuilder,
)
from services.web.risk.models import Risk
from services.web.strategy_v2.models import Strategy, StrategyTool
from services.web.tool.models import Tool


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
    调用AI Agent生成内容，支持缓存
    """

    # 缓存配置
    _cache_type = CacheTypeItem(key="ai_provider", timeout=settings.AI_PROVIDER_CACHE_TIMEOUT, user_related=False)

    def __init__(
        self,
        context: dict[str, Any],
        ai_variables_config: list[dict] = None,
        ai_executor: Callable = None,
        key: str = "ai",
        enable_cache: bool = False,
    ):
        """初始化AI Provider

        Args:
            context: 上下文信息，包含 risk_id 等
            ai_variables_config: AI变量配置列表，包含 name 和 prompt_template
            ai_executor: 自定义的AI执行器，用于测试时注入mock
            key: Provider的key，默认为 ai
            enable_cache: 是否启用缓存，默认关闭
        """
        self.context = context
        self.ai_variables_config = {var["name"]: var for var in (ai_variables_config or [])}
        self._ai_executor = ai_executor
        self.key = key
        self.enable_cache = enable_cache

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

        # 根据 enable_cache 动态包装 _execute_ai_agent
        if self.enable_cache:
            return using_cache(
                cache_type=self._cache_type,
                compress=True,
                is_cache_func=self._cache_write_trigger,
                func_key_generator=lambda _: self._generate_cache_key(),
            )(self._execute_ai_agent)(prompt)

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

        try:
            result = api.bk_plugins_ai_audit_report.chat_completion(
                user=self.context.get("user", "admin"),  # 会话用户名，通过 X-BKAIDEV-USER 请求头传递
                input=f'当前分析的Risk ID是{self.context["risk_id"]}。若后续无其他要求，返回标准的Markdown格式。\n' + prompt,
                chat_history=[],
                execute_kwargs={"stream": True},
            )
            if isinstance(result, dict):
                return result.get("choices", [{}])[0].get("delta", {}).get("content", "")
            return result or ""
        except Exception as e:
            return f"{AI_ERROR_PREFIX}{e}{AI_ERROR_SUFFIX}"

    def _generate_cache_key(self) -> str:
        """生成缓存 key 的业务部分

        完整缓存 key 由 UsingCache 自动组装，格式为：
            {key_prefix}:{cache_type.key}:{func_key}:{args_md5}
        其中：
            - func_key: 本方法返回的业务 key（risk_id:策略时间:工具时间:事件数）
            - args_md5: UsingCache 自动计算的 prompt 参数 MD5

        因此，完整缓存 key 包含以下失效因子：
            1. risk_id - 风险唯一标识
            2. strategy_updated_at - 策略更新时间（策略配置变更时失效）
            3. tools_max_updated_at - 工具最新更新时间（AI 工具变更时失效）
            4. event_count - 事件数量（新增事件时失效）
            5. prompt - 提示词内容（prompt 变化时失效，由 UsingCache 自动处理）
        """
        risk = self._risk
        if not risk:
            logger.warning("[AIProvider] Cache key=unknown; risk not found")
            return "unknown"

        cache_key = (
            f"{risk.risk_id}:"
            f"{self._get_strategy_updated_at(risk)}:"
            f"{self._get_tools_max_updated_at(risk.strategy_id)}:"
            f"{self._get_event_count(risk)}"
        )
        logger.info("[AIProvider] Cache key=%s", cache_key)
        return cache_key

    def _cache_write_trigger(self, result: Any) -> bool:
        """仅成功结果写入缓存"""
        risk_id = self.context["risk_id"]
        if not result:
            logger.info("[AIProvider] Cache skip; risk_id=%s, reason=empty_result", risk_id)
            return False
        if isinstance(result, str) and result.startswith(AI_ERROR_PREFIX):
            logger.info("[AIProvider] Cache skip; risk_id=%s, reason=error_result", risk_id)
            return False
        logger.info("[AIProvider] Cache write; risk_id=%s, result_len=%d", risk_id, len(result) if result else 0)
        return True

    @cached_property
    def _risk(self) -> Optional[Risk]:
        """获取 Risk 对象（实例级别缓存，避免重复查询）"""
        risk_id = self.context["risk_id"]
        if not risk_id:
            return None
        return Risk.objects.select_related("strategy").filter(risk_id=risk_id).first()

    def _get_strategy_updated_at(self, risk: Risk) -> str:
        """获取策略更新时间"""
        if risk.strategy and risk.strategy.updated_at:
            return risk.strategy.updated_at.strftime("%Y%m%d%H%M%S")
        return ""

    def _get_tools_max_updated_at(self, strategy_id: int) -> str:
        """获取策略关联工具的最新更新时间（仅查询最新版本的工具）"""
        tool_uids = list(
            StrategyTool.objects.filter(strategy_id=strategy_id).values_list("tool_uid", flat=True).distinct()
        )
        if not tool_uids:
            return ""
        # 使用 all_latest_tools 确保只查询每个工具的最新版本
        max_updated = (
            Tool.all_latest_tools().filter(uid__in=tool_uids).aggregate(max_updated=Max("updated_at"))["max_updated"]
        )
        return max_updated.strftime("%Y%m%d%H%M%S") if max_updated else ""

    def _get_event_count(self, risk: Risk) -> int:
        """使用 RiskEventAggregateSqlBuilder 查询事件数量"""
        try:
            builder = RiskEventAggregateSqlBuilder(risk)
            count_field = EventFieldConfig(
                raw_name="*",
                display_name="cnt",
                field_type=FieldType.LONG,
                aggregate=AggregateType.COUNT,
            )
            sql = builder.build_aggregate_sql([count_field])
            logger.info("[AIProvider] Event count SQL: %s", sql)
            if not sql:
                return 0

            result = api.bk_base.query_sync(sql=sql)
            return result.get("list", [{}])[0].get("cnt", 0)
        except Exception as e:
            logger.warning("[AIProvider] Failed to get event count: %s", e)
            return 0


class EventProvider(Provider):
    """事件数据Provider

    用于处理事件相关的聚合函数，如 first(event.account), count(event.event_id) 等

    架构：
    1. match() 解析 Jinja2 AST，识别 count(event.field) 等语法
    2. get() 构造 SQL 查询 BKBase Doris 表并返回聚合数据

    初始化：只接受 risk_id，内部惰性加载 Risk 对象。
    """

    # Provider的唯一标识key
    key: str = "event"

    def __init__(self, risk_id: str, **kwargs):
        """初始化事件Provider

        Args:
            risk_id: 风险ID，用于惰性加载 Risk 对象
            **kwargs: 其他参数
        """
        self._risk_id: str = risk_id
        self._risk: Risk = None

    @property
    def risk_id(self) -> str:
        """获取风险ID"""
        return self._risk_id

    @property
    def risk(self) -> Risk:
        """惰性加载 Risk 对象"""
        if self._risk is None and self._risk_id:
            self._risk = Risk.objects.select_related("strategy").filter(risk_id=self._risk_id).first()
        return self._risk

    def _get_field_type_from_strategy(self, field_name: str) -> Optional[str]:
        """从策略 configs.select 获取字段的真实类型

        Args:
            field_name: 字段名（对应 select.display_name）

        Returns:
            field_type 字符串，如 'string', 'long' 等；不存在则返回 None
        """
        strategy: Strategy = getattr(self.risk, "strategy", None)
        if not strategy:
            logger.warning("No strategy found for risk: %s", self.risk_id)
            return None

        configs = strategy.configs
        if not configs or not isinstance(configs, dict):
            logger.info("No configs found for strategy: %s", strategy.strategy_id)
            return None

        select_fields = configs.get("select", [])
        if not select_fields:
            logger.info("No select fields found for strategy: %s", strategy.strategy_id)
            return None

        field_type_map = {
            select["display_name"]: select["field_type"] for select in select_fields if select.get("field_type")
        }

        return field_type_map.get(field_name)

    def _get_field_type(self, field_name: str, aggregate: str) -> FieldType:
        """获取字段类型：优先从策略获取，fallback 根据聚合类型"""
        field_type_str = self._get_field_type_from_strategy(field_name)
        if field_type_str:
            try:
                return FieldType(field_type_str.lower())
            except ValueError:
                logger.error("Invalid field type: %s", field_type_str)
                pass
        # fallback: 根据聚合类型取默认值
        logger.debug("No field type found for field: %s", field_name)
        return DEFAULT_FIELD_TYPE_BY_AGGREGATE.get(aggregate, FieldType.STRING)

    def _build_sql(self, key: str, spec: Dict[str, Any]) -> Optional[str]:
        """构建查询 SQL"""
        aggregate = spec.get("aggregate", "")
        field_name = spec.get("field", key)
        field_type = self._get_field_type(field_name, aggregate)

        builder = RiskEventAggregateSqlBuilder(self.risk)

        field_config = EventFieldConfig(
            raw_name=field_name,
            display_name=key,
            field_type=field_type,
        )

        sql: Optional[str] = None
        if aggregate == AggregationFunction.FIRST:
            sql = builder.build_first_sql([field_config])
        elif aggregate == AggregationFunction.LATEST:
            sql = builder.build_latest_sql([field_config])
        else:
            # 聚合查询
            sql_aggregate = AGGREGATION_FUNCTION_TO_SQL_TYPE.get(aggregate)
            if sql_aggregate:
                field_config.aggregate = sql_aggregate
            sql = builder.build_aggregate_sql([field_config])

        return sql

    def _parse_result(self, result: Dict[str, Any], key: str, aggregate: str) -> Any:
        """解析查询结果

        Args:
            result: BKBase 查询结果
            key: 字段名（用于取值）
            aggregate: 聚合函数名

        Returns:
            查询结果值，list/list_distinct 返回逗号拼接的字符串
        """
        data_list = result.get("list", [])
        if not data_list:
            return None
        row = data_list[0]
        return row.get(key)

    def match(self, node: nodes.Node, **kwargs) -> ProviderMatchResult:
        """判断是否是事件聚合函数调用

        匹配形如 count(event.field) 的函数调用

        返回的 call_args 格式需与渲染器兼容：
        {"function": "count", "args": ["event.field"], "kwargs": {}, "field_name": "field"}
        """
        # 只处理函数调用节点
        if not isinstance(node, nodes.Call):
            return ProviderMatchResult(matched=False)

        # 检查是否是简单的函数调用（函数名是 Name 节点）
        if not isinstance(node.node, nodes.Name):
            return ProviderMatchResult(matched=False)

        func_name = node.node.name

        # 检查是否是 AggregationFunction 枚举中支持的函数
        if func_name not in AggregationFunction.values:
            return ProviderMatchResult(matched=False)

        # 检查是否有参数
        if not node.args:
            return ProviderMatchResult(matched=False)

        # 第一个参数应该是 event.field 形式的属性访问
        first_arg = node.args[0]
        if not isinstance(first_arg, nodes.Getattr):
            return ProviderMatchResult(matched=False)

        # 检查 base 是否是 'event'
        if not isinstance(first_arg.node, nodes.Name):
            return ProviderMatchResult(matched=False)

        if first_arg.node.name != self.key:
            return ProviderMatchResult(matched=False)

        field_name = first_arg.attr
        original_expr = f"{func_name}({self.key}.{field_name})"

        return ProviderMatchResult(
            matched=True,
            original_expr=original_expr,
            provider=self,
            node_type=nodes.Call,
            call_args={
                "function": func_name,
                "field_name": field_name,
                # 以下字段用于渲染器的 hash 计算
                "args": [f"{self.key}.{field_name}"],
                "kwargs": {},
            },
        )

    def get(self, function: str = None, field_name: str = None, **extra) -> Any:
        """获取事件聚合数据

        Args:
            function: 聚合函数名，如 first, count, sum 等
            field_name: 字段名

        Returns:
            查询结果单值，失败返回占位符
        """
        if not function or not field_name:
            return None

        # 验证函数名是否合法
        if function not in AggregationFunction.values:
            return None

        # 构建 spec 供内部方法使用
        spec = {"aggregate": function, "field": field_name}

        try:
            sql = self._build_sql(field_name, spec)
            logger.info(
                "[EventProvider] Build SQL. risk_id=%s, field=%s, function=%s, sql=%s",
                self.risk_id,
                field_name,
                function,
                sql,
            )
            if not sql:
                return EVENT_QUERY_FAILED

            result = api.bk_base.query_sync(sql=sql)
            return self._parse_result(result, field_name, function)
        except Exception as e:  # NOCC:broad-except(需要处理所有错误)
            logger.exception(
                "[EventProvider] Query failed. risk_id=%s, field=%s, function=%s, error=%s",
                self.risk_id,
                field_name,
                function,
                e,
            )
            return EVENT_QUERY_FAILED
