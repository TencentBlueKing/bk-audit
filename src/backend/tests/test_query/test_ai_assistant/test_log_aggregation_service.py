"""验证聚合帧、敏感规则及结果完整性；查询上下文、IAM和远端Doris响应使用替身。"""
import json
from unittest import mock

from bk_resource.exceptions import APIRequestError
from django.test import override_settings
from requests.exceptions import Timeout as RequestsTimeout

from api.bk_base.default import SafeQuerySyncResource
from apps.meta.constants import SensitiveResourceTypeEnum, SensitiveUserData
from apps.meta.models import SensitiveObject
from core.exceptions import PermissionException
from services.web.query.ai_assistant.exceptions import (
    LogQueryFailed,
    LogQueryTimeout,
    SensitiveFieldPermissionDenied,
    StatisticsBudgetExceeded,
    StatisticsResponseTooLarge,
    UnsupportedFieldType,
)
from services.web.query.ai_assistant.log_tools.aggregation import LogAggregationService
from services.web.query.ai_assistant.log_tools.context import LogQueryContext
from services.web.query.ai_assistant.schemas import Condition, ConditionField
from tests.base import TestCase
from tests.test_query.test_ai_assistant.test_log_aggregation_sql import make_request

AGGREGATION_MODULE = "services.web.query.ai_assistant.log_tools.aggregation"


def frames():
    """手算GET6/OTHER3/MISSING1；OTHER平均值来自2+4+12三条原记录。"""
    return [
        {"frame": "META", "n": "10", "a": "3", "b": "3", "c": "1", "d": "0", "e": "0"},
        {"frame": "GROUP", "key": "1", "kind": "VALUE", "n": "6", "d0_type": "string", "d0_json": '"GET"'},
        {"frame": "GROUP", "key": "2", "kind": "OTHER", "n": "3", "d0_type": None, "d0_json": None},
        {"frame": "GROUP", "key": "3", "kind": "MISSING", "n": "1", "d0_type": None, "d0_json": None},
        {"frame": "ROW", "key": "1", "n": "6", "m0": "6", "m1": "1.5"},
        {"frame": "ROW", "key": "2", "n": "3", "m0": "3", "m1": "6"},
        {"frame": "ROW", "key": "3", "n": "1", "m0": "1", "m1": None},
        {"frame": "QUALITY", "key": "1", "n": "9", "a": "8", "b": "1"},
    ]


class TestLogAggregationService(TestCase):
    username = "tester"
    namespace = "default"
    target_system_id = "s1"

    def setUp(self):
        super().setUp()
        self.condition = make_request().condition
        self.context = LogQueryContext(
            username=self.username,
            namespace=self.namespace,
            condition=self.condition,
            table="test_rt.doris",
            conditions=({"field": {"raw_name": "system_id", "keys": []}, "operator": "include", "filters": ["s1"]},),
        )
        self.mock_context = self.enterContext(
            mock.patch(f"{AGGREGATION_MODULE}.LogQueryContextService.build", return_value=self.context)
        )
        self.mock_query = self.enterContext(
            mock.patch.object(SafeQuerySyncResource, "bulk_request", return_value=({"list": frames()},))
        )
        self.mock_permissions = self.enterContext(
            mock.patch("services.web.query.ai_assistant.log_tools.sensitive.PermissionService")
        )

    def _aggregate(self, **kwargs):
        payload = dict(
            condition=self.condition,
            metrics=[
                {"id": "events", "type": "COUNT"},
                {
                    "id": "average",
                    "type": "AVG",
                    "field": {"raw_name": "extend_data", "keys": ["duration"]},
                    "value_type": "DOUBLE",
                },
            ],
        )
        payload.update(kwargs)
        return LogAggregationService.aggregate(
            username=self.username, namespace=self.namespace, request=make_request(**payload)
        )

    def make_condition(self, **kwargs):
        return make_request().condition.model_copy(update=kwargs)

    @staticmethod
    def make_field_condition(**kwargs):
        return Condition(field=ConditionField(raw_name=kwargs.pop("raw_name"), keys=kwargs.pop("keys")), **kwargs)

    def test_complete_groups_quality_and_original_other_average(self):
        with mock.patch(f"{AGGREGATION_MODULE}.time.perf_counter", side_effect=[20.0, 20.125]):
            result = self._aggregate()
        self.assertEqual([g.count for g in result.groups], [6, 3, 1])
        self.assertEqual([g.kind for g in result.groups], ["VALUE", "OTHER", "MISSING"])
        self.assertEqual([g.ratio for g in result.groups], [0.6, 0.3, 0.1])
        self.assertEqual(result.groups[0].values[0].value, "GET")
        self.assertEqual(result.rows[1]["average"], 6)
        self.assertEqual(result.rows[1]["log_count"], 3)
        self.assertEqual(result.query_summary.total_count, 10)
        self.assertEqual(result.query_summary.returned_count, 3)
        self.assertTrue(result.query_summary.complete)
        self.assertTrue(result.query_summary.has_other)
        self.assertEqual(result.query_summary.took_ms, 125)
        self.assertEqual(
            result.data_quality[0].model_dump(),
            dict(metric_id="average", present_count=9, converted_count=8, conversion_failed_count=1),
        )
        self.assertNotIn("test_rt", result.model_dump_json())
        requests = self.mock_query.call_args.args[0]
        self.assertEqual(len(requests), 1)
        self.assertIn("FROM mapped GROUP BY group_key", requests[0]["sql"])

    def test_missing_truncated_duplicate_or_inconsistent_frames_fail_closed(self):
        cases = []
        for index in (0, 1, 4, 7):
            data = frames()
            data.pop(index)
            cases.append(data)
        cases.append(frames() + [frames()[1]])
        for index, key, value in [
            (0, "n", "11"),
            (0, "a", "2"),
            (0, "b", "4"),
            (0, "c", "0"),
            (1, "n", "7"),
            (4, "n", "5"),
            (4, "m0", "5"),
            (4, "m1", "NaN"),
            (7, "a", "9"),
            (7, "n", "11"),
            (1, "key", "2"),
            (1, "d0_json", 1),
            (1, "d0_type", "array"),
        ]:
            data = frames()
            data[index][key] = value
            cases.append(data)
        for data in cases:
            with self.subTest(data=data):
                self.mock_query.return_value = ({"list": data},)
                with self.assertRaises(LogQueryFailed):
                    self._aggregate()

    def test_full_scope_invalid_type_or_unsafe_number_rejects_even_outside_top_n(self):
        for key in ("d", "e"):
            data = frames()
            data[0][key] = "1"
            self.mock_query.return_value = ({"list": data[:1]},)
            with self.assertRaises(UnsupportedFieldType):
                self._aggregate()

    def test_empty_categories_and_empty_global_all(self):
        self.mock_query.return_value = (
            {"list": [{"frame": "META", "n": "0", "a": "0", "b": "0", "c": "0", "d": "0", "e": "0"}]},
        )
        result = self._aggregate(metrics=[{"id": "events", "type": "COUNT"}])
        self.assertEqual(result.groups, ())
        self.assertEqual(result.rows, ())
        self.mock_query.return_value = (
            {
                "list": [
                    {"frame": "META", "n": "0", "a": "1", "b": "1", "c": "0", "d": "0", "e": "0"},
                    {"frame": "GROUP", "key": "1", "kind": "ALL", "n": "0"},
                    {"frame": "ROW", "key": "1", "n": "0", "m0": "0"},
                ]
            },
        )
        result = self._aggregate(dimensions=[], metrics=[{"id": "events", "type": "COUNT"}])
        self.assertEqual(result.groups[0].kind, "ALL")
        self.assertIsNone(result.groups[0].ratio)
        self.assertEqual(result.rows[0]["events"], 0)

    def test_typed_values_survive_transport_and_blank_remains_value(self):
        for kind, text, want in [
            ("number", "1", 1),
            ("string", '"1"', "1"),
            ("boolean", "true", True),
            ("string", '""', ""),
            ("number", "1e-20", 1e-20),
        ]:
            data = frames()
            data[1]["d0_type"] = kind
            data[1]["d0_json"] = text
            self.mock_query.return_value = ({"list": data},)
            result = self._aggregate()
            self.assertEqual(result.groups[0].values[0].value, want)
            self.assertIs(type(result.groups[0].values[0].value), type(want))

    @override_settings(AI_LOG_AGGREGATION_RESPONSE_MAX_BYTES=100)
    def test_complete_response_uses_statistics_byte_budget(self):
        with self.assertRaises(StatisticsResponseTooLarge):
            self._aggregate()

    def test_system_permission_error_is_preserved(self):
        error = PermissionException(action_name="view_system", permission={"system_id": "s1"})
        self.mock_context.side_effect = error
        with self.assertRaises(PermissionException):
            self._aggregate()
        self.mock_query.assert_not_called()

    def test_timeout_maps_without_raw_backend_details(self):
        self.mock_query.side_effect = TimeoutError("secret sql")
        with self.assertRaises(LogQueryTimeout) as raised:
            self._aggregate()
        self.assertNotIn("secret", str(raised.exception))

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
        self.mock_query.assert_not_called()

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
        self.mock_query.assert_not_called()

    def test_count_star_condition_field_is_included_in_sensitive_precheck(self):
        sensitive = SensitiveObject.objects.create(
            name="sensitive condition",
            system_id=self.target_system_id,
            resource_type=SensitiveResourceTypeEnum.RESOURCE.value,
            resource_id="host",
            fields=[{"field_name": "extend_data.ssn"}],
        )
        self.mock_permissions.return_value.get_sensitive_object_permissions.return_value = {str(sensitive.id): False}
        self.condition = self.make_condition(
            conditions=[
                self.make_field_condition(raw_name="extend_data", keys=["ssn"], operator="eq", filters=["candidate"])
            ]
        )
        self.context.condition.conditions = self.condition.conditions
        self.mock_query.return_value = ({"list": []},)

        with self.assertRaises(SensitiveFieldPermissionDenied):
            self._aggregate(dimensions=[], metrics=[{"id": "count", "type": "COUNT"}], **{})

        self.mock_query.assert_not_called()

    def test_sensitive_path_matches_ancestors_and_descendants_by_segments(self):
        cases = (
            ("extend_data.credentials", ["credentials", "token"]),
            ("extend_data.credentials.token", ["credentials"]),
        )
        for sensitive_path, requested_keys in cases:
            with self.subTest(sensitive_path=sensitive_path, requested_keys=requested_keys):
                SensitiveObject.objects.all().delete()
                sensitive = SensitiveObject.objects.create(
                    name="sensitive nested path",
                    system_id=self.target_system_id,
                    resource_type=SensitiveResourceTypeEnum.RESOURCE.value,
                    resource_id="host",
                    fields=[{"field_name": sensitive_path}],
                )
                self.mock_permissions.return_value.get_sensitive_object_permissions.return_value = {
                    str(sensitive.id): False
                }
                self.mock_query.return_value = ({"list": []},)

                with self.assertRaises(SensitiveFieldPermissionDenied):
                    self._aggregate(
                        dimensions=[
                            {
                                "id": "credential",
                                "type": "FIELD",
                                "field": {"raw_name": "extend_data", "keys": requested_keys},
                            }
                        ],
                        metrics=[{"id": "count", "type": "COUNT"}],
                        **{},
                    )

                self.mock_query.assert_not_called()

    def test_private_sensitive_ancestor_is_rejected_without_permission_lookup(self):
        SensitiveObject.objects.create(
            name="private credential object",
            system_id=self.target_system_id,
            resource_type=SensitiveResourceTypeEnum.RESOURCE.value,
            resource_id="host",
            fields=[{"field_name": "extend_data.credentials"}],
            is_private=True,
        )
        self.mock_query.return_value = ({"list": []},)

        with self.assertRaises(SensitiveFieldPermissionDenied):
            self._aggregate(
                dimensions=[
                    {
                        "id": "token",
                        "type": "FIELD",
                        "field": {"raw_name": "extend_data", "keys": ["credentials", "token"]},
                    }
                ],
                metrics=[{"id": "count", "type": "COUNT"}],
                **{},
            )

        self.mock_permissions.assert_not_called()
        self.mock_query.assert_not_called()

    def test_similar_sensitive_prefix_does_not_hide_accessible_field(self):
        SensitiveObject.objects.create(
            name="other path",
            system_id="s1",
            resource_type=SensitiveResourceTypeEnum.RESOURCE.value,
            resource_id="host",
            fields=[{"field_name": "extend_data.durations"}],
            is_private=True,
        )
        result = self._aggregate()
        self.assertEqual(result.rows[0]["average"], 1.5)
        self.mock_permissions.assert_not_called()

    def test_raw_log_retains_whole_object_sensitive_protection(self):
        SensitiveObject.objects.create(
            name="protected",
            system_id="s1",
            resource_type=SensitiveResourceTypeEnum.RESOURCE.value,
            resource_id="host",
            fields=[{"field_name": "extend_data.secret"}],
            is_private=True,
        )
        with self.assertRaises(SensitiveFieldPermissionDenied):
            self._aggregate(
                dimensions=[{"id": "raw", "type": "FIELD", "field": {"raw_name": "log"}}],
                metrics=[{"id": "events", "type": "COUNT"}],
            )
        self.mock_query.assert_not_called()

    def test_global_sensitive_rule_blocks_dimension_but_not_count_star(self):
        SensitiveObject.objects.create(
            name="global",
            system_id=SensitiveUserData.SYSTEM_ID,
            resource_type=SensitiveResourceTypeEnum.RESOURCE.value,
            resource_id=SensitiveUserData.RESOURCE_ID,
            fields=[{"field_name": "action_id"}],
            is_private=True,
        )
        with self.assertRaises(SensitiveFieldPermissionDenied):
            self._aggregate()
        self.mock_query.assert_not_called()
        self.mock_query.return_value = (
            {
                "list": [
                    {"frame": "META", "n": "0", "a": "1", "b": "1", "c": "0", "d": "0", "e": "0"},
                    {"frame": "GROUP", "key": "1", "kind": "ALL", "n": "0"},
                    {"frame": "ROW", "key": "1", "n": "0", "m0": "0"},
                ]
            },
        )
        result = self._aggregate(dimensions=[], metrics=[{"id": "events", "type": "COUNT"}])
        self.assertEqual(result.rows[0]["events"], 0)

    def test_backend_failure_contract_and_timeout_cause_do_not_leak_sql(self):
        error = APIRequestError(result="gateway error")
        error.__cause__ = RequestsTimeout("secret sql")
        self.mock_query.side_effect = error
        with self.assertRaises(LogQueryTimeout):
            self._aggregate()
        self.mock_query.side_effect = RuntimeError("SELECT secret")
        with self.assertRaises(LogQueryFailed) as raised:
            self._aggregate()
        self.assertNotIn("SELECT secret", str(raised.exception))
        self.mock_query.side_effect = None
        for result in [(), ([],), ({},), ({"list": None},), ({"list": ["bad"]},), ({"list": frames()}, {})]:
            self.mock_query.return_value = result
            with self.assertRaises(LogQueryFailed):
                self._aggregate()

    def test_unexpected_remote_columns_are_not_exposed_or_desensitized(self):
        data = frames()
        data[1]["secret"] = "hidden"
        data[4]["secret"] = "hidden"
        self.mock_query.return_value = ({"list": data},)
        with mock.patch(
            "services.web.query.resources.base.SearchDataParser.parse_data",
            side_effect=AssertionError("no post-query masking"),
        ):
            result = self._aggregate()
        self.assertNotIn("hidden", result.model_dump_json())
        self.assertEqual([c.id for c in result.columns], ["action", "events", "average"])

    def test_exact_utf8_budget_and_chinese_plus_one_byte(self):
        result = self._aggregate()
        result.groups[0].values[0].value = "中"
        result.rows[0]["action"] = "中"
        size = len(result.model_dump_json().encode("utf-8"))
        with override_settings(AI_LOG_AGGREGATION_RESPONSE_MAX_BYTES=size):
            LogAggregationService._ensure_response_within_budget(result)
        with override_settings(AI_LOG_AGGREGATION_RESPONSE_MAX_BYTES=size - 1):
            with self.assertRaises(StatisticsResponseTooLarge):
                LogAggregationService._ensure_response_within_budget(result)

    def test_top_n_500_returns_all_500_selected_plus_synthetic_groups(self):
        data = [{"frame": "META", "n": "502", "a": "502", "b": "502", "c": "0", "d": "0", "e": "0"}]
        for key in range(1, 503):
            data.append(
                {
                    "frame": "GROUP",
                    "key": str(key),
                    "kind": "VALUE" if key <= 500 else ("OTHER" if key == 501 else "MISSING"),
                    "n": "1",
                    "d0_type": "string" if key <= 500 else None,
                    "d0_json": json.dumps(str(key)) if key <= 500 else None,
                }
            )
            data.append({"frame": "ROW", "key": str(key), "n": "1", "m0": "1"})
        self.mock_query.return_value = ({"list": data},)
        result = self._aggregate(top_n=500, metrics=[{"id": "events", "type": "COUNT"}])
        self.assertEqual(len(result.groups), 502)
        self.assertEqual(len(result.rows), 502)
        self.assertEqual(result.query_summary.total_count, 502)

    def test_nonadditive_distinct_and_avg_are_not_summed_across_groups(self):
        data = frames()
        data[4]["m0"] = "2"
        data[5]["m0"] = "2"
        data[6]["m0"] = "0"
        self.mock_query.return_value = ({"list": data},)
        result = self._aggregate(
            metrics=[
                {"id": "unique", "type": "DISTINCT_COUNT", "field": {"raw_name": "username"}},
                {
                    "id": "average",
                    "type": "AVG",
                    "field": {"raw_name": "extend_data", "keys": ["duration"]},
                    "value_type": "DOUBLE",
                },
            ]
        )
        self.assertEqual([r["unique"] for r in result.rows], [2, 2, 0])
        self.assertEqual([r["average"] for r in result.rows], [1.5, 6, None])

    def test_duplicate_typed_tuple_and_number_output_collisions_reject(self):
        data = frames()
        data[0].update(n="11", a="4", b="4")
        data[2]["key"] = "3"
        data[3]["key"] = "4"
        data[5]["key"] = "3"
        data[6]["key"] = "4"
        data.extend(
            [
                {"frame": "GROUP", "key": "2", "kind": "VALUE", "n": "1", "d0_type": "number", "d0_json": "1.0"},
                {"frame": "ROW", "key": "2", "n": "1", "m0": "1", "m1": "1"},
            ]
        )
        data[1]["d0_type"] = "number"
        data[1]["d0_json"] = "1"
        self.mock_query.return_value = ({"list": data},)
        with self.assertRaises(LogQueryFailed):
            self._aggregate(top_n=2)

    def test_two_dimensions_keep_value_order_and_any_missing_has_no_values(self):
        data = frames()
        data[1].update(d1_type="boolean", d1_json="true")
        for index in (2, 3):
            data[index].update(d1_type=None, d1_json=None)
        self.mock_query.return_value = ({"list": data},)
        result = self._aggregate(
            dimensions=[
                {"id": "action", "type": "FIELD", "field": {"raw_name": "action_id"}},
                {"id": "flag", "type": "FIELD", "field": {"raw_name": "extend_data", "keys": ["flag"]}},
            ]
        )
        self.assertEqual(
            [(v.dimension_id, v.value) for v in result.groups[0].values], [("action", "GET"), ("flag", True)]
        )
        self.assertEqual(result.groups[2].values, ())
        self.assertEqual(result.rows[2]["flag"], None)

    def _time_dimensions(self, interval="HOUR", category=True):
        """时间列放首位，验证内部类别索引不会误用请求维度下标。"""
        dimensions = [{"id": "hour", "type": "TIME_BUCKET", "field": {"raw_name": "start_time"}, "interval": interval}]
        if category:
            dimensions.append({"id": "action", "type": "FIELD", "field": {"raw_name": "action_id"}})
        return dimensions

    def test_time_only_sensitive_dimension_denies_before_any_doris_query(self):
        """TIME_BUCKET 也暴露字段值，私密或缺少敏感权限时不能发出预检。"""
        for private in (True, False):
            with self.subTest(private=private):
                rule = SensitiveObject.objects.create(
                    name="protected time",
                    system_id="s1",
                    resource_type=SensitiveResourceTypeEnum.RESOURCE.value,
                    resource_id="host",
                    fields=[{"field_name": "start_time"}],
                    is_private=private,
                )
                self.mock_permissions.return_value.get_sensitive_object_permissions.return_value = {}
                self.mock_query.reset_mock()
                self.mock_query.side_effect = [
                    ({"list": [{"group_count": "1", "invalid_type_count": "0", "invalid_number_count": "0"}]},),
                    (
                        {
                            "list": [
                                {"frame": "META", "n": "1", "a": "1", "b": "1", "c": "0", "d": "0", "e": "0"},
                                {"frame": "GROUP", "key": "1", "kind": "ALL", "n": "1"},
                                {"frame": "ROW", "key": "1", "bucket": "0", "n": "1", "m0": "1"},
                            ]
                        },
                    ),
                ]
                try:
                    with self.assertRaises(SensitiveFieldPermissionDenied):
                        self._aggregate(
                            dimensions=self._time_dimensions(category=False),
                            metrics=[{"id": "events", "type": "COUNT"}],
                        )
                    self.mock_query.assert_not_called()
                finally:
                    rule.delete()

    def test_sparse_time_rows_fill_axis_and_keep_global_groups(self):
        data = frames()
        for row in data:
            if row["frame"] == "ROW":
                row["bucket"] = "0"
        self.mock_query.side_effect = [
            ({"list": [{"group_count": "3", "invalid_type_count": "0", "invalid_number_count": "0"}]},),
            ({"list": data},),
        ]
        result = self._aggregate(dimensions=self._time_dimensions())
        self.assertEqual(len(result.rows), 75)
        self.assertEqual([g.count for g in result.groups], [6, 3, 1])
        self.assertEqual(result.rows[0]["hour"], "2026-08-13T00:00:00+08:00")
        self.assertEqual(result.rows[24]["hour"], "2026-08-14T00:00:00+08:00")
        self.assertEqual(result.rows[1]["events"], 0)
        self.assertIsNone(result.rows[1]["average"])
        self.assertEqual(result.columns[0].effective_time_interval, "HOUR")
        self.assertEqual(result.query_summary.requested_interval, "HOUR")
        self.assertEqual(result.groups[0].values[0].dimension_id, "action")

    def test_empty_pure_time_all_has_axis_but_category_empty_has_no_rows(self):
        for category, groups, group_frames in [
            (True, "0", []),
            (False, "1", [{"frame": "GROUP", "key": "1", "kind": "ALL", "n": "0"}]),
        ]:
            with self.subTest(category=category):
                data = [{"frame": "META", "n": "0", "a": groups, "b": "0", "c": "0", "d": "0", "e": "0"}] + group_frames
                self.mock_query.side_effect = [
                    ({"list": [{"group_count": groups, "invalid_type_count": "0", "invalid_number_count": "0"}]},),
                    ({"list": data},),
                ]
                result = self._aggregate(
                    dimensions=self._time_dimensions(category=category), metrics=[{"id": "events", "type": "COUNT"}]
                )
                self.assertEqual(len(result.rows), 0 if category else 25)
                if not category:
                    self.assertEqual([row["events"] for row in result.rows], [0] * 25)

    def test_distinct_count_fills_empty_time_buckets_with_zero(self):
        """纯时序及类别时序空桶的去重计数为零，与有事件桶保留的引擎结果一致。"""
        for category, total in ((False, 0), (False, 2), (True, 2)):
            with self.subTest(category=category, total=total):
                group = {"frame": "GROUP", "key": "1", "kind": "VALUE" if category else "ALL", "n": str(total)}
                if category:
                    group.update(d0_type="string", d0_json='"GET"')
                data = [
                    {
                        "frame": "META",
                        "n": str(total),
                        "a": "1",
                        "b": "1" if total else "0",
                        "c": "0",
                        "d": "0",
                        "e": "0",
                    },
                    group,
                ]
                if total:
                    data.append({"frame": "ROW", "key": "1", "bucket": "0", "n": "2", "m0": "2", "m1": "1"})
                self.mock_query.side_effect = [
                    ({"list": [{"group_count": "1", "invalid_type_count": "0", "invalid_number_count": "0"}]},),
                    ({"list": data},),
                ]
                result = self._aggregate(
                    dimensions=self._time_dimensions(category=category),
                    metrics=[
                        {"id": "events", "type": "COUNT"},
                        {"id": "unique_users", "type": "DISTINCT_COUNT", "field": {"raw_name": "username"}},
                    ],
                )
                self.assertEqual([row["unique_users"] for row in result.rows], [1 if total else 0] + [0] * 24)
                self.assertEqual([row["events"] for row in result.rows], [total] + [0] * 24)

    def test_time_truncation_duplicate_bucket_and_nonclosing_counts_reject(self):
        for mutation in ("truncated", "duplicate", "count", "outside"):
            with self.subTest(mutation=mutation):
                data = frames()
                for row in data:
                    if row["frame"] == "ROW":
                        row["bucket"] = "0"
                if mutation == "truncated":
                    data.pop(4)
                elif mutation == "duplicate":
                    data.append(dict(data[4]))
                    data[0]["b"] = "4"
                elif mutation == "count":
                    data[4].update(n="5", m0="5")
                else:
                    data[4]["bucket"] = "25"
                self.mock_query.side_effect = [
                    ({"list": [{"group_count": "3", "invalid_type_count": "0", "invalid_number_count": "0"}]},),
                    ({"list": data},),
                ]
                with self.assertRaises(LogQueryFailed):
                    self._aggregate(dimensions=self._time_dimensions())

    @override_settings(AI_LOG_AGGREGATION_MAX_CELLS=200)
    def test_auto_growth_reexecutes_complete_query_and_uses_only_final_snapshot(self):
        data = frames()
        for row in data:
            if row["frame"] == "ROW":
                row["bucket"] = "0"
        self.mock_query.side_effect = [
            ({"list": [{"group_count": "1", "invalid_type_count": "0", "invalid_number_count": "0"}]},),
            ({"list": [data[0]]},),
            ({"list": data},),
        ]
        result = self._aggregate(dimensions=self._time_dimensions(interval="AUTO"))
        self.assertEqual(result.query_summary.effective_interval, "DAY")
        self.assertEqual(len(result.rows), 6)
        self.assertEqual(sum(row["events"] for row in result.rows), 10)
        self.assertEqual(self.mock_query.call_count, 3)
        final_sql = self.mock_query.call_args.args[0][0]["sql"]
        self.assertIn("ROW_NUMBER() OVER", final_sql)
        self.assertIn("FROM normalized", final_sql)

    @override_settings(AI_LOG_AGGREGATION_MAX_CELLS=200)
    def test_explicit_growth_returns_budget_error_without_changing_interval(self):
        self.mock_query.side_effect = [
            ({"list": [{"group_count": "1", "invalid_type_count": "0", "invalid_number_count": "0"}]},),
            ({"list": [frames()[0]]},),
        ]
        with self.assertRaises(StatisticsBudgetExceeded) as caught:
            self._aggregate(dimensions=self._time_dimensions())
        self.assertEqual(caught.exception.data["suggested_interval"], "DAY")
        self.assertEqual(self.mock_query.call_count, 2)

    @override_settings(AI_LOG_AGGREGATION_MAX_CELLS=11)
    def test_no_time_still_enforces_numeric_cell_budget(self):
        with self.assertRaises(StatisticsBudgetExceeded):
            self._aggregate()
