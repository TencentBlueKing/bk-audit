"""普通启停经真实控制器与SDK，按正式Flow配置回读完成。"""
import json
from copy import deepcopy
from unittest import mock

from django.test import TransactionTestCase, override_settings

from services.web.analyze.controls.rule_audit import RuleAuditController
from services.web.bkbase import flow
from services.web.strategy_v2.constants import StrategyStatusChoices
from services.web.strategy_v2.models import Strategy
from services.web.strategy_v2.resources import ToggleStrategy
from services.web.strategy_v2.tasks import StrategyStatusChecker
from tests.test_bkbase.test_flow_pure_operation import FlowFixture


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit")
class FlowNativeToggleTests(FlowFixture, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.bad_receipt = None

    def transport(self, method, url, **kwargs):
        if "/v4/tenants/" not in url:
            raise AssertionError("Flow consumers must use the native resource endpoint")
        response = super().transport(method, url, **kwargs)
        if method.upper() == "PUT" and self.bad_receipt:
            payload = json.loads(response.content)
            self.bad_receipt(payload["data"])
            response._content = json.dumps(payload).encode()
        return response

    def toggle_from_product(self, active):
        endpoint = ToggleStrategy()
        with mock.patch.object(endpoint, "ensure_active_scene_binding_or_404"), mock.patch.object(
            endpoint, "add_audit_instance_to_context"
        ), mock.patch("services.web.strategy_v2.resources.get_request_username", return_value="synthetic_operator"):
            endpoint.request({"strategy_id": self.strategy.pk, "toggle": active})

    def test_stop_waits_for_applied_configuration_without_mcp(self):
        original = deepcopy(self.remote["spec"])
        self.toggle_from_product(False)
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.STOPPING)
        self.remote["status"]["phase"] = "Pending"
        self.observe()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.STOPPING)
        self.remote["status"]["phase"] = "Ok"
        self.observe()
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.DISABLED)
        self.assertEqual(len(self.writes()), 1)
        self.assertEqual(self.writes()[0][2]["json"]["spec"], original)
        self.assertTrue(self.binding()["pure_operation"]["goal_observed"])

    def test_start_waits_for_applied_configuration_without_mcp(self):
        Strategy.objects.filter(pk=self.strategy.pk).update(status=StrategyStatusChoices.DISABLED)
        self.remote["metadata"]["annotations"]["task_stopped"] = "true"
        self.toggle_from_product(True)
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.STARTING)
        self.remote["status"]["phase"] = "Reconciling"
        self.observe()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.STARTING)
        self.remote["status"]["phase"] = "Ok"
        self.observe()
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.RUNNING)
        self.assertEqual(len(self.writes()), 1)

    def test_start_receipt_with_a_different_spec_is_unknown(self):
        Strategy.objects.filter(pk=self.strategy.pk).update(status=StrategyStatusChoices.DISABLED)
        self.bad_receipt = lambda resource: resource["spec"].update(unmanaged={"foreign": True})
        self.toggle_from_product(True)
        self.observe()
        pure = self.binding()["pure_operation"]
        self.assertTrue(pure["outcome_unknown"])
        self.assertFalse(pure["goal_observed"])
        self.assertEqual(self.strategy.status, StrategyStatusChoices.START_FAILED)
        self.assertEqual(len(self.writes()), 1)

    def test_wrong_target_does_not_terminate_as_new_failure(self):
        self.stop()
        self.remote["metadata"]["annotations"]["task_stopped"] = "false"
        self.remote["status"]["phase"] = "Failed"
        self.observe()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.STOPPING)
        self.assertTrue(self.binding()["pure_operation"]["observing"])

    def assert_failed_message(self, active):
        if active:
            Strategy.objects.filter(pk=self.strategy.pk).update(status=StrategyStatusChoices.DISABLED)
            self.remote["metadata"]["annotations"]["task_stopped"] = "true"
        self.toggle_from_product(active)
        self.remote["status"] = {"phase": "Failed", "message": "input field is unavailable"}
        self.observe()
        self.strategy.refresh_from_db()
        self.assertIn("input field is unavailable", self.strategy.status_msg)
        self.assertNotIn("C16", self.strategy.status_msg)
        self.assertEqual(
            self.strategy.status, StrategyStatusChoices.START_FAILED if active else StrategyStatusChoices.STOP_FAILED
        )

    def test_start_preserves_the_platform_failure_reason(self):
        self.assert_failed_message(True)

    def test_stop_preserves_the_platform_failure_reason(self):
        self.assert_failed_message(False)

    def test_read_only_inspection_projects_applied_configuration(self):
        before = deepcopy(self.binding())
        checker = StrategyStatusChecker()
        self.assertEqual(checker.fetch_flow_status(None, strategy=self.strategy), "running")
        self.remote["metadata"]["annotations"]["task_stopped"] = "true"
        self.assertEqual(RuleAuditController(self.strategy.pk)._describe_flow_status(), "no-start")
        self.remote["status"]["phase"] = "Pending"
        self.assertEqual(flow.observe_strategy_status(self.strategy), {"flow_status": "pending"})
        self.assertEqual(self.binding(), before)
        self.assertEqual(self.writes(), [])
