"""真实删除请求在停止声明受理后本地级联，不等实际引擎停止。

SDK传输与队列受控，事务真正提交；不对平台做停止或删除。
拒绝、未发送与未知均保留策略，已保存受理不得重复PUT。
"""
import hashlib
import json
import threading
import traceback
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock
from urllib.parse import urlsplit

import requests
from bk_resource import api
from blueapps.utils.local import request_local
from django.conf import settings
from django.core.cache import cache
from django.db import connection, connections
from django.http import Http404
from django.test import RequestFactory, TransactionTestCase, override_settings

from apps.meta.models import Tag
from services.web.analyze import tasks
from services.web.analyze.constants import BaseControlTypeChoices, ControlTypeChoices
from services.web.analyze.controls.rule_audit import RuleAuditController
from services.web.analyze.models import Control
from services.web.bkbase import flow
from services.web.bkbase.common import get_bkbase_context, resource_params
from services.web.bkbase.exceptions import BKBaseException
from services.web.strategy_v2.constants import StrategyStatusChoices, StrategyType
from services.web.strategy_v2.models import Strategy, StrategyRule, StrategyTag
from services.web.strategy_v2.resources import DeleteStrategy, ToggleStrategy
from services.web.strategy_v2.tasks import StrategyStatusChecker
from tests.test_bkbase.test_flow_pure_operation import FlowFixture


@override_settings(
    BKBASE_API_VERSION="v4",
    BKBASE_V4_TENANT="tenant_a",
    BKBASE_V4_NAMESPACE="audit",
    BKBASE_V4_MCP_PROJECT_ID=11,
)
class StrategyDeleteDeclarationTests(FlowFixture, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.endpoint = DeleteStrategy()
        self.enterContext(mock.patch.object(self.endpoint, "ensure_active_scene_binding_or_404"))
        self.enterContext(mock.patch.object(self.endpoint, "add_audit_instance_to_context"))
        self.reject = False
        self.invalid_response = False
        self.deployment_failure = False
        self.failure_after_save = False
        self.envelope = {"result": True, "code": "00"}
        self.native_response = False
        self.remote["spec"]["maintainers"] = ["synthetic_operator"]
        self.remote["spec"]["operation_config"] = {"start_position": "continue", "retained": 1}

    def transport(self, method, url, **kwargs):
        before = deepcopy(self.remote)
        response = FlowFixture.transport(self, method, url, **kwargs)
        if method.upper() == "GET" and "deploy" in url and self.deployment_failure:
            response._content = json.dumps({"status": "failure", "id": "old_deployment"}).encode()
        if method.upper() == "PUT":
            if self.reject:
                if not self.failure_after_save:
                    self.remote = before
                response._content = json.dumps(
                    {"result": False, "code": "1500100", "data": None, "message": "synthetic refusal"}
                ).encode()
            elif self.invalid_response:
                response._content = json.dumps({"result": True, "code": "00", "data": {"unexpected": True}}).encode()
            elif self.native_response:
                response._content = json.dumps(self.remote).encode()
            else:
                receipt = deepcopy(self.remote)
                receipt["status"]["phase"] = "Pending"
                response._content = json.dumps({**self.envelope, "data": receipt}).encode()
        return response

    def delete(self):
        return self.endpoint.request({"strategy_id": self.strategy.pk})

    def delete_successfully(self):
        try:
            return self.delete()
        except BKBaseException as error:
            self.fail(f"一次删除应能提交停止声明并在明确受理后本地级联: {error}")

    def deletion(self):
        saved = self.current().backend_data.get("bkbase_v4", {})
        self.assertIn("delete_operation", saved, "删除必须有独立提交的持久意图")
        return saved["delete_operation"]

    def current(self):
        return Strategy.objects.get_queryset().get(pk=self.strategy.pk)

    def test_one_request_saves_stop_declaration_then_local_delete_without_mcp_gate(self):
        before = deepcopy(self.remote)
        self.engine = "failure"
        self.delete_successfully()
        self.assertTrue(self.current().is_deleted)
        self.assertEqual(len(self.writes()), 1)
        payload = self.writes()[0][2]["json"]
        self.assertEqual(payload["spec"], before["spec"])
        self.assertEqual(payload["metadata"]["annotations"]["task_stopped"], "true")
        self.assertEqual(payload["metadata"]["annotations"]["unmanaged"], "keep")
        self.assertIsNone(payload["status"])
        self.assertFalse(any("/mcp/" in url for _, url, _ in self.calls))

    def test_delete_accepts_stop_receipt_with_null_inactive_deployment_omitted_by_get(self):
        self.remote["spec"]["nodes"].append({"name": "sql", "kind": "StreamNode", "inputs": ["source"]})
        self.remote["spec"]["operation_config"]["stream_sql_deploy_config"] = {
            "cluster": "published_stream",
            "deploy_mode": "k8s-operator",
            "deploy_config": None,
        }
        expected = deepcopy(self.remote["spec"])
        expected["operation_config"]["batch_sql_deploy_config"] = None

        self.delete_successfully()

        self.assertEqual(len(self.writes()), 1)
        self.assertEqual(self.writes()[0][2]["json"]["spec"], expected)
        self.assertIs(self.deletion()["accepted"], True)
        self.assertFalse(self.deletion()["outcome_unknown"])
        self.assertTrue(self.current().is_deleted)

    def test_failed_cr_is_not_a_stop_declaration_prohibition(self):
        self.remote["status"]["phase"] = "Failed"
        self.delete_successfully()
        self.assertTrue(self.current().is_deleted)
        self.assertEqual(len(self.writes()), 1)

    def test_unknown_receipt_keeps_strategy_and_allows_user_retry(self):
        self.write_error = requests.Timeout("synthetic accepted then timeout")
        for _ in range(2):
            with self.assertRaises(BKBaseException):
                self.delete()
        current = self.current()
        self.assertFalse(current.is_deleted)
        operation = self.deletion()
        self.assertTrue(operation["attempted"])
        self.assertTrue(operation["outcome_unknown"])
        self.assertIsNone(operation["accepted"])
        self.assertEqual(len(self.writes()), 2)

    def test_structured_failure_is_not_local_delete(self):
        self.reject = True
        with self.assertRaises(BKBaseException):
            self.delete()
        self.assertFalse(self.current().is_deleted)
        operation = self.deletion()
        self.assertIsNone(operation["accepted"])
        self.assertTrue(operation["outcome_unknown"])

    def test_normal_return_without_saved_acceptance_cannot_delete(self):
        with mock.patch.object(flow, "prepare_controller_delete", return_value=True):
            with self.assertRaises(BKBaseException):
                self.delete()
        self.assertFalse(self.current().is_deleted)
        self.assertEqual(self.writes(), [])

    def test_unexpected_success_payload_keeps_outcome_unknown(self):
        self.invalid_response = True
        with self.assertRaises(BKBaseException):
            self.delete()
        self.assertFalse(self.current().is_deleted)
        self.assertTrue(self.deletion()["outcome_unknown"])

    def test_get_failure_is_not_sent_and_has_no_local_cascade(self):
        self.read_error = True
        with self.assertRaises(BKBaseException):
            self.delete()
        self.assertFalse(self.current().is_deleted)
        self.assertEqual(self.writes(), [])
        operation = self.deletion()
        self.assertFalse(operation["attempted"])

    def test_scene_check_precedes_all_flow_io(self):
        self.endpoint.ensure_active_scene_binding_or_404.side_effect = Http404("synthetic forbidden binding")
        with self.assertRaises(Http404):
            self.delete()
        self.assertEqual(self.calls, [])
        self.assertNotIn("delete_operation", self.binding())

    def test_actual_tag_and_rule_cascade_runs_only_after_acceptance(self):
        tag = Tag.objects.create(tag_name="synthetic tag")
        StrategyTag.objects.create(strategy_id=self.strategy.pk, tag=tag)
        rule = StrategyRule.objects.create(strategy=self.strategy, rule_name="synthetic rule")
        self.delete_successfully()
        self.assertTrue(self.current().is_deleted)
        self.assertFalse(StrategyTag.objects.filter(strategy_id=self.strategy.pk).exists())
        rule.refresh_from_db()
        self.assertTrue(rule.is_deleted)
        self.assertIn("__deleted_", rule.rule_name)

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_keeps_original_outer_transaction_and_stop_order(self):
        def stop(*args, **kwargs):
            self.assertTrue(connection.in_atomic_block)

        with mock.patch(
            "services.web.analyze.controls.rule_audit.RuleAuditController._describe_flow_status_v3",
            return_value="running",
        ), mock.patch(
            "services.web.analyze.controls.rule_audit.RuleAuditController._toggle_strategy_v3", side_effect=stop
        ) as legacy:
            self.delete()
        self.assertTrue(self.current().is_deleted)
        legacy.assert_called_once_with("stop", force=False)
        self.assertEqual(self.calls, [])

    def test_interruption_after_reservation_reuses_id_and_claims_one_put(self):
        with mock.patch.object(flow, "prepare_controller_delete", side_effect=SystemExit("before dispatch")):
            with self.assertRaises(SystemExit):
                self.delete()
        operation_id = self.deletion()["id"]
        self.assertFalse(self.deletion()["attempted"])
        self.assertEqual(self.calls, [])
        self.delete_successfully()
        self.assertEqual(self.deletion()["id"], operation_id)
        self.assertEqual(len(self.writes()), 1)

    def test_interruption_after_persisted_acceptance_retries_only_local_delete(self):
        with mock.patch.object(flow, "finish_strategy_delete", side_effect=SystemExit("before local transaction")):
            with self.assertRaises(SystemExit):
                self.delete()
        operation_id = self.deletion()["id"]
        self.assertTrue(self.deletion()["accepted"])
        self.assertFalse(self.current().is_deleted)
        self.delete_successfully()
        self.assertEqual(self.deletion()["id"], operation_id)
        self.assertEqual(len(self.writes()), 1)

    def test_local_cascade_rollback_preserves_receipt_for_repeat(self):
        rule = StrategyRule.objects.create(strategy=self.strategy, rule_name="rollback rule")
        with mock.patch.object(self.endpoint, "delete_enum_mappings", side_effect=RuntimeError("local rollback")):
            with self.assertRaises(RuntimeError):
                self.delete()
        self.assertFalse(self.current().is_deleted)
        rule.refresh_from_db()
        self.assertFalse(rule.is_deleted)
        self.assertEqual(rule.rule_name, "rollback rule")
        self.assertTrue(self.deletion()["accepted"])
        operation_id = self.deletion()["id"]
        self.delete_successfully()
        self.assertEqual(self.deletion()["id"], operation_id)
        self.assertEqual(len(self.writes()), 1)

    def test_crash_after_send_claim_is_unknown_and_never_resent(self):
        self.write_hook = mock.Mock(side_effect=SystemExit("writer disappeared"))
        with self.assertRaises(SystemExit):
            self.delete()
        self.write_hook = None
        self.assertTrue(self.deletion()["writer"])
        with self.assertRaises(BKBaseException):
            self.delete()
        self.assertFalse(self.current().is_deleted)
        self.assertEqual(len(self.writes()), 1)

    def test_stopped_resource_without_receipt_still_needs_formal_stop_declaration(self):
        self.remote["metadata"]["annotations"]["task_stopped"] = "true"
        self.engine = "no-start"
        self.delete_successfully()
        self.assertTrue(self.current().is_deleted)
        self.assertEqual(len(self.writes()), 1)
        self.assertTrue(self.deletion()["accepted"])
        self.assertFalse(any("deploy" in url for _, url, _ in self.calls))

    def test_stopped_annotation_without_actual_proof_still_declares_stop(self):
        self.remote["metadata"]["annotations"]["task_stopped"] = "true"
        self.engine = "failure"
        self.delete_successfully()
        self.assertEqual(len(self.writes()), 1)
        self.assertTrue(self.current().is_deleted)

    def test_persisted_pure_stop_acceptance_does_not_need_actual_stop_before_delete(self):
        self.stop()
        self.assertEqual(self.engine, "running")
        self.assertTrue(self.binding()["pure_operation"]["accepted"])
        self.delete_successfully()
        self.assertEqual(len(self.writes()), 1)
        self.assertTrue(self.current().is_deleted)

    def test_draft_and_proven_no_flow_use_local_path(self):
        Strategy.objects.filter(pk=self.strategy.pk).update(status=StrategyStatusChoices.DRAFT, backend_data={})
        self.delete_successfully()
        self.assertEqual(self.calls, [])
        self.assertTrue(self.current().is_deleted)

    def test_legacy_flow_id_without_formal_binding_cannot_be_deleted_as_no_flow(self):
        Strategy.objects.filter(pk=self.strategy.pk).update(backend_data={"flow_id": 123})
        with self.assertRaises(BKBaseException):
            self.delete()
        self.assertFalse(self.current().is_deleted)
        self.assertEqual(self.calls, [])

    def test_pending_create_without_formal_binding_is_not_proven_no_flow(self):
        Strategy.objects.filter(pk=self.strategy.pk).update(status=StrategyStatusChoices.STARTING, backend_data={})
        with self.assertRaises(BKBaseException):
            self.delete()
        self.assertFalse(self.current().is_deleted)
        self.assertEqual(self.calls, [])

    def test_new_graph_or_enable_cannot_pass_persisted_delete_gap(self):
        with mock.patch.object(flow, "finish_strategy_delete", side_effect=SystemExit("hold ready")):
            with self.assertRaises(SystemExit):
                self.delete()
        controller = tasks.call_controller
        for action in ("enable", "update"):
            with self.subTest(action=action), self.assertRaises(BKBaseException):
                controller(
                    action,
                    self.strategy.pk,
                    BaseControlTypeChoices.RULE_AUDIT,
                    bkbase_version=get_bkbase_context()["version"],
                )
        self.assertEqual(len(self.writes()), 1)

    def test_identity_change_after_acceptance_does_not_delete(self):
        def change_namespace():
            Strategy.objects.filter(pk=self.strategy.pk).update(namespace="other_namespace")

        self.write_hook = change_namespace
        with self.assertRaises(BKBaseException):
            self.delete()
        self.assertFalse(self.current().is_deleted)

    def test_repeated_completed_delete_cannot_send_again(self):
        self.delete_successfully()
        with self.assertRaises(Http404):
            self.delete()
        self.assertEqual(len(self.writes()), 1)

    def test_non_bkbase_monitor_delete_keeps_original_consumer(self):
        control = Control.objects.create(control_name="synthetic monitor", control_type_id=ControlTypeChoices.BKM)
        Strategy.objects.filter(pk=self.strategy.pk).update(
            strategy_type=StrategyType.MODEL, control_id=control.pk, backend_data={"id": 171}
        )
        with mock.patch.object(api.bk_monitor, "delete_alarm_strategy", return_value={}) as monitor:
            self.delete_successfully()
        self.assertTrue(self.current().is_deleted)
        self.assertEqual(monitor.call_args.kwargs["ids"], [171])
        self.assertEqual(self.calls, [])

    def disable(self):
        endpoint = ToggleStrategy()
        with mock.patch.object(endpoint, "ensure_active_scene_binding_or_404"), mock.patch.object(
            endpoint, "add_audit_instance_to_context"
        ), mock.patch("services.web.strategy_v2.resources.get_request_username", return_value="synthetic_operator"):
            endpoint.request({"strategy_id": self.strategy.pk, "toggle": False})

    def accepted_failed_start(self):
        Strategy.objects.filter(pk=self.strategy.pk).update(status=StrategyStatusChoices.DISABLED)
        self.remote["metadata"]["annotations"]["task_stopped"] = "true"
        self.engine = "no-start"
        RuleAuditController(self.strategy.pk).enable()
        old_id = self.binding()["operation_id"]
        self.engine, self.deployment_failure = "failure", True
        self.remote["status"]["phase"] = "Failed"
        self.observe(old_id)
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.START_FAILED)
        return old_id

    def test_toggle_request_can_declare_stop_for_failed_cr_without_mcp_gate(self):
        self.remote["status"]["phase"] = "Failed"
        self.disable()
        self.assertTrue(self.binding()["pure_operation"]["accepted"])
        self.assertEqual(len(self.writes()), 1)
        self.assertFalse(any("/mcp/" in url for _, url, _ in self.calls))

    def test_stop_actual_no_start_does_not_depend_on_failed_deploy_history(self):
        self.deployment_failure = True
        self.disable()
        self.engine = "no-start"
        self.observe()
        self.assertEqual(self.binding()["pure_operation"]["goal_observed"], True)
        self.assertEqual(self.strategy.status, StrategyStatusChoices.DISABLED)
        self.assertFalse(any("deploy" in url for _, url, _ in self.calls))

    def test_known_accepted_failed_start_can_be_superseded_by_stop_and_old_callback_expires(self):
        old_id = self.accepted_failed_start()
        self.disable()
        new_id = self.binding()["operation_id"]
        self.assertNotEqual(new_id, old_id)
        self.assertTrue(self.binding()["pure_operation"]["accepted"])
        self.assertEqual(self.binding()["pure_operation"]["target"], "stop")
        before = len(self.calls)
        self.observe(old_id)
        self.assertEqual(len(self.calls), before)
        self.assertEqual(self.binding()["operation_id"], new_id)
        self.engine = "no-start"
        self.remote["status"]["phase"] = "Ok"
        self.observe()
        self.assertEqual(self.binding()["pure_operation"]["goal_observed"], True)

    def test_known_accepted_failed_start_can_be_deleted_after_new_stop_declaration(self):
        old_id = self.accepted_failed_start()
        self.delete_successfully()
        self.assertTrue(self.current().is_deleted)
        self.assertNotEqual(self.deletion()["id"], old_id)
        self.assertEqual(len(self.writes()), 2)

    def test_unknown_start_allows_new_user_actions(self):
        Strategy.objects.filter(pk=self.strategy.pk).update(status=StrategyStatusChoices.DISABLED)
        self.remote["metadata"]["annotations"]["task_stopped"] = "true"
        self.engine = "no-start"
        self.write_error = requests.Timeout("unknown start")
        RuleAuditController(self.strategy.pk).enable()
        Strategy.objects.filter(pk=self.strategy.pk).update(status=StrategyStatusChoices.START_FAILED)
        self.disable()
        with self.assertRaises(BKBaseException):
            self.delete()
        self.assertEqual(len(self.writes()), 3)
        self.assertFalse(self.current().is_deleted)

    def test_non_ok_phase_cannot_claim_actual_stop_from_stale_engine(self):
        self.disable()
        self.remote["status"]["phase"] = "Reconciling"
        self.engine = "no-start"
        self.observe()
        self.assertFalse(self.binding()["pure_operation"]["goal_observed"])
        self.assertNotEqual(self.strategy.status, StrategyStatusChoices.DISABLED)

    def test_start_failure_recovery_declares_start_and_waits_for_formal_running(self):
        Strategy.objects.filter(pk=self.strategy.pk).update(status=StrategyStatusChoices.DISABLED)
        self.remote["status"]["phase"] = "Failed"
        self.remote["metadata"]["annotations"]["task_stopped"] = "true"
        original = deepcopy(self.remote)
        RuleAuditController(self.strategy.pk).enable()
        self.assertEqual(len(self.writes()), 1)
        payload = self.writes()[0][2]["json"]
        expected_metadata = deepcopy(original["metadata"])
        expected_metadata["annotations"]["task_stopped"] = "false"
        self.assertEqual(payload["metadata"], expected_metadata)
        self.assertEqual(payload["spec"], original["spec"])
        pure = self.binding()["pure_operation"]
        self.assertEqual(pure["target"], "start")
        self.assertTrue(pure["attempted"])
        self.assertTrue(pure["accepted"])
        self.assertEqual(pure["failure_baseline"]["phase"], "Failed")
        for phase in ("Failed", "Pending"):
            with self.subTest(phase=phase):
                self.remote["status"]["phase"] = phase
                self.observe()
                self.strategy.refresh_from_db()
                self.assertEqual(self.strategy.status, StrategyStatusChoices.STARTING)
                self.assertFalse(self.binding()["pure_operation"]["goal_observed"])
        self.remote["status"]["phase"] = "Ok"
        self.observe()
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.RUNNING)
        self.assertTrue(self.binding()["pure_operation"]["goal_observed"])
        self.assertEqual(len(self.writes()), 1)

    def test_actual_no_flow_non_draft_can_delete_locally(self):
        Strategy.objects.filter(pk=self.strategy.pk).update(backend_data={})
        self.delete_successfully()
        self.assertTrue(self.current().is_deleted)
        self.assertEqual(self.calls, [])

    def test_malformed_disable_success_does_not_authorize_delete(self):
        self.invalid_response = True
        self.disable()
        self.assertIsNone(self.binding()["pure_operation"]["accepted"])
        self.assertTrue(self.binding()["pure_operation"]["outcome_unknown"])
        with self.assertRaises(BKBaseException):
            self.delete()
        self.assertFalse(self.current().is_deleted)
        self.assertEqual(len(self.writes()), 2)

    def test_structured_disable_failure_remains_unknown(self):
        self.reject = True
        self.disable()
        operation = self.binding()["pure_operation"]
        self.assertIsNone(operation["accepted"])
        self.assertTrue(operation["outcome_unknown"])
        self.assertEqual(self.strategy.status, StrategyStatusChoices.STOP_FAILED)
        self.assertFalse(self.current().is_deleted)

    def test_accepted_start_with_residual_writer_still_blocks_stop_and_delete(self):
        self.accepted_failed_start()
        backend = deepcopy(self.current().backend_data)
        backend["bkbase_v4"]["pure_operation"]["writer"] = "stranded_writer"
        Strategy.objects.filter(pk=self.strategy.pk).update(backend_data=backend)
        for action in (self.disable, self.delete):
            with self.subTest(action=action), self.assertRaises(BKBaseException):
                action()
        self.assertFalse(self.current().is_deleted)
        self.assertEqual(len(self.writes()), 1)

    def test_changed_spec_cannot_be_reported_as_completed_stop(self):
        self.disable()
        self.remote["spec"]["maintainers"] = ["changed_operator"]
        self.engine = "no-start"
        self.observe()
        self.assertFalse(self.binding()["pure_operation"]["goal_observed"])
        self.assertNotEqual(self.strategy.status, StrategyStatusChoices.DISABLED)

    def test_scene_revoked_after_acceptance_cannot_finish_local_cascade(self):
        def revoke():
            self.endpoint.ensure_active_scene_binding_or_404.side_effect = Http404("revoked")

        self.write_hook = revoke
        with self.assertRaises(Http404):
            self.delete()
        self.assertFalse(self.current().is_deleted)
        self.assertTrue(self.deletion()["accepted"])
        self.endpoint.ensure_active_scene_binding_or_404.side_effect = None
        self.delete_successfully()
        self.assertEqual(len(self.writes()), 1)

    def test_pending_delete_blocks_start_graph_and_duplicate_on_other_connection_after_lease_expiry(self):
        configuration = deepcopy(settings.CACHES)
        redis_location = urlsplit(configuration["default"]["LOCATION"])
        prefix = configuration["default"].get("KEY_PREFIX", "")
        configuration["default"]["KEY_PREFIX"] = f"{prefix}:bkbase-delete-concurrency:{self._testMethodName}"
        entered, release = threading.Event(), threading.Event()
        failures, writer_connection = [], []

        def pause():
            with connection.cursor() as cursor:
                cursor.execute("SELECT CONNECTION_ID()")
                writer_connection.append(cursor.fetchone()[0])
            entered.set()
            if not release.wait(10):
                raise AssertionError("Deletion writer was not released")

        def delete():
            request = RequestFactory().post("/synthetic-delete/", HTTP_HOST="localhost")
            request.user = SimpleNamespace(username="synthetic_operator")
            request_local.request = request
            try:
                self.delete()
            except BaseException:
                failures.append(traceback.format_exc())
            finally:
                del request_local.request
                connections.close_all()

        with override_settings(CACHES=configuration):
            self.lock_patch.stop()
            self.write_hook = pause
            writer = threading.Thread(target=delete)
            writer.start()
            try:
                self.assertTrue(entered.wait(5))
                with connection.cursor() as cursor:
                    cursor.execute("SELECT CONNECTION_ID()")
                    self.assertNotEqual(writer_connection[0], cursor.fetchone()[0])
                redis_config = cache.client.get_client().connection_pool.connection_kwargs
                self.assertEqual(redis_config["host"], redis_location.hostname)
                self.assertEqual(int(redis_config["port"]), redis_location.port or 6379)
                self.assertEqual(int(redis_config["db"]), int(redis_location.path.lstrip("/") or "0"))
                params = resource_params(get_bkbase_context(), self.ref)
                key = (
                    "bkbase_v4:"
                    + hashlib.sha256(json.dumps({**params, "kind": "Flow"}, sort_keys=True).encode()).hexdigest()
                )
                cache.delete(key)
                for action in (
                    RuleAuditController(self.strategy.pk).enable,
                    RuleAuditController(self.strategy.pk).update,
                    self.delete,
                ):
                    with self.subTest(action=action), self.assertRaises(BKBaseException):
                        action()
                self.assertFalse(self.current().is_deleted)
                self.assertEqual(len(self.writes()), 1)
            finally:
                release.set()
                writer.join(12)
            self.assertFalse(writer.is_alive())
        self.assertEqual(failures, [])
        self.assertTrue(self.current().is_deleted)
        self.assertEqual(len(self.writes()), 1)

    def non_ok_delete_submits_stop(self, phase):
        self.remote["status"]["phase"] = phase
        self.remote["metadata"]["annotations"]["task_stopped"] = "true"
        self.engine = "no-start"
        self.delete_successfully()
        self.assertTrue(self.current().is_deleted)
        self.assertEqual(len(self.writes()), 1, "非Ok CR不能使用旧引擎快照跳过停止声明")
        self.assertTrue(self.deletion()["accepted"])

    def test_failed_cr_and_old_no_start_still_submit_stop(self):
        self.non_ok_delete_submits_stop("Failed")

    def test_pending_cr_and_old_no_start_still_submit_stop(self):
        self.non_ok_delete_submits_stop("Pending")

    def test_gateway_failure_after_saved_delete_allows_user_retry(self):
        self.reject, self.failure_after_save = True, True
        for _ in range(2):
            with self.assertRaises(BKBaseException):
                self.delete()
        operation = self.deletion()
        self.assertFalse(self.current().is_deleted)
        self.assertFalse(operation["pending"])
        self.assertTrue(operation["outcome_unknown"])
        self.assertIsNone(operation["accepted"])
        self.assertEqual(self.remote["metadata"]["annotations"]["task_stopped"], "true")
        self.assertEqual(len(self.writes()), 2)

    def test_gateway_failure_after_saved_disable_allows_new_declaration(self):
        self.reject, self.failure_after_save = True, True
        self.disable()
        self.disable()
        operation = self.binding()["pure_operation"]
        self.assertFalse(operation["write_fence"])
        self.assertTrue(operation["outcome_unknown"])
        self.assertIsNone(operation["accepted"])
        with self.assertRaises(BKBaseException):
            self.delete()
        self.assertEqual(len(self.writes()), 3)
        self.assertFalse(self.current().is_deleted)

    def invalid_envelope_keeps_delete(self, envelope):
        self.envelope = envelope
        for _ in range(2):
            with self.assertRaises(BKBaseException):
                self.delete()
        self.assertFalse(self.current().is_deleted)
        self.assertIsNone(self.deletion()["accepted"])
        self.assertTrue(self.deletion()["outcome_unknown"])
        self.assertEqual(len(self.writes()), 2)

    def test_contradictory_success_code_cannot_authorize_delete(self):
        self.invalid_envelope_keeps_delete({"result": True, "code": "1500111"})

    def test_missing_result_cannot_authorize_delete(self):
        self.invalid_envelope_keeps_delete({"code": "00"})

    def test_missing_code_cannot_authorize_delete(self):
        self.invalid_envelope_keeps_delete({"result": True})

    def test_non_boolean_result_cannot_authorize_delete(self):
        self.invalid_envelope_keeps_delete({"result": "true", "code": "00"})

    def test_contradictory_success_code_cannot_authorize_disable(self):
        self.envelope = {"result": True, "code": "1500111"}
        self.disable()
        self.assertIsNone(self.binding()["pure_operation"]["accepted"])
        self.assertFalse(self.binding()["pure_operation"]["write_fence"])
        with self.assertRaises(BKBaseException):
            self.delete()
        self.assertEqual(len(self.writes()), 2)

    def test_native_resource_without_receipt_cannot_authorize_delete(self):
        self.native_response = True
        with self.assertRaises(BKBaseException):
            self.delete()
        self.assertFalse(self.current().is_deleted)
        self.assertTrue(self.deletion()["outcome_unknown"])

    def test_native_resource_without_receipt_cannot_authorize_disable(self):
        self.native_response = True
        self.disable()
        self.assertIsNone(self.binding()["pure_operation"]["accepted"])
        self.assertTrue(self.binding()["pure_operation"]["outcome_unknown"])

    def legacy_flow_without_ref(self):
        Strategy.objects.filter(pk=self.strategy.pk).update(backend_data={"flow_id": 123})
        self.strategy.refresh_from_db()

    def test_legacy_flow_without_ref_rejects_toggle_and_keeps_business_status(self):
        self.legacy_flow_without_ref()
        with self.assertRaises(BKBaseException) as caught:
            self.disable()
        self.assertIn("C19", str(caught.exception))
        self.assertEqual(self.current().status, StrategyStatusChoices.RUNNING)
        self.assertEqual(self.calls, [])

    def test_legacy_flow_without_ref_is_not_reported_stopped_by_controller(self):
        self.legacy_flow_without_ref()
        with self.assertRaises(BKBaseException) as caught:
            RuleAuditController(self.strategy.pk)._describe_flow_status()
        self.assertIn("C19", str(caught.exception))
        self.assertEqual(self.calls, [])

    def test_legacy_flow_without_ref_checker_records_error_without_changing_state(self):
        self.legacy_flow_without_ref()
        checker = StrategyStatusChecker()
        result = checker.fetch_flow_status(123, strategy=self.strategy)
        self.assertTrue(result.startswith("error:"), result)
        self.assertIn("C19", result)
        self.assertEqual(checker.judge(self.strategy, result), result)
        self.assertEqual(self.current().status, StrategyStatusChoices.RUNNING)
        self.assertEqual(self.calls, [])

    def test_genuine_no_flow_keeps_no_start_meaning(self):
        Strategy.objects.filter(pk=self.strategy.pk).update(backend_data={}, status=StrategyStatusChoices.DRAFT)
        self.strategy.refresh_from_db()
        self.assertFalse(flow.has_flow(self.strategy))
        self.assertEqual(flow.observe_strategy_status(self.strategy), {"flow_status": "no-start"})
        self.assertEqual(RuleAuditController(self.strategy.pk)._describe_flow_status(), "no-start")
        self.assertEqual(self.calls, [])

    def test_unattempted_stop_goal_cannot_substitute_for_delete_receipt(self):
        self.remote["metadata"]["annotations"]["task_stopped"] = "true"
        self.engine = "no-start"

        def observe_before_send():
            self.read_hook = None
            self.observe()

        self.read_hook = observe_before_send
        self.disable()
        self.assertTrue(self.binding()["pure_operation"]["attempted"])
        self.assertFalse(self.binding()["pure_operation"]["goal_observed"])
        self.assertEqual(len(self.writes()), 1)
        self.delete_successfully()
        self.assertTrue(self.current().is_deleted)
        self.assertEqual(len(self.writes()), 1)
        self.assertTrue(self.deletion()["accepted"])

    def observed_marker_without_send(self):
        operation_id = flow.reserve_strategy_delete(self.strategy)
        backend = deepcopy(self.current().backend_data)
        backend["bkbase_v4"]["delete_operation"].update(stage="ready", no_send_proof="observed_stopped")
        Strategy.objects.filter(pk=self.strategy.pk).update(backend_data=backend)
        self.strategy.refresh_from_db()
        return operation_id

    def test_old_observed_marker_reuses_id_but_requires_formal_declaration(self):
        operation_id = self.observed_marker_without_send()
        self.delete_successfully()
        self.assertTrue(self.current().is_deleted)
        self.assertEqual(self.deletion()["id"], operation_id)
        self.assertEqual(len(self.writes()), 1)
        self.assertTrue(self.deletion()["accepted"])
        self.assertNotIn("no_send_proof", self.deletion())

    def test_finalizer_cannot_consume_observed_marker_as_stop_receipt(self):
        operation_id = self.observed_marker_without_send()
        with self.assertRaises(BKBaseException):
            with flow.finish_strategy_delete(self.strategy, operation_id):
                self.fail("MCP派生快照不能替代删除受理凭证")
        self.assertFalse(self.current().is_deleted)

    def test_old_observed_marker_without_attempt_evidence_is_not_resumed(self):
        self.observed_marker_without_send()
        backend = deepcopy(self.current().backend_data)
        backend["bkbase_v4"]["delete_operation"].pop("attempted")
        Strategy.objects.filter(pk=self.strategy.pk).update(backend_data=backend)
        with self.assertRaises(BKBaseException):
            self.delete()
        self.assertFalse(self.current().is_deleted)
        self.assertEqual(self.calls, [])
