"""V4原生相对调度、存量窗口保护与完整离线部署参数。"""
from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, override_settings

from services.web.analyze import utils as analyze_utils
from services.web.analyze.constants import FlowDataSourceNodeType as NodeType
from services.web.analyze.controls.rule_audit import RuleAuditController
from services.web.analyze.storage_node import HDFSStorageNode
from services.web.bkbase import flow
from services.web.bkbase.exceptions import BKBaseResourceMappingError


def offsets(start=0, end=1, unit="hour"):
    return {
        "window_start_offset": start,
        "window_start_offset_unit": unit,
        "window_end_offset": end,
        "window_end_offset_unit": unit,
    }


@override_settings(BKBASE_API_VERSION="v4", TIME_ZONE="Asia/Shanghai")
class InitialBatchScheduleTests(SimpleTestCase):
    def setUp(self):
        self.context = {"version": "v4", "tenant": "default", "namespace": "audit", "rt_namespaces": {}}
        self.enterContext(
            mock.patch("requests.sessions.Session.request", side_effect=AssertionError("unexpected HTTP"))
        )
        self.profile = {"operation_config": {"batch_sql_deploy_config": {"cluster": "synthetic_batch"}}}
        self.strategy = SimpleNamespace(
            strategy_id=390,
            strategy_name="synthetic",
            namespace="default",
            backend_data={},
            sql="SELECT * FROM 47_input WHERE dtEventTimeStamp >= 42",
            configs={"data_source": {"source_type": NodeType.BATCH_REAL}},
        )
        self.controller = SimpleNamespace(
            strategy=self.strategy,
            rt_ids=["47_input"],
            raw_table_name="synthetic_output",
            rt_node_map={"47_input": "source"},
            storage_nodes=[HDFSStorageNode],
            check_source_type=lambda rt: NodeType.BATCH_REAL,
        )
        self.controller._build_sql_node_config = lambda biz: RuleAuditController._build_sql_node_config(
            self.controller, biz
        )
        self.enterContext(
            mock.patch.object(HDFSStorageNode, "cluster", new_callable=mock.PropertyMock, return_value="legacy_hdfs")
        )
        self.enterContext(
            mock.patch.object(flow.storage_service, "resolve_storage_cluster", return_value=self.storage_ref())
        )
        self.existing = []

    def storage_ref(self, kind="Hdfs"):
        return {"kind": kind, "tenant": "default", "namespace": "clusters", "name": "synthetic_storage"}

    def freeze(self, value):
        clock = SimpleNamespace(datetime=mock.Mock(wraps=datetime), timedelta=timedelta)
        clock.datetime.now.return_value = datetime.fromisoformat(value)
        return mock.patch.object(analyze_utils, "datetime", clock)

    def graph(self):
        with mock.patch.object(
            flow, "_controller_flow_nodes", side_effect=lambda *a: deepcopy(self.existing)
        ), mock.patch.object(
            flow,
            "_input_result_table_refs",
            return_value={
                rt: {"kind": "ResultTable", "tenant": "default", "namespace": "inputs", "name": rt}
                for rt in self.controller.rt_ids
            },
        ), mock.patch.object(
            flow.metadata_service,
            "get_result_tables",
            return_value=[{"result_table_id": rt, "bk_biz_id": 47} for rt in self.controller.rt_ids],
        ), mock.patch.object(
            flow.GlobalMetaConfig, "get", return_value=self.profile
        ), mock.patch.object(
            flow, "_save_operation_binding"
        ):
            return flow.build_controller_spec(self.controller, context=self.context)

    @staticmethod
    def sql_node(graph):
        return next(node for node in graph["nodes"] if node["kind"] == "BatchSqlNode")

    def configure_schedule(self, period="hour", frequency=1):
        self.strategy.configs["schedule_config"] = {"schedule_period": period, "count_freq": frequency}

    def configured_window(self, period="day", frequency=1, window_type="scroll", start=7, end=8):
        self.profile.setdefault("batch_window_offsets", {})[f"{window_type}:{frequency}:{period}:0:hour"] = offsets(
            start, end
        )

    def test_native_hour_and_day_do_not_capture_build_wall_time(self):
        self.configured_window()
        for period, anchor in (("hour", 1), ("day", 0)):
            self.configure_schedule(period)
            for now in ("2026-11-19 16:30:00", "2026-11-19 23:59:59", "2026-12-31 00:00:00"):
                with self.subTest(period=period, now=now), self.freeze(now):
                    graph = self.graph()
                node = self.sql_node(graph)
                self.assertEqual(
                    node["dedicated_config"]["schedule_config"],
                    {"count_freq": 1, "schedule_period": period, "start_time": anchor},
                )
                self.assertEqual(node["processing_info"], self.strategy.sql)
                self.assertEqual(
                    node["dedicated_config"]["output_config"],
                    {
                        "enable_customize_output": False,
                        "output_baseline_location": "start",
                        "output_offset": 0,
                        "output_offset_unit": "hour",
                        "output_baseline_type": "schedule_time",
                        "output_baseline": "schedule_time",
                    },
                )

    def test_fixed_policy_and_legacy_time_do_not_override_native_start_or_mutate_payload(self):
        self.profile["batch_schedules"] = {"hour:1": {"start_time": 1795078800000}}
        old = self.controller._build_sql_node_config(47)
        old["dedicated_config"]["schedule_config"]["start_time"] = "unused legacy timestamp"
        original = deepcopy(old)
        self.assertEqual(
            flow._batch_node(self.controller, old, self.profile)["dedicated_config"]["schedule_config"]["start_time"], 1
        )
        self.assertEqual(old, original)

    def test_unknown_schedule_period_is_not_guessed(self):
        self.configure_schedule("week")
        with self.assertRaisesMessage(BKBaseResourceMappingError, "schedule period"):
            self.graph()

    def test_hourly_new_scroll_and_whole_use_only_the_confirmed_combination(self):
        for source, expected in ((NodeType.BATCH_REAL, "scroll"), (NodeType.BATCH, "whole")):
            self.controller.check_source_type = lambda rt: source
            with self.subTest(source=source):
                window = self.sql_node(self.graph())["windows_info"][0]
                self.assertEqual(window["window_type"], expected)
                self.assertEqual({k: window[k] for k in offsets()}, offsets())
                self.assertEqual(window["window_size_unit"], "hour")
                self.assertEqual(window["dependency_rule"], "no_failed")

    def test_explicit_hourly_override_is_respected_and_bad_override_never_falls_back(self):
        self.configured_window("hour", start=-2, end=-1)
        self.assertEqual(self.sql_node(self.graph())["windows_info"][0]["window_end_offset"], -1)
        self.profile["batch_window_offsets"]["scroll:1:hour:0:hour"] = {}
        with self.assertRaisesMessage(BKBaseResourceMappingError, "batch window boundaries"):
            self.graph()

    def test_day_multi_hour_and_nonzero_offset_have_no_inferred_defaults(self):
        for period, count, offset_unit in (
            ("day", 1, "hour"),
            ("hour", 2, "hour"),
            ("hour", 12, "hour"),
            ("hour", 1, "day"),
        ):
            self.configure_schedule(period, count)
            self.strategy.configs["schedule_config"]["window_offset_unit"] = offset_unit
            with self.subTest(period=period, count=count, unit=offset_unit), self.assertRaisesMessage(
                BKBaseResourceMappingError, "batch window boundaries"
            ):
                self.graph()
        self.configure_schedule("hour", 2)
        self.configured_window("hour", 2, start=3, end=4)
        node = self.sql_node(self.graph())
        self.assertEqual(node["dedicated_config"]["schedule_config"]["start_time"], 1)
        self.assertEqual(node["windows_info"][0]["window_end_offset"], 4)

    def existing_graph(self, period="hour", anchor=1):
        self.configure_schedule(period)
        if period == "day":
            self.configured_window()
        graph = self.graph()
        node = self.sql_node(graph)
        node["name"] = "migrated_compute"
        for item in graph["nodes"]:
            if item.get("input"):
                item["input"] = node["name"]
        node["dedicated_config"]["schedule_config"].update(
            start_time=anchor, schedule_period={"hour": "H", "day": "D"}[period]
        )
        for window in node["windows_info"]:
            window.update(offsets(0, 0, "H"))
            window["window_size_unit"] = {"hour": "H", "day": "D"}[period]
            window["window_offset_unit"] = "H"
            window["retained_option"] = "keep"
        node["dedicated_config"]["output_config"]["output_baseline"] = "retained_native_baseline"
        return graph

    def test_existing_hour_day_and_multi_hour_keep_native_start_and_exact_windows(self):
        for period, anchor, frequency in (("hour", 17, 1), ("day", 0, 1), ("hour", 1, 2), ("hour", 1, 12)):
            with self.subTest(period=period, anchor=anchor, frequency=frequency):
                previous = self.existing_graph(period, anchor)
                old_node = self.sql_node(previous)
                old_node["dedicated_config"]["schedule_config"]["count_freq"] = frequency
                old_node["windows_info"][0]["window_size"] = frequency
                self.configure_schedule(period, frequency)
                self.profile.pop("batch_window_offsets", None)
                self.existing = deepcopy(previous["nodes"])
                self.strategy.sql = "SELECT id FROM 47_input"
                desired = self.graph()
                merged = flow._merged_spec(previous, desired, preserve_storage_targets=True)
                node = self.sql_node(merged)
                self.assertEqual(node["dedicated_config"]["schedule_config"]["start_time"], anchor)
                self.assertEqual(node["windows_info"], old_node["windows_info"])
                self.assertEqual(
                    node["dedicated_config"]["output_config"], old_node["dedicated_config"]["output_config"]
                )
                self.assertEqual(node["processing_info"], self.strategy.sql)
                self.existing = []

    def test_period_switch_does_not_reuse_start_in_old_units_or_old_window_offsets(self):
        for before, after, anchor, expected in (("hour", "day", 17, 0), ("day", "hour", 0, 1)):
            self.existing = []
            previous = self.existing_graph(before, anchor)
            self.configure_schedule(after)
            self.configured_window(after, start=3, end=4)
            self.existing = deepcopy(previous["nodes"])
            desired = self.graph()
            merged = flow._merged_spec(previous, desired)
            node = self.sql_node(merged)
            self.assertEqual(node["dedicated_config"]["schedule_config"]["start_time"], expected)
            self.assertEqual(node["windows_info"][0]["window_end_offset"], 4)
            self.assertNotIn("retained_option", node["windows_info"][0])

    def test_period_switch_without_confirmed_new_window_is_rejected(self):
        self.existing = self.existing_graph()["nodes"]
        self.configure_schedule("day")
        self.profile.pop("batch_window_offsets", None)
        with self.assertRaisesMessage(BKBaseResourceMappingError, "batch window boundaries"):
            self.graph()

    def test_existing_window_wins_over_an_explicit_profile_override(self):
        self.existing = self.existing_graph()["nodes"]
        self.configured_window("hour", start=-2, end=-1)
        self.assertEqual(self.sql_node(self.graph())["windows_info"][0]["window_end_offset"], 0)

    def test_batch_node_deploy_options_are_retained_without_mutating_profile(self):
        config = self.profile["operation_config"]["batch_sql_deploy_config"]
        config["node_deploy_configs"] = {"custom_output": {"engine_conf": "configured"}}
        original = deepcopy(self.profile)
        self.assertEqual(self.graph()["operation_config"]["batch_sql_deploy_config"], config)
        self.assertEqual(self.profile, original)

    def test_incomplete_existing_window_is_not_repaired_by_profile_or_hourly_default(self):
        self.existing = self.existing_graph()["nodes"]
        self.sql_node({"nodes": self.existing})["windows_info"][0].pop("window_end_offset")
        with self.assertRaisesMessage(BKBaseResourceMappingError, "existing batch window"):
            self.graph()

    def test_new_input_does_not_inherit_the_other_tables_window(self):
        self.existing = self.existing_graph()["nodes"]
        self.controller.rt_ids.append("47_new")
        windows = {w["result_table_id"]: w for w in self.sql_node(self.graph())["windows_info"]}
        self.assertEqual(windows["47_input"]["window_end_offset"], 0)
        self.assertEqual(windows["47_new"]["window_end_offset"], 1)

    def test_invalid_same_period_anchor_is_not_reset(self):
        desired = self.graph()
        for invalid in (None, True, -1, 24, "1", 1795078800000):
            previous = deepcopy(desired)
            self.sql_node(previous)["dedicated_config"]["schedule_config"]["start_time"] = invalid
            with self.subTest(invalid=invalid), self.assertRaisesMessage(
                BKBaseResourceMappingError, "existing batch schedule"
            ):
                flow._merged_spec(previous, desired)

    def test_locked_update_preserves_latest_anchor_and_windows_not_stale_builder_values(self):
        desired = self.graph()
        ref = {"kind": "Flow", "tenant": "default", "namespace": "audit", "name": "existing"}
        self.strategy.backend_data = {"bkbase_v4": {"flow": ref}}

        def resource(anchor, end):
            spec = deepcopy(desired)
            node = self.sql_node(spec)
            node["dedicated_config"]["schedule_config"]["start_time"] = anchor
            node["windows_info"][0].update(offsets(0, end, "H"))
            return {
                "kind": "Flow",
                "metadata": {**ref, "annotations": {"task_stopped": "true"}},
                "spec": spec,
                "status": {"phase": "Ok"},
            }

        with mock.patch.object(flow, "_save_operation_binding"), mock.patch.object(
            flow, "_validate_flow_inputs"
        ), mock.patch.object(flow, "resource_lock", side_effect=lambda *a: nullcontext()), mock.patch.object(
            flow.api.bk_base_v4, "flow_get", side_effect=[resource(2, 1), resource(3, 0)]
        ), mock.patch.object(
            flow,
            "get_rule_flow_status",
            side_effect=lambda context, strategy, resource: {"task_state": "stopped", "resource": resource},
        ), mock.patch.object(
            flow, "_write_flow_request", return_value=resource(3, 0)
        ) as write:
            flow.apply_rule_flow(self.context, self.strategy, desired)
        node = self.sql_node(write.call_args.kwargs["spec"])
        self.assertEqual(node["dedicated_config"]["schedule_config"]["start_time"], 3)
        self.assertEqual(node["windows_info"][0]["window_end_offset"], 0)

    def apply_running_graph(self, current, desired):
        """重放正式运行图的改图入口，断言是否真正请求停止或写出。"""
        ref = {"kind": "Flow", "tenant": "default", "namespace": "audit", "name": "existing"}
        self.strategy.backend_data = {"bkbase_v4": {"flow": ref}}
        resource = {
            "kind": "Flow",
            "metadata": {**ref, "annotations": {"task_stopped": "false"}},
            "spec": current,
            "status": {"phase": "Ok"},
        }
        original = deepcopy((current, desired))
        with mock.patch.object(flow, "_save_operation_binding"), mock.patch.object(
            flow, "_validate_flow_inputs"
        ), mock.patch.object(flow, "resource_lock", side_effect=lambda *a: nullcontext()), mock.patch.object(
            flow.api.bk_base_v4, "flow_get", return_value=resource
        ), mock.patch.object(
            flow, "get_rule_flow_status", return_value={"task_state": "running"}
        ), mock.patch.object(
            flow, "operate_rule_flow", return_value={"requested": "stop"}
        ) as stop, mock.patch.object(
            flow, "_write_flow_request"
        ) as write:
            result = flow.apply_rule_flow(self.context, self.strategy, desired)
        self.assertEqual((current, desired), original)
        write.assert_not_called()
        return result, stop

    def test_running_graph_empty_node_options_roundtrip_never_requests_stop_or_write(self):
        for before in ("missing", None, {}):
            for after in ("missing", None, {}):
                current = self.graph()
                desired = deepcopy(current)
                for spec, value in ((current, before), (desired, after)):
                    config = spec["operation_config"]["batch_sql_deploy_config"]
                    if value == "missing":
                        config.pop("node_deploy_configs")
                    else:
                        config["node_deploy_configs"] = value
                with self.subTest(before=before, after=after):
                    result, stop = self.apply_running_graph(current, desired)
                    stop.assert_not_called()
                    self.assertEqual(result, {"task_state": "running"})

    def test_empty_node_options_equivalence_does_not_hide_real_spec_changes(self):
        for change in ("sql", "cluster", "add_override", "remove_override", "change_override", "other_field"):
            current = self.graph()
            desired = deepcopy(current)
            before = current["operation_config"]["batch_sql_deploy_config"]
            after = desired["operation_config"]["batch_sql_deploy_config"]
            before["node_deploy_configs"] = None
            if change == "sql":
                self.sql_node(desired)["processing_info"] = "SELECT id FROM 47_input"
            elif change == "cluster":
                after["cluster"] = "another_batch"
            elif change == "add_override":
                after["node_deploy_configs"] = {"job": {"engine_conf": "custom"}}
            elif change == "remove_override":
                before["node_deploy_configs"] = {"job": {"engine_conf": "custom"}}
                after["node_deploy_configs"] = None
            elif change == "change_override":
                before["node_deploy_configs"] = {"job": {"engine_conf": "old"}}
                after["node_deploy_configs"] = {"job": {"engine_conf": "new"}}
            else:
                desired["description"] = "changed"
            with self.subTest(change=change):
                result, stop = self.apply_running_graph(current, desired)
                stop.assert_called_once_with(self.context, self.strategy, action="stop")
                self.assertEqual(result, {"requested": "stop"})

    def test_complete_batch_operation_and_model_storage_are_built_without_hardcoded_cluster(self):
        graph = self.graph()
        self.assertEqual(
            graph["operation_config"],
            {
                "start_position": "continue",
                "stream_sql_deploy_config": None,
                "batch_sql_deploy_config": {"cluster": "synthetic_batch", "node_deploy_configs": {}},
            },
        )
        sink = next(n for n in graph["nodes"] if n["kind"] == "HdfsStorageNode")
        self.assertEqual(sink["storage"], self.storage_ref())
        self.assertEqual(sink["input"], self.sql_node(graph)["name"])
        self.assertEqual(sink["storage_config"], {"other": {"dataType": "parquet"}})
        self.assertNotIn("node_deploy_configs", self.profile["operation_config"]["batch_sql_deploy_config"])

    def test_batch_cluster_and_node_options_must_be_explicit_valid_configuration(self):
        for config in (
            None,
            {},
            {"cluster": ""},
            {"cluster": " "},
            {"cluster": 42},
            {"cluster": "valid", "node_deploy_configs": []},
            {"cluster": "valid", "node_deploy_configs": False},
        ):
            self.profile["operation_config"]["batch_sql_deploy_config"] = config
            with self.subTest(config=config), self.assertRaisesMessage(BKBaseResourceMappingError, "batch deployment"):
                self.graph()

    def test_native_null_node_options_mean_no_overrides_in_profile_and_pending_spec(self):
        self.profile["operation_config"]["batch_sql_deploy_config"]["node_deploy_configs"] = None
        graph = self.graph()
        self.assertEqual(graph["operation_config"]["batch_sql_deploy_config"]["node_deploy_configs"], {})
        self.assertIsNone(self.profile["operation_config"]["batch_sql_deploy_config"]["node_deploy_configs"])
        graph["operation_config"]["batch_sql_deploy_config"]["node_deploy_configs"] = None
        flow._validate_batch_deployment(self.context, graph)
        self.assertEqual(graph["operation_config"]["batch_sql_deploy_config"]["node_deploy_configs"], {})

    def test_missing_or_unconfigured_storage_cannot_produce_a_source_and_sql_only_flow(self):
        self.controller.storage_nodes = []
        with self.assertRaisesMessage(BKBaseResourceMappingError, "batch storage output"):
            self.graph()
        self.controller.storage_nodes = [HDFSStorageNode]
        with mock.patch.object(
            HDFSStorageNode, "cluster", new_callable=mock.PropertyMock, return_value=""
        ), self.assertRaisesMessage(BKBaseResourceMappingError, "batch storage output"):
            self.graph()

    def test_deployment_guard_accepts_all_supported_valid_storage_types_not_only_doris(self):
        for node_kind, ref_kind in (
            ("HdfsStorageNode", "Hdfs"),
            ("DorisStorageNode", "Doris"),
            ("EsStorageNode", "ElasticSearch"),
            ("QueueStorageNode", "Kafka"),
        ):
            graph = self.graph()
            sink = graph["nodes"][-1]
            sink.update(kind=node_kind, storage=self.storage_ref(ref_kind))
            with self.subTest(kind=node_kind):
                flow._validate_batch_deployment(self.context, graph)
                sink["input"] = "wrong_node"
                with self.assertRaisesMessage(BKBaseResourceMappingError, "batch storage output"):
                    flow._validate_batch_deployment(self.context, graph)

    def test_realtime_path_does_not_require_batch_cluster_or_storage(self):
        self.strategy.configs["data_source"]["source_type"] = NodeType.REALTIME
        self.controller.storage_nodes = []
        self.profile["operation_config"] = {}
        graph = self.graph()
        self.assertEqual(graph["operation_config"], {"start_position": "continue"})
        self.assertEqual(graph["nodes"][-1]["kind"], "StreamNode")

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_branch_keeps_existing_boundary_string_and_legacy_controller(self):
        for period, now, expected in (
            ("hour", "2026-11-19 16:30:00", "2026-11-19 17:00:00"),
            ("hour", "2026-11-19 16:00:00", "2026-11-19 17:00:00"),
            ("hour", "2026-11-19 23:59:59", "2026-11-20 00:00:00"),
            ("day", "2026-11-19 00:00:00", "2026-11-20 00:00:00"),
            ("day", "2026-12-31 23:59:59", "2027-01-01 00:00:00"),
        ):
            self.configure_schedule(period)
            with self.subTest(period=period, now=now), self.freeze(now):
                self.assertEqual(
                    self.controller._build_sql_node_config(47)["dedicated_config"]["schedule_config"]["start_time"],
                    expected,
                )
        self.controller._update_or_create_bkbase_flow_v3 = mock.Mock(return_value="legacy result")
        with mock.patch.object(flow, "build_controller_spec", side_effect=AssertionError("V4 graph called")):
            self.assertEqual(flow.configure_rule_controller(self.controller), "legacy result")
