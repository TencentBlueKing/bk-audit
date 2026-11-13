"""验证 DataStorage 与 Flow 使用相同物理目标，缺省维护不切换存量目标。"""

from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from services.web.bkbase import flow, storage
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.models import CollectorPlugin
from tests.test_bkbase import test_flow_graph_migration as graph_fixture


def ref(kind, name):
    return {"kind": kind, "tenant": "tenant_a", "namespace": "audit", "name": name}


class PhysicalStorageConversionTests(SimpleTestCase):
    def test_existing_flow_destination_conflicts_fail_before_a_rebuild_can_retarget_it(self):
        for node_type, kind, cluster_kind, previous, requested in (
            (
                "doris",
                "DorisStorageNode",
                "Doris",
                {"storage_config": {"db": "old_db", "table": "events"}},
                "new_db.events",
            ),
            (
                "elastic_storage",
                "EsStorageNode",
                "ElasticSearch",
                {"write_alias": {"Fixed": "old_events"}},
                "new_events",
            ),
        ):
            cluster = ref(cluster_kind, "cluster")
            with self.subTest(kind=kind), mock.patch.object(storage, "resolve_storage_cluster", return_value=cluster):
                with self.assertRaises(BKBaseResourceMappingError):
                    flow._storage_node(
                        {"tenant": "tenant_a", "namespace": "audit"},
                        SimpleNamespace(namespace="audit", strategy_id=7),
                        {
                            "node_type": node_type,
                            "cluster": "legacy",
                            "expires": "7d",
                            "physical_table_name": requested,
                        },
                        {},
                        existing_nodes=[{"kind": kind, "name": "existing", "storage": cluster, **previous}],
                    )

    def test_locked_merge_checks_latest_target_but_omitted_targets_keep_latest_values(self):
        old, desired = graph_fixture.WholeFlowGraphTests().graph()
        desired["nodes"][2]["storage_config"].update(db="actual_db", table="actual_table")
        flow._merged_spec(old, desired, preserve_storage_targets=True)
        old["nodes"][2]["storage_config"]["db"] = "changed_after_build"
        with self.assertRaises(BKBaseResourceMappingError):
            flow._merged_spec(old, desired, preserve_storage_targets=True)
        desired["nodes"][2]["storage_config"].pop("db")
        result = flow._merged_spec(old, desired, preserve_storage_targets=True)
        self.assertEqual(result["nodes"][2]["storage_config"]["db"], "changed_after_build")

    def test_existing_equivalent_es_template_does_not_block_rebuild(self):
        cluster = ref("ElasticSearch", "es")
        current = {
            "kind": "EsStorageNode",
            "name": "saved",
            "storage": cluster,
            "write_alias": {"TimeBased": {"format": "write_{yyyyMMdd}_events", "timezone": 0}},
        }
        with mock.patch.object(storage, "resolve_storage_cluster", return_value=cluster):
            result = flow._storage_node(
                {"tenant": "tenant_a", "namespace": "audit"},
                SimpleNamespace(namespace="audit", strategy_id=7),
                {
                    "node_type": "elastic_storage",
                    "cluster": "legacy",
                    "expires": "7d",
                    "physical_table_name": "write_%Y%m%d_events",
                },
                {},
                existing_nodes=[current],
            )
        self.assertEqual(result["write_alias"], {"TimeBased": {"format": "write_%Y%m%d_events", "timezone": 0}})

    def test_explicit_targets_survive_conversion_without_inventing_timezone(self):
        for kind, supplied, expected in (
            ("doris", "event_db.events", "event_db.events"),
            ("es", "write_{yyyyMMdd}_events", "write_%Y%m%d_events"),
            ("es", "write_%Y%m%d_events", "write_%Y%m%d_events"),
            ("es", "fixed_events", "fixed_events"),
        ):
            with self.subTest(kind=kind, supplied=supplied):
                params = {"storage_type": kind, "physical_table_name": supplied}
                actual = storage.convert_storage_config(params)["tableInfo"]
                self.assertEqual(actual, {"physical_table_name": expected})
                self.assertEqual(params["physical_table_name"], supplied)

    def test_absent_target_stays_absent_for_platform_allocated_storages(self):
        for kind in ("doris", "es", "redis", "hdfs"):
            with self.subTest(kind=kind):
                self.assertNotIn(
                    "physical_table_name", storage.convert_storage_config({"storage_type": kind})["tableInfo"]
                )

    def test_flow_uses_same_qualified_doris_target_without_a_default_database(self):
        with mock.patch.object(storage, "resolve_storage_cluster", return_value=ref("Doris", "doris")):
            result = flow._storage_node(
                {"tenant": "tenant_a", "namespace": "audit"},
                SimpleNamespace(namespace="audit", strategy_id=7),
                {"node_type": "doris", "cluster": "legacy", "expires": "7d", "physical_table_name": "event_db.events"},
                {"doris_databases": {"doris": "unused_default"}},
            )
        self.assertEqual(result["storage_config"]["db"], "event_db")
        self.assertEqual(result["storage_config"]["table"], "events")

    def test_flow_es_old_and_new_templates_are_time_based_and_literals_are_fixed(self):
        for table, alias in (
            ("write_{yyyyMMdd}_events", {"TimeBased": {"format": "write_%Y%m%d_events", "timezone": 0}}),
            ("write_%Y%m%d_events", {"TimeBased": {"format": "write_%Y%m%d_events", "timezone": 0}}),
            ("fixed_events", {"Fixed": "fixed_events"}),
        ):
            with self.subTest(table=table), mock.patch.object(
                storage, "resolve_storage_cluster", return_value=ref("ElasticSearch", "es")
            ):
                result = flow._storage_node(
                    {"tenant": "tenant_a", "namespace": "audit"},
                    SimpleNamespace(namespace="audit", strategy_id=7),
                    {
                        "node_type": "elastic_storage",
                        "cluster": "legacy",
                        "expires": "7d",
                        "physical_table_name": table,
                    },
                    {},
                )
                self.assertEqual(result["write_alias"], alias)

    def test_omitted_flow_target_does_not_apply_profile_database_over_existing_target(self):
        cluster = ref("Doris", "doris")
        current = {
            "kind": "DorisStorageNode",
            "name": "old",
            "storage": cluster,
            "storage_config": {"db": "saved_db", "table": "saved_table"},
        }
        with mock.patch.object(storage, "resolve_storage_cluster", return_value=cluster):
            result = flow._storage_node(
                {"tenant": "tenant_a", "namespace": "audit"},
                SimpleNamespace(namespace="audit", strategy_id=7),
                {"node_type": "doris", "cluster": "legacy", "expires": "7d"},
                {"doris_databases": {"doris": "new_default"}},
                existing_nodes=[current],
            )
        self.assertNotIn("db", result["storage_config"])
        self.assertNotIn("table", result["storage_config"])


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit")
class PhysicalStoragePersistenceTests(TestCase):
    def setUp(self):
        self.rt = ref("ResultTable", "input")
        self.cluster = ref("Doris", "doris")
        self.owner = CollectorPlugin.objects.create(
            namespace="audit",
            collector_plugin_id=1,
            collector_plugin_name="synthetic",
            bkdata_biz_id=1,
            table_id=1,
            index_set_id=1,
            bkbase_v4_resources={"result_table": self.rt},
        )
        self.enterContext(mock.patch.object(storage, "resource_lock"))
        self.enterContext(mock.patch.object(storage, "resolve_storage_cluster", return_value=self.cluster))

    def configure(self, **params):
        return storage.configure_storage(self.owner, {"storage_type": "doris", "storage_cluster": "legacy", **params})

    def remote(self, physical=None):
        table = {"source": self.rt, "storage": self.cluster}
        if physical:
            table["physical_table_name"] = physical
        return {"metadata": {"name": "storage"}, "spec": {"tableInfo": table}, "status": {"phase": "Ok"}}

    def test_create_and_update_preserve_the_explicit_target(self):
        for old in (None, self.remote("event_db.events")):
            with self.subTest(old=old), mock.patch.object(
                storage, "get_resource_or_none", return_value=old
            ), mock.patch.object(
                storage.api.bk_base_v4,
                "data_storage_create",
                side_effect=lambda **kw: {**kw, "status": {"phase": "Pending"}},
            ) as post, mock.patch.object(
                storage.api.bk_base_v4,
                "data_storage_update",
                side_effect=lambda **kw: {**kw, "status": {"phase": "Pending"}},
            ) as put:
                # 每个分支从独立的未绑定状态覆盖 POST 或 PUT。
                self.owner.bkbase_v4_resources = {"result_table": self.rt}
                self.owner.save(update_fields=["bkbase_v4_resources"])
                result = self.configure(physical_table_name="event_db.events", expires=14)
                request = (put if old else post).call_args.kwargs
                self.assertEqual(request["spec"]["tableInfo"]["physical_table_name"], "event_db.events")
                self.assertEqual(result["physical_table_name"], "event_db.events")
                self.owner.refresh_from_db()
                self.assertEqual(self.owner.bkbase_v4_resources["physical_targets"]["main"], "event_db.events")

    def test_existing_formal_target_is_reused_when_update_omits_it(self):
        old = self.remote("existing_db.existing_table")
        with mock.patch.object(storage, "get_resource_or_none", return_value=old), mock.patch.object(
            storage.api.bk_base_v4,
            "data_storage_update",
            side_effect=lambda **kw: {**kw, "status": {"phase": "Pending"}},
        ) as put:
            result = self.configure(expires=14)
        self.assertEqual(put.call_args.kwargs["spec"]["tableInfo"]["physical_table_name"], "existing_db.existing_table")
        self.assertEqual(result["physical_table_name"], "existing_db.existing_table")

    def test_explicit_migration_target_is_used_even_if_remote_does_not_repeat_it(self):
        self.owner.bkbase_v4_resources["physical_targets"] = {"main": "migrated_db.events"}
        self.owner.save(update_fields=["bkbase_v4_resources"])
        with mock.patch.object(storage, "get_resource_or_none", return_value=self.remote()), mock.patch.object(
            storage.api.bk_base_v4,
            "data_storage_update",
            side_effect=lambda **kw: {**kw, "status": {"phase": "Pending"}},
        ) as put:
            self.configure(expires=14)
        self.assertEqual(put.call_args.kwargs["spec"]["tableInfo"]["physical_table_name"], "migrated_db.events")

    def test_platform_allocated_destination_can_still_be_created_and_maintained(self):
        for old in (None, self.remote()):
            with self.subTest(old=old), mock.patch.object(
                storage, "get_resource_or_none", return_value=old
            ), mock.patch.object(
                storage.api.bk_base_v4,
                "data_storage_create",
                side_effect=lambda **kw: {**kw, "status": {"phase": "Pending"}},
            ) as post, mock.patch.object(
                storage.api.bk_base_v4,
                "data_storage_update",
                side_effect=lambda **kw: {**kw, "status": {"phase": "Pending"}},
            ) as put:
                self.owner.bkbase_v4_resources = {"result_table": self.rt}
                self.owner.save(update_fields=["bkbase_v4_resources"])
                self.configure(expires=14)
                request = (put if old else post).call_args.kwargs
                self.assertNotIn("physical_table_name", request["spec"]["tableInfo"])

    def test_conflicting_saved_destination_fails_before_writing(self):
        self.owner.bkbase_v4_resources["physical_targets"] = {"main": "saved_db.events"}
        self.owner.save(update_fields=["bkbase_v4_resources"])
        with mock.patch.object(
            storage, "get_resource_or_none", return_value=self.remote("different_db.events")
        ), mock.patch.object(storage.api.bk_base_v4, "data_storage_update") as put, self.assertRaises(
            BKBaseResourceMappingError
        ):
            self.configure(expires=14)
        put.assert_not_called()

    def test_two_sources_keep_distinct_resource_identities_and_share_one_explicit_target(self):
        other = CollectorPlugin.objects.create(
            namespace="audit",
            collector_plugin_id=2,
            collector_plugin_name="other synthetic",
            bkdata_biz_id=1,
            table_id=2,
            index_set_id=2,
            bkbase_v4_resources={"result_table": ref("ResultTable", "other_input")},
        )
        with mock.patch.object(storage, "get_resource_or_none", return_value=None), mock.patch.object(
            storage.api.bk_base_v4,
            "data_storage_create",
            side_effect=lambda **kw: {**kw, "status": {"phase": "Pending"}},
        ) as post:
            for owner in (self.owner, other):
                storage.configure_storage(
                    owner,
                    {"storage_type": "doris", "storage_cluster": "legacy", "physical_table_name": "shared_db.events"},
                )
        specs = [call.kwargs["spec"] for call in post.call_args_list]
        self.assertEqual([spec["tableInfo"]["physical_table_name"] for spec in specs], ["shared_db.events"] * 2)
        self.assertNotEqual(specs[0]["tableInfo"]["source"], specs[1]["tableInfo"]["source"])
        self.assertNotEqual(self.owner.bkbase_v4_resources["storages"], other.bkbase_v4_resources["storages"])

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_keeps_original_parameters_and_has_no_v4_side_effects(self):
        params = {"storage_type": "es", "physical_table_name": "write_{yyyyMMdd}_events"}
        with mock.patch.object(storage.api.bk_base, "databus_storages_post") as post:
            storage.configure_storage(self.owner, params)
        post.assert_called_once_with(**params)
