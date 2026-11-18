"""纯启停失败后只由用户重试，后台不重发。"""
import json
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

import requests
from django.test import TransactionTestCase, override_settings

from services.web.analyze import tasks
from services.web.analyze.controls.rule_audit import RuleAuditController
from services.web.bkbase import flow, flow_operation
from services.web.bkbase.exceptions import BKBaseException
from services.web.strategy_v2.constants import StrategyStatusChoices
from services.web.strategy_v2.models import Strategy
from services.web.strategy_v2.resources import DeleteStrategy, RetryStrategy
from tests.test_bkbase.test_flow_pure_operation import FlowFixture


@override_settings(
    BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit", BKBASE_V4_MCP_PROJECT_ID=11
)
class FlowRetryAfterFailureTests(FlowFixture, TransactionTestCase):
    def test_old_monitor_get_cannot_write_after_alias_starts_new_generation(self):
        first = self.strategy
        self.stop()
        old_id = self.binding()["operation_id"]
        self.engine = "no-start"
        self.observe()
        second = Strategy.objects.create(
            namespace="audit",
            strategy_name="alias",
            strategy_type=first.strategy_type,
            status=StrategyStatusChoices.DISABLED,
            backend_data={"bkbase_v4": {"flow": self.ref}},
        )
        notify_calls = []
        config = {
            "alert_config": {
                "notify_group_configs": [{"active": True, "group": "g", "notify_configs": [], "receiver_config": {}}],
                "converge_rules": [],
            }
        }

        def transport(method, url, **kwargs):
            if not url.endswith("/v4/databus/data_source/notifies/"):
                return self.transport(method, url, **kwargs)
            notify_calls.append(method.upper())
            if method.upper() == "GET":
                self.strategy = second
                RuleAuditController(second.pk).enable()
                self.strategy = first
            response = requests.Response()
            response.status_code = 200
            response._content = json.dumps({"result": True, "code": "00", "data": config}).encode()
            response.url = url
            response.request = requests.Request(method, url).prepare()
            return response

        group = SimpleNamespace(notice_config=[{"msg_type": "mail"}])
        with mock.patch("requests.sessions.Session.request", side_effect=transport), mock.patch.object(
            tasks.NoticeGroup.objects, "filter", return_value=[group]
        ), mock.patch.object(tasks.IgnoreMemberVariableParser, "parse_groups", return_value=["synthetic_user"]):
            tasks.toggle_monitor.run(first.pk, False, operation_id=old_id)
        self.assertEqual(notify_calls, ["GET"])
        first.refresh_from_db()
        self.assertFalse(flow.is_current_operation(first, old_id))
        self.assertEqual(len(self.writes()), 2)

    def test_old_alias_stop_cannot_authorize_delete_or_monitor_after_new_start(self):
        first = self.strategy
        self.stop()
        old_id = self.binding()["operation_id"]
        self.engine = "no-start"
        self.observe()
        second = Strategy.objects.create(
            namespace="audit",
            strategy_name="alias",
            strategy_type=first.strategy_type,
            status=StrategyStatusChoices.DISABLED,
            backend_data={"bkbase_v4": {"flow": self.ref}},
        )
        self.strategy = second
        RuleAuditController(second.pk).enable()
        self.engine = "running"
        self.observe()
        new_id = self.binding()["operation_id"]
        first.refresh_from_db()
        self.assertFalse(flow.is_current_operation(first, old_id))
        with mock.patch.object(flow, "has_flow") as has_flow:
            tasks.toggle_monitor(first.pk, False, operation_id=old_id)
        has_flow.assert_not_called()
        self.strategy = first
        self.assertFalse(flow_operation.is_pure(first, old_id))
        flow_operation._receipt(first, old_id, attempted=True, accepted=True, writer_token="old")
        self.assertEqual(flow_operation.observe(first)["status"], "superseded")
        endpoint = DeleteStrategy()
        with mock.patch.object(endpoint, "ensure_active_scene_binding_or_404"), mock.patch.object(
            endpoint, "add_audit_instance_to_context"
        ):
            endpoint.request({"strategy_id": first.pk})
        deleted = Strategy.objects.get_queryset().get(pk=first.pk)
        self.assertTrue(deleted.is_deleted)
        self.assertNotEqual(deleted.backend_data["bkbase_v4"]["delete_operation"]["id"], old_id)
        self.assertEqual(len(self.writes()), 3)
        second.refresh_from_db()
        self.assertTrue(flow.is_current_operation(second, new_id) is False)  # new delete supersedes start

    def test_unsent_failure_releases_same_operation_alias(self):
        alias = Strategy.objects.create(
            namespace="audit",
            strategy_name="alias",
            strategy_type=self.strategy.strategy_type,
            status=StrategyStatusChoices.RUNNING,
            backend_data={"bkbase_v4": {"flow": self.ref}},
        )

        def fail_read():
            alias.backend_data = {"bkbase_v4": self.binding()}
            alias.save(update_fields=["backend_data"])
            raise requests.Timeout("synthetic read timeout")

        self.read_hook = fail_read
        self.stop()
        alias.refresh_from_db()
        pure = alias.backend_data["bkbase_v4"]["pure_operation"]
        self.assertFalse(pure["observing"])
        self.assertFalse(pure["write_fence"])
        self.assertFalse(pure["attempted"])
        self.assertEqual(self.writes(), [])

    def test_budget_does_not_release_stranded_writer(self):
        self.write_hook = mock.Mock(side_effect=SystemExit("worker crash"))
        with self.assertRaises(SystemExit):
            self.stop()
        self.write_hook = None
        data = deepcopy(self.strategy.backend_data)
        data["bkbase_v4"]["poll_count"] = flow_operation.BKBASE_V4_MAX_POLLS
        Strategy.objects.filter(pk=self.strategy.pk).update(backend_data=data)
        self.observe()
        pure = self.binding()["pure_operation"]
        self.assertTrue(pure["writer"])
        self.assertTrue(pure["write_fence"])
        self.assertEqual(len(self.writes()), 1)
        with self.assertRaises(BKBaseException):
            RuleAuditController(self.strategy.pk).disabled()

    def test_accepted_observation_budget_exhaustion_allows_user_retry(self):
        self.stop()
        self.remote["status"]["phase"] = "Pending"
        old_id = self.binding()["operation_id"]
        data = deepcopy(self.strategy.backend_data)
        data["bkbase_v4"]["poll_count"] = flow_operation.BKBASE_V4_MAX_POLLS
        Strategy.objects.filter(pk=self.strategy.pk).update(backend_data=data)
        self.observe()
        pure = self.binding()["pure_operation"]
        self.assertFalse(pure["observing"])
        self.assertFalse(pure["write_fence"])
        self.assertEqual(self.strategy.status, StrategyStatusChoices.STOP_FAILED)
        self.assertIn("未确认", self.strategy.status_msg)
        self.assertEqual(len(self.writes()), 1)
        self.stop()
        self.assertNotEqual(self.binding()["operation_id"], old_id)
        self.assertEqual(len(self.writes()), 2)

    def test_start_retry_keeps_original_target(self):
        Strategy.objects.filter(pk=self.strategy.pk).update(status=StrategyStatusChoices.DISABLED)
        self.remote["metadata"]["annotations"]["task_stopped"] = "true"
        self.engine = "no-start"
        self.write_error = requests.Timeout("synthetic timeout")
        RuleAuditController(self.strategy.pk).enable()
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.START_FAILED)
        previous = self.binding()["operation_id"]
        self.write_error = None
        endpoint = RetryStrategy()
        with mock.patch.object(endpoint, "ensure_active_scene_binding_or_404"), mock.patch(
            "services.web.strategy_v2.resources.get_request_username", return_value="operator"
        ):
            endpoint.request({"strategy_id": self.strategy.pk})
        self.assertEqual(len(self.writes()), 2)
        self.assertEqual(self.binding()["pure_operation"]["target"], "start")
        self.assertNotEqual(self.binding()["operation_id"], previous)

    def test_start_retry_recovers_failed_resource_with_original_configuration(self):
        Strategy.objects.filter(pk=self.strategy.pk).update(status=StrategyStatusChoices.DISABLED)
        self.remote["metadata"]["annotations"]["task_stopped"] = "true"
        self.engine = "no-start"
        self.write_error = requests.Timeout("synthetic timeout")
        RuleAuditController(self.strategy.pk).enable()
        self.write_error = None
        self.remote["status"]["phase"] = "Failed"
        endpoint = RetryStrategy()
        with mock.patch.object(endpoint, "ensure_active_scene_binding_or_404"), mock.patch(
            "services.web.strategy_v2.resources.get_request_username", return_value="operator"
        ):
            endpoint.request({"strategy_id": self.strategy.pk})
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.STARTING)
        self.assertEqual(len(self.writes()), 2)
        self.assertEqual(self.writes()[-1][2]["json"]["spec"], self.remote["spec"])

    def test_same_flow_aliases_finish_old_send_and_old_receipt_cannot_change_new_generation(self):
        alias = Strategy.objects.create(
            namespace="audit",
            strategy_name="alias",
            strategy_type=self.strategy.strategy_type,
            status=StrategyStatusChoices.RUNNING,
            backend_data={"bkbase_v4": {"flow": self.ref}},
        )
        token = {}

        def copy_inflight():
            current = self.binding()
            token["writer"] = current["pure_operation"]["writer"]
            alias.backend_data = {"bkbase_v4": current}
            alias.status = StrategyStatusChoices.STOPPING
            alias.save(update_fields=["backend_data", "status"])

        self.write_hook = copy_inflight
        self.write_error = requests.Timeout("synthetic timeout")
        self.stop()
        old_id = self.binding()["operation_id"]
        alias.refresh_from_db()
        self.assertFalse(alias.backend_data["bkbase_v4"]["pure_operation"]["write_fence"])
        self.assertFalse(alias.backend_data["bkbase_v4"]["pure_operation"]["observing"])
        self.write_hook = None
        self.write_error = None
        self.stop()
        new_id = self.binding()["operation_id"]
        alias.refresh_from_db()
        self.assertNotEqual(old_id, new_id)
        self.assertEqual(alias.backend_data["bkbase_v4"]["pure_operation"]["superseded_by"], new_id)
        flow_operation._receipt(alias, old_id, attempted=True, accepted=True, writer_token=token["writer"])
        self.assertEqual(self.binding()["operation_id"], new_id)
        self.assertEqual(len(self.writes()), 2)

    def test_delete_failed_send_requires_user_retry_and_new_reservation(self):
        endpoint = DeleteStrategy()
        self.write_error = requests.Timeout("synthetic timeout")
        with mock.patch.object(endpoint, "ensure_active_scene_binding_or_404"), mock.patch.object(
            endpoint, "add_audit_instance_to_context"
        ):
            with self.assertRaises(BKBaseException):
                endpoint.request({"strategy_id": self.strategy.pk})
            self.strategy.refresh_from_db()
            old = self.binding()["delete_operation"]
            self.assertEqual(self.strategy.status, StrategyStatusChoices.DELETE_FAILED)
            self.assertFalse(old["pending"])
            self.assertTrue(old["outcome_unknown"])
            self.assertEqual(len(self.writes()), 1)
            self.write_error = None
            endpoint.request({"strategy_id": self.strategy.pk})
            deleted = type(self.strategy).objects.get_queryset().get(pk=self.strategy.pk)
            self.assertTrue(deleted.is_deleted)
            self.assertNotEqual(deleted.backend_data["bkbase_v4"]["delete_operation"]["id"], old["id"])
            self.assertEqual(len(self.writes()), 2)

    def test_stop_failure_finishes_and_user_retry_sends_new_attempt(self):
        self.write_error = requests.Timeout("synthetic timeout")
        self.stop()
        old = self.binding()["pure_operation"]
        self.assertEqual(self.strategy.status, StrategyStatusChoices.STOP_FAILED)
        self.assertTrue(old["outcome_unknown"])
        self.assertFalse(old["observing"])
        self.assertFalse(old["write_fence"])
        self.assertNotIn("writer", old)
        old_id = old["id"]
        self.observe(old_id)
        self.assertEqual(len(self.writes()), 1)
        self.write_error = None
        endpoint = RetryStrategy()
        with mock.patch.object(endpoint, "ensure_active_scene_binding_or_404"), mock.patch(
            "services.web.strategy_v2.resources.get_request_username", return_value="operator"
        ):
            endpoint.request({"strategy_id": self.strategy.pk})
        self.assertEqual(len(self.writes()), 2)
        self.assertNotEqual(self.binding()["pure_operation"]["id"], old_id)
        self.assertEqual(self.binding()["pure_operation"]["target"], "stop")

    def test_late_old_receipt_cannot_affect_new_attempt(self):
        self.write_error = requests.Timeout("synthetic timeout")
        self.stop()
        old = self.binding()["pure_operation"]
        old_id = old["id"]
        self.write_error = None
        RuleAuditController(self.strategy.pk).disabled()
        current = self.binding()["pure_operation"]["id"]
        self.assertNotEqual(current, old_id)
        flow_operation._receipt(self.strategy, old_id, attempted=True, accepted=True, writer_token="stale")
        self.assertEqual(self.binding()["pure_operation"]["id"], current)
        self.assertEqual(len(self.writes()), 2)
