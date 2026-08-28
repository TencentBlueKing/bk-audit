# -*- coding: utf-8 -*-
"""日志工具公共协议与受控投影测试。"""

import ast
from pathlib import Path

from django.conf import settings
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
    GetLogFieldMetadataRequest,
    LogFieldRef,
)
from services.web.query.ai_assistant.log_tools.sql import ProjectedLogSQLBuilder
from tests.test_query.test_ai_assistant.base import AIAssistantTestCase

BACKEND_ROOT = Path(__file__).resolve().parents[3]
LOG_TOOL_EXCEPTIONS = Path("services/web/query/ai_assistant/exceptions.py")
PRODUCTION_SOURCE_DIRECTORIES = ("api", "apps", "blueking", "core", "services")


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
    """字段引用只允许既有查询白名单或 extend_data 子路径。"""

    def test_standard_field_without_keys_is_allowed(self):
        field = LogFieldRef(raw_name="username", field_type="string")

        self.assertEqual(field.model_dump(), {"raw_name": "username", "keys": [], "field_type": "string"})

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

    def test_extend_data_supports_empty_and_multilevel_keys(self):
        container = LogFieldRef(raw_name="extend_data")
        nested = LogFieldRef(raw_name="extend_data", keys=["ticket", "detail", "id"])

        self.assertEqual(container.keys, [])
        self.assertEqual(nested.keys, ["ticket", "detail", "id"])

    def test_unknown_standard_field_is_rejected(self):
        with self.assertRaises(PydanticValidationError):
            LogFieldRef(raw_name="unknown_column")

    def test_standard_field_cannot_use_nested_keys(self):
        with self.assertRaises(PydanticValidationError):
            LogFieldRef(raw_name="username", keys=["bypass"])

    def test_extend_data_rejects_empty_or_dangerous_keys(self):
        for key in ("", " ", "123field", "中文", "bad-key", "x`y", "x']; SELECT 1; --"):
            with self.subTest(key=key):
                with self.assertRaises(PydanticValidationError):
                    LogFieldRef(raw_name="extend_data", keys=[key])


class TestGetLogFieldMetadataRequest(AIAssistantTestCase):
    """字段探索父路径必须复用安全子路径约束。"""

    def test_parent_keys_reject_unsafe_key(self):
        with self.assertRaises(PydanticValidationError):
            GetLogFieldMetadataRequest(condition=self.make_condition(), parent_keys=["unsafe-key"])


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
