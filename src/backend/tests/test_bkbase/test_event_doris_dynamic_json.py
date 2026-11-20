"""动态事件JSON的Doris声明；真实Controller/Service/SDK，HTTP传输受控。"""
import json
from copy import deepcopy
from unittest import mock

import requests
from django.db import connection
from django.test import SimpleTestCase, TransactionTestCase, override_settings

from api.bk_base_v4.default import BkBaseV4Resource
from services.web.analyze.controls.rule_audit import RuleAuditController
from services.web.analyze.storage_node import DorisStorageNode, ESStorageNode
from services.web.bkbase import clean, flow, storage
from services.web.bkbase.constants import (
    BKBASE_V4_FLOW_CONFIG,
    BKBASE_V4_STORAGE_CLUSTER_MAP,
    TaskState,
)
from services.web.databus.collector_plugin.handlers import EventCollectorEtlHandler
from services.web.databus.constants import (
    COLLECTOR_PLUGIN_ID,
    DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
    DEFAULT_STORAGE_CONFIG_KEY,
    DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY,
    DORIS_EVENT_STORAGE_CONFIG_KEY,
    PluginSceneChoices,
)
from services.web.databus.models import CollectorPlugin
from services.web.strategy_v2.constants import StrategyStatusChoices, StrategyType
from services.web.strategy_v2.models import Strategy


class EventDorisJsonCompatibilityTests(SimpleTestCase):
    def setUp(self):
        configs = {
            DEFAULT_STORAGE_CONFIG_KEY: 1,
            DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY: {"bkbase_cluster_id": "doris_a"},
            DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY: "audit_db.events",
        }
        self.enterContext(
            mock.patch.object(
                flow.GlobalMetaConfig, "get", side_effect=lambda key=None, **kw: configs[key or kw["config_key"]]
            )
        )
        self.enterContext(
            mock.patch("services.web.analyze.storage_node.EventHandler.get_table_id", return_value="1.bklog_events")
        )
        self.enterContext(
            mock.patch(
                "services.web.analyze.storage_node.resource.databus.storage.storage_list",
                return_value=[{"cluster_config": {"cluster_id": 1, "custom_option": {"bkbase_cluster_id": "es_a"}}}],
            )
        )
        self.enterContext(
            mock.patch("requests.sessions.Session.request", side_effect=AssertionError("unexpected HTTP"))
        )

    def test_v3_doris_builder_keeps_legacy_dynamic_json_configuration(self):
        with override_settings(BKBASE_API_VERSION="v3"):
            config = DorisStorageNode("audit").build_node_config(1, "rule", ["1_input"])
        self.assertEqual(config["json_fields"], ["event_evidence", "event_data"])
        self.assertEqual(config["original_json_fields"], [])
        fields = {field["field"]: field for field in config["custom_param_config"]["fields"]}
        self.assertEqual(fields["event_data"]["config"], "json")
        self.assertEqual(fields["event_evidence"]["config"], "json")

    def test_es_builder_is_unchanged_between_v3_and_v4(self):
        with override_settings(BKBASE_API_VERSION="v3"):
            legacy = ESStorageNode("audit").build_node_config(1, "rule", ["1_input"])
        with override_settings(BKBASE_API_VERSION="v4"):
            current = ESStorageNode("audit").build_node_config(1, "rule", ["1_input"])
        self.assertEqual(current, legacy)
        self.assertEqual(current["json_fields"], [])
        self.assertNotIn("original_json_fields", current)

    def test_controlled_json_fields_are_not_blanket_converted_to_original_json(self):
        fields = EventCollectorEtlHandler.get_doris_fields()
        fields.append({"field_name": "known_structure", "is_json": True, "is_original_json": False})
        converted = storage.convert_storage_config({"storage_type": "doris", "fields": fields})["taskFieldSetting"]
        self.assertEqual(converted["json_fields"], ["known_structure"])
        self.assertEqual(converted["original_json_fields"], ["event_evidence", "event_data"])


@override_settings(
    BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit", DEFAULT_BK_BIZ_ID=1
)
class EventDorisJsonRequestTests(TransactionTestCase):
    def setUp(self):
        self.logical = "1_bklog_events"
        self.rt_ref = {"kind": "ResultTable", "tenant": "tenant_a", "namespace": "inputs", "name": "native_events"}
        self.cluster = {"kind": "Doris", "tenant": "tenant_a", "namespace": "clusters", "name": "doris_a"}
        self.owner = CollectorPlugin.objects.create(
            namespace="audit",
            collector_plugin_id=7,
            collector_plugin_name="Synthetic events",
            collector_plugin_name_en="events",
            bkdata_biz_id=1,
            table_id=1,
            index_set_id=1,
            plugin_scene=PluginSceneChoices.EVENT,
            bkbase_v4_resources={"result_table": self.rt_ref, "result_table_id": self.logical},
        )
        self.strategy = Strategy.objects.create(
            namespace="audit",
            strategy_name="Synthetic JSON rule",
            strategy_type=StrategyType.RULE,
            status=StrategyStatusChoices.STARTING,
            configs={"config_type": "BizRt", "data_source": {"source_type": "stream_source", "rt_id": self.logical}},
            backend_data={"bkbase_v4": {"operation_id": "json_operation", "output_name": "json_output"}},
        )
        self.configs = {
            COLLECTOR_PLUGIN_ID: 7,
            DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY: {"bkbase_cluster_id": "legacy_doris"},
            DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY: "audit_db.events",
            DORIS_EVENT_STORAGE_CONFIG_KEY: {},
            BKBASE_V4_STORAGE_CLUSTER_MAP: {"doris": {"legacy_doris": self.cluster}},
            BKBASE_V4_FLOW_CONFIG: {
                "operation_config": {"start_position": "continue"},
                "doris_databases": {"doris_a": "audit_db"},
            },
        }
        self.flow_resource = self.storage_resource = None
        self.writes = []
        self.enterContext(
            mock.patch.object(
                flow.GlobalMetaConfig,
                "get",
                side_effect=lambda key=None, **kw: deepcopy(
                    self.configs.get(key or kw["config_key"], kw.get("default"))
                ),
            )
        )

        def save_config(config_key, config_value, **kwargs):
            self.configs[config_key] = deepcopy(config_value)

        self.enterContext(mock.patch.object(flow.GlobalMetaConfig, "set", side_effect=save_config))
        self.enterContext(mock.patch.object(RuleAuditController, "storage_nodes", [DorisStorageNode]))
        self.enterContext(
            mock.patch.object(
                flow.metadata_service,
                "get_result_tables",
                return_value=[{"result_table_id": self.logical, "bk_biz_id": 1}],
            )
        )
        self.enterContext(mock.patch.object(flow, "resource_lock"))
        self.enterContext(mock.patch.object(storage, "resource_lock"))
        self.enterContext(mock.patch.object(BkBaseV4Resource, "build_header", return_value={}))
        self.enterContext(mock.patch("requests.sessions.Session.request", side_effect=self.transport))

    def transport(self, method, url, **kwargs):
        self.assertFalse(connection.in_atomic_block, "HTTP must not retain row-lock transaction")
        if method == "GET":
            if "/flows/" in url:
                value = self.flow_resource
            elif "/datastorages/" in url:
                value = self.storage_resource
            else:
                self.assertTrue("/result_tables/" in url or "/resulttables/" in url, url)
                value = {
                    "kind": "ResultTable",
                    "metadata": deepcopy(self.rt_ref),
                    "spec": {"predefiendResultTableId": self.logical},
                    "status": {
                        "phase": "Ok",
                        "related": [
                            {
                                "kind": "ChannelBinding",
                                "metadata": {"tenant": "tenant_a", "namespace": "inputs", "name": "events_channel"},
                                "spec": {"data": self.rt_ref},
                                "status": {"phase": "Ok"},
                            }
                        ],
                    },
                }
            envelope = (
                {"result": False, "code": "1558025", "data": None}
                if value is None
                else {"result": True, "code": "00", "data": deepcopy(value)}
            )
        else:
            self.assertIn(method, ("POST", "PUT"))
            payload = deepcopy(kwargs["json"])
            self.writes.append((method, url, payload))
            kind = "Flow" if "/flows/" in url else "DataStorage"
            self.assertTrue(kind == "Flow" or "/datastorages/" in url, url)
            value = {"kind": kind, **payload, "status": {"phase": "Pending"}}
            if kind == "Flow":
                self.flow_resource = value
            else:
                value["metadata"].setdefault("annotations", {})["task_stopped"] = "false"
                self.storage_resource = value
            envelope = {"result": True, "code": "00", "data": deepcopy(value)}
        response = requests.Response()
        response.status_code = 200
        response.url = url
        response.request = requests.Request(method, url).prepare()
        response._content = json.dumps(envelope).encode()
        return response

    def assert_original_json_policy(self, fields):
        self.assertEqual(fields["json_fields"], [])
        self.assertEqual(fields["original_json_fields"], ["event_evidence", "event_data"])
        self.assertFalse(set(fields["json_fields"]) & set(fields["original_json_fields"]))

    def test_controller_create_and_update_preserve_all_dynamic_json_shapes_and_target(self):
        # 只证明JSON载荷所在SQL及存储声明在SDK边界未改写，不模拟Doris执行结果。
        values = [[{"a": [1, True, None]}, "text"], {"nested": {"a": [False, 2.5]}}, True, 17, 2.5, "text", None]
        for index, value in enumerate(values):
            raw_json = json.dumps(value, ensure_ascii=False)
            sql = f"SELECT '{raw_json}' AS event_data, '{raw_json}' AS event_evidence FROM {self.logical}"
            self.strategy.sql = sql
            self.strategy.save(update_record=False, update_fields=["sql"])
            if self.flow_resource:
                self.flow_resource["status"] = {"phase": "Ok"}
                self.flow_resource["metadata"]["annotations"]["task_stopped"] = "true"
                # 模拟此前保存的旧声明；只核新请求，不宣称存量VARIANT物理列已迁移。
                if index == 1:
                    old = self.flow_resource["spec"]["nodes"][-1]["storage_config"]
                    old.update(json_fields=["event_evidence", "event_data"], original_json_fields=[])
            with self.subTest(value=value):
                RuleAuditController(self.strategy.pk)._update_or_create_bkbase_flow()
                method, url, payload = self.writes[-1]
                self.assertEqual(method, "POST" if index == 0 else "PUT")
                self.assertIn("/flows/", url)
                nodes = payload["spec"]["nodes"]
                self.assertEqual(nodes[1]["config"]["sql"], sql)
                self.assertEqual(nodes[-1]["kind"], "DorisStorageNode")
                self.assertEqual(nodes[-1]["storage"], self.cluster)
                self.assert_original_json_policy(nodes[-1]["storage_config"])
                self.assertEqual(nodes[-1]["storage_config"]["db"], "audit_db")
                self.assertEqual(nodes[-1]["storage_config"]["table"], "events")
        self.assertEqual(len(self.writes), len(values))
        self.strategy.refresh_from_db()
        self.assertNotIn("pending_spec", self.strategy.backend_data["bkbase_v4"])

    def test_running_flow_persists_correct_json_policy_until_pending_graph_is_published(self):
        self.strategy.sql = f"SELECT event_data, event_evidence FROM {self.logical}"
        self.strategy.save(update_record=False, update_fields=["sql"])
        RuleAuditController(self.strategy.pk)._update_or_create_bkbase_flow()
        self.flow_resource["status"] = {"phase": "Ok"}
        self.flow_resource["metadata"]["annotations"]["task_stopped"] = "false"
        self.strategy.sql = f"SELECT event_data, event_evidence FROM {self.logical} WHERE strategy_id = 1"
        self.strategy.save(update_record=False, update_fields=["sql"])
        RuleAuditController(self.strategy.pk)._update_or_create_bkbase_flow()
        self.strategy.refresh_from_db()
        pending = self.strategy.backend_data["bkbase_v4"]["pending_spec"]
        self.assert_original_json_policy(pending["nodes"][-1]["storage_config"])
        self.assertEqual(self.writes[-1][2]["metadata"]["annotations"]["task_stopped"], "true")
        self.flow_resource["status"] = {"phase": "Ok"}
        flow.strategy_deploy_data(self.strategy)
        self.assert_original_json_policy(self.writes[-1][2]["spec"]["nodes"][-1]["storage_config"])
        self.assertEqual(self.writes[-1][2]["spec"]["nodes"][1]["config"]["sql"], self.strategy.sql)
        self.strategy.refresh_from_db()
        self.assertNotIn("pending_spec", self.strategy.backend_data["bkbase_v4"])

    def test_event_storage_create_save_reload_and_update_keep_original_json(self):
        handler = EventCollectorEtlHandler(plugin=self.owner)
        with mock.patch.object(handler, "get_bk_data_id", return_value=11), mock.patch.object(
            handler, "build_clean_config", return_value={}
        ), mock.patch.object(clean, "configure_clean", return_value={"task_state": TaskState.RUNNING}):
            handler.create_or_update()
            self.assertEqual(self.writes[-1][0], "POST")
            self.assert_original_json_policy(self.writes[-1][2]["spec"]["taskFieldSetting"])
            self.storage_resource["status"] = {"phase": "Ok"}
            handler.create_or_update()
            self.assertEqual(len(self.writes), 1)
            saved = deepcopy(self.configs[DORIS_EVENT_STORAGE_CONFIG_KEY])
            self.assert_original_json_policy(storage.convert_storage_config(saved)["taskFieldSetting"])
            self.owner.refresh_from_db()
            self.assertTrue(self.owner.has_storage)
            self.storage_resource["spec"]["maintainers"] = ["synthetic_operator"]
            with override_settings(EVENT_DORIS_EXPIRES=30):
                handler.create_or_update()
                self.assertEqual(self.writes[-1][0], "PUT")
                self.assert_original_json_policy(self.writes[-1][2]["spec"]["taskFieldSetting"])
                self.assertEqual(self.writes[-1][2]["spec"]["maintainers"], ["synthetic_operator"])
                self.storage_resource["status"] = {"phase": "Ok"}
                handler.create_or_update()
            self.assertEqual(len(self.writes), 2)
            rebuilt = handler.build_event_storage_config()
            self.assert_original_json_policy(storage.convert_storage_config(rebuilt)["taskFieldSetting"])
            self.assertEqual(rebuilt["physical_table_name"], "audit_db.events")
            self.assertEqual(saved["fields"], rebuilt["fields"])
