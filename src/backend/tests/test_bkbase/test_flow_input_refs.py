"""构图只使用已存在且经过身份核对的输入ResultTable引用。"""
import json
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

import requests
from django.test import TransactionTestCase, override_settings

from api.bk_base_v4.default import BkBaseV4Resource, FlowUpdate
from services.web.analyze.constants import FlowDataSourceNodeType
from services.web.analyze.storage_node import DorisStorageNode
from services.web.bkbase import flow
from services.web.bkbase.constants import (
    BKBASE_V4_FLOW_CONFIG,
    BKBASE_V4_STORAGE_CLUSTER_MAP,
)
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.constants import (
    DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
    DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY,
)
from services.web.databus.models import Snapshot
from services.web.strategy_v2.models import Strategy


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit")
class FlowInputRefTests(TransactionTestCase):
    def setUp(self):
        self.context = {
            "version": "v4",
            "tenant": "tenant_a",
            "namespace": "audit",
            "rt_namespaces": {"1_input": "inputs"},
        }
        self.enterContext(mock.patch.object(flow, "get_bkbase_context", return_value=self.context))
        self.ref = {"kind": "ResultTable", "tenant": "tenant_a", "namespace": "inputs", "name": "physical_input_a"}
        self.strategy = Strategy.objects.create(namespace="audit", strategy_name="rule", sql="SELECT * FROM 1_input")
        self.controller = SimpleNamespace(
            strategy=self.strategy,
            rt_ids=["1_input"],
            check_source_type=lambda rt: FlowDataSourceNodeType.REALTIME,
            _build_sql_node_config=lambda biz: {"node_type": "realtime"},
            storage_nodes=[],
        )
        self.metadata = self.enterContext(mock.patch.object(flow.metadata_service, "get_result_tables"))
        self.metadata.return_value = [{"result_table_id": "1_input", "bk_biz_id": 1}]
        self.enterContext(
            mock.patch.object(
                flow.GlobalMetaConfig, "get", return_value={"operation_config": {"start_position": "continue"}}
            )
        )
        self.enterContext(
            mock.patch.object(
                flow, "bk_resource_settings", SimpleNamespace(PLATFORM_AUTH_ACCESS_USERNAME="synthetic_operator")
            )
        )
        self.flow_get = self.enterContext(mock.patch.object(flow.api.bk_base_v4, "flow_get"))
        self.flow_get.return_value = None
        self.enterContext(
            mock.patch.object(
                flow, "get_resource_or_none", side_effect=lambda *args, **kwargs: self.flow_get.return_value
            )
        )
        self.rt_get = self.enterContext(mock.patch.object(flow.api.bk_base_v4, "result_table_resource_get"))
        self.rt_get.return_value = {
            "kind": "ResultTable",
            "metadata": {**self.ref, "labels": {"result_table_id": "1_input"}},
            "spec": {},
            "status": {"phase": "Ok"},
        }
        self.post = self.enterContext(mock.patch.object(flow.api.bk_base_v4, "flow_create"))
        self.put = self.enterContext(mock.patch.object(flow.api.bk_base_v4, "flow_update"))

    def bind_snapshot(self, name="snapshot_a", ref=None, logical="1_input"):
        return Snapshot.objects.create(
            system_id="synthetic_system",
            resource_type_id=name,
            bkbase_table_id=logical,
            bkbase_v4_resources={"result_table_id": logical, "result_table": deepcopy(ref or self.ref)},
        )

    def build(self):
        return flow.build_controller_spec(self.controller, context=self.context)

    def test_controller_sql_update_preserves_latest_locked_doris_configuration_in_the_sdk_request(self):
        self.bind_snapshot()
        self.controller.storage_nodes = [DorisStorageNode]
        doris = {"kind": "Doris", "tenant": "tenant_a", "namespace": "clusters", "name": "doris_a"}
        configs = {
            BKBASE_V4_FLOW_CONFIG: {
                "operation_config": {"start_position": "continue"},
                "doris_databases": {"doris_a": "audit_db"},
            },
            BKBASE_V4_STORAGE_CLUSTER_MAP: {"doris": {"legacy_doris": doris}},
            DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY: {"bkbase_cluster_id": "legacy_doris"},
            DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY: None,
        }
        flow_ref = {"kind": "Flow", "tenant": "tenant_a", "namespace": "audit", "name": "flow_a"}
        sent = []

        def transport(method, url, **kwargs):
            self.assertEqual(method, "PUT")
            self.assertTrue(url.endswith("/v4/tenants/tenant_a/namespaces/audit/flows/flow_a/"))
            sent.append(deepcopy(kwargs["json"]))
            response = requests.Response()
            response.status_code = 200
            response._content = json.dumps(
                {
                    "result": True,
                    "code": "00",
                    "data": {
                        "metadata": sent[-1]["metadata"],
                        "spec": sent[-1]["spec"],
                        "status": {"phase": "Pending"},
                    },
                }
            ).encode()
            response.url = url
            response.request = requests.Request(method, url).prepare()
            return response

        with mock.patch.object(
            flow.GlobalMetaConfig, "get", side_effect=lambda *args, **kw: configs[args[0] if args else kw["config_key"]]
        ), mock.patch.object(flow, "resource_lock"), mock.patch.object(
            BkBaseV4Resource, "build_header", return_value={}
        ), mock.patch(
            "requests.sessions.Session.request", side_effect=transport
        ):
            original_spec = self.build()
            original_spec["nodes"][-1]["storage_config"].update(flush_timeout=60, tokenizers={"event_data": ","})
            self.strategy.backend_data["bkbase_v4"].update(
                flow=flow_ref, managed_nodes=[node["name"] for node in original_spec["nodes"]]
            )
            self.strategy.sql = "SELECT id FROM 1_input"
            self.strategy.save(update_fields=["backend_data", "sql"])
            current = {
                "kind": "Flow",
                "metadata": {**flow_ref, "annotations": {"task_stopped": "true"}},
                "spec": original_spec,
                "status": {"phase": "Ok"},
            }
            self.flow_get.return_value = current
            desired = self.build()
            locked = deepcopy(current)
            locked["spec"]["nodes"][-1]["storage_config"]["flush_timeout"] = 120
            self.flow_get.side_effect = [locked]
            self.put.side_effect = FlowUpdate().request
            flow.apply_rule_flow(self.context, self.strategy, desired)
            self.assertEqual(len(sent), 1)
            self.assertEqual(sent[0]["spec"]["nodes"][1]["config"]["sql"], "SELECT id FROM 1_input")
            self.assertIn("flush_timeout", sent[0]["spec"]["nodes"][-1]["storage_config"])
            self.assertEqual(sent[0]["spec"]["nodes"][-1]["storage_config"]["flush_timeout"], 120)
            self.assertEqual(sent[0]["spec"]["nodes"][-1]["storage_config"]["tokenizers"], {"event_data": ","})
            self.flow_get.side_effect = None
            self.flow_get.return_value = {"kind": "Flow", **deepcopy(sent[0]), "status": {"phase": "Ok"}}
            flow.apply_rule_flow(self.context, self.strategy, self.build())
            self.assertEqual(len(sent), 1)

    def assert_rejected_before_output_or_remote_writes(self):
        before = deepcopy(self.strategy.backend_data)
        with self.assertRaises(BKBaseResourceMappingError):
            flow.configure_rule_controller(self.controller)
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.backend_data, before)
        self.post.assert_not_called()
        self.put.assert_not_called()

    def test_missing_ref_is_resolved_from_formal_logical_id_without_local_binding(self):
        with mock.patch.object(
            flow.api.bk_base_v4,
            "result_table_info",
            return_value={
                "metadata": {key: self.ref[key] for key in ("tenant", "namespace", "name")},
                "spec": {"predefiendResultTableId": "1_input", "bizId": 1},
                "status": {"related": []},
            },
        ) as lookup:
            spec = self.build()
        self.assertEqual(spec["nodes"][0]["data"], self.ref)
        lookup.assert_called_once_with(tenant="tenant_a", result_table_id="1_input")
        self.rt_get.assert_not_called()
        self.post.assert_not_called()
        self.put.assert_not_called()

    def test_local_binding_uses_actual_name_in_another_authorized_project(self):
        self.bind_snapshot()
        spec = self.build()
        self.assertEqual(spec["nodes"][0]["data"], self.ref)
        self.rt_get.assert_called_once_with(namespace="inputs", name="physical_input_a")

    def test_existing_flow_input_is_inherited_after_logical_identity_check(self):
        flow_ref = {"kind": "Flow", "tenant": "tenant_a", "namespace": "audit", "name": "flow_a"}
        self.strategy.backend_data = {"bkbase_v4": {"flow": flow_ref}}
        self.strategy.save(update_fields=["backend_data"])
        self.flow_get.return_value = {
            "kind": "Flow",
            "metadata": flow_ref,
            "spec": {"nodes": [{"name": "original_source", "kind": "StreamSourceNode", "data": self.ref}]},
        }
        spec = self.build()
        self.assertEqual(spec["nodes"][0]["data"], self.ref)
        self.post.assert_not_called()
        self.put.assert_not_called()

    def test_mismatched_logical_label_is_rejected_before_stopping_existing_flow(self):
        self.bind_snapshot()
        flow_ref = {"kind": "Flow", "tenant": "tenant_a", "namespace": "audit", "name": "flow_a"}
        self.strategy.backend_data = {"bkbase_v4": {"flow": flow_ref, "output_name": "retained_output"}}
        self.strategy.save(update_fields=["backend_data"])
        self.flow_get.return_value = {
            "kind": "Flow",
            "metadata": flow_ref,
            "spec": {"nodes": [{"name": "original_source", "kind": "StreamSourceNode", "data": self.ref}]},
        }
        self.rt_get.return_value["metadata"]["labels"]["result_table_id"] = "1_other"
        self.assert_rejected_before_output_or_remote_writes()

    def test_conflicting_local_bindings_are_rejected(self):
        self.bind_snapshot()
        self.bind_snapshot(name="snapshot_b", ref={**self.ref, "name": "physical_input_b"})
        self.rt_get.side_effect = lambda **kw: {
            "kind": "ResultTable",
            "metadata": {**self.ref, "name": kw["name"], "labels": {"result_table_id": "1_input"}},
            "spec": {},
        }
        self.assert_rejected_before_output_or_remote_writes()

    def test_one_missing_join_input_prevents_all_writes(self):
        self.bind_snapshot()
        self.controller.rt_ids.append("1_missing")
        self.context["rt_namespaces"]["1_missing"] = "inputs"
        self.metadata.return_value.append({"result_table_id": "1_missing", "bk_biz_id": 1})
        with mock.patch.object(flow.api.bk_base_v4, "result_table_info", return_value={}):
            self.assert_rejected_before_output_or_remote_writes()

    def test_mismatched_or_cross_tenant_resource_is_rejected(self):
        self.bind_snapshot()
        self.rt_get.return_value["metadata"]["tenant"] = "tenant_b"
        self.assert_rejected_before_output_or_remote_writes()

    def test_persisted_pending_spec_is_checked_before_stopping_or_writing(self):
        flow_ref = {"kind": "Flow", "tenant": "tenant_a", "namespace": "audit", "name": "flow_a"}
        pending = {
            "nodes": [
                {
                    "name": flow.stable_name("src", "1_input"),
                    "kind": "StreamSourceNode",
                    "data": {**self.ref, "name": "1_input"},
                }
            ]
        }
        self.strategy.backend_data = {
            "bkbase_v4": {
                "flow": flow_ref,
                "requested_action": "start",
                "pending_spec": pending,
            }
        }
        self.strategy.save(update_fields=["backend_data"])
        self.flow_get.return_value = {
            "kind": "Flow",
            "metadata": {**flow_ref, "annotations": {"task_stopped": "false"}},
            "spec": {"nodes": [{"name": "original_source", "kind": "StreamSourceNode", "data": self.ref}]},
            "status": {"phase": "Ok"},
        }
        before = deepcopy(self.strategy.backend_data)
        with mock.patch.object(flow, "resource_lock"), self.assertRaises(BKBaseResourceMappingError):
            flow.advance_rule_flow(self.context, self.strategy)
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.backend_data, before)
        self.post.assert_not_called()
        self.put.assert_not_called()

    def pending_graph_with_extra_source(self, *, stopped=False):
        ref = {"kind": "Flow", "tenant": "tenant_a", "namespace": "audit", "name": "flow_a"}
        source = {"name": "arbitrary_migrated_input", "kind": "StreamSourceNode", "data": self.ref}
        desired = {"alias": "updated", "nodes": [deepcopy(source)]}
        other_ref = {**self.ref, "name": "physical_other"}
        current = {
            "kind": "Flow",
            "metadata": {**ref, "annotations": {"task_stopped": "true" if stopped else "false"}},
            "spec": {
                "alias": "old",
                "operation_config": {},
                "nodes": [source, {"name": "second_migrated_input", "kind": "StreamSourceNode", "data": other_ref}],
            },
            "status": {"phase": "Ok"},
        }
        self.strategy.backend_data = {
            "bkbase_v4": {
                "flow": ref,
                "pending_spec": desired,
                "requested_action": "start",
                "managed_nodes": ["stale_local_name"],
            }
        }
        self.strategy.save(update_fields=["backend_data"])
        self.flow_get.return_value = current
        self.rt_get.side_effect = lambda **kwargs: {
            "kind": "ResultTable",
            "metadata": {**self.ref, "name": kwargs["name"]},
            "spec": {"predefiendResultTableId": "1_input" if kwargs["name"] == self.ref["name"] else "1_other"},
        }
        self.put.side_effect = lambda **kwargs: {
            "metadata": kwargs["metadata"],
            "spec": kwargs["spec"],
            "status": {"phase": "Pending"},
        }
        return desired, current

    def test_pending_graph_checks_desired_source_ref_before_stop(self):
        desired, _ = self.pending_graph_with_extra_source()
        desired["nodes"][0]["data"] = {}
        self.strategy.backend_data["bkbase_v4"]["pending_spec"] = desired
        self.strategy.save(update_fields=["backend_data"])
        with mock.patch.object(flow, "resource_lock"), self.assertRaises(BKBaseResourceMappingError):
            flow.advance_rule_flow(self.context, self.strategy)
        self.put.assert_not_called()

    def test_pending_graph_rejects_two_desired_resources_with_one_logical_id(self):
        desired, _ = self.pending_graph_with_extra_source()
        desired["nodes"].append(
            {"kind": "StreamSourceNode", "name": "another", "data": {**self.ref, "name": "physical_b"}}
        )
        self.strategy.backend_data["bkbase_v4"]["pending_spec"] = desired
        self.strategy.save(update_fields=["backend_data"])
        self.rt_get.side_effect = lambda **kwargs: {
            "kind": "ResultTable",
            "metadata": {**self.ref, "name": kwargs["name"]},
            "spec": {"predefiendResultTableId": "1_input"},
        }
        with mock.patch.object(flow, "resource_lock"), self.assertRaises(BKBaseResourceMappingError):
            flow.advance_rule_flow(self.context, self.strategy)
        self.put.assert_not_called()

    def test_complete_update_rechecks_desired_identity_before_put(self):
        self.pending_graph_with_extra_source(stopped=True)
        valid = {"kind": "ResultTable", "metadata": self.ref, "spec": {"predefiendResultTableId": "1_input"}}
        invalid = deepcopy(valid)
        invalid["metadata"]["name"] = "identity_changed"
        self.rt_get.side_effect = [valid, invalid]
        with mock.patch.object(flow, "resource_lock"), self.assertRaises(BKBaseResourceMappingError):
            flow.advance_rule_flow(self.context, self.strategy)
        self.put.assert_not_called()

    def test_graph_stop_rechecks_desired_identity_before_put(self):
        self.pending_graph_with_extra_source()
        valid = {"kind": "ResultTable", "metadata": self.ref, "spec": {"predefiendResultTableId": "1_input"}}
        invalid = deepcopy(valid)
        invalid["metadata"]["name"] = "identity_changed"
        self.rt_get.side_effect = [valid, valid, invalid]
        with mock.patch.object(flow, "resource_lock"), self.assertRaises(BKBaseResourceMappingError):
            flow.advance_rule_flow(self.context, self.strategy)
        self.put.assert_not_called()

    def test_whole_graph_removes_unneeded_source_instead_of_preserving_external_ownership(self):
        _, current = self.pending_graph_with_extra_source(stopped=True)
        old_names = deepcopy(self.strategy.backend_data["bkbase_v4"]["managed_nodes"])
        with mock.patch.object(flow, "resource_lock"):
            flow.advance_rule_flow(self.context, self.strategy)
        self.put.assert_called_once()
        self.assertEqual(self.put.call_args.kwargs["spec"]["nodes"], current["spec"]["nodes"][:1])
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.backend_data["bkbase_v4"]["managed_nodes"], old_names)

    def test_position_update_keeps_native_names_for_the_complete_declared_graph(self):
        _, current = self.pending_graph_with_extra_source()
        current["spec"]["operation_config"] = {"start_position": "continue"}
        self.strategy.backend_data["bkbase_v4"].pop("pending_spec")
        self.strategy.save(update_fields=["backend_data"])

        def update(**kwargs):
            current.update(
                metadata=deepcopy(kwargs["metadata"]), spec=deepcopy(kwargs["spec"]), status={"phase": "Pending"}
            )
            return deepcopy(current)

        self.put.side_effect = update
        with mock.patch.object(flow, "resource_lock"):
            flow.operate_rule_flow(self.context, self.strategy, action="restart", start_position="from_head")
            self.assertEqual(self.put.call_count, 1)
            self.assertEqual(len(self.strategy.backend_data["bkbase_v4"]["pending_spec"]["nodes"]), 2)
            current["status"]["phase"] = "Ok"
            flow.advance_rule_flow(self.context, self.strategy)
        self.assertEqual(self.put.call_count, 2)
        self.assertEqual(
            [node["name"] for node in self.put.call_args.kwargs["spec"]["nodes"]],
            ["arbitrary_migrated_input", "second_migrated_input"],
        )

    def test_arbitrary_desired_source_name_uses_ref_identity_without_prefix_gate(self):
        _, current = self.pending_graph_with_extra_source(stopped=True)
        desired = {"nodes": [{"name": "new_arbitrary_name", "kind": "StreamSourceNode", "data": self.ref}]}
        with mock.patch.object(flow, "resource_lock"):
            flow.apply_rule_flow(self.context, self.strategy, desired)
        self.put.assert_called_once()
        self.assertEqual(self.put.call_args.kwargs["spec"]["nodes"][0]["name"], current["spec"]["nodes"][0]["name"])
        self.assertEqual(self.put.call_args.kwargs["spec"]["nodes"][0]["data"], self.ref)

    def test_unknown_create_with_remote_resource_is_not_adopted_as_empty_noop(self):
        _, current = self.pending_graph_with_extra_source()
        binding = self.strategy.backend_data["bkbase_v4"]
        binding.pop("managed_nodes")
        binding["operation"] = "create"
        binding["pending_spec"] = deepcopy(current["spec"])
        self.strategy.save(update_fields=["backend_data"])
        with mock.patch.object(flow, "resource_lock"), self.assertRaises(BKBaseResourceMappingError):
            flow.advance_rule_flow(self.context, self.strategy)
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.backend_data["bkbase_v4"]["operation"], "create")
        self.put.assert_not_called()
        self.post.assert_not_called()

    def test_complete_owned_graph_can_change_a_second_source_without_local_node_ownership(self):
        _, current = self.pending_graph_with_extra_source(stopped=True)
        desired = deepcopy(current["spec"])
        desired["nodes"][1]["description"] = "updated"
        self.strategy.backend_data["bkbase_v4"].pop("managed_nodes")
        self.strategy.save(update_fields=["backend_data"])
        with mock.patch.object(flow, "resource_lock"):
            flow.apply_rule_flow(self.context, self.strategy, desired)
        self.put.assert_called_once()
        self.assertEqual(self.put.call_args.kwargs["spec"]["nodes"][1]["description"], "updated")

    def test_noop_ignores_and_preserves_obsolete_local_node_list(self):
        _, current = self.pending_graph_with_extra_source()
        current["spec"]["operation_config"]["start_position"] = "continue"
        old_names = deepcopy(self.strategy.backend_data["bkbase_v4"]["managed_nodes"])
        with mock.patch.object(flow, "resource_lock"):
            flow.apply_rule_flow(self.context, self.strategy, deepcopy(current["spec"]))
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.backend_data["bkbase_v4"]["managed_nodes"], old_names)
        self.put.assert_not_called()

    def test_whole_graph_can_delete_obsolete_source_without_any_managed_nodes(self):
        desired, _ = self.pending_graph_with_extra_source(stopped=True)
        self.strategy.backend_data["bkbase_v4"].pop("managed_nodes")
        self.strategy.save(update_fields=["backend_data"])
        with mock.patch.object(flow, "resource_lock"):
            flow.apply_rule_flow(self.context, self.strategy, desired)
        self.put.assert_called_once()
        self.assertEqual(len(self.put.call_args.kwargs["spec"]["nodes"]), 1)

    def test_bound_existing_flow_missing_is_not_recreated(self):
        desired, _ = self.pending_graph_with_extra_source()
        self.strategy.backend_data["bkbase_v4"].pop("managed_nodes")
        self.strategy.save(update_fields=["backend_data"])
        self.flow_get.return_value = None
        with mock.patch.object(flow, "resource_lock"), self.assertRaises(BKBaseResourceMappingError):
            flow.apply_rule_flow(self.context, self.strategy, desired)
        self.post.assert_not_called()
        self.put.assert_not_called()
