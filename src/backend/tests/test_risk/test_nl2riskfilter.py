# -*- coding: utf-8 -*-
"""
NL2Risk 序列化器及工具函数单测
"""

from unittest.mock import patch

from services.web.risk.constants import NL2RiskFilterLogStatus
from services.web.risk.exceptions import NL2RiskFilterServiceError
from services.web.risk.handlers.nl2riskfilter import (
    build_nl2risk_user_message,
    extract_json_from_text,
)
from services.web.risk.models import NL2RiskFilterLog
from services.web.risk.resources.risk import (
    ListEventFieldsByStrategyBrief,
    ListNL2RiskFilterLog,
    NL2RiskFilter,
)
from services.web.risk.serializers import (
    ListNL2RiskFilterLogRequestSerializer,
    NL2RiskFilterRequestSerializer,
)
from tests.base import TestCase


class NL2RiskFilterRequestSerializerTest(TestCase):
    def test_valid_request(self):
        data = {
            "query": "最近一周的高危风险",
            "tags": [{"id": 1, "name": "重要"}],
            "strategies": [{"id": 10, "name": "异常登录"}],
        }
        serializer = NL2RiskFilterRequestSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["query"], "最近一周的高危风险")

    def test_query_required(self):
        data = {"tags": [], "strategies": []}
        serializer = NL2RiskFilterRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("query", serializer.errors)

    def test_empty_query_invalid(self):
        data = {"query": ""}
        serializer = NL2RiskFilterRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("query", serializer.errors)

    def test_tags_and_strategies_optional(self):
        data = {"query": "查询所有风险"}
        serializer = NL2RiskFilterRequestSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["tags"], [])
        self.assertEqual(serializer.validated_data["strategies"], [])

    def test_tag_item_structure(self):
        data = {
            "query": "test",
            "tags": [{"id": "not_int", "name": "tag"}],
        }
        serializer = NL2RiskFilterRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("tags", serializer.errors)


class BuildNL2RiskUserMessageTest(TestCase):
    @patch("services.web.risk.handlers.nl2riskfilter.datetime")
    def test_basic_message(self, mock_datetime):
        from datetime import datetime as real_datetime

        mock_datetime.now.return_value = real_datetime(2026, 3, 5, 10, 30, 0)
        mock_datetime.side_effect = lambda *a, **kw: real_datetime(*a, **kw)

        tags = [{"id": 1, "name": "重要"}]
        strategies = [{"id": 10, "name": "异常登录"}]
        result = build_nl2risk_user_message("高危风险", tags, strategies, username="testuser")

        self.assertIn("2026-03-05T10:30:00", result)
        self.assertIn("当前请求人：testuser", result)
        self.assertIn("id=1, 名称=重要", result)
        self.assertIn("id=10, 名称=异常登录", result)
        self.assertIn("用户查询：高危风险", result)

    def test_empty_tags_and_strategies(self):
        result = build_nl2risk_user_message("查询", [], [])
        self.assertIn("可用标签：\n无", result)
        self.assertIn("可用策略：\n无", result)

    def test_message_contains_current_time(self):
        result = build_nl2risk_user_message("test", [], [])
        self.assertIn("当前时间：", result)
        self.assertRegex(result, r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")

    def test_default_username(self):
        result = build_nl2risk_user_message("test", [], [])
        self.assertIn("当前请求人：未知", result)

    def test_custom_username(self):
        result = build_nl2risk_user_message("test", [], [], username="xxx")
        self.assertIn("当前请求人：xxx", result)


class ExtractJsonFromTextTest(TestCase):
    def test_pure_json(self):
        text = '{"key": "value", "num": 42}'
        result = extract_json_from_text(text)
        self.assertEqual(result, {"key": "value", "num": 42})

    def test_empty_json_object(self):
        self.assertEqual(extract_json_from_text("{}"), {})

    def test_empty_input_returns_empty(self):
        self.assertEqual(extract_json_from_text(""), {})
        self.assertEqual(extract_json_from_text(None), {})
        self.assertEqual(extract_json_from_text("   "), {})

    def test_invalid_json_returns_empty(self):
        self.assertEqual(extract_json_from_text("{key: value}"), {})

    def test_non_dict_returns_empty(self):
        self.assertEqual(extract_json_from_text("[1, 2, 3]"), {})
        self.assertEqual(extract_json_from_text('"just a string"'), {})

    def test_non_json_text_returns_empty(self):
        self.assertEqual(extract_json_from_text("这段文本没有任何JSON内容"), {})

    def test_nested_json(self):
        text = '{"event_filters": [{"field": "src_ip", "value": {"nested": true}}]}'
        result = extract_json_from_text(text)
        self.assertEqual(result["event_filters"][0]["field"], "src_ip")
        self.assertTrue(result["event_filters"][0]["value"]["nested"])

    def test_whitespace_padded_json(self):
        text = '  \n {"operator": "test"} \n  '
        self.assertEqual(extract_json_from_text(text), {"operator": "test"})


class NL2RiskFilterRequestTest(TestCase):
    """通过 resource.request() 走完整序列化器链"""

    def setUp(self):
        self.resource = NL2RiskFilter()

    @patch("services.web.risk.resources.risk.get_request_username", return_value="testuser")
    @patch("services.web.risk.resources.risk.api.bk_plugins_ai_agent.chat_completion")
    def test_ai_returns_json_string(self, mock_chat, mock_user):
        mock_chat.return_value = '{"risk_level": "HIGH", "status": "new"}'
        result = self.resource.request({"query": "高危风险"})
        self.assertEqual(result["filter_conditions"], {"risk_level": "HIGH", "status": "new"})
        self.assertEqual(result["message"], "")
        self.assertTrue(result["thread_id"])

    @patch("services.web.risk.resources.risk.get_request_username", return_value="testuser")
    @patch("services.web.risk.resources.risk.api.bk_plugins_ai_agent.chat_completion")
    def test_ai_returns_string(self, mock_chat, mock_user):
        mock_chat.return_value = '{"operator": "张三"}'
        result = self.resource.request({"query": "张三的风险"})
        self.assertEqual(result["filter_conditions"], {"operator": "张三"})

    @patch("services.web.risk.resources.risk.get_request_username", return_value="testuser")
    @patch("services.web.risk.resources.risk.api.bk_plugins_ai_agent.chat_completion")
    def test_ai_call_fails(self, mock_chat, mock_user):
        mock_chat.side_effect = Exception("AI service timeout")
        with self.assertRaises(NL2RiskFilterServiceError):
            self.resource.request({"query": "测试"})

    @patch("services.web.risk.resources.risk.get_request_username", return_value="testuser")
    @patch("services.web.risk.resources.risk.api.bk_plugins_ai_agent.chat_completion")
    def test_ai_returns_empty_string(self, mock_chat, mock_user):
        mock_chat.return_value = ""
        result = self.resource.request({"query": "测试"})
        self.assertEqual(result["filter_conditions"], {})
        self.assertEqual(result["message"], "")
        self.assertTrue(result["thread_id"])

    @patch("services.web.risk.resources.risk.get_request_username", return_value="testuser")
    @patch("services.web.risk.resources.risk.api.bk_plugins_ai_agent.chat_completion")
    def test_ai_returns_chinese_message(self, mock_chat, mock_user):
        """AI 无法解析时返回中文说明，message 应携带原文"""
        ai_text = '根据您提供的工具调用结果，我找到了多个与"IP"相关的字段，但没有明确匹配"目标IP"的字段。'
        mock_chat.return_value = ai_text
        result = self.resource.request({"query": "目标IP为10.0.0.1的风险"})
        self.assertEqual(result["filter_conditions"], {})
        self.assertEqual(result["message"], ai_text)

    @patch("services.web.risk.resources.risk.get_request_username", return_value="testuser")
    @patch("services.web.risk.resources.risk.api.bk_plugins_ai_agent.chat_completion")
    def test_thread_id_passthrough(self, mock_chat, mock_user):
        """前端传入 thread_id 时应原样返回"""
        mock_chat.return_value = '{"status": "new"}'
        result = self.resource.request({"query": "新风险", "thread_id": "my-thread-001"})
        self.assertEqual(result["thread_id"], "my-thread-001")
        call_kwargs = mock_chat.call_args
        self.assertEqual(call_kwargs.kwargs.get("execute_kwargs", {}).get("thread_id"), "my-thread-001")

    @patch("services.web.risk.resources.risk.get_request_username", return_value="testuser")
    @patch("services.web.risk.resources.risk.api.bk_plugins_ai_agent.chat_completion")
    def test_thread_id_auto_generated(self, mock_chat, mock_user):
        """未传 thread_id 时应自动生成 uuid"""
        mock_chat.return_value = "{}"
        result = self.resource.request({"query": "测试"})
        thread_id = result["thread_id"]
        self.assertTrue(thread_id)
        self.assertEqual(len(thread_id), 36)  # uuid4 格式


class ListEventFieldsByStrategyBriefTest(TestCase):
    """ListEventFieldsByStrategyBrief 去重、简化、keyword 过滤"""

    MOCK_RAW_RESULTS = [
        {"field_name": "access_source_ip", "display_name": "来源IP(access_source_ip)"},
        {"field_name": "username", "display_name": "用户名"},
        {"field_name": "action", "display_name": "操作类型"},
        {"field_name": "dst_ip", "display_name": "目标IP"},
        {"field_name": "host_name", "display_name": "host_name"},
        {"field_name": "access_source_ip", "display_name": "access_source_ip"},
    ]

    def setUp(self):
        self.resource = ListEventFieldsByStrategyBrief()

    @patch.object(ListEventFieldsByStrategyBrief.__bases__[0], "perform_request")
    def test_dedup_and_simplify(self, mock_parent):
        """去重 + field_name==display_name 时不返回 display_name"""
        mock_parent.return_value = self.MOCK_RAW_RESULTS
        data = self.resource.request({"strategy_ids": ""})
        results = data["results"]

        field_names = [r["field_name"] for r in results]
        self.assertEqual(len(field_names), len(set(field_names)))

        host_entry = next(r for r in results if r["field_name"] == "host_name")
        self.assertNotIn("display_name", host_entry)

        ip_entry = next(r for r in results if r["field_name"] == "access_source_ip")
        self.assertEqual(ip_entry["display_name"], "来源IP(access_source_ip)")

    @patch.object(ListEventFieldsByStrategyBrief.__bases__[0], "perform_request")
    def test_keyword_single(self, mock_parent):
        """单个 keyword 过滤"""
        mock_parent.return_value = self.MOCK_RAW_RESULTS
        data = self.resource.request({"strategy_ids": "", "keyword": "用户名"})

        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["field_name"], "username")

    @patch.object(ListEventFieldsByStrategyBrief.__bases__[0], "perform_request")
    def test_keyword_multiple_or(self, mock_parent):
        """多个 keyword 逗号分隔，OR 匹配"""
        mock_parent.return_value = self.MOCK_RAW_RESULTS
        data = self.resource.request({"strategy_ids": "", "keyword": "源IP,来源IP"})

        field_names = {r["field_name"] for r in data["results"]}
        self.assertIn("access_source_ip", field_names)

    @patch.object(ListEventFieldsByStrategyBrief.__bases__[0], "perform_request")
    def test_keyword_case_insensitive(self, mock_parent):
        """keyword 大小写不敏感"""
        mock_parent.return_value = self.MOCK_RAW_RESULTS
        data = self.resource.request({"strategy_ids": "", "keyword": "HOST_NAME"})

        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["field_name"], "host_name")

    @patch.object(ListEventFieldsByStrategyBrief.__bases__[0], "perform_request")
    def test_keyword_no_match(self, mock_parent):
        """keyword 无匹配返回空"""
        mock_parent.return_value = self.MOCK_RAW_RESULTS
        data = self.resource.request({"strategy_ids": "", "keyword": "不存在的字段"})

        self.assertEqual(data["results"], [])

    @patch.object(ListEventFieldsByStrategyBrief.__bases__[0], "perform_request")
    def test_keyword_empty_returns_all(self, mock_parent):
        """keyword 为空时返回全部"""
        mock_parent.return_value = self.MOCK_RAW_RESULTS
        data = self.resource.request({"strategy_ids": "", "keyword": ""})

        self.assertEqual(len(data["results"]), 5)

    @patch.object(ListEventFieldsByStrategyBrief.__bases__[0], "perform_request")
    def test_keyword_matches_field_name(self, mock_parent):
        """keyword 匹配 field_name"""
        mock_parent.return_value = self.MOCK_RAW_RESULTS
        data = self.resource.request({"strategy_ids": "", "keyword": "dst_ip"})

        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["field_name"], "dst_ip")


class NL2RiskFilterLogModelTest(TestCase):
    """NL2RiskFilterLog Model 测试"""

    def test_create_log_success(self):
        """成功创建日志记录"""
        log = NL2RiskFilterLog.objects.create(
            query="最近一周的高危风险",
            request_params={"query": "最近一周的高危风险", "tags": [], "strategies": []},
            response_data={"filter_conditions": {"level": "high"}, "thread_id": "t1", "message": ""},
            status=NL2RiskFilterLogStatus.SUCCESS,
            created_by="admin",
            updated_by="admin",
        )
        self.assertIsNotNone(log.id)
        self.assertEqual(log.query, "最近一周的高危风险")
        self.assertEqual(log.status, NL2RiskFilterLogStatus.SUCCESS)
        self.assertEqual(log.created_by, "admin")

    def test_create_log_api_error(self):
        """创建 api_error 状态的日志"""
        log = NL2RiskFilterLog.objects.create(
            query="测试查询",
            request_params={"query": "测试查询"},
            response_data={},
            status=NL2RiskFilterLogStatus.API_ERROR,
            error_message="Connection timeout",
            created_by="user1",
            updated_by="user1",
        )
        self.assertEqual(log.status, NL2RiskFilterLogStatus.API_ERROR)
        self.assertEqual(log.error_message, "Connection timeout")

    def test_ordering_by_created_at_desc(self):
        """日志按 created_at 倒序排列"""
        for i in range(3):
            NL2RiskFilterLog.objects.create(
                query=f"query_{i}",
                request_params={},
                response_data={},
                status=NL2RiskFilterLogStatus.SUCCESS,
                created_by="admin",
                updated_by="admin",
            )
        logs = list(NL2RiskFilterLog.objects.all())
        self.assertEqual(len(logs), 3)
        for i in range(len(logs) - 1):
            self.assertGreaterEqual(logs[i].created_at, logs[i + 1].created_at)


class SaveNL2RiskFilterLogModelTest(TestCase):
    """NL2RiskFilterLog.save_nl2risk_filter_log 模型方法测试"""

    def test_save_success_log(self):
        """正常保存成功日志"""
        NL2RiskFilterLog.save_nl2risk_filter_log(
            username="admin",
            query="高危风险",
            request_params={"query": "高危风险"},
            response_data={"filter_conditions": {"level": "high"}},
            status=NL2RiskFilterLogStatus.SUCCESS,
        )
        self.assertEqual(NL2RiskFilterLog.objects.count(), 1)
        log = NL2RiskFilterLog.objects.first()
        self.assertEqual(log.query, "高危风险")
        self.assertEqual(log.status, NL2RiskFilterLogStatus.SUCCESS)
        self.assertEqual(log.created_by, "admin")

    def test_save_error_log(self):
        """保存失败日志"""
        NL2RiskFilterLog.save_nl2risk_filter_log(
            username="user1",
            query="测试",
            request_params={},
            response_data={},
            status=NL2RiskFilterLogStatus.API_ERROR,
            error_message="timeout",
        )
        log = NL2RiskFilterLog.objects.first()
        self.assertEqual(log.status, NL2RiskFilterLogStatus.API_ERROR)
        self.assertEqual(log.error_message, "timeout")

    @patch("services.web.risk.models.NL2RiskFilterLog.objects.create")
    def test_save_fail_silent(self, mock_create):
        """保存异常时不抛出，fail-silent"""
        mock_create.side_effect = Exception("DB error")
        # 不应抛出异常
        NL2RiskFilterLog.save_nl2risk_filter_log(
            username="admin",
            query="test",
            request_params={},
            response_data={},
        )

    def test_query_truncation(self):
        """超长 query 被截断到 2048 字符"""
        long_query = "x" * 3000
        NL2RiskFilterLog.save_nl2risk_filter_log(
            username="admin",
            query=long_query,
            request_params={},
            response_data={},
        )
        log = NL2RiskFilterLog.objects.first()
        self.assertEqual(len(log.query), 2048)


class NL2RiskFilterWithLoggingTest(TestCase):
    """NL2RiskFilter Resource 日志记录集成测试"""

    def setUp(self):
        self.resource = NL2RiskFilter()

    @patch("services.web.risk.resources.risk.NL2RiskFilterLog.save_nl2risk_filter_log")
    @patch("services.web.risk.resources.risk.get_request_username", return_value="admin")
    @patch("services.web.risk.resources.risk.api.bk_plugins_ai_agent.chat_completion")
    def test_success_logs_saved(self, mock_chat, mock_user, mock_save_log):
        """AI 返回有效 JSON 时记录 success 日志"""
        mock_chat.return_value = '{"filter_conditions": {"level": "high"}}'

        result = self.resource.request({"query": "高危风险", "tags": [], "strategies": []})

        self.assertTrue(result["filter_conditions"])
        mock_save_log.assert_called_once()
        call_kwargs = mock_save_log.call_args[1]
        self.assertEqual(call_kwargs["status"], NL2RiskFilterLogStatus.SUCCESS)
        self.assertEqual(call_kwargs["username"], "admin")
        self.assertIn("result", call_kwargs)
        self.assertIn("message", call_kwargs)

    @patch("services.web.risk.resources.risk.NL2RiskFilterLog.save_nl2risk_filter_log")
    @patch("services.web.risk.resources.risk.get_request_username", return_value="admin")
    @patch("services.web.risk.resources.risk.api.bk_plugins_ai_agent.chat_completion")
    def test_parse_failed_logs_saved(self, mock_chat, mock_user, mock_save_log):
        """AI 返回非 JSON 文本时记录 parse_failed 日志"""
        mock_chat.return_value = "抱歉，我无法理解您的查询"

        result = self.resource.request({"query": "无效查询", "tags": [], "strategies": []})

        self.assertFalse(result["filter_conditions"])
        mock_save_log.assert_called_once()
        call_kwargs = mock_save_log.call_args[1]
        self.assertEqual(call_kwargs["status"], NL2RiskFilterLogStatus.PARSE_FAILED)

    @patch("services.web.risk.resources.risk.NL2RiskFilterLog.save_nl2risk_filter_log")
    @patch("services.web.risk.resources.risk.get_request_username", return_value="admin")
    @patch("services.web.risk.resources.risk.api.bk_plugins_ai_agent.chat_completion")
    def test_api_error_logs_saved(self, mock_chat, mock_user, mock_save_log):
        """AI 平台异常时记录 api_error 日志"""
        mock_chat.side_effect = Exception("Connection refused")

        with self.assertRaises(NL2RiskFilterServiceError):
            self.resource.request({"query": "测试", "tags": [], "strategies": []})

        mock_save_log.assert_called_once()
        call_kwargs = mock_save_log.call_args[1]
        self.assertEqual(call_kwargs["status"], NL2RiskFilterLogStatus.API_ERROR)
        self.assertIn("Connection refused", call_kwargs["error_message"])


class ListNL2RiskFilterLogRequestSerializerTest(TestCase):
    """ListNL2RiskFilterLogRequestSerializer 测试"""

    def test_defaults(self):
        """默认参数验证"""
        ser = ListNL2RiskFilterLogRequestSerializer(data={})
        self.assertTrue(ser.is_valid(), ser.errors)
        self.assertEqual(ser.validated_data["status"], "")

    def test_status_filter(self):
        """有效 status 值通过验证"""
        ser = ListNL2RiskFilterLogRequestSerializer(data={"status": "success"})
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_invalid_status(self):
        """无效 status 值被拒绝"""
        ser = ListNL2RiskFilterLogRequestSerializer(data={"status": "invalid_status"})
        self.assertFalse(ser.is_valid())


class ListNL2RiskFilterLogResourceTest(TestCase):
    """ListNL2RiskFilterLog Resource 测试

    注意：分页由框架 enable_paginate=True 在 ViewSet 层处理，
    perform_request 只负责返回过滤后的 queryset。
    """

    def setUp(self):
        self.resource = ListNL2RiskFilterLog()
        # 预置测试数据
        for i in range(5):
            NL2RiskFilterLog.objects.create(
                query=f"query_{i}",
                request_params={"query": f"query_{i}"},
                response_data={"filter_conditions": {"level": "high"}},
                status=NL2RiskFilterLogStatus.SUCCESS,
                created_by="admin",
                updated_by="admin",
            )
        NL2RiskFilterLog.objects.create(
            query="failed_query",
            request_params={"query": "failed_query"},
            response_data={},
            status=NL2RiskFilterLogStatus.PARSE_FAILED,
            created_by="admin",
            updated_by="admin",
        )
        NL2RiskFilterLog.objects.create(
            query="other_user_query",
            request_params={"query": "other"},
            response_data={},
            status=NL2RiskFilterLogStatus.SUCCESS,
            created_by="other_user",
            updated_by="other_user",
        )

    @patch("services.web.risk.resources.risk.get_request_username", return_value="admin")
    def test_list_own_records_only(self, mock_user):
        """只返回当前用户的记录"""
        results = self.resource.request({})
        self.assertEqual(len(results), 6)  # admin 有 5 + 1 条
        for log in results:
            self.assertEqual(log["created_by"], "admin")

    @patch("services.web.risk.resources.risk.get_request_username", return_value="admin")
    def test_status_filter(self, mock_user):
        """按 status 过滤"""
        results = self.resource.request({"status": NL2RiskFilterLogStatus.PARSE_FAILED})
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], NL2RiskFilterLogStatus.PARSE_FAILED)

    @patch("services.web.risk.resources.risk.get_request_username", return_value="admin")
    def test_returns_full_queryset(self, mock_user):
        """返回完整结果（分页由框架 enable_paginate 处理）"""
        results = self.resource.request({})
        # 应返回所有 admin 的记录，未手动切片
        self.assertEqual(len(results), 6)

    @patch("services.web.risk.resources.risk.get_request_username", return_value="other_user")
    def test_other_user_isolation(self, mock_user):
        """不同用户数据隔离"""
        results = self.resource.request({})
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["created_by"], "other_user")
