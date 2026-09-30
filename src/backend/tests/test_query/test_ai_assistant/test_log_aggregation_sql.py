"""完整聚合 SQL 关系及安全边界。"""
import sqlite3
from datetime import datetime

import sqlglot
from django.test import SimpleTestCase, override_settings

from core.constants import OrderTypeChoices
from services.web.query.ai_assistant.log_tools.context import LogQueryContext
from services.web.query.ai_assistant.log_tools.schemas import (
    AggregateLogsRequest,
    LogFieldRef,
)
from services.web.query.ai_assistant.log_tools.sql import (
    LogAggregationSQLBuilder,
    ProjectedLogSQLBuilder,
)
from services.web.query.ai_assistant.log_tools.statistics_budget import build_time_axis
from services.web.query.ai_assistant.schemas import SearchCondition
from services.web.query.utils.doris import DorisQuerySQLBuilder


def make_request(**kwargs):
    """创建固定范围请求，允许调用方覆盖统计定义。"""
    payload = dict(
        condition=SearchCondition(
            scope_type="system",
            scope_id="s1",
            start_time="2026-08-13T00:00:00+08:00",
            end_time="2026-08-14T00:00:00+08:00",
        ),
        dimensions=[{"id": "action", "type": "FIELD", "field": {"raw_name": "action_id"}}],
        metrics=[{"id": "events", "type": "COUNT"}],
        top_n=1,
    )
    payload.update(kwargs)
    if not any(d["type"] == "FIELD" for d in payload["dimensions"]):
        payload.pop("top_n", None)
    return AggregateLogsRequest(**payload)


class TestLogAggregationSQLBuilder(SimpleTestCase):
    def setUp(self):
        self.context = LogQueryContext(
            username="tester",
            namespace="default",
            condition=make_request().condition,
            table="test_rt.doris",
            conditions=({"field": {"raw_name": "system_id", "keys": []}, "operator": "include", "filters": ["s1"]},),
        )

    def test_top_n_ranks_full_categories_then_maps_original_rows(self):
        sql = LogAggregationSQLBuilder.from_request(self.context, make_request()).build_complete_sql()
        self.assertIn("FROM normalized WHERE d0_type IS NOT NULL GROUP BY d0_type, d0_key", sql)
        self.assertIn("ROW_NUMBER() OVER (ORDER BY log_count DESC, d0_type ASC, d0_key ASC)", sql)
        self.assertIn("FROM ranked WHERE group_key <= 1", sql)
        self.assertIn("FROM normalized n LEFT JOIN selected s ON n.d0_type = s.d0_type AND n.d0_key = s.d0_key", sql)
        self.assertIn("FROM mapped GROUP BY group_key", sql)
        self.assertIn("`system_id` IN ('s1')", sql)
        self.assertNotIn("LIMIT", sql)

    def test_other_avg_uses_original_values_and_global_metric_order(self):
        request = make_request(
            metrics=[
                {
                    "id": "average",
                    "type": "AVG",
                    "field": {"raw_name": "extend_data", "keys": ["duration"]},
                    "value_type": "DOUBLE",
                }
            ],
            order_by=[{"target_id": "average", "direction": "ASC"}],
        )
        sql = LogAggregationSQLBuilder.from_request(self.context, request).build_complete_sql()
        self.assertIn("AVG(m0_value) AS m0", sql)
        self.assertIn("ORDER BY m0 ASC NULLS LAST, d0_type ASC, d0_key ASC", sql)
        self.assertNotIn("AVG(m0)", sql)
        self.assertIn("COUNT(f1_type) AS present_count", sql)
        self.assertIn("COUNT(m0_value) AS converted_count", sql)

    def test_two_categories_use_tuple_keys_and_any_missing_is_one_group(self):
        sql = LogAggregationSQLBuilder.from_request(
            self.context,
            make_request(
                dimensions=[
                    {"id": "action", "type": "FIELD", "field": {"raw_name": "action_id"}},
                    {"id": "actor", "type": "FIELD", "field": {"raw_name": "username"}},
                ]
            ),
        ).build_complete_sql()
        self.assertIn("GROUP BY d0_type, d0_key, d1_type, d1_key", sql)
        self.assertIn("n.d0_type IS NULL OR n.d1_type IS NULL", sql)
        self.assertIn("n.d1_type = s.d1_type AND n.d1_key = s.d1_key", sql)
        self.assertNotIn("CONCAT(n.d0", sql)

    def test_numeric_type_guard_precedes_canonicalization_and_checks_full_scope(self):
        sql = LogAggregationSQLBuilder.from_request(
            self.context,
            make_request(
                dimensions=[{"id": "number", "type": "FIELD", "field": {"raw_name": "extend_data", "keys": ["n"]}}]
            ),
        ).build_complete_sql()
        self.assertIn("JSON_EXTRACT_LARGEINT(`extend_data`,'$.n')", sql)
        self.assertIn("JSON_EXTRACT_DOUBLE(`extend_data`,'$.n')", sql)
        self.assertIn("BETWEEN CAST(-9007199254740991 AS LARGEINT) AND CAST(9007199254740991 AS LARGEINT)", sql)
        self.assertIn("CAST(f0_d_text AS DOUBLE) = f0_d_safe", sql)
        self.assertIn("FROM normalized", sql[sql.index("validation AS") :])
        self.assertNotIn("DECIMAL", sql)
        self.assertIn("CAST(f0_i_safe AS STRING)", sql)

    def test_json_path_escapes_punctuation_and_preserves_scalar_type(self):
        sql = LogAggregationSQLBuilder.from_request(
            self.context,
            make_request(
                dimensions=[
                    {"id": "value", "type": "FIELD", "field": {"raw_name": "extend_data", "keys": [" a'b ", "*", "中"]}}
                ]
            ),
        ).build_complete_sql()
        self.assertIn('$." a\'\'b "."*".中', sql)
        self.assertIn("JSON_TYPE", sql)
        self.assertIn("JSON_QUOTE", sql)
        self.assertIn("'null'", sql)

    def test_preflight_is_bounded_and_final_recalculates_groups(self):
        builder = LogAggregationSQLBuilder.from_request(self.context, make_request())
        self.assertIn("COUNT(*)", builder.build_preflight_sql())
        self.assertIn("FROM category_counts", builder.build_preflight_sql())
        self.assertIn("category_counts AS", builder.build_complete_sql())

    def test_global_empty_aggregate_uses_unconditional_all(self):
        sql = LogAggregationSQLBuilder.from_request(self.context, make_request(dimensions=[])).build_complete_sql()
        self.assertIn("'ALL'", sql)
        self.assertIn("COUNT(*) AS log_count", sql)
        self.assertIn("FROM normalized", sql)

    def test_projected_data_and_inherited_count_preserve_query_contract(self):
        """复用计数不应改变投影字段、分页排序或给计数引入分页偏移。"""
        builder = ProjectedLogSQLBuilder(
            table=self.context.table,
            conditions=list(self.context.conditions),
            sort_list=[{"order_field": "start_time", "order_type": OrderTypeChoices.DESC.value}],
            page=2,
            page_size=5,
        )
        self.assertEqual(
            builder.build_data_sql([LogFieldRef(raw_name="start_time"), LogFieldRef(raw_name="username")]),
            "SELECT `start_time`,`username` FROM test_rt.doris WHERE `system_id` IN ('s1')"
            " ORDER BY `start_time` DESC LIMIT 5 OFFSET 5",
        )
        self.assertEqual(
            builder.build_count_sql(),
            "SELECT COUNT(*) `count` FROM test_rt.doris WHERE `system_id` IN ('s1') LIMIT 1",
        )
        web_builder = DorisQuerySQLBuilder(
            table=self.context.table,
            conditions=list(self.context.conditions),
            sort_list=[{"order_field": "start_time", "order_type": OrderTypeChoices.DESC.value}],
            page=2,
            page_size=5,
        )
        self.assertEqual(
            web_builder.build_data_sql(),
            "SELECT * FROM test_rt.doris WHERE `system_id` IN ('s1')" " ORDER BY `start_time` DESC LIMIT 5 OFFSET 5",
        )
        self.assertEqual(
            web_builder.build_count_sql(),
            "SELECT COUNT(*) `count` FROM test_rt.doris WHERE `system_id` IN ('s1') LIMIT 1",
        )

    def test_doris_bool_type_is_normalized_before_grouping(self):
        request = make_request(
            dimensions=[{"id": "value", "type": "FIELD", "field": {"raw_name": "extend_data", "keys": ["value"]}}]
        )
        sql = LogAggregationSQLBuilder.from_request(self.context, request).build_complete_sql()
        self.assertIn("WHEN f0_observed IN ('bool','boolean') THEN 'boolean'", sql)
        self.assertIn("IN ('bool','boolean') THEN CAST(JSON_EXTRACT", sql)

    def test_execute_generated_group_relations_with_hand_checked_other_average(self):
        """用本地SQL执行真实排名/映射关系；不声称验证Doris标量函数。"""
        request = make_request(
            metrics=[
                {
                    "id": "average",
                    "type": "AVG",
                    "field": {"raw_name": "extend_data", "keys": ["duration"]},
                    "value_type": "DOUBLE",
                }
            ]
        )
        sql = LogAggregationSQLBuilder.from_request(self.context, request).build_complete_sql()
        tree = sqlglot.parse_one(sql, read="starrocks")
        required = {"category_counts", "ranked", "selected", "mapped", "aggregated"}
        ctes = [cte.sql(dialect="sqlite") for cte in tree.find_all(sqlglot.exp.CTE) if cte.alias in required]
        with sqlite3.connect(":memory:") as db:
            db.execute("CREATE TABLE normalized(d0_type TEXT,d0_key TEXT,m0_value REAL)")
            db.executemany(
                "INSERT INTO normalized VALUES(?,?,?)",
                [("string", "GET", 1)] * 6
                + [("string", "POST", 2), ("string", "POST", 4), ("string", "PUT", 12), (None, None, None)],
            )
            rows = db.execute(
                "WITH " + ",".join(ctes) + " SELECT group_kind,log_count,m0 FROM aggregated ORDER BY group_key"
            ).fetchall()
        self.assertEqual(rows, [("VALUE", 6, 1.0), ("OTHER", 3, 6.0), ("MISSING", 1, None)])

    def test_execute_metric_order_and_string_value_order_on_full_categories(self):
        for order, want in [
            ([{"target_id": "average", "direction": "DESC"}], ("PUT", 12.0)),
            ([{"target_id": "action", "direction": "ASC"}], ("GET", 1.0)),
        ]:
            request = make_request(
                metrics=[
                    {
                        "id": "average",
                        "type": "AVG",
                        "field": {"raw_name": "extend_data", "keys": ["duration"]},
                        "value_type": "DOUBLE",
                    }
                ],
                order_by=order,
            )
            tree = sqlglot.parse_one(
                LogAggregationSQLBuilder.from_request(self.context, request).build_complete_sql(), read="starrocks"
            )
            ctes = [
                c.sql(dialect="sqlite")
                for c in tree.find_all(sqlglot.exp.CTE)
                if c.alias in {"category_counts", "ranked", "selected"}
            ]
            with sqlite3.connect(":memory:") as db:
                db.execute("CREATE TABLE normalized(d0_type TEXT,d0_key TEXT,m0_value REAL)")
                db.executemany(
                    "INSERT INTO normalized VALUES(?,?,?)",
                    [("string", "GET", 1)] * 6 + [("string", "POST", 2), ("string", "PUT", 12)],
                )
                rows = db.execute("WITH " + ",".join(ctes) + " SELECT d0_key,m0 FROM selected").fetchall()
            self.assertEqual(rows, [want])

    def test_whole_json_objects_and_forged_field_type_cannot_bypass_declared_type(self):
        request = make_request(
            dimensions=[{"id": "code", "type": "FIELD", "field": {"raw_name": "access_type", "field_type": "string"}}],
            metrics=[{"id": "sum", "type": "SUM", "field": {"raw_name": "access_type", "field_type": "double"}}],
        )
        sql = LogAggregationSQLBuilder.from_request(self.context, request).build_complete_sql()
        self.assertIn("f0_i_safe AS m0_value", sql)
        self.assertNotIn("f0_d_safe AS m0_value", sql)

    def test_multiple_distinct_metrics_use_lossless_single_column_keys(self):
        """Doris 多去重要求单列；类型、空串、分隔符和缺失值不能混淆。"""
        request = make_request(
            dimensions=[],
            metrics=[
                {"id": "users", "type": "DISTINCT_COUNT", "field": {"raw_name": "username"}},
                {"id": "actions", "type": "DISTINCT_COUNT", "field": {"raw_name": "action_id"}},
            ],
        )
        builder = LogAggregationSQLBuilder.from_request(self.context, request)
        sql = "SELECT " + ", ".join(builder.metric_aggregate(i) for i in range(2)) + " FROM normalized"
        tree = sqlglot.parse_one(sql, read="starrocks")
        for distinct in tree.find_all(sqlglot.exp.Distinct):
            self.assertEqual(len(distinct.expressions), 1)
        with sqlite3.connect(":memory:") as db:
            db.execute("CREATE TABLE normalized(f0_type TEXT, f0_key TEXT, f1_type TEXT, f1_key TEXT)")
            db.executemany(
                "INSERT INTO normalized VALUES(?,?,?,?)",
                [
                    ("string", "1", "string", "a:b"),
                    ("number", "1", "string", "a:b"),
                    ("boolean", "true", "string", ""),
                    ("string", "true", None, None),
                    ("string", "", "string", "string:a:b"),
                    (None, None, "string", "a:b"),
                    ("string", "1", "string", "a:b"),
                ],
            )
            self.assertEqual(db.execute(tree.sql(dialect="sqlite")).fetchone(), (5, 3))

    def test_variant_subpath_guards_actual_storage_type_before_cast(self):
        request = make_request(
            dimensions=[{"id": "value", "type": "FIELD", "field": {"raw_name": "snapshot_action_info", "keys": ["id"]}}]
        )
        sql = LogAggregationSQLBuilder.from_request(self.context, request).build_complete_sql()
        self.assertIn("VARIANT_TYPE(`snapshot_action_info`)", sql)
        self.assertNotIn("JSON_TYPE(`snapshot_action_info`", sql)
        self.assertIn("COALESCE(", sql)

    def test_time_bucket_builds_complete_sql_without_legacy_rejection(self):
        request = make_request(
            dimensions=[{"id": "bucket", "type": "TIME_BUCKET", "field": {"raw_name": "start_time"}}]
        )
        sql = LogAggregationSQLBuilder.from_request(self.context, request).build_complete_sql()
        self.assertIn("time_rows AS", sql)
        self.assertIn("`dtEventTimeStamp` AS event_timestamp", sql)
        self.assertNotIn("FROM_UNIXTIME", sql)

    def test_actual_numeric_category_order_is_not_lexical(self):
        for direction, expected in [("ASC", ["-3", "0.5", "2", "10"]), ("DESC", ["10", "2", "0.5", "-3"])]:
            request = make_request(top_n=4, order_by=[{"target_id": "action", "direction": direction}])
            tree = sqlglot.parse_one(
                LogAggregationSQLBuilder.from_request(self.context, request).build_complete_sql(), read="starrocks"
            )
            ctes = [
                cte.sql(dialect="sqlite")
                for cte in tree.find_all(sqlglot.exp.CTE)
                if cte.alias in {"category_counts", "ranked", "selected"}
            ]
            with sqlite3.connect(":memory:") as db:
                db.execute("CREATE TABLE normalized(d0_type TEXT,d0_key TEXT)")
                db.executemany(
                    "INSERT INTO normalized VALUES('number',?)", [(value,) for value in ["2", "10", "-3", "0.5"]]
                )
                rows = db.execute(
                    "WITH " + ",".join(ctes) + " SELECT d0_key FROM selected ORDER BY group_key"
                ).fetchall()
            self.assertEqual([row[0] for row in rows], expected)

    def test_time_relations_keep_full_range_topn_and_independent_bucket_counts(self):
        request = make_request(
            dimensions=[
                {"id": "action", "type": "FIELD", "field": {"raw_name": "action_id"}},
                {"id": "hour", "type": "TIME_BUCKET", "field": {"raw_name": "start_time"}, "interval": "HOUR"},
            ]
        )
        builder = LogAggregationSQLBuilder.from_request(self.context, request)
        tree = sqlglot.parse_one(builder.build_complete_sql(effective_interval="HOUR"), read="starrocks")
        ctes = [
            cte.sql(dialect="sqlite")
            for cte in tree.find_all(sqlglot.exp.CTE)
            if cte.alias in {"category_counts", "ranked", "selected", "mapped", "aggregated", "bucketed", "time_rows"}
        ]
        origin = 1786550400000
        with sqlite3.connect(":memory:") as db:
            db.execute("CREATE TABLE normalized(d0_type TEXT,d0_key TEXT,event_timestamp INTEGER)")
            db.executemany(
                "INSERT INTO normalized VALUES(?,?,?)",
                [("string", "GET", origin)] * 3
                + [("string", "POST", origin + 3600000)] * 2
                + [("string", "GET", origin + 86400000), (None, None, origin + 86400000)],
            )
            rows = db.execute(
                "WITH "
                + ",".join(ctes)
                + " SELECT group_key,bucket,log_count,m0 FROM time_rows ORDER BY group_key,bucket"
            ).fetchall()
        self.assertEqual(rows, [(1, 0, 3, 3), (1, 24, 1, 1), (2, 1, 2, 2), (3, 24, 1, 1)])

    @override_settings(TIME_ZONE="America/New_York")
    def test_last_day_bucket_does_not_overflow_when_dst_makes_it_longer(self):
        request = make_request(
            dimensions=[{"id": "day", "type": "TIME_BUCKET", "field": {"raw_name": "start_time"}, "interval": "DAY"}]
        )
        builder = LogAggregationSQLBuilder.from_request(self.context, request)
        builder.time_axis = build_time_axis(
            start_time="2026-10-31T00:00:00-04:00",
            end_time="2026-11-01T23:59:00-05:00",
            interval="DAY",
            group_count=1,
            numeric_columns=3,
        )
        expression = sqlglot.parse_one(builder._bucket_expression(), read="starrocks").sql(dialect="sqlite")
        timestamp = int(datetime.fromisoformat("2026-11-01T23:59:00-05:00").timestamp() * 1000)
        with sqlite3.connect(":memory:") as db:
            bucket = db.execute(
                "SELECT " + expression + " FROM (SELECT ? AS event_timestamp)", (timestamp,)
            ).fetchone()[0]
        self.assertEqual(bucket, 1)

    @override_settings(TIME_ZONE="America/New_York")
    def test_dst_multi_segment_day_axis_assigns_real_sql_boundaries(self):
        """执行生产归桶表达式，跨25小时日的前后区段边界均落正确桶。"""
        request = make_request(
            dimensions=[{"id": "day", "type": "TIME_BUCKET", "field": {"raw_name": "start_time"}, "interval": "DAY"}]
        )
        builder = LogAggregationSQLBuilder.from_request(self.context, request)
        builder.time_axis = build_time_axis(
            start_time="2026-10-30T00:00:00-04:00",
            end_time="2026-11-03T00:00:00-05:00",
            interval="DAY",
            group_count=1,
            numeric_columns=3,
        )
        expression = sqlglot.parse_one(builder._bucket_expression(), read="starrocks").sql(dialect="sqlite")
        samples = [
            ("2026-10-31T23:59:59-04:00", 1),
            ("2026-11-01T00:00:00-04:00", 2),
            ("2026-11-01T01:30:00-04:00", 2),
            ("2026-11-01T01:30:00-05:00", 2),
            ("2026-11-01T23:59:59-05:00", 2),
            ("2026-11-02T00:00:00-05:00", 3),
            ("2026-11-03T00:00:00-05:00", 4),
        ]
        with sqlite3.connect(":memory:") as db:
            for value, expected in samples:
                with self.subTest(value=value):
                    timestamp = int(datetime.fromisoformat(value).timestamp() * 1000)
                    actual = db.execute(
                        "SELECT " + expression + " FROM (SELECT ? AS event_timestamp)", (timestamp,)
                    ).fetchone()[0]
                    self.assertEqual(actual, expected)

    def test_physical_timestamp_closed_filter_precedes_bucket_assignment(self):
        request = make_request(
            dimensions=[{"id": "hour", "type": "TIME_BUCKET", "field": {"raw_name": "start_time"}, "interval": "HOUR"}]
        )
        start_ms, end_ms = 1786550400000 + 1500000, 1786550400000 + 3600000
        context = LogQueryContext(
            username="tester",
            namespace="default",
            condition=request.condition,
            table="logs",
            conditions=tuple(
                {"field": {"raw_name": "dtEventTimeStamp", "keys": []}, "operator": op, "filters": [value]}
                for op, value in [("gte", start_ms), ("lte", end_ms)]
            ),
        )
        builder = LogAggregationSQLBuilder.from_request(context, request)
        tree = sqlglot.parse_one(builder.build_complete_sql(), read="starrocks")
        ctes = [cte.sql(dialect="sqlite") for cte in tree.find_all(sqlglot.exp.CTE)]
        with sqlite3.connect(":memory:") as db:
            db.execute("CREATE TABLE logs(dtEventTimeStamp INTEGER,start_time INTEGER)")
            db.executemany(
                "INSERT INTO logs VALUES(?,0)", [(value,) for value in [start_ms - 1, start_ms, end_ms, end_ms + 1]]
            )
            rows = db.execute(
                "WITH " + ",".join(ctes) + " SELECT bucket,log_count FROM time_rows ORDER BY bucket"
            ).fetchall()
        self.assertEqual(rows, [(0, 1), (1, 1)])
