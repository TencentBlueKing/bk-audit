"""按 Binding 和场景判定 V4 资产、调度与构图，不回填旧分类字段。"""
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, override_settings

from services.web.analyze.constants import FlowDataSourceNodeType as NodeType
from services.web.analyze.controls.rule_audit import RuleAuditController
from services.web.analyze.utils import is_asset
from services.web.bkbase import flow, metadata
from services.web.bkbase import table_capabilities as capabilities
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.strategy_v2.constants import RuleAuditConfigType
from services.web.strategy_v2.resources import GetRTLastData
from services.web.strategy_v2.utils import table


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit")
class TableCapabilitiesTests(SimpleTestCase):
    def setUp(self):
        self.context = {"version": "v4", "tenant": "tenant_a", "namespace": "audit"}
        self.ref = {"kind": "ResultTable", "tenant": "tenant_a", "namespace": "inputs", "name": "actual_table"}
        self.rt = {"result_table_id": "11_input", "processing_type": "cdc_static", "result_table_type": "upsert_static"}
        self.enterContext(
            mock.patch("requests.sessions.Session.request", side_effect=AssertionError("unexpected HTTP"))
        )
        self.enterContext(
            mock.patch.object(
                metadata.api.bk_base_v4,
                "dataset_detail",
                return_value={"dataset_name": "11_input", "kind": "DorisBinding", "storage_type": "doris"},
            )
        )

    def binding(self, kind, dimension=None, *, engine="iceberg", phase="Ok"):
        spec = {"data": self.ref}
        if kind == "HdfsBinding":
            spec["storageConfig"] = {engine: {} if dimension is None else {"dimensionTable": dimension}}
        return {
            "kind": kind,
            "metadata": {"tenant": "tenant_a", "namespace": "inputs", "name": kind.lower()},
            "spec": spec,
            "status": {"phase": phase},
        }

    def parse(self, *bindings):
        return capabilities.parse_bindings({"status": {"related": list(bindings)}}, self.ref)

    def test_five_confirmed_source_scenarios_select_different_nodes(self):
        cases = [
            (self.binding("ChannelBinding"), NodeType.REALTIME, None, NodeType.REALTIME),
            (self.binding("RedisBinding"), NodeType.REALTIME, True, NodeType.REDIS_KV_SOURCE),
            (self.binding("HdfsBinding", True), NodeType.REALTIME, True, NodeType.BATCH),
            (self.binding("HdfsBinding", True, engine="paimon"), NodeType.BATCH, True, NodeType.BATCH),
            (self.binding("HdfsBinding", False), NodeType.BATCH, False, NodeType.BATCH_REAL),
        ]
        for binding, mode, asset, expected in cases:
            with self.subTest(binding=binding["kind"], mode=mode, asset=asset):
                self.assertEqual(capabilities.source_node_type(self.parse(binding), mode, asset=asset), expected)

    def test_missing_or_non_boolean_dimension_never_becomes_offline_flow(self):
        for value in (None, "false", "true", 0, 1):
            cap = self.parse(self.binding("HdfsBinding", value))
            with self.subTest(value=value):
                self.assertIsNone(capabilities.source_node_type(cap, NodeType.BATCH))
                self.assertIsNone(capabilities.asset_status(cap))
        binding = self.binding("HdfsBinding")
        binding["spec"] = {"data": self.ref, "tableInfo": {"dimension_table": False}}
        self.assertIsNone(capabilities.source_node_type(self.parse(binding), NodeType.BATCH))

    def test_paimon_only_literal_true_is_dimension_and_other_values_are_batch_flow(self):
        cases = [
            ({"dimensionTable": True}, True, NodeType.BATCH),
            ({"dimensionTable": False}, False, NodeType.BATCH_REAL),
            ({}, False, NodeType.BATCH_REAL),
            ({"dimensionTable": None}, False, NodeType.BATCH_REAL),
            ({"dimensionTable": 0}, False, NodeType.BATCH_REAL),
            ({"dimensionTable": 1}, False, NodeType.BATCH_REAL),
            ({"dimensionTable": "true"}, False, NodeType.BATCH_REAL),
            ({"dimensionTable": "false"}, False, NodeType.BATCH_REAL),
            ({"dimensionTable": {}}, False, NodeType.BATCH_REAL),
            ({"dimensionTable": []}, False, NodeType.BATCH_REAL),
        ]
        for config, asset, node_type in cases:
            binding = self.binding("HdfsBinding", engine="paimon")
            binding["spec"]["storageConfig"]["paimon"] = config
            before = deepcopy(binding)
            with self.subTest(config=config):
                cap = self.parse(binding)
                self.assertIs(capabilities.asset_status(cap), asset)
                self.assertEqual(capabilities.source_node_type(cap, NodeType.BATCH), node_type)
                self.assertEqual(binding, before)

    def test_paimon_requires_ready_binding_to_the_selected_result_table(self):
        for resource in ({}, {"status": {}}, {"status": {"related": []}}):
            with self.subTest(resource=resource):
                cap = capabilities.parse_bindings(resource, self.ref)
                self.assertIsNone(capabilities.asset_status(cap))
                self.assertIsNone(capabilities.source_node_type(cap, NodeType.BATCH))
        for phase in (None, "Pending", "Failed", "Terminating"):
            with self.subTest(phase=phase):
                cap = self.parse(self.binding("HdfsBinding", engine="paimon", phase=phase))
                self.assertIsNone(capabilities.asset_status(cap))
                self.assertIsNone(capabilities.source_node_type(cap, NodeType.BATCH))
        wrong = self.binding("HdfsBinding", engine="paimon")
        wrong["spec"]["data"] = {**self.ref, "name": "another_table"}
        with self.assertRaises(BKBaseResourceMappingError):
            self.parse(wrong)

    def test_unrecognized_hdfs_storage_model_stays_unknown(self):
        for config in (None, {}, {"paimon": None}, {"paimon": []}, {"other": {"dimensionTable": False}}):
            binding = self.binding("HdfsBinding")
            binding["spec"]["storageConfig"] = config
            with self.subTest(config=config):
                cap = self.parse(binding)
                self.assertIsNone(capabilities.asset_status(cap))
                self.assertIsNone(capabilities.source_node_type(cap, NodeType.BATCH))

    def test_paimon_default_and_iceberg_conflicting_dimensions_stay_unknown(self):
        binding = self.binding("HdfsBinding")
        binding["spec"]["storageConfig"] = {"iceberg": {"dimensionTable": True}, "paimon": {}}
        cap = self.parse(binding)
        self.assertIsNone(capabilities.asset_status(cap))
        self.assertIsNone(capabilities.source_node_type(cap, NodeType.BATCH))

    def test_multiple_paimon_bindings_keep_explicit_role_selection(self):
        cap = self.parse(
            self.binding("HdfsBinding", True, engine="paimon"), self.binding("HdfsBinding", engine="paimon")
        )
        self.assertIsNone(capabilities.source_node_type(cap, NodeType.BATCH))
        self.assertEqual(capabilities.source_node_type(cap, NodeType.BATCH, asset=True), NodeType.BATCH)
        self.assertEqual(capabilities.source_node_type(cap, NodeType.BATCH, asset=False), NodeType.BATCH_REAL)

    def test_multiple_bindings_are_selected_for_the_current_scenario(self):
        cap = self.parse(
            self.binding("DorisBinding"),
            self.binding("RedisBinding"),
            self.binding("HdfsBinding", True),
            self.binding("ChannelBinding"),
        )
        self.assertEqual(capabilities.source_node_type(cap, NodeType.REALTIME), NodeType.REALTIME)
        self.assertEqual(capabilities.source_node_type(cap, NodeType.REALTIME, asset=True), NodeType.REDIS_KV_SOURCE)
        self.assertEqual(capabilities.source_node_type(cap, NodeType.BATCH, asset=True), NodeType.BATCH)
        both = self.parse(self.binding("HdfsBinding", True), self.binding("HdfsBinding", False))
        self.assertIsNone(capabilities.source_node_type(both, NodeType.BATCH))
        self.assertEqual(capabilities.source_node_type(both, NodeType.BATCH, asset=False), NodeType.BATCH_REAL)
        self.assertEqual(capabilities.source_node_type(both, NodeType.BATCH, asset=True), NodeType.BATCH)

    def test_unready_or_wrong_table_binding_does_not_establish_capability(self):
        for phase in (None, "Pending", "Failed", "Terminating"):
            with self.subTest(phase=phase):
                self.assertIsNone(capabilities.asset_status(self.parse(self.binding("RedisBinding", phase=phase))))
        bad = self.binding("RedisBinding")
        bad["spec"]["data"] = {**self.ref, "name": "another_table"}
        with self.assertRaises(BKBaseResourceMappingError):
            self.parse(bad)
        bad = self.binding("HdfsBinding", True)
        bad["metadata"]["tenant"] = "another_tenant"
        with self.assertRaises(BKBaseResourceMappingError):
            self.parse(bad)

    def test_formal_service_checks_identity_and_reads_actual_binding_config(self):
        response = {
            "metadata": {k: self.ref[k] for k in ("tenant", "namespace", "name")},
            "spec": {"predefiendResultTableId": "11_input"},
            "status": {"related": [self.binding("HdfsBinding", True, engine="paimon")]},
        }
        before = deepcopy(response)
        with mock.patch.object(metadata.api.bk_base_v4, "result_table_info", return_value=response) as get:
            cap = metadata.get_source_capabilities("11_input", context=self.context)
        get.assert_called_once_with(tenant="tenant_a", result_table_id="11_input")
        self.assertTrue(capabilities.asset_status(cap))
        self.assertEqual(response, before)
        self.assertNotIn("storageConfig", str(cap))

    def test_channel_dataset_uses_exact_logical_table_and_actual_namespace_without_aliasing_queue(self):
        response = {
            "metadata": {k: self.ref[k] for k in ("tenant", "namespace", "name")},
            "spec": {"predefiendResultTableId": "11_input"},
            "status": {"related": [self.binding("DorisBinding")]},
        }

        channel = {
            "dataset_name": "11_input",
            "storage_type": "channel",
            "kind": "ChannelBinding",
            "id": "inputs/ChannelBinding/actual_binding",
        }
        with mock.patch.object(metadata.api.bk_base_v4, "result_table_info", return_value=response), mock.patch.object(
            metadata.api.bk_base_v4, "dataset_detail", return_value=channel
        ) as detail:
            cap = metadata.get_source_capabilities("11_input", context=self.context)
            self.assertEqual(capabilities.source_node_type(cap, NodeType.REALTIME), NodeType.REALTIME)
            detail.assert_called_once_with(
                tenant="tenant_a", namespace="inputs", dataset_name="11_input", storage_type="channel"
            )
            self.assertNotIn("result_table_ref", cap)
            self.assertNotIn("binding", cap)
            channel["kind"] = "QueueBinding"
            self.assertIsNone(
                capabilities.source_node_type(
                    metadata.get_source_capabilities("11_input", context=self.context), NodeType.REALTIME
                )
            )
            channel["dataset_name"] = "11_other"
            with self.assertRaises(BKBaseResourceMappingError):
                metadata.get_source_capabilities("11_input", context=self.context)

    def test_v4_asset_classification_ignores_old_cdc_fields(self):
        with mock.patch.object(
            metadata, "get_source_capabilities", return_value=self.parse(self.binding("HdfsBinding", False))
        ):
            self.assertFalse(is_asset(self.rt))
        with mock.patch.object(
            metadata, "get_source_capabilities", return_value=self.parse(self.binding("RedisBinding"))
        ):
            self.assertTrue(is_asset(self.rt))
        with mock.patch.object(
            metadata, "get_source_capabilities", return_value=self.parse(self.binding("HdfsBinding"))
        ):
            with self.assertRaises(BKBaseResourceMappingError):
                is_asset(self.rt)

    def test_schedule_checker_and_controller_select_the_same_modes(self):
        cap = self.parse(self.binding("HdfsBinding", False), self.binding("ChannelBinding"))
        checker = table.RuleAuditSourceTypeChecker(namespace="audit")
        strategy = SimpleNamespace(
            configs={"config_type": RuleAuditConfigType.BIZ_RT, "data_source": {"source_type": NodeType.BATCH}}
        )
        controller = object.__new__(RuleAuditController)
        controller.strategy = strategy
        with mock.patch.object(metadata, "get_source_capabilities", return_value=cap), mock.patch.object(
            table.CollectorPlugin, "build_collector_rt", return_value="11_log"
        ), mock.patch.object(
            RuleAuditController, "event_log_rt_id", new_callable=mock.PropertyMock, return_value="11_log"
        ):
            self.assertEqual(checker.rt_support_source_types("11_input"), [NodeType.REALTIME, NodeType.BATCH])
            self.assertEqual(controller.check_source_type("11_input"), NodeType.BATCH_REAL)

    def test_link_schedule_validates_log_channel_and_each_asset_for_each_mode(self):
        checker = table.RuleAuditSourceTypeChecker(namespace="audit")
        link = SimpleNamespace(rt_ids=["11_log", "11_asset"])
        caps = {
            "11_log": self.parse(self.binding("ChannelBinding"), self.binding("HdfsBinding", False)),
            "11_asset": self.parse(self.binding("RedisBinding")),
        }
        with mock.patch.object(table.CollectorPlugin, "build_collector_rt", return_value="11_log"), mock.patch.object(
            metadata, "get_source_capabilities", side_effect=lambda rt_id: caps[rt_id]
        ):
            self.assertEqual(checker.link_table_support_source_types(link), [NodeType.REALTIME])
            caps["11_asset"] = self.parse(self.binding("HdfsBinding", True, engine="paimon"))
            self.assertEqual(checker.link_table_support_source_types(link), [NodeType.REALTIME, NodeType.BATCH])
            caps["11_log"] = self.parse(self.binding("HdfsBinding", False))
            self.assertEqual(checker.link_table_support_source_types(link), [NodeType.BATCH])

    def test_real_flow_builder_uses_confirmed_source_kind_and_keeps_user_date_sql(self):
        sql = "SELECT * FROM 11_input WHERE thedate = 20261109 AND dtEventTimeStamp >= 42"
        cases = [
            (self.binding("ChannelBinding"), NodeType.REALTIME, RuleAuditConfigType.BIZ_RT, "StreamSourceNode"),
            (self.binding("RedisBinding"), NodeType.REALTIME, RuleAuditConfigType.LINK_TABLE, "StreamStaticSource"),
            (self.binding("HdfsBinding", True), NodeType.REALTIME, RuleAuditConfigType.LINK_TABLE, "BatchStaticSource"),
            (
                self.binding("HdfsBinding", True, engine="paimon"),
                NodeType.BATCH,
                RuleAuditConfigType.LINK_TABLE,
                "BatchStaticSource",
            ),
            (self.binding("HdfsBinding", False), NodeType.BATCH, RuleAuditConfigType.BIZ_RT, "BatchSourceNode"),
            (
                self.binding("HdfsBinding", engine="paimon"),
                NodeType.BATCH,
                RuleAuditConfigType.BIZ_RT,
                "BatchSourceNode",
            ),
        ]
        for binding, mode, config_type, expected in cases:
            strategy = SimpleNamespace(
                strategy_id=13,
                strategy_name="synthetic",
                namespace="audit",
                sql=sql,
                backend_data={},
                configs={"config_type": config_type, "data_source": {"source_type": mode}},
            )
            controller = SimpleNamespace(
                strategy=strategy, event_log_rt_id="11_log", rt_ids=["11_input"], storage_nodes=[]
            )

            def check_source_type(rt_id):
                return RuleAuditController.check_source_type(controller, rt_id)

            controller.check_source_type = check_source_type
            dedicated = {
                "schedule_config": {"schedule_period": "hour", "count_freq": 1},
                "self_dependence": {"self_dependency_config": {}},
                "output_config": {"output_baseline_type": "schedule_time"},
            }

            def build_sql_node_config(biz):
                return {
                    "node_type": "realtime" if mode == NodeType.REALTIME else "batchv2",
                    "dedicated_config": dedicated,
                    "window_info": [],
                }

            controller._build_sql_node_config = build_sql_node_config
            profile = {
                "operation_config": {"start_position": "continue"},
                "batch_schedules": {"hour:1": {"start_time": 42}},
            }
            with self.subTest(expected=expected, mode=mode), mock.patch.object(
                metadata, "get_source_capabilities", return_value=self.parse(binding)
            ), mock.patch.object(
                metadata, "get_result_tables", return_value=[{"result_table_id": "11_input", "bk_biz_id": 11}]
            ), mock.patch.object(
                flow, "_input_result_table_refs", return_value={"11_input": self.ref}
            ), mock.patch.object(
                flow.GlobalMetaConfig, "get", return_value=profile
            ), mock.patch.object(
                flow, "_save_operation_binding"
            ):
                graph = flow.build_controller_spec(controller, context=self.context)
            self.assertEqual(graph["nodes"][0]["kind"], expected)
            self.assertEqual(graph["nodes"][0]["data"], self.ref)
            sql_node = graph["nodes"][1]
            self.assertEqual(sql_node.get("processing_info", sql_node.get("config", {}).get("sql")), sql)

    def test_asset_candidate_filter_uses_the_same_binding_classification(self):
        handler = table.BizAssetTableHandler("BizAsset")
        rows = [
            {"result_table_id": "11_asset", "processing_type": "none"},
            {"result_table_id": "11_stream", "processing_type": "cdc_static"},
        ]
        caps = {
            "11_asset": self.parse(self.binding("RedisBinding")),
            "11_stream": self.parse(self.binding("HdfsBinding", False)),
        }
        with mock.patch.object(table.bkbase_permissions, "get_project_data", return_value=rows), mock.patch.object(
            metadata, "get_result_tables_bulk", return_value=[rows]
        ), mock.patch.object(
            metadata, "get_source_capabilities", side_effect=lambda rt_id: caps[rt_id]
        ), mock.patch.object(
            handler, "format_result_tables", side_effect=lambda values: values
        ):
            self.assertEqual(handler.list_tables(), [rows[0]])

    def test_preview_preserves_business_date_filter_for_flow_and_omits_it_for_verified_asset(self):
        resource = GetRTLastData()
        with mock.patch.object(metadata, "get_result_table", return_value=self.rt), mock.patch.object(
            metadata, "get_source_capabilities", return_value=self.parse(self.binding("HdfsBinding", False))
        ), mock.patch("services.web.strategy_v2.resources.bkbase_query.query_sync", return_value={"list": []}) as query:
            self.assertEqual(resource.get_last_data("11_input", 7), {"last_data": []})
        self.assertIn("WHERE thedate = ", query.call_args.kwargs["sql"])
        self.assertIn("ORDER BY dteventtimestamp DESC LIMIT 7", query.call_args.kwargs["sql"])
        with mock.patch.object(metadata, "get_result_table", return_value=self.rt), mock.patch.object(
            metadata, "get_source_capabilities", return_value=self.parse(self.binding("HdfsBinding", True))
        ), mock.patch("services.web.strategy_v2.resources.bkbase_query.query_sync", return_value={"list": []}) as query:
            resource.get_last_data("11_input", 7)
        query.assert_called_once_with(sql="SELECT * FROM 11_input LIMIT 7")

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_schedule_options_use_original_storage_and_classification(self):
        checker = table.RuleAuditSourceTypeChecker(namespace="audit")
        legacy = {"storages": {"kafka": {}, "hdfs": {}}, "processing_type": "stream"}
        with mock.patch.object(metadata, "get_result_table", return_value=legacy), mock.patch.object(
            metadata, "get_source_capabilities", side_effect=AssertionError("V4 called")
        ):
            self.assertEqual(checker.rt_support_source_types("legacy_rt"), [NodeType.REALTIME, NodeType.BATCH])

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_legacy_classification_does_not_consult_bindings(self):
        with mock.patch.object(metadata, "get_source_capabilities", side_effect=AssertionError("V4 called")):
            self.assertTrue(is_asset(self.rt))
            self.assertFalse(is_asset({"processing_type": "stream"}))
