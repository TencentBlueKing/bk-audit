# -*- coding: utf-8 -*-
"""aggregate_logs 聚合协议的成本、安全与交叉字段约束。"""

from django.test import override_settings
from pydantic import ValidationError as PydanticValidationError

from services.web.query.ai_assistant.log_tools import schemas
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
        )

        self.assertIsNone(request.top_n)
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
                dimensions=[field_dimension(raw_name="COUNT(*)")],
                metrics=[count_metric()],
            )
        with self.assertRaises(PydanticValidationError):
            AggregateLogsRequest(
                condition=condition,
                metrics=[avg_extension_metric(key="x" * 129)],
            )

    def test_categories_default_top_n_and_reject_old_limit(self):
        request = AggregateLogsRequest(
            condition=self.make_condition(), dimensions=[field_dimension()], metrics=[count_metric()]
        )
        self.assertEqual(request.top_n, 100)
        self.assertEqual(AggregateLogsRequest.model_validate(request.model_dump()).top_n, 100)
        with self.assertRaises(PydanticValidationError):
            AggregateLogsRequest.model_validate({**request.model_dump(), "limit": 20})

    def test_no_category_omission_survives_serialization_but_explicit_options_fail(self):
        for dimensions in ([], [time_dimension()]):
            payload = {"condition": self.make_condition(), "dimensions": dimensions, "metrics": [count_metric()]}
            request = AggregateLogsRequest.model_validate(payload)
            for mode in ("python", "json"):
                dumped = request.model_dump(mode=mode)
                self.assertNotIn("top_n", dumped)
                self.assertNotIn("order_by", dumped)
                self.assertIsNone(AggregateLogsRequest.model_validate(dumped).top_n)
            for options in (
                {"top_n": None},
                {"top_n": 1},
                {"order_by": []},
                {"order_by": [{"target_id": "count", "direction": "DESC"}]},
            ):
                with self.subTest(dimensions=dimensions, options=options), self.assertRaises(PydanticValidationError):
                    AggregateLogsRequest.model_validate({**payload, **options})

    def test_business_fields_and_json_paths_are_open_but_expressions_are_rejected(self):
        for field in (
            {"raw_name": "access_source_ip"},
            {"raw_name": "event_id"},
            {"raw_name": "request_id"},
            {"raw_name": "log"},
            {"raw_name": "extend_data", "keys": ["业务", "时长-ms"]},
        ):
            request = AggregateLogsRequest(
                condition=self.make_condition(),
                dimensions=[{"id": "category", "type": "FIELD", "field": field}],
                metrics=[{"id": "distinct", "type": "DISTINCT_COUNT", "field": field}],
            )
            self.assertEqual(request.dimensions[0].field.raw_name, field["raw_name"])
        for raw_name in ("COUNT(*)", "username; DROP TABLE logs", "source_ip"):
            with self.subTest(raw_name=raw_name), self.assertRaises(PydanticValidationError):
                AggregateLogsRequest(
                    condition=self.make_condition(),
                    dimensions=[field_dimension(raw_name=raw_name)],
                    metrics=[count_metric()],
                )

    def test_reserved_ids_and_time_ranking_are_rejected(self):
        for identifier in ("group_id", "group_kind", "log_count", "log_ratio", "bucket_start"):
            for payload in (
                {"dimensions": [field_dimension(identifier)], "metrics": [count_metric()]},
                {"metrics": [count_metric(identifier)]},
            ):
                with self.subTest(identifier=identifier), self.assertRaises(PydanticValidationError):
                    AggregateLogsRequest(condition=self.make_condition(), **payload)
        with self.assertRaises(PydanticValidationError):
            AggregateLogsRequest(
                condition=self.make_condition(),
                dimensions=[field_dimension(), time_dimension()],
                metrics=[count_metric()],
                order_by=[{"target_id": "bucket", "direction": "ASC"}],
            )
        request = AggregateLogsRequest(
            condition=self.make_condition(),
            dimensions=[field_dimension(), time_dimension()],
            metrics=[count_metric()],
            order_by=[{"target_id": "count", "direction": "DESC"}],
        )
        self.assertEqual(request.order_by[0].target_id, "count")

    @override_settings(AI_LOG_AGGREGATION_MAX_TOP_N=100)
    def test_runtime_top_n_can_tighten_maximum(self):
        with self.assertRaises(PydanticValidationError):
            AggregateLogsRequest(
                condition=self.make_condition(), dimensions=[field_dimension()], metrics=[count_metric()], top_n=101
            )

    @override_settings(AI_LOG_AGGREGATION_MAX_TOP_N=999)
    def test_runtime_top_n_cannot_expand_hard_maximum(self):
        for value in (0, 501, True, 1.5, "10", None):
            with self.subTest(value=value), self.assertRaises(PydanticValidationError):
                AggregateLogsRequest(
                    condition=self.make_condition(),
                    dimensions=[field_dimension()],
                    metrics=[count_metric()],
                    top_n=value,
                )
        self.assertEqual(
            AggregateLogsRequest(
                condition=self.make_condition(), dimensions=[field_dimension()], metrics=[count_metric()], top_n=500
            ).top_n,
            500,
        )


class TestAggregationModels(AIAssistantTestCase):
    """单项模型同样不接受越过顶层校验的额外或歧义字段。"""

    def test_dimension_and_metric_forbid_untrusted_extra_attributes(self):
        with self.assertRaises(PydanticValidationError):
            AggregationDimension.model_validate({**field_dimension(), "sql": "SELECT *"})
        with self.assertRaises(PydanticValidationError):
            AggregationMetric.model_validate({**count_metric(), "function": "SLEEP"})

    def test_interval_default_and_field_omission_survive_roundtrip(self):
        payload = time_dimension()
        payload.pop("interval")
        self.assertEqual(AggregationDimension.model_validate(payload).interval, "AUTO")
        field = AggregationDimension.model_validate(field_dimension())
        self.assertNotIn("interval", field.model_dump())
        self.assertEqual(AggregationDimension.model_validate(field.model_dump()), field)
        for value in (None, "AUTO", "DAY"):
            with self.subTest(value=value), self.assertRaises(PydanticValidationError):
                AggregationDimension.model_validate({**field_dimension(), "interval": value})

    def test_typed_values_preserve_scalar_identity_and_reject_ambiguous_values(self):
        for value_type, value in (("boolean", True), ("integer", 1), ("number", 1.5), ("string", "")):
            result = schemas.AggregationGroupValue(dimension_id="category", value_type=value_type, value=value)
            self.assertEqual(
                result.model_dump(mode="json"), {"dimension_id": "category", "value_type": value_type, "value": value}
            )
        for value_type, value in (
            ("integer", True),
            ("string", 1),
            ("number", float("inf")),
            ("null", None),
            ("array", []),
            ("object", {}),
        ):
            with self.subTest(value_type=value_type), self.assertRaises(PydanticValidationError):
                schemas.AggregationGroupValue(dimension_id="category", value_type=value_type, value=value)

    def test_synthetic_groups_do_not_forge_business_values(self):
        value = {"dimension_id": "category", "value_type": "string", "value": "OTHER"}
        for kind in ("OTHER", "MISSING", "ALL"):
            result = schemas.AggregationGroup(group_id="g", kind=kind, values=(), count=0, ratio=None)
            self.assertEqual(result.model_dump(mode="json")["values"], [])
            with self.assertRaises(PydanticValidationError):
                schemas.AggregationGroup(group_id="g", kind=kind, values=[value], count=1, ratio=1)
        with self.assertRaises(PydanticValidationError):
            schemas.AggregationGroup(group_id="g", kind="VALUE", values=(), count=1, ratio=1)

    def test_quality_counts_include_present_empty_strings_and_reject_old_contract(self):
        quality = schemas.AggregationDataQuality(
            metric_id="avg", present_count=3, converted_count=2, conversion_failed_count=1
        )
        self.assertEqual(
            quality.model_dump(),
            {"metric_id": "avg", "present_count": 3, "converted_count": 2, "conversion_failed_count": 1},
        )
        for payload in (
            {"present_count": 2, "converted_count": 2, "conversion_failed_count": 1},
            {"non_empty_count": 3, "converted_count": 2, "conversion_failed_count": 1},
        ):
            with self.assertRaises(PydanticValidationError):
                schemas.AggregationDataQuality(metric_id="avg", **payload)

    def test_result_column_types_preserve_boolean_numeric_and_mixed_scalar_meaning(self):
        for value in ("boolean", "number", "scalar"):
            column = schemas.AggregationColumn(id="category", name="Category", role="DIMENSION", data_type=value)
            self.assertEqual(column.model_dump(mode="json")["data_type"], value)
