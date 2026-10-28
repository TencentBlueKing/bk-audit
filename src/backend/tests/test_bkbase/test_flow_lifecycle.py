"""整图创建重试、先停后改和历史部署隔离的回归。"""
from copy import deepcopy
from unittest import mock

from django.test import TestCase, override_settings

from services.web.bkbase import flow
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.strategy_v2.models import Strategy


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit")
class FlowLifecycleTests(TestCase):
    def setUp(self):
        transport = mock.patch(
            "requests.sessions.Session.request", side_effect=AssertionError("Unexpected unmocked HTTP request")
        )
        transport.start()
        self.addCleanup(transport.stop)
        self.context = {"version": "v4", "tenant": "tenant_a", "namespace": "audit"}
        self.strategy = Strategy.objects.create(namespace="audit", strategy_name="rule", backend_data={})
        self.spec = {
            "alias": "rule",
            "nodes": [{"name": "source"}, {"name": "sql", "inputs": ["source"]}],
            "operation_config": {"start_position": "continue"},
        }

    def test_retry_does_not_stop_unchanged_new_flow(self):
        remote = None

        def create(**kw):
            nonlocal remote
            remote = {"metadata": kw["metadata"], "spec": kw["spec"], "status": {"phase": "Pending"}}
            return deepcopy(remote)

        with mock.patch("services.web.bkbase.flow.resource_lock"), mock.patch(
            "services.web.bkbase.flow.get_resource_or_none", side_effect=lambda *a, **kw: deepcopy(remote)
        ), mock.patch("services.web.bkbase.flow.api.bk_base_v4.flow_create", side_effect=create) as post, mock.patch(
            "services.web.bkbase.flow.get_rule_flow_status", return_value={"task_state": None}
        ), mock.patch(
            "services.web.bkbase.flow.operate_rule_flow"
        ) as stop:
            flow.apply_rule_flow(self.context, self.strategy, self.spec)
            ref = deepcopy(self.strategy.backend_data["bkbase_v4"]["flow"])
            flow.apply_rule_flow(self.context, self.strategy, self.spec)
            post.assert_called_once()
            stop.assert_not_called()
            self.assertEqual(self.strategy.backend_data["bkbase_v4"]["flow"], ref)

    def test_graph_change_waits_for_stop_then_preserves_unmanaged_nodes(self):
        ref = {"kind": "Flow", "tenant": "tenant_a", "namespace": "audit", "name": "flow_a"}
        self.strategy.backend_data = {"flow_id": 7, "bkbase_v4": {"flow": ref, "managed_nodes": ["source", "old_sql"]}}
        self.strategy.save(update_fields=["backend_data"])
        remote = {
            "metadata": {"name": "flow_a", "annotations": {"keep": "value"}},
            "spec": {
                "nodes": [{"name": "source"}, {"name": "old_sql", "inputs": ["source"]}, {"name": "other"}],
                "operation_config": {"keep": True},
                "unknown": True,
            },
            "status": {"phase": "Ok"},
        }
        with mock.patch("services.web.bkbase.flow.resource_lock"), mock.patch(
            "services.web.bkbase.flow.get_resource_or_none", return_value=remote
        ), mock.patch("services.web.bkbase.flow.api.bk_base_v4.flow_get", return_value=remote), mock.patch(
            "services.web.bkbase.flow.get_rule_flow_status",
            side_effect=[{"task_state": "running"}, {"task_state": "stopped"}],
        ), mock.patch(
            "services.web.bkbase.flow.operate_rule_flow"
        ) as stop, mock.patch(
            "services.web.bkbase.flow.api.bk_base_v4.flow_update",
            side_effect=lambda **kw: {"metadata": kw["metadata"], "spec": kw["spec"]},
        ) as put:
            flow.apply_rule_flow(self.context, self.strategy, self.spec)
            stop.assert_called_once_with(self.context, self.strategy, action="stop")
            put.assert_not_called()
            flow.apply_rule_flow(self.context, self.strategy, self.spec)
            sent = put.call_args.kwargs
            self.assertEqual([n["name"] for n in sent["spec"]["nodes"]], ["source", "sql", "other"])
            self.assertTrue(sent["spec"]["unknown"])
            self.assertTrue(sent["spec"]["operation_config"]["keep"])
            self.assertEqual(sent["metadata"]["annotations"], {"keep": "value", "task_stopped": "false"})
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.backend_data["flow_id"], 7)

    def test_old_flow_id_does_not_enable_v4_legacy_fallback(self):
        self.strategy.backend_data = {"flow_id": 7}
        self.strategy.save(update_fields=["backend_data"])
        with mock.patch("services.web.bkbase.flow.api.bk_base.create_flow") as legacy:
            with self.assertRaises(BKBaseResourceMappingError):
                flow.apply_rule_flow(self.context, self.strategy, self.spec)
            legacy.assert_not_called()

    def test_restart_does_not_reuse_previous_successful_deployment(self):
        ref = {"kind": "Flow", "tenant": "tenant_a", "namespace": "audit", "name": "flow_a"}
        self.strategy.backend_data = {"bkbase_v4": {"flow": ref, "requested_action": "restart"}}
        self.strategy.save(update_fields=["backend_data"])
        old = {"task_state": "running", "engine_flow_id": 1, "deployment": {"status": "success", "id": 10}}
        with mock.patch("services.web.bkbase.flow.get_rule_flow_status", return_value=old), mock.patch(
            "services.web.bkbase.flow.api.bk_base_v4.flow_restart"
        ), mock.patch("services.web.bkbase.flow.advance_rule_flow", return_value=old):
            flow.operate_rule_flow(self.context, self.strategy, action="restart")
            self.assertEqual(flow.strategy_deploy_data(self.strategy)["status"], "other")
        new = {**old, "deployment": {"status": "success", "id": 11}}
        with mock.patch("services.web.bkbase.flow.advance_rule_flow", return_value=new):
            self.assertEqual(flow.strategy_deploy_data(self.strategy)["status"], "success")
