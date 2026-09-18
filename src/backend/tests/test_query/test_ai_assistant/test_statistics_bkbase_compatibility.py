"""BKBase/Doris 真实故障的兼容回归：路由参数、表达式子查询与 UNION 别名。"""

import re
import sqlite3
from dataclasses import replace
from unittest import mock

import sqlglot
from django.test import SimpleTestCase, override_settings
from sqlglot import exp

from api.bk_base.default import SafeQuerySyncResource
from services.web.query.ai_assistant.log_tools.aggregation import LogAggregationService
from services.web.query.ai_assistant.log_tools.field_metadata import (
    LogFieldMetadataService,
)
from services.web.query.ai_assistant.log_tools.schemas import (
    LogFieldRef,
    SearchLogsRequest,
)
from services.web.query.ai_assistant.log_tools.search import LogDetailSearchService
from services.web.query.ai_assistant.log_tools.statistics_sql import (
    StatisticsSQLBuilder,
)
from tests.test_query.test_ai_assistant import test_log_aggregation_sql as sql_fixture
from tests.test_query.test_ai_assistant.test_log_aggregation_sql import make_request


class TestStatisticsBKBaseCompatibility(SimpleTestCase):
    """测试真实链路已确认的语法约束，不将 SQL 解析通过视为远端执行证明。"""

    def setUp(self):
        fixture = sql_fixture.TestLogAggregationSQLBuilder()
        fixture.setUp()
        self.context = fixture.context

    def test_count_metadata_does_not_cast_a_scalar_subquery(self):
        """预检和完整结果的 CAST 输入应是列值，兼容远端表达式解析。"""
        builder = StatisticsSQLBuilder.from_request(self.context, make_request())
        for sql in (builder.build_preflight_sql(), builder.build_complete_sql()):
            with self.subTest(sql=sql[:40]):
                tree = sqlglot.parse_one(sql, read="starrocks")
                self.assertFalse(any(cast.find(exp.Subquery) for cast in tree.find_all(exp.Cast)))

    def test_time_bucket_avoids_bkbase_unsupported_div_operator(self):
        """BKBase 在 Doris 执行前拒绝 DIV，即使本地语法解析器支持。"""
        request = make_request(
            dimensions=[dict(id="hour", type="TIME_BUCKET", field=dict(raw_name="start_time"), interval="HOUR")]
        )
        sql = StatisticsSQLBuilder.from_request(self.context, request).build_complete_sql()
        self.assertNotIn(" DIV ", sql)

    def test_union_frame_identifiers_avoid_reserved_key(self):
        """BKBase 重写 UNION 时不能依赖反引号保留 key 别名。"""
        tree = sqlglot.parse_one(
            StatisticsSQLBuilder.from_request(self.context, make_request()).build_complete_sql(), read="starrocks"
        )
        aliases = {alias.alias for alias in tree.find_all(exp.Alias)}
        self.assertNotIn("key", aliases)
        self.assertIn("frame_key", aliases)

    def test_doris_queries_use_bare_table_and_storage_hint(self):
        """三条查询路径统一使用裸表和显式存储，避免重复路由声明。"""
        builder = StatisticsSQLBuilder.from_request(self.context, make_request())
        with mock.patch.object(SafeQuerySyncResource, "bulk_request", return_value=({"list": []},)) as query:
            LogAggregationService._query(builder)
            self.assertEqual(query.call_args.args[0][0]["prefer_storage"], "doris")
            self.assertNotIn(".doris", query.call_args.args[0][0]["sql"])
        with mock.patch.object(
            SafeQuerySyncResource, "bulk_request", return_value=({"list": []}, {"list": [{"count": 0}]})
        ) as query:
            LogDetailSearchService._query(
                context=self.context,
                request=SearchLogsRequest(condition=self.context.condition),
                fields=(LogFieldRef(raw_name="username"),),
            )
            for request in query.call_args.args[0]:
                self.assertEqual(request["prefer_storage"], "doris")
                self.assertNotIn(".doris", request["sql"])
        with mock.patch.object(SafeQuerySyncResource, "request", return_value={"list": []}) as query:
            LogFieldMetadataService._query_samples(self.context, LogFieldRef(raw_name="extend_data"))
            self.assertEqual(query.call_args.kwargs["prefer_storage"], "doris")
            self.assertNotIn(".doris", query.call_args.kwargs["sql"])

    def test_complete_frames_keep_meta_for_empty_inputs_and_exceeded_budget(self):
        """执行完整 UNION，保护单行计数关系在空集和预算失败时的 META 保留。"""
        time_dimension = dict(id="hour", type="TIME_BUCKET", field=dict(raw_name="start_time"), interval="HOUR")
        cases = (
            ("category", make_request(), [], 100000, ("0", "0", "0")),
            ("all", make_request(dimensions=[]), [], 100000, ("0", "1", "1")),
            ("time", make_request(dimensions=[time_dimension]), [], 100000, ("0", "1", "0")),
            ("budget", make_request(), [("s1", "a", 0)], 0, ("1", "1", "1")),
        )
        for name, request, rows, budget, expected in cases:
            with self.subTest(name=name), override_settings(AI_LOG_AGGREGATION_MAX_CELLS=budget):
                builder = StatisticsSQLBuilder.from_request(replace(self.context, table="logs"), request)
                sql = sqlglot.parse_one(builder.build_complete_sql(), read="starrocks").sql(dialect="sqlite")
                with sqlite3.connect(":memory:") as db:
                    db.row_factory = sqlite3.Row
                    db.create_function("REGEXP_LIKE", 2, lambda value, pattern: bool(re.search(pattern, value or "")))
                    db.execute("CREATE TABLE logs(system_id TEXT, action_id TEXT, dtEventTimeStamp INTEGER)")
                    db.executemany("INSERT INTO logs VALUES(?,?,?)", rows)
                    frames = [dict(row) for row in db.execute(sql)]
                meta = [frame for frame in frames if frame["frame"] == "META"]
                self.assertEqual(len(meta), 1)
                self.assertEqual(tuple(meta[0][key] for key in ("n", "a", "b")), expected)
                if name == "budget":
                    self.assertEqual(len(frames), 1)
                else:
                    self.assertEqual(sum(frame["frame"] == "GROUP" for frame in frames), int(expected[1]))
                    self.assertEqual(sum(frame["frame"] == "ROW" for frame in frames), int(expected[2]))
