"""发布迁移的跨业务输出和既有ES切日配置边界，不连接数据库。"""
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from services.web.bkbase import flow, flow_migration
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.strategy_v2.constants import (
    RuleAuditConfigType,
    StrategyStatusChoices,
    StrategyType,
)


class ReleaseFlowMigrationTests(SimpleTestCase):
    def setUp(self):
        self.context = {"tenant": "tenant_a", "namespace": "audit"}
        self.ref = {"kind": "Flow", **self.context, "name": "migrated"}
        self.strategy = SimpleNamespace(
            pk=7,
            namespace="audit",
            is_deleted=False,
            strategy_type=StrategyType.RULE,
            status=StrategyStatusChoices.DISABLED,
            configs={
                "config_type": RuleAuditConfigType.LINK_TABLE,
                "data_source": {"link_table": {"uid": "join", "version": 1}},
            },
            backend_data={"flow_id": 41, "raw_table_name": "existing_output"},
        )
        self.nodes = [
            {"kind": "StreamSourceNode", "name": "logs"},
            {"kind": "StreamSourceNode", "name": "asset"},
            {"kind": "StreamNode", "name": "sql", "inputs": ["logs", "asset"], "output": "2_existing_output"},
        ]
        self.enterContext(
            mock.patch.object(
                flow_migration.LinkTable.objects, "get", return_value=SimpleNamespace(rt_ids=["47_logs", "2_asset"])
            )
        )
        self.enterContext(mock.patch.object(flow_migration.Strategy.objects, "get", return_value=self.strategy))
        self.enterContext(mock.patch.object(flow_migration, "_reject_aliases"))
        self.read = self.enterContext(mock.patch.object(flow, "read_flow_nodes", return_value=self.nodes))

    def test_detailed_cross_business_mapping_uses_explicit_output_and_formal_graph(self):
        row = {
            "strategy_id": 7,
            "audit_namespace": "audit",
            "legacy_flow_id": 41,
            "flow": self.ref,
            "output_rt_id": "2_existing_output",
        }
        result = flow_migration.preview_mapping(self.context, row)
        self.assertEqual(result["after_backend_data"]["bkbase_v4"]["output_rt_id"], "2_existing_output")
        self.assertEqual(self.strategy.backend_data, result["before_backend_data"])
        row["output_rt_id"] = "3_existing_output"
        with self.assertRaises(ValueError):
            flow_migration.preview_mapping(self.context, row)

    def test_minimal_cross_business_mapping_resolves_unique_formal_sql_output(self):
        with mock.patch.object(flow_migration.Strategy.objects, "get_queryset") as manager:
            manager.return_value.filter.return_value = [self.strategy]
            rows = flow_migration.resolve_mappings(self.context, [{"legacy_flow_id": 41, "flow_name": "migrated"}])
        self.assertEqual(rows[0]["output_rt_id"], "2_existing_output")
        self.read.assert_called_once_with(self.context, self.ref)

    def test_controller_uses_saved_output_business_instead_of_first_input(self):
        self.strategy.strategy_id = 7
        self.strategy.sql = "SELECT * FROM input"
        self.strategy.backend_data["bkbase_v4"] = {
            "flow": self.ref,
            "output_name": "existing_output",
            "output_rt_id": "2_existing_output",
        }
        controller = SimpleNamespace(
            strategy=self.strategy,
            rt_ids=["47_logs", "2_asset"],
            storage_nodes=[],
            check_source_type=lambda rt: flow.FlowDataSourceNodeType.REALTIME,
            _build_sql_node_config=lambda biz: {"node_type": "realtime"},
        )
        with mock.patch.object(flow, "_controller_flow_spec", return_value={"nodes": self.nodes}), mock.patch.object(
            flow, "_input_result_table_refs", return_value={"47_logs": {}, "2_asset": {}}
        ), mock.patch.object(
            flow.metadata_service, "get_result_tables", return_value=[{"bk_biz_id": 47}, {"bk_biz_id": 2}]
        ), mock.patch.object(
            flow.GlobalMetaConfig, "get", return_value={"operation_config": {}}
        ), mock.patch.object(
            flow, "_save_operation_binding"
        ), mock.patch.object(
            flow, "build_rule_flow", side_effect=lambda strategy, **kwargs: kwargs["binding_map"]
        ):
            spec = flow.build_controller_spec(controller, context=self.context)
        self.assertEqual(spec["output"], "2_existing_output")

    def test_ordinary_edit_preserves_existing_es_timezone_and_template(self):
        ref = {"kind": "ElasticSearch", **self.context, "name": "es"}
        source = {"kind": "StreamNode", "name": "sql", "inputs": [], "output": "2_existing_output"}
        old = {
            "nodes": [
                source,
                {
                    "kind": "EsStorageNode",
                    "name": "es",
                    "input": "sql",
                    "storage": ref,
                    "write_alias": {"TimeBased": {"format": "write_{yyyyMMdd}_old", "timezone": 8}},
                    "expires": "7d",
                },
            ]
        }
        desired = deepcopy(old)
        desired["nodes"][1].update(
            write_alias={"TimeBased": {"format": "write_%Y%m%d_old", "timezone": 0}}, expires="14d"
        )
        result = flow._merged_spec(old, desired, preserve_storage_targets=True)
        self.assertEqual(result["nodes"][1]["write_alias"], old["nodes"][1]["write_alias"])
        self.assertEqual(result["nodes"][1]["expires"], "14d")
        desired["nodes"][1]["write_alias"]["TimeBased"]["format"] = "different_%Y%m%d"
        with self.assertRaises(BKBaseResourceMappingError):
            flow._merged_spec(old, desired, preserve_storage_targets=True)
