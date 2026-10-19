"""程序与MCP共用可读性策略，保护配置及隐式SQL构造入口。"""
from unittest import mock

from django.test import SimpleTestCase, override_settings

from services.web.query.ai_assistant.log_tools.aggregation import LogAggregationService
from services.web.query.ai_assistant.log_tools.context import LogQueryContext
from services.web.query.ai_assistant.log_tools.schemas import (
    AgentSearchCondition,
    AggregateLogsRequest,
)
from services.web.query.ai_assistant.log_tools.statistics_sql import (
    StatisticsQuery,
    StatisticsSQLBuilder,
)


class TestStatisticsAutoPolicy(SimpleTestCase):
    """无FIELD的MCP也没有top_n，不能据此判断其为程序统计。"""

    def builder(self, *, program=False, with_field=True):
        """构造32天桶/745小时桶的整月范围，所有候选均满足测试容量。"""
        condition = AgentSearchCondition(
            scope_id="example",
            start_time="2026-01-01T00:00:00+08:00",
            end_time="2026-02-01T00:00:00+08:00",
        )
        dimensions = [dict(id="value", type="FIELD", field=dict(raw_name="action_id"))] if with_field else []
        dimensions.append(dict(id="time", type="TIME_BUCKET", field=dict(raw_name="start_time"), interval="AUTO"))
        request = AggregateLogsRequest(
            condition=condition, dimensions=dimensions, metrics=[dict(id="events", type="COUNT")]
        )
        if program:
            request = StatisticsQuery(condition=condition, dimensions=request.dimensions, metrics=request.metrics)
        context = LogQueryContext(
            username="tester", namespace="default", condition=condition, table="logs", conditions=()
        )
        return StatisticsSQLBuilder.from_request(context, request)

    def execute(self, builder):
        """只替换远端帧和权限边界，使用真实执行层规划与解析。"""
        with_field = bool(builder.dimensions)
        frames = [
            dict(frame="META", n="1", a="1", b="1", c="0", d="0", e="0"),
            dict(frame="GROUP", frame_key="1", kind="VALUE" if with_field else "ALL", n="1"),
            dict(frame="ROW", frame_key="1", bucket="0", n="1", m0="1"),
        ]
        if with_field:
            frames[1].update(d0_type="string", d0_json='"controlled"')
        responses = []
        if with_field:
            responses.append(({"list": [dict(group_count="1", invalid_type_count="0", invalid_number_count="0")]}, 0))
        responses.append(({"list": frames}, 0))
        with mock.patch.object(LogAggregationService, "_query", side_effect=responses), mock.patch(
            "services.web.query.ai_assistant.log_tools.aggregation.SensitiveLogFieldPermissionService.ensure_access"
        ):
            return LogAggregationService._execute(builder, numeric_columns=1, fill_time_buckets=True)

    def test_mcp_auto_uses_readability_with_and_without_field(self):
        for threshold in (12, 48):
            for with_field in (False, True):
                with self.subTest(threshold=threshold, with_field=with_field), override_settings(
                    AI_LOG_STATISTICS_AUTO_MIN_BUCKETS=threshold
                ):
                    result, axis, _ = self.execute(self.builder(with_field=with_field))
                    self.assertEqual(
                        (axis.effective_interval, len(axis.bucket_starts)),
                        ("DAY", 32) if threshold == 12 else ("HOUR", 745),
                    )
                    self.assertEqual(result.total_count, 1)

    def test_program_auto_reads_the_configured_readability_threshold(self):
        for threshold, interval, buckets in ((12, "DAY", 32), (48, "HOUR", 745)):
            with self.subTest(threshold=threshold), override_settings(AI_LOG_STATISTICS_AUTO_MIN_BUCKETS=threshold):
                result, axis, _ = self.execute(self.builder(program=True))
                self.assertEqual((axis.effective_interval, len(axis.bucket_starts)), (interval, buckets))
                self.assertEqual(sum(row["events"] for row in result.rows), 1)

    def test_implicit_sql_axis_uses_the_same_policy_as_execution(self):
        for threshold in (12, 48):
            for program, with_field in ((True, True), (False, True), (False, False)):
                with self.subTest(threshold=threshold, program=program, with_field=with_field), override_settings(
                    AI_LOG_STATISTICS_AUTO_MIN_BUCKETS=threshold
                ):
                    builder = self.builder(program=program, with_field=with_field)
                    builder.build_complete_sql()
                    expected = ("DAY", 32) if threshold == 12 else ("HOUR", 745)
                    self.assertEqual(
                        (builder.time_axis.effective_interval, len(builder.time_axis.bucket_starts)), expected
                    )
