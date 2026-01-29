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

from unittest import mock

from jinja2 import nodes

from services.web.risk.report.providers import EventProvider
from tests.base import TestCase

from .constants import (
    EVENT_ONLY_TEMPLATE,
    MOCK_AI_RESPONSE,
    MOCK_AI_VARIABLES_CONFIG,
    MOCK_EVENTS,
    MOCK_RISK,
    SIMPLE_TEMPLATE,
    TEST_TEMPLATE,
)


def create_event_provider_with_mock_api(
    risk_id: str = "test_risk_123",
    events: list[dict] = None,
) -> EventProvider:
    """创建带有 mock API 的 EventProvider

    通过 mock api.bk_base.query_sync 来模拟事件查询结果。

    Args:
        risk_id: 风险ID
        events: 模拟事件数据

    Returns:
        配置好 mock 的 EventProvider 实例
    """
    events = events if events is not None else MOCK_EVENTS
    provider = EventProvider(risk_id=risk_id)
    # 设置私有属性绕过数据库查询
    provider._risk = _create_mock_risk(risk_id)
    return provider


def _create_mock_risk(risk_id: str):
    """创建 mock Risk 对象"""
    from datetime import datetime

    mock_risk = mock.MagicMock()
    mock_risk.risk_id = risk_id
    mock_risk.strategy_id = 1
    mock_risk.raw_event_id = "raw_event_001"
    mock_risk.event_time = datetime(2025, 12, 17, 4, 57, 25)
    mock_risk.event_end_time = datetime(2025, 12, 17, 5, 30, 0)
    # Mock strategy
    mock_strategy = mock.MagicMock()
    mock_strategy.strategy_id = 1
    mock_strategy.configs = {
        "select": [
            {"display_name": "account", "field_type": "string"},
            {"display_name": "username", "field_type": "string"},
            {"display_name": "amount", "field_type": "long"},
            {"display_name": "event_id", "field_type": "string"},
        ]
    }
    mock_risk.strategy = mock_strategy
    return mock_risk


def mock_bkbase_query(events: list[dict]):
    """创建 mock bk_base.query_sync 响应的函数

    Args:
        events: 模拟事件列表

    Returns:
        mock 函数，根据 SQL 内容返回适当的聚合结果

    注意：由于 SQL 中 COUNT DISTINCT 和 COUNT 的区别难以通过 SQL 文本准确判断，
    测试时根据字段名来区分：
    - username 字段使用 count_distinct 返回去重数量
    - event_id 字段使用 count 返回总数量
    """

    def _mock_query(sql: str):
        """根据 SQL 解析聚合函数并返回模拟结果"""
        sql_lower = sql.lower()

        # 解析字段名（从 SELECT 和 AS 子句中提取）
        field_name = None
        for event_field in ["account", "username", "amount", "event_id"]:
            if event_field in sql_lower:
                field_name = event_field
                break

        if not field_name or not events:
            return {"list": []}

        values = [e.get(field_name) for e in events if e.get(field_name) is not None]

        # 根据 SQL 中的聚合函数返回结果
        if "count(" in sql_lower:
            # 根据字段区分 count 和 count_distinct
            # username 字段测试 count_distinct，其他字段测试 count
            if field_name == "username":
                return {"list": [{field_name: len(set(values))}]}
            else:
                return {"list": [{field_name: len(values)}]}
        elif "sum(" in sql_lower:
            return {"list": [{field_name: sum(float(v) for v in values)}]}
        elif "avg(" in sql_lower:
            return {"list": [{field_name: sum(float(v) for v in values) / len(values) if values else 0}]}
        elif "max(" in sql_lower:
            return {"list": [{field_name: max(float(v) for v in values)}]}
        elif "min(" in sql_lower:
            return {"list": [{field_name: min(float(v) for v in values)}]}
        elif "order by" in sql_lower and "desc" in sql_lower:
            # latest - 最后一条
            return {"list": [{field_name: values[-1] if values else None}]}
        elif "order by" in sql_lower and "asc" in sql_lower:
            # first - 第一条
            return {"list": [{field_name: values[0] if values else None}]}
        elif "group_concat" in sql_lower and "distinct" in sql_lower:
            # list_distinct
            return {"list": [{field_name: ", ".join(sorted({str(v) for v in values}))}]}
        elif "group_concat" in sql_lower:
            # list
            return {"list": [{field_name: ", ".join(str(v) for v in values)}]}
        else:
            # 默认返回第一个值
            return {"list": [{field_name: values[0] if values else None}]}

    return _mock_query


class TestEventProviderWithMockAPI(TestCase):
    """测试 EventProvider（使用 mock API）"""

    @mock.patch("services.web.risk.report.providers.api.bk_base.query_sync")
    def test_first_aggregation(self, mock_query):
        """测试first聚合函数"""
        mock_query.side_effect = mock_bkbase_query(MOCK_EVENTS)
        provider = create_event_provider_with_mock_api()
        result = provider.get(function="first", field_name="account")
        self.assertEqual(result, "game_admin_001")

    @mock.patch("services.web.risk.report.providers.api.bk_base.query_sync")
    def test_latest_aggregation(self, mock_query):
        """测试latest聚合函数"""
        mock_query.side_effect = mock_bkbase_query(MOCK_EVENTS)
        provider = create_event_provider_with_mock_api()
        result = provider.get(function="latest", field_name="account")
        self.assertEqual(result, "game_admin_001")

    @mock.patch("services.web.risk.report.providers.api.bk_base.query_sync")
    def test_count_aggregation(self, mock_query):
        """测试count聚合函数"""
        mock_query.side_effect = mock_bkbase_query(MOCK_EVENTS)
        provider = create_event_provider_with_mock_api()
        result = provider.get(function="count", field_name="event_id")
        self.assertEqual(result, 3)

    @mock.patch("services.web.risk.report.providers.api.bk_base.query_sync")
    def test_count_distinct_aggregation(self, mock_query):
        """测试count_distinct聚合函数"""
        mock_query.side_effect = mock_bkbase_query(MOCK_EVENTS)
        provider = create_event_provider_with_mock_api()
        result = provider.get(function="count_distinct", field_name="username")
        self.assertEqual(result, 2)  # zhangsan, lisi

    @mock.patch("services.web.risk.report.providers.api.bk_base.query_sync")
    def test_sum_aggregation(self, mock_query):
        """测试sum聚合函数"""
        mock_query.side_effect = mock_bkbase_query(MOCK_EVENTS)
        provider = create_event_provider_with_mock_api()
        result = provider.get(function="sum", field_name="amount")
        self.assertEqual(result, 500000)

    @mock.patch("services.web.risk.report.providers.api.bk_base.query_sync")
    def test_list_aggregation(self, mock_query):
        """测试list聚合函数"""
        mock_query.side_effect = mock_bkbase_query(MOCK_EVENTS)
        provider = create_event_provider_with_mock_api()
        result = provider.get(function="list", field_name="username")
        self.assertIn("zhangsan", result)
        self.assertIn("lisi", result)

    @mock.patch("services.web.risk.report.providers.api.bk_base.query_sync")
    def test_list_distinct_aggregation(self, mock_query):
        """测试list_distinct聚合函数"""
        mock_query.side_effect = mock_bkbase_query(MOCK_EVENTS)
        provider = create_event_provider_with_mock_api()
        result = provider.get(function="list_distinct", field_name="username")
        # 去重后应该只有两个值
        self.assertIn("lisi", result)
        self.assertIn("zhangsan", result)

    @mock.patch("services.web.risk.report.providers.api.bk_base.query_sync")
    def test_empty_events(self, mock_query):
        """测试空事件列表"""
        mock_query.side_effect = mock_bkbase_query([])
        provider = create_event_provider_with_mock_api()
        # 空列表返回 None
        self.assertIsNone(provider.get(function="count", field_name="event_id"))
        self.assertIsNone(provider.get(function="first", field_name="account"))

    def test_match_call_node(self):
        """测试match方法匹配函数调用节点"""
        from jinja2 import Environment

        provider = EventProvider(risk_id="test_risk_123")
        env = Environment()

        # 测试匹配 first(event.account)
        ast = env.parse("{{ first(event.account) }}")
        # 获取Call节点
        output_node = ast.body[0]
        call_node = output_node.nodes[0]

        result = provider.match(call_node)
        self.assertTrue(result.matched)
        self.assertEqual(result.original_expr, "first(event.account)")
        self.assertIs(result.provider, provider)
        self.assertEqual(result.node_type, nodes.Call)
        self.assertEqual(result.call_args["function"], "first")
        self.assertEqual(result.call_args["field_name"], "account")
        self.assertEqual(result.call_args["args"], ["event.account"])
        self.assertEqual(result.call_args["kwargs"], {})

    def test_match_wrong_provider_key(self):
        """测试match方法不匹配错误的provider_key"""
        from jinja2 import Environment

        provider = EventProvider(risk_id="test_risk_123")
        env = Environment()

        # 测试不匹配 first(other.account)
        ast = env.parse("{{ first(other.account) }}")
        output_node = ast.body[0]
        call_node = output_node.nodes[0]

        result = provider.match(call_node)
        self.assertFalse(result.matched)

    def test_match_unsupported_function(self):
        """测试match方法不匹配不支持的函数"""
        from jinja2 import Environment

        provider = EventProvider(risk_id="test_risk_123")
        env = Environment()

        # 测试不匹配 unknown_func(event.account)
        ast = env.parse("{{ unknown_func(event.account) }}")
        output_node = ast.body[0]
        call_node = output_node.nodes[0]

        result = provider.match(call_node)
        self.assertFalse(result.matched)


class TestAIProvider(TestCase):
    """测试AIProvider"""

    def test_get_ai_content(self):
        """测试获取AI生成内容"""
        from services.web.risk.report.providers import AIProvider

        # 使用ai_executor参数注入mock执行器
        def mock_executor(prompt):
            return MOCK_AI_RESPONSE["content"]

        provider = AIProvider(
            context={"risk_id": "123"}, ai_variables_config=MOCK_AI_VARIABLES_CONFIG, ai_executor=mock_executor
        )
        result = provider.get(name="summary")
        self.assertIn("2025年12月17日", result)

    def test_get_ai_content_no_prompt(self):
        """测试AI变量未配置prompt的情况"""
        from services.web.risk.report.providers import AIProvider

        provider = AIProvider(context={"risk_id": "123"}, ai_variables_config=[])
        result = provider.get(name="unknown_var")
        self.assertIn("未配置prompt", result)

    def test_match_getattr_node(self):
        """测试AIProvider的match方法匹配属性访问节点"""
        from jinja2 import Environment

        from services.web.risk.report.providers import AIProvider

        provider = AIProvider(context={}, key="ai")
        env = Environment()

        # 测试匹配 ai.summary
        ast = env.parse("{{ ai.summary }}")
        output_node = ast.body[0]
        getattr_node = output_node.nodes[0]

        result = provider.match(getattr_node)
        self.assertTrue(result.matched)
        self.assertEqual(result.original_expr, "ai.summary")
        self.assertIs(result.provider, provider)
        self.assertEqual(result.node_type, nodes.Getattr)
        self.assertEqual(result.call_args["name"], "ai.summary")  # 完整变量表达式

    def test_match_wrong_provider_key(self):
        """测试AIProvider的match方法不匹配错误的provider_key"""
        from jinja2 import Environment

        from services.web.risk.report.providers import AIProvider

        provider = AIProvider(context={}, key="ai")
        env = Environment()

        # 测试不匹配 other.summary
        ast = env.parse("{{ other.summary }}")
        output_node = ast.body[0]
        getattr_node = output_node.nodes[0]

        result = provider.match(getattr_node)
        self.assertFalse(result.matched)


class TestTemplateParser(TestCase):
    """测试模板解析（使用Jinja2 AST + Provider.match）"""

    def _get_default_providers(self):
        """获取默认的providers列表"""
        from services.web.risk.report.providers import AIProvider

        return [create_event_provider_with_mock_api(), AIProvider(context={})]

    def test_parse_function_calls(self):
        """测试解析函数调用"""
        from services.web.risk.report.renderer import _parse_template

        template = "{{ first(event.account) }} and {{ count(event.event_id) }}"
        calls = _parse_template(template, self._get_default_providers())

        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0].call_args["function"], "first")
        self.assertEqual(calls[0].provider.key, "event")
        self.assertEqual(calls[0].call_args["args"], ["event.account"])
        self.assertEqual(calls[0].node_type, nodes.Call)

    def test_parse_ai_variables(self):
        """测试解析AI变量"""
        from services.web.risk.report.renderer import _parse_template

        template = "{{ ai.summary }} and {{ ai.suggestion }}"
        calls = _parse_template(template, self._get_default_providers())

        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0].provider.key, "ai")
        self.assertEqual(calls[0].call_args["name"], "ai.summary")  # 完整变量表达式
        self.assertEqual(calls[0].node_type, nodes.Getattr)

    def test_parse_mixed_template(self):
        """测试解析混合模板"""
        from services.web.risk.report.renderer import _parse_template

        calls = _parse_template(TEST_TEMPLATE, self._get_default_providers())

        # 应该包含AI变量和事件聚合函数
        ai_calls = [c for c in calls if c.provider.key == "ai"]
        event_calls = [c for c in calls if c.provider.key == "event"]

        self.assertEqual(len(ai_calls), 1)  # ai.summary
        self.assertGreaterEqual(len(event_calls), 4)  # first, sum, count, list_distinct

    def test_ast_parse_all_aggregation_functions(self):
        """测试AST解析所有支持的聚合函数"""
        from services.web.risk.constants import AggregationFunction
        from services.web.risk.report.renderer import _parse_template

        # 使用 AggregationFunction.values 保持一致
        supported_functions = set(AggregationFunction.values)

        # 构建包含所有聚合函数的模板
        template_parts = [f"{{{{ {func}(event.field) }}}}" for func in supported_functions]
        template = " ".join(template_parts)

        providers = [EventProvider(risk_id="test_risk")]
        calls = _parse_template(template, providers)
        parsed_functions = {call.call_args["function"] for call in calls}

        self.assertEqual(parsed_functions, supported_functions)

    def test_ast_parse_ignores_unsupported_functions(self):
        """测试AST解析忽略不支持的函数"""
        from services.web.risk.report.renderer import _parse_template

        template = "{{ unsupported_func(event.field) }} {{ first(event.account) }}"
        calls = _parse_template(template, self._get_default_providers())

        # 只应该解析出first函数
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].call_args["function"], "first")

    def test_ast_parse_ignores_regular_variables(self):
        """测试AST解析忽略普通变量（非注册的provider）"""
        from services.web.risk.report.renderer import _parse_template

        template = "{{ risk.strategy_name }} {{ user.name }} {{ ai.summary }}"
        calls = _parse_template(template, self._get_default_providers())

        # 只应该解析出ai.summary
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].provider.key, "ai")
        self.assertEqual(calls[0].call_args["name"], "ai.summary")  # 完整变量表达式

    def test_ast_parse_complex_template(self):
        """测试AST解析复杂模板（包含条件、循环等Jinja2语法）"""
        from services.web.risk.report.renderer import _parse_template

        template = """
        {% if show_summary %}
        {{ ai.summary }}
        {% endif %}

        {% for item in items %}
        - {{ item.name }}: {{ first(event.value) }}
        {% endfor %}

        {{ count(event.event_id) }}
        """
        calls = _parse_template(template, self._get_default_providers())

        # 应该解析出ai.summary和两个聚合函数
        ai_calls = [c for c in calls if c.provider.key == "ai"]
        func_calls = [c for c in calls if c.provider.key == "event"]

        self.assertEqual(len(ai_calls), 1)
        self.assertEqual(len(func_calls), 2)

    def test_ast_parse_original_expr(self):
        """测试AST解析生成的original_expr格式正确"""
        from services.web.risk.report.renderer import _parse_template

        template = "{{ first(event.account) }} {{ ai.summary }}"
        calls = _parse_template(template, self._get_default_providers())

        func_call = next(c for c in calls if c.provider.key == "event")
        ai_call = next(c for c in calls if c.provider.key == "ai")

        self.assertEqual(func_call.original_expr, "first(event.account)")
        self.assertEqual(ai_call.original_expr, "ai.summary")

    def test_parse_without_providers_returns_empty(self):
        """测试没有providers时返回空列表"""
        from services.web.risk.report.renderer import _parse_template

        template = "{{ first(event.account) }} {{ ai.summary }}"
        calls = _parse_template(template, [])

        self.assertEqual(len(calls), 0)


class TestRenderTemplate(TestCase):
    """测试render_template函数"""

    def test_render_simple_variables(self):
        """测试渲染简单变量（无Provider调用）"""
        from services.web.risk.report.renderer import _render_template

        result = _render_template(template=SIMPLE_TEMPLATE, providers=[], variables={"risk": MOCK_RISK})

        self.assertIn("虚拟资源发放异常检测", result)
        self.assertIn("高危", result)
        self.assertIn("张三", result)

    @mock.patch("services.web.risk.report.providers.api.bk_base.query_sync")
    def test_render_event_aggregations(self, mock_query):
        """测试渲染事件聚合函数"""
        from services.web.risk.report.renderer import _render_template

        mock_query.side_effect = mock_bkbase_query(MOCK_EVENTS)

        result = _render_template(
            template=EVENT_ONLY_TEMPLATE, providers=[create_event_provider_with_mock_api()], variables={}
        )

        self.assertIn("事件数量：3", result)
        self.assertIn("第一个账号：game_admin_001", result)
        self.assertIn("总金额：500000", result)

    @mock.patch("services.web.risk.report.providers.api.bk_base.query_sync")
    def test_render_full_template(self, mock_query):
        """测试渲染完整模板（包含普通变量、事件聚合、AI变量）"""
        from services.web.risk.report.providers import AIProvider
        from services.web.risk.report.renderer import _render_template

        mock_query.side_effect = mock_bkbase_query(MOCK_EVENTS)

        # 使用ai_executor参数注入mock执行器
        def mock_executor(prompt):
            return MOCK_AI_RESPONSE["content"]

        result = _render_template(
            template=TEST_TEMPLATE,
            providers=[
                create_event_provider_with_mock_api(),
                AIProvider(
                    context={"risk_id": MOCK_RISK["risk_id"]},
                    ai_variables_config=MOCK_AI_VARIABLES_CONFIG,
                    ai_executor=mock_executor,
                ),
            ],
            variables={"risk": MOCK_RISK},
        )

        # 验证普通变量渲染
        self.assertIn("虚拟资源发放异常检测", result)
        self.assertIn("张三", result)

        # 验证事件聚合渲染
        self.assertIn("game_admin_001", result)  # first(event.account)
        self.assertIn("500000", result)  # sum(event.amount)
        self.assertIn("3", result)  # count(event.event_id)

        # 验证AI变量渲染
        self.assertIn("2025年12月17日", result)

    @mock.patch("services.web.risk.report.providers.api.bk_base.query_sync")
    def test_render_missing_provider(self, mock_query):
        """测试Provider不存在的情况"""
        from services.web.risk.report.renderer import _render_template

        mock_query.side_effect = mock_bkbase_query([])

        # 模板中使用unknown.field，但providers中只有event
        # 由于unknown没有对应的provider，解析时不会匹配，Jinja2渲染时会报错
        template = "{{ first(unknown.field) }}"
        result = _render_template(
            template=template, providers=[create_event_provider_with_mock_api(events=[])], variables={}
        )

        # 由于unknown没有provider，Jinja2渲染失败，返回错误信息
        self.assertIn("Render Error", result)

    @mock.patch("services.web.risk.report.providers.api.bk_base.query_sync")
    def test_render_with_registered_provider_missing_data(self, mock_query):
        """测试注册了Provider但数据为空的情况"""
        from services.web.risk.report.renderer import _render_template

        mock_query.side_effect = mock_bkbase_query([])

        template = "{{ first(event.account) }}"
        result = _render_template(
            template=template, providers=[create_event_provider_with_mock_api(events=[])], variables={}
        )

        # Provider注册了，但事件列表为空，first返回None，Jinja2渲染为字符串"None"
        self.assertEqual(result.strip(), "None")

    @mock.patch("services.web.risk.report.providers.api.bk_base.query_sync")
    def test_concurrent_execution(self, mock_query):
        """测试并发执行"""
        from services.web.risk.report.renderer import _render_template

        mock_query.side_effect = mock_bkbase_query(MOCK_EVENTS)

        # 创建包含多个Provider调用的模板
        template = """
        {{ first(event.account) }}
        {{ latest(event.account) }}
        {{ count(event.event_id) }}
        {{ sum(event.amount) }}
        {{ list_distinct(event.username) }}
        """

        result = _render_template(
            template=template, providers=[create_event_provider_with_mock_api()], variables={}, max_workers=5
        )

        self.assertIn("game_admin_001", result)
        self.assertIn("500000", result)
        self.assertIn("3", result)

    @mock.patch("services.web.risk.report.providers.api.bk_base.query_sync")
    def test_function_results_hash_lookup(self, mock_query):
        """测试function_results按照function_name和args_hash存储和获取结果"""
        from services.web.risk.report.renderer import _render_template

        mock_query.side_effect = mock_bkbase_query(MOCK_EVENTS)

        # 测试相同函数不同参数的情况
        template = """
        第一个账号：{{ first(event.account) }}
        第一个用户名：{{ first(event.username) }}
        """

        result = _render_template(template=template, providers=[create_event_provider_with_mock_api()], variables={})

        self.assertIn("第一个账号：game_admin_001", result)
        self.assertIn("第一个用户名：zhangsan", result)

    @mock.patch("services.web.risk.report.providers.api.bk_base.query_sync")
    def test_same_function_same_args_dedup(self, mock_query):
        """测试相同函数相同参数去重"""
        from services.web.risk.report.renderer import _render_template

        mock_query.side_effect = mock_bkbase_query(MOCK_EVENTS)

        # 相同的表达式在模板中出现多次
        template = """
        账号1：{{ first(event.account) }}
        账号2：{{ first(event.account) }}
        """

        result = _render_template(template=template, providers=[create_event_provider_with_mock_api()], variables={})

        # 两个位置都应该渲染相同的结果
        self.assertEqual(result.count("game_admin_001"), 2)

    @mock.patch("services.web.risk.report.providers.api.bk_base.query_sync")
    def test_render_all_aggregation_functions(self, mock_query):
        """测试渲染所有 AggregationFunction 定义的聚合函数"""
        from services.web.risk.report.renderer import _render_template

        mock_query.side_effect = mock_bkbase_query(MOCK_EVENTS)

        # 构建包含所有聚合函数的模板
        template = """
sum: {{ sum(event.amount) }}
avg: {{ avg(event.amount) }}
max: {{ max(event.amount) }}
min: {{ min(event.amount) }}
count: {{ count(event.event_id) }}
count_distinct: {{ count_distinct(event.username) }}
first: {{ first(event.account) }}
latest: {{ latest(event.account) }}
list: {{ list(event.username) }}
list_distinct: {{ list_distinct(event.username) }}
"""

        result = _render_template(
            template=template,
            providers=[create_event_provider_with_mock_api()],
            variables={},
        )

        # 验证所有聚合函数都被正确渲染
        self.assertIn("sum: 500000", result)
        # avg: 500000 / 3 ≈ 166666.67
        self.assertIn("avg:", result)
        self.assertIn("max: 250000", result)
        self.assertIn("min: 100000", result)
        self.assertIn("count: 3", result)
        self.assertIn("count_distinct: 2", result)  # zhangsan, lisi
        self.assertIn("first: game_admin_001", result)
        self.assertIn("latest: game_admin_001", result)
        self.assertIn("list:", result)
        self.assertIn("list_distinct:", result)


class TestAIPreviewResource(TestCase):
    """测试 AIPreview Resource"""

    def test_ai_preview_request_serializer_valid(self):
        """测试 AIPreviewRequestSerializer 验证有效数据"""
        from services.web.risk.serializers import AIPreviewRequestSerializer

        data = {
            "risk_id": "test_risk_123",
            "ai_variables": [
                {"name": "ai.summary", "prompt_template": "请总结风险"},
                {"name": "ai.suggestion", "prompt_template": "请给出建议"},
            ],
        }
        serializer = AIPreviewRequestSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["risk_id"], "test_risk_123")
        self.assertEqual(len(serializer.validated_data["ai_variables"]), 2)

    def test_ai_preview_request_serializer_invalid_name(self):
        """测试 AIPreviewRequestSerializer 验证无效的AI变量名"""
        from services.web.risk.serializers import AIPreviewRequestSerializer

        data = {
            "risk_id": "test_risk_123",
            "ai_variables": [{"name": "invalid_name", "prompt_template": "请总结风险"}],  # 不以 ai. 开头
        }
        serializer = AIPreviewRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("ai_variables", serializer.errors)

    def test_ai_preview_request_serializer_empty_variables(self):
        """测试 AIPreviewRequestSerializer 验证空的AI变量列表"""
        from services.web.risk.serializers import AIPreviewRequestSerializer

        data = {"risk_id": "test_risk_123", "ai_variables": []}  # 空列表
        serializer = AIPreviewRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("ai_variables", serializer.errors)

    def test_ai_variable_serializer_valid(self):
        """测试 AIVariableConfig.drf_serializer_with_validation 验证有效数据"""
        from services.web.risk.report_config import AIVariableConfig

        data = {"name": "ai.summary", "prompt_template": "请总结风险"}
        serializer = AIVariableConfig.drf_serializer_with_validation()(data=data)
        self.assertTrue(serializer.is_valid())

    def test_ai_variable_serializer_name_must_start_with_ai(self):
        """测试 AIVariableConfig.drf_serializer_with_validation 验证name必须以ai.开头"""
        from services.web.risk.report_config import AIVariableConfig

        data = {"name": "summary", "prompt_template": "请总结风险"}
        serializer = AIVariableConfig.drf_serializer_with_validation()(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)

    @classmethod
    def setUpTestData(cls):
        """创建测试数据"""
        from django.utils import timezone

        from services.web.risk.models import Risk
        from services.web.strategy_v2.models import Strategy

        # 创建策略
        cls.strategy = Strategy.objects.create(
            strategy_id=99999,
            strategy_name="测试策略",
            namespace="default",
        )

        # 创建风险
        cls.risk = Risk.objects.create(
            risk_id="test_risk_for_ai_preview",
            strategy_id=cls.strategy.strategy_id,
            event_content="测试事件内容",
            risk_label="normal",
            event_time=timezone.now(),
            raw_event_id="test_raw_event_id_ai_preview",
        )

    def test_ai_preview_resource_submit_task(self):
        """测试通过 resource 调用 AIPreview 提交异步任务"""
        from unittest.mock import MagicMock, patch

        from services.web.risk.report_config import AIVariableConfig

        # Mock celery task 的 delay 方法
        mock_task = MagicMock()
        mock_task.id = "test_task_id_123"

        with patch("services.web.risk.resources.report.render_ai_variable") as mock_render:
            mock_render.delay.return_value = mock_task

            result = self.resource.risk.ai_preview(
                risk_id=self.risk.risk_id,
                ai_variables=[
                    {"name": "ai.summary", "prompt_template": "请总结风险"},
                ],
            )

            # 验证返回结果
            self.assertEqual(result["task_id"], "test_task_id_123")
            self.assertEqual(result["status"], "PENDING")

            # 验证 celery task 被调用
            mock_render.delay.assert_called_once_with(
                risk_id=self.risk.risk_id,
                ai_variables=[
                    {
                        "name": "ai.summary",
                        "prompt_template": f"{AIVariableConfig.PREDEFINED_PROMPT_TEMPLATE}\n请总结风险",
                    },
                ],
            )

    def test_ai_preview_task_execution_with_mock_ai(self):
        """测试 render_ai_variable 任务实际执行（mock AI 执行器）"""
        from unittest.mock import patch

        from services.web.risk.tasks import render_ai_variable

        ai_variables = [
            {"name": "ai.summary", "prompt_template": "请总结风险"},
            {"name": "ai.suggestion", "prompt_template": "请给出建议"},
        ]

        # Mock AIProvider._execute_ai_agent 方法
        def mock_ai_executor(self, prompt):
            if "总结" in prompt:
                return "这是AI生成的风险摘要内容"
            elif "建议" in prompt:
                return "这是AI生成的处理建议"
            return f"Mock AI response for: {prompt}"

        with patch("services.web.risk.tasks.AIProvider._execute_ai_agent", mock_ai_executor):
            # 直接调用任务函数（同步执行）
            result = render_ai_variable(risk_id=self.risk.risk_id, ai_variables=ai_variables)

            # 验证返回结果结构
            self.assertIn("ai", result)
            self.assertIn("summary", result["ai"])
            self.assertIn("suggestion", result["ai"])

            # 验证 AI 执行器被调用并返回了 mock 结果（内容经过 markdown 渲染）
            self.assertIn("这是AI生成的风险摘要内容", result["ai"]["summary"])
            self.assertIn("这是AI生成的处理建议", result["ai"]["suggestion"])

    def test_ai_preview_task_with_single_variable(self):
        """测试 render_ai_variable 任务执行单个 AI 变量"""
        from unittest.mock import patch

        from services.web.risk.tasks import render_ai_variable

        ai_variables = [
            {"name": "ai.analysis", "prompt_template": "请分析风险原因"},
        ]

        # Mock AIProvider._execute_ai_agent 方法
        with patch("services.web.risk.tasks.AIProvider._execute_ai_agent", return_value="这是AI生成的风险分析"):
            result = render_ai_variable(risk_id=self.risk.risk_id, ai_variables=ai_variables)

            self.assertIn("ai", result)
            self.assertIn("analysis", result["ai"])
            # 内容经过 markdown 渲染
            self.assertIn("这是AI生成的风险分析", result["ai"]["analysis"])

    def test_ai_preview_task_risk_not_found(self):
        """测试 render_ai_variable 任务风险单不存在的情况"""
        from services.web.risk.tasks import render_ai_variable

        ai_variables = [
            {"name": "ai.summary", "prompt_template": "请总结风险"},
        ]

        with self.assertRaises(ValueError) as context:
            render_ai_variable(risk_id="non_existent_risk_id", ai_variables=ai_variables)

        self.assertIn("风险单不存在", str(context.exception))

    def test_ai_preview_resource_risk_not_found(self):
        """测试 AIPreview Resource 风险单不存在的情况"""
        from django.http import Http404

        with self.assertRaises(Http404):
            self.resource.risk.ai_preview(
                risk_id="non_existent_risk_id",
                ai_variables=[
                    {"name": "ai.summary", "prompt_template": "请总结风险"},
                ],
            )


class TestGetTaskResultResource(TestCase):
    """测试 GetTaskResult Resource"""

    def test_task_result_request_serializer_valid(self):
        """测试 TaskResultRequestSerializer 验证有效数据"""
        from services.web.risk.serializers import TaskResultRequestSerializer

        data = {"task_id": "task_abc_123"}
        serializer = TaskResultRequestSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["task_id"], "task_abc_123")

    def test_task_result_response_serializer(self):
        """测试 TaskResultResponseSerializer 序列化响应"""
        from services.web.risk.serializers import TaskResultResponseSerializer

        data = {"task_id": "task_abc_123", "status": "SUCCESS", "result": {"ai": {"summary": "风险摘要"}}}
        serializer = TaskResultResponseSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_task_result_response_serializer_pending(self):
        """测试 TaskResultResponseSerializer 序列化PENDING状态"""
        from services.web.risk.serializers import TaskResultResponseSerializer

        data = {"task_id": "task_abc_123", "status": "PENDING", "result": None}
        serializer = TaskResultResponseSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_task_result_response_serializer_failure(self):
        """测试 TaskResultResponseSerializer 序列化FAILURE状态"""
        from services.web.risk.serializers import TaskResultResponseSerializer

        data = {"task_id": "task_abc_123", "status": "FAILURE", "result": {"error": "任务执行失败"}}
        serializer = TaskResultResponseSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_async_task_response_serializer(self):
        """测试 AsyncTaskResponseSerializer 序列化异步任务提交响应"""
        from services.web.risk.serializers import AsyncTaskResponseSerializer

        data = {"task_id": "task_abc_123", "status": "PENDING"}
        serializer = AsyncTaskResponseSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_status_map_coverage(self):
        """测试 GetTaskResult STATUS_MAP 状态映射完整性"""
        from services.web.risk.resources.report import GetTaskResult

        resource = GetTaskResult()
        status_map = resource.STATUS_MAP

        # 验证关键状态都有映射
        self.assertEqual(status_map["PENDING"], "PENDING")
        self.assertEqual(status_map["STARTED"], "RUNNING")
        self.assertEqual(status_map["PROGRESS"], "RUNNING")
        self.assertEqual(status_map["SUCCESS"], "SUCCESS")
        self.assertEqual(status_map["FAILURE"], "FAILURE")
        self.assertEqual(status_map["REVOKED"], "FAILURE")
        self.assertEqual(status_map["RETRY"], "RUNNING")

    def test_status_map_unknown_status(self):
        """测试 GetTaskResult 处理未知状态"""
        from services.web.risk.resources.report import GetTaskResult

        resource = GetTaskResult()
        # 未知状态应该默认为 PENDING
        self.assertEqual(resource.STATUS_MAP.get("UNKNOWN", "PENDING"), "PENDING")

    @classmethod
    def setUpTestData(cls):
        """创建测试数据"""
        from django.utils import timezone

        from services.web.risk.models import Risk
        from services.web.strategy_v2.models import Strategy

        # 创建策略
        cls.strategy = Strategy.objects.create(
            strategy_id=99998,
            strategy_name="测试策略2",
            namespace="default",
        )

        # 创建风险
        cls.risk = Risk.objects.create(
            risk_id="test_risk_for_task_result",
            strategy_id=cls.strategy.strategy_id,
            event_content="测试事件内容",
            risk_label="normal",
            event_time=timezone.now(),
            raw_event_id="test_raw_event_id_task_result",
        )

    def test_get_task_result_resource_pending(self):
        """测试通过 resource 调用 GetTaskResult 获取 PENDING 状态任务"""
        from unittest.mock import MagicMock, patch

        # Mock AsyncResult
        mock_async_result = MagicMock()
        mock_async_result.status = "PENDING"
        mock_async_result.result = None

        with patch("services.web.risk.resources.report.AsyncResult") as mock_ar:
            mock_ar.return_value = mock_async_result

            result = self.resource.risk.get_task_result(task_id="test_task_id_pending")

            # 验证返回结果
            self.assertEqual(result["task_id"], "test_task_id_pending")
            self.assertEqual(result["status"], "PENDING")
            self.assertIsNone(result["result"])

            # 验证 AsyncResult 被调用
            mock_ar.assert_called_once_with("test_task_id_pending")

    def test_get_task_result_resource_success(self):
        """测试通过 resource 调用 GetTaskResult 获取 SUCCESS 状态任务"""
        from unittest.mock import MagicMock, patch

        # Mock AsyncResult
        mock_async_result = MagicMock()
        mock_async_result.status = "SUCCESS"
        mock_async_result.result = {"ai": {"summary": "AI生成的风险摘要", "suggestion": "AI生成的处理建议"}}

        with patch("services.web.risk.resources.report.AsyncResult") as mock_ar:
            mock_ar.return_value = mock_async_result

            result = self.resource.risk.get_task_result(task_id="test_task_id_success")

            # 验证返回结果
            self.assertEqual(result["task_id"], "test_task_id_success")
            self.assertEqual(result["status"], "SUCCESS")
            self.assertEqual(result["result"]["ai"]["summary"], "AI生成的风险摘要")
            self.assertEqual(result["result"]["ai"]["suggestion"], "AI生成的处理建议")

    def test_get_task_result_resource_failure(self):
        """测试通过 resource 调用 GetTaskResult 获取 FAILURE 状态任务"""
        from unittest.mock import MagicMock, patch

        # Mock AsyncResult
        mock_async_result = MagicMock()
        mock_async_result.status = "FAILURE"
        mock_async_result.result = Exception("任务执行失败")

        with patch("services.web.risk.resources.report.AsyncResult") as mock_ar:
            mock_ar.return_value = mock_async_result

            result = self.resource.risk.get_task_result(task_id="test_task_id_failure")

            # 验证返回结果
            self.assertEqual(result["task_id"], "test_task_id_failure")
            self.assertEqual(result["status"], "FAILURE")
            self.assertIn("error", result["result"])
            self.assertIn("任务执行失败", result["result"]["error"])

    def test_get_task_result_resource_running(self):
        """测试通过 resource 调用 GetTaskResult 获取 STARTED 状态任务（映射为 RUNNING）"""
        from unittest.mock import MagicMock, patch

        # Mock AsyncResult
        mock_async_result = MagicMock()
        mock_async_result.status = "STARTED"
        mock_async_result.result = None

        with patch("services.web.risk.resources.report.AsyncResult") as mock_ar:
            mock_ar.return_value = mock_async_result

            result = self.resource.risk.get_task_result(task_id="test_task_id_running")

            # 验证返回结果
            self.assertEqual(result["task_id"], "test_task_id_running")
            self.assertEqual(result["status"], "RUNNING")  # STARTED 映射为 RUNNING
            self.assertIsNone(result["result"])

    def test_get_task_result_with_real_task_execution(self):
        """测试真实执行 render_ai_variable 任务后获取结果"""
        from unittest.mock import MagicMock, patch

        from services.web.risk.tasks import render_ai_variable

        ai_variables = [
            {"name": "ai.summary", "prompt_template": "请总结风险"},
        ]

        # Mock AIProvider._execute_ai_agent 方法
        with patch("services.web.risk.tasks.AIProvider._execute_ai_agent", return_value="这是AI生成的风险摘要"):
            # 直接调用任务函数获取结果（同步执行）
            task_result = render_ai_variable(risk_id=self.risk.risk_id, ai_variables=ai_variables)

        # 模拟 AsyncResult 返回任务执行结果
        mock_async_result = MagicMock()
        mock_async_result.status = "SUCCESS"
        mock_async_result.result = task_result

        with patch("services.web.risk.resources.report.AsyncResult") as mock_ar:
            mock_ar.return_value = mock_async_result

            result = self.resource.risk.get_task_result(task_id="test_real_task_id")

            # 验证返回结果（内容经过 markdown 渲染）
            self.assertEqual(result["status"], "SUCCESS")
            self.assertIn("ai", result["result"])
            self.assertIn("这是AI生成的风险摘要", result["result"]["ai"]["summary"])

    def test_full_ai_preview_workflow(self):
        """测试完整的 AI 预览工作流：提交任务 -> 执行任务 -> 获取结果"""
        from unittest.mock import MagicMock, patch

        from services.web.risk.tasks import render_ai_variable

        ai_variables = [
            {"name": "ai.summary", "prompt_template": "请总结风险"},
            {"name": "ai.suggestion", "prompt_template": "请给出建议"},
        ]

        # Step 1: Mock task.delay 提交任务
        mock_task = MagicMock()
        mock_task.id = "workflow_task_id"

        with patch("services.web.risk.resources.report.render_ai_variable") as mock_render:
            mock_render.delay.return_value = mock_task

            submit_result = self.resource.risk.ai_preview(risk_id=self.risk.risk_id, ai_variables=ai_variables)

            self.assertEqual(submit_result["task_id"], "workflow_task_id")
            self.assertEqual(submit_result["status"], "PENDING")

        # Step 2: 实际执行任务（mock AI 执行器）
        def mock_ai_executor(self, prompt):
            if "总结" in prompt:
                return "风险摘要：检测到异常行为"
            elif "建议" in prompt:
                return "建议：立即进行安全审查"
            return "默认响应"

        with patch("services.web.risk.tasks.AIProvider._execute_ai_agent", mock_ai_executor):
            task_result = render_ai_variable(risk_id=self.risk.risk_id, ai_variables=ai_variables)

        # Step 3: 获取任务结果
        mock_async_result = MagicMock()
        mock_async_result.status = "SUCCESS"
        mock_async_result.result = task_result

        with patch("services.web.risk.resources.report.AsyncResult") as mock_ar:
            mock_ar.return_value = mock_async_result

            get_result = self.resource.risk.get_task_result(task_id="workflow_task_id")

            # 验证完整工作流结果（内容经过 markdown 渲染）
            self.assertEqual(get_result["status"], "SUCCESS")
            self.assertIn("风险摘要：检测到异常行为", get_result["result"]["ai"]["summary"])
            self.assertIn("建议：立即进行安全审查", get_result["result"]["ai"]["suggestion"])
