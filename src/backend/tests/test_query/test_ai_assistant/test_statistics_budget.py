"""时间轴与预算边界使用手算期望，防止闭区间漏桶和多列预算低估。"""
from django.test import SimpleTestCase, override_settings

from services.web.query.ai_assistant.exceptions import StatisticsBudgetExceeded
from services.web.query.ai_assistant.log_tools.statistics_budget import build_time_axis


class TestStatisticsBudget(SimpleTestCase):
    def axis(self, **kwargs):
        """构造整点闭区间，所有预算输入允许单独覆盖。"""
        params = dict(
            start_time="2026-09-15T10:00:00+08:00",
            end_time="2026-09-15T11:00:00+08:00",
            interval="HOUR",
            group_count=1,
            numeric_columns=3,
        )
        params.update(kwargs)
        return build_time_axis(**params)

    def test_closed_interval_keeps_terminal_bucket_and_partial_first_bucket(self):
        axis = self.axis(start_time="2026-09-15T10:25:01+08:00")
        self.assertEqual(axis.bucket_starts, ("2026-09-15T10:00:00+08:00", "2026-09-15T11:00:00+08:00"))
        self.assertEqual(axis.effective_interval, "HOUR")
        self.assertEqual(axis.timezone, "Asia/Shanghai")

    def test_auto_uses_actual_groups_and_all_numeric_columns(self):
        self.assertEqual(self.axis(interval="AUTO", group_count=500, numeric_columns=3).effective_interval, "MINUTE")
        self.assertEqual(self.axis(interval="AUTO", group_count=500, numeric_columns=4).effective_interval, "HOUR")
        self.assertEqual(self.axis(interval="AUTO", group_count=500, numeric_columns=1).effective_interval, "MINUTE")

    @override_settings(AI_LOG_AGGREGATION_MAX_CELLS=12)
    def test_exact_cells_pass_but_explicit_overflow_only_suggests(self):
        self.assertEqual(len(self.axis(group_count=2).bucket_starts), 2)
        with self.assertRaises(StatisticsBudgetExceeded) as caught:
            self.axis(group_count=3)
        self.assertEqual(caught.exception.data["suggested_interval"], "DAY")

    @override_settings(AI_LOG_AGGREGATION_MAX_TIME_BUCKETS=60)
    def test_closed_minute_range_is_61_buckets_not_60(self):
        with self.assertRaises(StatisticsBudgetExceeded) as caught:
            self.axis(interval="MINUTE")
        self.assertEqual(caught.exception.data["suggested_interval"], "HOUR")

    @override_settings(AI_LOG_AGGREGATION_MAX_CELLS=2)
    def test_no_time_is_one_bucket_and_empty_category_has_no_cells(self):
        self.assertEqual(self.axis(interval=None, group_count=0).bucket_starts, (None,))
        with self.assertRaises(StatisticsBudgetExceeded):
            self.axis(interval=None)

    @override_settings(TIME_ZONE="UTC")
    def test_timezone_is_server_timezone_not_input_offset(self):
        self.assertEqual(self.axis().bucket_starts, ("2026-09-15T02:00:00+00:00", "2026-09-15T03:00:00+00:00"))

    def test_hard_bucket_and_cell_limits_cannot_be_raised_by_settings(self):
        with override_settings(AI_LOG_AGGREGATION_MAX_TIME_BUCKETS=999999, AI_LOG_AGGREGATION_MAX_CELLS=999999):
            with self.assertRaises(StatisticsBudgetExceeded):
                self.axis(interval="MINUTE", end_time="2026-09-16T10:00:00+08:00")
            self.assertEqual(
                self.axis(interval="HOUR", group_count=50000, numeric_columns=1).effective_interval, "HOUR"
            )
            with self.assertRaises(StatisticsBudgetExceeded):
                self.axis(interval="HOUR", group_count=50001, numeric_columns=1)

    @override_settings(TIME_ZONE="America/New_York")
    def test_fall_back_hour_preserves_both_real_hours_and_local_midnights(self):
        axis = self.axis(start_time="2026-11-01T00:30:00-04:00", end_time="2026-11-01T02:00:00-05:00")
        self.assertEqual(
            axis.bucket_starts,
            (
                "2026-11-01T00:00:00-04:00",
                "2026-11-01T01:00:00-04:00",
                "2026-11-01T01:00:00-05:00",
                "2026-11-01T02:00:00-05:00",
            ),
        )
        axis = self.axis(interval="DAY", start_time="2026-10-31T12:00:00-04:00", end_time="2026-11-02T00:00:00-05:00")
        self.assertEqual(
            axis.bucket_starts, ("2026-10-31T00:00:00-04:00", "2026-11-01T00:00:00-04:00", "2026-11-02T00:00:00-05:00")
        )
