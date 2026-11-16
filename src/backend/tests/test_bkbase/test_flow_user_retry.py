"""已结束Flow改图发送失败允许显式用户重试，仍保护活动写者。"""
import json
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

import requests
from bk_resource.exceptions import APIRequestError
from django.db import connection
from django.test import TransactionTestCase, override_settings

from api.bk_base_v4.default import BkBaseV4Resource
from services.web.analyze import tasks
from services.web.bkbase import flow
from services.web.bkbase.common import get_bkbase_context
from services.web.bkbase.exceptions import (
    BKBaseException,
    BKBaseFlowOperationPending,
    BKBaseResourceMappingError,
)
from services.web.strategy_v2.constants import StrategyStatusChoices, StrategyType
from services.web.strategy_v2.models import Strategy
from services.web.strategy_v2.resources import RetryStrategy


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit")
class FlowUserRetryTests(TransactionTestCase):
    def setUp(self):
        self.ref = {"kind": "Flow", "tenant": "tenant_a", "namespace": "audit", "name": "owned"}
        self.spec = {"nodes": [{"name": "sql", "kind": "StreamNode", "config": {"sql": "SELECT 1"}}]}
        self.strategy = Strategy.objects.create(
            namespace="audit",
            strategy_name="synthetic",
            strategy_type=StrategyType.RULE,
            status=StrategyStatusChoices.UPDATING,
            backend_data={
                "flow_id": 123,
                "retained": {"keep": True},
                "bkbase_v4": {"flow": self.ref, "managed_nodes": ["sql"], "operation_id": "original"},
            },
        )
        self.remote = {
            "kind": "Flow",
            "metadata": {**self.ref, "annotations": {"task_stopped": "true"}},
            "spec": deepcopy(self.spec),
            "status": {"phase": "Ok"},
        }
        self.calls = []
        self.failure = requests.Timeout("synthetic write timeout")
        self.on_write = None
        self.enterContext(mock.patch.object(flow, "resource_lock"))
        self.enterContext(mock.patch.object(BkBaseV4Resource, "build_header", return_value={}))
        self.enterContext(mock.patch("requests.sessions.Session.request", side_effect=self.transport))
        self.requeue = self.enterContext(mock.patch.object(tasks.check_flow_status, "apply_async"))
        self.enterContext(mock.patch.object(tasks, "ErrorMsgHandler"))

    def transport(self, method, url, **kwargs):
        self.assertFalse(connection.in_atomic_block)
        self.assertIn("/v4/tenants/tenant_a/namespaces/audit/flows/owned/", url)
        self.calls.append(method.upper())
        if method.upper() == "PUT":
            if self.on_write:
                self.on_write()
            if self.failure:
                raise self.failure
            self.remote.update(metadata=deepcopy(kwargs["json"]["metadata"]), spec=deepcopy(kwargs["json"]["spec"]))
        response = requests.Response()
        response.status_code = 200
        response.url = url
        response.request = requests.Request(method, url).prepare()
        response._content = json.dumps({"result": True, "code": "00", "data": deepcopy(self.remote)}).encode()
        return response

    def send(self):
        context = get_bkbase_context()
        context["operation_id"] = self.strategy.backend_data["bkbase_v4"]["operation_id"]
        return flow._write_flow_request(
            context,
            self.strategy,
            flow.api.bk_base_v4.flow_update,
            tenant="tenant_a",
            namespace="audit",
            name="owned",
            metadata=deepcopy(self.remote["metadata"]),
            spec=deepcopy(self.spec),
            status=None,
        )

    def controller(self):
        return SimpleNamespace(
            strategy=self.strategy, _update_or_create_bkbase_flow=self.send, check_flow_status=mock.Mock()
        )

    def test_finished_write_failure_is_failed_and_allows_explicit_retry(self):
        def during_send():
            current = Strategy.objects.get(pk=self.strategy.pk)
            self.assertTrue(current.backend_data["bkbase_v4"]["flow_write"])
            with self.assertRaises(BKBaseFlowOperationPending):
                flow.prepare_controller_update(current, StrategyStatusChoices.UPDATING)

        self.on_write = during_send
        try:
            flow.update_or_create_controller(self.controller(), StrategyStatusChoices.UPDATING)
        except (APIRequestError, BKBaseException):
            pass
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.UPDATE_FAILED)
        self.assertNotIn("flow_write", self.strategy.backend_data["bkbase_v4"])
        previous = self.strategy.backend_data["bkbase_v4"]["operation_id"]
        self.failure = self.on_write = None
        flow.prepare_controller_update(self.strategy, StrategyStatusChoices.UPDATING)
        flow.update_or_create_controller(self.controller(), StrategyStatusChoices.UPDATING)
        self.assertNotEqual(self.strategy.backend_data["bkbase_v4"]["operation_id"], previous)
        self.assertEqual(self.calls.count("PUT"), 2)
        self.assertEqual(self.strategy.backend_data["flow_id"], 123)
        self.assertEqual(self.strategy.backend_data["retained"], {"keep": True})

    def test_pending_graph_write_error_finishes_without_automatic_requeue(self):
        backend = deepcopy(self.strategy.backend_data)
        backend["bkbase_v4"].update(
            pending_spec={"nodes": [{"name": "sql", "kind": "StreamNode", "config": {"sql": "SELECT 2"}}]},
            operation="wait_stopped",
            requested_action="update",
            poll_count=0,
        )
        self.strategy.backend_data = backend
        self.strategy.save(update_fields=["backend_data"])
        try:
            tasks.check_flow_status.run(
                self.strategy.pk,
                StrategyStatusChoices.RUNNING,
                StrategyStatusChoices.UPDATE_FAILED,
                StrategyStatusChoices.UPDATING,
                operation_id="original",
            )
        except BKBaseException:
            pass
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.UPDATE_FAILED)
        self.assertNotIn("flow_write", self.strategy.backend_data["bkbase_v4"])
        self.assertEqual(self.calls.count("PUT"), 1)
        self.requeue.assert_not_called()

    def test_interrupted_sender_keeps_its_guard(self):
        self.failure = SystemExit("synthetic interrupted worker")
        with self.assertRaises(SystemExit):
            self.send()
        self.strategy.refresh_from_db()
        self.assertTrue(self.strategy.backend_data["bkbase_v4"]["flow_write"]["outcome_unknown"])
        with self.assertRaises(BKBaseFlowOperationPending):
            flow.prepare_controller_update(self.strategy, StrategyStatusChoices.UPDATING)

    def test_old_sender_does_not_clear_new_operation_guard_or_status(self):
        def newer():
            backend = deepcopy(self.strategy.backend_data)
            backend["bkbase_v4"].update(
                operation_id="newer", flow_write={"token": "new-token", "operation_id": "newer"}
            )
            Strategy.objects.filter(pk=self.strategy.pk).update(
                backend_data=backend, status=StrategyStatusChoices.RUNNING
            )

        self.on_write = newer
        try:
            flow.update_or_create_controller(self.controller(), StrategyStatusChoices.UPDATING)
        except (APIRequestError, BKBaseException):
            pass
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.RUNNING)
        self.assertEqual(
            self.strategy.backend_data["bkbase_v4"]["flow_write"], {"token": "new-token", "operation_id": "newer"}
        )

    def retry_graph_from_product(self):
        """仅替换图构造与队列边界，保留Resource、Service及正式Flow读写。"""
        endpoint = RetryStrategy()
        desired = deepcopy(self.spec)
        desired["nodes"][0]["config"]["sql"] = "SELECT 2"

        def dispatch(_method, strategy_id, _controller_cls, *, bkbase_version):
            self.assertEqual(bkbase_version, "v4")
            strategy = Strategy.objects.get(pk=strategy_id)

            def apply():
                context = get_bkbase_context()
                context["operation_id"] = strategy.backend_data["bkbase_v4"]["operation_id"]
                return flow.apply_rule_flow(context, strategy, desired)

            controller = SimpleNamespace(
                strategy=strategy, _update_or_create_bkbase_flow=apply, check_flow_status=mock.Mock()
            )
            return flow.update_or_create_controller(controller, StrategyStatusChoices.UPDATING)

        with mock.patch.object(endpoint, "ensure_active_scene_binding_or_404"), mock.patch(
            "services.web.strategy_v2.resources.get_request_username", return_value="synthetic_operator"
        ), mock.patch("services.web.strategy_v2.resources.call_controller", side_effect=dispatch):
            endpoint.request({"strategy_id": self.strategy.pk})
        self.strategy.refresh_from_db()

    def fail_initial_write(self):
        """先经过真实写入失败路径，验证释放后才能进入用户重试。"""
        with self.assertRaises(BKBaseException):
            flow.update_or_create_controller(self.controller(), StrategyStatusChoices.UPDATING)
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.UPDATE_FAILED)
        self.assertNotIn("flow_write", self.strategy.backend_data["bkbase_v4"])
        self.failure = None

    def test_graph_apply_rejects_failed_flow_instead_of_publishing_desired(self):
        self.fail_initial_write()
        self.remote["status"]["phase"] = "Failed"
        self.remote["metadata"]["annotations"]["task_stopped"] = "false"
        context = get_bkbase_context()
        context["operation_id"] = self.strategy.backend_data["bkbase_v4"]["operation_id"]
        desired = deepcopy(self.spec)
        desired["nodes"][0]["config"]["sql"] = "SELECT 2"
        with self.assertRaises(BKBaseResourceMappingError) as error:
            flow.apply_rule_flow(context, self.strategy, desired)
        self.assertIn("原配置启动", str(error.exception))
        self.strategy.refresh_from_db()
        self.assertIn(self.strategy.status, (StrategyStatusChoices.FAILED, StrategyStatusChoices.UPDATE_FAILED))
        self.assertGreater(self.calls.count("GET"), 0)
        self.assertEqual(self.calls.count("PUT"), 1)
        self.assertEqual(self.strategy.backend_data["bkbase_v4"]["flow"], self.ref)

    def test_product_retry_waits_for_pending_flow_without_new_put(self):
        self.fail_initial_write()
        self.remote["status"]["phase"] = "Pending"
        self.remote["metadata"]["annotations"]["task_stopped"] = "false"
        self.retry_graph_from_product()
        self.assertEqual(self.calls.count("PUT"), 1)
        self.assertEqual(
            self.strategy.backend_data["bkbase_v4"]["pending_spec"]["nodes"][0]["config"]["sql"], "SELECT 2"
        )
        operation_id = self.strategy.backend_data["bkbase_v4"]["operation_id"]
        tasks.check_flow_status.run(
            self.strategy.pk,
            StrategyStatusChoices.RUNNING,
            StrategyStatusChoices.UPDATE_FAILED,
            StrategyStatusChoices.UPDATING,
            operation_id=operation_id,
        )
        self.assertEqual(self.calls.count("PUT"), 1)
        self.requeue.assert_called_once()

    def test_product_retry_applies_graph_when_formal_flow_is_stopped(self):
        self.fail_initial_write()
        self.retry_graph_from_product()
        self.assertEqual(self.calls.count("PUT"), 2)
        self.assertEqual(self.remote["spec"]["nodes"][0]["config"]["sql"], "SELECT 2")
        self.assertNotEqual(self.strategy.backend_data["bkbase_v4"]["operation_id"], "original")

    def test_failed_callback_does_not_automatically_retry_pending_graph(self):
        backend = deepcopy(self.strategy.backend_data)
        backend["bkbase_v4"].update(
            pending_spec=deepcopy(self.spec), requested_action="update", operation="wait_stopped"
        )
        self.strategy.backend_data = backend
        self.strategy.save(update_fields=["backend_data"])
        self.fail_initial_write()
        operation_id = self.strategy.backend_data["bkbase_v4"]["operation_id"]
        self.remote["status"]["phase"] = "Pending"
        self.remote["metadata"]["annotations"]["task_stopped"] = "false"
        tasks.check_flow_status.run(
            self.strategy.pk,
            StrategyStatusChoices.RUNNING,
            StrategyStatusChoices.UPDATE_FAILED,
            StrategyStatusChoices.UPDATING,
            operation_id=operation_id,
        )
        self.strategy.refresh_from_db()
        self.assertEqual(self.calls.count("PUT"), 1)
        self.assertEqual(self.strategy.status, StrategyStatusChoices.UPDATE_FAILED)
        self.requeue.assert_not_called()
