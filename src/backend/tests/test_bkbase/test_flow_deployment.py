"""V4 规则计算部署参数与正式读回的兼容性。"""

import json
from contextlib import nullcontext
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

import requests
from django.test import SimpleTestCase, override_settings

from api.bk_base_v4.default import BkBaseV4Resource, FlowCreate
from services.web.analyze.constants import FlowDataSourceNodeType as NodeType
from services.web.analyze.controls.rule_audit import RuleAuditController
from services.web.analyze.storage_node import HDFSStorageNode
from services.web.bkbase import flow
from services.web.bkbase.constants import TaskState
from services.web.bkbase.exceptions import BKBaseResourceMappingError


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_STREAM_CLUSTER="", BKBASE_V4_BATCH_CLUSTER="")
class FlowDeploymentTests(SimpleTestCase):
    def setUp(self):
        self.context = {"version": "v4", "tenant": "tenant_a", "namespace": "audit", "rt_namespaces": {}}
        self.ref = {"kind": "Flow", "tenant": "tenant_a", "namespace": "audit", "name": "existing"}
        self.input = {"kind": "ResultTable", "tenant": "tenant_a", "namespace": "inputs", "name": "47_input"}
        self.strategy = SimpleNamespace(
            strategy_id=390,
            strategy_name="rule",
            namespace="audit",
            backend_data={},
            sql="SELECT * FROM 47_input",
            configs={"data_source": {"source_type": NodeType.REALTIME}},
        )
        self.controller = SimpleNamespace(
            strategy=self.strategy,
            rt_ids=["47_input"],
            rt_node_map={},
            raw_table_name="synthetic_output",
            storage_nodes=[HDFSStorageNode],
            check_source_type=lambda rt: self.strategy.configs["data_source"]["source_type"],
        )
        self.controller._build_sql_node_config = lambda biz: RuleAuditController._build_sql_node_config(
            self.controller, biz
        )
        self.profile = self.enterContext(mock.patch.object(flow.GlobalMetaConfig, "get", return_value={}))
        self.flow_get = self.enterContext(mock.patch.object(flow.api.bk_base_v4, "flow_get"))
        self.enterContext(mock.patch.object(flow, "_input_result_table_refs", return_value={"47_input": self.input}))
        self.enterContext(
            mock.patch.object(
                flow.metadata_service,
                "get_result_tables",
                return_value=[{"result_table_id": "47_input", "bk_biz_id": 47}],
            )
        )
        self.enterContext(mock.patch.object(flow, "_save_operation_binding"))
        self.enterContext(
            mock.patch.object(HDFSStorageNode, "cluster", new_callable=mock.PropertyMock, return_value="legacy_hdfs")
        )
        self.enterContext(
            mock.patch.object(
                flow.storage_service,
                "resolve_storage_cluster",
                return_value={"kind": "Hdfs", "tenant": "tenant_a", "namespace": "clusters", "name": "hdfs"},
            )
        )

    def build(self, source_type=NodeType.REALTIME):
        self.strategy.configs["data_source"]["source_type"] = source_type
        return flow.build_controller_spec(self.controller, context=self.context)

    def resource(self, spec):
        return {
            "kind": "Flow",
            "metadata": {**self.ref, "annotations": {"task_stopped": "true"}},
            "spec": spec,
            "status": {"phase": "Ok"},
        }

    def bind(self, spec):
        self.strategy.backend_data = {"bkbase_v4": {"flow": self.ref}}
        self.flow_get.side_effect = None
        self.flow_get.return_value = self.resource(spec)

    def apply(self, desired, *readbacks):
        self.flow_get.reset_mock(side_effect=True)
        self.flow_get.side_effect = [self.resource(spec) for spec in readbacks]
        with mock.patch.object(flow, "_validate_flow_inputs"), mock.patch.object(
            flow, "resource_lock", return_value=nullcontext()
        ), mock.patch.object(
            flow, "get_rule_flow_status", return_value={"task_state": TaskState.STOPPED}
        ), mock.patch.object(
            flow, "_write_flow_request", return_value={}
        ) as write, mock.patch.object(
            flow, "operation_result"
        ):
            flow.apply_rule_flow(self.context, self.strategy, desired)
        return write.call_args.kwargs["spec"]["operation_config"]

    @override_settings(BKBASE_V4_STREAM_CLUSTER=" stream_env ")
    def test_new_stream_uses_environment_and_ignores_profile_deployment(self):
        self.profile.return_value = {
            "operation_config": {
                "stream_sql_deploy_config": {"cluster": "previous", "deploy_config": {"parallelism": 5}},
                "batch_sql_deploy_config": {"cluster": "batch_previous"},
                "start_position": "from_head",
                "retained": True,
            }
        }
        self.assertEqual(
            self.build()["operation_config"],
            {
                "stream_sql_deploy_config": {
                    "cluster": "stream_env",
                    "deploy_mode": "k8s-operator",
                    "deploy_config": None,
                },
                "batch_sql_deploy_config": None,
                "start_position": "continue",
                "retained": True,
            },
        )

    @override_settings(BKBASE_V4_BATCH_CLUSTER="batch_env")
    def test_new_batch_only_requires_batch_environment_cluster(self):
        self.assertEqual(
            self.build(NodeType.BATCH_REAL)["operation_config"],
            {
                "stream_sql_deploy_config": None,
                "batch_sql_deploy_config": {"cluster": "batch_env", "node_deploy_configs": {}},
                "start_position": "continue",
            },
        )

    def test_new_flow_rejects_legacy_cluster_and_names_only_the_required_setting(self):
        self.profile.return_value = {
            "operation_config": {
                "stream_sql_deploy_config": {"cluster": "legacy_stream"},
                "batch_sql_deploy_config": {"cluster": "legacy_batch"},
            }
        }
        for source, needed, other in (
            (NodeType.REALTIME, "BKAPP_BKBASE_V4_STREAM_CLUSTER", "BKAPP_BKBASE_V4_BATCH_CLUSTER"),
            (NodeType.BATCH_REAL, "BKAPP_BKBASE_V4_BATCH_CLUSTER", "BKAPP_BKBASE_V4_STREAM_CLUSTER"),
        ):
            with self.subTest(source=source), self.assertRaisesMessage(BKBaseResourceMappingError, needed) as error:
                self.build(source)
            self.assertNotIn(other, str(error.exception))

    def test_queued_create_without_deployment_is_checked_before_post(self):
        with override_settings(BKBASE_V4_STREAM_CLUSTER="temporary_stream"):
            pending = self.build()
        pending["operation_config"] = {"start_position": "continue"}
        self.profile.return_value = {"operation_config": {"stream_sql_deploy_config": {"cluster": "legacy_stream"}}}
        self.strategy.backend_data = {"bkbase_v4": {"flow": self.ref, "operation": "create"}}
        self.flow_get.return_value = None
        with mock.patch.object(flow, "_validate_flow_inputs"), mock.patch.object(
            flow, "resource_lock", return_value=nullcontext()
        ), mock.patch.object(flow, "_write_flow_request", return_value={}) as write, mock.patch.object(
            flow, "operation_result"
        ):
            with self.assertRaisesMessage(BKBaseResourceMappingError, "BKAPP_BKBASE_V4_STREAM_CLUSTER"):
                flow.apply_rule_flow(self.context, self.strategy, pending)
        write.assert_not_called()

    def test_queued_create_with_cluster_adds_missing_inactive_block_to_post(self):
        with override_settings(BKBASE_V4_STREAM_CLUSTER="temporary_stream"):
            pending = self.build()
        active = pending["operation_config"]["stream_sql_deploy_config"]
        pending["operation_config"].pop("batch_sql_deploy_config")
        self.strategy.backend_data = {"bkbase_v4": {"flow": self.ref, "operation": "create"}}
        self.flow_get.return_value = None

        def transport(method, url, **kwargs):
            self.assertEqual(method, "POST")
            self.assertEqual(
                kwargs["json"]["spec"]["operation_config"],
                {"start_position": "continue", "stream_sql_deploy_config": active, "batch_sql_deploy_config": None},
            )
            response = requests.Response()
            response.status_code = 200
            response._content = json.dumps({"result": True, "code": "00", "data": {}}).encode()
            response.url = url
            response.request = requests.Request(method, url).prepare()
            return response

        with mock.patch.object(flow, "_validate_flow_inputs"), mock.patch.object(
            flow, "resource_lock", return_value=nullcontext()
        ), mock.patch.object(flow.flow_operation, "write_guard", return_value=nullcontext()), mock.patch.object(
            flow.api.bk_base_v4, "flow_create", side_effect=FlowCreate().request
        ), mock.patch.object(
            BkBaseV4Resource, "build_header", return_value={}
        ), mock.patch(
            "requests.sessions.Session.request", side_effect=transport
        ), mock.patch.object(
            flow, "operation_result"
        ):
            flow.apply_rule_flow(self.context, self.strategy, pending)
        self.assertNotIn("batch_sql_deploy_config", pending["operation_config"])

    def test_same_type_edit_without_environment_preserves_fresh_stream_deployment(self):
        with override_settings(BKBASE_V4_STREAM_CLUSTER="old_stream"):
            before = self.build()
        self.bind(before)
        desired = self.build()
        latest = deepcopy(before)
        latest_config = latest["operation_config"]
        latest_config["stream_sql_deploy_config"].update(
            cluster="latest_stream",
            deploy_mode="k8s",
            deploy_config={"parallelism": 8},
        )
        latest_config["batch_sql_deploy_config"] = {"cluster": "platform_retained"}
        self.assertEqual(self.apply(desired, before, latest), latest_config)

    def test_same_type_batch_write_preserves_fresh_null_node_options(self):
        with override_settings(BKBASE_V4_BATCH_CLUSTER="old_batch"):
            before = self.build(NodeType.BATCH_REAL)
        self.bind(before)
        latest = deepcopy(before)
        latest["operation_config"]["batch_sql_deploy_config"] = {
            "cluster": "updated_batch",
            "node_deploy_configs": None,
        }
        with override_settings(BKBASE_V4_BATCH_CLUSTER="unrelated_default"):
            desired = self.build(NodeType.BATCH_REAL)
        self.assertEqual(self.apply(desired, before, latest), latest["operation_config"])

    def test_switch_in_either_direction_uses_only_target_environment(self):
        for old_type, old_setting, new_type, new_setting, expected in (
            (
                NodeType.REALTIME,
                "BKBASE_V4_STREAM_CLUSTER",
                NodeType.BATCH_REAL,
                "BKBASE_V4_BATCH_CLUSTER",
                {
                    "stream_sql_deploy_config": None,
                    "batch_sql_deploy_config": {"cluster": "target", "node_deploy_configs": {}},
                },
            ),
            (
                NodeType.BATCH_REAL,
                "BKBASE_V4_BATCH_CLUSTER",
                NodeType.REALTIME,
                "BKBASE_V4_STREAM_CLUSTER",
                {
                    "stream_sql_deploy_config": {
                        "cluster": "target",
                        "deploy_mode": "k8s-operator",
                        "deploy_config": None,
                    },
                    "batch_sql_deploy_config": None,
                },
            ),
        ):
            with self.subTest(target=new_type):
                self.strategy.backend_data = {}
                with override_settings(**{old_setting: "old"}):
                    previous = self.build(old_type)
                self.bind(previous)
                with override_settings(**{new_setting: "target"}):
                    desired = self.build(new_type)
                    self.assertEqual(
                        self.apply(desired, previous, previous), {**expected, "start_position": "continue"}
                    )

    def test_switch_without_target_environment_rejects_legacy_cluster(self):
        with override_settings(BKBASE_V4_STREAM_CLUSTER="current_stream"):
            self.bind(self.build())
        self.profile.return_value = {"operation_config": {"batch_sql_deploy_config": {"cluster": "legacy_batch"}}}

        with self.assertRaisesMessage(BKBaseResourceMappingError, "BKAPP_BKBASE_V4_BATCH_CLUSTER"):
            self.build(NodeType.BATCH_REAL)

    def test_switch_after_a_new_locked_read_does_not_reuse_the_stale_target_deployment(self):
        with override_settings(BKBASE_V4_STREAM_CLUSTER="old_stream", BKBASE_V4_BATCH_CLUSTER="old_batch"):
            previous = self.build()
            latest = self.build(NodeType.BATCH_REAL)
        self.bind(previous)
        with override_settings(BKBASE_V4_STREAM_CLUSTER="target_stream"):
            desired = self.build()
            self.assertEqual(
                self.apply(desired, previous, latest),
                {
                    "stream_sql_deploy_config": {
                        "cluster": "target_stream",
                        "deploy_mode": "k8s-operator",
                        "deploy_config": None,
                    },
                    "batch_sql_deploy_config": None,
                    "start_position": "continue",
                },
            )
