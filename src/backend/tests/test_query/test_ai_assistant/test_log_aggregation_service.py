# -*- coding: utf-8 -*-
"""aggregate_logs Service 的权限、批量查询和响应语义测试。"""

from unittest import mock

from bk_resource.exceptions import APIRequestError
from requests.exceptions import Timeout as RequestsTimeout

from apps.meta.constants import SensitiveResourceTypeEnum, SensitiveUserData
from apps.meta.models import SensitiveObject
from services.web.query.ai_assistant.exceptions import (
    LogQueryFailed,
    LogQueryTimeout,
    SensitiveFieldPermissionDenied,
)
from services.web.query.ai_assistant.log_tools.aggregation import LogAggregationService
from services.web.query.ai_assistant.log_tools.context import LogQueryContext
from services.web.query.ai_assistant.log_tools.schemas import AggregateLogsRequest
from services.web.query.ai_assistant.schemas import SearchCondition
from tests.base import TestCase

AGGREGATION_MODULE = "services.web.query.ai_assistant.log_tools.aggregation"


def aggregation_request(condition, **kwargs):
    payload = {
        "condition": condition,
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
        "limit": 2,
    }
    payload.update(kwargs)
    return AggregateLogsRequest(**payload)


class TestLogAggregationService(TestCase):
    """聚合必须先预检敏感字段，且绝不试图对分组行执行逐行脱敏。"""

    username = "tester"
    namespace = "default"
    target_system_id = "bk_log"

    def setUp(self):
        super().setUp()
        self.condition = self.make_condition(scope_id=self.target_system_id)
        self.context = LogQueryContext(
            username=self.username,
            namespace=self.namespace,
            condition=self.condition,
            table="test_rt.doris",
            conditions=(
                {
                    "field": {"raw_name": "system_id", "keys": []},
                    "operator": "include",
                    "filters": [self.target_system_id],
                },
            ),
        )
        self.mock_context = self.enterContext(
            mock.patch(f"{AGGREGATION_MODULE}.LogQueryContextService.build", return_value=self.context)
        )
        self.mock_query = self.enterContext(mock.patch(f"{AGGREGATION_MODULE}.safe_query_sync"))
        self.mock_permissions = self.enterContext(mock.patch(f"{AGGREGATION_MODULE}.PermissionService"))
        self.mock_query.bulk_request.return_value = (
            {
                "list": [
                    {"action": "view", "count": 3, "avg_duration": 1.5, "untrusted": "ignored"},
                    {"action": "edit", "count": 2, "avg_duration": 2.0},
                    {"action": "delete", "count": 1, "avg_duration": 3.0},
                ]
            },
            {
                "list": [
                    {
                        "avg_duration_non_empty_count": 6,
                        "avg_duration_converted_count": 5,
                        "avg_duration_conversion_failed_count": 1,
                    }
                ]
            },
        )

    def make_condition(self, **kwargs):
        return SearchCondition(
            scope_type="system",
            scope_id=kwargs.pop("scope_id", self.target_system_id),
            start_time="2026-08-13T00:00:00+08:00",
            end_time="2026-08-14T00:00:00+08:00",
            conditions=[],
        )

    def _aggregate(self, **kwargs):
        return LogAggregationService.aggregate(
            username=self.username,
            namespace=self.namespace,
            request=aggregation_request(self.condition, **kwargs),
        )

    def test_limit_plus_one_trims_rows_and_returns_real_bulk_timing(self):
        with mock.patch(f"{AGGREGATION_MODULE}.time.perf_counter", side_effect=[20.0, 20.125]):
            result = self._aggregate()

        self.assertEqual(
            result.rows,
            (
                {"action": "view", "count": 3, "avg_duration": 1.5},
                {"action": "edit", "count": 2, "avg_duration": 2.0},
            ),
        )
        self.assertEqual(result.query_summary.returned_count, 2)
        self.assertTrue(result.query_summary.has_more)
        self.assertEqual(result.query_summary.took_ms, 125)
        self.assertTrue(result.query_summary.executed_at)
        self.assertEqual(result.data_quality[0].metric_id, "avg_duration")
        self.assertEqual(result.data_quality[0].non_empty_count, 6)
        self.assertEqual(result.data_quality[0].converted_count, 5)
        self.assertEqual(result.data_quality[0].conversion_failed_count, 1)
        self.assertEqual([column.id for column in result.columns], ["action", "count", "avg_duration"])
        self.assertNotIn("test_rt.doris", result.model_dump_json())
        self.assertNotIn("SELECT", result.model_dump_json())

        (requests,), _ = self.mock_query.bulk_request.call_args
        self.assertEqual(len(requests), 2)
        self.assertIn("LIMIT 3", requests[0]["sql"])

    def test_no_conversion_metric_uses_one_bulk_item_and_no_quality_result(self):
        self.mock_query.bulk_request.return_value = ({"list": [{"action": "view", "count": 1}]},)

        result = self._aggregate(metrics=[{"id": "count", "type": "COUNT"}])

        self.assertEqual(result.rows, ({"action": "view", "count": 1},))
        self.assertEqual(result.data_quality, ())
        (requests,), _ = self.mock_query.bulk_request.call_args
        self.assertEqual(len(requests), 1)

    def test_service_never_uses_row_desensitization_for_grouped_output(self):
        with mock.patch(
            "services.web.query.resources.base.SearchDataParser.parse_data",
            side_effect=AssertionError("aggregate rows must not be desensitized post-query"),
        ):
            result = self._aggregate()

        self.assertEqual(result.rows[0]["action"], "view")

    def test_private_and_missing_sensitive_permission_stop_before_doris(self):
        private = SensitiveObject.objects.create(
            name="private duration",
            system_id=self.target_system_id,
            resource_type=SensitiveResourceTypeEnum.RESOURCE.value,
            resource_id="host",
            fields=[{"field_name": "extend_data.duration"}],
            is_private=True,
        )
        with self.assertRaises(SensitiveFieldPermissionDenied):
            self._aggregate()
        self.assertTrue(private.pk)
        self.mock_query.bulk_request.assert_not_called()

        private.delete()
        permitted = SensitiveObject.objects.create(
            name="ungranted duration",
            system_id=self.target_system_id,
            resource_type=SensitiveResourceTypeEnum.RESOURCE.value,
            resource_id="host",
            fields=[{"field_name": "extend_data.duration"}],
        )
        self.mock_permissions.return_value.get_sensitive_object_permissions.return_value = {}
        with self.assertRaises(SensitiveFieldPermissionDenied):
            self._aggregate()
        self.mock_permissions.return_value.get_sensitive_object_permissions.assert_called_once_with([permitted.id])
        self.mock_query.bulk_request.assert_not_called()

    def test_global_sensitive_rule_is_checked_and_count_star_does_not_trigger_field_precheck(self):
        global_sensitive = SensitiveObject.objects.create(
            name="global action",
            system_id=SensitiveUserData.SYSTEM_ID,
            resource_type=SensitiveResourceTypeEnum.RESOURCE.value,
            resource_id=SensitiveUserData.RESOURCE_ID,
            fields=[{"field_name": "action_id"}],
        )
        self.mock_permissions.return_value.get_sensitive_object_permissions.return_value = {global_sensitive.id: False}
        with self.assertRaises(SensitiveFieldPermissionDenied):
            self._aggregate(metrics=[{"id": "count", "type": "COUNT"}])
        self.mock_query.bulk_request.assert_not_called()

        self.mock_permissions.reset_mock()
        self.mock_query.bulk_request.return_value = ({"list": [{"count": 4}]},)
        result = self._aggregate(dimensions=[], metrics=[{"id": "count", "type": "COUNT"}])
        self.assertEqual(result.rows, ({"count": 4},))
        self.mock_permissions.return_value.get_sensitive_object_permissions.assert_not_called()

    def test_zero_rows_and_backend_failures_have_controlled_semantics(self):
        self.mock_query.bulk_request.return_value = (
            {"list": []},
            {
                "list": [
                    {
                        "avg_duration_non_empty_count": 0,
                        "avg_duration_converted_count": 0,
                        "avg_duration_conversion_failed_count": 0,
                    }
                ]
            },
        )
        result = self._aggregate()
        self.assertEqual(result.rows, ())
        self.assertFalse(result.query_summary.has_more)
        self.assertEqual(result.query_summary.returned_count, 0)

        timeout = APIRequestError(result="gateway failed")
        timeout.__cause__ = RequestsTimeout("upstream timeout")
        self.mock_query.bulk_request.side_effect = timeout
        with self.assertRaises(LogQueryTimeout) as raised:
            self._aggregate()
        self.assertIs(raised.exception.__cause__, timeout)

        self.mock_query.bulk_request.side_effect = RuntimeError("SELECT secret FROM audit")
        with self.assertRaises(LogQueryFailed) as raised:
            self._aggregate()
        self.assertNotIn("SELECT secret", str(raised.exception))

    def test_bulk_response_contract_rejects_invalid_subresponses_and_missing_declared_columns(self):
        invalid_responses = (
            (),
            ([], {}),
            ({}, {}),
            (
                {"list": [{"action": "view", "count": 1}]},
                {
                    "list": [
                        {
                            "avg_duration_non_empty_count": 1,
                            "avg_duration_converted_count": 1,
                            "avg_duration_conversion_failed_count": 0,
                        }
                    ]
                },
            ),
            (
                {"list": [{"action": "view", "count": 1, "avg_duration": 1.0}]},
                {
                    "list": [
                        {
                            "avg_duration_non_empty_count": 1,
                            "avg_duration_converted_count": 1,
                        }
                    ]
                },
            ),
            (
                {"list": [{"action": "view", "count": 1, "avg_duration": 1.0}]},
                {
                    "list": [
                        {
                            "avg_duration_non_empty_count": 2,
                            "avg_duration_converted_count": 1,
                            "avg_duration_conversion_failed_count": 0,
                        }
                    ]
                },
            ),
        )
        for responses in invalid_responses:
            with self.subTest(responses=responses):
                self.mock_query.bulk_request.return_value = responses
                with self.assertRaises(LogQueryFailed):
                    self._aggregate()

    def test_columns_use_server_declared_types_not_request_field_type(self):
        self.mock_query.bulk_request.return_value = (
            {
                "list": [
                    {
                        "bucket": "2026-08-13 00:00:00",
                        "extension": "1",
                        "count": 1,
                        "distinct": 1,
                        "avg": 1.0,
                        "p95": 1.0,
                        "min_access": 1,
                    }
                ]
            },
            {
                "list": [
                    {
                        "avg_non_empty_count": 1,
                        "avg_converted_count": 1,
                        "avg_conversion_failed_count": 0,
                        "p95_non_empty_count": 1,
                        "p95_converted_count": 1,
                        "p95_conversion_failed_count": 0,
                    }
                ]
            },
        )
        result = self._aggregate(
            dimensions=[
                {
                    "id": "bucket",
                    "type": "TIME_BUCKET",
                    "field": {"raw_name": "start_time", "field_type": "injected"},
                    "interval": "HOUR",
                },
                {
                    "id": "extension",
                    "type": "FIELD",
                    "field": {"raw_name": "extend_data", "keys": ["duration"], "field_type": "injected"},
                },
            ],
            metrics=[
                {"id": "count", "type": "COUNT"},
                {
                    "id": "distinct",
                    "type": "DISTINCT_COUNT",
                    "field": {"raw_name": "username", "field_type": "injected"},
                },
                {
                    "id": "avg",
                    "type": "AVG",
                    "field": {"raw_name": "extend_data", "keys": ["duration"]},
                    "value_type": "LONG",
                },
                {
                    "id": "p95",
                    "type": "PERCENTILE_APPROX",
                    "field": {"raw_name": "extend_data", "keys": ["duration"]},
                    "value_type": "LONG",
                    "percentile": 0.95,
                },
                {"id": "min_access", "type": "MIN", "field": {"raw_name": "access_type", "field_type": "injected"}},
            ],
        )

        self.assertEqual(
            {column.id: column.data_type for column in result.columns},
            {
                "bucket": "datetime",
                "extension": "string",
                "count": "long",
                "distinct": "long",
                "avg": "double",
                "p95": "double",
                "min_access": "int",
            },
        )

        self.mock_query.bulk_request.return_value = (
            {"list": [{"sum_access": 1, "sum_duration": 1.0}]},
            {
                "list": [
                    {
                        "sum_duration_non_empty_count": 1,
                        "sum_duration_converted_count": 1,
                        "sum_duration_conversion_failed_count": 0,
                    }
                ]
            },
        )
        sums = self._aggregate(
            dimensions=[],
            order_by=[],
            metrics=[
                {"id": "sum_access", "type": "SUM", "field": {"raw_name": "access_type", "field_type": "injected"}},
                {
                    "id": "sum_duration",
                    "type": "SUM",
                    "field": {"raw_name": "extend_data", "keys": ["duration"]},
                    "value_type": "DOUBLE",
                },
            ],
        )
        self.assertEqual(
            {column.id: column.data_type for column in sums.columns}, {"sum_access": "long", "sum_duration": "double"}
        )
