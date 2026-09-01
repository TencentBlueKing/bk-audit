# -*- coding: utf-8 -*-
"""日志字段元信息探索测试。"""

import json
from unittest import mock

from bk_resource.exceptions import APIRequestError
from django.test import override_settings
from pydantic import ValidationError as PydanticValidationError
from requests.exceptions import Timeout as RequestsTimeout

from api.bk_base.default import SafeQuerySyncResource
from apps.meta.constants import (
    SENSITIVE_REPLACE_VALUE,
    SensitiveResourceTypeEnum,
    SensitiveUserData,
)
from apps.meta.models import SensitiveObject
from apps.meta.utils.fields import EXTEND_DATA
from services.web.query.ai_assistant.exceptions import (
    LogQueryFailed,
    LogQueryResponseTooLarge,
    LogQueryTimeout,
    SensitiveFieldPermissionDenied,
)
from services.web.query.ai_assistant.log_tools import sensitive
from services.web.query.ai_assistant.log_tools.context import LogQueryContext
from services.web.query.ai_assistant.log_tools.field_metadata import (
    LogFieldMetadataService,
)
from services.web.query.ai_assistant.log_tools.schemas import (
    FieldSampleSummary,
    GetLogFieldMetadataRequest,
    GetLogFieldMetadataResponse,
    JSONValueType,
    LogFieldCategory,
    LogFieldMetadataItem,
    LogFieldMetadataTypeSource,
    LogFieldRef,
)
from services.web.query.constants import COLLECT_SEARCH_CONFIG
from services.web.query.search_data import SearchDataParser
from services.web.query.utils.formatter import HitsFormatter
from tests.test_query.test_ai_assistant.base import AIAssistantTestCase

FIELD_METADATA_MODULE = "services.web.query.ai_assistant.log_tools.field_metadata"
INVALID_FIELD_KEY = "x" * 129


class TestSensitiveQueryFields(AIAssistantTestCase):
    """查询补列只处理根投影与脱敏身份，不改变调用方字段。"""

    def test_child_paths_share_root_and_identity_columns_are_unique(self):
        """生成器输入中的重复子路径和身份列只产生一个根投影。"""
        fields = [
            LogFieldRef(raw_name="extend_data", keys=["credential"]),
            LogFieldRef(raw_name="extend_data", keys=["public"]),
            LogFieldRef(raw_name="extend_data"),
            LogFieldRef(raw_name="system_id"),
            LogFieldRef(raw_name="username"),
        ]

        result = sensitive.prepare_sensitive_query_fields(iter(fields))

        self.assertEqual(
            result,
            tuple(
                LogFieldRef(raw_name=name)
                for name in ("extend_data", "system_id", "username", "resource_type_id", "action_id")
            ),
        )
        self.assertEqual(fields[0].keys, ["credential"])

    def test_empty_input_still_includes_all_identity_columns(self):
        """无请求列时也保留逐行规则匹配所需身份。"""
        self.assertEqual(
            sensitive.prepare_sensitive_query_fields(()),
            tuple(LogFieldRef(raw_name=name) for name in ("system_id", "resource_type_id", "action_id")),
        )


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
                    "业务-字段": "raw-unsafe",
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
                    "业务-字段": "masked-unsafe",
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
        self.mock_query = self.enterContext(mock.patch.object(SafeQuerySyncResource, "request"))
        self.mock_query.return_value = {"list": self.raw_rows}
        self.mock_parser = self.enterContext(mock.patch(f"{FIELD_METADATA_MODULE}.SearchDataParser"))
        self.mock_parser.return_value.parse_data.return_value = self.safe_rows
        self.mock_sensitive_access = self.enterContext(
            mock.patch(f"{FIELD_METADATA_MODULE}.SensitiveLogFieldPermissionService.ensure_access")
        )

    def _get_metadata(self, **kwargs):
        return LogFieldMetadataService.get_metadata(
            username=self.username,
            namespace=self.namespace,
            request=GetLogFieldMetadataRequest(condition=self.condition, **kwargs),
        )

    def test_extended_fields_are_inferred_one_level_only_after_desensitization(self):
        result = self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data"))

        region = next(item for item in result.fields if item.field.keys == ["region"])
        risk = next(item for item in result.fields if item.field.keys == ["risk"])
        self.assertEqual(region.field.field_type, "string")
        self.assertEqual(region.observed_types, [JSONValueType.STRING])
        self.assertEqual(region.sample_values, ["masked-region"])
        self.assertTrue(risk.is_expandable)
        self.assertEqual(risk.observed_types, [JSONValueType.OBJECT])
        self.assertEqual(risk.sample_values, [])
        mixed = next(item for item in result.fields if item.field.keys == ["mixed"])
        self.assertEqual(mixed.observed_types, [JSONValueType.ARRAY])
        self.assertEqual(mixed.sample_values, [])
        self.assertNotIn("score", [item.field.keys[-1] for item in result.fields])
        business_field = next(item for item in result.fields if item.field.keys == ["业务-字段"])
        self.assertEqual(business_field.sample_values, ["masked-unsafe"])
        self.mock_parser.return_value.parse_data.assert_called_once_with(
            self.raw_rows,
            username=self.username,
            system_id=self.target_system_id,
        )

    def test_unsupported_child_key_marks_field_scan_truncated(self):
        self.mock_parser.return_value.parse_data.return_value = [
            {"extend_data": {"valid": "visible", "literal.dot": "unsupported"}}
        ]

        result = self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data"))

        self.assertEqual([item.field.keys for item in result.fields], [["valid"]])
        self.assertTrue(result.sample_summary.truncated)

    def test_parent_field_only_discovers_the_next_level(self):
        result = self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data", keys=["risk"]))

        self.assertEqual([item.field.keys for item in result.fields], [["risk", "score"]])
        self.assertEqual(result.fields[0].sample_values, [80, 90])
        self.assertFalse(result.fields[0].is_expandable)

    def test_root_and_child_requests_have_expected_categories(self):
        basic = self._get_metadata()
        extended = self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data"))

        self.assertTrue(basic.fields)
        self.assertTrue(all(item.category == LogFieldCategory.BASIC for item in basic.fields))
        self.assertTrue(extended.fields)
        self.assertTrue(all(item.category == LogFieldCategory.EXTENDED for item in extended.fields))

    def test_all_visible_json_roots_are_marked_expandable(self):
        result = self._get_metadata()

        fields_by_name = {item.field.raw_name: item for item in result.fields}
        json_fields = {
            config.field.field_name for config in COLLECT_SEARCH_CONFIG.field_configs if config.field.is_json
        }
        non_json_fields = {
            config.field.field_name for config in COLLECT_SEARCH_CONFIG.field_configs if not config.field.is_json
        }
        self.assertTrue(json_fields - {EXTEND_DATA.field_name})
        self.assertTrue(non_json_fields)
        self.assertTrue(all(fields_by_name[field_name].is_expandable for field_name in json_fields))
        self.assertTrue(all(not fields_by_name[field_name].is_expandable for field_name in non_json_fields))
        self.assertIn("start_time", fields_by_name)
        self.assertEqual(fields_by_name["start_time"].field.field_type, "long")
        self.assertEqual(fields_by_name["start_time"].allow_operators, [])

    def test_exploration_uses_formatted_samples_without_rejecting_parent(self):
        """父路径不参与拒绝校验；系统及全局规则统一控制样本遮罩和私密删除。"""
        for keys in ([], ["credential"]):
            for global_rule in (False, True):
                for authorized in (False, True):
                    with self.subTest(keys=keys, global_rule=global_rule, authorized=authorized):
                        prefix = ".".join(["extend_data", *keys])
                        rule_kwargs = {
                            "system_id": SensitiveUserData.SYSTEM_ID if global_rule else self.target_system_id,
                            "resource_id": SensitiveUserData.RESOURCE_ID if global_rule else "host",
                            "resource_type": SensitiveResourceTypeEnum.RESOURCE.value,
                        }
                        sensitive = SensitiveObject(id=1, fields=[{"field_name": f"{prefix}.secret"}], **rule_kwargs)
                        private = SensitiveObject(
                            id=2, is_private=True, fields=[{"field_name": f"{prefix}.private"}], **rule_kwargs
                        )
                        payload = {
                            "public": "visible",
                            "secret": "protected-value",
                            "private": "private-value",
                        }
                        self.mock_query.return_value = {
                            "list": [
                                {
                                    "system_id": self.target_system_id,
                                    "resource_type_id": "host",
                                    "action_id": "view",
                                    "extend_data": json.dumps({"credential": payload} if keys else payload),
                                }
                            ]
                        }
                        self.mock_parser.return_value = SearchDataParser()
                        self.mock_sensitive_access.reset_mock()
                        with (
                            mock.patch.object(SensitiveObject._objects, "filter") as private_filter,
                            mock.patch.object(SensitiveObject.objects, "all") as sensitive_all,
                            mock.patch.object(SearchDataParser, "_permission_service") as permission_service,
                        ):
                            private_filter.return_value.filter.return_value = [private]
                            sensitive_all.return_value.filter.return_value = [sensitive]
                            permission_service.return_value.get_sensitive_object_permissions.return_value = {
                                "1": authorized,
                            }
                            result = self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data", keys=keys))

                        self.mock_sensitive_access.assert_called_once_with(
                            username=self.username, system_id=self.target_system_id, fields=set()
                        )
                        self.assertEqual(
                            {item.field.keys[-1]: item.sample_values for item in result.fields},
                            {
                                "public": ["visible"],
                                "secret": ["protected-value" if authorized else SENSITIVE_REPLACE_VALUE],
                            },
                        )
                        self.assertNotIn("private-value", result.model_dump_json())
                        if not authorized:
                            self.assertNotIn("protected-value", result.model_dump_json())

    def test_sensitive_condition_is_checked_before_query(self):
        self.condition = self.make_condition(
            conditions=[self.make_field_condition(raw_name="extend_data", keys=["identity", "ssn"])]
        )
        self.context.condition.conditions = self.condition.conditions
        self.mock_sensitive_access.side_effect = SensitiveFieldPermissionDenied()

        with self.assertRaises(SensitiveFieldPermissionDenied):
            self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data", keys=["public"]))

        self.mock_sensitive_access.assert_called_once_with(
            username=self.username,
            system_id=self.target_system_id,
            fields={"extend_data.identity.ssn"},
        )
        self.mock_query.assert_not_called()
        self.mock_parser.return_value.parse_data.assert_not_called()

    def test_raw_log_condition_uses_the_same_sensitive_precheck_as_other_tools(self):
        self.condition = self.make_condition(
            conditions=[self.make_field_condition(raw_name="log", operator="match_any")]
        )
        self.context.condition.conditions = self.condition.conditions
        self.mock_sensitive_access.side_effect = SensitiveFieldPermissionDenied()

        with self.assertRaises(SensitiveFieldPermissionDenied):
            self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data"))

        self.mock_sensitive_access.assert_called_once_with(
            username=self.username,
            system_id=self.target_system_id,
            fields={"log"},
        )
        self.mock_query.assert_not_called()

    def test_other_visible_json_roots_can_be_explored(self):
        self.safe_rows = [{"instance_data": {"risk": "masked"}}]
        self.mock_parser.return_value.parse_data.return_value = self.safe_rows

        result = self._get_metadata(parent_field=LogFieldRef(raw_name="instance_data"))

        self.assertEqual(result.fields[0].field.raw_name, "instance_data")
        self.assertEqual(result.fields[0].field.keys, ["risk"])
        self.assertEqual(result.fields[0].sample_values, ["masked"])

    @override_settings(AI_LOG_TOOL_MAX_FIELD_PATH_DEPTH=0)
    def test_extend_data_root_is_not_expandable_when_path_depth_is_zero(self):
        result = self._get_metadata()

        extend_data = next(item for item in result.fields if item.field.raw_name == EXTEND_DATA.field_name)
        self.assertFalse(extend_data.is_expandable)

    def test_unprojected_basic_fields_do_not_claim_a_null_observation(self):
        result = self._get_metadata()
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

        result = self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data"))
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

        result = self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data"))

        self.assertEqual(result.fields, [])
        self.assertEqual(result.sample_summary.sampled_count, 0)
        self.assertEqual(result.sample_summary.returned_field_count, 0)
        self.assertFalse(result.sample_summary.truncated)

    @override_settings(AI_LOG_FIELD_METADATA_SAMPLE_VALUES=1)
    def test_sample_values_are_desensitized_deduplicated_and_bounded(self):
        result = self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data"))
        region = next(item for item in result.fields if item.field.keys == ["region"])

        self.assertEqual(region.sample_values, ["masked-region"])
        serialized = result.model_dump_json()
        self.assertNotIn("raw-region", serialized)
        self.assertNotIn("raw-unsafe", serialized)

    def test_parent_object_does_not_leak_deep_or_unsupported_keys_through_samples(self):
        self.safe_rows[0]["extend_data"]["risk"][INVALID_FIELD_KEY] = "deep-secret"

        result = self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data"))

        risk = next(item for item in result.fields if item.field.keys == ["risk"])
        self.assertTrue(risk.is_expandable)
        self.assertEqual(risk.sample_values, [])
        self.assertNotIn("deep-secret", result.model_dump_json())
        self.assertNotIn(INVALID_FIELD_KEY, result.model_dump_json())

    @override_settings(AI_LOG_FIELD_METADATA_SAMPLE_VALUE_MAX_BYTES=16)
    def test_oversized_scalar_sample_is_skipped_without_a_truncated_value(self):
        self.safe_rows = [{"extend_data": {"region": "x" * 64}}]
        self.mock_parser.return_value.parse_data.return_value = self.safe_rows

        result = self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data"))

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

        result = self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data"))

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

        result = self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data"))

        self.assertEqual(len(result.fields), 1)
        self.assertFalse(result.fields[0].sample_values)
        self.assertLess(len(result.model_dump_json().encode("utf-8")), 4096)

    @override_settings(AI_LOG_FIELD_METADATA_MAX_FIELDS=2)
    def test_field_count_is_bounded_with_summary_truncated(self):
        result = self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data"))

        self.assertEqual(len(result.fields), 2)
        self.assertEqual(result.sample_summary.returned_field_count, 2)
        self.assertTrue(result.sample_summary.truncated)
        self.assertEqual([item.field.keys for item in result.fields], [["region"], ["risk"]])

    @override_settings(AI_LOG_FIELD_METADATA_MAX_FIELDS=999)
    def test_field_count_hard_limit_accepts_limit_minus_one_and_limit_then_truncates_plus_one(self):
        for count in (99, 100, 101):
            with self.subTest(count=count):
                self.safe_rows = [{"extend_data": {f"field_{index:03d}": index for index in range(count)}}]
                self.mock_parser.return_value.parse_data.return_value = self.safe_rows

                result = self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data"))

                self.assertEqual(len(result.fields), min(count, 100))
                self.assertEqual(result.sample_summary.truncated, count > 100)

    @override_settings(AI_LOG_FIELD_METADATA_MAX_FIELDS=999)
    def test_extended_field_scan_stops_after_hard_limit_plus_one_inspected_keys(self):
        class GuardedFields(dict):
            def items(self):
                for index, item in enumerate(super().items()):
                    if index >= 101:
                        raise AssertionError("must stop scanning after hard max plus one")
                    yield item

        self.safe_rows = [{"extend_data": GuardedFields({f"field_{index:03d}": index for index in range(102)})}]
        self.mock_parser.return_value.parse_data.return_value = self.safe_rows

        result = self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data"))

        self.assertEqual(len(result.fields), 100)
        self.assertTrue(result.sample_summary.truncated)

    @override_settings(AI_LOG_FIELD_METADATA_MAX_FIELDS=2)
    def test_extended_field_scan_budget_counts_invalid_keys(self):
        class CountingFields(dict):
            inspected = 0

            def items(self):
                for item in super().items():
                    self.inspected += 1
                    yield item

        extend_data = CountingFields({f"{INVALID_FIELD_KEY}-{index}": index for index in range(100)})
        self.safe_rows = [{"extend_data": extend_data}]
        self.mock_parser.return_value.parse_data.return_value = self.safe_rows

        result = self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data"))

        self.assertEqual(result.fields, [])
        self.assertEqual(extend_data.inspected, 3)
        self.assertTrue(result.sample_summary.truncated)

    @override_settings(AI_LOG_FIELD_METADATA_MAX_FIELDS=2)
    def test_invalid_key_flood_does_not_block_later_sample_rows(self):
        self.safe_rows = [
            {"extend_data": {f"{INVALID_FIELD_KEY}-{index}": index for index in range(100)}},
            {"extend_data": {"valid": 1}},
        ]
        self.mock_parser.return_value.parse_data.return_value = self.safe_rows

        result = self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data"))

        self.assertEqual([item.field.keys for item in result.fields], [["valid"]])
        self.assertTrue(result.sample_summary.truncated)

    @override_settings(AI_LOG_FIELD_METADATA_MAX_FIELDS=2)
    def test_existing_field_observations_are_aggregated_across_sample_rows(self):
        self.safe_rows = [
            {"extend_data": {"shared": 1, "first": 0}},
            {"extend_data": {"new": True, "shared": "two"}},
        ]
        self.mock_parser.return_value.parse_data.return_value = self.safe_rows

        result = self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data"))

        shared = next(item for item in result.fields if item.field.keys == ["shared"])
        self.assertEqual(shared.observed_types, ["integer", "string"])
        self.assertEqual(shared.sampled_non_null_count, 2)
        self.assertEqual(shared.coverage, 1.0)
        self.assertTrue(result.sample_summary.truncated)

    @override_settings(AI_LOG_FIELD_METADATA_MAX_FIELDS=2)
    def test_extended_field_scan_budget_is_applied_to_each_sample_row(self):
        class CountingFields(dict):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.inspected = 0

            def items(self):
                for item in super().items():
                    self.inspected += 1
                    yield item

        containers = [
            CountingFields({f"{INVALID_FIELD_KEY}-{row}-{index}": index for index in range(100)}) for row in range(2)
        ]
        self.safe_rows = [{"extend_data": container} for container in containers]
        self.mock_parser.return_value.parse_data.return_value = self.safe_rows

        result = self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data"))

        self.assertEqual([container.inspected for container in containers], [3, 3])
        self.assertEqual(result.fields, [])
        self.assertTrue(result.sample_summary.truncated)

    @override_settings(AI_LOG_FIELD_METADATA_MAX_FIELDS=2)
    def test_invalid_and_valid_keys_share_the_same_scan_budget(self):
        self.safe_rows = [{"extend_data": {INVALID_FIELD_KEY: 0, "valid": 1, "later": 2}}]
        self.mock_parser.return_value.parse_data.return_value = self.safe_rows

        result = self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data"))

        self.assertEqual([item.field.keys for item in result.fields], [["valid"]])
        self.assertTrue(result.sample_summary.truncated)

    def test_oversized_json_string_is_not_parsed_and_marks_scan_truncated(self):
        oversized = json.dumps({"payload": "x" * (1024 * 1024)})
        self.safe_rows = [{"extend_data": oversized}, {"extend_data": {"valid": 1}}]
        self.mock_parser.return_value.parse_data.return_value = self.safe_rows

        with (
            override_settings(AI_LOG_FIELD_METADATA_RESPONSE_MAX_BYTES=2 * 1024 * 1024),
            mock.patch(f"{FIELD_METADATA_MODULE}.json.loads", wraps=json.loads) as loads,
        ):
            result = self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data"))

        loads.assert_not_called()
        self.assertEqual([item.field.keys for item in result.fields], [["valid"]])
        self.assertTrue(result.sample_summary.truncated)

    @override_settings(AI_LOG_FIELD_METADATA_RESPONSE_MAX_BYTES=8)
    def test_oversized_json_string_uses_character_count_fast_rejection(self):
        class EncodeForbiddenString(str):
            def encode(self, *args, **kwargs):
                raise AssertionError("oversized string must not be encoded")

        with mock.patch(f"{FIELD_METADATA_MODULE}.json.loads") as loads:
            container, truncated = LogFieldMetadataService._resolve_parent(EncodeForbiddenString("x" * 9), [])

        self.assertIsNone(container)
        self.assertTrue(truncated)
        loads.assert_not_called()

    def test_extended_object_expandability_respects_effective_path_depth(self):
        def nested_row(parent_keys):
            root = {}
            current = root
            for key in parent_keys:
                current[key] = {}
                current = current[key]
            current["child"] = {"deeper": True}
            return {"extend_data": root}

        for parent_depth, expected_expandable in ((14, True), (15, False)):
            with self.subTest(parent_depth=parent_depth):
                parent_keys = [f"level_{index}" for index in range(parent_depth)]
                self.safe_rows = [nested_row(parent_keys)]
                self.mock_parser.return_value.parse_data.return_value = self.safe_rows

                result = self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data", keys=parent_keys))

                self.assertEqual(len(result.fields[0].field.keys), parent_depth + 1)
                self.assertEqual(result.fields[0].is_expandable, expected_expandable)

        with override_settings(AI_LOG_TOOL_MAX_FIELD_PATH_DEPTH=2):
            self.safe_rows = [nested_row(["parent"])]
            self.mock_parser.return_value.parse_data.return_value = self.safe_rows
            result = self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data", keys=["parent"]))
        self.assertEqual(len(result.fields[0].field.keys), 2)
        self.assertFalse(result.fields[0].is_expandable)

    def test_sample_row_limit_uses_hard_limit_and_environment_can_only_tighten(self):
        for configured, expected in ((49, 49), (50, 50), (51, 50), (999, 50)):
            with self.subTest(configured=configured):
                with override_settings(AI_ASSISTANT_FIELD_SAMPLE_ROWS=configured):
                    self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data"))
                self.assertIn(f"LIMIT {expected}", self.mock_query.call_args.kwargs["sql"])

    def test_sample_value_count_and_utf8_bytes_use_frozen_hard_limits(self):
        with override_settings(AI_LOG_FIELD_METADATA_SAMPLE_VALUES=999):
            self.safe_rows = [{"extend_data": {"value": value}} for value in (1, 2, 3, 4)]
            self.mock_parser.return_value.parse_data.return_value = self.safe_rows
            result = self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data"))
            self.assertEqual(result.fields[0].sample_values, [1, 2, 3])

        for encoded_size, included in ((1023, True), (1024, True), (1025, False)):
            with self.subTest(encoded_size=encoded_size):
                value = "x" * (encoded_size - 2)
                self.safe_rows = [{"extend_data": {"value": value}}]
                self.mock_parser.return_value.parse_data.return_value = self.safe_rows
                with override_settings(AI_LOG_FIELD_METADATA_SAMPLE_VALUE_MAX_BYTES=9999):
                    result = self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data"))
                self.assertEqual(bool(result.fields[0].sample_values), included)

        self.safe_rows = [{"extend_data": {"value": "中" * 342}}]
        self.mock_parser.return_value.parse_data.return_value = self.safe_rows
        result = self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data"))
        self.assertEqual(result.fields[0].sample_values, [])

    def test_response_utf8_budget_accepts_exact_configured_limit_and_rejects_plus_one(self):
        def item(description):
            return LogFieldMetadataItem(
                field=LogFieldRef(raw_name="username"),
                category=LogFieldCategory.BASIC,
                description=description,
                type_source=LogFieldMetadataTypeSource.DECLARED,
            )

        base = GetLogFieldMetadataResponse(
            fields=[item("")],
            sample_summary=FieldSampleSummary(sampled_count=2, returned_field_count=1, truncated=False),
        )
        configured_limit = len(base.model_dump_json().encode("utf-8")) + 128
        with mock.patch.object(LogFieldMetadataService, "_build_basic_fields", return_value=[item("x" * 128)]):
            with override_settings(AI_LOG_FIELD_METADATA_RESPONSE_MAX_BYTES=configured_limit):
                result = self._get_metadata()
            self.assertEqual(len(result.model_dump_json().encode("utf-8")), configured_limit)

        with mock.patch.object(LogFieldMetadataService, "_build_basic_fields", return_value=[item("x" * 129)]):
            with override_settings(AI_LOG_FIELD_METADATA_RESPONSE_MAX_BYTES=configured_limit):
                with self.assertRaises(LogQueryResponseTooLarge):
                    self._get_metadata()

    def test_response_budget_counts_chinese_utf8_bytes(self):
        oversized = LogFieldMetadataItem(
            field=LogFieldRef(raw_name="username"),
            category=LogFieldCategory.BASIC,
            description="中" * 400,
            type_source=LogFieldMetadataTypeSource.DECLARED,
        )

        with mock.patch.object(LogFieldMetadataService, "_build_basic_fields", return_value=[oversized]):
            with override_settings(AI_LOG_FIELD_METADATA_RESPONSE_MAX_BYTES=1024):
                with self.assertRaises(LogQueryResponseTooLarge):
                    self._get_metadata()

    def test_multiple_fields_are_rejected_when_cumulative_response_exceeds_budget(self):
        fields = [
            LogFieldMetadataItem(
                field=LogFieldRef(raw_name="username"),
                category=LogFieldCategory.BASIC,
                description=f"{index}-" + "x" * 11000,
                type_source=LogFieldMetadataTypeSource.DECLARED,
            )
            for index in range(100)
        ]

        with mock.patch.object(LogFieldMetadataService, "_build_basic_fields", return_value=fields):
            with self.assertRaises(LogQueryResponseTooLarge):
                self._get_metadata()

    @override_settings(AI_LOG_FIELD_METADATA_RESPONSE_MAX_BYTES=2 * 1024 * 1024)
    def test_response_hard_budget_cannot_be_expanded_and_does_not_leak_value(self):
        marker = "secret-marker-" + "x" * (1024 * 1024)
        oversized = LogFieldMetadataItem(
            field=LogFieldRef(raw_name="username"),
            category=LogFieldCategory.BASIC,
            description=marker,
            type_source=LogFieldMetadataTypeSource.DECLARED,
        )

        with mock.patch.object(LogFieldMetadataService, "_build_basic_fields", return_value=[oversized]):
            with self.assertRaises(LogQueryResponseTooLarge) as raised:
                self._get_metadata()

        self.assertNotIn("secret-marker", str(raised.exception))

    def test_query_uses_only_minimal_projection(self):
        self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data"))

        sql = self.mock_query.call_args.kwargs["sql"]
        self.assertEqual(
            sql,
            "SELECT `extend_data`,`system_id`,`resource_type_id`,`action_id` FROM test_rt.doris"
            " ORDER BY `dtEventTimeStamp` DESC,`gseIndex` DESC,`iterationIndex` DESC LIMIT 50",
        )

    def test_api_request_timeout_cause_is_mapped_to_controlled_timeout(self):
        for chain_attribute in ("__cause__", "__context__"):
            with self.subTest(chain_attribute=chain_attribute):
                error = APIRequestError(result="gateway failed")
                setattr(error, chain_attribute, RequestsTimeout("upstream timeout"))
                self.mock_query.side_effect = error

                with self.assertRaises(LogQueryTimeout) as raised:
                    self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data"))

                self.assertIs(raised.exception.__cause__, error)

    def test_controlled_log_tool_exception_is_preserved(self):
        error = LogQueryTimeout()
        self.mock_query.side_effect = error

        with self.assertRaises(LogQueryTimeout) as raised:
            self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data"))

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
                    self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data"))

                self.assertNotIn("SELECT secret", str(raised.exception))

    def test_desensitization_error_is_mapped_to_controlled_query_failure(self):
        self.mock_parser.return_value.parse_data.side_effect = RuntimeError("sensitive raw value")

        with self.assertRaises(LogQueryFailed) as raised:
            self._get_metadata(parent_field=LogFieldRef(raw_name="extend_data"))

        self.assertNotIn("sensitive raw value", str(raised.exception))


class TestGetLogFieldMetadataRequest(AIAssistantTestCase):
    """请求父路径与下游可消费的 LogFieldRef 使用同一安全边界。"""

    def test_parent_field_reuses_visible_json_path_contract(self):
        request = GetLogFieldMetadataRequest(
            condition=self.make_condition(),
            parent_field={"raw_name": "instance_data", "keys": ["风险", "detail-key"]},
        )

        self.assertEqual(request.parent_field.keys, ["风险", "detail-key"])
        with self.assertRaises(PydanticValidationError):
            GetLogFieldMetadataRequest(condition=self.make_condition(), parent_field={"raw_name": "username"})
