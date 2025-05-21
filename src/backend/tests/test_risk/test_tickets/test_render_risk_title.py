from django.test import TestCase
from unittest.mock import patch
import json

from services.web.risk.handlers.risk import RiskHandler, RiskTitleUndefined
from services.web.strategy_v2.models import Strategy


class TestListRenderingInRiskTitle(TestCase):
    """测试 render_risk_title 方法中 list 变量的渲染逻辑"""

    def setUp(self):
        self.strategy = Strategy.objects.create(
            strategy_id=1,
            risk_title="Risk: {{ event_data.list_field }} | {{ event_evidence.nested_list }}"
        )

    def test_simple_list_rendering(self):
        """测试简单列表的逗号拼接（正确格式的 event_evidence）"""
        test_data = {
            "strategy_id": 1,
            "event_data": {"list_field": ["a", "b", "c"]},
            "event_evidence": json.dumps([{"nested_list": [1, 2, 3]}])
        }
        result = RiskHandler.render_risk_title(test_data)
        self.assertEqual(result, "Risk: a, b, c | 1, 2, 3")

    def test_empty_list_rendering(self):
        """测试空列表渲染（event_evidence 包含空列表）"""
        test_data = {
            "strategy_id": 1,
            "event_data": {"list_field": []},
            "event_evidence": json.dumps([{"nested_list": []}])
        }
        result = RiskHandler.render_risk_title(test_data)
        self.assertEqual(result, "Risk:  | ")

    def test_nested_list_rendering(self):
        """测试嵌套列表渲染（仅处理一级列表，嵌套内容转为字符串）"""
        test_data = {
            "strategy_id": 1,
            "event_data": {"list_field": [["a", "b"], ["c"]]},
            "event_evidence": json.dumps([{"nested_list": [[1], [2, 3]]}])
        }
        result = RiskHandler.render_risk_title(test_data)
        self.assertEqual(result, "Risk: ['a', 'b'], ['c'] | [1], [2, 3]")

    def test_mixed_data_types(self):
        """测试混合数据类型列表渲染（自动转换为字符串拼接）"""
        test_data = {
            "strategy_id": 1,
            "event_data": {"list_field": ["text", 123, True, None]},
            "event_evidence": json.dumps([{"nested_list": [1.5, "string"]}])
        }
        result = RiskHandler.render_risk_title(test_data)
        self.assertEqual(result, "Risk: text, 123, True, None | 1.5, string")

    @patch('services.web.risk.handlers.risk.Jinja2Renderer')
    def test_template_syntax_with_lists(self, mock_renderer_class):
        """测试模板语法（如过滤器）和模拟渲染逻辑"""
        self.strategy.risk_title = "Count: {{ event_data.numbers|length }} | {{ event_data.numbers }}"
        self.strategy.save()

        test_data = {
            "strategy_id": 1,
            "event_data": {"numbers": [10, 20, 30]},
            "event_evidence": json.dumps([{}])
        }

        mock_renderer_instance = mock_renderer_class.return_value
        mock_renderer_instance.jinja_render.return_value = "Count: 3 | 10, 20, 30"

        result = RiskHandler.render_risk_title(test_data)

        # 验证 Jinja2Renderer 的初始化参数是否包含 RiskTitleUndefined
        mock_renderer_class.assert_called_once_with(undefined=RiskTitleUndefined)
        mock_renderer_instance.jinja_render.assert_called_once_with(
            self.strategy.risk_title,
            {
                "event_data": {"numbers": "10, 20, 30"},
                "event_evidence": {},
                "strategy_id": 1
            }
        )

    def test_non_ascii_chars_in_list(self):
        """测试包含非ASCII字符的列表渲染"""
        test_data = {
            "strategy_id": 1,
            "event_data": {"list_field": ["中文", "日本語", "한국어"]},
            "event_evidence": json.dumps([{"nested_list": ["€", "£"]}])
        }
        result = RiskHandler.render_risk_title(test_data)
        self.assertEqual(result, "Risk: 中文, 日本語, 한국어 | €, £")

    def test_missing_nested_list_key(self):
        """测试event_evidence中缺少目标键时的渲染"""
        test_data = {
            "strategy_id": 1,
            "event_data": {"list_field": ["a", "b", "c"]},
            "event_evidence": json.dumps([{"other_key": "value"}])
        }
        result = RiskHandler.render_risk_title(test_data)
        self.assertEqual(result, "Risk: a, b, c | (未获取到变量值:nested_list)")

    def test_invalid_event_evidence_json(self):
        """测试event_evidence为非法JSON格式时的处理"""
        test_data = {
            "strategy_id": 1,
            "event_data": {"list_field": ["a", "b", "c"]},
            "event_evidence": "not_a_json"
        }
        result = RiskHandler.render_risk_title(test_data)
        self.assertEqual(result, "Risk: a, b, c | (未获取到变量值:nested_list)")