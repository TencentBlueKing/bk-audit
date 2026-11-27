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

import datetime
from types import SimpleNamespace
from unittest import mock

from django.conf import settings
from django.test import TestCase, override_settings

from services.web.databus.collector.check.log_flow_sampler import (
    SAMPLE_CUSTOM_TYPES,
    STORAGE_TYPES,
    _to_seconds,
    build_storage_sql,
    get_result_table_id,
    sample_source,
    sample_storage,
)
from services.web.databus.constants import SourcePlatformChoices
from services.web.databus.tasks import (
    _build_flow_dimension,
    _build_flow_records,
    collector_log_flow_check,
)

API_BK_LOG = "services.web.databus.collector.check.log_flow_sampler.api.bk_log"
API_BK_BASE = "services.web.databus.collector.check.log_flow_sampler.api.bk_base"
SAMPLER_COLLECTOR_PLUGIN = "services.web.databus.collector.check.log_flow_sampler.CollectorPlugin"
SAMPLER_NOW_SECONDS = "services.web.databus.collector.check.log_flow_sampler._now_seconds"
GET_RESULT_TABLE_ID = "services.web.databus.collector.check.log_flow_sampler.get_result_table_id"
TASK_METRIC = "services.web.databus.tasks.Metric"
TASK_SAMPLE_SOURCE = "services.web.databus.tasks.sample_source"
TASK_SAMPLE_STORAGE = "services.web.databus.tasks.sample_storage"

RESULT_TABLE_ID = "2_bklog_app_audit_log"


def make_collector(
    collector_config_id=2178,
    collector_plugin_id=321,
    system_id="bk_audit",
    bk_data_id=1001,
    custom_type="log",
    source_platform="bk_log",
):
    """构造一个轻量采集项桩，仅暴露采样/SQL/维度用到的属性。"""
    return SimpleNamespace(
        collector_config_id=collector_config_id,
        collector_plugin_id=collector_plugin_id,
        system_id=system_id,
        bk_data_id=bk_data_id,
        custom_type=custom_type,
        source_platform=source_platform,
    )


class SamplerConstantsTests(TestCase):
    def test_first_phase_covers_log_and_otlp_log_only(self):
        self.assertEqual(SAMPLE_CUSTOM_TYPES, ("log", "otlp_log"))

    def test_first_phase_storage_is_doris_only(self):
        self.assertEqual(STORAGE_TYPES, ("doris",))


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


class GetResultTableIdTests(TestCase):
    @mock.patch(SAMPLER_COLLECTOR_PLUGIN)
    def test_resolves_by_collector_plugin_id(self, mock_plugin):
        mock_plugin.objects.filter.return_value.first.return_value = SimpleNamespace(result_table_id=RESULT_TABLE_ID)
        collector = make_collector(collector_plugin_id=321)

        self.assertEqual(get_result_table_id(collector), RESULT_TABLE_ID)
        mock_plugin.objects.filter.assert_called_once_with(collector_plugin_id=321)

    @mock.patch(SAMPLER_COLLECTOR_PLUGIN)
    def test_missing_plugin_returns_none(self, mock_plugin):
        mock_plugin.objects.filter.return_value.first.return_value = None

        self.assertIsNone(get_result_table_id(make_collector()))


class BuildStorageSqlTests(TestCase):
    def test_normal_sql(self):
        collector = make_collector()
        sql = build_storage_sql(collector, RESULT_TABLE_ID)
        self.assertIsNotNone(sql)
        self.assertIn("max(bk_receive_time) AS m", sql)
        self.assertIn(RESULT_TABLE_ID, sql)
        self.assertIn("collector_config_id = 2178", sql)
        # thedate 用 Python 算出的整型字面量（7 天前的 %Y%m%d）
        self.assertRegex(sql, r"thedate >= \d{8}")

    def test_invalid_table_id_returns_none(self):
        self.assertIsNone(build_storage_sql(make_collector(), "bad;table"))
        self.assertIsNone(build_storage_sql(make_collector(), ""))

    def test_cutoff_is_7_days_ago(self):
        now = datetime.datetime(2026, 11, 18, 12, 0, 0)
        collector = make_collector()
        sql = build_storage_sql(collector, RESULT_TABLE_ID, now=now)
        expected = (now - datetime.timedelta(days=settings.LOG_FLOW_STORAGE_LOOKBACK_DAYS)).strftime("%Y%m%d")
        self.assertIn(f"thedate >= {int(expected)}", sql)


class SampleSourceTests(TestCase):
    @mock.patch(SAMPLER_NOW_SECONDS, return_value=1794556400)
    @mock.patch(f"{API_BK_LOG}.get_collector_tail_log")
    def test_tail_ok(self, mock_tail, _mock_now):
        T = 1794556370
        mock_tail.return_value = [
            {
                "origin": {"time": T, "datetime": "2026-11-13 15:51:14"},
                "start_time": 1794556000,
                "time": 1794556000,
                "dtEventTimeStamp": 1794556000,
            }
        ]
        collector = make_collector()
        result = sample_source(collector)
        self.assertEqual(result["query_ok"], 1)
        self.assertEqual(result["receive_time"], T)
        self.assertEqual(result["age_seconds"], 30)

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
    def test_tail_unordered_uses_max_valid_origin_time(self, mock_tail):
        mock_tail.return_value = [
            {"origin": {"time": 1794556370}},
            {"origin": {"time": "abc"}},
            {"origin": {"time": None}},
            {"origin": {"time": 0}},
            {"origin": {"time": 1794556400}},
        ]
        result = sample_source(make_collector())
        self.assertEqual(result["query_ok"], 1)
        self.assertEqual(result["receive_time"], 1794556400)

    @mock.patch(f"{API_BK_LOG}.get_collector_tail_log")
    def test_no_valid_origin_time_keeps_query_ok(self, mock_tail):
        mock_tail.return_value = [
            {"origin": {"datetime": "2026-11-13 15:51:14"}},
            {"start_time": 1794556400, "time": 1794556400, "dtEventTimeStamp": 1794556400},
        ]
        result = sample_source(make_collector())
        self.assertEqual(result["query_ok"], 1)
        self.assertIsNone(result["receive_time"])
        self.assertIsNone(result["age_seconds"])


class SampleStorageTests(TestCase):
    @override_settings(LOG_FLOW_STORAGE_QUERY_TIMEOUT=25)
    def test_storage_ok_with_lag(self):
        T2 = 1794556310
        with mock.patch(GET_RESULT_TABLE_ID, return_value=RESULT_TABLE_ID) as mock_get_rt, mock.patch(
            f"{API_BK_BASE}.query_sync"
        ) as mock_qs:
            mock_qs.return_value = {"list": [{"m": T2}]}
            collector = make_collector()
            result = sample_storage(collector, "doris")

            self.assertEqual(result["query_ok"], 1)
            self.assertEqual(result["has_watermark"], 1)
            self.assertEqual(result["receive_time"], T2)
            mock_get_rt.assert_called_once_with(collector)
            call_kwargs = mock_qs.call_args.kwargs
            self.assertEqual(call_kwargs["prefer_storage"], "doris")
            self.assertEqual(call_kwargs["request_timeout"], 25)
            self.assertIn(RESULT_TABLE_ID, call_kwargs["sql"])

    def test_storage_no_watermark(self):
        with mock.patch(GET_RESULT_TABLE_ID, return_value=RESULT_TABLE_ID), mock.patch(
            f"{API_BK_BASE}.query_sync"
        ) as mock_qs:
            mock_qs.return_value = {"list": [{"m": None}]}
            result = sample_storage(make_collector(), "doris")
            self.assertEqual(result["query_ok"], 1)
            self.assertEqual(result["has_watermark"], 0)
            self.assertIsNone(result["receive_time"])

    def test_storage_raises(self):
        with mock.patch(GET_RESULT_TABLE_ID, return_value=RESULT_TABLE_ID), mock.patch(
            f"{API_BK_BASE}.query_sync"
        ) as mock_qs:
            mock_qs.side_effect = RuntimeError("boom")
            result = sample_storage(make_collector(), "doris")
            self.assertEqual(result["query_ok"], 0)
            self.assertEqual(result["has_watermark"], 0)
            self.assertIsNone(result["receive_time"])

    def test_invalid_table_no_query_called(self):
        with mock.patch(GET_RESULT_TABLE_ID, return_value="bad table"), mock.patch(
            f"{API_BK_BASE}.query_sync"
        ) as mock_qs:
            result = sample_storage(make_collector(), "doris")
            self.assertEqual(result["query_ok"], 0)
            mock_qs.assert_not_called()

    def test_missing_plugin_no_query_called(self):
        with mock.patch(GET_RESULT_TABLE_ID, return_value=None), mock.patch(f"{API_BK_BASE}.query_sync") as mock_qs:
            result = sample_storage(make_collector(), "doris")
            self.assertEqual(result["query_ok"], 0)
            mock_qs.assert_not_called()

    def test_unsupported_storage_type_no_query_called(self):
        with mock.patch(GET_RESULT_TABLE_ID, return_value=RESULT_TABLE_ID), mock.patch(
            f"{API_BK_BASE}.query_sync"
        ) as mock_qs:
            result = sample_storage(make_collector(), "hdfs")
            self.assertEqual(result["query_ok"], 0)
            self.assertEqual(result["has_watermark"], 0)
            mock_qs.assert_not_called()


class BuildFlowRecordsTests(TestCase):
    def test_negative_lag_reported_as_is(self):
        collector = make_collector()
        source = {"query_ok": 1, "receive_time": 1794556370, "age_seconds": 30}
        storage = {"query_ok": 1, "has_watermark": 1, "receive_time": 1794556400}
        records = _build_flow_records(collector, source, "doris", storage)
        metrics = records[0]["metrics"]
        # 源端比存储旧 -> lag 为负，原样上报
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

    def test_lag_requires_both_queries_ok(self):
        collector = make_collector()
        storage = {"query_ok": 1, "has_watermark": 1, "receive_time": 1794556310}
        source_failed = {"query_ok": 0, "receive_time": 1794556370, "age_seconds": 30}
        records = _build_flow_records(collector, source_failed, "doris", storage)
        self.assertNotIn("log_collect_lag_seconds", records[0]["metrics"])

        source_ok = {"query_ok": 1, "receive_time": 1794556370, "age_seconds": 30}
        storage_failed = {"query_ok": 0, "has_watermark": 0, "receive_time": 1794556310}
        records = _build_flow_records(collector, source_ok, "doris", storage_failed)
        self.assertNotIn("log_collect_lag_seconds", records[0]["metrics"])

    def test_bk_data_id_none_dimension_empty(self):
        collector = make_collector(bk_data_id=None)
        dimension = _build_flow_dimension(collector)
        self.assertEqual(dimension["bk_data_id"], "")
        self.assertEqual(dimension["collector_config_id"], "2178")


class CollectorLogFlowCheckTests(TestCase):
    """整轮任务：覆盖采样范围、Doris-only、缺值不补 0、记录数与未配置跳过。"""

    @override_settings(LOG_EXPORT_STATUS_DATA_ID=1, LOG_EXPORT_STATUS_ACCESS_TOKEN="token")
    def test_full_round_record_count_and_isolation(self):
        collector = make_collector()
        source = {"query_ok": 1, "receive_time": 1794556370, "age_seconds": 30}
        doris = {"query_ok": 1, "has_watermark": 1, "receive_time": 1794556310}

        with (
            mock.patch("services.web.databus.tasks.CollectorConfig") as mock_model,
            mock.patch(TASK_SAMPLE_SOURCE, return_value=source) as mock_src,
            mock.patch(TASK_SAMPLE_STORAGE, return_value=doris) as mock_st,
            mock.patch(TASK_METRIC) as mock_metric,
        ):
            mock_model.objects.filter.return_value = [collector]
            collector_log_flow_check()

            mock_model.objects.filter.assert_called_once_with(
                source_platform=SourcePlatformChoices.BKLOG.value,
                custom_type__in=SAMPLE_CUSTOM_TYPES,
            )
            self.assertEqual(mock_src.call_count, 1)
            self.assertEqual(mock_st.call_count, len(STORAGE_TYPES))
            called_types = [call.args[1] for call in mock_st.call_args_list]
            self.assertEqual(called_types, list(STORAGE_TYPES))

            self.assertTrue(mock_metric.called)
            built = mock_metric.call_args.kwargs["records"]
            # 1 个采集项：源端 1 条 + doris 1 条 + 心跳 1 条 = 3
            self.assertEqual(len(built), 3)
            source_record = next(r for r in built if "log_collect_source_query_ok" in r["metrics"])
            self.assertEqual(
                source_record["metrics"],
                {
                    "log_collect_source_query_ok": 1,
                    "log_collect_source_receive_time": 1794556370,
                    "log_collect_source_age_seconds": 30,
                },
            )

    @override_settings(LOG_EXPORT_STATUS_DATA_ID=1, LOG_EXPORT_STATUS_ACCESS_TOKEN="token")
    def test_no_watermark_keeps_query_ok_and_omits_metrics(self):
        collector = make_collector()
        source = {"query_ok": 1, "receive_time": None, "age_seconds": None}
        doris = {"query_ok": 1, "has_watermark": 0, "receive_time": None}

        with (
            mock.patch("services.web.databus.tasks.CollectorConfig") as mock_model,
            mock.patch(TASK_SAMPLE_SOURCE, return_value=source),
            mock.patch(TASK_SAMPLE_STORAGE, return_value=doris),
            mock.patch(TASK_METRIC) as mock_metric,
        ):
            mock_model.objects.filter.return_value = [collector]
            collector_log_flow_check()

            built = mock_metric.call_args.kwargs["records"]
            source_record = next(r for r in built if "log_collect_source_query_ok" in r["metrics"])
            storage_record = next(r for r in built if "storage_type" in r["dimension"])
            self.assertEqual(source_record["metrics"], {"log_collect_source_query_ok": 1})
            self.assertEqual(
                storage_record["metrics"],
                {
                    "log_collect_storage_query_ok": 1,
                    "log_collect_storage_has_watermark": 0,
                },
            )

    @override_settings(LOG_EXPORT_STATUS_DATA_ID=0, LOG_EXPORT_STATUS_ACCESS_TOKEN="")
    def test_metric_skipped_when_unconfigured(self):
        collector = make_collector()
        source = {"query_ok": 0, "receive_time": None, "age_seconds": None}
        doris = {"query_ok": 0, "has_watermark": 0, "receive_time": None}
        with (
            mock.patch("services.web.databus.tasks.CollectorConfig") as mock_model,
            mock.patch(TASK_SAMPLE_SOURCE, return_value=source),
            mock.patch(TASK_SAMPLE_STORAGE, return_value=doris),
            mock.patch(TASK_METRIC) as mock_metric,
            mock.patch("services.web.databus.tasks.logger") as mock_logger,
        ):
            mock_model.objects.filter.return_value = [collector]
            collector_log_flow_check()
            mock_logger.warning.assert_any_call("[CollectorLogFlowCheck] metric skipped, data_id/access_token unset")
            mock_metric.assert_not_called()

    @override_settings(LOG_EXPORT_STATUS_DATA_ID=1, LOG_EXPORT_STATUS_ACCESS_TOKEN="token")
    def test_two_collectors_record_count(self):
        c1 = make_collector(collector_config_id=2178)
        c2 = make_collector(collector_config_id=2179)
        source = {"query_ok": 1, "receive_time": 1794556370, "age_seconds": 30}
        storage = {"query_ok": 1, "has_watermark": 1, "receive_time": 1794556310}
        with (
            mock.patch("services.web.databus.tasks.CollectorConfig") as mock_model,
            mock.patch(TASK_SAMPLE_SOURCE, return_value=source),
            mock.patch(TASK_SAMPLE_STORAGE, return_value=storage) as mock_st,
            mock.patch(TASK_METRIC) as mock_metric,
        ):
            mock_model.objects.filter.return_value = [c1, c2]
            collector_log_flow_check()
            self.assertEqual(mock_metric.call_count, 1)
            self.assertEqual(mock_st.call_count, 2)
            built = mock_metric.call_args.kwargs["records"]
            # 2×(1 源端 + 1 Doris 存储) + 1 心跳 = 5
            self.assertEqual(len(built), 5)

    @override_settings(LOG_EXPORT_STATUS_DATA_ID=1, LOG_EXPORT_STATUS_ACCESS_TOKEN="token")
    def test_source_failure_continues_round(self):
        c1 = make_collector(collector_config_id=2178)
        c2 = make_collector(collector_config_id=2179)
        source = {"query_ok": 1, "receive_time": 1794556370, "age_seconds": 30}
        storage = {"query_ok": 1, "has_watermark": 1, "receive_time": 1794556310}
        with (
            mock.patch("services.web.databus.tasks.CollectorConfig") as mock_model,
            mock.patch(TASK_SAMPLE_SOURCE, side_effect=[RuntimeError("boom"), source]),
            mock.patch(TASK_SAMPLE_STORAGE, return_value=storage),
            mock.patch(TASK_METRIC) as mock_metric,
        ):
            mock_model.objects.filter.return_value = [c1, c2]
            collector_log_flow_check()

            built = mock_metric.call_args.kwargs["records"]
            heartbeat = next(r for r in built if "log_collect_check_heartbeat" in r["metrics"])
            self.assertEqual(heartbeat["metrics"]["log_collect_collector_total"], 2)
            self.assertEqual(heartbeat["metrics"]["log_collect_collector_failed"], 1)
            # 失败项不产生源端/存储记录；成功项 2 条 + 心跳 1 条 = 3
            self.assertEqual(len(built), 3)
