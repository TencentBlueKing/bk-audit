"""真实Retry资源/Controller重构已结束创建失败，外部HTTP与队列受控。"""

import json
from copy import deepcopy
from unittest import mock

import requests
from bk_resource.exceptions import APIRequestError
from django.db import connection
from django.http import Http404
from django.test import TransactionTestCase, override_settings

from api.bk_base_v4.default import BkBaseV4Resource
from services.web.analyze import tasks
from services.web.analyze.constants import FlowDataSourceNodeType
from services.web.analyze.controls import base as base_control
from services.web.analyze.controls.rule_audit import RuleAuditController
from services.web.analyze.storage_node import DorisStorageNode
from services.web.bkbase import flow
from services.web.bkbase.constants import (
    BKBASE_V4_FLOW_CONFIG,
    BKBASE_V4_STORAGE_CLUSTER_MAP,
)
from services.web.bkbase.exceptions import BKBaseException, BKBaseOperationSuperseded
from services.web.databus.constants import (
    COLLECTOR_PLUGIN_ID,
    DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
    DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY,
)
from services.web.databus.models import CollectorPlugin
from services.web.strategy_v2.constants import (
    RuleAuditConfigType,
    StrategyStatusChoices,
    StrategyType,
)
from services.web.strategy_v2.models import Strategy
from services.web.strategy_v2.resources import RetryStrategy


@override_settings(
    BKBASE_API_VERSION="v4",
    BKBASE_V4_TENANT="tenant_a",
    BKBASE_V4_NAMESPACE="audit",
    BKBASE_V4_STREAM_CLUSTER="synthetic_stream",
)
class MissingCreateRetryTests(TransactionTestCase):
    def setUp(self):
        self.logical = "1_" + "long_input_" * 6
        self.ref = {"kind": "Flow", "tenant": "tenant_a", "namespace": "audit", "name": "original_flow"}
        self.input_ref = {"kind": "ResultTable", "tenant": "tenant_a", "namespace": "inputs", "name": "real_input"}
        source_name = flow.stable_name("src", self.logical)
        self.old_spec = {
            "nodes": [
                {"kind": "StreamSourceNode", "name": source_name, "data": self.input_ref},
                {
                    "kind": "StreamNode",
                    "name": "old_sql",
                    "inputs": [source_name],
                    "output": "1_saved_output",
                    "config": {"sql": "SELECT old"},
                },
            ]
        }
        self.strategy = Strategy.objects.create(
            namespace="audit",
            strategy_name="synthetic retry",
            strategy_type=StrategyType.RULE,
            status=StrategyStatusChoices.UPDATE_FAILED,
            configs={
                "config_type": RuleAuditConfigType.BIZ_RT,
                "data_source": {"rt_id": self.logical, "source_type": FlowDataSourceNodeType.REALTIME},
            },
            sql="SELECT current_configuration FROM input",
            backend_data={
                "retained": {"keep": True},
                "bkbase_v4": {
                    "flow": self.ref,
                    "operation": "create",
                    "pending_spec": deepcopy(self.old_spec),
                    "requested_action": "start",
                    "operation_id": "original",
                    "output_name": "saved_output",
                    "output_rt_id": "1_saved_output",
                },
            },
        )
        self.remote = None
        self.mode = "missing"
        self.flow_reads, self.posts, self.gets = 0, [], []
        self.on_flow_read = self.on_rt_read = None
        self.appear_at = None
        self.input = {
            "kind": "ResultTable",
            "metadata": {**self.input_ref, "labels": {"result_table_id": self.logical}},
            "spec": {"predefiendResultTableId": self.logical, "bizId": 1},
            "status": {
                "phase": "Ok",
                "related": [
                    {
                        "kind": "ChannelBinding",
                        "metadata": {"tenant": "tenant_a", "namespace": "inputs", "name": "channel"},
                        "spec": {"data": self.input_ref},
                        "status": {"phase": "Ok"},
                    }
                ],
            },
        }
        cluster = {"kind": "Doris", "tenant": "tenant_a", "namespace": "clusters", "name": "doris_a"}
        CollectorPlugin.objects.create(
            namespace="audit",
            collector_plugin_id=7,
            collector_plugin_name="synthetic events",
            collector_plugin_name_en="synthetic_events",
            bkdata_biz_id=1,
            table_id=1,
            index_set_id=1,
        )
        configs = {
            BKBASE_V4_FLOW_CONFIG: {
                "operation_config": {"start_position": "continue"},
                "doris_databases": {"doris_a": "audit_db"},
            },
            BKBASE_V4_STORAGE_CLUSTER_MAP: {"doris": {"legacy_doris": cluster}},
            DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY: {"bkbase_cluster_id": "legacy_doris"},
            DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY: None,
        }
        configs[COLLECTOR_PLUGIN_ID] = 7
        self.enterContext(
            mock.patch.object(
                flow.GlobalMetaConfig,
                "get",
                side_effect=lambda *a, **kw: deepcopy(configs.get(a[0] if a else kw["config_key"], kw.get("default"))),
            )
        )
        self.enterContext(
            mock.patch.object(
                flow.metadata_service,
                "get_result_tables",
                return_value=[{"result_table_id": self.logical, "bk_biz_id": 1}],
            )
        )
        self.enterContext(mock.patch.object(RuleAuditController, "storage_nodes", [DorisStorageNode]))
        self.enterContext(mock.patch.object(flow, "resource_lock"))
        self.enterContext(mock.patch.object(BkBaseV4Resource, "build_header", return_value={}))
        self.enterContext(mock.patch("requests.sessions.Session.request", side_effect=self.transport))
        self.queue = self.enterContext(mock.patch.object(tasks.check_flow_status, "delay"))
        self.dispatches = []

        def dispatch(*args, **kwargs):
            self.dispatches.append((args, deepcopy(kwargs)))
            return tasks.call_controller.run(*args, **kwargs)

        # 只将delay队列边界同步驱动，保留真实call_controller/Controller/构图及写保护。
        self.enterContext(mock.patch.object(base_control.call_controller, "delay", side_effect=dispatch))

    def transport(self, method, url, **kwargs):
        self.assertFalse(connection.in_atomic_block, "HTTP cannot hold a row-lock transaction")
        method = method.upper()
        if method == "GET":
            self.gets.append(url)
            if "/flows/" in url:
                self.flow_reads += 1
                if self.on_flow_read:
                    self.on_flow_read(self.flow_reads)
                if self.appear_at == self.flow_reads:
                    self.remote = {
                        "kind": "Flow",
                        "metadata": deepcopy(self.ref),
                        "spec": deepcopy(self.old_spec),
                        "status": {"phase": "Pending"},
                    }
                if self.mode == "timeout":
                    raise requests.Timeout("synthetic read timeout")
                if self.mode == "denied":
                    envelope = {
                        "result": False,
                        "code": "1500001",
                        "message": "synthetic permission error",
                        "data": None,
                    }
                elif self.remote is None:
                    envelope = {"result": False, "code": "1558025", "message": "resource not exists", "data": None}
                else:
                    envelope = {"result": True, "code": "00", "data": deepcopy(self.remote)}
            else:
                self.assertTrue("/result_tables/" in url or "/resulttables/" in url)
                if "/resulttables/" in url and self.on_rt_read:
                    callback, self.on_rt_read = self.on_rt_read, None
                    callback()
                envelope = {"result": True, "code": "00", "data": deepcopy(self.input)}
        else:
            self.assertEqual(method, "POST")
            self.assertTrue(url.endswith("/tenants/tenant_a/namespaces/audit/flows/"))
            payload = deepcopy(kwargs["json"])
            current = Strategy.objects.get(pk=self.strategy.pk)
            self.assertEqual(current.backend_data["bkbase_v4"]["operation"], "create")
            self.assertEqual(current.backend_data["bkbase_v4"]["flow"], self.ref)
            self.assertTrue(current.backend_data["bkbase_v4"]["flow_write"]["token"])
            self.posts.append(payload)
            self.remote = {"kind": "Flow", **payload, "status": {"phase": "Pending"}}
            envelope = {"result": True, "code": "00", "data": deepcopy(self.remote)}
        response = requests.Response()
        response.status_code = 200
        response.url = url
        response.request = requests.Request(method, url).prepare()
        response._content = json.dumps(envelope).encode()
        return response

    def retry(self):
        endpoint = RetryStrategy()
        with mock.patch.object(endpoint, "ensure_active_scene_binding_or_404"), mock.patch(
            "services.web.strategy_v2.resources.get_request_username", return_value="synthetic_operator"
        ):
            endpoint.request({"strategy_id": self.strategy.pk})
        self.strategy.refresh_from_db()

    def assert_rebuilt_once(self):
        self.retry()
        self.assertEqual(len(self.posts), 1)
        spec = self.posts[0]["spec"]
        self.assertNotEqual(spec, self.old_spec)
        self.assertTrue(all(len(n["name"]) <= 50 for n in spec["nodes"]))
        source, sql, storage = spec["nodes"]
        self.assertEqual(source["data"], self.input_ref)
        self.assertEqual(sql["inputs"], [source["name"]])
        self.assertEqual(storage["input"], sql["name"])
        self.assertEqual(sql["config"]["sql"], self.strategy.sql)
        self.assertEqual(sql["output"], "1_saved_output")
        binding = self.strategy.backend_data["bkbase_v4"]
        self.assertEqual(binding["flow"], self.ref)
        self.assertEqual(binding["operation"], "wait_running")
        self.assertNotIn("pending_spec", binding)
        self.assertNotIn("flow_write", binding)
        self.assertNotEqual(binding["operation_id"], "original")
        self.assertEqual(self.strategy.backend_data["retained"], {"keep": True})
        self.assertEqual(Strategy.objects.count(), 1)
        self.assertEqual(len(self.dispatches), 1)
        self.assertEqual(self.dispatches[0][1]["func_name"], "_update_or_create")
        self.queue.assert_called_once()

    def test_product_retry_rebuilds_long_input_from_current_controller_and_same_ref(self):
        self.assertGreater(len(self.old_spec["nodes"][0]["name"]), 50)
        self.assert_rebuilt_once()

    def test_finished_outcome_unknown_hint_without_active_writer_still_allows_explicit_retry(self):
        self.strategy.backend_data["bkbase_v4"]["outcome_unknown"] = True
        self.strategy.save(update_record=False, update_fields=["backend_data"])
        self.assert_rebuilt_once()

    def test_only_explicit_notfound_can_continue_to_controller(self):
        for mode in ("timeout", "denied"):
            self.mode = mode
            with self.subTest(mode=mode), self.assertRaises((APIRequestError, requests.Timeout)):
                self.retry()
        self.assertEqual(self.posts, [])
        self.assertEqual(self.dispatches, [])

    def test_missing_existing_update_delete_or_empty_pending_is_not_recreated(self):
        original = deepcopy(self.strategy.backend_data)
        for operation, pending in (
            ("wait_running", self.old_spec),
            ("wait_stopped", self.old_spec),
            ("delete", self.old_spec),
            ("create", None),
            ("create", {}),
        ):
            backend = deepcopy(original)
            backend["bkbase_v4"].update(operation=operation, pending_spec=pending)
            Strategy.objects.filter(pk=self.strategy.pk).update(backend_data=backend)
            with self.subTest(operation=operation, pending=pending is not None), self.assertRaises(APIRequestError):
                self.retry()
        self.assertEqual(self.posts, [])

    def test_active_write_pure_observation_restart_and_delete_guards_block_rebuild(self):
        original = deepcopy(self.strategy.backend_data)
        guards = [
            {"flow_write": {"token": "interrupted", "outcome_unknown": True}},
            {"flow_write": {}},
            {"pure_operation": {"writer": "active"}},
            {"pure_operation": {"write_fence": True}},
            {"pure_operation": {"id": "original", "target": "start", "observing": True}},
            {"pure_operation": {"restart": True}},
            {"delete_operation": {"pending": True}},
            {"delete_operation": {"writer": "active"}},
        ]
        for guard in guards:
            backend = deepcopy(original)
            backend["bkbase_v4"].update(guard)
            Strategy.objects.filter(pk=self.strategy.pk).update(
                backend_data=backend, status=StrategyStatusChoices.UPDATE_FAILED
            )
            with self.subTest(guard=guard), self.assertRaises(BKBaseException):
                self.retry()
        self.assertEqual(self.posts, [])

    def test_shared_and_soft_deleted_aliases_block_recreation(self):
        for deleted in (False, True):
            alias = Strategy.objects.create(
                namespace="audit",
                strategy_name="alias",
                strategy_type=StrategyType.RULE,
                status=StrategyStatusChoices.DISABLED,
                is_deleted=deleted,
                backend_data={"bkbase_v4": {"flow": self.ref}},
            )
            with self.subTest(deleted=deleted), self.assertRaises(BKBaseException):
                self.retry()
            alias.backend_data = {}
            alias.save(update_record=False, update_fields=["backend_data"])
        self.assertEqual(self.posts, [])

    def test_deleted_strategy_is_not_recreated(self):
        Strategy.objects.filter(pk=self.strategy.pk).update(is_deleted=True)
        with self.assertRaises((BKBaseException, Http404)):
            self.retry()
        self.assertEqual(self.posts, [])

    def test_new_operation_or_configuration_during_notfound_preflight_is_not_replaced(self):
        for field in ("operation_id", "sql"):

            def change(_count):
                self.on_flow_read = None
                if field == "sql":
                    Strategy.objects.filter(pk=self.strategy.pk).update(sql="SELECT newer")
                else:
                    backend = deepcopy(self.strategy.backend_data)
                    backend["bkbase_v4"]["operation_id"] = "newer"
                    Strategy.objects.filter(pk=self.strategy.pk).update(backend_data=backend)

            self.strategy.refresh_from_db()
            self.on_flow_read = change
            with self.subTest(field=field), self.assertRaises(BKBaseOperationSuperseded):
                self.retry()
        self.assertEqual(self.posts, [])

    def test_changed_config_between_preflight_and_prepare_is_not_overwritten(self):
        self.assertFalse(flow.retry_failed_pure(self.strategy))
        Strategy.objects.filter(pk=self.strategy.pk).update(sql="SELECT newer")
        with self.assertRaises(BKBaseOperationSuperseded):
            flow.prepare_controller_update(self.strategy, StrategyStatusChoices.UPDATING)
        self.assertEqual(self.posts, [])

    def test_configuration_change_after_build_observation_is_blocked_at_writer_registration(self):
        self.on_rt_read = lambda: Strategy.objects.filter(pk=self.strategy.pk).update(sql="SELECT newer")
        with self.assertRaises(BKBaseOperationSuperseded):
            self.retry()
        self.assertEqual(self.posts, [])
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.sql, "SELECT newer")

    def test_alias_added_during_rebuild_is_not_written_through(self):
        self.on_rt_read = lambda: Strategy.objects.create(
            namespace="audit",
            strategy_name="late alias",
            strategy_type=StrategyType.RULE,
            status=StrategyStatusChoices.DISABLED,
            is_deleted=True,
            backend_data={"bkbase_v4": {"flow": self.ref}},
        )
        with self.assertRaises(BKBaseException):
            self.retry()
        self.assertEqual(self.posts, [])

    def test_resource_appearing_before_locked_apply_is_not_adopted_or_overwritten(self):
        self.appear_at = 3
        with self.assertRaises(BKBaseException):
            self.retry()
        self.assertEqual(self.posts, [])
        self.assertEqual(self.remote["spec"], self.old_spec)
