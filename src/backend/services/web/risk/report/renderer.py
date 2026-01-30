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

import hashlib
import json
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Type

from blueapps.core.celery import celery_app
from blueapps.utils.logger import logger_celery
from jinja2 import Environment, nodes
from markupsafe import Markup

from services.web.risk.report.markdown import render_ai_markdown
from services.web.risk.report.providers import Provider


class ProviderNamespace:
    """Provider命名空间，用于支持 provider.field 语法

    支持任意层级的属性访问，如 event.account.name
    在Jinja2渲染时，会被转换为字符串路径用于查找预计算的结果
    """

    def __init__(self, name: str):
        self._name = name

    def __getattr__(self, attr: str):
        # 返回新的命名空间对象，支持链式访问
        return ProviderNamespace(f"{self._name}.{attr}")

    def __repr__(self):
        return self._name


@dataclass
class ProviderCall:
    """Provider调用信息

    简化设计：存储原始表达式、Provider实例和调用参数
    执行时直接使用存储的provider实例
    """

    original_expr: str  # 原始表达式，如 first(event.account) 或 ai.summary
    provider: Provider  # 匹配到的Provider实例
    call_args: dict  # 调用参数，若node_type是nodes.Call：
    # {"function": "first", "args": ["event.account"], "kwargs": {"mode":"quick"}}，
    # 若是GetAttr： {"name": "ai.summary"}
    node_type: Type[nodes.Expr]


class TemplateParser:
    """使用Jinja2 AST解析模板，提取Provider调用

    与具体Provider实现解耦，通过Provider.match()方法判断节点是否由某个Provider处理
    """

    def __init__(self, template: str, providers: list[Provider]):
        """初始化模板解析器

        Args:
            template: Jinja2模板字符串
            providers: Provider列表
        """
        self.template = template
        self.providers = providers
        self.env = Environment()
        self.provider_calls: list[ProviderCall] = []
        self._processed_exprs: set[str] = set()  # 用于去重

    def parse(self) -> list[ProviderCall]:
        """解析模板，提取所有Provider调用

        Returns:
            ProviderCall列表
        """
        try:
            ast = self.env.parse(self.template)
            self._visit_node(ast)
        except Exception as e:
            logger_celery.exception("[TemplateParser] Failed to parse template: %s", e)

        return self.provider_calls

    def _visit_node(self, node: nodes.Node) -> None:
        """递归遍历AST节点

        Args:
            node: Jinja2 AST节点
        """
        # 尝试用所有Provider的match方法匹配当前节点
        self._try_match_providers(node)

        # 递归处理子节点
        for child in node.iter_child_nodes():
            self._visit_node(child)

    def _try_match_providers(self, node: nodes.Node) -> None:
        """尝试用所有Provider匹配当前节点

        Args:
            node: Jinja2 AST节点
        """
        if not isinstance(node, nodes.Expr):
            return
        for provider in self.providers:
            match_result = provider.match(node)

            if match_result.matched:
                # 检查是否已经处理过（去重）
                if match_result.original_expr in self._processed_exprs:
                    continue

                self._processed_exprs.add(match_result.original_expr)

                self.provider_calls.append(
                    ProviderCall(
                        original_expr=match_result.original_expr,
                        provider=match_result.provider,
                        call_args=match_result.call_args,
                        node_type=type(node),
                    )
                )

                # 找到匹配的Provider后，不再尝试其他Provider
                break


def _parse_template(template: str, providers: list[Provider] = None) -> list[ProviderCall]:
    """解析模板，提取所有需要通过Provider获取的变量/函数调用

    使用Jinja2 AST语法树解析，通过Provider.match()方法判断匹配

    Args:
        template: Jinja2模板字符串
        providers: Provider列表

    Returns:
        ProviderCall列表
    """
    if providers is None:
        providers = []

    parser = TemplateParser(template, providers)
    return parser.parse()


def _execute_provider_call(call: ProviderCall) -> tuple[ProviderCall, Any]:
    """执行单个Provider调用

    Args:
        call: Provider调用信息（包含provider实例和调用参数）

    Returns:
        (调用信息, 结果) 元组
    """
    try:
        # 直接使用存储的provider实例和调用参数
        result = call.provider.get(**call.call_args)
        return call, result
    except Exception as e:
        logger_celery.exception("[RenderTemplate] Provider call failed: %s - %s", call.original_expr, e)
        return call, f"[Error: {e}]"


def _compute_args_hash(args: list, kwargs: dict) -> str:
    """计算args和kwargs的哈希值

    Args:
        args: 位置参数列表
        kwargs: 关键字参数字典

    Returns:
        哈希字符串
    """
    # 将args和kwargs序列化为JSON字符串，然后计算MD5哈希
    hash_input = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    return hashlib.md5(hash_input.encode()).hexdigest()


def _build_render_context(
    provider_calls: list[ProviderCall], results: dict[str, Any], variables: dict[str, Any]
) -> dict[str, Any]:
    """构建Jinja2渲染上下文

    将Provider调用的结果转换为可被Jinja2直接渲染的变量和函数

    Args:
        provider_calls: Provider调用列表
        results: Provider调用结果，key为original_expr
        variables: 用户提供的普通变量

    Returns:
        Jinja2渲染上下文
    """
    context = dict(variables)

    # 为每个聚合函数创建一个包装函数，返回预先计算好的结果
    function_results: dict[str, dict[str, Any]] = {}

    # 记录需要创建命名空间的Provider（用于AI变量等属性访问）
    namespace_providers: dict[str, dict[str, Any]] = {}  # provider_key -> {field_name: result}

    for call in provider_calls:
        call_args = call.call_args
        provider_key = call.provider.key

        # 判断是函数调用还是属性访问（根据node_type）
        if call.node_type is nodes.Call:
            # 聚合函数调用：记录结果
            function_name = call_args["function"]
            args = call_args.get("args", [])
            kwargs = call_args.get("kwargs", {})

            if function_name not in function_results:
                function_results[function_name] = {}

            # 使用args和kwargs生成的hash作为key
            args_hash = _compute_args_hash(args, kwargs)
            function_results[function_name][args_hash] = results.get(call.original_expr, "")
        else:
            # 属性访问（如AI变量）：记录到命名空间
            # call_args["name"] 是完整表达式如 "ai.summary"，需要提取实际属性名 "summary"
            full_name = call_args.get("name", "")
            # 从完整表达式中提取属性名（最后一部分）
            field_name = full_name.split(".")[-1] if "." in full_name else full_name
            if provider_key not in namespace_providers:
                namespace_providers[provider_key] = {}
            # AI变量返回的内容：先使用 markdown 渲染（HTML转义），使用 Markup 防止二次转义
            ai_result = results.get(call.original_expr, "")
            if ai_result:
                html_content = render_ai_markdown(ai_result)
                ai_result = Markup(f'<div class="ai-content">{html_content}</div>')
            namespace_providers[provider_key][field_name] = ai_result

    # 为每个命名空间创建对象（如ai）
    for ns_name, ns_fields in namespace_providers.items():
        ns_obj = type(f"{ns_name.capitalize()}Namespace", (), {})()
        for field_name, value in ns_fields.items():
            setattr(ns_obj, field_name, value)
        context[ns_name] = ns_obj

    # 为每个聚合函数创建包装函数
    for func_name, func_results in function_results.items():
        # 使用闭包捕获func_results
        def make_wrapper(results_map):
            def wrapper(*args, **kwargs):
                # 将参数转换为可序列化的形式（ProviderNamespace对象转为字符串路径）
                serializable_args = [arg._name if isinstance(arg, ProviderNamespace) else str(arg) for arg in args]
                serializable_kwargs = {
                    k: v._name if isinstance(v, ProviderNamespace) else str(v) for k, v in kwargs.items()
                }

                # 计算args_hash并查找结果
                args_hash = _compute_args_hash(serializable_args, serializable_kwargs)
                return results_map.get(args_hash, "")

            return wrapper

        context[func_name] = make_wrapper(func_results)

    # 为Provider创建命名空间对象（用于函数参数访问，如 event.account）
    for call in provider_calls:
        if "function" in call.call_args:
            ns_name = call.provider.key
            if ns_name not in context:
                context[ns_name] = ProviderNamespace(ns_name)

    return context


def _render_template(template: str, providers: list[Provider], variables: dict[str, Any], max_workers: int = 10) -> str:
    """渲染模板

    该函数会：
    1. 使用Jinja2 AST解析模板，通过Provider.match()识别Provider变量/函数调用
    2. 使用线程池并发调用Provider.get获取数据
    3. 构建渲染上下文，将结果注入为函数和变量
    4. 使用Jinja2渲染最终结果

    Args:
        template: Jinja2模板字符串
        providers: Provider列表
        variables: 普通变量字典，会直接传递给Jinja2渲染
        max_workers: 线程池最大工作线程数

    Returns:
        渲染后的字符串
    """
    # 1. 使用AST解析模板，提取所有Provider调用
    provider_calls = _parse_template(template, providers)

    env = Environment()

    if not provider_calls:
        # 没有Provider调用，直接用Jinja2渲染普通变量
        try:
            return env.from_string(template).render(**variables)
        except Exception as e:
            logger_celery.exception("[RenderTemplate] Jinja2 render failed: %s", e)
            return f"[Render Error: {e}]"

    # 2. 使用线程池并发执行Provider调用
    results: dict[str, Any] = {}  # original_expr -> result

    with ThreadPoolExecutor(max_workers=min(max_workers, len(provider_calls))) as executor:
        # 提交所有任务，直接使用call中的provider实例
        future_to_call: dict[Future, ProviderCall] = {
            executor.submit(_execute_provider_call, call): call for call in provider_calls
        }

        # 收集结果
        for future in as_completed(future_to_call):
            try:
                call, result = future.result()
                # 将列表结果转换为字符串
                if isinstance(result, list):
                    result = ", ".join(str(v) for v in result)
                results[call.original_expr] = result
            except Exception as e:
                call = future_to_call[future]
                logger_celery.exception("[RenderTemplate] Future failed for %s: %s", call.original_expr, e)
                results[call.original_expr] = f"[Error: {e}]"

    # 3. 构建渲染上下文
    context = _build_render_context(provider_calls, results, variables)

    # 4. 使用Jinja2渲染
    try:
        final_result = env.from_string(template).render(**context)
    except Exception as e:
        logger_celery.exception("[RenderTemplate] Jinja2 render failed: %s", e)
        # 如果Jinja2渲染失败，尝试返回部分渲染结果
        final_result = f"[Render Error: {e}]"

    return final_result


@celery_app.task(queue="risk_render")
def render_template(*args, **kwargs) -> str:
    """Celery任务：渲染报告模板

    Args:
        *args, **kwargs: 传递给_render_template的参数

    Returns:
        渲染后的字符串
    """
    return _render_template(*args, **kwargs)
