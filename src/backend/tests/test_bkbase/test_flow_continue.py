"""V4每次审计启用均与V3 continue一致，停止及无关配置保持原值。"""

from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, TransactionTestCase, override_settings

from services.web.analyze.constants import FlowDataSourceNodeType
from services.web.analyze.controls.base import BkbaseFlowController
from services.web.analyze.controls.rule_audit import RuleAuditController
from services.web.bkbase import flow
from services.web.strategy_v2.constants import StrategyStatusChoices
from services.web.strategy_v2.models import Strategy
from services.web.strategy_v2.resources import RetryStrategy
from tests.test_bkbase.test_flow_pure_operation import FlowFixture


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit")
class ContinueStartTests(FlowFixture, TransactionTestCase):
    def prepare(self, position, *, failed=False):
        self.remote["spec"]["operation_config"] = {"retained": {"checkpoint": True}}
        if position is not None:
            self.remote["spec"]["operation_config"]["start_position"] = position
        else:
            self.remote["spec"].pop("operation_config")
        self.remote["metadata"]["annotations"]["task_stopped"] = "true"
        backend = deepcopy(self.strategy.backend_data)
        if failed:
            self.remote["status"] = {"phase": "Failed", "message": "synthetic failure"}
            backend["bkbase_v4"]["pending_spec"] = {"nodes": [{"name": "unpublished"}]}
        Strategy.objects.filter(pk=self.strategy.pk).update(
            status=StrategyStatusChoices.START_FAILED if failed else StrategyStatusChoices.DISABLED,
            backend_data=backend,
        )
        expected = deepcopy(self.remote["spec"])
        expected.setdefault("operation_config", {})["start_position"] = "continue"
        return expected

    def assert_start_continues(self, position):
        expected = self.prepare(position)
        RuleAuditController(self.strategy.pk).enable()
        self.assertEqual(len(self.writes()), 1)
        self.assertEqual(self.writes()[0][2]["json"]["spec"], expected)
        self.remote["status"]["phase"] = "Ok"
        self.observe()
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.RUNNING)
        self.assertTrue(self.binding()["pure_operation"]["goal_observed"])

    def test_start_replaces_old_from_head_and_preserves_other_fields(self):
        self.assert_start_continues("from_head")

    def test_start_replaces_old_from_tail_and_preserves_other_fields(self):
        self.assert_start_continues("from_tail")

    def test_start_explicitly_sets_continue_when_operation_config_is_absent(self):
        self.assert_start_continues(None)

    def test_stop_preserves_previous_from_head_configuration(self):
        self.prepare("from_head")
        Strategy.objects.filter(pk=self.strategy.pk).update(status=StrategyStatusChoices.RUNNING)
        self.remote["metadata"]["annotations"]["task_stopped"] = "false"
        original = deepcopy(self.remote["spec"])
        self.stop()
        self.assertEqual(len(self.writes()), 1)
        self.assertEqual(self.writes()[0][2]["json"]["spec"], original)

    def test_failed_enable_changes_only_consumption_position_not_the_unpublished_graph(self):
        expected = self.prepare("from_head", failed=True)
        RuleAuditController(self.strategy.pk).enable()
        self.assertEqual(len(self.writes()), 1)
        self.assertEqual(self.writes()[0][2]["json"]["spec"], expected)
        self.assertEqual(self.binding()["pending_spec"], {"nodes": [{"name": "unpublished"}]})
        self.assertEqual(self.binding()["pure_operation"]["failure_baseline"]["message"], "synthetic failure")

    def test_failed_retry_resource_keeps_pending_spec_and_uses_continue(self):
        expected = self.prepare("from_tail", failed=True)
        endpoint = RetryStrategy()
        with mock.patch.object(endpoint, "ensure_active_scene_binding_or_404"), mock.patch(
            "services.web.strategy_v2.resources.get_request_username", return_value="synthetic_operator"
        ), mock.patch("services.web.strategy_v2.resources.call_controller", side_effect=AssertionError("No rebuild")):
            endpoint.request({"strategy_id": self.strategy.pk})
        self.assertEqual(len(self.writes()), 1)
        self.assertEqual(self.writes()[0][2]["json"]["spec"], expected)
        self.assertEqual(self.binding()["pending_spec"], {"nodes": [{"name": "unpublished"}]})


class ContinueSpecTests(SimpleTestCase):
    def test_direct_start_changes_only_start_position_of_the_current_spec(self):
        ref = {"kind": "Flow", "tenant": "tenant_a", "namespace": "audit", "name": "flow_a"}
        context = {"version": "v4", "tenant": "tenant_a", "namespace": "audit"}
        strategy = SimpleNamespace(backend_data={"bkbase_v4": {"flow": ref}})
        remote = {
            "metadata": ref,
            "spec": {
                "nodes": [],
                "retained": {"keep": True},
                "operation_config": {"start_position": "from_tail", "checkpoint": "keep"},
            },
        }
        expected = deepcopy(remote["spec"])
        expected["operation_config"]["start_position"] = "continue"
        with mock.patch.object(flow, "resource_lock"), mock.patch.object(
            flow.api.bk_base_v4, "flow_get", return_value=deepcopy(remote)
        ), mock.patch.object(
            flow,
            "_write_flow_request",
            side_effect=lambda *a, **kw: {
                "metadata": kw["metadata"],
                "spec": kw["spec"],
                "status": {"phase": "Pending"},
            },
        ) as write:
            flow.operate_rule_flow(context, strategy, action="start")
        self.assertEqual(write.call_args.kwargs["spec"], expected)
        self.assertEqual(remote["spec"]["operation_config"]["start_position"], "from_tail")

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_control_parameters_already_use_continue(self):
        controller = SimpleNamespace(strategy=SimpleNamespace(backend_data={"flow_id": 1}))
        self.assertEqual(BkbaseFlowController.build_update_flow_params(controller)["consuming_mode"], "continue")

    def test_profile_from_head_is_overridden_without_mutating_other_operation_fields(self):
        strategy = SimpleNamespace(
            strategy_id=7,
            strategy_name="synthetic rule",
            namespace="audit",
            sql="SELECT 1",
            backend_data={"bkbase_v4": {"output_name": "rule_output"}},
        )
        controller = SimpleNamespace(
            strategy=strategy,
            rt_ids=["7_input"],
            storage_nodes=[],
            check_source_type=lambda value: FlowDataSourceNodeType.REALTIME,
            _build_sql_node_config=lambda value: {"node_type": "realtime"},
        )
        profile = {"operation_config": {"start_position": "from_head", "retained": {"checkpoint": True}}}
        original = deepcopy(profile)
        context = {"version": "v4", "tenant": "tenant_a", "namespace": "audit"}
        with mock.patch.object(flow.GlobalMetaConfig, "get", return_value=profile), mock.patch.object(
            flow,
            "_input_result_table_refs",
            return_value={
                "7_input": {"kind": "ResultTable", "tenant": "tenant_a", "namespace": "inputs", "name": "input"}
            },
        ), mock.patch.object(
            flow.metadata_service, "get_result_tables", return_value=[{"result_table_id": "7_input", "bk_biz_id": 7}]
        ), mock.patch.object(
            flow, "_save_operation_binding"
        ), mock.patch.object(
            flow, "get_bkbase_v4_platform_username", return_value="synthetic_user"
        ):
            spec = flow.build_controller_spec(controller, context=context)
        self.assertEqual(spec["operation_config"], {"start_position": "continue", "retained": {"checkpoint": True}})
        self.assertEqual(profile, original)
