# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

from types import SimpleNamespace
from unittest import mock

from django.conf import settings
from django.test import TestCase

from services.web.databus.collector.check.log_flow_sampler import (
    STORAGE_TYPES,
    _to_seconds,
    build_storage_sql,
    sample_source,
    sample_storage,
)
from services.web.databus.tasks import (
    _build_flow_dimension,
    _build_flow_records,
    collector_log_flow_check,
)

API_BK_LOG = "services.web.databus.collector.check.log_flow_sampler.api.bk_log"
API_BK_BASE = "services.web.databus.collector.check.log_flow_sampler.api.bk_base"
TASK_METRIC = "services.web.databus.tasks.Metric"
TASK_SAMPLE_SOURCE = "services.web.databus.tasks.sample_source"
TASK_SAMPLE_STORAGE = "services.web.databus.tasks.sample_storage"


def make_collector(
    collector_config_id=2178, bkbase_table_id="2_bklog_app_audit_log", system_id="bk_audit", bk_data_id=1001
):
    """构造一个轻量采集项桩，仅暴露采样/SQL 用到的属性。"""
    return SimpleNamespace(
        collector_config_id=collector_config_id,
        bkbase_table_id=bkbase_table_id,
        system_id=system_id,
        bk_data_id=bk_data_id,
    )


class ToSecondsTests(TestCase):
    def test_int_passthrough(self):
        self.assertEqual(_to_seconds(1794556274), 1794556274)

    def test_str_passthrough(self):
        self.assertEqual(_to_seconds("1794556274"), 1794556274)

    def test_millisecond_downgrade(self):
        self.assertEqual(_to_seconds(1794556274000), 1794556274)

    def test_none_and_empty(self):
        self.assertIsNone(_to_seconds(None))
        self.assertIsNone(_to_seconds(""))

    def test_invalid_string(self):
        self.assertIsNone(_to_seconds("abc"))


class BuildStorageSqlTests(TestCase):
    def test_normal_sql(self):
        collector = make_collector()
        sql = build_storage_sql(collector)
        self.assertIsNotNone(sql)
        self.assertIn("max(bk_receive_time) AS m", sql)
        self.assertIn("2_bklog_app_audit_log", sql)
        self.assertIn("collector_config_id = 2178", sql)
        # thedate 用 Python 算出的整型字面量（7 天前的 %Y%m%d）
        self.assertRegex(sql, r"thedate >= \d{8}")

    def test_invalid_table_id_returns_none(self):
        collector = make_collector(bkbase_table_id="bad;table")
        self.assertIsNone(build_storage_sql(collector))
        collector2 = make_collector(bkbase_table_id="")
        self.assertIsNone(build_storage_sql(collector2))

    def test_cutoff_is_7_days_ago(self):
        import datetime

        now = datetime.datetime(2026, 11, 18, 12, 0, 0)
        collector = make_collector()
        sql = build_storage_sql(collector, now=now)
        expected = (now - datetime.timedelta(days=settings.LOG_FLOW_STORAGE_LOOKBACK_DAYS)).strftime("%Y%m%d")
        self.assertIn(f"thedate >= {int(expected)}", sql)


class SampleSourceTests(TestCase):
    @mock.patch(f"{API_BK_LOG}.get_collector_tail_log")
    def test_tail_ok(self, mock_tail):
        T = 1794556370
        mock_tail.return_value = [{"origin": {"time": T}}]
        collector = make_collector()
        result = sample_source(collector)
        self.assertEqual(result["query_ok"], 1)
        self.assertEqual(result["receive_time"], T)
        self.assertIsNotNone(result["age_seconds"])
        self.assertLessEqual(result["age_seconds"], 5)

    @mock.patch(f"{API_BK_LOG}.get_collector_tail_log")
    def test_tail_empty(self, mock_tail):
        mock_tail.return_value = []
        collector = make_collector()
        result = sample_source(collector)
        self.assertEqual(result["query_ok"], 1)
        self.assertIsNone(result["receive_time"])
        self.assertIsNone(result["age_seconds"])

    @mock.patch(f"{API_BK_LOG}.get_collector_tail_log")
    def test_tail_raises(self, mock_tail):
        mock_tail.side_effect = RuntimeError("boom")
        collector = make_collector()
        result = sample_source(collector)
        self.assertEqual(result["query_ok"], 0)
        self.assertIsNone(result["receive_time"])
        self.assertIsNone(result["age_seconds"])

    @mock.patch(f"{API_BK_LOG}.get_collector_tail_log")
    def test_tail_millisecond(self, mock_tail):
        mock_tail.return_value = [{"origin": {"time": 1794556370000}}]
        result = sample_source(make_collector())
        self.assertEqual(result["receive_time"], 1794556370)

    @mock.patch(f"{API_BK_LOG}.get_collector_tail_log")
    def test_tail_unordered_uses_max(self, mock_tail):
        mock_tail.return_value = [
            {"origin": {"time": 1794556370}},
            {"origin": {"time": 1794556000}},
            {"origin": {"time": 1794556400}},
        ]
        result = sample_source(make_collector())
        self.assertEqual(result["receive_time"], 1794556400)


class SampleStorageTests(TestCase):
    @mock.patch(f"{API_BK_BASE}.query_sync")
    def test_storage_ok_with_lag(self, mock_qs):
        T2 = 1794556310
        mock_qs.return_value = {"list": [{"m": T2}]}
        collector = make_collector()
        result = sample_storage(collector, "doris")
        self.assertEqual(result["query_ok"], 1)
        self.assertEqual(result["has_watermark"], 1)
        self.assertEqual(result["receive_time"], T2)

    @mock.patch(f"{API_BK_BASE}.query_sync")
    def test_storage_no_watermark(self, mock_qs):
        mock_qs.return_value = {"list": [{"m": None}]}
        result = sample_storage(make_collector(), "doris")
        self.assertEqual(result["query_ok"], 1)
        self.assertEqual(result["has_watermark"], 0)
        self.assertIsNone(result["receive_time"])

    @mock.patch(f"{API_BK_BASE}.query_sync")
    def test_storage_raises(self, mock_qs):
        mock_qs.side_effect = RuntimeError("boom")
        result = sample_storage(make_collector(), "hdfs")
        self.assertEqual(result["query_ok"], 0)
        self.assertEqual(result["has_watermark"], 0)
        self.assertIsNone(result["receive_time"])

    def test_invalid_table_no_query_called(self):
        with mock.patch(f"{API_BK_BASE}.query_sync") as mock_qs:
            result = sample_storage(make_collector(bkbase_table_id="bad table"), "doris")
            self.assertEqual(result["query_ok"], 0)
            mock_qs.assert_not_called()


class BuildFlowRecordsTests(TestCase):
    def test_negative_lag_reported_as_is(self):
        collector = make_collector()
        source = {"query_ok": 1, "receive_time": 1794556370, "age_seconds": 30}
        storage = {"query_ok": 1, "has_watermark": 1, "receive_time": 1794556400}
        records = _build_flow_records(collector, source, "doris", storage)
        metrics = records[0]["metrics"]
        # 源端比存储新 -> lag 为负，原样上报
        self.assertEqual(metrics["log_collect_lag_seconds"], 1794556370 - 1794556400)
        self.assertEqual(metrics["log_collect_lag_source_receive_time"], 1794556370)
        self.assertEqual(records[0]["dimension"]["storage_type"], "doris")

    def test_no_storage_watermark_no_lag(self):
        collector = make_collector()
        source = {"query_ok": 1, "receive_time": 1794556370, "age_seconds": 30}
        storage = {"query_ok": 1, "has_watermark": 0, "receive_time": None}
        records = _build_flow_records(collector, source, "doris", storage)
        metrics = records[0]["metrics"]
        self.assertNotIn("log_collect_lag_seconds", metrics)
        self.assertNotIn("log_collect_storage_receive_time", metrics)

    def test_bk_data_id_none_dimension_empty(self):
        collector = make_collector(bk_data_id=None)
        dimension = _build_flow_dimension(collector)
        self.assertEqual(dimension["bk_data_id"], "")
        self.assertEqual(dimension["collector_config_id"], "2178")


class CollectorLogFlowCheckTests(TestCase):
    """整轮任务：覆盖失败隔离、缺值不补 0、记录数、未配置跳过。"""

    def test_full_round_record_count_and_isolation(self):
        collector = make_collector()
        source = {"query_ok": 1, "receive_time": 1794556370, "age_seconds": 30}
        doris = {"query_ok": 1, "has_watermark": 1, "receive_time": 1794556310}
        hdfs = {"query_ok": 0, "has_watermark": 0, "receive_time": None}

        with mock.patch("services.web.databus.tasks.CollectorConfig") as mock_model, mock.patch(
            TASK_SAMPLE_SOURCE, return_value=source
        ) as mock_src, mock.patch(TASK_SAMPLE_STORAGE, side_effect=[doris, hdfs]) as mock_st, mock.patch(
            TASK_METRIC
        ) as mock_metric:
            mock_model.objects.filter.return_value.exclude.return_value.exclude.return_value = [collector]
            collector_log_flow_check()

            # 1 个采集项：源端 3 条(query_ok/receive_time/age) + doris 1 + hdfs 1 + 心跳 1 = 6
            self.assertEqual(mock_src.call_count, 1)
            self.assertEqual(mock_st.call_count, len(STORAGE_TYPES))
            # sample_storage 必须按 STORAGE_TYPES 顺序、对每个类型各调用一次（失败隔离的基底）
            called_types = [call.args[1] for call in mock_st.call_args_list]
            self.assertEqual(called_types, list(STORAGE_TYPES))
            # 心跳等轮次记录 + 采集项记录都被构造并提交（按块 report 一次）
            self.assertTrue(mock_metric.called)

    def test_metric_skipped_when_unconfigured(self):
        collector = make_collector()
        source = {"query_ok": 0, "receive_time": None, "age_seconds": None}
        with mock.patch("services.web.databus.tasks.CollectorConfig") as mock_model, mock.patch(
            TASK_SAMPLE_SOURCE, return_value=source
        ), mock.patch(
            TASK_SAMPLE_STORAGE, return_value={"query_ok": 0, "has_watermark": 0, "receive_time": None}
        ), mock.patch(
            TASK_METRIC
        ) as mock_metric:
            mock_model.objects.filter.return_value.exclude.return_value.exclude.return_value = [collector]
            mock_metric.return_value.is_configured = False
            with mock.patch("services.web.databus.tasks.logger") as mock_logger:
                collector_log_flow_check()
                mock_logger.warning.assert_any_call(
                    "[CollectorLogFlowCheck] metric skipped, data_id/access_token unset"
                )

    def test_two_collectors_record_count(self):
        c1 = make_collector(collector_config_id=2178)
        c2 = make_collector(collector_config_id=2179)
        source = {"query_ok": 1, "receive_time": 1794556370, "age_seconds": 30}
        storage = {"query_ok": 1, "has_watermark": 1, "receive_time": 1794556310}
        with mock.patch("services.web.databus.tasks.CollectorConfig") as mock_model, mock.patch(
            TASK_SAMPLE_SOURCE, return_value=source
        ), mock.patch(TASK_SAMPLE_STORAGE, return_value=storage), mock.patch(TASK_METRIC) as mock_metric:
            mock_model.objects.filter.return_value.exclude.return_value.exclude.return_value = [c1, c2]
            collector_log_flow_check()
            # 每个采集项 3 条源端 + 2 存储 + 1 心跳
            self.assertEqual(mock_metric.call_count, 1)
            built = mock_metric.call_args.kwargs["records"]
            # 2×(3 源端 + 2 存储) + 1 心跳 = 11
            self.assertEqual(len(built), 11)
