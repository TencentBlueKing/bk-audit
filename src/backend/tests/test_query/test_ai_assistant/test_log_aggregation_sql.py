# -*- coding: utf-8 -*-
"""aggregate_logs 受控 Doris SQL 生成测试。"""

import re
from datetime import timedelta

from django.utils import timezone
from pydantic import ValidationError as PydanticValidationError

from services.web.query.ai_assistant.log_tools.context import LogQueryContext
from services.web.query.ai_assistant.log_tools.schemas import (
    AggregateLogsRequest,
    AggregationMetric,
    AggregationMetricType,
)
from services.web.query.ai_assistant.log_tools.sql import (
    DOUBLE_LITERAL_REGEXP,
    LONG_LITERAL_REGEXP,
    LogAggregationSQLBuilder,
)
from tests.test_query.test_ai_assistant.base import AIAssistantTestCase


def _condition(testcase, **kwargs):
    return testcase.make_condition(**kwargs)


def _request(testcase, **kwargs):
    payload = {
        "condition": _condition(testcase),
        "dimensions": [{"id": "action", "type": "FIELD", "field": {"raw_name": "action_id"}}],
        "metrics": [
            {"id": "count", "type": "COUNT"},
            {
                "id": "avg_duration",
                "type": "AVG",
                "field": {"raw_name": "extend_data", "keys": ["duration"]},
                "value_type": "DOUBLE",
            },
        ],
        "order_by": [{"target_id": "count", "direction": "DESC"}],
        "limit": 5,
    }
    payload.update(kwargs)
    return AggregateLogsRequest(**payload)


class TestLogAggregationSQLBuilder(AIAssistantTestCase):
    """字段、函数、别名和排序都必须由协议枚举映射，而非请求字符串拼接。"""

    def setUp(self):
        super().setUp()
        self.context = LogQueryContext(
            username=self.username,
            namespace=self.namespace,
            condition=self.make_condition(),
            table="test_rt.doris",
            conditions=({"field": {"raw_name": "system_id", "keys": []}, "operator": "include", "filters": ["s1"]},),
        )

    def test_one_dimension_can_compute_multiple_metrics_with_limit_plus_one(self):
        builder = LogAggregationSQLBuilder.from_request(self.context, _request(self))

        sql = builder.build_data_sql()
        self.assertIn("GROUP BY", sql)
        self.assertIn("COUNT(*) `count`", sql)
        self.assertIn("AVG(CASE WHEN", sql)
        self.assertIn("THEN CAST(", sql)
        self.assertIn("`action`", sql)
        self.assertIn("`avg_duration`", sql)
        self.assertIn("ORDER BY `count` DESC", sql)
        self.assertIn("LIMIT 6", sql)
        self.assertIn("`system_id` IN ('s1')", sql)

    def test_overall_aggregate_has_no_group_by_and_uses_count_star(self):
        request = _request(self, dimensions=[])
        sql = LogAggregationSQLBuilder.from_request(self.context, request).build_data_sql()

        self.assertIn("COUNT(*) `count`", sql)
        self.assertNotIn("GROUP BY", sql)

    def test_supported_metrics_use_fixed_function_map(self):
        request = _request(
            self,
            order_by=[],
            metrics=[
                {"id": "count", "type": "COUNT"},
                {"id": "distinct", "type": "DISTINCT_COUNT", "field": {"raw_name": "username"}},
                {"id": "minimum", "type": "MIN", "field": {"raw_name": "access_type"}},
                {"id": "maximum", "type": "MAX", "field": {"raw_name": "access_type"}},
                {"id": "p95", "type": "PERCENTILE_APPROX", "field": {"raw_name": "access_type"}, "percentile": 0.95},
            ],
        )

        sql = LogAggregationSQLBuilder.from_request(self.context, request).build_data_sql()
        self.assertIn("COUNT(DISTINCT", sql)
        self.assertIn("MIN(", sql)
        self.assertIn("MAX(", sql)
        self.assertIn("PERCENTILE_APPROX(", sql)
        self.assertNotIn("SLEEP", sql)

    def test_two_dimensions_use_group_by_and_default_stable_dimension_order(self):
        request = _request(
            self,
            dimensions=[
                {"id": "action", "type": "FIELD", "field": {"raw_name": "action_id"}},
                {"id": "resource", "type": "FIELD", "field": {"raw_name": "resource_type_id"}},
            ],
            metrics=[
                {"id": "count", "type": "COUNT"},
                {"id": "sum_access", "type": "SUM", "field": {"raw_name": "access_type"}},
            ],
            order_by=[],
        )

        sql = LogAggregationSQLBuilder.from_request(self.context, request).build_data_sql()
        self.assertIn("GROUP BY `action_id`,`resource_type_id`", sql)
        self.assertIn("SUM(`access_type`) `sum_access`", sql)
        self.assertIn("ORDER BY `action` ASC,`resource` ASC", sql)

    def test_time_bucket_auto_selection_is_stable_and_reported_by_builder(self):
        intervals = (
            (timedelta(hours=2), "MINUTE"),
            (timedelta(days=3), "HOUR"),
            (timedelta(days=31), "DAY"),
        )
        for span, expected_interval in intervals:
            with self.subTest(expected_interval=expected_interval):
                start = timezone.now().replace(microsecond=0)
                request = _request(
                    self,
                    condition=self.make_condition(start_time=start.isoformat(), end_time=(start + span).isoformat()),
                    dimensions=[
                        {
                            "id": "bucket",
                            "type": "TIME_BUCKET",
                            "field": {"raw_name": "start_time"},
                            "interval": "AUTO",
                        }
                    ],
                )
                builder = LogAggregationSQLBuilder.from_request(self.context, request)

                self.assertEqual(builder.effective_time_intervals, {"bucket": expected_interval})
                self.assertIn("DATE_TRUNC(FROM_UNIXTIME", builder.build_data_sql())
                self.assertIn(f"'{expected_interval}'", builder.build_data_sql())

    def test_conversion_expression_and_quality_sql_share_the_same_bounded_criterion(self):
        builder = LogAggregationSQLBuilder.from_request(self.context, _request(self))
        data_sql = builder.build_data_sql()
        quality_sql = builder.build_quality_sql()

        self.assertIn("REGEXP", data_sql)
        self.assertIn(DOUBLE_LITERAL_REGEXP, data_sql)
        self.assertIn(DOUBLE_LITERAL_REGEXP, quality_sql)
        self.assertIn("CAST(", data_sql)
        self.assertIn("AS DOUBLE", data_sql)
        self.assertIn("IS NOT NULL", quality_sql)
        self.assertIn("<>''", quality_sql)
        self.assertIn("COUNT(CASE WHEN", quality_sql)
        self.assertIn("non_empty_count", quality_sql)
        self.assertIn("converted_count", quality_sql)
        self.assertIn("conversion_failed_count", quality_sql)
        self.assertIn("avg_duration", quality_sql)

    def test_long_literal_grammar_rejects_decimal_exponent_and_overflow_prone_values(self):
        for value in ("0", "-1", "123456789012345678"):
            with self.subTest(value=value):
                self.assertIsNotNone(re.fullmatch(LONG_LITERAL_REGEXP, value))
        for value in ("", "-", "1.5", "1e3", "+1", "1234567890123456789", "not-a-number"):
            with self.subTest(value=value):
                self.assertIsNone(re.fullmatch(LONG_LITERAL_REGEXP, value))

    def test_double_literal_grammar_accepts_bounded_decimal_only(self):
        for value in ("0", "-1", "1.5", ".5", "123456789012345.123456789012345"):
            with self.subTest(value=value):
                self.assertIsNotNone(re.fullmatch(DOUBLE_LITERAL_REGEXP, value))
        for value in ("", "-", "1.", "1e3", "+1", "1234567890123456", "1.1234567890123456"):
            with self.subTest(value=value):
                self.assertIsNone(re.fullmatch(DOUBLE_LITERAL_REGEXP, value))

    def test_long_conversion_uses_long_criterion_for_data_and_quality(self):
        request = _request(
            self,
            order_by=[],
            metrics=[
                {
                    "id": "sum_duration",
                    "type": "SUM",
                    "field": {"raw_name": "extend_data", "keys": ["duration"]},
                    "value_type": "LONG",
                }
            ],
        )
        builder = LogAggregationSQLBuilder.from_request(self.context, request)

        self.assertIn(LONG_LITERAL_REGEXP, builder.build_data_sql())
        self.assertIn(LONG_LITERAL_REGEXP, builder.build_quality_sql())

    def test_builder_revalidates_constructed_objects_before_sql_generation(self):
        unsafe_request = AggregateLogsRequest.model_construct(
            condition=self.make_condition(),
            dimensions=(),
            metrics=(AggregationMetric.model_construct(id="count; DROP", type=AggregationMetricType.COUNT),),
            order_by=(),
            limit=5,
        )

        with self.assertRaises(PydanticValidationError):
            LogAggregationSQLBuilder.from_request(self.context, unsafe_request)
