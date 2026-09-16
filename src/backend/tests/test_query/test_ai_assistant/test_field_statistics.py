"""程序固定包：真实服务、SQL builder 和严格帧解析；仅替换远端查询及系统上下文。"""
import copy
import sqlite3
from unittest import mock

import sqlglot
from django.test import override_settings

from api.bk_base.default import SafeQuerySyncResource
from apps.meta.constants import SensitiveResourceTypeEnum
from apps.meta.models import SensitiveObject
from core.exceptions import PermissionException
from services.web.query.ai_assistant.exceptions import (
    InvalidLogCondition,
    LogQueryFailed,
    SensitiveFieldPermissionDenied,
    StatisticsResponseTooLarge,
    UnsupportedFieldType,
)
from services.web.query.ai_assistant.log_tools.aggregation import LogAggregationService
from services.web.query.ai_assistant.log_tools.context import (
    LogQueryContext,
    LogQueryContextService,
)
from services.web.query.ai_assistant.log_tools.schemas import LogFieldRef
from services.web.query.ai_assistant.log_tools.statistics import FieldStatisticsService
from services.web.query.ai_assistant.log_tools.statistics_sql import (
    StatisticsSQLBuilder,
)
from tests.base import TestCase
from tests.test_query.test_ai_assistant.test_log_aggregation_sql import make_request

REAL_CONTEXT_BUILD = LogQueryContextService.build


def field_frames():
    """手算完整范围 GET6、OTHER3、缺失1；两桶分别4/6。"""
    data = [
        dict(frame="META", n="10", a="3", b="5", c="0", d="0", e="0"),
        dict(frame="SUMMARY", n="9", a="0", s_min=None, s_max=None, s_avg=None, s_median=None),
        dict(frame="GROUP", key="1", kind="VALUE", n="6", d0_type="string", d0_json='"GET"'),
        dict(frame="GROUP", key="2", kind="OTHER", n="3", d0_type=None, d0_json=None),
        dict(frame="GROUP", key="3", kind="MISSING", n="1", d0_type=None, d0_json=None),
    ]
    for key, bucket, count in [(1, 0, 2), (1, 1, 4), (2, 0, 1), (2, 1, 2), (3, 0, 1)]:
        data.append(dict(frame="ROW", key=str(key), bucket=str(bucket), n=str(count), m0=str(count)))
    return data


class TestFieldStatistics(TestCase):
    """每个断言保护固定包、同快照摘要或失败关闭边界。"""

    def setUp(self):
        super().setUp()
        self.condition = make_request().condition.model_copy(
            update={
                "start_time": "2026-09-15T10:00:00+08:00",
                "end_time": "2026-09-15T11:59:59+08:00",
            }
        )
        self.context = LogQueryContext(
            username="tester", namespace="default", condition=self.condition, table="logs", conditions=()
        )
        self.context_builder = self.enterContext(
            mock.patch(
                "services.web.query.ai_assistant.log_tools.aggregation.LogQueryContextService.build",
                return_value=self.context,
            )
        )
        self.query = self.enterContext(mock.patch.object(SafeQuerySyncResource, "bulk_request"))
        self.data = field_frames()
        self.query.side_effect = self._remote

    def _remote(self, requests):
        """区分预检和最终SQL，最终只提供同一快照的完整帧。"""
        sql = requests[0]["sql"]
        if "AS group_count" in sql:
            return ({"list": [dict(group_count="3", invalid_type_count="0", invalid_number_count="0")]},)
        self.assertIn("AS s_median", sql)
        self.assertIn("FROM normalized", sql)
        return ({"list": copy.deepcopy(self.data)},)

    def _analyze(self, field=None, **kwargs):
        """调用公开程序服务，保留真实解析和敏感权限检查。"""
        return FieldStatisticsService.analyze(
            username="tester",
            namespace="default",
            condition=self.condition,
            field=field or LogFieldRef(raw_name="extend_data", keys=["method"]),
            top_n=1,
            interval="HOUR",
            **kwargs
        )

    def test_fixed_package_typed_groups_complete_axis_and_same_snapshot(self):
        result = self._analyze()
        self.assertEqual(
            set(result.model_dump()),
            {"field", "statistics_kind", "overview", "distribution", "time_series", "numeric_summary", "query_summary"},
        )
        self.assertEqual(
            result.overview.model_dump(), dict(total_count=10, present_count=9, missing_count=1, present_ratio=0.9)
        )
        self.assertEqual(result.time_series.bucket_starts, ("2026-09-15T10:00:00+08:00", "2026-09-15T11:00:00+08:00"))
        self.assertEqual([s.counts for s in result.time_series.series], [(2, 4), (1, 2), (1, 0)])
        self.assertEqual(result.distribution.groups[0].value, "GET")
        self.assertIsNone(result.distribution.groups[1].value_type)
        self.assertIsNone(result.distribution.groups[2].value)
        self.assertEqual(result.field.display_name, "method")
        self.assertEqual(result.statistics_kind, "CATEGORICAL")
        self.assertIsNone(result.numeric_summary)
        self.assertEqual(self.query.call_count, 2)

    def test_native_numeric_summary_and_client_hint_is_not_authority(self):
        self.data[1].update(a="9", s_min="1e-20", s_max="9", s_avg="3", s_median="2")
        self.data[2].update(d0_type="number", d0_json="2")
        result = self._analyze(LogFieldRef(raw_name="extend_data", keys=["n"], field_type="string"))
        self.assertEqual(result.statistics_kind, "NUMERIC")
        self.assertEqual(
            result.numeric_summary.model_dump(),
            dict(
                min=1e-20, max=9, avg=3, median=2, median_is_approximate=True, valid_count=9, conversion_failed_count=0
            ),
        )

    def test_mixed_scalars_and_numeric_strings_remain_categorical(self):
        for numeric_count in ("0", "3"):
            self.data[1]["a"] = numeric_count
            self.data[2]["d0_json"] = '"12"'
            result = self._analyze(LogFieldRef(raw_name="extend_data", keys=["n"], field_type="double"))
            self.assertEqual(result.statistics_kind, "CATEGORICAL")
            self.assertEqual(result.distribution.groups[0].value, "12")
            self.assertIsNone(result.numeric_summary)

    def test_empty_and_all_missing_unknown_paths_succeed_and_declared_numeric_stays_numeric(self):
        for total in (0, 2):
            for field, kind in [
                (LogFieldRef(raw_name="extend_data", keys=["unknown"]), "CATEGORICAL"),
                (LogFieldRef(raw_name="access_type", field_type="string"), "NUMERIC"),
            ]:
                self.data = [
                    dict(
                        frame="META",
                        n=str(total),
                        a="1" if total else "0",
                        b="1" if total else "0",
                        c="0",
                        d="0",
                        e="0",
                    ),
                    dict(frame="SUMMARY", n="0", a="0", s_min=None, s_max=None, s_avg=None, s_median=None),
                ]
                if total:
                    self.data.extend(
                        [
                            dict(frame="GROUP", key="3", kind="MISSING", n="2", d0_type=None, d0_json=None),
                            dict(frame="ROW", key="3", n="2", m0="2", bucket="0"),
                        ]
                    )
                result = self._analyze(field)
                self.assertEqual(result.statistics_kind, kind)
                self.assertEqual(result.overview.present_count, 0)
                self.assertEqual(result.overview.missing_count, total)
                self.assertEqual(result.overview.present_ratio, 0 if total else None)
                self.assertEqual(len(result.time_series.series), 1 if total else 0)
                if kind == "NUMERIC":
                    self.assertIsNone(result.numeric_summary.min)
                    self.assertIsNone(result.numeric_summary.max)
                    self.assertIsNone(result.numeric_summary.avg)
                    self.assertIsNone(result.numeric_summary.median)

    def test_empty_string_is_present(self):
        self.data[2]["d0_json"] = '""'
        result = self._analyze()
        self.assertEqual(result.overview.present_count, 9)
        self.assertEqual(result.distribution.groups[0].value, "")

    def test_summary_missing_duplicate_inconsistent_or_malformed_fails_closed(self):
        original = field_frames()
        variants = [original[:1] + original[2:], original + [original[1]]]
        for key, value in [("n", "8"), ("a", "10"), ("a", "-1"), ("s_min", "NaN")]:
            data = copy.deepcopy(original)
            data[1][key] = value
            variants.append(data)
        for data in variants:
            self.data = data
            with self.assertRaises(LogQueryFailed):
                self._analyze()

    def test_summary_numeric_count_cannot_contradict_typed_selected_groups(self):
        self.data[1].update(a="9", s_min="1", s_max="9", s_avg="3", s_median="2")
        with self.assertRaises(LogQueryFailed):
            self._analyze()

    def test_summary_only_sensitive_path_is_in_shared_authorization(self):
        SensitiveObject.objects.create(
            name="private summary",
            system_id="s1",
            resource_type=SensitiveResourceTypeEnum.RESOURCE.value,
            resource_id="host",
            fields=[{"field_name": "extend_data.secret"}],
            is_private=True,
        )
        builder = StatisticsSQLBuilder.from_request(
            self.context, make_request(), summary_field=LogFieldRef(raw_name="extend_data", keys=["secret"])
        )
        with self.assertRaises(SensitiveFieldPermissionDenied):
            LogAggregationService._execute(builder, numeric_columns=1)
        self.query.assert_not_called()

    @override_settings(AI_LOG_AGGREGATION_MAX_CELLS=6)
    def test_program_count_only_budget_uses_one_numeric_column(self):
        result = self._analyze()
        self.assertEqual(result.overview.total_count, 10)

    @override_settings(AI_LOG_AGGREGATION_RESPONSE_MAX_BYTES=1)
    def test_complete_program_package_has_byte_budget(self):
        with self.assertRaises(StatisticsResponseTooLarge):
            self._analyze()

    def test_sensitive_summary_path_fails_before_query(self):
        SensitiveObject.objects.create(
            name="private",
            system_id="s1",
            resource_type=SensitiveResourceTypeEnum.RESOURCE.value,
            resource_id="host",
            fields=[{"field_name": "extend_data.method"}],
            is_private=True,
        )
        with self.assertRaises(SensitiveFieldPermissionDenied):
            self._analyze()
        self.query.assert_not_called()

    def test_program_other_field_still_authorizes_sensitive_time_dimension(self):
        """程序统计其他字段仍包含时间维度，私密与无权时间字段都必须提前拒绝。"""
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
                self.query.reset_mock()
                try:
                    with mock.patch(
                        "services.web.query.ai_assistant.log_tools.sensitive.PermissionService"
                    ) as permissions:
                        permissions.return_value.get_sensitive_object_permissions.return_value = {}
                        with self.assertRaises(SensitiveFieldPermissionDenied):
                            self._analyze(LogFieldRef(raw_name="username"))
                    self.query.assert_not_called()
                finally:
                    rule.delete()

    def test_real_context_denies_system_before_remote_query(self):
        self.context_builder.side_effect = REAL_CONTEXT_BUILD
        with mock.patch(
            "services.web.query.ai_assistant.log_tools.context.SearchLogPermission.has_system_search_permission",
            return_value=False,
        ), mock.patch(
            "services.web.query.ai_assistant.log_tools.context."
            "SearchLogPermission.raise_system_view_permission_exception",
            side_effect=PermissionException(action_name="view_system", permission={}, apply_url=""),
        ):
            with self.assertRaises(PermissionException):
                self._analyze()
        self.query.assert_not_called()

    def test_real_context_rejects_scope_outside_namespace(self):
        self.context_builder.side_effect = REAL_CONTEXT_BUILD
        with mock.patch(
            "services.web.query.ai_assistant.log_tools.context.SearchLogPermission.has_system_search_permission",
            return_value=True,
        ):
            with self.assertRaises(InvalidLogCondition):
                FieldStatisticsService.analyze(
                    username="tester",
                    namespace="outside-statistics-namespace",
                    condition=self.condition,
                    field=LogFieldRef(raw_name="username"),
                )
        self.query.assert_not_called()

    def test_final_full_range_invalid_type_or_number_is_rejected(self):
        for key in ("d", "e"):
            self.data = field_frames()
            self.data[0][key] = "1"
            with self.assertRaises(UnsupportedFieldType):
                self._analyze()

    def test_selected_typed_scalars_preserve_boolean_number_and_reserved_strings(self):
        for kind, text, value, numeric in [
            ("boolean", "true", True, "0"),
            ("number", "-3", -3, "6"),
            ("string", '"OTHER"', "OTHER", "0"),
            ("string", '"MISSING"', "MISSING", "0"),
        ]:
            self.data = field_frames()
            self.data[1]["a"] = numeric
            self.data[2].update(d0_type=kind, d0_json=text)
            result = self._analyze()
            group = result.distribution.groups[0]
            self.assertEqual(group.value_type, kind)
            self.assertEqual(group.value, value)
            self.assertIs(type(group.value), type(value))
            self.assertEqual(group.kind, "VALUE")
            self.assertIsNone(result.numeric_summary)

    def test_summary_relations_use_full_normalized_values_not_selected_topn(self):
        request = make_request(
            dimensions=[dict(id="value", type="FIELD", field=dict(raw_name="extend_data", keys=["n"]))]
        )
        builder = StatisticsSQLBuilder.from_request(
            self.context, request, summary_field=LogFieldRef(raw_name="extend_data", keys=["n"])
        )
        self.assertEqual(len(builder.fields), 1)
        tree = sqlglot.parse_one(builder.build_complete_sql(), read="starrocks")
        summary = next(cte for cte in tree.find_all(sqlglot.exp.CTE) if cte.alias == "field_summary")
        # 本地关系执行验证 min/max/avg 覆盖未选中值；近似分位只替换SQLite不支持的聚合函数。
        for node in list(summary.find_all(sqlglot.exp.Anonymous)):
            if node.name.upper() == "PERCENTILE_APPROX":
                node.replace(sqlglot.exp.Avg(this=node.expressions[0].copy()))
        with sqlite3.connect(":memory:") as db:
            db.execute("CREATE TABLE normalized(f0_type TEXT,f0_i_safe INTEGER,f0_d_safe REAL)")
            db.executemany(
                "INSERT INTO normalized VALUES(?,?,?)",
                [("number", 1, None)] * 6 + [("number", 22, None), (None, None, None)],
            )
            row = db.execute(
                "WITH "
                + summary.sql(dialect="sqlite")
                + " SELECT present_count,numeric_count,s_min,s_max,s_avg FROM field_summary"
            ).fetchone()
        self.assertEqual(row[:2], (7, 7))
        self.assertEqual(tuple(float(value) for value in row[2:]), (1, 22, 4))
