# -*- coding: utf-8 -*-
"""aggregate_logs 聚合协议的成本、安全与交叉字段约束。"""

from django.test import override_settings
from pydantic import ValidationError as PydanticValidationError

from services.web.query.ai_assistant.log_tools.schemas import (
    AggregateLogsRequest,
    AggregationDimension,
    AggregationMetric,
)
from tests.test_query.test_ai_assistant.base import AIAssistantTestCase


def field_dimension(identifier="action", raw_name="action_id"):
    return {"id": identifier, "type": "FIELD", "field": {"raw_name": raw_name}}


def time_dimension(identifier="bucket", interval="AUTO"):
    return {
        "id": identifier,
        "type": "TIME_BUCKET",
        "field": {"raw_name": "start_time"},
        "interval": interval,
    }


def count_metric(identifier="count"):
    return {"id": identifier, "type": "COUNT"}


def avg_extension_metric(identifier="avg_duration", key="duration", value_type="DOUBLE"):
    return {
        "id": identifier,
        "type": "AVG",
        "field": {"raw_name": "extend_data", "keys": [key]},
        "value_type": value_type,
    }


class TestAggregateLogsRequest(AIAssistantTestCase):
    """聚合协议必须在 Context 与 Doris 前阻断不受控输入。"""

    def test_overall_aggregation_and_multiple_metrics_are_valid(self):
        request = AggregateLogsRequest(
            condition=self.make_condition(),
            dimensions=[],
            metrics=[count_metric(), avg_extension_metric()],
            order_by=[{"target_id": "count", "direction": "DESC"}],
        )

        self.assertEqual(request.limit, 20)
        self.assertEqual(request.dimensions, ())
        self.assertEqual([metric.id for metric in request.metrics], ["count", "avg_duration"])

    def test_hard_dimension_metric_and_time_bucket_limits_are_enforced(self):
        condition = self.make_condition()
        with self.assertRaises(PydanticValidationError):
            AggregateLogsRequest(
                condition=condition,
                dimensions=[
                    field_dimension("action"),
                    field_dimension("resource", "resource_type_id"),
                    field_dimension("user", "username"),
                ],
                metrics=[count_metric()],
            )
        with self.assertRaises(PydanticValidationError):
            AggregateLogsRequest(condition=condition, metrics=[count_metric(str(index)) for index in range(6)])
        with self.assertRaises(PydanticValidationError):
            AggregateLogsRequest(
                condition=condition,
                dimensions=[time_dimension("minute", "MINUTE"), time_dimension("hour", "HOUR")],
                metrics=[count_metric()],
            )

    def test_identifier_order_and_alias_injection_boundaries_are_rejected(self):
        condition = self.make_condition()
        invalid_identifiers = ("1count", "count-name", "count;DROP", "x" * 65)
        for identifier in invalid_identifiers:
            with self.subTest(identifier=identifier):
                with self.assertRaises(PydanticValidationError):
                    AggregateLogsRequest(condition=condition, metrics=[count_metric(identifier)])

        with self.assertRaises(PydanticValidationError):
            AggregateLogsRequest(
                condition=condition,
                dimensions=[field_dimension("same")],
                metrics=[count_metric("same")],
            )
        with self.assertRaises(PydanticValidationError):
            AggregateLogsRequest(
                condition=condition,
                metrics=[count_metric()],
                order_by=[{"target_id": "unknown", "direction": "DESC"}],
            )
        with self.assertRaises(PydanticValidationError):
            AggregateLogsRequest(
                condition=condition,
                metrics=[count_metric()],
                order_by=[
                    {"target_id": "count", "direction": "ASC"},
                    {"target_id": "count", "direction": "DESC"},
                ],
            )

    def test_metric_contract_requires_exact_supported_fields_and_options(self):
        condition = self.make_condition()
        with self.assertRaises(PydanticValidationError):
            AggregateLogsRequest(
                condition=condition,
                metrics=[{"id": "count", "type": "COUNT", "field": {"raw_name": "action_id"}}],
            )
        with self.assertRaises(PydanticValidationError):
            AggregateLogsRequest(condition=condition, metrics=[{"id": "avg", "type": "AVG"}])
        with self.assertRaises(PydanticValidationError):
            AggregateLogsRequest(
                condition=condition,
                metrics=[
                    {
                        "id": "distinct",
                        "type": "DISTINCT_COUNT",
                        "field": {"raw_name": "username"},
                        "value_type": "LONG",
                    }
                ],
            )
        for percentile in (0, 1, -0.1, 1.1):
            with self.subTest(percentile=percentile):
                with self.assertRaises(PydanticValidationError):
                    AggregateLogsRequest(
                        condition=condition,
                        metrics=[
                            {
                                "id": "p95",
                                "type": "PERCENTILE_APPROX",
                                "field": {"raw_name": "extend_data", "keys": ["duration"]},
                                "value_type": "DOUBLE",
                                "percentile": percentile,
                            }
                        ],
                    )
        with self.assertRaises(PydanticValidationError):
            AggregateLogsRequest(condition=condition, metrics=[avg_extension_metric(value_type=None)])
        with self.assertRaises(PydanticValidationError):
            AggregateLogsRequest(
                condition=condition,
                metrics=[{"id": "avg_username", "type": "AVG", "field": {"raw_name": "username"}}],
            )
        standard_string_metric = AggregateLogsRequest(
            condition=condition,
            metrics=[
                {
                    "id": "avg_username",
                    "type": "AVG",
                    "field": {"raw_name": "username"},
                    "value_type": "DOUBLE",
                }
            ],
        )
        self.assertTrue(standard_string_metric.metrics[0].needs_conversion)
        with self.assertRaises(PydanticValidationError):
            AggregateLogsRequest(
                condition=condition,
                metrics=[
                    {
                        "id": "sum_access",
                        "type": "SUM",
                        "field": {"raw_name": "access_type"},
                        "value_type": "LONG",
                    }
                ],
            )
        with self.assertRaises(PydanticValidationError):
            AggregateLogsRequest(
                condition=condition,
                dimensions=[field_dimension(raw_name="log")],
                metrics=[count_metric()],
            )
        with self.assertRaises(PydanticValidationError):
            AggregateLogsRequest(
                condition=condition,
                metrics=[avg_extension_metric(key="x" * 129)],
            )

    @override_settings(AI_LOG_AGGREGATION_MAX_LIMIT=1)
    def test_runtime_limit_can_only_tighten_hard_maximum(self):
        with self.assertRaises(PydanticValidationError):
            AggregateLogsRequest(condition=self.make_condition(), metrics=[count_metric()], limit=2)

    @override_settings(AI_LOG_AGGREGATION_MAX_LIMIT=999)
    def test_runtime_limit_cannot_expand_hard_maximum(self):
        with self.assertRaises(PydanticValidationError):
            AggregateLogsRequest(condition=self.make_condition(), metrics=[count_metric()], limit=101)


class TestAggregationModels(AIAssistantTestCase):
    """单项模型同样不接受越过顶层校验的额外或歧义字段。"""

    def test_dimension_and_metric_forbid_untrusted_extra_attributes(self):
        with self.assertRaises(PydanticValidationError):
            AggregationDimension.model_validate({**field_dimension(), "sql": "SELECT *"})
        with self.assertRaises(PydanticValidationError):
            AggregationMetric.model_validate({**count_metric(), "function": "SLEEP"})
