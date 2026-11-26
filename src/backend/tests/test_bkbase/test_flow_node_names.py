"""V4 Flow节点50字符限制：保留既有短名及摘要，构图引用一致，V3不变。"""

from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

import requests
from django.test import SimpleTestCase, override_settings

from services.web.analyze.constants import FlowDataSourceNodeType
from services.web.bkbase import common, flow
from services.web.bkbase.exceptions import BKBaseResourceMappingError


class FlowNodeNameTests(SimpleTestCase):
    def setUp(self):
        self.enterContext(
            mock.patch.object(requests.Session, "request", side_effect=AssertionError("real HTTP forbidden"))
        )

    @override_settings(BKBASE_V4_STREAM_CLUSTER="synthetic_stream")
    def test_long_multi_input_names_match_controller_map_sql_inputs_and_storage_link(self):
        ids = ["1_" + "same_long_input_" * 5 + suffix for suffix in ("a", "b")]
        strategy = SimpleNamespace(
            strategy_id=7, strategy_name="synthetic", namespace="audit", sql="SELECT * FROM input", backend_data={}
        )
        storage = mock.Mock()
        storage.build_node_config.return_value = {
            "node_type": "doris",
            "cluster": "legacy",
            "expires": "7d",
            "physical_table_name": "audit_db.events",
        }
        seen = {}
        controller = SimpleNamespace(
            strategy=strategy,
            rt_ids=ids,
            check_source_type=lambda rt: FlowDataSourceNodeType.REALTIME,
            storage_nodes=[mock.Mock(return_value=storage)],
        )

        def sql_config(biz_id):
            seen.update(controller.rt_node_map)
            return {"node_type": "realtime"}

        controller._build_sql_node_config = sql_config
        refs = {
            rt: {"kind": "ResultTable", "tenant": "tenant_a", "namespace": "inputs", "name": "physical_" + str(i)}
            for i, rt in enumerate(ids)
        }
        cluster = {"kind": "Doris", "tenant": "tenant_a", "namespace": "clusters", "name": "doris"}
        with mock.patch.object(flow, "_input_result_table_refs", return_value=refs), mock.patch.object(
            flow.metadata_service,
            "get_result_tables",
            return_value=[{"result_table_id": rt, "bk_biz_id": 1} for rt in ids],
        ), mock.patch.object(
            flow.GlobalMetaConfig, "get", return_value={"operation_config": {"start_position": "continue"}}
        ), mock.patch.object(
            flow.storage_service, "resolve_storage_cluster", return_value=cluster
        ), mock.patch.object(
            flow, "_save_operation_binding"
        ):
            result = flow.build_controller_spec(controller, context={"tenant": "tenant_a", "namespace": "audit"})
        sources, sql, saved_storage = result["nodes"][:2], result["nodes"][2], result["nodes"][3]
        self.assertTrue(all(len(node["name"]) <= 50 for node in result["nodes"]))
        self.assertEqual(len({node["name"] for node in sources}), 2)
        self.assertEqual(controller.rt_node_map, seen)
        self.assertEqual(controller.rt_node_map, dict(zip(ids, [node["name"] for node in sources])))
        self.assertEqual(sql["inputs"], [seen[rt] for rt in ids])
        self.assertEqual(saved_storage["input"], sql["name"])
        self.assertEqual([node["data"] for node in sources], list(refs.values()))
        self.assertEqual(saved_storage["storage"], cluster)

    def test_short_and_exactly_fifty_names_keep_original_stable_identity(self):
        for prefix in ("src", "sql", "store"):
            for count in (1, 10, 50 - len(prefix) - 14):
                parts = "x" * count
                with self.subTest(prefix=prefix, count=count):
                    original = common.stable_name(prefix, parts)
                    self.assertLessEqual(len(original), 50)
                    self.assertEqual(flow.node_name(prefix, parts), original)

    def test_all_node_families_bound_long_names_without_losing_hash_suffix(self):
        for prefix in ("src", "sql", "store"):
            first, second = "same_readable_" * 8 + "a", "same_readable_" * 8 + "b"
            with self.subTest(prefix=prefix):
                a, b = flow.node_name(prefix, first), flow.node_name(prefix, second)
                self.assertEqual(len(a), 50)
                self.assertEqual(len(b), 50)
                self.assertEqual(a[-12:], common.stable_name(prefix, first)[-12:])
                self.assertEqual(b[-12:], common.stable_name(prefix, second)[-12:])
                self.assertNotEqual(a, b)
                self.assertEqual(a, flow.node_name(prefix, first))

    def test_other_resource_names_retain_original_fifty_eight_character_rule(self):
        value = "resource_name_" * 8
        original = common.stable_name("flow", value)
        self.assertEqual(len(original), 58)
        self.assertEqual(flow.stable_name("flow", value), original)

    def test_existing_fifty_character_formal_node_names_are_preserved_by_alignment(self):
        source = {
            "kind": "StreamSourceNode",
            "name": "s" * 50,
            "data": {"kind": "ResultTable", "tenant": "tenant_a", "namespace": "inputs", "name": "input"},
        }
        sql = {
            "kind": "StreamNode",
            "name": "q" * 50,
            "inputs": [source["name"]],
            "output": "1_output",
            "config": {"sql": "old"},
        }
        old = {"nodes": [source, sql]}
        desired = deepcopy(old)
        desired["nodes"][0]["name"] = "new_generated_source"
        desired["nodes"][1].update(name="new_generated_sql", inputs=["new_generated_source"], config={"sql": "new"})
        result = flow._merged_spec(old, desired, preserve_storage_targets=True)
        self.assertEqual([node["name"] for node in result["nodes"]], [source["name"], sql["name"]])
        self.assertEqual(result["nodes"][1]["inputs"], [source["name"]])

    def test_explicit_overlong_node_name_is_rejected_before_platform_write(self):
        with self.assertRaises(BKBaseResourceMappingError):
            flow.validate_graph([{"kind": "StreamSourceNode", "name": "x" * 51}])

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_controller_keeps_legacy_entry_without_using_v4_node_naming(self):
        legacy = mock.Mock(return_value="legacy result")
        controller = SimpleNamespace(_update_or_create_bkbase_flow_v3=legacy)
        with mock.patch.object(flow, "node_name", create=True, side_effect=AssertionError("V4 naming must not run")):
            self.assertEqual(flow.configure_rule_controller(controller), "legacy result")
        legacy.assert_called_once_with()
