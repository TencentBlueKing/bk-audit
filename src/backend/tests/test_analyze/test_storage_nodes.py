import json
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.apps import apps as django_apps
from django.conf import settings
from django.test import TestCase

from apps.meta.utils.fields import BKDATA_ES_TYPE_MAP
from services.web.analyze.constants import (
    DEFAULT_HDFS_STORAGE_CLUSTER_KEY,
    DEFAULT_QUEUE_STORAGE_CLUSTER_KEY,
)
from services.web.analyze.controls.aiops import AIOpsController
from services.web.analyze.controls.rule_audit import RuleAuditController
from services.web.analyze.storage_node import DorisStorageNode, ESStorageNode
from services.web.databus.constants import (
    DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
    DEFAULT_RETENTION,
    DEFAULT_STORAGE_CONFIG_KEY,
    DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY,
)
from services.web.risk.constants import EventMappingFields
from services.web.strategy_v2.constants import StrategyType
from services.web.strategy_v2.models import Strategy

storage_migration = import_module("services.web.strategy_v2.migrations.0018_storage_node_ids_map")


def build_expected_doris_fields():
    fields = []
    for field in EventMappingFields().fields:
        field_type = BKDATA_ES_TYPE_MAP.get(field.field_type, field.field_type)
        fields.append(
            {
                "type": field_type,
                "config": "json" if field.is_json else "",
                "field": field.field_name,
                "alias": str(field.description or field.alias_name or field.field_name),
            }
        )
    return fields


EXPECTED_JSON_FIELDS = [
    EventMappingFields.EVENT_EVIDENCE.field_name,
    EventMappingFields.EVENT_DATA.field_name,
]


class DummyStrategy(SimpleNamespace):
    def save(self, *args, **kwargs):
        """Skip ORM persistence in unit tests."""
        return None


class RuleAuditStorageNodeTests(TestCase):
    def _mock_global_meta_get(self, config_key, *args, **kwargs):
        mapping = {
            DEFAULT_STORAGE_CONFIG_KEY: 100,
            DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY: {"bkbase_cluster_id": 300},
            DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY: "mapleleaf_5000448.bklog_event_test",
            DEFAULT_QUEUE_STORAGE_CLUSTER_KEY: "",
            DEFAULT_HDFS_STORAGE_CLUSTER_KEY: "",
        }
        return mapping.get(config_key, "")

    @patch("services.web.analyze.storage_node.EventHandler.get_table_id", return_value="5000448.bkaudit_event")
    @patch("services.web.analyze.storage_node.resource.databus.storage.storage_list")
    @patch("services.web.analyze.storage_node.GlobalMetaConfig.get")
    @patch("services.web.analyze.controls.rule_audit.api.bk_base.update_flow_node")
    @patch("services.web.analyze.controls.rule_audit.api.bk_base.create_flow_node")
    def test_append_missing_doris_node_on_update(
        self,
        mock_create_flow_node: MagicMock,
        mock_update_flow_node: MagicMock,
        mock_meta_get: MagicMock,
        mock_storage_list: MagicMock,
        _mock_table_id: MagicMock,
    ):
        mock_meta_get.side_effect = self._mock_global_meta_get
        mock_storage_list.return_value = [
            {"cluster_config": {"cluster_id": 100, "custom_option": {"bkbase_cluster_id": 200}}}
        ]
        mock_update_flow_node.return_value = {"node_id": 501}
        mock_create_flow_node.return_value = {"node_id": 601}

        controller = RuleAuditController.__new__(RuleAuditController)
        controller.strategy = DummyStrategy(
            namespace=settings.DEFAULT_NAMESPACE,
            backend_data={"storage_node_ids": {ESStorageNode.node_type: 501}, "raw_table_name": "rule_raw"},
        )
        controller.x_interval = 300
        controller.y_interval = 100
        controller.x = 0
        controller.y = 0
        controller.__dict__["rt_ids"] = ["2_existing_rt"]

        storage_ids = controller.create_or_update_storage_nodes(
            need_create=False,
            flow_id=10,
            sql_node_id=20,
        )

        mock_update_flow_node.assert_called()
        mock_create_flow_node.assert_called_once()
        create_call_kwargs = mock_create_flow_node.call_args.kwargs
        expected_doris_config = {
            "node_type": DorisStorageNode.node_type,
            "from_result_table_ids": ["2_rule_raw"],
            "bk_biz_id": 2,
            "result_table_id": "2_rule_raw",
            "name": f"{DorisStorageNode.node_type}_rule_raw",
            "expires": settings.EVENT_DORIS_EXPIRES,
            "cluster": 300,
            "indexed_fields": [],
            "has_replica": False,
            "has_unique_key": False,
            "storage_keys": [],
            "analyzed_fields": [],
            "doc_values_fields": [],
            "json_fields": EXPECTED_JSON_FIELDS,
            "physical_table_name": "mapleleaf_5000448.bklog_event_test",
            "original_json_fields": [],
            "udc_name": "doris",
            "storage_field_config": {},
            "custom_param_config": {
                "fields": build_expected_doris_fields(),
                "expires_dup": settings.EVENT_DORIS_EXPIRES,
                "expires_uniq": "-1",
                "data_model": "duplicate",
            },
        }
        self.assertEqual(create_call_kwargs["node_type"], DorisStorageNode.node_type)
        self.assertJSONEqual(
            json.dumps(create_call_kwargs["config"], ensure_ascii=False),
            json.dumps(expected_doris_config, ensure_ascii=False),
        )

        expected_backend_map = {
            ESStorageNode.node_type: 501,
            DorisStorageNode.node_type: 601,
        }
        self.assertEqual(controller.strategy.backend_data["storage_node_ids"], expected_backend_map)
        self.assertEqual(sorted(storage_ids), sorted(expected_backend_map.values()))

    @patch("services.web.analyze.storage_node.EventHandler.get_table_id", return_value="5000448.bkaudit_event")
    @patch("services.web.analyze.storage_node.resource.databus.storage.storage_list")
    @patch("services.web.analyze.storage_node.GlobalMetaConfig.get")
    @patch("services.web.analyze.controls.rule_audit.api.bk_base.update_flow_node")
    @patch("services.web.analyze.controls.rule_audit.api.bk_base.create_flow_node")
    def test_migration_converts_list_and_controller_updates(
        self,
        mock_create_flow_node: MagicMock,
        mock_update_flow_node: MagicMock,
        mock_meta_get: MagicMock,
        mock_storage_list: MagicMock,
        _mock_table_id: MagicMock,
    ):
        mock_meta_get.side_effect = self._mock_global_meta_get
        mock_storage_list.return_value = [
            {"cluster_config": {"cluster_id": 100, "custom_option": {"bkbase_cluster_id": 200}}}
        ]
        mock_update_flow_node.return_value = {"node_id": 501}
        mock_create_flow_node.return_value = {"node_id": 601}

        strategy = Strategy.objects.create(
            namespace=settings.DEFAULT_NAMESPACE,
            strategy_name="legacy",
            control_id="",
            strategy_type=StrategyType.RULE.value,
            configs={},
            backend_data={"storage_node_ids": [501], "raw_table_name": "rule_raw"},
        )

        storage_migration.list_to_map(django_apps, None)
        strategy.refresh_from_db()
        self.assertEqual(strategy.backend_data["storage_node_ids"], {ESStorageNode.node_type: 501})

        controller = RuleAuditController.__new__(RuleAuditController)
        controller.strategy = strategy
        controller.x_interval = 300
        controller.y_interval = 100
        controller.x = 0
        controller.y = 0
        controller.__dict__["rt_ids"] = ["2_existing_rt"]

        storage_ids = controller.create_or_update_storage_nodes(
            need_create=False,
            flow_id=10,
            sql_node_id=20,
        )

        mock_update_flow_node.assert_called()
        mock_create_flow_node.assert_called_once()
        self.assertEqual(
            strategy.backend_data["storage_node_ids"],
            {
                ESStorageNode.node_type: 501,
                DorisStorageNode.node_type: 601,
            },
        )
        self.assertEqual(sorted(storage_ids), [501, 601])


class AiopsStorageNodeTests(TestCase):
    def _mock_global_meta_get(self, config_key, *args, **kwargs):
        mapping = {
            DEFAULT_STORAGE_CONFIG_KEY: 100,
            DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY: {"bkbase_cluster_id": 300},
            DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY: "mapleleaf_5000448.bklog_event_test",
        }
        return mapping.get(config_key, "")

    @patch("services.web.analyze.storage_node.EventHandler.get_table_id", return_value="5000448.bkaudit_event")
    @patch("services.web.analyze.storage_node.resource.databus.storage.storage_list")
    @patch("services.web.analyze.storage_node.GlobalMetaConfig.get")
    def test_aiops_build_storage_nodes(self, mock_meta_get: MagicMock, mock_storage_list: MagicMock, _mock_table_id):
        mock_meta_get.side_effect = self._mock_global_meta_get
        mock_storage_list.return_value = [
            {"cluster_config": {"cluster_id": 100, "custom_option": {"bkbase_cluster_id": 200}}}
        ]

        controller = AIOpsController.__new__(AIOpsController)
        controller.strategy = DummyStrategy(
            namespace=settings.DEFAULT_NAMESPACE,
            backend_data={},
        )

        nodes = controller._build_storage_nodes(bk_biz_id=2, raw_table_name="aiops_rt")

        expected_nodes = [
            {
                "node_type": ESStorageNode.node_type,
                "name": "es_storage_aiops_rt",
                "result_table_id": "2_scenario_aiops_rt",
                "bk_biz_id": 2,
                "indexed_fields": [],
                "cluster": 200,
                "expires": DEFAULT_RETENTION,
                "has_replica": False,
                "has_unique_key": False,
                "storage_keys": [],
                "analyzed_fields": [],
                "doc_values_fields": [],
                "json_fields": [],
                "from_result_table_ids": ["2_scenario_aiops_rt"],
                "physical_table_name": "write_{yyyyMMdd}_5000448_bkaudit_event",
            },
            {
                "node_type": DorisStorageNode.node_type,
                "from_result_table_ids": ["2_scenario_aiops_rt"],
                "bk_biz_id": 2,
                "result_table_id": "2_scenario_aiops_rt",
                "name": f"{DorisStorageNode.node_type}_scenario_aiops_rt",
                "expires": settings.EVENT_DORIS_EXPIRES,
                "cluster": 300,
                "indexed_fields": [],
                "has_replica": False,
                "has_unique_key": False,
                "storage_keys": [],
                "analyzed_fields": [],
                "doc_values_fields": [],
                "json_fields": EXPECTED_JSON_FIELDS,
                "physical_table_name": "mapleleaf_5000448.bklog_event_test",
                "original_json_fields": [],
                "udc_name": "doris",
                "storage_field_config": {},
                "custom_param_config": {
                    "fields": build_expected_doris_fields(),
                    "expires_dup": settings.EVENT_DORIS_EXPIRES,
                    "expires_uniq": "-1",
                    "data_model": "duplicate",
                },
            },
        ]

        self.assertJSONEqual(
            json.dumps(nodes, ensure_ascii=False),
            json.dumps(expected_nodes, ensure_ascii=False),
        )
