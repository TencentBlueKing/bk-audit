"""验证普通实时规则控制器到 V4 整图受理的本地业务链。"""
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, override_settings

from services.web.analyze.constants import (
    DEFAULT_HDFS_STORAGE_CLUSTER_KEY,
    DEFAULT_QUEUE_STORAGE_CLUSTER_KEY,
)
from services.web.analyze.controls.rule_audit import RuleAuditController
from services.web.bkbase.constants import (
    BKBASE_V4_FLOW_CONFIG,
    BKBASE_V4_STORAGE_CLUSTER_MAP,
)
from services.web.databus.constants import (
    DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
    DEFAULT_STORAGE_CONFIG_KEY,
    DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY,
)
from services.web.strategy_v2.constants import StrategyStatusChoices


@override_settings(
    BKBASE_API_VERSION="v4",
    BKBASE_V4_TENANT="tenant_a",
    BKBASE_V4_NAMESPACE="audit",
    BKBASE_V4_RESULT_TABLE_NAMESPACES={"1_input_rt": "inputs"},
)
class RuleControllerAcceptanceTests(SimpleTestCase):
    def test_realtime_rule_is_submitted_as_graph_but_not_reported_running(self):
        sql = "SELECT user_id FROM 1_input_rt WHERE action = 'read'"
        strategy = SimpleNamespace(
            strategy_id=7,
            strategy_name="test rule",
            namespace="audit",
            status=StrategyStatusChoices.STARTING,
            sql=sql,
            configs={"config_type": "BizRt", "data_source": {"source_type": "stream_source", "rt_id": "1_input_rt"}},
            backend_data={"bkbase_v4": {"operation_id": "op_a", "output_name": "rule_output"}},
        )
        refs = {
            kind: {"kind": ref_kind, "tenant": "tenant_a", "namespace": "clusters", "name": name}
            for kind, ref_kind, name in (
                ("es", "EsCluster", "es_a"),
                ("kafka", "KafkaCluster", "kafka_a"),
                ("hdfs", "HdfsCluster", "hdfs_a"),
                ("doris", "DorisCluster", "doris_a"),
            )
        }
        config = {
            BKBASE_V4_FLOW_CONFIG: {
                "operation_config": {"start_position": "continue"},
                "doris_databases": {"doris_a": "audit_db"},
            },
            BKBASE_V4_STORAGE_CLUSTER_MAP: {
                "es": {"legacy_es": refs["es"]},
                "kafka": {"legacy_kafka": refs["kafka"]},
                "hdfs": {"legacy_hdfs": refs["hdfs"]},
                "doris": {"legacy_doris": refs["doris"]},
            },
            DEFAULT_STORAGE_CONFIG_KEY: 1,
            DEFAULT_QUEUE_STORAGE_CLUSTER_KEY: "legacy_kafka",
            DEFAULT_HDFS_STORAGE_CLUSTER_KEY: "legacy_hdfs",
            DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY: {"bkbase_cluster_id": "legacy_doris"},
            DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY: "events_table",
        }
        rt = {"result_table_id": "1_input_rt", "bk_biz_id": 1, "fields": [], "storages": {}}

        def save_binding(owner, patch, *, remove=(), expected_operation_id=None):
            binding = owner.backend_data.setdefault("bkbase_v4", {})
            if expected_operation_id is not None:
                self.assertEqual(binding["operation_id"], expected_operation_id)
            binding.update(deepcopy(patch))
            for key in remove:
                binding.pop(key, None)
            return binding

        def create_flow(**payload):
            return {"metadata": payload["metadata"], "spec": payload["spec"], "status": {"phase": "Pending"}}

        with mock.patch("requests.sessions.Session.request", side_effect=AssertionError("Unexpected HTTP")), mock.patch(
            "services.web.analyze.controls.base.Strategy.objects.get", return_value=strategy
        ), mock.patch(
            "apps.meta.models.GlobalMetaConfig.get",
            side_effect=lambda *args, **kwargs: config[args[0] if args else kwargs["config_key"]],
        ), mock.patch(
            "services.web.analyze.storage_node.resource.databus.storage.storage_list",
            return_value=[{"cluster_config": {"cluster_id": 1, "custom_option": {"bkbase_cluster_id": "legacy_es"}}}],
        ), mock.patch(
            "services.web.analyze.storage_node.EventHandler.get_table_id", return_value="1.event"
        ), mock.patch(
            "services.web.analyze.controls.rule_audit.CollectorPlugin.build_collector_rt", return_value="1_event_log"
        ), mock.patch(
            "services.web.bkbase.metadata.api.bk_base_v4.result_table", return_value=rt
        ), mock.patch(
            "services.web.bkbase.flow.bk_resource_settings",
            SimpleNamespace(PLATFORM_AUTH_ACCESS_USERNAME="test_operator"),
        ), mock.patch(
            "services.web.bkbase.flow._save_binding", side_effect=save_binding
        ), mock.patch(
            "services.web.bkbase.flow.resource_lock"
        ), mock.patch(
            "services.web.bkbase.flow.get_resource_or_none", return_value=None
        ), mock.patch(
            "services.web.bkbase.flow.api.bk_base_v4.flow_create", side_effect=create_flow
        ) as create:
            controller = RuleAuditController(strategy.strategy_id)
            result = controller._update_or_create_bkbase_flow()

        create.assert_called_once()
        payload = create.call_args.kwargs
        source, stream, *storage_nodes = payload["spec"]["nodes"]
        self.assertEqual(source["kind"], "StreamSourceNode")
        self.assertEqual(
            source["data"], {"kind": "ResultTable", "tenant": "tenant_a", "namespace": "inputs", "name": "1_input_rt"}
        )
        self.assertEqual(stream["kind"], "StreamNode")
        self.assertEqual(stream["inputs"], [source["name"]])
        self.assertEqual(stream["config"]["sql"], sql)
        self.assertEqual(stream["biz_id"], 1)
        self.assertEqual(stream["output"], "1_rule_output")
        self.assertEqual(strategy.backend_data["bkbase_v4"]["output_rt_id"], "1_rule_output")
        self.assertEqual(
            {node["kind"]: node["storage"] for node in storage_nodes},
            {
                "EsStorageNode": refs["es"],
                "QueueStorageNode": refs["kafka"],
                "HdfsStorageNode": refs["hdfs"],
                "DorisStorageNode": refs["doris"],
            },
        )
        self.assertTrue(all(node["input"] == stream["name"] for node in storage_nodes))
        doris = next(node for node in storage_nodes if node["kind"] == "DorisStorageNode")
        self.assertEqual(doris["storage_config"]["db"], "audit_db")
        self.assertEqual(doris["storage_config"]["table"], "events_table")
        self.assertTrue(result["accepted"])
        self.assertEqual(result["resource_phase"], "Pending")
        self.assertIsNone(result["task_state"])
        self.assertEqual(strategy.status, StrategyStatusChoices.STARTING)
        self.assertEqual(strategy.backend_data["bkbase_v4"]["operation"], "wait_running")
