"""策略独占整图：任意迁移节点名、正式Ref及最小迁移映射。"""
import json
from contextlib import contextmanager
from copy import deepcopy
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TransactionTestCase, override_settings

from services.web.analyze.storage_node import DorisStorageNode
from services.web.bkbase import flow, flow_migration
from services.web.bkbase.constants import (
    BKBASE_V4_FLOW_CONFIG,
    BKBASE_V4_STORAGE_CLUSTER_MAP,
)
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.constants import (
    DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
    DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY,
)
from services.web.strategy_v2.models import Strategy
from tests.test_bkbase import test_flow_input_refs as input_fixture
from tests.test_bkbase import test_flow_migration_command as command_fixture


def native_ref(kind, name, namespace="inputs"):
    return {"kind": kind, "tenant": "tenant_a", "namespace": namespace, "name": name}


class WholeFlowGraphTests(SimpleTestCase):
    def graph(self):
        source = native_ref("ResultTable", "input")
        storage = native_ref("Doris", "doris", "clusters")
        old = {
            "description": "keep",
            "nodes": [
                {"kind": "StreamSourceNode", "name": "migrated_source", "data": source},
                {
                    "kind": "StreamNode",
                    "name": "migrated_compute",
                    "inputs": ["migrated_source"],
                    "output": "1_output",
                    "config": {"sql": "old"},
                },
                {
                    "kind": "DorisStorageNode",
                    "name": "migrated_storage",
                    "input": "migrated_compute",
                    "storage": storage,
                    "storage_config": {"db": "actual_db", "table": "actual_table", "flush_timeout": 60},
                },
                {"kind": "StreamSourceNode", "name": "obsolete", "data": native_ref("ResultTable", "obsolete")},
            ],
        }
        desired = {
            "nodes": [
                {"kind": "StreamSourceNode", "name": "generated_source", "data": source},
                {
                    "kind": "StreamNode",
                    "name": "generated_compute",
                    "inputs": ["generated_source"],
                    "output": "1_output",
                    "config": {"sql": "new"},
                },
                {
                    "kind": "DorisStorageNode",
                    "name": "generated_storage",
                    "input": "generated_compute",
                    "storage": storage,
                    "storage_config": {"expires": "7d"},
                },
            ]
        }
        return old, desired

    def test_arbitrary_names_follow_ref_and_output_and_whole_graph_removes_obsolete_nodes(self):
        old, desired = self.graph()
        original = deepcopy((old, desired))
        result = flow._merged_spec(old, desired)
        self.assertEqual(
            [node["name"] for node in result["nodes"]], ["migrated_source", "migrated_compute", "migrated_storage"]
        )
        self.assertEqual(result["nodes"][1]["inputs"], ["migrated_source"])
        self.assertEqual(result["nodes"][1]["config"]["sql"], "new")
        self.assertEqual(result["nodes"][2]["input"], "migrated_compute")
        self.assertEqual(
            result["nodes"][2]["storage_config"],
            {"db": "actual_db", "table": "actual_table", "flush_timeout": 60, "expires": "7d"},
        )
        self.assertEqual((old, desired), original)

    def test_source_addition_and_deletion_rewire_existing_sql_without_local_node_ids(self):
        old, desired = self.graph()
        desired["nodes"][0] = {
            "kind": "StreamSourceNode",
            "name": "new_source",
            "data": native_ref("ResultTable", "new"),
        }
        desired["nodes"][1]["inputs"] = ["new_source"]
        result = flow._merged_spec(old, desired)
        self.assertEqual(
            [node["name"] for node in result["nodes"]], ["new_source", "migrated_compute", "migrated_storage"]
        )
        self.assertEqual(result["nodes"][1]["inputs"], ["new_source"])

    def test_ambiguous_native_identity_is_not_guessed(self):
        old, desired = self.graph()
        old["nodes"].append({**deepcopy(old["nodes"][1]), "name": "another_compute"})
        with self.assertRaises(BKBaseResourceMappingError):
            flow._merged_spec(old, desired)

    def test_sql_kind_change_retains_output_identity_without_old_kind_configuration(self):
        old, desired = self.graph()
        desired["nodes"][1] = {
            "kind": "BatchSqlNode",
            "name": "batch",
            "inputs": ["generated_source"],
            "output": "1_output",
            "processing_info": "new",
        }
        desired["nodes"][2]["input"] = "batch"
        result = flow._merged_spec(old, desired)
        self.assertEqual(result["nodes"][1]["name"], "migrated_compute")
        self.assertNotIn("config", result["nodes"][1])
        self.assertEqual(result["nodes"][2]["input"], "migrated_compute")

    def test_formal_source_identity_is_independent_of_node_name_prefix(self):
        context = {"tenant": "tenant_a", "namespace": "audit"}
        ref = native_ref("ResultTable", "input")
        value = {"kind": "ResultTable", "metadata": ref, "spec": {"predefiendResultTableId": "1_input"}}
        with mock.patch.object(flow.api.bk_base_v4, "result_table_resource_get", return_value=value):
            flow._validate_flow_inputs(
                context, {"nodes": [{"kind": "StreamSourceNode", "name": "arbitrary", "data": ref}]}
            )

    def test_minimal_mapping_needs_no_legacy_scope_or_strategy_details(self):
        context = {"tenant": "tenant_a", "namespace": "target"}
        self.assertEqual(
            flow_migration.validate_manifest({"41": "migrated"}, context=context),
            [{"legacy_flow_id": 41, "flow_name": "migrated"}],
        )
        for payload in ({}, {"0": "bad"}, {"41": ""}, {"41": "same", "42": "same"}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                flow_migration.validate_manifest(payload, context=context)

    def test_explicit_bad_cluster_mapping_is_not_hidden_by_an_existing_destination(self):
        old, _ = self.graph()
        config = {"node_type": "doris", "cluster": "legacy", "expires": "7d"}
        error = BKBaseResourceMappingError(message="Explicit cluster mapping mismatch")
        with mock.patch.object(flow.storage_service, "resolve_storage_cluster", side_effect=error), mock.patch.object(
            flow.GlobalMetaConfig, "get", return_value={"doris": {"legacy": native_ref("Doris", "wrong", "clusters")}}
        ), self.assertRaises(BKBaseResourceMappingError):
            flow._storage_node(
                {"tenant": "tenant_a", "namespace": "audit"},
                SimpleNamespace(namespace="audit", strategy_id=7),
                config,
                {},
                existing_nodes=old["nodes"],
            )

    def test_missing_requested_cluster_mapping_never_reuses_a_unique_old_destination(self):
        old, _ = self.graph()
        for requested in ("legacy_old", "unmapped_new"):
            with self.subTest(requested=requested), mock.patch.object(flow.GlobalMetaConfig, "get", return_value={}):
                with self.assertRaisesRegex(BKBaseResourceMappingError, requested):
                    flow._storage_node(
                        {"tenant": "tenant_a", "namespace": "audit"},
                        SimpleNamespace(namespace="audit", strategy_id=7),
                        {"node_type": "doris", "cluster": requested, "expires": "7d"},
                        {},
                        existing_nodes=old["nodes"],
                        output_rt_id="1_output",
                    )

    def test_new_doris_destination_still_requires_an_explicit_physical_database(self):
        config = {"node_type": "doris", "cluster": "legacy", "expires": "7d"}
        with mock.patch.object(
            flow.storage_service, "resolve_storage_cluster", return_value=native_ref("Doris", "new", "clusters")
        ), self.assertRaises(BKBaseResourceMappingError):
            flow._storage_node(
                {"tenant": "tenant_a", "namespace": "audit"},
                SimpleNamespace(namespace="audit", strategy_id=7),
                config,
                {},
            )

    def test_existing_destination_defaults_preserve_the_latest_locked_configuration(self):
        context = {"tenant": "tenant_a", "namespace": "audit"}
        strategy = SimpleNamespace(namespace="audit", strategy_id=7)
        cases = (
            (
                "doris",
                "DorisStorageNode",
                "Doris",
                "storage_config",
                {"db": "old", "table": "old_table"},
                {"db": "latest", "table": "latest_table"},
            ),
            ("elastic_storage", "EsStorageNode", "ElasticSearch", "write_alias", {"Fixed": "old"}, {"Fixed": "latest"}),
            (
                "hdfs_storage",
                "HdfsStorageNode",
                "Hdfs",
                "storage_config",
                {"other": {"dataType": "parquet"}},
                {"other": {"dataType": "orc"}},
            ),
        )
        for node_type, kind, cluster_kind, field, previous, latest in cases:
            with self.subTest(node_type=node_type):
                old, desired = self.graph()
                node = old["nodes"][2]
                node.update(kind=kind, storage=native_ref(cluster_kind, "existing", "clusters"))
                node.pop("storage_config")
                node[field] = previous
                with mock.patch.object(flow.storage_service, "resolve_storage_cluster", return_value=node["storage"]):
                    store = flow._storage_node(
                        context,
                        strategy,
                        {"node_type": node_type, "cluster": "legacy", "expires": "7d"},
                        {},
                        existing_nodes=old["nodes"],
                        output_rt_id="1_output",
                    )
                store["input"] = "generated_compute"
                desired["nodes"][2] = store
                node[field] = latest
                merged = flow._merged_spec(old, desired)["nodes"][2][field]
                if node_type == "doris":
                    self.assertEqual({key: merged[key] for key in latest}, latest)
                else:
                    self.assertEqual(merged, latest)


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit")
class MigratedFlowConsumerTests(TransactionTestCase):
    bind_snapshot = input_fixture.FlowInputRefTests.bind_snapshot
    build = input_fixture.FlowInputRefTests.build

    def setUp(self):
        input_fixture.FlowInputRefTests.setUp(self)
        self.flow_ref = native_ref("Flow", "migrated_flow", "audit")
        self.cluster = native_ref("Doris", "existing_doris", "clusters")
        self.strategy.backend_data = {
            "flow_id": 41,
            "sql_node_id": 900,
            "data_source_node_ids": [901],
            "storage_node_ids": [902],
            "raw_table_name": "existing_output",
            "bkbase_v4": {"flow": self.flow_ref, "output_name": "existing_output", "output_rt_id": "1_existing_output"},
        }
        self.strategy.save(update_record=False, update_fields=["backend_data"])
        self.legacy = {key: deepcopy(value) for key, value in self.strategy.backend_data.items() if key != "bkbase_v4"}
        self.current = {
            "kind": "Flow",
            "metadata": {**self.flow_ref, "annotations": {"keep": "value"}},
            "spec": {
                "nodes": [
                    {"kind": "StreamSourceNode", "name": "vendor_input", "data": self.ref},
                    {
                        "kind": "StreamNode",
                        "name": "vendor_sql",
                        "inputs": ["vendor_input"],
                        "output": "1_existing_output",
                        "config": {"sql": "old"},
                    },
                    {
                        "kind": "DorisStorageNode",
                        "name": "vendor_store",
                        "input": "vendor_sql",
                        "storage": self.cluster,
                        "storage_config": {"db": "known_db", "table": "known_table", "flush_timeout": 60},
                    },
                ],
                "operation_config": {"start_position": "continue"},
            },
            "status": {"phase": "Ok"},
        }
        self.flow_get.return_value = self.current
        self.flow_get.side_effect = lambda **kwargs: deepcopy(self.current)
        self.controller.storage_nodes = [DorisStorageNode]
        configs = {
            BKBASE_V4_FLOW_CONFIG: {"operation_config": {"start_position": "continue"}},
            BKBASE_V4_STORAGE_CLUSTER_MAP: {"doris": {"legacy_doris": self.cluster}},
            DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY: {"bkbase_cluster_id": "legacy_doris"},
            DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY: None,
        }
        self.configs = configs
        self.enterContext(
            mock.patch.object(
                flow.GlobalMetaConfig,
                "get",
                side_effect=lambda *args, **kwargs: deepcopy(configs[args[0] if args else kwargs["config_key"]]),
            )
        )
        self.enterContext(mock.patch.object(flow, "resource_lock"))
        self.put.side_effect = self.receipt

    def receipt(self, **kwargs):
        self.current.update(
            metadata=deepcopy(kwargs["metadata"]), spec=deepcopy(kwargs["spec"]), status={"phase": "Pending"}
        )
        return deepcopy(self.current)

    def test_existing_ref_graph_waits_for_stop_then_updates_without_managed_nodes_or_v3_ids(self):
        flow.configure_rule_controller(self.controller)
        self.assertEqual(self.put.call_count, 1)
        self.assertEqual(self.current["metadata"]["annotations"]["task_stopped"], "true")
        self.assertEqual(self.current["spec"]["nodes"][1]["config"]["sql"], "old")
        flow.advance_rule_flow(self.context, self.strategy)
        self.assertEqual(self.put.call_count, 1)
        self.current["status"]["phase"] = "Ok"
        flow.advance_rule_flow(self.context, self.strategy)
        self.assertEqual(self.put.call_count, 2)
        self.assertEqual(
            [node["name"] for node in self.current["spec"]["nodes"]], ["vendor_input", "vendor_sql", "vendor_store"]
        )
        self.assertEqual(self.current["spec"]["nodes"][1]["config"]["sql"], self.strategy.sql)
        self.assertEqual(self.current["spec"]["nodes"][2]["storage_config"]["table"], "known_table")
        self.assertEqual(self.current["spec"]["nodes"][2]["storage_config"]["flush_timeout"], 60)
        self.assertEqual(self.current["metadata"]["annotations"]["task_stopped"], "false")
        self.assertIsNone(flow.advance_rule_flow(self.context, self.strategy)["task_state"])
        self.current["status"]["phase"] = "Ok"
        self.assertEqual(flow.advance_rule_flow(self.context, self.strategy)["task_state"], "running")
        self.strategy.refresh_from_db()
        self.assertEqual({key: self.strategy.backend_data[key] for key in self.legacy}, self.legacy)
        self.post.assert_not_called()

    def test_existing_physical_destination_uses_the_latest_locked_get(self):
        self.current["metadata"]["annotations"]["task_stopped"] = "true"

        @contextmanager
        def lock(*args):
            # 模拟锁外构图后、正式写锁内GET之前，平台目标已由迁移方更新。
            self.current["spec"]["nodes"][2]["storage_config"].update(db="latest_db", table="latest_table")
            yield

        with mock.patch.object(flow, "resource_lock", side_effect=lock):
            flow.configure_rule_controller(self.controller)
        self.assertEqual(self.put.call_count, 1)
        config = self.current["spec"]["nodes"][2]["storage_config"]
        self.assertEqual((config["db"], config["table"]), ("latest_db", "latest_table"))
        self.assertEqual(config["flush_timeout"], 60)
        self.post.assert_not_called()

    def test_latest_locked_running_state_defers_graph_write_and_stops_on_next_advance(self):
        desired = self.build()
        self.current["metadata"]["annotations"]["task_stopped"] = "true"
        self.flow_get.return_value = deepcopy(self.current)
        self.current["metadata"]["annotations"]["task_stopped"] = "false"
        held = False

        class NonReentrantLock:
            def __enter__(lock):
                nonlocal held
                self.assertFalse(held, "Flow lock must not be reacquired while held")
                held = True

            def __exit__(lock, *args):
                nonlocal held
                held = False

        with mock.patch.object(flow, "resource_lock", side_effect=lambda *args: NonReentrantLock()):
            result = flow.apply_rule_flow(self.context, self.strategy, desired)
            self.assertEqual(result["task_state"], "running")
            self.put.assert_not_called()
            self.strategy.refresh_from_db()
            binding = self.strategy.backend_data["bkbase_v4"]
            self.assertEqual(binding["operation"], "wait_stopped")
            self.assertIn("pending_spec", binding)
            self.flow_get.return_value = deepcopy(self.current)
            flow.advance_rule_flow(self.context, self.strategy)
        self.assertEqual(self.put.call_count, 1)
        self.assertEqual(self.current["metadata"]["annotations"]["task_stopped"], "true")
        self.assertEqual(self.current["spec"]["nodes"][1]["config"]["sql"], "old")

    def test_switch_to_unmapped_requested_cluster_fails_before_any_flow_write(self):
        self.configs[DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY]["bkbase_cluster_id"] = "unmapped_new"
        with self.assertRaisesRegex(BKBaseResourceMappingError, "unmapped_new"):
            flow.configure_rule_controller(self.controller)
        self.put.assert_not_called()
        self.post.assert_not_called()
        self.assertEqual(self.current["spec"]["nodes"][2]["storage"], self.cluster)

    @override_settings(BKBASE_API_VERSION="v3")
    def test_version_switch_keeps_v3_controller_and_legacy_fields(self):
        legacy = mock.Mock(return_value="legacy")
        self.controller._update_or_create_bkbase_flow_v3 = legacy
        self.assertEqual(flow.configure_rule_controller(self.controller), "legacy")
        legacy.assert_called_once_with()
        self.flow_get.assert_not_called()
        self.put.assert_not_called()


@override_settings(
    BKBASE_API_VERSION="v4",
    BKBASE_V4_TENANT="tenant_a",
    BKBASE_V4_NAMESPACE="audit",
    BKBASE_PROJECT_ID=999,
    APP_CODE="synthetic_app",
    SECRET_KEY="synthetic_secret",
    BK_RESOURCE={
        "PLATFORM_AUTH_ENABLED": True,
        "PLATFORM_AUTH_ACCESS_USERNAME": "synthetic_platform",
        "PLATFORM_AUTH_ACCESS_TOKEN": "synthetic_token",
    },
)
class MinimalFlowMappingCommandTests(TransactionTestCase):
    lock = command_fixture.FlowMigrationCommandTests.lock
    transport = command_fixture.FlowMigrationCommandTests.transport

    def setUp(self):
        command_fixture.FlowMigrationCommandTests.setUp(self)
        self.ref = {**self.ref, "namespace": "audit"}
        self.remote["metadata"] = self.ref

    def run_simple(self, payload=None, *, apply=False):
        self.input.write_text(json.dumps({"41": self.ref["name"]} if payload is None else payload))
        self.reports += 1
        self.report = Path(self.temp) / f"simple-{self.reports}.jsonl"
        output = StringIO()
        call_command(
            "import_bkbase_v4_flow_mappings", input=str(self.input), report=str(self.report), apply=apply, stdout=output
        )
        return output.getvalue(), [json.loads(line) for line in self.report.read_text().splitlines()]

    def test_simple_mapping_preview_and_apply_derive_strategy_output_and_environment_scope(self):
        _, events = self.run_simple()
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.backend_data, self.before)
        preview = next(item for item in events if item["event"] == "preview")
        self.assertEqual(preview["after_backend_data"]["bkbase_v4"]["flow"], self.ref)
        self.assertEqual(preview["after_backend_data"]["bkbase_v4"]["output_rt_id"], "7_existing_output")
        output, _ = self.run_simple(apply=True)
        self.assertIn("updated=1", output)
        self.strategy.refresh_from_db()
        self.assertEqual({key: self.strategy.backend_data[key] for key in self.before}, self.before)
        self.assertNotIn("managed_nodes", self.strategy.backend_data["bkbase_v4"])
        output, _ = self.run_simple(apply=True)
        self.assertIn("unchanged=1", output)
        self.assertTrue(all(method == "GET" for method, _ in self.http))

    def test_simple_mapping_rejects_ambiguous_local_flow_and_wrong_remote_output(self):
        self.remote["spec"]["nodes"][1]["output"] = "7_wrong"
        with self.assertRaises(CommandError):
            self.run_simple(apply=True)
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.backend_data, self.before)
        self.remote["spec"]["nodes"][1]["output"] = "7_existing_output"
        Strategy.objects.create(namespace="another_audit", strategy_name="alias", backend_data={"flow_id": 41})
        with self.assertRaises(CommandError):
            self.run_simple(apply=True)
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.backend_data, self.before)
