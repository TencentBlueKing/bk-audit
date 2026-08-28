# -*- coding: utf-8 -*-
"""日志字段元信息探索测试。"""

import json
from unittest import mock

from bk_resource.exceptions import APIRequestError
from django.test import override_settings
from pydantic import ValidationError as PydanticValidationError
from requests.exceptions import Timeout as RequestsTimeout

from services.web.query.ai_assistant.exceptions import LogQueryFailed, LogQueryTimeout
from services.web.query.ai_assistant.log_tools.context import LogQueryContext
from services.web.query.ai_assistant.log_tools.field_metadata import (
    LogFieldMetadataService,
)
from services.web.query.ai_assistant.log_tools.schemas import (
    GetLogFieldMetadataRequest,
    LogFieldScope,
)
from services.web.query.utils.formatter import HitsFormatter
from tests.test_query.test_ai_assistant.base import AIAssistantTestCase

FIELD_METADATA_MODULE = "services.web.query.ai_assistant.log_tools.field_metadata"


class TestLogFieldMetadataService(AIAssistantTestCase):
    """字段探索只基于已授权、脱敏后的受控样本。"""

    def setUp(self):
        super().setUp()
        self.condition = self.make_condition()
        self.context = LogQueryContext(
            username=self.username,
            namespace=self.namespace,
            condition=self.condition,
            table="test_rt.doris",
            conditions=(),
        )
        self.raw_rows = [
            {
                "system_id": self.target_system_id,
                "resource_type_id": "host",
                "action_id": "view",
                "extend_data": {
                    "risk": {"score": 80},
                    "region": "raw-region",
                    "unsafe-key": "raw-unsafe",
                },
            },
            {
                "system_id": self.target_system_id,
                "resource_type_id": "host",
                "action_id": "view",
                "extend_data": {
                    "risk": {"score": 90},
                    "region": "raw-region",
                    "mixed": ["value"],
                    "nullable": None,
                },
            },
        ]
        self.safe_rows = [
            {
                "system_id": self.target_system_id,
                "resource_type_id": "host",
                "action_id": "view",
                "extend_data": {
                    "risk": {"score": 80},
                    "region": "masked-region",
                    "unsafe-key": "masked-unsafe",
                },
            },
            {
                "system_id": self.target_system_id,
                "resource_type_id": "host",
                "action_id": "view",
                "extend_data": {
                    "risk": {"score": 90},
                    "region": "masked-region",
                    "mixed": ["value"],
                    "nullable": None,
                },
            },
        ]
        self.mock_context = self.enterContext(
            mock.patch(f"{FIELD_METADATA_MODULE}.LogQueryContextService.build", return_value=self.context)
        )
        self.mock_query = self.enterContext(mock.patch(f"{FIELD_METADATA_MODULE}.api.bk_base.query_sync"))
        self.mock_query.return_value = {"list": self.raw_rows}
        self.mock_parser = self.enterContext(mock.patch(f"{FIELD_METADATA_MODULE}.SearchDataParser"))
        self.mock_parser.return_value.parse_data.return_value = self.safe_rows

    def _get_metadata(self, **kwargs):
        return LogFieldMetadataService.get_metadata(
            username=self.username,
            namespace=self.namespace,
            request=GetLogFieldMetadataRequest(condition=self.condition, **kwargs),
        )

    def test_extended_fields_are_inferred_one_level_only_after_desensitization(self):
        result = self._get_metadata(field_scope=LogFieldScope.EXTENDED)

        region = next(item for item in result.fields if item.field.keys == ["region"])
        risk = next(item for item in result.fields if item.field.keys == ["risk"])
        self.assertEqual(region.field.field_type, "string")
        self.assertEqual(region.observed_types, ["string"])
        self.assertEqual(region.sample_values, ["masked-region"])
        self.assertTrue(risk.is_expandable)
        self.assertEqual(risk.observed_types, ["object"])
        self.assertEqual(risk.sample_values, [])
        mixed = next(item for item in result.fields if item.field.keys == ["mixed"])
        self.assertEqual(mixed.observed_types, ["array"])
        self.assertEqual(mixed.sample_values, [])
        self.assertNotIn("score", [item.field.keys[-1] for item in result.fields])
        self.assertNotIn("unsafe-key", [item.field.keys[-1] for item in result.fields])
        self.mock_parser.return_value.parse_data.assert_called_once_with(self.raw_rows, username=self.username)

    def test_parent_keys_only_discovers_the_next_level(self):
        result = self._get_metadata(parent_keys=["risk"], field_scope=LogFieldScope.EXTENDED)

        self.assertEqual([item.field.keys for item in result.fields], [["risk", "score"]])
        self.assertEqual(result.fields[0].sample_values, [80, 90])
        self.assertFalse(result.fields[0].is_expandable)

    def test_basic_extended_and_all_scopes_have_expected_categories(self):
        basic = self._get_metadata(field_scope=LogFieldScope.BASIC)
        extended = self._get_metadata(field_scope=LogFieldScope.EXTENDED)
        combined = self._get_metadata(field_scope=LogFieldScope.ALL)

        self.assertTrue(basic.fields)
        self.assertTrue(all(item.category == LogFieldScope.BASIC for item in basic.fields))
        self.assertTrue(extended.fields)
        self.assertTrue(all(item.category == LogFieldScope.EXTENDED for item in extended.fields))
        self.assertEqual(
            [item.category for item in combined.fields],
            [LogFieldScope.BASIC] * len(basic.fields) + [LogFieldScope.EXTENDED] * len(extended.fields),
        )

    def test_unprojected_basic_fields_do_not_claim_a_null_observation(self):
        result = self._get_metadata(field_scope=LogFieldScope.BASIC)
        username = next(item for item in result.fields if item.field.raw_name == "username")

        self.assertEqual(username.observed_types, [])
        self.assertEqual(username.sampled_non_null_count, 0)
        self.assertEqual(username.coverage, 0.0)

    def test_mixed_null_and_empty_samples_have_stable_observations_and_coverage(self):
        self.safe_rows = [
            {"extend_data": {"mixed": "text", "nullable": None}},
            {"extend_data": {"mixed": 3, "nullable": None}},
            {"extend_data": {"mixed": False}},
        ]
        self.mock_parser.return_value.parse_data.return_value = self.safe_rows

        result = self._get_metadata(field_scope=LogFieldScope.EXTENDED)
        mixed = next(item for item in result.fields if item.field.keys == ["mixed"])
        nullable = next(item for item in result.fields if item.field.keys == ["nullable"])

        self.assertEqual(mixed.observed_types, ["boolean", "integer", "string"])
        self.assertEqual(mixed.sampled_non_null_count, 3)
        self.assertEqual(mixed.coverage, 1.0)
        self.assertEqual(nullable.observed_types, ["null"])
        self.assertEqual(nullable.sampled_non_null_count, 0)
        self.assertEqual(nullable.coverage, 0.0)

    def test_empty_samples_return_a_valid_empty_summary(self):
        self.mock_query.return_value = {"list": []}
        self.mock_parser.return_value.parse_data.return_value = []

        result = self._get_metadata(field_scope=LogFieldScope.EXTENDED)

        self.assertEqual(result.fields, [])
        self.assertEqual(result.sample_summary.sampled_count, 0)
        self.assertEqual(result.sample_summary.returned_field_count, 0)
        self.assertFalse(result.sample_summary.truncated)

    @override_settings(AI_LOG_FIELD_METADATA_SAMPLE_VALUES=1)
    def test_sample_values_are_desensitized_deduplicated_and_bounded(self):
        result = self._get_metadata(field_scope=LogFieldScope.EXTENDED)
        region = next(item for item in result.fields if item.field.keys == ["region"])

        self.assertEqual(region.sample_values, ["masked-region"])
        serialized = result.model_dump_json()
        self.assertNotIn("raw-region", serialized)
        self.assertNotIn("raw-unsafe", serialized)

    def test_parent_object_does_not_leak_deep_or_unsupported_keys_through_samples(self):
        self.safe_rows[0]["extend_data"]["risk"]["unsafe-key"] = "deep-secret"

        result = self._get_metadata(field_scope=LogFieldScope.EXTENDED)

        risk = next(item for item in result.fields if item.field.keys == ["risk"])
        self.assertTrue(risk.is_expandable)
        self.assertEqual(risk.sample_values, [])
        self.assertNotIn("deep-secret", result.model_dump_json())
        self.assertNotIn("unsafe-key", result.model_dump_json())

    @override_settings(AI_LOG_FIELD_METADATA_SAMPLE_VALUE_MAX_BYTES=16)
    def test_oversized_scalar_sample_is_skipped_without_a_truncated_value(self):
        self.safe_rows = [{"extend_data": {"region": "x" * 64}}]
        self.mock_parser.return_value.parse_data.return_value = self.safe_rows

        result = self._get_metadata(field_scope=LogFieldScope.EXTENDED)

        region = result.fields[0]
        self.assertEqual(region.observed_types, ["string"])
        self.assertEqual(region.sample_values, [])

    def test_unencodable_scalar_from_hits_formatter_is_skipped_without_failing_request(self):
        formatted_row = HitsFormatter(
            {
                "system_id": self.target_system_id,
                "resource_type_id": "host",
                "action_id": "view",
                "extend_data": json.dumps({"bad": chr(0xD800)}),
            },
            [],
        ).value
        self.mock_parser.return_value.parse_data.return_value = [formatted_row]

        result = self._get_metadata(field_scope=LogFieldScope.EXTENDED)

        bad = result.fields[0]
        self.assertEqual(bad.field.keys, ["bad"])
        self.assertEqual(bad.observed_types, ["string"])
        self.assertEqual(bad.coverage, 1.0)
        self.assertEqual(bad.sample_values, [])

    @override_settings(AI_LOG_FIELD_METADATA_MAX_FIELDS=1, AI_LOG_FIELD_METADATA_SAMPLE_VALUE_MAX_BYTES=32)
    def test_large_nested_samples_keep_the_serialized_response_bounded(self):
        self.safe_rows = [
            {
                "extend_data": {
                    "payload": {"deep": "x" * 1024 * 1024},
                    "entries": ["x" * 1024 * 1024],
                }
            }
        ]
        self.mock_parser.return_value.parse_data.return_value = self.safe_rows

        result = self._get_metadata(field_scope=LogFieldScope.EXTENDED)

        self.assertEqual(len(result.fields), 1)
        self.assertFalse(result.fields[0].sample_values)
        self.assertLess(len(result.model_dump_json().encode("utf-8")), 4096)

    @override_settings(AI_LOG_FIELD_METADATA_MAX_FIELDS=2)
    def test_field_count_is_bounded_with_summary_truncated(self):
        result = self._get_metadata(field_scope=LogFieldScope.EXTENDED)

        self.assertEqual(len(result.fields), 2)
        self.assertEqual(result.sample_summary.returned_field_count, 2)
        self.assertTrue(result.sample_summary.truncated)
        self.assertEqual([item.field.keys for item in result.fields], [["mixed"], ["nullable"]])

    def test_query_uses_only_minimal_projection(self):
        self._get_metadata(field_scope=LogFieldScope.EXTENDED)

        sql = self.mock_query.call_args.kwargs["sql"]
        self.assertIn("`system_id`", sql)
        self.assertIn("`resource_type_id`", sql)
        self.assertIn("`action_id`", sql)
        self.assertIn("`extend_data`", sql)
        self.assertNotIn("SELECT *", sql)
        self.assertNotIn("`username`", sql)

    def test_api_request_timeout_cause_is_mapped_to_controlled_timeout(self):
        for chain_attribute in ("__cause__", "__context__"):
            with self.subTest(chain_attribute=chain_attribute):
                error = APIRequestError(result="gateway failed")
                setattr(error, chain_attribute, RequestsTimeout("upstream timeout"))
                self.mock_query.side_effect = error

                with self.assertRaises(LogQueryTimeout) as raised:
                    self._get_metadata(field_scope=LogFieldScope.EXTENDED)

                self.assertIs(raised.exception.__cause__, error)

    def test_controlled_log_tool_exception_is_preserved(self):
        error = LogQueryTimeout()
        self.mock_query.side_effect = error

        with self.assertRaises(LogQueryTimeout) as raised:
            self._get_metadata(field_scope=LogFieldScope.EXTENDED)

        self.assertIs(raised.exception, error)

    def test_direct_timeouts_and_infrastructure_errors_are_mapped_without_details(self):
        for error, expected_exception in (
            (RequestsTimeout("request timeout"), LogQueryTimeout),
            (TimeoutError("socket timeout"), LogQueryTimeout),
            (RuntimeError("SELECT secret FROM audit_log"), LogQueryFailed),
        ):
            with self.subTest(error=type(error).__name__):
                self.mock_query.side_effect = error
                with self.assertRaises(expected_exception) as raised:
                    self._get_metadata(field_scope=LogFieldScope.EXTENDED)

                self.assertNotIn("SELECT secret", str(raised.exception))

    def test_desensitization_error_is_mapped_to_controlled_query_failure(self):
        self.mock_parser.return_value.parse_data.side_effect = RuntimeError("sensitive raw value")

        with self.assertRaises(LogQueryFailed) as raised:
            self._get_metadata(field_scope=LogFieldScope.EXTENDED)

        self.assertNotIn("sensitive raw value", str(raised.exception))


class TestGetLogFieldMetadataRequest(AIAssistantTestCase):
    """请求父路径与下游可消费的 LogFieldRef 使用同一安全边界。"""

    def test_parent_keys_reuse_safe_extend_data_path_contract(self):
        request = GetLogFieldMetadataRequest(condition=self.make_condition(), parent_keys=["risk", "detail"])

        self.assertEqual(request.parent_keys, ["risk", "detail"])
        with self.assertRaises(PydanticValidationError):
            GetLogFieldMetadataRequest(condition=self.make_condition(), parent_keys=["unsafe-key"])
