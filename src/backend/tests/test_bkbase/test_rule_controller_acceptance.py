"""验证普通实时规则控制器到 V4 整图受理的本地业务链。"""
import json
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

import requests
from django.test import TransactionTestCase, override_settings

from api.bk_base_v4.default import BkBaseV4Resource
from services.web.analyze.constants import (
    DEFAULT_HDFS_STORAGE_CLUSTER_KEY,
    DEFAULT_QUEUE_STORAGE_CLUSTER_KEY,
)
from services.web.analyze.controls.rule_audit import RuleAuditController
from services.web.analyze.storage_node import DorisStorageNode
from services.web.bkbase.constants import (
    BKBASE_V4_FLOW_CONFIG,
    BKBASE_V4_STORAGE_CLUSTER_MAP,
)
from services.web.databus.constants import (
    DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
    DEFAULT_STORAGE_CONFIG_KEY,
    DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY,
)
from services.web.databus.models import Snapshot
from services.web.strategy_v2.constants import StrategyStatusChoices
from services.web.strategy_v2.models import Strategy


@override_settings(
    BKBASE_API_VERSION="v4",
    BKBASE_V4_TENANT="tenant_a",
    BKBASE_V4_NAMESPACE="audit",
    BKBASE_V4_STREAM_CLUSTER="synthetic_stream",
    BKBASE_V4_RESULT_TABLE_NAMESPACES={"1_input_rt": "inputs"},
)
class RuleControllerAcceptanceTests(TransactionTestCase):
    def test_realtime_rule_is_submitted_as_graph_but_not_reported_running(self):
        self._assert_realtime_rule_submission()

    def test_realtime_doris_graph_includes_required_empty_field_configuration(self):
        """实际三节点请求必须携带 Doris 必需配置，允许平台自动分配物理表。"""
        with mock.patch.object(RuleAuditController, "storage_nodes", [DorisStorageNode]), mock.patch.object(
            DorisStorageNode, "expires", "1d"
        ):
            payload = self._assert_realtime_rule_submission(doris_only=True)

        self.assertEqual(
            [node["kind"] for node in payload["spec"]["nodes"]],
            ["StreamSourceNode", "StreamNode", "DorisStorageNode"],
        )
        storage_config = payload["spec"]["nodes"][-1]["storage_config"]
        self.assertIn("field_config_group", storage_config)
        self.assertEqual(
            storage_config,
            {
                "db": "audit_db",
                "table": None,
                "use_lowercase_field": False,
                "table_type": "duplicate_table",
                "storage_keys": [],
                "json_fields": [],
                "original_json_fields": ["event_evidence", "event_data"],
                "field_config_group": {},
                "expires": "1d",
            },
        )

    def _assert_realtime_rule_submission(self, *, doris_only=False):
        """保留真实控制器、节点生成和 API 序列化，仅隔离外部依赖。"""
        sql = "SELECT user_id FROM 1_input_rt WHERE action = 'read'"
        strategy = Strategy.objects.create(
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
                ("es", "ElasticSearch", "es_a"),
                ("kafka", "Kafka", "kafka_a"),
                ("hdfs", "Hdfs", "hdfs_a"),
                ("doris", "Doris", "doris_a"),
            )
        }
        input_ref = {"kind": "ResultTable", "tenant": "tenant_a", "namespace": "inputs", "name": "physical_input_rt"}
        Snapshot.objects.create(
            system_id="synthetic_system",
            resource_type_id="input",
            bkbase_table_id="1_input_rt",
            bkbase_v4_resources={"result_table_id": "1_input_rt", "result_table": input_ref},
        )
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
            DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY: None if doris_only else "events_table",
        }

        submitted = []

        def transport(method, url, **kwargs):
            if method == "GET":
                info = url.endswith("/v4/result_tables/1_input_rt/")
                self.assertTrue(info or url.endswith("/v4/namespaces/inputs/resulttables/physical_input_rt/"))
                result = {
                    "kind": "ResultTable",
                    "metadata": {**input_ref, "labels": {}},
                    "spec": {"predefiendResultTableId": "1_input_rt"},
                    "status": {
                        "phase": "Ok",
                        "related": [
                            {
                                "kind": "ChannelBinding",
                                "metadata": {"tenant": "tenant_a", "namespace": "inputs", "name": "input_channel"},
                                "spec": {"data": input_ref},
                                "status": {"phase": "Ok"},
                            }
                        ]
                        if info
                        else [],
                    },
                }
            else:
                self.assertEqual(method, "POST")
                self.assertTrue(url.endswith("/v4/tenants/tenant_a/namespaces/audit/flows/"))
                payload = kwargs["json"]
                submitted.append(deepcopy(payload))
                result = {"metadata": payload["metadata"], "spec": payload["spec"], "status": {"phase": "Pending"}}
            response = requests.Response()
            response.status_code = 200
            response._content = json.dumps({"result": True, "code": "00", "data": result}).encode()
            response.url = url
            response.request = requests.Request(method, url).prepare()
            return response

        with mock.patch("requests.sessions.Session.request", side_effect=transport), mock.patch.object(
            BkBaseV4Resource, "build_header", return_value={}
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
            "services.web.bkbase.metadata.api.bk_base_v4.dataset_detail",
            return_value={"dataset_name": "1_input_rt", "fields": []},
        ), mock.patch(
            "services.web.bkbase.metadata.api.bk_base_v4.dataset_list",
            return_value={"pages_num": 0, "total": 0, "list": []},
        ), mock.patch(
            "services.web.bkbase.flow.bk_resource_settings",
            SimpleNamespace(PLATFORM_AUTH_ACCESS_USERNAME="test_operator"),
        ), mock.patch(
            "services.web.bkbase.flow.resource_lock"
        ), mock.patch(
            "services.web.bkbase.flow.get_resource_or_none", return_value=None
        ):
            controller = RuleAuditController(strategy.strategy_id)
            result = controller._update_or_create_bkbase_flow()

        self.assertEqual(len(submitted), 1)
        payload = submitted[0]
        source, stream, *storage_nodes = payload["spec"]["nodes"]
        self.assertEqual(source["kind"], "StreamSourceNode")
        self.assertEqual(source["data"], input_ref)
        self.assertEqual(stream["kind"], "StreamNode")
        self.assertEqual(stream["inputs"], [source["name"]])
        self.assertEqual(stream["config"]["sql"], sql)
        self.assertEqual(stream["biz_id"], 1)
        self.assertEqual(stream["output"], "1_rule_output")
        strategy.refresh_from_db()
        self.assertEqual(strategy.backend_data["bkbase_v4"]["output_rt_id"], "1_rule_output")
        self.assertEqual(
            {node["kind"]: node["storage"] for node in storage_nodes},
            (
                {"DorisStorageNode": refs["doris"]}
                if doris_only
                else {
                    "EsStorageNode": refs["es"],
                    "QueueStorageNode": refs["kafka"],
                    "HdfsStorageNode": refs["hdfs"],
                    "DorisStorageNode": refs["doris"],
                }
            ),
        )
        self.assertTrue(all(node["input"] == stream["name"] for node in storage_nodes))
        doris = next(node for node in storage_nodes if node["kind"] == "DorisStorageNode")
        self.assertEqual(doris["storage_config"]["db"], "audit_db")
        self.assertEqual(doris["storage_config"]["table"], None if doris_only else "events_table")
        self.assertTrue(result["accepted"])
        self.assertEqual(result["resource_phase"], "Pending")
        self.assertIsNone(result["task_state"])
        self.assertEqual(strategy.status, StrategyStatusChoices.STARTING)
        self.assertEqual(strategy.backend_data["bkbase_v4"]["operation"], "wait_running")
        return payload
