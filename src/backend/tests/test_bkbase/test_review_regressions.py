"""最终独立审查发现的生命周期、业务消费与协议映射回归。"""
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase, override_settings

from services.web.bkbase import clean, flow, source, storage
from services.web.bkbase.common import operation_result
from services.web.databus.collector.etl.etl_config_handler.bk_base_json import (
    BkBaseJsonConfig,
)
from services.web.databus.collector.resources import (
    GetDataIdDetail,
    GetSystemDataIdList,
)
from services.web.databus.collector.serializers import GetCollectorsResponseSerializer
from services.web.databus.constants import SourcePlatformChoices
from services.web.databus.models import CollectorConfig, CollectorPlugin
from services.web.strategy_v2.models import Strategy


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit")
class ReviewRegressionTests(TestCase):
    def setUp(self):
        transport = mock.patch(
            "requests.sessions.Session.request", side_effect=AssertionError("Unexpected unmocked HTTP request")
        )
        transport.start()
        self.addCleanup(transport.stop)
        self.context = {"version": "v4", "tenant": "tenant_a", "namespace": "audit"}
        self.ref = {"kind": "Clean", "tenant": "tenant_a", "namespace": "existing", "name": "clean_a"}

    def test_wait_stopped_does_not_finish_using_old_running_graph(self):
        strategy = Strategy.objects.create(
            namespace="audit",
            strategy_name="rule",
            backend_data={
                "bkbase_v4": {
                    "operation": "wait_stopped",
                    "requested_action": "start",
                    "pending_spec": {"nodes": [{"name": "changed"}]},
                }
            },
        )
        with mock.patch("services.web.bkbase.flow.advance_rule_flow", return_value={"task_state": "running"}):
            self.assertEqual(flow.strategy_deploy_data(strategy)["status"], "other")

    def test_pending_old_actual_state_does_not_mean_current_config_ready(self):
        for kind in ("Clean", "DataSource", "DataStorage"):
            for phase in ("Pending", "Reconciling", "Terminating"):
                with self.subTest(kind=kind, phase=phase):
                    resource = {"spec": {"current_status": "Running"}, "status": {"phase": phase, "message": "running"}}
                    self.assertIsNone(operation_result(resource, {**self.ref, "kind": kind}, "update")["task_state"])

    def test_real_json_builder_preserves_whole_object_assignment(self):
        builder = SimpleNamespace(
            uniq_label_id=lambda: "label", build_custom_field_config=lambda: [], assign_other_fields=[], time_conf={}
        )
        original = BkBaseJsonConfig.build_config(builder, {"next": {"next": []}})
        rules = clean.convert_rules(original)
        self.assertEqual(next(r for r in rules if r["output_id"] == "log")["operator"]["key_index"], "")

    def make_collector(self):
        return CollectorConfig.objects.create(
            system_id="system_a",
            bk_biz_id=1,
            collector_plugin_id=1,
            collector_config_id=1,
            collector_config_name="source",
            source_platform=SourcePlatformChoices.BKBASE,
            bkbase_v4_resources={
                "clean_ready": True,
                "result_table": {**self.ref, "kind": "ResultTable", "name": "1_logs"},
            },
        )

    def test_ready_source_response_exposes_active_rt_without_overwriting_old_id(self):
        owner = self.make_collector()
        response = GetSystemDataIdList().request({"system_id": owner.system_id})
        self.assertEqual(response[0]["bkbase_table_id"], "1_logs")
        self.assertEqual(GetCollectorsResponseSerializer(owner).data["bkbase_table_id"], "1_logs")
        owner.refresh_from_db()
        self.assertIsNone(owner.bkbase_table_id)
        self.assertNotIn("bkbase_v4_resources", response[0])

    def test_storage_keeps_key_and_chinese_analyzer_from_existing_config(self):
        params = {"fields": [{"field_name": "id", "is_key": True}, {"field_name": "log", "is_zh_analyzed": True}]}
        result = storage.convert_storage_config(params)
        self.assertEqual(result["taskFieldSetting"], {"key_fields": ["id"], "zh_analyzed_fields": ["log"]})

    def test_storage_create_route_uses_actual_target_namespace(self):
        owner = CollectorPlugin.objects.create(
            namespace="audit",
            collector_plugin_id=1,
            collector_plugin_name="plugin",
            bkdata_biz_id=1,
            table_id=1,
            index_set_id=1,
        )
        rt = {**self.ref, "kind": "ResultTable", "name": "rt_a"}
        cluster = {**self.ref, "kind": "Doris", "namespace": "resources", "name": "doris_a"}
        with mock.patch("services.web.bkbase.storage.resource_lock"), mock.patch(
            "services.web.bkbase.storage.get_resource_or_none", return_value=None
        ), mock.patch(
            "services.web.bkbase.storage.api.bk_base_v4.data_storage_create",
            side_effect=lambda **kw: {"metadata": kw["metadata"], "spec": kw["spec"], "status": {"phase": "Pending"}},
        ) as create:
            storage.ensure_storage(self.context, owner, rt_ref=rt, cluster_ref=cluster, purpose="main", config={})
            self.assertEqual(create.call_args.kwargs["namespace"], "existing")
            self.assertEqual(create.call_args.kwargs["metadata"]["namespace"], "existing")

    def test_detail_allows_v4_missing_optional_audit_timestamps(self):
        source = {"id": 11, "bk_biz_id": 1, "raw_data_name": "source", "raw_data_alias": "source", "description": ""}
        with mock.patch(
            "services.web.databus.collector.resources.bkbase_source.get_rawdata_detail", return_value=source
        ), mock.patch("services.web.databus.collector.resources.CollectorConfig.objects.filter") as filter_, mock.patch(
            "services.web.databus.collector.resources.get_saas_url", return_value="https://audit.example"
        ):
            filter_.return_value.first.return_value = None
            result = GetDataIdDetail().request({"bk_data_id": 11})
            self.assertIsNone(result["created_at"])

    def test_synced_source_persists_actual_distinct_dataid_reference(self):
        owner = self.make_collector()
        synced = {
            "kind": "DataSource",
            "metadata": {
                "tenant": "tenant_a",
                "namespace": "audit",
                "name": "source_a",
                "labels": {"raw_data_id": "11"},
            },
            "spec": {"data_id": {"namespace": "raw_project", "name": "actual_dataid"}},
        }
        with mock.patch("services.web.bkbase.source.api.bk_base_v4.data_source_list", return_value=[synced]):
            source.resolve_synced_source(self.context, owner, raw_data_id=11)
        owner.refresh_from_db()
        self.assertEqual(owner.bkbase_v4_resources["data_source"]["name"], "source_a")
        self.assertEqual(owner.bkbase_v4_resources["data_id"]["name"], "actual_dataid")
        self.assertEqual(owner.bkbase_v4_resources["data_id"]["namespace"], "raw_project")

    def test_shared_storage_is_created_once_across_owners_and_replica_is_independent(self):
        first = self.make_collector()
        second = CollectorConfig.objects.create(
            system_id="system_a",
            bk_biz_id=1,
            collector_plugin_id=1,
            collector_config_id=2,
            collector_config_name="second",
        )
        rt = {**self.ref, "kind": "ResultTable", "name": "rt_a"}
        cluster = {**self.ref, "kind": "Doris", "namespace": "resources", "name": "doris_a"}
        resources = {}

        def create(**kw):
            resource = {"metadata": kw["metadata"], "spec": kw["spec"], "status": {"phase": "Pending"}}
            resources[kw["metadata"]["name"]] = resource
            return resource

        with mock.patch("services.web.bkbase.storage.resource_lock"), mock.patch(
            "services.web.bkbase.storage.get_resource_or_none", side_effect=lambda *a, **kw: resources.get(kw["name"])
        ), mock.patch(
            "services.web.bkbase.storage.api.bk_base_v4.data_storage_create", side_effect=create
        ) as post, mock.patch(
            "services.web.bkbase.storage.api.bk_base_v4.data_storage_update"
        ) as put:
            storage.ensure_storage(self.context, first, rt_ref=rt, cluster_ref=cluster, purpose="main", config={})
            storage.ensure_storage(self.context, second, rt_ref=rt, cluster_ref=cluster, purpose="main", config={})
            self.assertEqual(post.call_count, 1)
            put.assert_not_called()
            storage.ensure_storage(
                self.context, first, rt_ref=rt, cluster_ref={**cluster, "name": "replica"}, purpose="replica", config={}
            )
            self.assertEqual(post.call_count, 2)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.bkbase_v4_resources["storages"]["main"], second.bkbase_v4_resources["storages"]["main"])
        self.assertNotEqual(
            first.bkbase_v4_resources["storages"]["main"], first.bkbase_v4_resources["storages"]["replica"]
        )
