# -*- coding: utf-8 -*-
"""
AIProvider 缓存功能单元测试
"""

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from jinja2 import nodes

from services.web.risk.constants import AI_ERROR_PREFIX, AI_ERROR_SUFFIX
from services.web.risk.models import Risk
from services.web.risk.report.providers import AIProvider
from services.web.strategy_v2.models import Strategy, StrategyTool
from services.web.tool.models import Tool

from .constants import MOCK_AI_RESPONSE, MOCK_AI_VARIABLES_CONFIG


class TestAIProvider(TestCase):
    """测试AIProvider"""

    def test_get_ai_content(self):
        """测试获取AI生成内容"""

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
        provider = AIProvider(context={"risk_id": "123"}, ai_variables_config=[])
        result = provider.get(name="unknown_var")
        self.assertIn("未配置prompt", result)

    def test_match_getattr_node(self):
        """测试AIProvider的match方法匹配属性访问节点"""
        from jinja2 import Environment

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

        provider = AIProvider(context={}, key="ai")
        env = Environment()

        # 测试不匹配 other.summary
        ast = env.parse("{{ other.summary }}")
        output_node = ast.body[0]
        getattr_node = output_node.nodes[0]

        result = provider.match(getattr_node)
        self.assertFalse(result.matched)


class TestAIProviderCache(TestCase):
    """测试 AIProvider 缓存功能"""

    def setUp(self):
        # 创建测试策略
        self.strategy = Strategy.objects.create(
            strategy_id=8888,
            strategy_name="Test Strategy for Cache",
            namespace="default",
        )

        # 创建测试风险
        now = timezone.now()
        self.risk = Risk.objects.create(
            risk_id="cache_test_risk_001",
            strategy_id=self.strategy.strategy_id,
            raw_event_id="raw_event_cache_001",
            event_time=now - timedelta(hours=1),
            event_end_time=now,
        )

        # 创建测试工具
        self.tool = Tool.objects.create(
            uid="test_tool_uid_001",
            name="Test Tool",
            namespace="default",
            tool_type="data_search",
            version=1,
            config={},
        )

        # 关联策略和工具
        self.strategy_tool = StrategyTool.objects.create(
            strategy=self.strategy,
            tool_uid=self.tool.uid,
            tool_version=1,
            field_name="test_field",
            field_source="data",
        )

    def tearDown(self):
        StrategyTool.objects.filter(strategy=self.strategy).delete()
        Tool.objects.filter(uid="test_tool_uid_001").delete()
        Risk.objects.filter(risk_id="cache_test_risk_001").delete()
        Strategy.objects.filter(strategy_id=8888).delete()

    def test_cache_disabled_by_default(self):
        """测试缓存默认关闭"""
        provider = AIProvider(
            context={"risk_id": self.risk.risk_id},
            ai_variables_config=[],
        )

        self.assertFalse(provider.enable_cache)

    def test_cache_enabled(self):
        """测试缓存启用"""
        provider = AIProvider(
            context={"risk_id": self.risk.risk_id},
            ai_variables_config=[],
            enable_cache=True,
        )

        self.assertTrue(provider.enable_cache)

    def test_generate_cache_key_contains_risk_id(self):
        """测试缓存 key 包含 risk_id"""
        provider = AIProvider(
            context={"risk_id": self.risk.risk_id},
            ai_variables_config=[],
            enable_cache=True,
        )

        cache_key = provider._generate_cache_key()

        # _generate_cache_key 只返回业务相关的 key 部分
        # UsingCache 会自动拼接 key_prefix 和 cache_type.key（ai_provider）
        self.assertIn(self.risk.risk_id, cache_key)

    def test_generate_cache_key_contains_strategy_updated_at(self):
        """测试缓存 key 包含策略更新时间"""
        # 更新策略
        self.strategy.updated_at = timezone.now()
        self.strategy.save()

        provider = AIProvider(
            context={"risk_id": self.risk.risk_id},
            ai_variables_config=[],
            enable_cache=True,
        )

        cache_key = provider._generate_cache_key()

        # 验证包含时间戳格式
        self.assertRegex(cache_key, r"\d{14}")

    def test_generate_cache_key_contains_tools_updated_at(self):
        """测试缓存 key 包含工具更新时间"""
        # 更新工具
        self.tool.updated_at = timezone.now()
        self.tool.save()

        provider = AIProvider(
            context={"risk_id": self.risk.risk_id},
            ai_variables_config=[],
            enable_cache=True,
        )

        cache_key = provider._generate_cache_key()

        # 验证 key 不为空
        self.assertTrue(len(cache_key) > 20)

    @mock.patch("services.web.risk.report.providers.api.bk_base.query_sync")
    def test_get_event_count(self, mock_query):
        """测试获取事件数量"""
        mock_query.return_value = {"list": [{"count": 100}]}

        provider = AIProvider(
            context={"risk_id": self.risk.risk_id},
            ai_variables_config=[],
            enable_cache=True,
        )

        count = provider._get_event_count(self.risk)

        self.assertEqual(count, 100)

    @mock.patch("services.web.risk.report.providers.api.bk_base.query_sync")
    def test_get_event_count_error_returns_zero(self, mock_query):
        """测试获取事件数量失败返回 0"""
        mock_query.side_effect = Exception("Query failed")

        provider = AIProvider(
            context={"risk_id": self.risk.risk_id},
            ai_variables_config=[],
            enable_cache=True,
        )

        count = provider._get_event_count(self.risk)

        self.assertEqual(count, 0)

    def test_cache_write_trigger_success(self):
        """测试成功结果触发缓存写入"""
        provider = AIProvider(
            context={"risk_id": self.risk.risk_id},
            ai_variables_config=[],
            enable_cache=True,
        )

        self.assertTrue(provider._cache_write_trigger("valid result"))

    def test_cache_write_trigger_failure(self):
        """测试失败结果不触发缓存写入"""
        provider = AIProvider(
            context={"risk_id": self.risk.risk_id},
            ai_variables_config=[],
            enable_cache=True,
        )

        self.assertFalse(provider._cache_write_trigger(f"{AI_ERROR_PREFIX}error{AI_ERROR_SUFFIX}"))
        self.assertFalse(provider._cache_write_trigger(""))
        self.assertFalse(provider._cache_write_trigger(None))

    def test_generate_cache_key_unknown_when_risk_not_found(self):
        """测试 Risk 不存在时缓存 key 为 unknown"""
        provider = AIProvider(
            context={"risk_id": "non_existent_risk_id_12345"},
            ai_variables_config=[],
            enable_cache=True,
        )

        cache_key = provider._generate_cache_key()
        self.assertEqual(cache_key, "unknown")

    def test_get_tools_max_updated_at_empty_when_no_tools(self):
        """测试策略无关联工具时返回空字符串"""
        # 删除工具关联
        StrategyTool.objects.filter(strategy=self.strategy).delete()

        provider = AIProvider(
            context={"risk_id": self.risk.risk_id},
            ai_variables_config=[],
            enable_cache=True,
        )

        result = provider._get_tools_max_updated_at(self.strategy.strategy_id)
        self.assertEqual(result, "")

    def test_get_strategy_updated_at_empty_when_no_strategy(self):
        """测试 Risk 无关联策略时返回空字符串"""
        provider = AIProvider(
            context={"risk_id": self.risk.risk_id},
            ai_variables_config=[],
            enable_cache=True,
        )

        # 创建一个 mock Risk 对象，strategy 为 None
        mock_risk = mock.MagicMock()
        mock_risk.strategy = None

        # 当策略不存在时应返回空字符串
        result = provider._get_strategy_updated_at(mock_risk)
        self.assertEqual(result, "")

    def test_get_strategy_updated_at_empty_when_no_updated_at(self):
        """测试策略存在但 updated_at 为空时返回空字符串"""
        provider = AIProvider(
            context={"risk_id": self.risk.risk_id},
            ai_variables_config=[],
            enable_cache=True,
        )

        # 创建一个 mock Risk 对象，strategy 存在但 updated_at 为 None
        mock_risk = mock.MagicMock()
        mock_risk.strategy = mock.MagicMock()
        mock_risk.strategy.updated_at = None

        # 当 updated_at 为空时应返回空字符串
        result = provider._get_strategy_updated_at(mock_risk)
        self.assertEqual(result, "")

    @mock.patch("services.web.risk.report.providers.api.bk_plugins_ai_audit_report.chat_completion")
    @mock.patch("services.web.risk.report.providers.api.bk_base.query_sync")
    def test_cache_hit_skips_api_call(self, mock_bkbase_query, mock_chat_completion):
        """测试缓存命中时不重复调用 AI API"""
        from django.core.cache import cache

        # 清除缓存
        cache.clear()

        # Mock 返回值
        mock_bkbase_query.return_value = {"list": [{"count": 10}]}
        mock_chat_completion.return_value = "这是 AI 生成的内容"

        ai_variables = [{"name": "ai.test_cache", "prompt_template": "测试缓存"}]

        # 第一次调用（缓存未命中，应调用 API）
        provider1 = AIProvider(
            context={"risk_id": self.risk.risk_id},
            ai_variables_config=ai_variables,
            enable_cache=True,
        )
        result1 = provider1.get(name="test_cache")

        # 验证第一次调用了 API
        self.assertEqual(mock_chat_completion.call_count, 1)
        self.assertIn("AI 生成的内容", result1)

        # 第二次调用（缓存命中，不应再次调用 API）
        provider2 = AIProvider(
            context={"risk_id": self.risk.risk_id},
            ai_variables_config=ai_variables,
            enable_cache=True,
        )
        result2 = provider2.get(name="test_cache")

        # 验证第二次没有再调用 API（call_count 仍为 1）
        self.assertEqual(mock_chat_completion.call_count, 1)
        self.assertEqual(result1, result2)

        # 清理缓存
        cache.clear()

    @mock.patch("services.web.risk.report.providers.api.bk_plugins_ai_audit_report.chat_completion")
    @mock.patch("services.web.risk.report.providers.api.bk_base.query_sync")
    def test_cache_invalidation_on_event_count_change(self, mock_bkbase_query, mock_chat_completion):
        """测试事件数量变化时缓存失效"""
        from django.core.cache import cache

        # 清除缓存
        cache.clear()

        ai_variables = [{"name": "ai.test_invalidation", "prompt_template": "测试失效"}]

        # 第一次调用，事件数为 10
        mock_bkbase_query.return_value = {"list": [{"count": 10}]}
        mock_chat_completion.return_value = "第一次生成"

        provider1 = AIProvider(
            context={"risk_id": self.risk.risk_id},
            ai_variables_config=ai_variables,
            enable_cache=True,
        )
        provider1.get(name="test_invalidation")  # 第一次调用
        self.assertEqual(mock_chat_completion.call_count, 1)

        # 第二次调用，事件数变为 20（缓存应失效）
        mock_bkbase_query.return_value = {"list": [{"count": 20}]}
        mock_chat_completion.return_value = "第二次生成"

        provider2 = AIProvider(
            context={"risk_id": self.risk.risk_id},
            ai_variables_config=ai_variables,
            enable_cache=True,
        )
        provider2.get(name="test_invalidation")  # 第二次调用

        # 验证因为事件数变化，API 被再次调用
        self.assertEqual(mock_chat_completion.call_count, 2)

        # 清理缓存
        cache.clear()
