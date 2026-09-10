# -*- coding: utf-8 -*-
"""受控日志明细查询测试。"""

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
from core.exceptions import PermissionException
from services.web.query.ai_assistant.exceptions import (
    LogQueryFailed,
    LogQueryResponseTooLarge,
    LogQueryTimeout,
    SensitiveFieldPermissionDenied,
)
from services.web.query.ai_assistant.log_tools.context import LogQueryContext
from services.web.query.ai_assistant.log_tools.schemas import (
    LogFieldRef,
    LogSortItem,
    SearchLogsRequest,
)
from services.web.query.ai_assistant.log_tools.search import LogDetailSearchService
from services.web.query.ai_assistant.log_tools.sensitive import (
    SensitiveLogFieldPermissionService,
    prepare_sensitive_query_fields,
)
from services.web.query.ai_assistant.schemas import SearchCondition
from tests.base import TestCase
from tests.test_query.test_ai_assistant.base import AIAssistantTestCase

SEARCH_MODULE = "services.web.query.ai_assistant.log_tools.search"


class TestLogDetailSearchService(AIAssistantTestCase):
    """明细查询必须先执行敏感处理，再按请求字段裁剪输出。"""

    def setUp(self):
        super().setUp()
        self.condition = self.make_condition()
        self.context = LogQueryContext(
            username=self.username,
            namespace=self.namespace,
            condition=self.condition,
            table="test_rt.doris",
            conditions=({"field": {"raw_name": "system_id", "keys": []}, "operator": "include", "filters": ["s1"]},),
        )
        self.raw_rows = [
            {
                "system_id": "s1",
                "resource_type_id": "host",
                "action_id": "view",
                "username": "raw-user",
                "start_time": "2026-08-28 10:00:00",
                "extend_data": {"region": "raw-region", "secret": "raw-secret"},
            }
        ]
        self.safe_rows = [
            {
                "system_id": "s1",
                "resource_type_id": "host",
                "action_id": "view",
                "username": "masked-user",
                "start_time": "2026-08-28 10:00:00",
                "extend_data": {"region": "masked-region", "secret": "***"},
            }
        ]
        self.mock_context = self.enterContext(
            mock.patch(f"{SEARCH_MODULE}.LogQueryContextService.build", return_value=self.context)
        )
        self.mock_query = self.enterContext(mock.patch.object(SafeQuerySyncResource, "bulk_request"))
        self.mock_query.return_value = ({"list": self.raw_rows}, {"list": [{"count": 3}]})
        self.mock_parser = self.enterContext(mock.patch(f"{SEARCH_MODULE}.SearchDataParser"))
        self.mock_parser.return_value.parse_data.return_value = self.safe_rows

    def _search(self, **kwargs):
        return LogDetailSearchService.search(
            username=self.username,
            namespace=self.namespace,
            request=SearchLogsRequest(condition=self.condition, **kwargs),
        )

    def test_requested_extend_field_is_desensitized_before_final_projection(self):
        result = self._search(fields=[LogFieldRef(raw_name="extend_data", keys=["region"])])

        self.assertEqual(result.items, ({"extend_data.region": "masked-region"},))
        self.assertEqual(result.columns[0].key, "extend_data.region")
        self.assertEqual(result.columns[0].field.keys, ["region"])
        self.assertNotIn("raw-region", result.model_dump_json())
        self.assertNotIn("raw-secret", result.model_dump_json())
        self.mock_parser.return_value.parse_data.assert_called_once_with(
            self.raw_rows,
            username=self.username,
            system_id=self.target_system_id,
        )

        (requests,), _ = self.mock_query.call_args
        data_sql, count_sql = (item["sql"] for item in requests)
        self.assertIn("`system_id`", data_sql)
        self.assertIn("`resource_type_id`", data_sql)
        self.assertIn("`action_id`", data_sql)
        self.assertIn("`extend_data`", data_sql)
        self.assertNotIn("SELECT *", data_sql)
        self.assertIn("`system_id` IN ('s1')", data_sql)
        self.assertIn("`system_id` IN ('s1')", count_sql)

    def test_query_projection_collapses_json_children_to_their_root(self):
        """最终子路径从脱敏根对象裁剪，Doris 无需重复投影未使用的子路径列。"""

        query_fields = prepare_sensitive_query_fields(
            (
                LogFieldRef(raw_name="extend_data", keys=["region"]),
                LogFieldRef(raw_name="extend_data", keys=["secret"]),
                LogFieldRef(raw_name="extend_data"),
            )
        )

        self.assertEqual(sum(field.raw_name == "extend_data" for field in query_fields), 1)
        self.assertTrue(all(not field.keys for field in query_fields))

    def test_default_compact_columns_and_pagination_do_not_expose_query_details(self):
        self.mock_query.return_value = ({"list": self.raw_rows}, {"list": [{"count": 5}]})

        with mock.patch(f"{SEARCH_MODULE}.time.perf_counter", side_effect=[100.0, 100.125], create=True):
            result = self._search(page=2, page_size=2)

        self.assertEqual(
            [column.key for column in result.columns],
            [
                "start_time",
                "username",
                "system_id",
                "action_id",
                "resource_type_id",
                "instance_id",
                "result_code",
                "extend_data",
                "log",
            ],
        )
        self.assertEqual(result.total, 5)
        self.assertNotIn("total", type(result.pagination).model_fields)
        self.assertEqual(result.pagination.returned_count, 1)
        self.assertTrue(result.pagination.has_more)
        self.assertEqual(result.pagination.page, 2)
        self.assertEqual(result.pagination.page_size, 2)
        serialized = result.model_dump_json()
        self.assertNotIn("test_rt.doris", serialized)
        self.assertNotIn("SELECT", serialized)
        self.assertNotIn("raw-user", serialized)
        self.assertEqual(
            result.query_summary.model_dump(),
            {"took_ms": 125, "executed_at": result.query_summary.executed_at},
        )

    def test_zero_hits_are_a_successful_empty_page(self):
        self.mock_query.return_value = ({"list": []}, {"list": [{"count": 0}]})
        self.mock_parser.return_value.parse_data.side_effect = RuntimeError("sensitive permission unavailable")

        result = self._search(fields=[LogFieldRef(raw_name="username")])

        self.assertEqual(result.items, ())
        self.assertEqual(result.total, 0)
        self.assertEqual(result.pagination.returned_count, 0)
        self.assertFalse(result.pagination.has_more)
        self.mock_parser.return_value.parse_data.assert_not_called()

    def test_has_more_reflects_remaining_rows_without_page_budget(self):
        self.mock_query.return_value = ({"list": self.raw_rows}, {"list": [{"count": 5}]})

        result = self._search(page=2, page_size=2)

        self.assertEqual(result.total, 5)
        self.assertTrue(result.pagination.has_more)

    def test_sort_uses_physical_time_and_checks_sensitive_fields(self):
        """排序字段先鉴权，时间排序复用采集器物理列且不重复补列。"""
        with mock.patch.object(SensitiveLogFieldPermissionService, "ensure_access") as permission:
            self._search(
                sort=[
                    LogSortItem(field=LogFieldRef(raw_name="username")),
                    LogSortItem(field=LogFieldRef(raw_name="start_time"), direction="asc"),
                ]
            )
        permission.assert_called_once_with(
            username=self.username, system_id=self.condition.scope_id, fields={"username", "start_time"}
        )
        sql = self.mock_query.call_args.args[0][0]["sql"]
        self.assertIn("ORDER BY `username` DESC,`dtEventTimeStamp` ASC,`gseIndex` DESC,`iterationIndex` DESC", sql)
        self.mock_query.reset_mock()
        with mock.patch.object(
            SensitiveLogFieldPermissionService, "ensure_access", side_effect=SensitiveFieldPermissionDenied()
        ):
            with self.assertRaises(SensitiveFieldPermissionDenied):
                self._search(sort=[LogSortItem(field=LogFieldRef(raw_name="username"))])
        self.mock_query.assert_not_called()

    def test_sensitive_condition_is_rejected_before_doris_query(self):
        """明细列即使不返回敏感值，也不能通过命中数推断敏感条件。"""

        condition = self.make_condition(
            conditions=[self.make_field_condition(raw_name="extend_data", keys=["identity", "ssn"])]
        )
        self.context.condition.conditions = condition.conditions
        request = SearchLogsRequest(
            condition=condition,
            fields=[LogFieldRef(raw_name="username")],
        )

        with mock.patch.object(
            SensitiveLogFieldPermissionService,
            "ensure_access",
            side_effect=SensitiveFieldPermissionDenied(),
        ) as mock_sensitive_access:
            with self.assertRaises(SensitiveFieldPermissionDenied):
                LogDetailSearchService.search(
                    username=self.username,
                    namespace=self.namespace,
                    request=request,
                )

        mock_sensitive_access.assert_called_once_with(
            username=self.username,
            system_id=self.target_system_id,
            fields={"extend_data.identity.ssn"},
        )
        self.mock_query.assert_not_called()

    def test_system_permission_failure_precedes_sensitive_condition_precheck(self):
        """系统权限失败应保留平台申请信息，且不能继续执行敏感或 Doris 查询。"""

        permission_error = PermissionException(
            action_name="view_system",
            permission={"system_id": self.target_system_id},
            apply_url="https://iam.example/apply",
        )
        self.mock_context.side_effect = permission_error

        with mock.patch.object(SensitiveLogFieldPermissionService, "ensure_access") as mock_sensitive_access:
            with self.assertRaises(PermissionException) as raised:
                self._search(fields=[LogFieldRef(raw_name="username")])

        self.assertIs(raised.exception, permission_error)
        mock_sensitive_access.assert_not_called()
        self.mock_query.assert_not_called()

    def test_sort_is_limited_to_safe_standard_fields(self):
        with mock.patch.object(SensitiveLogFieldPermissionService, "ensure_access"):
            result = self._search(sort=[LogSortItem(field=LogFieldRef(raw_name="start_time"), direction="asc")])

        (requests,), _ = self.mock_query.call_args
        self.assertIn(
            "ORDER BY `dtEventTimeStamp` ASC,`gseIndex` DESC,`iterationIndex` DESC",
            requests[0]["sql"],
        )
        self.assertEqual(result.items[0]["start_time"], "2026-08-28 10:00:00")

    def test_projection_preserves_explicit_null_but_omits_missing_fields(self):
        self.safe_rows = [
            {
                "system_id": "s1",
                "resource_type_id": "host",
                "action_id": "view",
                "username": None,
                "extend_data": {"null_value": None, "empty": "", "zero": 0, "false": False},
            }
        ]
        self.mock_parser.return_value.parse_data.return_value = self.safe_rows

        result = self._search(
            fields=[
                LogFieldRef(raw_name="username"),
                LogFieldRef(raw_name="log"),
                LogFieldRef(raw_name="extend_data", keys=["missing"]),
                LogFieldRef(raw_name="extend_data", keys=["null_value"]),
                LogFieldRef(raw_name="extend_data", keys=["empty"]),
                LogFieldRef(raw_name="extend_data", keys=["zero"]),
                LogFieldRef(raw_name="extend_data", keys=["false"]),
            ]
        )

        self.assertEqual(
            result.items,
            (
                {
                    "username": None,
                    "extend_data.null_value": None,
                    "extend_data.empty": "",
                    "extend_data.zero": 0,
                    "extend_data.false": False,
                },
            ),
        )

    def test_missing_count_response_is_mapped_without_exposing_details(self):
        for count_response in ({}, {"list": []}, {"list": [{}]}):
            with self.subTest(count_response=count_response):
                self.mock_query.return_value = ({"list": self.raw_rows}, count_response)

                with self.assertRaises(LogQueryFailed) as raised:
                    self._search()

                self.assertNotIn("count", str(raised.exception).lower())

    def test_invalid_count_value_is_mapped_without_exposing_details(self):
        self.mock_query.return_value = ({"list": self.raw_rows}, {"list": [{"count": "invalid"}]})

        with self.assertRaises(LogQueryFailed) as raised:
            self._search()

        self.assertNotIn("invalid", str(raised.exception).lower())

    def test_count_only_accepts_non_negative_integer_or_decimal_string(self):
        for invalid_count in (True, -1, 1.0, -0.1, "", "-1", "1.0", None):
            with self.subTest(invalid_count=invalid_count):
                self.mock_query.return_value = (
                    {"list": self.raw_rows},
                    {"list": [{"count": invalid_count}]},
                )

                with self.assertRaises(LogQueryFailed):
                    self._search()

        for valid_count, expected_total in ((0, 0), (12, 12), ("012", 12)):
            with self.subTest(valid_count=valid_count):
                self.mock_query.return_value = (
                    {"list": []},
                    {"list": [{"count": valid_count}]},
                )

                result = self._search(fields=[LogFieldRef(raw_name="username")])

                self.assertEqual(result.total, expected_total)

    def test_api_timeout_and_controlled_errors_follow_task_three_mapping(self):
        timeout = APIRequestError(result="gateway failed")
        timeout.__cause__ = RequestsTimeout("upstream timeout")
        self.mock_query.side_effect = timeout
        with self.assertRaises(LogQueryTimeout) as raised:
            self._search()
        self.assertIs(raised.exception.__cause__, timeout)

        controlled = LogQueryTimeout()
        self.mock_query.side_effect = controlled
        with self.assertRaises(LogQueryTimeout) as raised:
            self._search()
        self.assertIs(raised.exception, controlled)

    def test_bypassed_sort_validation_is_rejected_before_context_or_doris(self):
        unsafe_field = LogFieldRef(raw_name="extend_data", keys=["duration"])
        unsafe_sort = LogSortItem.model_construct(field=unsafe_field, direction="asc")
        request = SearchLogsRequest.model_construct(
            condition=self.condition,
            fields=[LogFieldRef(raw_name="username")],
            sort=[unsafe_sort],
            page=1,
            page_size=20,
        )

        with self.assertRaises(PydanticValidationError):
            LogDetailSearchService.search(username=self.username, namespace=self.namespace, request=request)

        self.mock_context.assert_not_called()
        self.mock_query.assert_not_called()

    def test_bypassed_literal_dot_key_is_rejected_before_context_or_doris(self):
        unsafe_field = LogFieldRef.model_construct(raw_name="extend_data", keys=["a.b"], field_type=None)
        request = SearchLogsRequest.model_construct(
            condition=self.condition,
            fields=[unsafe_field],
            sort=[],
            page=1,
            page_size=20,
        )

        with self.assertRaises(PydanticValidationError):
            LogDetailSearchService.search(username=self.username, namespace=self.namespace, request=request)

        self.mock_context.assert_not_called()
        self.mock_query.assert_not_called()

    def test_duplicate_sort_fields_are_rejected_before_context_or_doris(self):
        sort_field = LogFieldRef(raw_name="start_time")
        for directions in (("asc", "asc"), ("asc", "desc")):
            with self.subTest(directions=directions):
                request = SearchLogsRequest.model_construct(
                    condition=self.condition,
                    fields=[LogFieldRef(raw_name="username")],
                    sort=[
                        LogSortItem.model_construct(field=sort_field, direction=directions[0]),
                        LogSortItem.model_construct(field=sort_field, direction=directions[1]),
                    ],
                    page=1,
                    page_size=20,
                )

                with self.assertRaises(PydanticValidationError):
                    LogDetailSearchService.search(username=self.username, namespace=self.namespace, request=request)

        self.mock_context.assert_not_called()
        self.mock_query.assert_not_called()

    def test_response_byte_budget_rejects_large_log_even_when_environment_raises_limit(self):
        self.safe_rows[0]["log"] = "x" * (1024 * 1024 + 1)

        with override_settings(AI_LOG_SEARCH_RESPONSE_MAX_BYTES=2 * 1024 * 1024):
            with self.assertRaises(LogQueryResponseTooLarge) as raised:
                self._search(fields=[LogFieldRef(raw_name="log")])

        self.assertNotIn("x" * 128, str(raised.exception))

    def test_response_byte_budget_rejects_large_json_object_without_changing_its_type(self):
        self.safe_rows[0]["extend_data"] = {"payload": "x" * (1024 * 1024 + 1)}

        with self.assertRaises(LogQueryResponseTooLarge):
            self._search(fields=[LogFieldRef(raw_name="extend_data")])


class TestSearchLogsRequest(AIAssistantTestCase):
    """协议在进入 Context 或 Doris 前拒绝越界和非白名单字段。"""

    def test_page_is_not_limited_and_scalar_sort_is_supported(self):
        request = SearchLogsRequest(
            condition=self.make_condition(), page=101, sort=[LogSortItem(field=LogFieldRef(raw_name="username"))]
        )
        self.assertEqual(request.page, 101)

    def test_request_rejects_protocol_and_sort_boundaries(self):
        condition = self.make_condition()
        with self.assertRaises(PydanticValidationError):
            SearchLogsRequest(condition=condition, fields=[])
        with self.assertRaises(PydanticValidationError):
            SearchLogsRequest(
                condition=condition,
                fields=[LogFieldRef(raw_name="username"), LogFieldRef(raw_name="username")],
            )
        with self.assertRaises(PydanticValidationError):
            SearchLogsRequest(condition=condition, page=0)
        with self.assertRaises(PydanticValidationError):
            SearchLogsRequest(condition=condition, page_size=101)
        with self.assertRaises(PydanticValidationError):
            SearchLogsRequest(condition=condition, fields=[LogFieldRef(raw_name="username")] * 21)
        with self.assertRaises(PydanticValidationError):
            SearchLogsRequest(
                condition=condition,
                sort=[LogSortItem(field=LogFieldRef(raw_name="start_time"))] * 4,
            )
        for directions in (("asc", "asc"), ("asc", "desc")):
            with self.subTest(directions=directions):
                with self.assertRaises(PydanticValidationError):
                    SearchLogsRequest(
                        condition=condition,
                        sort=[
                            LogSortItem(field=LogFieldRef(raw_name="start_time"), direction=directions[0]),
                            LogSortItem(field=LogFieldRef(raw_name="start_time"), direction=directions[1]),
                        ],
                    )
        with self.assertRaises(PydanticValidationError):
            LogSortItem(field=LogFieldRef(raw_name="extend_data", keys=["region"]))
        for raw_name in ("extend_data", "snapshot_user_info"):
            with self.subTest(raw_name=raw_name):
                with self.assertRaises(PydanticValidationError):
                    LogSortItem(field=LogFieldRef(raw_name=raw_name))
        with self.assertRaises(PydanticValidationError):
            LogFieldRef(raw_name="username; DROP TABLE audit")

    @override_settings(
        AI_LOG_SEARCH_MAX_FIELDS=1,
        AI_LOG_SEARCH_MAX_SORT_FIELDS=0,
        AI_LOG_SEARCH_MAX_PAGE_SIZE=20,
    )
    def test_runtime_limits_can_be_tightened_by_environment_settings(self):
        condition = self.make_condition()
        with self.assertRaises(PydanticValidationError):
            SearchLogsRequest(
                condition=condition, fields=[LogFieldRef(raw_name="username"), LogFieldRef(raw_name="log")]
            )
        with self.assertRaises(PydanticValidationError):
            SearchLogsRequest(condition=condition, sort=[LogSortItem(field=LogFieldRef(raw_name="start_time"))])
        self.assertEqual(SearchLogsRequest(condition=condition, page=101).page, 101)
        with self.assertRaises(PydanticValidationError):
            SearchLogsRequest(condition=condition, page_size=21)
        self.assertEqual(SearchLogsRequest(condition=condition).page_size, 20)

    @override_settings(
        AI_LOG_SEARCH_MAX_FIELDS=999,
        AI_LOG_SEARCH_MAX_SORT_FIELDS=999,
        AI_LOG_SEARCH_MAX_PAGE_SIZE=999,
    )
    def test_runtime_limits_cannot_expand_frozen_protocol_upper_bounds(self):
        condition = self.make_condition()
        with self.assertRaises(PydanticValidationError):
            SearchLogsRequest(condition=condition, fields=[LogFieldRef(raw_name="username")] * 21)
        with self.assertRaises(PydanticValidationError):
            SearchLogsRequest(condition=condition, sort=[LogSortItem(field=LogFieldRef(raw_name="start_time"))] * 4)
        self.assertEqual(SearchLogsRequest(condition=condition, page=1001).page, 1001)
        with self.assertRaises(PydanticValidationError):
            SearchLogsRequest(condition=condition, page_size=101)


class TestLogDetailSearchSensitiveProjection(TestCase):
    """真实脱敏器必须在 JSON 子字段最终投影前处理完整原始行。"""

    username = "tester"
    target_system_id = "bk_log"

    @override_settings(IAM_PERMISSION_BACKEND="v3")
    @mock.patch("services.web.query.search_data.PermissionService")
    @mock.patch.object(SafeQuerySyncResource, "bulk_request")
    @mock.patch(f"{SEARCH_MODULE}.LogQueryContextService.build")
    def test_nested_sensitive_value_cannot_bypass_desensitization_by_projection(
        self, mock_context, mock_query, mock_permission_service
    ):
        condition = SearchCondition(
            scope_type="system",
            scope_id=self.target_system_id,
            start_time="2026-08-13T00:00:00+08:00",
            end_time="2026-08-14T00:00:00+08:00",
        )
        mock_context.return_value = LogQueryContext(
            username=self.username,
            namespace=self.namespace,
            condition=condition,
            table="test_rt.doris",
            conditions=(),
        )
        sensitive_object = SensitiveObject.objects.create(
            name="extend-secret",
            system_id=self.target_system_id,
            resource_type=SensitiveResourceTypeEnum.RESOURCE.value,
            resource_id="host",
            fields=[{"field_name": "extend_data.secret"}],
        )
        mock_permission_service.return_value.get_sensitive_object_permissions.return_value = {
            str(sensitive_object.id): False
        }
        mock_query.return_value = (
            {
                "list": [
                    {
                        "system_id": self.target_system_id,
                        "resource_type_id": "host",
                        "action_id": "view",
                        "extend_data": {"secret": "raw-secret", "region": "sh"},
                    }
                ]
            },
            {"list": [{"count": 1}]},
        )

        result = LogDetailSearchService.search(
            username=self.username,
            namespace=self.namespace,
            request=SearchLogsRequest(
                condition=condition,
                fields=[LogFieldRef(raw_name="extend_data", keys=["secret"])],
            ),
        )

        self.assertEqual(result.items, ({"extend_data.secret": SENSITIVE_REPLACE_VALUE},))
        self.assertNotIn("raw-secret", result.model_dump_json())
        mock_permission_service.assert_called_once_with(username=self.username)
        mock_permission_service.return_value.get_sensitive_object_permissions.assert_called_once_with(
            [sensitive_object.id]
        )

    @mock.patch.object(SafeQuerySyncResource, "bulk_request")
    @mock.patch(f"{SEARCH_MODULE}.LogQueryContextService.build")
    def test_default_columns_do_not_expose_raw_log_for_private_rule(self, mock_context, mock_query):
        condition = SearchCondition(
            scope_id=self.target_system_id,
            start_time="2026-08-13T00:00:00+08:00",
            end_time="2026-08-14T00:00:00+08:00",
        )
        mock_context.return_value = LogQueryContext(
            username=self.username,
            namespace=self.namespace,
            condition=condition,
            table="test_rt.doris",
            conditions=(),
        )
        SensitiveObject._objects.create(
            name="private secret",
            system_id=self.target_system_id,
            resource_type=SensitiveResourceTypeEnum.RESOURCE.value,
            resource_id="host",
            fields=[{"field_name": "extend_data.secret"}],
            is_private=True,
        )
        mock_query.return_value = (
            {
                "list": [
                    {
                        "system_id": self.target_system_id,
                        "resource_type_id": "host",
                        "action_id": "view",
                        "extend_data": {"secret": "raw-secret", "public": "visible"},
                        "log": "payload raw-secret",
                    }
                ]
            },
            {"list": [{"count": 1}]},
        )

        result = LogDetailSearchService.search(
            username=self.username,
            namespace=self.namespace,
            request=SearchLogsRequest(condition=condition),
        )

        self.assertEqual(result.items[0]["extend_data"], {"public": "visible"})
        self.assertEqual(result.items[0]["log"], SENSITIVE_REPLACE_VALUE)
        self.assertNotIn("raw-secret", result.model_dump_json())

    @mock.patch("services.web.query.ai_assistant.log_tools.sensitive.PermissionService")
    @mock.patch.object(SafeQuerySyncResource, "bulk_request")
    @mock.patch(f"{SEARCH_MODULE}.LogQueryContextService.build")
    def test_nested_sensitive_condition_is_rejected_before_query(
        self, mock_context, mock_query, mock_permission_service
    ):
        condition = SearchCondition(
            scope_id=self.target_system_id,
            start_time="2026-08-13T00:00:00+08:00",
            end_time="2026-08-14T00:00:00+08:00",
            conditions=[
                {
                    "field": {"raw_name": "extend_data", "keys": ["identity", "ssn"]},
                    "operator": "eq",
                    "filters": ["candidate"],
                }
            ],
        )
        mock_context.return_value = LogQueryContext(
            username=self.username,
            namespace=self.namespace,
            condition=condition,
            table="test_rt.doris",
            conditions=(),
        )
        sensitive_object = SensitiveObject.objects.create(
            name="identity",
            system_id=self.target_system_id,
            resource_type=SensitiveResourceTypeEnum.RESOURCE.value,
            resource_id="host",
            fields=[{"field_name": "extend_data.identity"}],
        )
        mock_permission_service.return_value.get_sensitive_object_permissions.return_value = {
            str(sensitive_object.id): False
        }

        with self.assertRaises(SensitiveFieldPermissionDenied):
            LogDetailSearchService.search(
                username=self.username,
                namespace=self.namespace,
                request=SearchLogsRequest(
                    condition=condition,
                    fields=[LogFieldRef(raw_name="username")],
                ),
            )

        mock_query.assert_not_called()

    @mock.patch("services.web.query.ai_assistant.log_tools.sensitive.PermissionService")
    @mock.patch.object(SafeQuerySyncResource, "bulk_request")
    @mock.patch(f"{SEARCH_MODULE}.LogQueryContextService.build")
    def test_global_user_sensitive_condition_is_rejected_before_query(
        self, mock_context, mock_query, mock_permission_service
    ):
        condition = SearchCondition(
            scope_id=self.target_system_id,
            start_time="2026-08-13T00:00:00+08:00",
            end_time="2026-08-14T00:00:00+08:00",
            conditions=[
                {
                    "field": {"raw_name": "username"},
                    "operator": "eq",
                    "filters": ["candidate"],
                }
            ],
        )
        mock_context.return_value = LogQueryContext(
            username=self.username,
            namespace=self.namespace,
            condition=condition,
            table="test_rt.doris",
            conditions=(),
        )
        sensitive_object = SensitiveObject.objects.create(
            name="global user",
            system_id=SensitiveUserData.SYSTEM_ID,
            resource_type=SensitiveResourceTypeEnum.RESOURCE.value,
            resource_id=SensitiveUserData.RESOURCE_ID,
            fields=[{"field_name": "username"}],
        )
        mock_permission_service.return_value.get_sensitive_object_permissions.return_value = {
            str(sensitive_object.id): False
        }

        with self.assertRaises(SensitiveFieldPermissionDenied):
            LogDetailSearchService.search(
                username=self.username,
                namespace=self.namespace,
                request=SearchLogsRequest(
                    condition=condition,
                    fields=[LogFieldRef(raw_name="action_id")],
                ),
            )

        mock_query.assert_not_called()

    @mock.patch("services.web.query.ai_assistant.log_tools.sensitive.PermissionService")
    @mock.patch.object(SafeQuerySyncResource, "bulk_request")
    @mock.patch(f"{SEARCH_MODULE}.LogQueryContextService.build")
    def test_raw_log_condition_is_rejected_when_any_sensitive_rule_is_denied(
        self, mock_context, mock_query, mock_permission_service
    ):
        """原始日志包含未脱敏正文，不能通过命中数旁路推断敏感值。"""

        condition = SearchCondition(
            scope_id=self.target_system_id,
            start_time="2026-08-13T00:00:00+08:00",
            end_time="2026-08-14T00:00:00+08:00",
            conditions=[
                {
                    "field": {"raw_name": "log", "keys": []},
                    "operator": "match_any",
                    "filters": ["secret-token"],
                }
            ],
        )
        mock_context.return_value = LogQueryContext(
            username=self.username,
            namespace=self.namespace,
            condition=condition,
            table="test_rt.doris",
            conditions=(),
        )
        sensitive_object = SensitiveObject.objects.create(
            name="raw-log-secret",
            system_id=self.target_system_id,
            resource_type=SensitiveResourceTypeEnum.RESOURCE.value,
            resource_id="host",
            fields=[{"field_name": "extend_data.secret"}],
        )
        mock_permission_service.return_value.get_sensitive_object_permissions.return_value = {
            str(sensitive_object.id): False
        }

        with self.assertRaises(SensitiveFieldPermissionDenied):
            LogDetailSearchService.search(
                username=self.username,
                namespace=self.namespace,
                request=SearchLogsRequest(
                    condition=condition,
                    fields=[LogFieldRef(raw_name="username")],
                ),
            )

        mock_query.assert_not_called()
