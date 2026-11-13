"""已有 Flow 纯启停的真实控制器、SDK 与任务契约。

仅替换外部传输和队列，不绕过请求序列化及数据库状态。
超时不证明失败，旧意图不能穿过新写入或触发图发布。
"""
import hashlib
import json
import threading
from contextlib import contextmanager
from copy import deepcopy
from unittest import mock
from urllib.parse import urlsplit

import requests
from bk_resource.exceptions import APIRequestError
from django.conf import settings
from django.core.cache import cache
from django.db import connection, connections, transaction
from django.test import TransactionTestCase, override_settings

from api.bk_base_v4.default import BkBaseV4Resource
from core.exceptions import LockError
from services.web.analyze import tasks
from services.web.analyze.controls.rule_audit import RuleAuditController
from services.web.bkbase import flow, flow_operation
from services.web.bkbase.common import (
    get_bkbase_context,
    resource_lock,
    resource_params,
)
from services.web.bkbase.exceptions import BKBaseException
from services.web.strategy_v2.constants import StrategyStatusChoices, StrategyType
from services.web.strategy_v2.models import Strategy
from services.web.strategy_v2.resources import (
    DeleteStrategy,
    RetryStrategy,
    ToggleStrategy,
    UpdateStrategy,
)
from services.web.strategy_v2.tasks import check_strategy_status_anomalies


class FlowFixture:
    def setUp(self):
        self.ref = {"kind": "Flow", "tenant": "tenant_a", "namespace": "audit", "name": "flow_a"}
        self.strategy = Strategy.objects.create(
            namespace="audit",
            strategy_name="synthetic rule",
            strategy_type=StrategyType.RULE,
            status=StrategyStatusChoices.RUNNING,
            backend_data={"flow_id": 123, "bkbase_v4": {"flow": self.ref}, "retained": {"a": 1}},
        )
        self.remote = {
            "kind": "Flow",
            "metadata": {**self.ref, "annotations": {"task_stopped": "false", "unmanaged": "keep"}},
            "spec": {
                "nodes": [{"name": "source", "kind": "StreamSourceNode"}],
                "operation_config": {"start_position": "continue"},
                "unmanaged": {"keep": True},
            },
            "status": {"phase": "Ok"},
        }
        self.engine = "running"
        self.calls = []
        self.write_error = None
        self.read_error = False
        self.write_hook = None
        self.read_hook = None
        self.response_hook = None
        self.redirect = False
        self.atomic_depth = len(connection.atomic_blocks)
        self.enterContext(mock.patch("requests.sessions.Session.request", side_effect=self.transport))
        self.enterContext(mock.patch.object(BkBaseV4Resource, "build_header", return_value={}))
        self.lock_patch = mock.patch.object(flow, "resource_lock")
        self.lock_patch.start()
        self.addCleanup(self.lock_patch.stop)
        self.queue = self.enterContext(mock.patch.object(tasks.check_flow_status, "delay"))
        self.requeue = self.enterContext(mock.patch.object(tasks.check_flow_status, "apply_async"))
        self.monitor = self.enterContext(mock.patch.object(tasks.toggle_monitor, "delay"))

    def transport(self, method, url, **kwargs):
        self.assertEqual(len(connection.atomic_blocks), self.atomic_depth, "HTTP must not hold DB row locks")
        self.calls.append((method.upper(), url, deepcopy(kwargs)))
        if method.upper() == "PUT":
            self.strategy.refresh_from_db()
            self.assertEqual(
                self.strategy.status,
                StrategyStatusChoices.STOPPING
                if kwargs["json"]["metadata"]["annotations"]["task_stopped"] == "true"
                else StrategyStatusChoices.STARTING,
            )
            self.assertTrue(self.binding()["operation_id"])
            if self.write_hook:
                self.write_hook()
            self.remote["metadata"] = deepcopy(kwargs["json"]["metadata"])
            self.remote["spec"] = deepcopy(kwargs["json"]["spec"])
            if self.write_error:
                raise self.write_error
            receipt = deepcopy(self.remote)
            receipt["status"]["phase"] = "Pending"
            payload = {"result": True, "code": "00", "data": receipt}
        elif "/v4/tenants/" in url:
            if self.read_hook:
                self.read_hook()
            if self.read_error:
                raise requests.Timeout("synthetic read timeout")
            payload = self.remote
        elif url.rstrip("/").endswith("/mcp/flows"):
            payload = {"count": 1, "results": [{"flow_id": 17, "flow_name": "flow_a"}]}
        elif "/status/" in url:
            payload = {"flow_status": self.engine}
        elif "deploy" in url:
            payload = {"status": "success", "id": "deployment_a"}
        else:
            raise AssertionError(f"Unexpected endpoint: {method} {url}")
        response = requests.Response()
        response.status_code = 307 if self.redirect and method.upper() == "PUT" else 200
        response._content = json.dumps(payload).encode()
        response.url = url
        response.request = requests.Request(method, url).prepare()
        if self.response_hook:
            self.response_hook(method, url)
        return response

    def binding(self):
        self.strategy.refresh_from_db()
        return self.strategy.backend_data["bkbase_v4"]

    def writes(self):
        return [call for call in self.calls if call[0] == "PUT"]

    def stop(self):
        try:
            RuleAuditController(self.strategy.pk).disabled()
        except APIRequestError as error:
            self.fail(f"纯启停应持久记录未决或未发送结果，不向调用方丢出裸传输异常: {error}")

    def observe(self, operation_id=None):
        tasks.check_flow_status(
            self.strategy.pk,
            StrategyStatusChoices.DISABLED,
            StrategyStatusChoices.STOP_FAILED,
            StrategyStatusChoices.STOPPING,
            operation_id=operation_id or self.binding()["operation_id"],
        )


@override_settings(
    BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit", BKBASE_V4_MCP_PROJECT_ID=11
)
class FlowPureOperationTests(FlowFixture, TransactionTestCase):
    def test_timeout_after_put_finishes_failed_and_user_may_retry(self):
        self.write_error = requests.Timeout("synthetic timeout")
        self.stop()
        pure = self.binding()["pure_operation"]
        self.assertEqual(self.strategy.status, StrategyStatusChoices.STOP_FAILED)
        self.assertTrue(pure["attempted"])
        self.assertTrue(pure["outcome_unknown"])
        self.assertFalse(pure["write_fence"])
        self.assertFalse(pure["observing"])
        self.assertEqual(len(self.writes()), 1)
        RuleAuditController(self.strategy.pk).disabled()
        self.assertEqual(len(self.writes()), 2)

    def test_opposite_enable_cannot_choose_restart_or_replace_intent(self):
        self.stop()
        before = self.binding()
        with self.assertRaises(BKBaseException):
            RuleAuditController(self.strategy.pk).enable()
        self.assertEqual(self.binding(), before)
        self.assertEqual(len(self.writes()), 1)

    def test_graph_update_is_rejected_before_business_status_and_enqueue(self):
        self.stop()
        before = self.binding()
        with mock.patch.object(tasks.call_controller, "delay") as queue:
            with self.assertRaises(BKBaseException):
                RuleAuditController(self.strategy.pk).update()
        self.assertEqual(self.binding(), before)
        self.assertEqual(self.strategy.status, StrategyStatusChoices.STOPPING)
        queue.assert_not_called()

    def test_get_failure_is_definitely_not_sent(self):
        self.read_error = True
        self.stop()
        pure = self.binding()["pure_operation"]
        self.assertFalse(pure["attempted"])
        self.assertFalse(pure["outcome_unknown"])
        self.assertFalse(pure["write_fence"])
        self.assertIn("未发送", self.strategy.status_msg)
        self.assertEqual(self.writes(), [])

    def test_sdk_put_disables_redirect_and_redirect_is_unknown(self):
        self.redirect = True
        self.stop()
        self.assertIs(self.writes()[0][2].get("allow_redirects"), False)
        pure = self.binding()["pure_operation"]
        self.assertTrue(pure["outcome_unknown"])
        self.assertIsNone(pure["accepted"])

    def test_known_acceptance_needs_actual_target_then_releases_fence(self):
        self.stop()
        self.remote["status"]["phase"] = "Pending"
        self.observe()
        self.assertEqual(self.binding()["pure_operation"]["accepted"], True)
        self.assertEqual(self.strategy.status, StrategyStatusChoices.STOPPING)
        self.remote["status"]["phase"] = "Ok"
        self.observe()
        self.assertFalse(self.binding()["pure_operation"]["write_fence"])
        self.assertEqual(self.strategy.status, StrategyStatusChoices.DISABLED)
        self.assertEqual(len(self.writes()), 1)

    def test_unknown_receipt_is_not_turned_into_success_by_observation(self):
        self.write_error = requests.Timeout("synthetic timeout")
        self.stop()
        self.engine = "no-start"
        self.observe()
        pure = self.binding()["pure_operation"]
        self.assertFalse(pure["goal_observed"])
        self.assertFalse(pure["write_fence"])
        self.assertTrue(pure["outcome_unknown"])
        self.assertEqual(self.strategy.status, StrategyStatusChoices.STOP_FAILED)
        self.assertEqual(len(self.writes()), 1)

    def test_budget_and_pending_spec_never_cause_observer_to_write(self):
        self.stop()
        self.remote["status"]["phase"] = "Pending"
        self.strategy.refresh_from_db()
        backend = deepcopy(self.strategy.backend_data)
        backend["bkbase_v4"]["poll_count"] = 60
        backend["bkbase_v4"]["pending_spec"] = {"nodes": [{"name": "changed"}]}
        Strategy.objects.filter(pk=self.strategy.pk).update(backend_data=backend)
        with mock.patch.object(flow, "apply_rule_flow", side_effect=AssertionError("Observer wrote graph")):
            self.observe()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.STOPPING)
        self.assertFalse(self.binding()["pure_operation"]["write_fence"])
        self.assertEqual(len(self.writes()), 1)
        self.requeue.assert_not_called()

    def test_enqueue_failure_keeps_intent_for_existing_periodic_recovery(self):
        self.queue.side_effect = RuntimeError("synthetic queue unavailable")
        self.stop()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.STOPPING)
        operation_id = self.binding()["operation_id"]
        self.assertIn("周期", self.strategy.status_msg)
        self.queue.side_effect = None
        with mock.patch("services.web.strategy_v2.tasks.StrategyStatusChecker"):
            check_strategy_status_anomalies()
        self.assertEqual(self.queue.call_args.kwargs["operation_id"], operation_id)
        self.assertEqual(len(self.writes()), 1)

    def test_old_callback_cannot_write_new_operation_status(self):
        self.stop()
        old_id = self.binding()["operation_id"]
        backend = deepcopy(self.strategy.backend_data)
        backend["bkbase_v4"]["operation_id"] = "newer_operation"
        Strategy.objects.filter(pk=self.strategy.pk).update(backend_data=backend, status=StrategyStatusChoices.UPDATING)
        before = len(self.calls)
        self.observe(old_id)
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.UPDATING)
        self.assertEqual(len(self.calls), before)

    def test_repeated_enable_after_unknown_start_retries_without_restart(self):
        Strategy.objects.filter(pk=self.strategy.pk).update(status=StrategyStatusChoices.DISABLED)
        self.remote["metadata"]["annotations"]["task_stopped"] = "true"
        self.engine = "no-start"
        self.write_error = requests.Timeout("synthetic timeout")
        RuleAuditController(self.strategy.pk).enable()
        operation_id = self.binding()["operation_id"]
        RuleAuditController(self.strategy.pk).enable()
        self.assertNotEqual(self.binding()["operation_id"], operation_id)
        self.assertEqual(len(self.writes()), 2)
        self.assertFalse(any("restart" in url for _, url, _ in self.calls))

    def test_unknown_at_poll_budget_is_not_platform_failure(self):
        self.write_error = requests.Timeout("synthetic timeout")
        self.stop()
        self.strategy.refresh_from_db()
        backend = deepcopy(self.strategy.backend_data)
        backend["bkbase_v4"]["poll_count"] = 60
        Strategy.objects.filter(pk=self.strategy.pk).update(backend_data=backend)
        self.observe()
        self.assertEqual(self.binding()["pure_operation"]["outcome_unknown"], True)
        self.assertEqual(self.strategy.status, StrategyStatusChoices.STOP_FAILED)
        self.assertEqual(len(self.writes()), 1)
        self.requeue.assert_not_called()

    def test_registered_crash_recovers_only_observation_then_cancels_unsent_intent(self):
        self.read_hook = mock.Mock(side_effect=SystemExit("synthetic worker crash"))
        with self.assertRaises(SystemExit):
            self.stop()
        self.assertFalse(self.binding()["pure_operation"]["attempted"])
        self.queue.assert_not_called()
        self.read_hook = None
        with mock.patch("services.web.strategy_v2.tasks.StrategyStatusChecker"):
            check_strategy_status_anomalies()
        self.queue.assert_called_once()
        RuleAuditController(self.strategy.pk).disabled()
        self.assertEqual(self.writes(), [])
        backend = deepcopy(self.strategy.backend_data)
        backend["bkbase_v4"]["poll_count"] = 60
        Strategy.objects.filter(pk=self.strategy.pk).update(backend_data=backend)
        self.observe()
        self.assertFalse(self.binding()["pure_operation"]["write_fence"])
        self.assertEqual(self.strategy.status, StrategyStatusChoices.STOP_FAILED)
        self.stop()
        self.assertEqual(len(self.writes()), 1)

    def test_old_observation_preserves_new_configuration_status_and_message(self):
        self.stop()
        Strategy.objects.filter(pk=self.strategy.pk).update(
            sql="SELECT changed", status=StrategyStatusChoices.UPDATING, status_msg="new result"
        )
        self.observe()
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.UPDATING)
        self.assertEqual(self.strategy.status_msg, "new result")
        self.assertTrue(self.binding()["pure_operation"]["write_fence"])

    def test_same_physical_flow_alias_cannot_replace_pending_intent(self):
        self.stop()
        alias = Strategy.objects.create(
            namespace="audit",
            strategy_name="alias",
            strategy_type=StrategyType.RULE,
            status=StrategyStatusChoices.RUNNING,
            backend_data={"bkbase_v4": {"flow": self.ref}},
        )
        with self.assertRaises(BKBaseException):
            RuleAuditController(alias.pk).disabled()
        alias.refresh_from_db()
        self.assertEqual(alias.status, StrategyStatusChoices.RUNNING)
        self.assertEqual(len(self.writes()), 1)

    def test_direct_graph_restart_and_cr_writers_respect_pure_fence(self):
        self.stop()
        context = {**get_bkbase_context(), "operation_id": self.binding()["operation_id"]}
        for call in (
            lambda: flow.operate_rule_flow(context, self.strategy, action="start"),
            lambda: flow.operate_rule_flow(context, self.strategy, action="restart"),
            lambda: flow.apply_rule_flow(context, self.strategy, self.remote["spec"]),
        ):
            with self.subTest(call=call), self.assertRaises(BKBaseException):
                call()
        self.assertEqual(len(self.writes()), 1)

    def test_actual_platform_failure_is_visible_and_observation_ends(self):
        self.stop()
        self.remote["status"]["phase"] = "Failed"
        self.observe()
        self.assertEqual(self.binding()["pure_operation"]["accepted"], True)
        self.assertEqual(self.strategy.status, StrategyStatusChoices.STOP_FAILED)
        self.assertIn("失败", self.strategy.status_msg)
        self.assertFalse(self.binding()["pure_operation"]["write_fence"])

    def test_crash_after_send_claim_keeps_unknown_writer_even_when_goal_is_observed(self):
        self.write_hook = mock.Mock(side_effect=SystemExit("synthetic writer crash"))
        with self.assertRaises(SystemExit):
            self.stop()
        pure = self.binding()["pure_operation"]
        self.assertTrue(pure["attempted"])
        self.assertTrue(pure["writer"])
        self.assertTrue(pure["outcome_unknown"])
        self.queue.assert_not_called()
        self.write_hook = None
        with mock.patch("services.web.strategy_v2.tasks.StrategyStatusChecker"):
            check_strategy_status_anomalies()
        self.queue.assert_called_once()
        self.remote["metadata"]["annotations"]["task_stopped"] = "true"
        self.engine = "no-start"
        self.observe()
        self.assertTrue(self.binding()["pure_operation"]["write_fence"])
        with self.assertRaises(BKBaseException):
            RuleAuditController(self.strategy.pk).enable()

    def test_two_xx_persisted_and_queue_failure_can_finish_read_only(self):
        self.queue.side_effect = RuntimeError("queue unavailable")
        self.stop()
        self.assertTrue(self.binding()["pure_operation"]["accepted"])
        self.queue.side_effect = None
        with mock.patch("services.web.strategy_v2.tasks.StrategyStatusChecker"):
            check_strategy_status_anomalies()
        self.engine = "no-start"
        self.observe()
        self.assertFalse(self.binding()["pure_operation"]["write_fence"])
        self.assertEqual(self.strategy.status, StrategyStatusChoices.DISABLED)
        self.assertEqual(len(self.writes()), 1)

    def test_toggle_resource_uses_real_controller_and_serializer(self):
        endpoint = ToggleStrategy()
        with mock.patch.object(endpoint, "ensure_active_scene_binding_or_404"), mock.patch.object(
            endpoint, "add_audit_instance_to_context"
        ), mock.patch("services.web.strategy_v2.resources.get_request_username", return_value="synthetic_operator"):
            endpoint.request({"strategy_id": self.strategy.pk, "toggle": False})
        self.assertTrue(self.binding()["pure_operation"]["attempted"])
        self.assertEqual(self.strategy.status, StrategyStatusChoices.STOPPING)
        self.assertEqual(len(self.writes()), 1)

    def test_existing_mcp_failure_does_not_prohibit_stop_declaration(self):
        self.engine = "failure"
        self.stop()
        self.assertEqual(len(self.writes()), 1)
        self.assertTrue(self.binding()["pure_operation"]["accepted"])

    def test_soft_deleted_owner_does_not_remove_other_alias_write_protection(self):
        self.stop()
        self.strategy.delete()
        alias = Strategy.objects.create(
            namespace="audit",
            strategy_name="alias",
            strategy_type=StrategyType.RULE,
            status=StrategyStatusChoices.RUNNING,
            backend_data={"bkbase_v4": {"flow": self.ref}},
        )
        with self.assertRaises(BKBaseException):
            RuleAuditController(alias.pk).disabled()
        self.assertEqual(len(self.writes()), 1)

    def test_observation_before_positive_receipt_requires_post_receipt_check(self):
        def observe_early():
            self.remote["metadata"]["annotations"]["task_stopped"] = "true"
            self.engine = "no-start"
            self.observe()
            self.assertTrue(self.binding()["pure_operation"]["write_fence"])

        self.write_hook = observe_early
        self.stop()
        self.assertTrue(self.binding()["pure_operation"]["observing"])
        self.observe()
        self.assertFalse(self.binding()["pure_operation"]["write_fence"])

    def test_unsent_observed_goal_does_not_claim_success(self):
        self.remote["metadata"]["annotations"]["task_stopped"] = "true"
        self.engine = "no-start"

        def fail_after_observation():
            self.read_hook = None
            self.observe()
            raise requests.Timeout("initial GET failed")

        self.read_hook = fail_after_observation
        self.stop()
        self.assertFalse(self.binding()["pure_operation"]["goal_observed"])
        self.assertEqual(self.strategy.status, StrategyStatusChoices.STOP_FAILED)
        self.assertEqual(self.writes(), [])

    def test_older_pending_observation_cannot_replace_later_goal(self):
        self.stop()

        def finish_newer_observation(method, url):
            if "/v4/tenants/" in url:
                self.response_hook = None
                self.remote["status"]["phase"] = "Ok"
                self.observe()

        self.response_hook = finish_newer_observation
        self.remote["status"]["phase"] = "Pending"
        self.observe()
        self.assertEqual(self.binding()["pure_operation"]["goal_observed"], True)
        self.assertEqual(self.strategy.status, StrategyStatusChoices.DISABLED)
        self.assertFalse(self.binding()["pure_operation"]["write_fence"])

    def test_late_queue_error_cannot_replace_completed_message(self):
        def goal_then_queue_error(*args, **kwargs):
            self.engine = "no-start"
            self.observe()
            raise RuntimeError("old queue failed after observation completed")

        self.queue.side_effect = goal_then_queue_error
        self.stop()
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.DISABLED)
        self.assertNotIn("未入队", self.strategy.status_msg)

    def test_actual_update_db_rejects_fence_before_configuration_changes(self):
        self.stop()
        before = self.binding()
        with self.assertRaises(BKBaseException):
            UpdateStrategy().update_db(self.strategy, {"strategy_type": StrategyType.RULE, "sql": "SELECT changed"})
        self.assertEqual(self.binding(), before)
        self.assertIsNone(self.strategy.sql)
        self.assertEqual(self.strategy.status, StrategyStatusChoices.STOPPING)

    def test_configuration_commit_reserves_graph_intent_before_controller_enqueue(self):
        self.assertTrue(
            UpdateStrategy().update_db(self.strategy, {"strategy_type": StrategyType.RULE, "sql": "SELECT changed"})
        )
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.UPDATING)
        with self.assertRaises(BKBaseException):
            RuleAuditController(self.strategy.pk).disabled()
        self.assertEqual(self.writes(), [])

    def test_delete_can_save_stop_and_delete_locally_in_one_request(self):
        endpoint = DeleteStrategy()
        with mock.patch.object(endpoint, "ensure_active_scene_binding_or_404"), mock.patch.object(
            endpoint, "add_audit_instance_to_context"
        ):
            endpoint.request({"strategy_id": self.strategy.pk})
        self.assertTrue(Strategy.objects.get_queryset().get(pk=self.strategy.pk).is_deleted)
        self.assertEqual(len(self.writes()), 1)

    def test_retry_resource_does_not_overwrite_pending_pure_status(self):
        self.stop()
        self.strategy.refresh_from_db()
        before_message = self.strategy.status_msg
        endpoint = RetryStrategy()
        with mock.patch.object(endpoint, "ensure_active_scene_binding_or_404"), mock.patch(
            "services.web.strategy_v2.resources.get_request_username", return_value="synthetic_operator"
        ):
            with self.assertRaises(BKBaseException):
                endpoint.request({"strategy_id": self.strategy.pk})
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.STOPPING)
        self.assertEqual(self.strategy.status_msg, before_message)

    def test_contention_between_preparations_is_not_reported_failed(self):
        original = flow.prepare_controller_update
        for action in ("retry", "update_remote"):
            with self.subTest(action=action):
                Strategy.objects.filter(pk=self.strategy.pk).update(status=StrategyStatusChoices.RUNNING)
                self.strategy.refresh_from_db()
                endpoint = RetryStrategy() if action == "retry" else UpdateStrategy()
                claims = []

                def prepare(strategy, status):
                    result = original(strategy, status)
                    if not claims:
                        claim = flow.flow_operation.write_guard(
                            {**get_bkbase_context(), "operation_id": None}, Strategy.objects.get(pk=self.strategy.pk)
                        )
                        claim.__enter__()
                        claims.append(claim)
                    return result

                try:
                    with mock.patch.object(endpoint, "ensure_active_scene_binding_or_404"), mock.patch(
                        "services.web.strategy_v2.resources.get_request_username", return_value="synthetic_operator"
                    ), mock.patch.object(flow, "prepare_controller_update", side_effect=prepare):
                        with self.assertRaises(BKBaseException):
                            if action == "retry":
                                endpoint.request({"strategy_id": self.strategy.pk})
                            else:
                                endpoint.update_remote(self.strategy)
                    self.strategy.refresh_from_db()
                    self.assertEqual(self.strategy.status, StrategyStatusChoices.UPDATING)
                finally:
                    for claim in claims:
                        claim.__exit__(None, None, None)

    def test_outer_transaction_is_rejected_before_any_pure_io_or_intent(self):
        with transaction.atomic(), self.assertRaises(BKBaseException):
            RuleAuditController(self.strategy.pk).disabled()
        self.assertEqual(self.calls, [])
        self.assertNotIn("pure_operation", self.binding())

    def test_config_drift_before_claim_keeps_new_message_and_allows_explicit_retry(self):
        def mutate_configuration():
            self.read_hook = None
            Strategy.objects.filter(pk=self.strategy.pk).update(sql="SELECT changed", status_msg="newer result")

        self.read_hook = mutate_configuration
        self.stop()
        first_id = self.binding()["operation_id"]
        self.assertEqual(self.strategy.status_msg, "newer result")
        self.assertFalse(self.binding()["pure_operation"]["attempted"])
        self.assertEqual(self.writes(), [])
        self.stop()
        self.assertNotEqual(self.binding()["operation_id"], first_id)
        self.assertEqual(len(self.writes()), 1)

    def test_confirmed_stop_delete_performs_no_additional_remote_io(self):
        self.stop()
        self.engine = "no-start"
        self.observe()
        before = len(self.calls)
        endpoint = DeleteStrategy()
        with mock.patch.object(endpoint, "ensure_active_scene_binding_or_404"), mock.patch.object(
            endpoint, "add_audit_instance_to_context"
        ), mock.patch(
            "services.web.strategy_v2.resources.BindingMetadataHelper.delete_resource_binding"
        ), mock.patch.object(
            endpoint, "delete_enum_mappings"
        ):
            endpoint.request({"strategy_id": self.strategy.pk})
        self.assertFalse(Strategy.objects.filter(pk=self.strategy.pk).exists())
        self.assertEqual(len(self.calls), before)

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_update_keeps_original_status_and_toggle_path(self):
        self.assertTrue(
            UpdateStrategy().update_db(self.strategy, {"strategy_type": StrategyType.RULE, "sql": "SELECT changed"})
        )
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.RUNNING)
        with mock.patch.object(
            RuleAuditController, "_describe_flow_status_v3", return_value="running"
        ), mock.patch.object(RuleAuditController, "_toggle_strategy_v3") as legacy:
            RuleAuditController(self.strategy.pk).disabled()
        legacy.assert_called_once_with("stop", force=False)


@override_settings(
    BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit", BKBASE_V4_MCP_PROJECT_ID=11
)
class FlowMonitorProducerTests(FlowFixture, TransactionTestCase):
    """真实策略启停入口仅在受理回执提交后调度通知，网络/队列只替换边界。"""

    def setUp(self):
        super().setUp()
        self.flow_lock_depth = 0

        @contextmanager
        def tracked_lock(*args):
            self.flow_lock_depth += 1
            try:
                yield
            finally:
                self.flow_lock_depth -= 1

        self.enterContext(mock.patch.object(flow, "resource_lock", side_effect=tracked_lock))

    def transport(self, method, url, **kwargs):
        if method.upper() == "PUT" and self.binding().get("pure_operation", {}).get("restart"):
            self.assertFalse(connection.in_atomic_block)
            self.assertEqual(self.strategy.status, StrategyStatusChoices.UPDATING)
            self.calls.append((method.upper(), url, deepcopy(kwargs)))
            if self.write_error:
                raise self.write_error
            if self.write_hook:
                self.write_hook()
            revision = self.remote["status"].get("version", 0) + 1
            self.remote.update(
                metadata=deepcopy(kwargs["json"]["metadata"]),
                spec=deepcopy(kwargs["json"]["spec"]),
                status={"phase": "Pending", "history_id": revision, "version": revision},
            )
            response = requests.Response()
            response.status_code = 200
            response._content = json.dumps({"result": True, "code": "00", "data": self.remote}).encode()
            return response
        return super().transport(method, url, **kwargs)

    def toggle_from_product(self, active):
        endpoint = ToggleStrategy()
        with mock.patch.object(endpoint, "ensure_active_scene_binding_or_404"), mock.patch.object(
            endpoint, "add_audit_instance_to_context"
        ), mock.patch("services.web.strategy_v2.resources.get_request_username", return_value="synthetic_operator"):
            endpoint.request({"strategy_id": self.strategy.pk, "toggle": active})

    def test_stop_product_path_publishes_monitor_after_accepted_receipt_commit(self):
        self.strategy.backend_data.pop("flow_id")
        self.strategy.save(update_record=False, update_fields=["backend_data"])
        observations = []

        def queued(**kwargs):
            self.assertFalse(connection.in_atomic_block)
            self.assertEqual(self.flow_lock_depth, 0, "Broker publish must be outside the Flow resource lock")
            current = Strategy.objects.get(pk=self.strategy.pk)
            self.assertTrue(current.backend_data["bkbase_v4"]["pure_operation"]["accepted"])
            self.assertEqual(current.status, StrategyStatusChoices.STOPPING)
            observations.append(kwargs)

        self.monitor.side_effect = queued
        self.toggle_from_product(False)
        self.assertEqual(
            observations,
            [{"strategy_id": self.strategy.pk, "is_active": False, "operation_id": self.binding()["operation_id"]}],
        )

    def test_start_product_path_publishes_monitor_after_acceptance(self):
        Strategy.objects.filter(pk=self.strategy.pk).update(status=StrategyStatusChoices.DISABLED)
        self.engine = "no-start"
        self.toggle_from_product(True)
        self.monitor.assert_called_once_with(
            strategy_id=self.strategy.pk, is_active=True, operation_id=self.binding()["operation_id"]
        )
        self.assertEqual(len(self.writes()), 1)

    def test_supported_restart_product_path_publishes_monitor_after_local_commit(self):
        committed = []

        def queued(**kwargs):
            self.assertFalse(connection.in_atomic_block)
            self.assertEqual(self.flow_lock_depth, 0, "Broker publish must be outside the Flow resource lock")
            self.assertEqual(Strategy.objects.get(pk=self.strategy.pk).status, StrategyStatusChoices.RUNNING)
            committed.append(kwargs)

        self.monitor.side_effect = queued
        self.toggle_from_product(True)
        self.monitor.assert_not_called()
        self.remote["status"]["phase"] = "Ok"
        self.observe()
        self.monitor.assert_not_called()
        self.remote["status"]["phase"] = "Ok"
        self.observe()
        self.assertEqual(len(self.writes()), 2)
        self.assertEqual(
            committed,
            [{"strategy_id": self.strategy.pk, "is_active": True, "operation_id": self.binding()["operation_id"]}],
        )

    def test_restart_inflight_configuration_change_does_not_publish_monitor(self):
        def changed_during_restart():
            Strategy.objects.filter(pk=self.strategy.pk).update(
                sql="SELECT newer_configuration", status_msg="new configuration"
            )

        self.write_hook = changed_during_restart
        self.toggle_from_product(True)
        self.remote["status"]["phase"] = "Ok"
        self.observe()
        self.monitor.assert_not_called()
        current = Strategy.objects.get(pk=self.strategy.pk)
        self.assertEqual(current.sql, "SELECT newer_configuration")
        self.assertEqual(current.status_msg, "new configuration")
        self.assertEqual(current.status, StrategyStatusChoices.UPDATING)
        self.assertFalse(current.backend_data["bkbase_v4"]["pure_operation"]["observing"])
        self.assertEqual(len(self.writes()), 1)

    def test_restart_configuration_change_before_commit_callback_does_not_publish_monitor(self):
        callbacks = []
        self.toggle_from_product(True)
        self.remote["status"]["phase"] = "Ok"
        self.observe()
        self.remote["status"]["phase"] = "Ok"
        with mock.patch.object(transaction, "on_commit", side_effect=callbacks.append):
            self.observe()
        self.assertEqual(len(callbacks), 1)
        current = Strategy.objects.get(pk=self.strategy.pk)
        operation_id = current.backend_data["bkbase_v4"]["operation_id"]
        Strategy.objects.filter(pk=current.pk).update(configs=[{"newer_configuration": True}])
        for callback in callbacks:
            callback()
        self.monitor.assert_not_called()
        current.refresh_from_db()
        self.assertEqual(current.status, StrategyStatusChoices.RUNNING)
        self.assertEqual(current.backend_data["bkbase_v4"]["operation_id"], operation_id)
        self.assertTrue(current.backend_data["bkbase_v4"]["pure_operation"]["goal_observed"])
        self.assertEqual(current.configs, [{"newer_configuration": True}])

    def test_read_failure_does_not_publish_monitor(self):
        self.read_error = True
        self.toggle_from_product(False)
        self.monitor.assert_not_called()
        self.assertFalse(self.binding()["pure_operation"]["accepted"])

    def test_unknown_write_receipt_does_not_publish_monitor(self):
        self.write_error = requests.Timeout("synthetic unknown receipt")
        self.toggle_from_product(False)
        self.monitor.assert_not_called()
        self.assertIsNone(self.binding()["pure_operation"]["accepted"])

    def test_superseded_receipt_does_not_publish_monitor(self):
        def replaced(method, url):
            if method.upper() == "PUT":
                current = Strategy.objects.get(pk=self.strategy.pk)
                current.backend_data["bkbase_v4"]["operation_id"] = "new_operation"
                Strategy.objects.filter(pk=current.pk).update(backend_data=current.backend_data)

        self.response_hook = replaced
        self.toggle_from_product(False)
        self.monitor.assert_not_called()

    def test_changed_configuration_receipt_does_not_publish_monitor(self):
        def configuration_changed(method, url):
            if method.upper() == "PUT":
                Strategy.objects.filter(pk=self.strategy.pk).update(sql="SELECT newer_configuration")

        self.response_hook = configuration_changed
        self.toggle_from_product(False)
        self.assertTrue(self.binding()["pure_operation"]["accepted"])
        self.monitor.assert_not_called()

    def test_superseded_on_commit_callback_does_not_publish_monitor(self):
        callbacks = []
        with mock.patch.object(transaction, "on_commit", side_effect=callbacks.append):
            self.toggle_from_product(False)
        self.assertTrue(self.binding()["pure_operation"]["accepted"])
        self.monitor.assert_not_called()
        self.assertEqual(len(callbacks), 1)
        current = Strategy.objects.get(pk=self.strategy.pk)
        current.backend_data["bkbase_v4"]["operation_id"] = "new_operation"
        Strategy.objects.filter(pk=current.pk).update(backend_data=current.backend_data)
        for callback in callbacks:
            callback()
        self.monitor.assert_not_called()

    def test_rolled_back_receipt_does_not_publish_monitor(self):
        self.write_error = requests.Timeout("synthetic unknown receipt")
        self.toggle_from_product(False)
        operation_id = self.binding()["operation_id"]
        with self.assertRaisesRegex(RuntimeError, "synthetic rollback"):
            with transaction.atomic():
                accepted = flow_operation._receipt(self.strategy, operation_id, attempted=True, accepted=True)
                if accepted:
                    flow_operation.enqueue_monitor_after_commit(self.strategy, operation_id, is_active=False)
                self.monitor.assert_not_called()
                raise RuntimeError("synthetic rollback")
        self.monitor.assert_not_called()
        self.assertIsNone(self.binding()["pure_operation"]["accepted"])

    def test_configuration_changed_after_receipt_before_publish_does_not_enqueue(self):
        callbacks = []
        with mock.patch.object(transaction, "on_commit", side_effect=callbacks.append):
            self.toggle_from_product(False)
        self.assertEqual(len(callbacks), 1)
        Strategy.objects.filter(pk=self.strategy.pk).update(sql="SELECT newer_configuration")
        for callback in callbacks:
            callback()
        self.monitor.assert_not_called()

    def test_restart_observation_without_restart_write_does_not_publish_monitor(self):
        self.remote["metadata"]["annotations"]["task_stopped"] = "true"
        self.toggle_from_product(True)
        self.assertEqual(self.writes(), [])
        self.monitor.assert_not_called()

    def test_pending_graph_stop_is_not_a_restart_notification_receipt(self):
        self.strategy.backend_data["bkbase_v4"]["pending_spec"] = {"nodes": []}
        self.strategy.save(update_record=False, update_fields=["backend_data"])
        with mock.patch.object(flow, "apply_rule_flow", return_value={"accepted": True, "requested_action": "stop"}):
            self.toggle_from_product(True)
        self.monitor.assert_not_called()

    def test_reused_stop_only_observes_without_republishing_monitor(self):
        self.toggle_from_product(False)
        self.toggle_from_product(False)
        self.assertEqual(self.monitor.call_count, 1)
        self.assertEqual(len(self.writes()), 1)

    def test_monitor_queue_error_does_not_change_flow_acceptance(self):
        self.monitor.side_effect = RuntimeError("synthetic queue failure")
        self.toggle_from_product(False)
        self.assertTrue(self.binding()["pure_operation"]["accepted"])
        self.assertEqual(self.monitor.call_count, 1)

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_product_path_keeps_original_monitor_arguments(self):
        with mock.patch.object(
            RuleAuditController, "_describe_flow_status_v3", return_value="running"
        ), mock.patch.object(flow.api.bk_base, "stop_flow", return_value={}):
            self.toggle_from_product(False)
        self.monitor.assert_called_once_with(strategy_id=self.strategy.pk, is_active=False)


@override_settings(
    BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit", BKBASE_V4_MCP_PROJECT_ID=11
)
class FlowPureConcurrencyTests(FlowFixture, TransactionTestCase):
    def setUp(self):
        configuration = deepcopy(settings.CACHES)
        self.redis_location = urlsplit(configuration["default"]["LOCATION"])
        prefix = configuration["default"].get("KEY_PREFIX", "")
        configuration["default"]["KEY_PREFIX"] = f"{prefix}:bkbase-flow-concurrency:{self._testMethodName}"
        self.enterContext(override_settings(CACHES=configuration))
        super().setUp()

    def test_two_db_connections_and_expired_real_redis_lease_cannot_admit_opposite_or_graph(self):
        self.lock_patch.stop()
        entered, release = threading.Event(), threading.Event()
        writer_connections, failures = [], []

        def pause_write():
            with connection.cursor() as cursor:
                cursor.execute("SELECT CONNECTION_ID()")
                writer_connections.append(cursor.fetchone()[0])
            entered.set()
            if not release.wait(8):
                raise AssertionError("Test did not release synthetic HTTP")

        def writer():
            try:
                self.stop()
            except BaseException as error:
                failures.append(error)
            finally:
                connections.close_all()

        self.write_hook = pause_write
        thread = threading.Thread(target=writer)
        thread.start()
        try:
            self.assertTrue(entered.wait(5))
            with connection.cursor() as cursor:
                cursor.execute("SELECT CONNECTION_ID()")
                other_connection = cursor.fetchone()[0]
            self.assertNotEqual(writer_connections[0], other_connection)
            context = get_bkbase_context()
            redis_config = cache.client.get_client().connection_pool.connection_kwargs
            self.assertEqual(redis_config["host"], self.redis_location.hostname)
            self.assertEqual(int(redis_config["port"]), self.redis_location.port or 6379)
            self.assertEqual(int(redis_config["db"]), int(self.redis_location.path.lstrip("/") or "0"))
            with self.assertRaises(LockError), resource_lock(context, self.ref):
                pass
            params = resource_params(context, self.ref)
            key = (
                "bkbase_v4:"
                + hashlib.sha256(json.dumps({**params, "kind": "Flow"}, sort_keys=True).encode()).hexdigest()
            )
            cache.delete(key)  # 仅模拟本测试持有租约过期；持久意图仍在另一连接可见。
            with resource_lock(context, self.ref):
                with self.assertRaises(BKBaseException):
                    RuleAuditController(self.strategy.pk).enable()
                with self.assertRaises(BKBaseException):
                    RuleAuditController(self.strategy.pk).update()
            self.assertEqual(self.binding()["pure_operation"]["attempted"], True)
        finally:
            release.set()
            thread.join(10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(len(self.writes()), 1)

    def test_observation_started_before_receipt_cannot_release_after_receipt(self):
        entered, release_write = threading.Event(), threading.Event()
        captured, release_read = threading.Event(), threading.Event()
        failures = []

        def writer_pause():
            self.remote["metadata"]["annotations"]["task_stopped"] = "true"
            self.engine = "no-start"
            entered.set()
            if not release_write.wait(8):
                raise AssertionError("Writer not released")

        def reader_pause(method, url):
            if threading.current_thread().name == "old-observer" and "/v4/tenants/" in url:
                captured.set()
                if not release_read.wait(8):
                    raise AssertionError("Reader not released")

        def run(action):
            try:
                action()
            except BaseException as error:
                failures.append(error)
            finally:
                connections.close_all()

        self.write_hook, self.response_hook = writer_pause, reader_pause
        writer = threading.Thread(target=run, args=(self.stop,), name="writer")
        observer = threading.Thread(target=run, args=(self.observe,), name="old-observer")
        writer.start()
        try:
            self.assertTrue(entered.wait(5))
            observer.start()
            self.assertTrue(captured.wait(5))
            release_write.set()
            writer.join(8)
            self.assertFalse(writer.is_alive())
            self.assertTrue(self.binding()["pure_operation"]["accepted"])
            release_read.set()
            observer.join(8)
            self.assertFalse(observer.is_alive())
            self.assertTrue(self.binding()["pure_operation"]["write_fence"])
            self.assertTrue(self.binding()["pure_operation"]["observing"])
            self.response_hook = None
            self.observe()
            self.assertFalse(self.binding()["pure_operation"]["write_fence"])
        finally:
            release_write.set()
            release_read.set()
            writer.join(10)
            if observer.ident:
                observer.join(10)
        self.assertEqual(failures, [])

    def test_primary_key_lock_does_not_hold_unrelated_strategy(self):
        unrelated = Strategy.objects.create(
            namespace="audit", strategy_name="unrelated", strategy_type=StrategyType.RULE
        )
        entered, release = threading.Event(), threading.Event()
        failures = []

        def holder():
            try:
                with flow.flow_operation.locked_rows(self.strategy):
                    entered.set()
                    if not release.wait(8):
                        raise AssertionError("Holder not released")
            except BaseException as error:
                failures.append(error)
            finally:
                connections.close_all()

        thread = threading.Thread(target=holder)
        thread.start()
        try:
            self.assertTrue(entered.wait(5))
            # 当前测试MySQL无NOWAIT，用本会话1秒锁等待上限检测无关行是否被锁。
            with connection.cursor() as cursor:
                cursor.execute("SELECT @@session.innodb_lock_wait_timeout")
                previous_timeout = cursor.fetchone()[0]
                cursor.execute("SET SESSION innodb_lock_wait_timeout = 1")
            try:
                with transaction.atomic():
                    Strategy.objects.select_for_update().get(pk=unrelated.pk)
                    query = Strategy.objects.select_for_update().filter(pk__in=[self.strategy.pk]).order_by("pk")
                    sql, params = query.query.sql_with_params()
            finally:
                with connection.cursor() as cursor:
                    cursor.execute("SET SESSION innodb_lock_wait_timeout = %s", [previous_timeout])
            with connection.cursor() as cursor:
                cursor.execute("EXPLAIN " + sql, params)
                plan = [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
            self.assertEqual(plan[0]["key"], "PRIMARY")
            print("FLOW_LOCK_EXPLAIN", json.dumps(plan, default=str))
        finally:
            release.set()
            thread.join(10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])

    def test_start_waiting_for_delete_transaction_cannot_write_deleted_strategy(self):
        self.stop()
        self.engine = "no-start"
        self.observe()
        deleting, release_delete, starting = threading.Event(), threading.Event(), threading.Event()
        failures, denied = [], []
        endpoint = DeleteStrategy()
        original = flow.flow_operation.locked_rows

        def pause_delete(*args):
            deleting.set()
            if not release_delete.wait(8):
                raise AssertionError("Delete not released")

        @contextmanager
        def intercept(strategy):
            if threading.current_thread().name == "new-start":
                starting.set()
            with original(strategy) as rows:
                yield rows

        def delete():
            try:
                endpoint.request({"strategy_id": self.strategy.pk})
            except BaseException as error:
                failures.append(error)
            finally:
                connections.close_all()

        def start():
            try:
                RuleAuditController(self.strategy.pk).enable()
            except (BKBaseException, Strategy.DoesNotExist) as error:
                denied.append(type(error).__name__)
            except BaseException as error:
                failures.append(error)
            finally:
                connections.close_all()

        with mock.patch.object(endpoint, "ensure_active_scene_binding_or_404"), mock.patch.object(
            endpoint, "add_audit_instance_to_context"
        ), mock.patch.object(endpoint, "_soft_delete_rules", side_effect=pause_delete), mock.patch(
            "services.web.strategy_v2.resources.BindingMetadataHelper.delete_resource_binding"
        ), mock.patch.object(
            endpoint, "delete_enum_mappings"
        ), mock.patch.object(
            flow.flow_operation, "locked_rows", side_effect=intercept
        ):
            deleter = threading.Thread(target=delete, name="delete")
            starter = threading.Thread(target=start, name="new-start")
            deleter.start()
            try:
                self.assertTrue(deleting.wait(5))
                starter.start()
                self.assertTrue(starting.wait(5))
            finally:
                release_delete.set()
                deleter.join(10)
                if starter.ident:
                    starter.join(10)
        self.assertFalse(deleter.is_alive())
        self.assertFalse(starter.is_alive())
        self.assertEqual(failures, [])
        self.assertTrue(denied)
        self.assertEqual(len(self.writes()), 1)
