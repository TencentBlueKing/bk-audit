"""V4 规则策略重启通过正式 Flow GET/PUT 按同次回执推进。"""
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
from services.web.strategy_v2.resources import DeleteStrategy, RetryStrategy
from tests.test_bkbase.test_flow_pure_operation import FlowFixture


@override_settings(
    BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit", BKBASE_V4_MCP_PROJECT_ID=11
)
class FlowRestartTests(FlowFixture, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.remote["status"] = {"phase": "Ok", "history_id": 10, "version": 10}
        self.original_spec = deepcopy(self.remote["spec"])
        self.missing_receipt = False
        self.annotation_only = False

    def transport(self, method, url, **kwargs):
        if method.upper() == "GET" and "/v4/tenants/" not in url:
            return super().transport(method, url, **kwargs)
        self.assertFalse(connection.in_atomic_block)
        method = method.upper()
        self.calls.append((method, url, deepcopy(kwargs)))
        if method == "PUT":
            if self.write_hook:
                self.write_hook()
            previous = self.remote["status"]["version"]
            status = {"phase": "Pending", "history_id": previous + 1, "version": previous + 1}
            if self.annotation_only:
                step = len(self.writes())
                status = {
                    "phase": "Pending",
                    "version": previous,
                    "start_time": f"2026-11-06 11:39:0{step}.294000510 UTC",
                }
            self.remote.update(
                metadata=deepcopy(kwargs["json"]["metadata"]),
                spec=deepcopy(kwargs["json"]["spec"]),
                status=status,
            )
            if self.write_error:
                raise self.write_error
            resource = deepcopy(self.remote)
            if self.annotation_only:
                resource["status"]["start_time"] = status["start_time"].replace("294000510", "293996573")
            if self.missing_receipt:
                resource["status"].pop("phase")
            payload = {"result": True, "code": "00", "data": resource}
        elif method == "POST" and url.rstrip("/").endswith("/restart"):
            payload = {"result": True, "code": "00", "data": {}}
        else:
            if self.read_error:
                raise requests.Timeout("Flow GET unavailable")
            payload = self.remote
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps(payload).encode()
        response.url = url
        response.request = requests.Request(method, url).prepare()
        return response

    def restart(self):
        RuleAuditController(self.strategy.pk).enable()
        return self.binding()["operation_id"]

    def complete_step(self, phase="Ok"):
        self.remote["status"]["phase"] = phase

    def assert_write_targets(self, *targets):
        self.assertEqual(
            [call[2]["json"]["metadata"]["annotations"]["task_stopped"] for call in self.writes()], list(targets)
        )

    def test_waits_for_same_stop_and_start_receipts(self):
        operation_id = self.restart()
        self.assert_write_targets("true")
        stop_receipt = deepcopy(self.remote["status"])
        self.remote["status"] = {"phase": "Ok", "history_id": 10, "version": 10}
        self.remote["metadata"]["annotations"]["task_stopped"] = "false"
        self.observe()
        self.assert_write_targets("true")
        self.remote["status"] = stop_receipt
        self.remote["metadata"]["annotations"]["task_stopped"] = "true"
        self.observe()
        self.assert_write_targets("true")
        self.complete_step()
        self.remote["status"].update(history_id=20, version=10)
        self.observe()
        self.assert_write_targets("true", "false")
        self.assertEqual(self.binding()["operation_id"], operation_id)
        self.assertEqual(self.strategy.status, StrategyStatusChoices.UPDATING)
        self.observe()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.UPDATING)
        self.complete_step()
        self.observe()
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.RUNNING)
        self.assertTrue(all("/v4/tenants/" in url for _, url, _ in self.calls))
        for _, _, kwargs in self.writes():
            self.assertEqual(kwargs["json"]["spec"], self.original_spec)
            self.assertEqual(kwargs["json"]["metadata"]["annotations"]["unmanaged"], "keep")
            self.assertIsNone(kwargs["json"]["status"])

    def test_confirmed_stop_failure_cannot_start(self):
        self.restart()
        self.complete_step("Failed")
        self.observe()
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.UPDATE_FAILED)
        self.assert_write_targets("true")

    def assert_restart_continues(self, position):
        self.remote["spec"]["operation_config"] = {"start_position": position, "retained": {"keep": True}}
        original = deepcopy(self.remote["spec"])
        self.restart()
        self.assertEqual(self.writes()[0][2]["json"]["spec"], original)
        self.complete_step()
        self.observe()
        self.assert_write_targets("true", "false")
        expected = deepcopy(original)
        expected["operation_config"]["start_position"] = "continue"
        self.assertEqual(self.writes()[1][2]["json"]["spec"], expected)
        self.complete_step()
        self.observe()
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.RUNNING)
        self.assertTrue(self.binding()["pure_operation"]["goal_observed"])

    def test_restart_from_head_changes_only_start_request_and_observes_its_new_spec(self):
        self.assert_restart_continues("from_head")

    def test_restart_from_tail_changes_only_start_request_and_observes_its_new_spec(self):
        self.assert_restart_continues("from_tail")

    def test_confirmed_start_failure_does_not_resend(self):
        self.restart()
        self.complete_step()
        self.observe()
        self.complete_step("Failed")
        self.observe()
        self.observe()
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.UPDATE_FAILED)
        self.assert_write_targets("true", "false")

    def test_unconfirmed_receipt_does_not_advance(self):
        self.missing_receipt = True
        self.restart()
        self.complete_step()
        self.observe()
        self.assert_write_targets("true")

    def test_annotation_only_update_without_history_or_version_change_completes(self):
        self.annotation_only = True
        self.remote["status"]["start_time"] = "2026-11-06 11:39:00.110 UTC"
        self.restart()
        self.complete_step()
        self.observe()
        self.assert_write_targets("true", "false")
        self.complete_step()
        self.observe()
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.RUNNING)

    def test_annotation_only_update_does_not_use_old_target_or_changed_graph(self):
        self.annotation_only = True
        self.remote["status"]["start_time"] = "2026-11-06 11:39:00.110 UTC"
        self.restart()
        self.complete_step()
        self.remote["metadata"]["annotations"]["task_stopped"] = "false"
        self.observe()
        self.remote["metadata"]["annotations"]["task_stopped"] = "true"
        self.remote["spec"]["unmanaged"] = {"keep": False}
        self.observe()
        self.assert_write_targets("true")

    def test_user_can_retry_after_first_read_failed_before_any_write(self):
        self.read_error = True
        old_operation = self.restart()
        self.assert_write_targets()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.UPDATE_FAILED)
        self.read_error = False
        self.retry_from_product()
        self.assertNotEqual(self.binding()["operation_id"], old_operation)
        self.assert_write_targets("true")

    def retry_from_product(self):
        endpoint = RetryStrategy()
        with mock.patch.object(endpoint, "ensure_active_scene_binding_or_404"), mock.patch(
            "services.web.strategy_v2.resources.get_request_username", return_value="synthetic_operator"
        ):
            endpoint.request({"strategy_id": self.strategy.pk})

    def test_missing_attempt_flag_is_not_proof_of_no_write(self):
        self.read_error = True
        old_operation = self.restart()
        binding = self.binding()
        binding["pure_operation"].pop("attempted")
        self.strategy.save(update_record=False, update_fields=["backend_data"])
        self.read_error = False
        with self.assertRaises(BKBaseFlowOperationPending):
            self.retry_from_product()
        self.assertEqual(self.binding()["operation_id"], old_operation)
        self.assert_write_targets()

    def test_unknown_stop_is_not_resent_or_followed_by_start(self):
        self.write_error = requests.Timeout("stop receipt unavailable")
        self.restart()
        self.complete_step()
        self.observe()
        self.assert_write_targets("true")
        self.assertTrue(self.binding()["pure_operation"]["outcome_unknown"])

    def test_unknown_start_does_not_resend_or_report_success(self):
        self.restart()
        self.complete_step()
        self.write_error = requests.Timeout("start receipt unavailable")
        self.observe()
        self.complete_step()
        self.observe()
        self.assert_write_targets("true", "false")
        self.assertFalse(self.binding()["pure_operation"]["write_fence"])
        self.assertEqual(self.strategy.status, StrategyStatusChoices.UPDATE_FAILED)

    def test_unmatched_completion_exhausts_budget_without_start(self):
        self.restart()
        self.remote["status"] = {"phase": "Ok", "history_id": 12, "version": 12}
        self.remote["metadata"]["annotations"]["task_stopped"] = "false"
        with mock.patch.object(flow_operation, "BKBASE_V4_MAX_POLLS", 1):
            self.observe()
        self.assert_write_targets("true")
        self.assertTrue(self.binding()["pure_operation"]["outcome_unknown"])
        self.assertEqual(self.strategy.status, StrategyStatusChoices.UPDATE_FAILED)

    def test_stop_receipt_is_not_authorization_for_delete_or_another_toggle(self):
        operation_id = self.restart()
        self.assertEqual(self.restart(), operation_id)
        with self.assertRaises(BKBaseFlowOperationPending):
            RuleAuditController(self.strategy.pk).disabled()
        endpoint = DeleteStrategy()
        with mock.patch.object(endpoint, "ensure_active_scene_binding_or_404"), mock.patch.object(
            endpoint, "add_audit_instance_to_context"
        ):
            with self.assertRaises(BKBaseFlowOperationPending):
                endpoint.request({"strategy_id": self.strategy.pk})
        self.assertTrue(Strategy.objects.filter(pk=self.strategy.pk).exists())
        self.assert_write_targets("true")

    def test_old_operation_and_changed_local_configuration_do_not_advance(self):
        self.restart()
        self.complete_step()
        self.observe(operation_id="old-operation")
        self.assert_write_targets("true")
        Strategy.objects.filter(pk=self.strategy.pk).update(sql="SELECT newer_configuration")
        self.observe()
        self.assert_write_targets("true")
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.sql, "SELECT newer_configuration")

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_keeps_the_original_restart_route(self):
        with mock.patch.object(
            RuleAuditController, "_describe_flow_status_v3", return_value="running"
        ), mock.patch.object(RuleAuditController, "_toggle_strategy_v3") as legacy:
            RuleAuditController(self.strategy.pk).enable()
        legacy.assert_called_once_with("restart", force=False)
        self.assertEqual(self.calls, [])

    def test_finished_unknown_stop_allows_explicit_retry_via_regular_start(self):
        self.write_error = requests.Timeout("stop response lost")
        previous = self.restart()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.UPDATE_FAILED)
        self.assertFalse(self.binding()["pure_operation"]["write_fence"])
        self.observe()
        self.assert_write_targets("true")
        self.write_error = None
        self.complete_step()
        self.retry_from_product()
        self.assertNotEqual(self.binding()["operation_id"], previous)
        self.assert_write_targets("true", "false")
        self.complete_step()
        self.observe()
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.RUNNING)

    def test_finished_unknown_start_allows_explicit_new_restart(self):
        self.restart()
        self.complete_step()
        self.write_error = requests.Timeout("start response lost")
        self.observe()
        self.assertFalse(self.binding()["pure_operation"]["write_fence"])
        previous = self.binding()["operation_id"]
        self.write_error = None
        self.complete_step()
        self.retry_from_product()
        self.assertNotEqual(self.binding()["operation_id"], previous)
        self.assert_write_targets("true", "false", "true")

    def test_observation_budget_releases_only_finished_restart_for_user_retry(self):
        self.restart()
        with mock.patch.object(flow_operation, "BKBASE_V4_MAX_POLLS", 1):
            self.observe()
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.UPDATE_FAILED)
        self.assertFalse(self.binding()["pure_operation"]["write_fence"])
        self.assert_write_targets("true")
        self.complete_step()
        self.retry_from_product()
        self.assert_write_targets("true", "false")

    def test_sender_still_in_progress_blocks_restart_retry(self):
        def while_sending():
            with mock.patch.object(flow_operation, "BKBASE_V4_MAX_POLLS", 1):
                self.observe()
            self.assertTrue(self.binding()["pure_operation"]["writer"])
            with self.assertRaises(BKBaseFlowOperationPending):
                self.retry_from_product()

        self.write_hook = while_sending
        self.restart()
        self.assert_write_targets("true")

    def test_retry_preflight_cannot_replace_a_newer_operation(self):
        self.read_error = True
        self.restart()
        self.read_error = False
        previous = self.binding()["operation_id"]
        original = self.transport

        def changed(method, url, **kwargs):
            if method.upper() == "GET":
                data = deepcopy(self.strategy.backend_data)
                data["bkbase_v4"]["operation_id"] = "newer"
                Strategy.objects.filter(pk=self.strategy.pk).update(
                    backend_data=data, status=StrategyStatusChoices.RUNNING
                )
            return original(method, url, **kwargs)

        with mock.patch("requests.sessions.Session.request", side_effect=changed):
            with self.assertRaises((BKBaseOperationSuperseded, BKBaseFlowOperationPending)):
                self.retry_from_product()
        self.assertNotEqual(previous, "newer")
        self.assertEqual(self.binding()["operation_id"], "newer")
        self.assert_write_targets()
