# -*- coding: utf-8 -*-
"""
EventProvider 和 EventProviderSqlBuilder 测试

测试设计原则：
1. EventProviderSqlBuilder：完整 SQL 验证，一个测试覆盖所有聚合函数
2. EventProvider：精简但覆盖全面，验证类型匹配和参数传递
"""
from datetime import datetime
from unittest import mock

from bk_resource.exceptions import APIRequestError
from jinja2 import Environment, nodes

from core.sql.constants import AggregateType, FieldType
from services.web.risk.constants import EVENT_QUERY_FAILED, AggregationFunction
from services.web.risk.handlers.event_provider_sql import (
    EventFieldConfig,
    EventProviderSqlBuilder,
)
from services.web.risk.report.providers import EventProvider
from tests.base import TestCase


class TestEventProviderSqlBuilder(TestCase):
    """EventProviderSqlBuilder SQL 完整性测试"""

    TABLE_NAME = "591_test_table.doris"
    STRATEGY_ID = 1001
    RAW_EVENT_ID = "raw_event_abc"
    START_TIME = 1735689600000  # 2025-01-01 00:00:00 UTC (TestEventProviderSqlBuilder 专用)
    END_TIME = 1735776000000  # 2025-01-02 00:00:00 UTC (TestEventProviderSqlBuilder 专用)

    # 基础 WHERE 条件（复用）
    BASE_WHERE = (
        f"WHERE `t`.`strategy_id`={STRATEGY_ID} "
        f"AND `t`.`raw_event_id`='{RAW_EVENT_ID}' "
        f"AND `t`.`dtEventTimeStamp` BETWEEN {START_TIME} AND {END_TIME}"
    )

    def setUp(self):
        self.builder = EventProviderSqlBuilder(
            table_name=self.TABLE_NAME,
            strategy_id=self.STRATEGY_ID,
            raw_event_id=self.RAW_EVENT_ID,
            start_time=self.START_TIME,
            end_time=self.END_TIME,
        )

    # --- LIST/LIST_DISTINCT 非 STRING 字段跳过 CAST 验证 ---

    def test_aggregate_sql_list_distinct_long_field_no_cast(self):
        """测试 LIST_DISTINCT 聚合对 LONG 类型字段不做 CAST

        GROUP_CONCAT 要求参数是 STRING 类型，即使 field_type 是 LONG，
        也应跳过 CAST，直接使用 JSON_EXTRACT_STRING 输出。
        """
        fields = [
            EventFieldConfig(
                raw_name="gse索引",
                display_name="gse索引",
                field_type=FieldType.LONG,  # 字段类型是 LONG
                aggregate=AggregateType.LIST_DISTINCT,  # 但聚合是 LIST_DISTINCT
            )
        ]
        sql = self.builder.build_aggregate_sql(fields)

        # 验证：不应出现 CAST ... AS BIGINT，应保持 STRING
        self.assertNotIn("CAST", sql)
        self.assertNotIn("BIGINT", sql)
        # 应使用 GROUP_CONCAT(DISTINCT ...)
        self.assertIn("GROUP_CONCAT(DISTINCT", sql)
        self.assertIn("JSON_EXTRACT_STRING", sql)

    def test_aggregate_sql_list_long_field_no_cast(self):
        """测试 LIST 聚合对 LONG 类型字段不做 CAST"""
        fields = [
            EventFieldConfig(
                raw_name="event_count",
                display_name="event_count",
                field_type=FieldType.LONG,
                aggregate=AggregateType.LIST,
            )
        ]
        sql = self.builder.build_aggregate_sql(fields)

        # 验证：不应出现 CAST
        self.assertNotIn("CAST", sql)
        # 应使用 GROUP_CONCAT(...)（无 DISTINCT）
        self.assertIn("GROUP_CONCAT(JSON_EXTRACT_STRING", sql)
        self.assertNotIn("DISTINCT", sql)

    # --- 聚合查询 SQL 完整验证 ---

    def test_aggregate_sql_count(self):
        """测试 COUNT 聚合 SQL"""
        fields = [
            EventFieldConfig(
                raw_name="event_id",
                display_name="event_id",
                field_type=FieldType.LONG,
                aggregate=AggregateType.COUNT,
            )
        ]
        sql = self.builder.build_aggregate_sql(fields)

        expected = (
            "SELECT COUNT(CAST(JSON_EXTRACT_STRING(`t`.`event_data`,'$.event_id') AS BIGINT)) `event_id` "
            f"FROM {self.TABLE_NAME} `t` {self.BASE_WHERE}"
        )
        self.assertEqual(sql, expected)

    def test_aggregate_sql_count_distinct(self):
        """测试 COUNT_DISTINCT 聚合 SQL"""
        fields = [
            EventFieldConfig(
                raw_name="user_id",
                display_name="user_id",
                field_type=FieldType.STRING,
                aggregate=AggregateType.DISCOUNT,
            )
        ]
        sql = self.builder.build_aggregate_sql(fields)

        # DISCOUNT 当前映射为 COUNT（非 COUNT DISTINCT）
        expected = (
            "SELECT COUNT(DISTINCT JSON_EXTRACT_STRING(`t`.`event_data`,'$.user_id')) `user_id` "
            f"FROM {self.TABLE_NAME} `t` {self.BASE_WHERE}"
        )
        self.assertEqual(sql, expected)

    def test_aggregate_sql_sum(self):
        """测试 SUM 聚合 SQL（LONG 类型 CAST 到 BIGINT）"""
        fields = [
            EventFieldConfig(
                raw_name="amount",
                display_name="amount",
                field_type=FieldType.LONG,
                aggregate=AggregateType.SUM,
            )
        ]
        sql = self.builder.build_aggregate_sql(fields)

        expected = (
            "SELECT SUM(CAST(JSON_EXTRACT_STRING(`t`.`event_data`,'$.amount') AS BIGINT)) `amount` "
            f"FROM {self.TABLE_NAME} `t` {self.BASE_WHERE}"
        )
        self.assertEqual(sql, expected)

    def test_aggregate_sql_avg(self):
        """测试 AVG 聚合 SQL"""
        fields = [
            EventFieldConfig(
                raw_name="score",
                display_name="score",
                field_type=FieldType.LONG,
                aggregate=AggregateType.AVG,
            )
        ]
        sql = self.builder.build_aggregate_sql(fields)

        expected = (
            "SELECT AVG(CAST(JSON_EXTRACT_STRING(`t`.`event_data`,'$.score') AS BIGINT)) `score` "
            f"FROM {self.TABLE_NAME} `t` {self.BASE_WHERE}"
        )
        self.assertEqual(sql, expected)

    def test_aggregate_sql_max(self):
        """测试 MAX 聚合 SQL"""
        fields = [
            EventFieldConfig(
                raw_name="price",
                display_name="price",
                field_type=FieldType.LONG,
                aggregate=AggregateType.MAX,
            )
        ]
        sql = self.builder.build_aggregate_sql(fields)

        expected = (
            "SELECT MAX(CAST(JSON_EXTRACT_STRING(`t`.`event_data`,'$.price') AS BIGINT)) `price` "
            f"FROM {self.TABLE_NAME} `t` {self.BASE_WHERE}"
        )
        self.assertEqual(sql, expected)

    def test_aggregate_sql_min(self):
        """测试 MIN 聚合 SQL"""
        fields = [
            EventFieldConfig(
                raw_name="latency",
                display_name="latency",
                field_type=FieldType.LONG,
                aggregate=AggregateType.MIN,
            )
        ]
        sql = self.builder.build_aggregate_sql(fields)

        expected = (
            "SELECT MIN(CAST(JSON_EXTRACT_STRING(`t`.`event_data`,'$.latency') AS BIGINT)) `latency` "
            f"FROM {self.TABLE_NAME} `t` {self.BASE_WHERE}"
        )
        self.assertEqual(sql, expected)

    def test_aggregate_sql_list(self):
        """测试 LIST 聚合 SQL（GROUP_CONCAT）"""
        fields = [
            EventFieldConfig(
                raw_name="action",
                display_name="action",
                field_type=FieldType.STRING,
                aggregate=AggregateType.LIST,
            )
        ]
        sql = self.builder.build_aggregate_sql(fields)

        expected = (
            "SELECT GROUP_CONCAT(JSON_EXTRACT_STRING(`t`.`event_data`,'$.action')) `action` "
            f"FROM {self.TABLE_NAME} `t` {self.BASE_WHERE}"
        )
        self.assertEqual(sql, expected)

    def test_aggregate_sql_list_distinct(self):
        """测试 LIST_DISTINCT 聚合 SQL"""
        fields = [
            EventFieldConfig(
                raw_name="category",
                display_name="category",
                field_type=FieldType.STRING,
                aggregate=AggregateType.LIST_DISTINCT,
            )
        ]
        sql = self.builder.build_aggregate_sql(fields)

        expected = (
            "SELECT GROUP_CONCAT(DISTINCT JSON_EXTRACT_STRING(`t`.`event_data`,'$.category')) `category` "
            f"FROM {self.TABLE_NAME} `t` {self.BASE_WHERE}"
        )
        self.assertEqual(sql, expected)

    # --- First / Latest SQL 完整验证 ---

    def test_first_sql(self):
        """测试 FIRST SQL（ORDER BY ASC LIMIT 1）"""
        fields = [
            EventFieldConfig(
                raw_name="username",
                display_name="username",
                field_type=FieldType.STRING,
            )
        ]
        sql = self.builder.build_first_sql(fields)

        expected = (
            "SELECT JSON_EXTRACT_STRING(`t`.`event_data`,'$.username') `username` "
            f"FROM {self.TABLE_NAME} `t` {self.BASE_WHERE} "
            "ORDER BY `t`.`dtEventTimeStamp` ASC LIMIT 1"
        )
        self.assertEqual(sql, expected)

    def test_latest_sql(self):
        """测试 LATEST SQL（ORDER BY DESC LIMIT 1）"""
        fields = [
            EventFieldConfig(
                raw_name="ip",
                display_name="ip",
                field_type=FieldType.STRING,
            )
        ]
        sql = self.builder.build_latest_sql(fields)

        expected = (
            "SELECT JSON_EXTRACT_STRING(`t`.`event_data`,'$.ip') `ip` "
            f"FROM {self.TABLE_NAME} `t` {self.BASE_WHERE} "
            "ORDER BY `t`.`dtEventTimeStamp` DESC LIMIT 1"
        )
        self.assertEqual(sql, expected)

    # --- 类型转换验证 ---

    def test_field_type_cast_double(self):
        """测试 DOUBLE 类型的 CAST"""
        fields = [
            EventFieldConfig(
                raw_name="rate",
                display_name="rate",
                field_type=FieldType.DOUBLE,
                aggregate=AggregateType.SUM,
            )
        ]
        sql = self.builder.build_aggregate_sql(fields)

        expected = (
            "SELECT SUM(CAST(JSON_EXTRACT_STRING(`t`.`event_data`,'$.rate') AS DOUBLE)) `rate` "
            f"FROM {self.TABLE_NAME} `t` {self.BASE_WHERE}"
        )
        self.assertEqual(sql, expected)

    def test_field_type_string_no_cast(self):
        """测试 STRING 类型无需 CAST（first/latest 场景）"""
        fields = [
            EventFieldConfig(
                raw_name="name",
                display_name="name",
                field_type=FieldType.STRING,
            )
        ]
        sql = self.builder.build_first_sql(fields)

        # STRING 类型不 CAST，直接 JSON_EXTRACT_STRING
        self.assertIn("JSON_EXTRACT_STRING(`t`.`event_data`,'$.name') `name`", sql)
        self.assertNotIn("CAST", sql)

    # --- 边界情况 ---

    def test_empty_fields_returns_none(self):
        """测试空字段列表返回 None"""
        self.assertIsNone(self.builder.build_aggregate_sql([]))
        self.assertIsNone(self.builder.build_first_sql([]))
        self.assertIsNone(self.builder.build_latest_sql([]))


class TestEventProviderMatch(TestCase):
    """EventProvider.match() 匹配测试"""

    def setUp(self):
        self.provider = EventProvider(risk_id="test_risk_123")

    def _parse_expr(self, expr: str) -> nodes.Node:
        """解析 Jinja2 表达式为 AST 节点"""
        env = Environment()
        template = env.parse(f"{{{{ {expr} }}}}")
        return template.body[0].nodes[0]

    def test_match_all_aggregation_functions(self):
        """测试所有聚合函数的匹配"""
        for func in AggregationFunction.values:
            with self.subTest(function=func):
                node = self._parse_expr(f"{func}(event.field)")
                result = self.provider.match(node)
                self.assertTrue(result.matched, f"函数 {func} 应该被匹配")
                self.assertEqual(result.call_args["function"], func)
                self.assertEqual(result.call_args["field_name"], "field")
                # 验证用于渲染器 hash 计算的字段
                self.assertEqual(result.call_args["args"], ["event.field"])
                self.assertEqual(result.call_args["kwargs"], {})
                self.assertEqual(result.original_expr, f"{func}(event.field)")

    def test_match_returns_provider_instance(self):
        """测试匹配结果包含正确的 Provider 实例"""
        node = self._parse_expr("count(event.event_id)")
        result = self.provider.match(node)
        self.assertIs(result.provider, self.provider)

    def test_no_match_non_event_field(self):
        """测试不匹配非 event 字段"""
        node = self._parse_expr("count(risk.field)")
        self.assertFalse(self.provider.match(node).matched)

    def test_no_match_unknown_function(self):
        """测试不匹配未知函数"""
        node = self._parse_expr("unknown_func(event.field)")
        self.assertFalse(self.provider.match(node).matched)

    def test_no_match_simple_variable(self):
        """测试不匹配简单变量访问"""
        node = self._parse_expr("event.field")
        self.assertFalse(self.provider.match(node).matched)

    def test_no_match_no_args(self):
        """测试不匹配无参函数"""
        node = self._parse_expr("count()")
        self.assertFalse(self.provider.match(node).matched)


@mock.patch("services.web.risk.report.providers.GlobalMetaConfig.get")
@mock.patch("services.web.risk.report.providers.api.bk_base.query_sync")
class TestEventProviderGet(TestCase):
    """EventProvider.get() 集成测试

    Mock BKBase API，验证参数传递和结果解析。
    """

    def setUp(self):
        self.mock_risk = mock.MagicMock()
        self.mock_risk.risk_id = "test_risk_123"
        self.mock_risk.strategy_id = 1001
        self.mock_risk.raw_event_id = "raw_event_abc"
        self.mock_risk.event_time = datetime(2026, 1, 1, 0, 0, 0)
        self.mock_risk.event_end_time = datetime(2026, 1, 2, 0, 0, 0)
        self.mock_risk.strategy = None

        # 使用 risk_id 初始化，然后设置 _risk 跳过数据库查询
        self.provider = EventProvider(risk_id=self.mock_risk.risk_id)
        self.provider._risk = self.mock_risk

    def test_get_all_aggregate_functions(self, mock_query_sync, mock_global_config):
        """测试所有聚合函数的 get 调用"""
        mock_global_config.return_value = "591_test_table"

        test_cases = [
            # (function, field_name, mock_result, expected_value)
            ("count", "event_id", {"event_id": 100}, 100),
            ("count_distinct", "user_id", {"user_id": 50}, 50),
            ("sum", "amount", {"amount": 999}, 999),
            ("avg", "score", {"score": 85.5}, 85.5),
            ("max", "price", {"price": 1000}, 1000),
            ("min", "latency", {"latency": 10}, 10),
            ("first", "username", {"username": "alice"}, "alice"),
            ("latest", "ip", {"ip": "192.168.1.1"}, "192.168.1.1"),
            ("list", "action", {"action": "read,write,delete"}, "read,write,delete"),
            ("list_distinct", "category", {"category": "a,b,c"}, "a,b,c"),
        ]

        for function, field_name, mock_result, expected in test_cases:
            with self.subTest(function=function):
                mock_query_sync.return_value = {"list": [mock_result]}
                result = self.provider.get(function=function, field_name=field_name)
                self.assertEqual(result, expected)
                mock_query_sync.assert_called()

    def test_get_passes_correct_sql_to_api(self, mock_query_sync, mock_global_config):
        """测试 SQL 正确传递给 API"""
        mock_global_config.return_value = "591_test_table"
        mock_query_sync.return_value = {"list": [{"event_id": 100}]}

        self.provider.get(function="count", field_name="event_id")

        # 验证 query_sync 被调用，且 sql 参数包含关键元素
        call_kwargs = mock_query_sync.call_args.kwargs
        sql = call_kwargs.get("sql", "")
        self.assertIn("COUNT", sql)
        self.assertIn("event_id", sql)
        self.assertIn("591_test_table.doris", sql)
        self.assertIn(str(self.mock_risk.strategy_id), sql)

    def test_get_empty_result_returns_none(self, mock_query_sync, mock_global_config):
        """测试空结果返回 None"""
        mock_global_config.return_value = "591_test_table"
        mock_query_sync.return_value = {"list": []}

        result = self.provider.get(function="count", field_name="event_id")
        self.assertIsNone(result)

    def test_get_without_required_params_returns_none(self, mock_query_sync, mock_global_config):
        """测试缺少必需参数返回 None"""
        self.assertIsNone(self.provider.get(field_name="event_id"))
        self.assertIsNone(self.provider.get(function="count"))
        mock_query_sync.assert_not_called()

    def test_get_unsupported_function_returns_none(self, mock_query_sync, mock_global_config):
        """测试不支持的函数返回 None"""
        result = self.provider.get(function="unsupported", field_name="event_id")
        self.assertIsNone(result)
        mock_query_sync.assert_not_called()

    def test_get_api_error_returns_placeholder(self, mock_query_sync, mock_global_config):
        """测试 API 异常返回占位符"""
        mock_global_config.return_value = "591_test_table"
        mock_query_sync.side_effect = APIRequestError()

        result = self.provider.get(function="count", field_name="event_id")
        self.assertEqual(result, EVENT_QUERY_FAILED)

    def test_get_unexpected_error_returns_placeholder(self, mock_query_sync, mock_global_config):
        """测试未预期异常返回占位符"""
        mock_global_config.return_value = "591_test_table"
        mock_query_sync.side_effect = Exception("Unexpected error")

        result = self.provider.get(function="count", field_name="event_id")
        self.assertEqual(result, EVENT_QUERY_FAILED)


class TestEventProviderFieldType(TestCase):
    """EventProvider 字段类型推断测试"""

    def setUp(self):
        self.mock_risk = mock.MagicMock()
        self.mock_risk.risk_id = "test_risk_123"
        self.mock_risk.strategy_id = 1001
        self.mock_risk.raw_event_id = "raw_event_abc"
        self.mock_risk.event_time = datetime(2026, 1, 1, 0, 0, 0)
        self.mock_risk.event_end_time = datetime(2026, 1, 2, 0, 0, 0)

        # 使用 risk_id 初始化，然后设置 _risk 跳过数据库查询
        self.provider = EventProvider(risk_id=self.mock_risk.risk_id)
        self.provider._risk = self.mock_risk

    def test_get_field_type_from_strategy(self):
        """测试从策略配置获取字段类型"""
        self.mock_risk.strategy = mock.MagicMock()
        self.mock_risk.strategy.configs = {
            "select": [
                {"display_name": "amount", "field_type": "long"},
                {"display_name": "rate", "field_type": "double"},
                {"display_name": "name", "field_type": "string"},
            ]
        }

        # 从策略获取
        self.assertEqual(self.provider._get_field_type("amount", "sum"), FieldType.LONG)
        self.assertEqual(self.provider._get_field_type("rate", "avg"), FieldType.DOUBLE)
        self.assertEqual(self.provider._get_field_type("name", "first"), FieldType.STRING)

    def test_get_field_type_fallback_by_aggregate(self):
        """测试根据聚合类型 fallback"""
        self.mock_risk.strategy = None

        # sum/avg 默认 LONG
        self.assertEqual(self.provider._get_field_type("unknown", "sum"), FieldType.LONG)
        self.assertEqual(self.provider._get_field_type("unknown", "avg"), FieldType.LONG)
        # 其他默认 STRING
        self.assertEqual(self.provider._get_field_type("unknown", "first"), FieldType.STRING)
        self.assertEqual(self.provider._get_field_type("unknown", "count"), FieldType.STRING)


class TestEventProviderStorageSuffix(TestCase):
    """EventProvider._apply_storage_suffix() 测试"""

    def test_apply_suffix(self):
        """测试追加 doris 后缀"""
        self.assertEqual(EventProvider._apply_storage_suffix("591_test"), "591_test.doris")

    def test_not_duplicate_suffix(self):
        """测试不重复追加后缀"""
        self.assertEqual(EventProvider._apply_storage_suffix("591_test.doris"), "591_test.doris")

    def test_empty_table_name(self):
        """测试空表名"""
        self.assertEqual(EventProvider._apply_storage_suffix(""), "")
        self.assertEqual(EventProvider._apply_storage_suffix(None), "")
        self.assertEqual(EventProvider._apply_storage_suffix("  "), "")


class TestEventProviderLazyLoad(TestCase):
    """EventProvider 惰性加载测试"""

    def test_init_with_risk_id(self):
        """测试用 risk_id 初始化"""
        provider = EventProvider(risk_id="test_risk_456")

        self.assertEqual(provider.risk_id, "test_risk_456")
        # _risk 此时为 None，访问 risk property 会触发数据库查询
        self.assertIsNone(provider._risk)


class TestCeilToSecond(TestCase):
    """测试 ceil_to_second 函数"""

    def test_ceil_with_microseconds(self):
        """测试有微秒时向上取整"""
        from core.utils.time import ceil_to_second

        dt = datetime(2026, 1, 1, 12, 30, 45, 500000)  # 有 500ms
        result = ceil_to_second(dt)

        self.assertEqual(result.second, 46)
        self.assertEqual(result.microsecond, 0)

    def test_no_ceil_without_microseconds(self):
        """测试无微秒时不变"""
        from core.utils.time import ceil_to_second

        dt = datetime(2026, 1, 1, 12, 30, 45, 0)
        result = ceil_to_second(dt)

        self.assertEqual(result.second, 45)
        self.assertEqual(result.microsecond, 0)

    def test_none_input_returns_none(self):
        """测试 None 输入返回 None"""
        from core.utils.time import ceil_to_second

        self.assertIsNone(ceil_to_second(None))
