# -*- coding: utf-8 -*-
"""日志工具公共协议与受控投影测试。"""

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, override_settings
from pydantic import ValidationError as PydanticValidationError

from services.web.query.ai_assistant.exceptions import (
    InvalidLogCondition,
    LogQueryFailed,
    LogQueryResponseTooLarge,
    LogQueryTimeout,
    SensitiveFieldPermissionDenied,
    UnsupportedAggregation,
    UnsupportedLogField,
)
from services.web.query.ai_assistant.log_tools.schemas import (
    AggregateLogsRequest,
    GetLogFieldMetadataRequest,
    JSONValueType,
    LogFieldRef,
    LogFieldType,
    SearchLogsRequest,
)
from services.web.query.ai_assistant.log_tools.sql import ProjectedLogSQLBuilder
from services.web.query.ai_assistant.schemas import SearchCondition
from tests.test_query.test_ai_assistant.base import AIAssistantTestCase

BACKEND_ROOT = Path(__file__).resolve().parents[3]
LOG_TOOL_EXCEPTIONS = Path("services/web/query/ai_assistant/exceptions.py")
PRODUCTION_SOURCE_DIRECTORIES = ("api", "apps", "blueking", "core", "services")


class TestLogToolSettings(SimpleTestCase):
    """部署配置不能破坏公开请求的固定默认值。"""

    def test_page_size_limit_below_public_default_fails_at_startup(self):
        environment = os.environ.copy()
        environment["BKAPP_AI_LOG_SEARCH_MAX_PAGE_SIZE"] = "19"

        completed = subprocess.run(
            [sys.executable, "-c", "import services.web.settings"],
            cwd=BACKEND_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("AI_LOG_SEARCH_MAX_PAGE_SIZE 不能小于公开默认值 20", completed.stderr)

    def test_aggregation_limit_below_public_default_fails_at_startup(self):
        environment = os.environ.copy()
        environment["BKAPP_AI_LOG_AGGREGATION_MAX_LIMIT"] = "19"

        completed = subprocess.run(
            [sys.executable, "-c", "import services.web.settings"],
            cwd=BACKEND_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("AI_LOG_AGGREGATION_MAX_LIMIT 不能小于公开默认值 20", completed.stderr)


def _module_code_owners(module_code: str):
    """扫描生产源码中的 MODULE_CODE 声明，避免测试和本地生成文件污染唯一性契约。"""
    owners = []
    for source_directory in PRODUCTION_SOURCE_DIRECTORIES:
        for source_path in (BACKEND_ROOT / source_directory).rglob("*.py"):
            tree = ast.parse(source_path.read_text(encoding="utf-8-sig"), filename=str(source_path))
            relative_path = source_path.relative_to(BACKEND_ROOT)
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    for statement in node.body:
                        if (
                            isinstance(statement, (ast.Assign, ast.AnnAssign))
                            and _module_code_value(statement) == module_code
                        ):
                            owners.append((relative_path, node.name))
                elif isinstance(node, (ast.Assign, ast.AnnAssign)) and _module_code_value(node) == module_code:
                    owners.append((relative_path, None))
    return owners


def _module_code_value(statement):
    targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
    if not any(isinstance(target, ast.Name) and target.id == "MODULE_CODE" for target in targets):
        return None
    value = statement.value
    return value.value if isinstance(value, ast.Constant) and isinstance(value.value, str) else None


def _log_tool_exception_hierarchy():
    """解析 LogToolException 继承树，避免把同一模块内的合法子类误判为冲突。"""
    tree = ast.parse((BACKEND_ROOT / LOG_TOOL_EXCEPTIONS).read_text(encoding="utf-8-sig"))
    bases = {
        node.name: {base.id for base in node.bases if isinstance(base, ast.Name)}
        for node in tree.body
        if isinstance(node, ast.ClassDef)
    }

    def belongs_to_log_tool_exception(class_name):
        if class_name == "LogToolException":
            return True
        return any(
            base == "LogToolException" or belongs_to_log_tool_exception(base) for base in bases.get(class_name, set())
        )

    return {class_name for class_name in bases if belongs_to_log_tool_exception(class_name)}


class TestLogFieldRef(AIAssistantTestCase):
    """字段引用只允许现有日志检索可见字段及其 JSON 子路径。"""

    def test_standard_field_without_keys_is_allowed(self):
        field = LogFieldRef(raw_name="username", field_type="string")

        self.assertEqual(field.model_dump(), {"raw_name": "username", "keys": [], "field_type": "string"})
        self.assertEqual(field.field_type, LogFieldType.STRING)

    def test_start_time_is_the_only_extra_projection_field_needed_by_default_columns(self):
        field = LogFieldRef(raw_name="start_time")

        self.assertEqual(field.raw_name, "start_time")

    def test_internal_collector_fields_are_not_agent_projection_fields(self):
        for raw_name in (
            "__ext",
            "cloudId",
            "collector_config_id",
            "end_time",
            "gseIndex",
            "iterationIndex",
            "path",
            "serverIp",
            "snapshot_user_info",
        ):
            with self.subTest(raw_name=raw_name):
                with self.assertRaises(PydanticValidationError):
                    LogFieldRef(raw_name=raw_name)

    def test_all_visible_json_fields_support_multilevel_keys(self):
        container = LogFieldRef(raw_name="extend_data")
        nested = LogFieldRef(raw_name="instance_data", keys=["ticket", "detail", "id"])

        self.assertEqual(container.keys, [])
        self.assertEqual(nested.keys, ["ticket", "detail", "id"])

    def test_unknown_standard_field_is_rejected(self):
        with self.assertRaises(PydanticValidationError):
            LogFieldRef(raw_name="unknown_column")

    def test_standard_field_cannot_use_nested_keys(self):
        with self.assertRaises(PydanticValidationError):
            LogFieldRef(raw_name="username", keys=["bypass"])

    def test_extend_data_accepts_business_defined_unicode_and_punctuation_keys(self):
        for key in ("中文字段", "123field", "bad-key", "x`y", "带 空格", "x']; SELECT 1; --"):
            with self.subTest(key=key):
                field = LogFieldRef(raw_name="extend_data", keys=[key])
                self.assertEqual(field.keys, [key])

    def test_extend_data_rejects_literal_dot_in_path_segment(self):
        """点号是跨模块路径分隔符，不能同时作为无转义的字面 key。"""

        with self.assertRaises(PydanticValidationError):
            LogFieldRef(raw_name="extend_data", keys=["a.b"])

    def test_extend_data_rejects_empty_key(self):
        with self.assertRaises(PydanticValidationError):
            LogFieldRef(raw_name="extend_data", keys=[""])

    def test_observed_json_types_are_explicit_enums(self):
        self.assertEqual(JSONValueType.OBJECT, "object")
        self.assertEqual(JSONValueType.NULL, "null")


class TestGetLogFieldMetadataRequest(AIAssistantTestCase):
    """字段探索位置使用完整字段引用，不再隐式绑定 extend_data。"""

    def test_parent_field_accepts_any_visible_json_path(self):
        request = GetLogFieldMetadataRequest(
            condition=self.make_condition(),
            parent_field={"raw_name": "instance_data", "keys": ["风险-详情"]},
        )
        self.assertEqual(request.parent_field.raw_name, "instance_data")
        self.assertEqual(request.parent_field.keys, ["风险-详情"])

    def test_parent_field_rejects_non_json_field_and_empty_key(self):
        with self.assertRaises(PydanticValidationError):
            GetLogFieldMetadataRequest(condition=self.make_condition(), parent_field={"raw_name": "username"})
        with self.assertRaises(PydanticValidationError):
            GetLogFieldMetadataRequest(
                condition=self.make_condition(),
                parent_field={"raw_name": "extend_data", "keys": [""]},
            )


class TestSearchConditionTimeRange(AIAssistantTestCase):
    """检索条件模型统一保证时间顺序，避免调用方重复补充校验。"""

    def test_reversed_time_range_is_rejected_by_schema(self):
        with self.assertRaises(PydanticValidationError):
            SearchCondition(
                scope_id=self.target_system_id,
                start_time="2026-08-14T00:00:00+08:00",
                end_time="2026-08-13T00:00:00+08:00",
            )


class TestAgentLogToolRequestCostBoundaries(AIAssistantTestCase):
    """三项 Agent 日志工具共享同一组不可放大的请求成本边界。"""

    request_models = (GetLogFieldMetadataRequest, SearchLogsRequest, AggregateLogsRequest)

    def _request_payload(self, model, condition):
        payload = {"condition": condition}
        if model is AggregateLogsRequest:
            payload["metrics"] = [{"id": "count", "type": "COUNT"}]
        return payload

    def _validate_all(self, condition):
        for model in self.request_models:
            with self.subTest(model=model.__name__):
                model.model_validate(self._request_payload(model, condition))

    def _reject_all(self, condition):
        for model in self.request_models:
            with self.subTest(model=model.__name__):
                with self.assertRaises(PydanticValidationError):
                    model.model_validate(self._request_payload(model, condition))

    def _condition(self, **changes):
        payload = self.make_condition().model_dump(mode="json")
        payload.update(changes)
        return payload

    def _condition_with_encoded_size(self, encoded_size):
        filters = [""] * 17
        condition = self._condition(conditions=[self._field_condition(filters=filters)])
        overhead = len(json.dumps(condition, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        remaining = encoded_size - overhead
        for index in range(len(filters)):
            content_bytes = min(16 * 1024 - 2, remaining)
            filters[index] = "x" * content_bytes
            remaining -= content_bytes
        self.assertEqual(remaining, 0)
        return condition

    @staticmethod
    def _field_condition(*, filters=None, keys=None):
        return {
            "field": {"raw_name": "extend_data", "field_type": None, "keys": keys or ["risk"]},
            "operator": "eq",
            "filters": ["value"] if filters is None else filters,
        }

    def test_condition_count_accepts_limit_minus_one_and_limit_but_rejects_plus_one(self):
        for count in (99, 100):
            with self.subTest(count=count):
                self._validate_all(self._condition(conditions=[self._field_condition()] * count))
        self._reject_all(self._condition(conditions=[self._field_condition()] * 101))

    def test_filter_count_accepts_limit_minus_one_and_limit_but_rejects_plus_one(self):
        for count in (999, 1000):
            with self.subTest(count=count):
                self._validate_all(self._condition(conditions=[self._field_condition(filters=["x"] * count)]))
        self._reject_all(self._condition(conditions=[self._field_condition(filters=["x"] * 1001)]))

    def test_filter_values_accept_only_string_integer_and_float(self):
        """复杂 JSON 值没有稳定的 SQL 比较语义，必须在 Agent 协议入口拒绝。"""

        self._validate_all(self._condition(conditions=[self._field_condition(filters=["alice", 1, -2, 3.5])]))
        for value in ({"nested": "value"}, ["nested"], True, None, float("nan"), float("inf")):
            with self.subTest(value=value):
                self._reject_all(self._condition(conditions=[self._field_condition(filters=[value])]))

    def test_single_filter_utf8_size_accepts_limit_minus_one_and_limit_but_rejects_plus_one(self):
        limit = 16 * 1024
        for encoded_size in (limit - 1, limit):
            with self.subTest(encoded_size=encoded_size):
                value = "x" * (encoded_size - len(json.dumps("", ensure_ascii=False).encode("utf-8")))
                self._validate_all(self._condition(conditions=[self._field_condition(filters=[value])]))
        oversized = "中" * ((limit // 3) + 1)
        self._reject_all(self._condition(conditions=[self._field_condition(filters=[oversized])]))

    def test_complete_condition_utf8_size_accepts_limit_minus_one_and_limit_but_rejects_plus_one(self):
        limit = 256 * 1024
        for encoded_size in (limit - 1, limit):
            with self.subTest(encoded_size=encoded_size):
                self._validate_all(self._condition_with_encoded_size(encoded_size))
        self._reject_all(self._condition_with_encoded_size(limit + 1))

    def test_field_key_length_and_depth_boundaries(self):
        for key_length in (127, 128):
            with self.subTest(key_length=key_length):
                self._validate_all(self._condition(conditions=[self._field_condition(keys=["k" * key_length])]))
        self._reject_all(self._condition(conditions=[self._field_condition(keys=["k" * 129])]))

        for depth in (15, 16):
            with self.subTest(depth=depth):
                self._validate_all(self._condition(conditions=[self._field_condition(keys=["level"] * depth)]))
        self._reject_all(self._condition(conditions=[self._field_condition(keys=["level"] * 17)]))

    def test_full_field_path_utf8_size_accepts_limit_minus_one_and_limit_but_rejects_plus_one(self):
        prefix_size = len(b"extend_data.")
        for encoded_size in (1023, 1024):
            with self.subTest(encoded_size=encoded_size):
                keys = ["k" * 128] * 7
                consumed = prefix_size + sum(len(key) for key in keys) + len(keys)
                keys.append("k" * (encoded_size - consumed))
                self._validate_all(self._condition(conditions=[self._field_condition(keys=keys)]))
        keys = ["k" * 128] * 7
        consumed = prefix_size + sum(len(key) for key in keys) + len(keys)
        keys.append("k" * (1025 - consumed))
        self._reject_all(self._condition(conditions=[self._field_condition(keys=keys)]))

    def test_scope_id_length_accepts_limit_minus_one_and_limit_but_rejects_plus_one(self):
        for length in (254, 255):
            with self.subTest(length=length):
                self._validate_all(self._condition(scope_id="s" * length))
        self._reject_all(self._condition(scope_id="s" * 256))

    def test_runtime_configuration_can_tighten_request_limits(self):
        cases = (
            ("AI_LOG_TOOL_MAX_CONDITIONS", 2, self._condition(conditions=[self._field_condition()] * 3)),
            (
                "AI_LOG_TOOL_MAX_FILTERS_PER_CONDITION",
                2,
                self._condition(conditions=[self._field_condition(filters=["a", "b", "c"])]),
            ),
            (
                "AI_LOG_TOOL_MAX_CONDITION_BYTES",
                256,
                self._condition(conditions=[self._field_condition(filters=["x" * 256])]),
            ),
            (
                "AI_LOG_TOOL_MAX_FILTER_BYTES",
                4,
                self._condition(conditions=[self._field_condition(filters=["xxx"])]),
            ),
            (
                "AI_LOG_TOOL_MAX_FIELD_KEY_LENGTH",
                2,
                self._condition(conditions=[self._field_condition(keys=["key"])]),
            ),
            (
                "AI_LOG_TOOL_MAX_FIELD_PATH_DEPTH",
                2,
                self._condition(conditions=[self._field_condition(keys=["a", "b", "c"])]),
            ),
            (
                "AI_LOG_TOOL_MAX_FIELD_PATH_BYTES",
                16,
                self._condition(conditions=[self._field_condition(keys=["abcdef"])]),
            ),
            ("AI_LOG_TOOL_MAX_SCOPE_ID_LENGTH", 2, self._condition(scope_id="sys")),
        )
        for setting_name, limit, condition in cases:
            with self.subTest(setting_name=setting_name):
                with override_settings(**{setting_name: limit}):
                    self._reject_all(condition)

    @override_settings(
        AI_LOG_TOOL_MAX_CONDITIONS=999,
        AI_LOG_TOOL_MAX_FILTERS_PER_CONDITION=9999,
        AI_LOG_TOOL_MAX_CONDITION_BYTES=999999,
        AI_LOG_TOOL_MAX_FILTER_BYTES=999999,
        AI_LOG_TOOL_MAX_FIELD_KEY_LENGTH=999,
        AI_LOG_TOOL_MAX_FIELD_PATH_DEPTH=999,
        AI_LOG_TOOL_MAX_FIELD_PATH_BYTES=9999,
        AI_LOG_TOOL_MAX_SCOPE_ID_LENGTH=999,
    )
    def test_runtime_configuration_cannot_expand_frozen_request_limits(self):
        self._reject_all(self._condition(scope_id="s" * 256))
        self._reject_all(self._condition(conditions=[self._field_condition()] * 101))
        self._reject_all(self._condition(conditions=[self._field_condition(filters=["x"] * 1001)]))
        self._reject_all(self._condition(conditions=[self._field_condition(filters=["x" * (16 * 1024 - 1)])]))
        self._reject_all(self._condition_with_encoded_size(256 * 1024 + 1))
        self._reject_all(self._condition(conditions=[self._field_condition(keys=["x" * 129])]))
        self._reject_all(self._condition(conditions=[self._field_condition(keys=["x"] * 17)]))
        keys = ["k" * 128] * 7
        consumed = len(b"extend_data.") + sum(len(key) for key in keys) + len(keys)
        keys.append("k" * (1025 - consumed))
        self._reject_all(self._condition(conditions=[self._field_condition(keys=keys)]))

    def test_long_log_search_time_range_remains_valid(self):
        self._validate_all(
            self._condition(
                start_time="2020-01-01T00:00:00+08:00",
                end_time="2026-08-29T00:00:00+08:00",
            )
        )


class TestProjectedLogSQLBuilder(AIAssistantTestCase):
    """投影只从已验证的字段引用构造，不接受 SQL 片段。"""

    def _builder(self):
        return ProjectedLogSQLBuilder(
            table="test_rt.doris",
            conditions=[],
            sort_list=[],
            page=2,
            page_size=25,
        )

    def test_builds_projection_from_validated_fields(self):
        sql = self._builder().build_data_sql(
            [
                LogFieldRef(raw_name="username"),
                LogFieldRef(raw_name="extend_data", keys=["ticket", "id"]),
            ]
        )

        self.assertIn("`username`", sql)
        self.assertIn("JSON_EXTRACT_STRING(`extend_data`,'$.ticket.id')", sql)
        self.assertIn("LIMIT 25", sql)
        self.assertIn("OFFSET 25", sql)
        self.assertNotIn("SELECT *", sql)

    def test_unicode_and_quote_keys_are_escaped_by_json_sql_builder(self):
        sql = self._builder().build_data_sql([LogFieldRef(raw_name="extend_data", keys=["中文字段", "x']; SELECT 1; --"])])

        self.assertIn("中文字段", sql)
        self.assertIn("'$.中文字段.\"x'']; SELECT 1; --\"'", sql)
        self.assertNotIn("'$.中文字段.\"x']; SELECT 1; --\"'", sql)

    def test_quote_and_backslash_key_keeps_json_path_escaping_after_sql_parsing(self):
        sql = self._builder().build_data_sql([LogFieldRef(raw_name="extend_data", keys=['quoted"key', r"path\key"])])

        self.assertIn(r'quoted\\"key', sql)
        self.assertIn(r"path\\\\key", sql)

    def test_rejects_non_field_reference(self):
        with self.assertRaises(TypeError):
            self._builder().build_data_sql(["username"])


class TestLogToolExceptions(AIAssistantTestCase):
    """Agent/MCP 工具异常使用独立且不泄露内部细节的数字码。"""

    def test_codes_statuses_and_messages_are_fixed(self):
        cases = (
            (InvalidLogCondition, "26001", 400),
            (UnsupportedLogField, "26002", 400),
            (UnsupportedAggregation, "26003", 400),
            (SensitiveFieldPermissionDenied, "26004", 403),
            (LogQueryTimeout, "26005", 504),
            (LogQueryFailed, "26006", 502),
            (LogQueryResponseTooLarge, "26007", 413),
        )

        codes = set()
        internal_detail = "SELECT secret FROM logs WHERE token='private'"
        for exception_cls, expected_code, expected_status in cases:
            with self.subTest(exception_cls=exception_cls.__name__):
                exception = exception_cls(message=internal_detail)
                public_code = f"{settings.PLATFORM_CODE}{expected_code}"
                codes.add(exception.code)
                self.assertEqual(exception.code, public_code)
                self.assertEqual(exception.STATUS_CODE, expected_status)
                self.assertEqual(exception.message, str(exception_cls.MESSAGE))
                self.assertNotIn(internal_detail, exception.message)
                self.assertEqual(
                    exception.response_data(),
                    {
                        "result": False,
                        "code": public_code,
                        "message": str(exception_cls.MESSAGE),
                        "data": None,
                    },
                )

        self.assertEqual(len(codes), len(cases))

    def test_module_code_scan_is_limited_to_production_sources(self):
        self.assertEqual(
            PRODUCTION_SOURCE_DIRECTORIES,
            ("api", "apps", "blueking", "core", "services"),
        )
        forbidden_roots = {".venv", "agent", "debug", "evals", "tests"}

        for source_path, _ in _module_code_owners("26"):
            self.assertNotIn(source_path.parts[0], forbidden_roots)

    def test_module_code_26_is_reserved_for_log_tool_exception_hierarchy(self):
        owners = _module_code_owners("26")
        log_tool_hierarchy = _log_tool_exception_hierarchy()
        unrelated_owners = [
            owner for owner in owners if owner[0] != LOG_TOOL_EXCEPTIONS or owner[1] not in log_tool_hierarchy
        ]

        self.assertIn((LOG_TOOL_EXCEPTIONS, "LogToolException"), owners)
        self.assertEqual(unrelated_owners, [])
