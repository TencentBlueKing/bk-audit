"""可信Flow失败后显式原配置启动，不发布待改图或重发未知写。"""
import json
from copy import deepcopy
from unittest import mock

import requests
from django.db import connection
from django.test import TransactionTestCase, override_settings

from services.web.analyze.controls.rule_audit import RuleAuditController
from services.web.bkbase import flow_operation
from services.web.bkbase.exceptions import (
    BKBaseFlowOperationPending,
    BKBaseOperationSuperseded,
)
from services.web.strategy_v2.constants import StrategyStatusChoices
from services.web.strategy_v2.models import Strategy
from services.web.strategy_v2.resources import RetryStrategy
from tests.test_bkbase.test_flow_pure_operation import FlowFixture


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit")
class FailedFlowRecoveryTests(FlowFixture, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.remote["status"].update(history_id=10, version=10)
        self.keep_old_failure = True
        self.controller = self.enterContext(
            mock.patch(
                "services.web.strategy_v2.resources.call_controller",
                side_effect=AssertionError("Recovery must not build or publish a graph"),
            )
        )

    def transport(self, method, url, **kwargs):
        if method.upper() != "PUT":
            return super().transport(method, url, **kwargs)
        self.assertFalse(connection.in_atomic_block)
        self.calls.append(("PUT", url, deepcopy(kwargs)))
        if self.write_hook:
            self.write_hook()
        previous = deepcopy(self.remote["status"])
        self.remote.update(metadata=deepcopy(kwargs["json"]["metadata"]), spec=deepcopy(kwargs["json"]["spec"]))
        if self.write_error:
            raise self.write_error
        receipt = deepcopy(self.remote)
        receipt["status"] = {
            "phase": "Pending",
            "history_id": previous.get("history_id", 0) + 1,
            "version": previous.get("version", 0) + 1,
        }
        if previous["phase"] != "Failed" or not self.keep_old_failure:
            self.remote["status"] = deepcopy(receipt["status"])
        response = requests.Response()
        response.status_code = 200
        response.url = url
        response.request = requests.Request(method, url).prepare()
        response._content = json.dumps({"result": True, "code": "00", "data": receipt}).encode()
        return response

    def failed(self, *, local=StrategyStatusChoices.UPDATE_FAILED, pending=False):
        self.remote["status"].update(phase="Failed", message="synthetic original failure")
        backend = deepcopy(self.strategy.backend_data)
        backend["bkbase_v4"].update(operation_id="original", managed_nodes=["source"])
        if pending:
            backend["bkbase_v4"]["pending_spec"] = {"nodes": [{"name": "unpublished"}], "keep": "desired"}
        self.strategy.backend_data = backend
        self.strategy.status = local
        self.strategy.status_msg = "synthetic original failure"
        self.strategy.save(update_record=False, update_fields=["backend_data", "status", "status_msg"])

    def retry(self):
        endpoint = RetryStrategy()
        with mock.patch.object(endpoint, "ensure_active_scene_binding_or_404"), mock.patch(
            "services.web.strategy_v2.resources.get_request_username", return_value="synthetic_operator"
        ):
            endpoint.request({"strategy_id": self.strategy.pk})
        self.strategy.refresh_from_db()

    def observe_current(self):
        self.observe()
        self.strategy.refresh_from_db()

    def test_enable_failed_flow_preserves_original_spec_and_observes_before_success(self):
        self.failed(local=StrategyStatusChoices.DISABLED)
        self.remote["metadata"]["annotations"]["task_stopped"] = "true"
        original = deepcopy(self.remote)
        RuleAuditController(self.strategy.pk).enable()
        self.strategy.refresh_from_db()
        self.assertEqual(len(self.writes()), 1)
        sent = self.writes()[0][2]["json"]
        expected_metadata = deepcopy(original["metadata"])
        expected_metadata["annotations"]["task_stopped"] = "false"
        self.assertEqual(sent["metadata"], expected_metadata)
        self.assertEqual(sent["spec"], original["spec"])
        self.assertEqual(self.strategy.status, StrategyStatusChoices.STARTING)
        self.assertIn("synthetic original failure", self.strategy.status_msg)
        self.observe_current()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.STARTING)
        self.remote["status"] = {"phase": "Pending", "version": 11}
        self.observe_current()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.STARTING)
        self.remote["status"]["phase"] = "Ok"
        self.observe_current()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.RUNNING)
        self.assertEqual(len(self.writes()), 1)

    def test_enable_with_local_running_and_formal_failed_uses_original_start(self):
        self.failed(local=StrategyStatusChoices.RUNNING)
        original = deepcopy(self.remote["spec"])
        RuleAuditController(self.strategy.pk).enable()
        self.strategy.refresh_from_db()
        self.assertEqual(len(self.writes()), 1)
        self.assertEqual(self.writes()[0][2]["json"]["spec"], original)
        self.assertEqual(self.writes()[0][2]["json"]["metadata"]["annotations"]["task_stopped"], "false")
        self.assertFalse(self.binding()["pure_operation"].get("restart", False))
        self.assertEqual(self.strategy.status, StrategyStatusChoices.STARTING)

    def test_product_retry_restores_original_flow_and_keeps_pending_spec_unpublished(self):
        self.failed(pending=True)
        original_spec = deepcopy(self.remote["spec"])
        pending = deepcopy(self.binding()["pending_spec"])
        self.retry()
        self.assertEqual(len(self.writes()), 1)
        self.assertEqual(self.writes()[0][2]["json"]["spec"], original_spec)
        self.assertEqual(self.binding()["pending_spec"], pending)
        self.assertEqual(self.strategy.status, StrategyStatusChoices.STARTING)
        self.assertNotEqual(self.binding()["operation_id"], "original")
        self.controller.assert_not_called()
        self.remote["status"]["phase"] = "Ok"
        self.observe_current()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.RUNNING)
        self.assertEqual(self.binding()["pending_spec"], pending)
        self.assertIn("未发布", self.strategy.status_msg)
        self.assertEqual(self.strategy.backend_data["retained"], {"a": 1})

    def test_product_retry_without_pending_spec_uses_start_not_graph_controller(self):
        self.failed(local=StrategyStatusChoices.FAILED)
        self.retry()
        self.assertEqual(len(self.writes()), 1)
        self.assertEqual(self.writes()[0][2]["json"]["metadata"]["annotations"]["task_stopped"], "false")
        self.assertNotIn("pending_spec", self.binding())
        self.controller.assert_not_called()

    def test_failed_restart_product_retry_only_sends_original_start(self):
        original = deepcopy(self.remote["spec"])
        flow_operation.request_restart(self.strategy)
        self.remote["status"].update(phase="Failed", message="synthetic stop failure")
        self.observe_current()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.UPDATE_FAILED)
        self.assertIn("synthetic stop failure", self.strategy.status_msg)
        self.retry()
        self.assertEqual(
            [x[2]["json"]["metadata"]["annotations"]["task_stopped"] for x in self.writes()], ["true", "false"]
        )
        self.assertEqual(self.writes()[-1][2]["json"]["spec"], original)
        self.assertFalse(self.binding()["pure_operation"].get("restart", False))
        self.assertEqual(self.strategy.status, StrategyStatusChoices.STARTING)

    def test_pending_remote_does_not_allow_start(self):
        self.strategy.status = StrategyStatusChoices.DISABLED
        self.strategy.save(update_record=False, update_fields=["status"])
        self.remote["status"]["phase"] = "Pending"
        RuleAuditController(self.strategy.pk).enable()
        self.strategy.refresh_from_db()
        self.assertEqual(self.writes(), [])
        self.assertEqual(self.strategy.status, StrategyStatusChoices.START_FAILED)

    def test_unknown_recovery_write_is_not_resent_and_can_be_explicitly_retried(self):
        self.failed(pending=True)
        pending = deepcopy(self.binding()["pending_spec"])
        self.write_error = requests.Timeout("synthetic write result unknown")
        self.retry()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.START_FAILED)
        self.assertTrue(self.binding()["pure_operation"]["outcome_unknown"])
        self.observe_current()
        self.assertEqual(len(self.writes()), 1)
        self.write_error = None
        self.remote["status"]["phase"] = "Ok"
        self.retry()
        self.assertEqual(len(self.writes()), 2)
        self.assertEqual(self.binding()["pending_spec"], pending)
        self.controller.assert_not_called()

    @mock.patch.object(flow_operation, "BKBASE_V4_MAX_POLLS", 1)
    def test_stale_failed_observation_uses_existing_budget_without_resending(self):
        self.failed(pending=True)
        self.retry()
        self.observe_current()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.START_FAILED)
        self.assertIn("synthetic original failure", self.strategy.status_msg)
        self.assertFalse(self.binding()["pure_operation"]["write_fence"])
        self.assertFalse(self.binding()["pure_operation"]["observing"])
        self.assertEqual(len(self.writes()), 1)
        self.assertIn("pending_spec", self.binding())

    def test_new_failure_after_recovery_is_shown_and_not_automatically_retried(self):
        self.failed()
        self.retry()
        self.remote["status"].update(phase="Failed", version=11, message="synthetic new failure")
        self.observe_current()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.STARTING)
        self.assertIn("synthetic new failure", self.strategy.status_msg)
        self.assertTrue(self.binding()["pure_operation"]["observing"])
        with mock.patch.object(flow_operation, "BKBASE_V4_MAX_POLLS", 1):
            self.observe_current()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.START_FAILED)
        self.assertIn("synthetic new failure", self.strategy.status_msg)
        self.assertFalse(self.binding()["pure_operation"]["observing"])
        self.assertEqual(len(self.writes()), 1)

    def test_newer_operation_during_recovery_preflight_is_not_replaced(self):
        self.failed(pending=True)

        def newer():
            self.read_hook = None
            backend = deepcopy(self.strategy.backend_data)
            backend["bkbase_v4"]["operation_id"] = "newer"
            Strategy.objects.filter(pk=self.strategy.pk).update(
                backend_data=backend, status=StrategyStatusChoices.RUNNING
            )

        self.read_hook = newer
        with self.assertRaises(BKBaseOperationSuperseded):
            self.retry()
        self.assertEqual(self.binding()["operation_id"], "newer")
        self.assertEqual(self.writes(), [])

    def test_configuration_change_during_recovery_preflight_is_not_replaced(self):
        self.failed(pending=True)

        def changed():
            self.read_hook = None
            Strategy.objects.filter(pk=self.strategy.pk).update(sql="SELECT newer_configuration")

        self.read_hook = changed
        with self.assertRaises(BKBaseOperationSuperseded):
            self.retry()
        self.assertEqual(self.writes(), [])
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.sql, "SELECT newer_configuration")

    def test_active_generic_writer_blocks_recovery_before_remote_read(self):
        self.failed(pending=True)
        backend = deepcopy(self.strategy.backend_data)
        backend["bkbase_v4"]["flow_write"] = {"token": "active", "operation_id": "original"}
        self.strategy.backend_data = backend
        self.strategy.save(update_record=False, update_fields=["backend_data"])
        with self.assertRaises(BKBaseFlowOperationPending):
            self.retry()
        self.assertEqual(self.calls, [])
        self.assertEqual(self.binding()["flow_write"]["token"], "active")

    def test_active_alias_writer_blocks_recovery_without_remote_write(self):
        self.failed()
        Strategy.objects.create(
            namespace="audit",
            strategy_name="synthetic alias",
            strategy_type=self.strategy.strategy_type,
            status=StrategyStatusChoices.STOPPING,
            backend_data={
                "bkbase_v4": {
                    "flow": self.ref,
                    "operation_id": "alias",
                    "pure_operation": {"id": "alias", "target": "stop", "writer": "active", "write_fence": True},
                }
            },
        )
        with self.assertRaises(BKBaseFlowOperationPending):
            self.retry()
        self.assertEqual(self.calls, [])

    def assert_preflight_failure_preserved(self, *, enable):
        """两种实际入口均先读Failed，再模拟登记后的读异常/未收敛。"""
        original_backend = deepcopy(self.strategy.backend_data)
        original_remote = deepcopy(self.remote)
        for fault in ("timeout", "invalid", "pending"):
            with self.subTest(enable=enable, fault=fault):
                self.strategy.backend_data = deepcopy(original_backend)
                self.remote = deepcopy(original_remote)
                self.read_error = False
                self.calls.clear()
                self.failed(
                    local=StrategyStatusChoices.RUNNING if enable else StrategyStatusChoices.UPDATE_FAILED, pending=True
                )
                reads = []

                def after_preflight():
                    reads.append(True)
                    if len(reads) == 2:
                        if fault == "timeout":
                            self.read_error = True
                        elif fault == "invalid":
                            self.remote["kind"] = "Unexpected"
                        else:
                            self.remote["status"]["phase"] = "Pending"

                self.read_hook = after_preflight
                if enable:
                    RuleAuditController(self.strategy.pk).enable()
                else:
                    self.retry()
                self.strategy.refresh_from_db()
                self.assertEqual(len(reads), 2)
                self.assertEqual(self.writes(), [])
                self.assertEqual(self.strategy.status, StrategyStatusChoices.START_FAILED)
                self.assertIn("synthetic original failure", self.strategy.status_msg)
                self.assertFalse(self.binding()["pure_operation"]["attempted"])
                self.assertIn("pending_spec", self.binding())
                self.read_hook = None
                self.read_error = False

    def test_enable_preserves_preflight_failure_when_next_read_cannot_start(self):
        self.assert_preflight_failure_preserved(enable=True)

    def test_product_retry_preserves_preflight_failure_when_next_read_cannot_start(self):
        self.assert_preflight_failure_preserved(enable=False)

    def test_enable_read_error_preserves_known_local_failure(self):
        self.failed(local=StrategyStatusChoices.DISABLED)
        self.read_error = True
        RuleAuditController(self.strategy.pk).enable()
        self.strategy.refresh_from_db()
        self.assertEqual(self.writes(), [])
        self.assertEqual(self.strategy.status, StrategyStatusChoices.START_FAILED)
        self.assertIn("synthetic original failure", self.strategy.status_msg)

    def test_unrelated_failed_status_changes_do_not_finish_recovery(self):
        self.failed()
        self.retry()
        self.remote["status"].update(update_time="unrelated timestamp", unrelated="changed")
        self.observe_current()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.STARTING)
        self.assertTrue(self.binding()["pure_operation"]["observing"])
        self.assertTrue(self.binding()["pure_operation"]["write_fence"])
        self.assertIn("synthetic original failure", self.strategy.status_msg)
        self.assertEqual(len(self.writes()), 1)

    def test_ordinary_start_failure_still_ends_observation(self):
        self.strategy.status = StrategyStatusChoices.DISABLED
        self.strategy.save(update_record=False, update_fields=["status"])
        RuleAuditController(self.strategy.pk).enable()
        self.remote["status"].update(phase="Failed", message="synthetic ordinary start failure")
        self.observe_current()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.START_FAILED)
        self.assertIn("synthetic ordinary start failure", self.strategy.status_msg)
        self.assertFalse(self.binding()["pure_operation"]["observing"])
        self.assertFalse(self.binding()["pure_operation"]["write_fence"])
        self.assertEqual(len(self.writes()), 1)

    def test_normal_enable_after_completed_start_keeps_restart_behavior(self):
        self.strategy.status = StrategyStatusChoices.DISABLED
        self.strategy.save(update_record=False, update_fields=["status"])
        RuleAuditController(self.strategy.pk).enable()
        self.remote["status"]["phase"] = "Ok"
        self.observe_current()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.RUNNING)
        RuleAuditController(self.strategy.pk).enable()
        self.assertEqual(
            [x[2]["json"]["metadata"]["annotations"]["task_stopped"] for x in self.writes()],
            ["false", "true"],
        )
        self.assertTrue(self.binding()["pure_operation"]["restart"])

    def test_completed_recovery_diagnostic_does_not_change_later_ordinary_start_failure(self):
        self.failed(local=StrategyStatusChoices.DISABLED)
        RuleAuditController(self.strategy.pk).enable()
        self.remote["status"]["phase"] = "Ok"
        self.observe_current()
        self.assertTrue(self.binding()["pure_operation"]["goal_observed"])
        flow_operation.request(self.strategy, "start")
        self.remote["status"].update(phase="Failed", message="synthetic later ordinary failure")
        self.observe_current()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.START_FAILED)
        self.assertFalse(self.binding()["pure_operation"]["observing"])
        self.assertIn("synthetic later ordinary failure", self.strategy.status_msg)
