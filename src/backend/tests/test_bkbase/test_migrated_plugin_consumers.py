"""显式迁移绑定通过真实插件 Handler 和 Service 消费。"""
from types import SimpleNamespace
from unittest import mock

from bk_resource.exceptions import APIRequestError
from django.test import SimpleTestCase, override_settings

from services.web.bkbase import clean, metadata, source, storage
from services.web.bkbase.constants import CleanRole
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.collector_plugin.handlers import PluginEtlHandler
from services.web.databus.constants import (
    DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
    DEFAULT_STORAGE_CONFIG_KEY,
    PluginSceneChoices,
)


def ref(kind, name, namespace):
    return {"kind": kind, "tenant": "tenant_a", "namespace": namespace, "name": name}


@override_settings(
    BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="current_project", DEFAULT_BK_BIZ_ID=47
)
class MigratedPluginConsumerTests(SimpleTestCase):
    def setUp(self):
        self.logical_id = "17_legacy_plugin_table"
        self.source_ref = ref("DataSource", "actual-source", "legacy_sources")
        self.data_ref = ref("DataId", "actual-data", "legacy_sources")
        self.clean_ref = ref("Clean", "actual-clean", "legacy_tables")
        self.rt_ref = ref("ResultTable", "actual-rt", "legacy_tables")
        self.storage_ref = ref("DataStorage", "actual-storage", "legacy_tables")
        self.cluster_ref = ref("ElasticSearch", "es_target", "clusters")
        self.plugin = SimpleNamespace(
            pk=1,
            namespace="audit",
            plugin_scene=PluginSceneChoices.COLLECTOR,
            collector_plugin_name_en="current_name",
            processing_id="legacy-processing",
            bkbase_table_id=self.logical_id,
            has_storage=True,
            has_replica_storage=False,
            bkbase_v4_resources={
                "data_source": self.source_ref,
                "data_id": self.data_ref,
                "source_raw_data_id": 73,
                "clean": self.clean_ref,
                "clean_role": CleanRole.OWNER,
                "result_table_id": self.logical_id,
                "result_table": self.rt_ref,
                "storages": {"main": self.storage_ref},
            },
            save=mock.Mock(),
        )
        self.handler = PluginEtlHandler(plugin=self.plugin)
        self.sdk = mock.Mock()
        api = SimpleNamespace(bk_base_v4=self.sdk)
        for module in (source, clean, metadata, storage):
            self.enterContext(mock.patch.object(module, "api", new=api))
        self.sdk.data_source_get.return_value = {
            "kind": "DataSource",
            "metadata": {
                **{key: self.source_ref[key] for key in ("tenant", "namespace", "name")},
                "labels": {"raw_data_id": "73"},
            },
            "spec": {"data_id": self.data_ref},
            "status": {"phase": "Ok"},
        }
        self.sdk.result_table_info.return_value = {
            "metadata": {key: self.rt_ref[key] for key in ("tenant", "namespace", "name")},
            "spec": {"predefiendResultTableId": self.logical_id},
        }
        self.enterContext(mock.patch.object(clean, "resource_lock"))
        self.enterContext(mock.patch.object(storage, "resource_lock"))

        def bind(owner, patch, *, remove=()):
            owner.bkbase_v4_resources.update(patch)
            for key in remove:
                owner.bkbase_v4_resources.pop(key, None)

        self.enterContext(mock.patch.object(clean, "update_owner_binding", side_effect=bind))
        self.enterContext(mock.patch.object(storage, "update_owner_binding", side_effect=bind))
        self.enterContext(mock.patch.object(storage, "resolve_storage_cluster", return_value=self.cluster_ref))

    def test_explicit_cross_project_source_is_used_without_name_discovery(self):
        self.assertEqual(self.handler.get_bk_data_id(), 73)
        self.sdk.data_source_get.assert_called_once_with(
            tenant="tenant_a", namespace="legacy_sources", name="actual-source"
        )
        self.sdk.data_source_list.assert_not_called()
        self.assertEqual(self.plugin.processing_id, "legacy-processing")
        self.sdk.data_source_get.return_value["spec"]["data_id"] = ref("DataId", "other", "legacy_sources")
        with self.assertRaises(BKBaseResourceMappingError):
            self.handler.get_bk_data_id()

    def test_explicit_configuration_can_update_an_imported_clean_using_its_existing_identity(self):
        self.plugin.bkbase_v4_resources["migration_import"] = {"owner": "plugin", "owner_pk": 1}
        with mock.patch.object(self.handler, "get_bk_data_id", return_value=73):
            params = self.handler.build_clean_config()
        spec = clean.build_clean_spec(params, data_ref=self.data_ref, logical_id=self.logical_id, rt_owner=True)
        spec.update(config_revision=1, deploy_revision=1, desired_status="Stopped", current_status="Stopped")
        self.sdk.clean_get.return_value = {
            "kind": "Clean",
            "metadata": {key: self.clean_ref[key] for key in ("tenant", "namespace", "name")},
            "spec": spec,
            "status": {"phase": "Ok"},
        }
        self.sdk.clean_update.side_effect = lambda **kw: {
            "kind": "Clean",
            "metadata": kw["metadata"],
            "spec": kw["spec"],
            "status": {"phase": "Pending"},
        }
        with mock.patch.object(self.handler, "get_bk_data_id", return_value=73):
            clean.reset_plugin_operation(self.plugin)
            self.handler.create_or_update()
        self.sdk.clean_update.assert_called_once()
        self.assertEqual(self.sdk.clean_update.call_args.kwargs["name"], self.clean_ref["name"])
        self.assertEqual(self.sdk.clean_update.call_args.kwargs["spec"]["result_table_id"], self.logical_id)
        self.sdk.clean_create.assert_not_called()
        self.assertTrue(self.plugin.bkbase_v4_resources["migration_maintenance"])
        # 首次PUT未收敛时保留显式维护意图，后续Beat完成已授权的存储步骤。
        self.sdk.clean_get.return_value.update(
            spec={**self.sdk.clean_update.call_args.kwargs["spec"], "current_status": "Running"},
            status={"phase": "Ok"},
        )
        with mock.patch.object(self.handler, "get_bk_data_id", return_value=73), mock.patch.object(
            self.handler, "build_storage_config", return_value=({"storage_type": "es"}, None)
        ), mock.patch.object(storage, "configure_storage", return_value={"task_state": "running"}) as configure_storage:
            self.handler.create_or_update()
        configure_storage.assert_called_once()
        self.assertNotIn("migration_maintenance", self.plugin.bkbase_v4_resources)
        self.assertTrue(self.plugin.bkbase_v4_resources["ready"])

    def test_historical_logical_table_survives_handler_clean_and_storage(self):
        with mock.patch.object(self.handler, "get_bk_data_id", return_value=73):
            params = self.handler.build_clean_config()
        existing_spec = clean.build_clean_spec(
            params, data_ref=self.data_ref, logical_id=self.logical_id, rt_owner=True
        )
        existing_spec.update(config_revision=1, deploy_revision=1, desired_status="Running", current_status="Running")
        self.sdk.clean_get.return_value = {
            "kind": "Clean",
            "metadata": {key: self.clean_ref[key] for key in ("tenant", "namespace", "name")},
            "spec": existing_spec,
            "status": {"phase": "Ok"},
        }
        self.sdk.clean_update.side_effect = lambda **kw: {
            "kind": "Clean",
            "metadata": kw["metadata"],
            "spec": {**kw["spec"], "current_status": "Running"},
            "status": {"phase": "Ok"},
        }
        with mock.patch.object(self.handler, "get_bk_data_id", return_value=73):
            self.handler.create_or_update_clean()
        self.sdk.clean_create.assert_not_called()
        if self.sdk.clean_update.called:
            self.assertEqual(self.sdk.clean_update.call_args.kwargs["spec"]["result_table_id"], self.logical_id)
        self.sdk.result_table_info.assert_called_with(tenant="tenant_a", result_table_id=self.logical_id)

        default = {
            DEFAULT_STORAGE_CONFIG_KEY: 11,
            DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY: {},
        }
        with mock.patch(
            "services.web.databus.collector_plugin.handlers.GlobalMetaConfig.get",
            side_effect=lambda key, **kw: default[key],
        ), mock.patch(
            "services.web.databus.collector_plugin.handlers.resource.databus.storage.storage_list",
            return_value=[
                {
                    "cluster_config": {
                        "cluster_id": 11,
                        "custom_option": {
                            "bkbase_cluster_id": "es_target",
                            "setup_config": {"retention_days_default": 14},
                        },
                    }
                }
            ],
        ):
            main, replica = self.handler.build_storage_config()
        self.assertFalse(replica)
        self.sdk.data_storage_get.return_value = {
            "kind": "DataStorage",
            "metadata": {key: self.storage_ref[key] for key in ("tenant", "namespace", "name")},
            "spec": {
                "tableInfo": {"source": self.rt_ref, "storage": self.cluster_ref, "expire": 14},
                "taskFieldSetting": {},
            },
            "status": {"phase": "Ok"},
        }
        self.sdk.data_storage_update.side_effect = lambda **kw: {
            "kind": "DataStorage",
            "metadata": kw["metadata"],
            "spec": kw["spec"],
            "status": {"phase": "Ok"},
        }
        storage.configure_storage(self.plugin, main)
        self.sdk.data_storage_create.assert_not_called()
        self.assertEqual(self.sdk.data_storage_update.call_args.kwargs["spec"]["tableInfo"]["source"], self.rt_ref)
        self.assertEqual(self.plugin.bkbase_table_id, self.logical_id)
        self.assertEqual(self.plugin.processing_id, "legacy-processing")

    def test_established_clean_or_table_cannot_be_silently_replaced(self):
        missing = APIRequestError(result={"message": "missing"})
        missing.http_status = 404
        self.sdk.clean_get.side_effect = missing
        with self.assertRaisesMessage(BKBaseResourceMappingError, "established V4 Clean is missing"):
            self.handler.create_or_update_clean()
        self.sdk.clean_create.assert_not_called()
        self.sdk.clean_update.assert_not_called()
        self.sdk.result_table_info.return_value["metadata"]["name"] = "another-rt"
        with self.assertRaisesMessage(BKBaseResourceMappingError, "identity conflicts"):
            self.handler.create_or_update_clean()
        self.sdk.clean_create.assert_not_called()
        self.sdk.clean_update.assert_not_called()

    def test_bound_missing_storage_is_not_recreated(self):
        missing = APIRequestError(result={"message": "missing"})
        missing.http_status = 404
        self.sdk.data_storage_get.side_effect = missing
        with self.assertRaisesMessage(BKBaseResourceMappingError, "established V4 DataStorage is missing"):
            storage.configure_storage(
                self.plugin, {"storage_type": "es", "storage_cluster": "es_target", "expires": 14}
            )
        self.sdk.data_storage_create.assert_not_called()

    def test_unbound_storage_uses_normal_create_and_initial_claim_hook(self):
        self.plugin.bkbase_v4_resources["storages"] = {}
        missing = APIRequestError(result={"message": "missing"})
        missing.http_status = 404
        self.sdk.data_storage_get.side_effect = missing
        self.sdk.data_storage_create.side_effect = lambda **kw: {
            "kind": "DataStorage",
            "metadata": kw["metadata"],
            "spec": kw["spec"],
            "status": {"phase": "Pending"},
        }
        claim = mock.Mock()
        result = storage.configure_storage(
            self.plugin,
            {"storage_type": "es", "storage_cluster": "es_target", "expires": 14},
            _before_write=claim,
            _bind_owner=False,
        )
        claim.assert_called_once()
        self.sdk.data_storage_create.assert_called_once()
        self.assertEqual(self.plugin.bkbase_v4_resources["storages"], {})
        self.assertIsNone(result["task_state"])
