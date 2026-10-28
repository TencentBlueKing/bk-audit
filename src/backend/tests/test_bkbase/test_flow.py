"""验证Flow整图转换、稳定身份和真实运行状态边界。"""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from services.web.bkbase import flow
from services.web.bkbase.exceptions import BKBaseResourceMappingError


class FlowTests(SimpleTestCase):
    def setUp(self):
        self.context = {"version": "v4", "tenant": "tenant_a", "namespace": "audit", "mcp_project_id": 7}
        self.ref = {"kind": "Flow", "tenant": "tenant_a", "namespace": "audit", "name": "flow_a"}

    def test_compile_realtime_graph(self):
        strategy = SimpleNamespace(
            strategy_id=7, strategy_name="test rule", namespace="audit", sql="SELECT * FROM rt_a", backend_data={}
        )
        rt = {"result_table_id": "rt_a", "bk_biz_id": 1, "fields": [], "storages": {}}
        bindings = {
            "sources": {
                "rt_a": {
                    "kind": "StreamSourceNode",
                    "data": {"kind": "ResultTable", "tenant": "tenant_a", "namespace": "inputs", "name": "rt_a"},
                }
            },
            "output": "1_audit_rule_7",
            "biz_id": 1,
            "sql_node": {
                "kind": "StreamNode",
                "config": {"sql": "SELECT * FROM rt_a", "window_config": {"type": None}},
            },
            "storages": [],
        }
        result = flow.build_rule_flow(strategy, rt_metadata=[rt], binding_map=bindings)
        source_node, sql_node = result["nodes"]
        self.assertEqual(source_node["data"]["namespace"], "inputs")
        self.assertEqual(sql_node["inputs"], [source_node["name"]])
        self.assertEqual(sql_node["output"], "1_audit_rule_7")
        self.assertEqual(result, flow.build_rule_flow(strategy, rt_metadata=[rt], binding_map=bindings))

    def test_phase_ok_is_not_engine_running(self):
        strategy = SimpleNamespace(backend_data={"bkbase_v4": {"flow": self.ref}})
        with mock.patch(
            "services.web.bkbase.flow.api.bk_base_v4.flow_get",
            return_value={"metadata": {"name": "flow_a"}, "spec": {"nodes": []}, "status": {"phase": "Ok"}},
        ), mock.patch("services.web.bkbase.flow.api.bk_base_v4.flows", return_value=[]):
            result = flow.get_rule_flow_status(self.context, strategy)
            self.assertNotEqual(result["task_state"], "running")

    def test_engine_flow_id_must_match_exactly_once(self):
        with mock.patch(
            "services.web.bkbase.flow.api.bk_base_v4.flows",
            return_value=[{"flow_id": 1, "flow_name": "flow_a"}, {"flow_id": 2, "flow_name": "flow_a"}],
        ):
            with self.assertRaises(BKBaseResourceMappingError):
                flow.resolve_engine_flow_id(self.context, self.ref)

    def test_stop_preserves_spec_and_uses_string_annotation(self):
        original = {
            "metadata": {"name": "flow_a", "annotations": {"other": "value"}},
            "spec": {
                "nodes": [{"kind": "StreamNode", "name": "sql"}],
                "operation_config": {"start_position": "continue"},
                "maintainers": ["operator"],
            },
            "status": {"phase": "Ok"},
        }
        strategy = SimpleNamespace(backend_data={"bkbase_v4": {"flow": self.ref}})
        with mock.patch("services.web.bkbase.flow.resource_lock"), mock.patch(
            "services.web.bkbase.flow.api.bk_base_v4.flow_get", return_value=original
        ), mock.patch(
            "services.web.bkbase.flow.api.bk_base_v4.flow_update",
            side_effect=lambda **kw: {"metadata": kw["metadata"], "spec": kw["spec"], "status": {"phase": "Pending"}},
        ) as put:
            result = flow.operate_rule_flow(self.context, strategy, action="stop")
            self.assertEqual(
                put.call_args.kwargs["metadata"]["annotations"], {"other": "value", "task_stopped": "true"}
            )
            self.assertEqual(put.call_args.kwargs["spec"], original["spec"])
            self.assertIsNone(result["task_state"])
