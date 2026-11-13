"""Exercise the default storage action and the periodic V4 switch consumer."""

from copy import deepcopy
from unittest import mock

from bk_resource import api, resource
from bk_resource.exceptions import APIRequestError, ValidateException
from django.test import TestCase, override_settings

from apps.exceptions import StorageChanging
from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from services.web.bkbase import plugin_storage_switch
from services.web.bkbase.constants import BKBASE_V4_STORAGE_CLUSTER_MAP
from services.web.databus import tasks
from services.web.databus.collector_plugin.resources import UpdatePluginResource
from services.web.databus.constants import (
    COLLECTOR_PLUGIN_ID,
    DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
    DEFAULT_STORAGE_CONFIG_KEY,
    EtlConfigEnum,
)
from services.web.databus.models import CollectorPlugin
from services.web.databus.storage.resources import (
    StorageActivateResource,
    UpdateStorageResource,
)


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="default", BKBASE_V4_NAMESPACE="audit")
class PluginStorageSwitchTests(TestCase):
    def setUp(self):
        self.main_old = self.ref("ElasticSearch", "main_old")
        self.main_new = self.ref("ElasticSearch", "main_new")
        self.replica_old = self.ref("Doris", "replica_old")
        self.replica_new = self.ref("Doris", "replica_new")
        self.table = self.ref("ResultTable", "actual_rt")
        self.main = self.ref("DataStorage", "switch_main_store")
        self.replica = self.ref("DataStorage", "switch_replica_store")
        self.plugin = CollectorPlugin.objects.create(
            namespace="audit",
            collector_plugin_id=91,
            collector_plugin_name="synthetic",
            collector_plugin_name_en="synthetic",
            bkdata_biz_id=1,
            table_id=10,
            index_set_id=11,
            has_storage=True,
            has_replica_storage=True,
            etl_config=EtlConfigEnum.BK_LOG_JSON,
            bkbase_v4_resources={
                "clean_role": "owner",
                "result_table_id": "logical_table",
                "result_table": self.table,
                "storages": {"main": self.main, "replica": self.replica},
                "retained": {"keep": "value"},
            },
        )
        self.set_config(COLLECTOR_PLUGIN_ID, self.plugin.collector_plugin_id)
        self.set_config(DEFAULT_STORAGE_CONFIG_KEY, 1)
        self.set_config(DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY, {"cluster_id": 31, "bkbase_cluster_id": "doris_a"})
        self.set_config(
            BKBASE_V4_STORAGE_CLUSTER_MAP,
            {
                "es": {"es_a": self.main_old, "es_b": self.main_new},
                "doris": {"doris_a": self.replica_old, "doris_b": self.replica_new},
            },
        )
        self.remote = {
            self.main["name"]: self.storage(self.main, self.main_old),
            self.replica["name"]: self.storage(self.replica, self.replica_old),
        }
        self.baseline = deepcopy(self.remote)
        self.requests = []
        self.drop_response = False
        self.keep_old_remote = False
        self.enterContext(mock.patch.object(api.bk_base_v4, "data_storage_get", side_effect=self.get_storage))
        self.enterContext(mock.patch.object(api.bk_base_v4, "data_storage_update", side_effect=self.put_storage))
        self.enterContext(mock.patch.object(api.bk_base_v4, "data_storage_create"))
        self.enterContext(
            mock.patch.object(
                api.bk_base_v4,
                "result_table_resource_get",
                return_value={
                    "kind": "ResultTable",
                    "metadata": {**self.table, "labels": {"result_table_id": "logical_table"}},
                    "spec": {},
                    "status": {"phase": "Ok"},
                },
            )
        )
        self.enterContext(
            mock.patch.object(
                resource.databus.storage,
                "storage_list",
                return_value=[
                    {"cluster_config": {"cluster_id": 1, "custom_option": {"bkbase_cluster_id": "es_a"}}},
                    {"cluster_config": {"cluster_id": 2, "custom_option": {"bkbase_cluster_id": "es_b"}}},
                ],
            )
        )
        self.sync = self.enterContext(mock.patch.object(resource.databus.collector_plugin, "update_plugin"))
        self.edit = self.enterContext(
            mock.patch.object(api.bk_log, "update_storage", return_value={"cluster_config": {"cluster_id": 2}})
        )
        self.enterContext(mock.patch("core.lock.CacheLock")).return_value.locked = False
        self.enterContext(mock.patch("services.web.databus.storage.resources.cache", mock.Mock(get=lambda _: None)))

    @staticmethod
    def ref(kind, name):
        return {"kind": kind, "tenant": "default", "namespace": "audit", "name": name}

    @staticmethod
    def set_config(key, value):
        GlobalMetaConfig.set(key, value, config_level=ConfigLevelChoices.NAMESPACE, instance_key="audit")

    def storage(self, ref, cluster):
        return {
            "kind": "DataStorage",
            "metadata": {
                **ref,
                "labels": {"result_table_id": "logical_table"},
                "annotations": {"task_stopped": "false", "keep": "value", "bk_username": "old"},
            },
            "spec": {
                "tableInfo": {"source": self.table, "storage": cluster, "expire": 7},
                "taskFieldSetting": {"key_fields": ["event_id"]},
                "autoOffsetReset": "latest",
                "maintainers": ["keeper"],
            },
            "status": {"phase": "Ok", "history_id": 10},
        }

    def get_storage(self, *, name, **kwargs):
        return deepcopy(self.remote[name])

    def put_storage(self, *, name, metadata, spec, status, **kwargs):
        self.assertIsNone(status)
        self.requests.append((name, deepcopy(metadata), deepcopy(spec)))
        result = {
            "metadata": deepcopy(metadata),
            "spec": deepcopy(spec),
            "status": {"phase": "Pending", "history_id": 11},
        }
        if not self.keep_old_remote:
            self.remote[name] = {"kind": "DataStorage", **deepcopy(result)}
            self.remote[name]["metadata"]["annotations"]["bk_username"] = "new"
        if self.drop_response:
            raise APIRequestError(result="lost response")
        return result

    def activate(self, *, cluster_id=2, **changes):
        return StorageActivateResource().request({"namespace": "audit", "cluster_id": cluster_id, **changes})

    def advance(self):
        tasks.change_storage_cluster.run()
        self.plugin.refresh_from_db()

    def edit_storage(self):
        return UpdateStorageResource().request(
            {
                "namespace": "audit",
                "cluster_id": 2,
                "domain_name": "storage.example.test",
                "port": 9200,
                "schema": "https",
                "auth_info": {"username": "", "password": ""},
                "setup_config": {},
                "source_type": "custom",
                "admin": [],
                "description": "test storage",
            }
        )

    def test_legacy_mark_does_not_claim_switch_without_known_previous_cluster(self):
        self.set_config(DEFAULT_STORAGE_CONFIG_KEY, 2)
        CollectorPlugin.objects.filter(pk=self.plugin.pk).update(storage_changed=True)
        self.advance()
        self.assertTrue(self.plugin.storage_changed)
        self.assertEqual(self.requests, [])
        self.sync.assert_not_called()

    def test_legacy_mark_can_sync_when_both_bindings_match_current_defaults(self):
        CollectorPlugin.objects.filter(pk=self.plugin.pk).update(storage_changed=True)
        self.advance()
        self.assertFalse(self.plugin.storage_changed)
        self.assertEqual(self.requests, [])
        self.sync.assert_called_once()

    def test_first_storage_setup_observes_bindings_that_arrive_before_bklog_reply(self):
        existing_bindings = deepcopy(self.plugin.bkbase_v4_resources)
        CollectorPlugin.objects.filter(pk=self.plugin.pk).update(
            bkbase_v4_resources={}, has_storage=False, has_replica_storage=False
        )
        self.activate()
        self.remote[self.main["name"]]["spec"]["tableInfo"]["storage"] = self.main_new

        def bind_from_etl(**kwargs):
            latest = CollectorPlugin.objects.get(pk=self.plugin.pk)
            CollectorPlugin.objects.filter(pk=self.plugin.pk).update(
                bkbase_v4_resources={**latest.bkbase_v4_resources, **existing_bindings},
                has_storage=True,
                has_replica_storage=True,
            )

        self.sync.side_effect = bind_from_etl
        self.advance()
        self.assertTrue(self.plugin.storage_changed)

        self.advance()
        self.assertFalse(self.plugin.storage_changed)
        self.sync.assert_called_once()
        self.assertEqual(self.requests, [])

    def test_real_storage_edit_during_bklog_reply_remains_pending_until_processed(self):
        self.activate()
        self.advance()
        self.remote[self.main["name"]]["status"]["phase"] = "Ok"
        self.sync.side_effect = lambda **kwargs: self.edit_storage()

        self.advance()

        self.edit.assert_called_once()
        self.assertTrue(self.plugin.storage_changed)
        self.sync.assert_called_once()

        self.sync.side_effect = None
        self.advance()

        self.assertFalse(self.plugin.storage_changed)
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.sync.call_count, 2)

    def test_real_storage_edit_after_bklog_reply_registers_new_work(self):
        self.activate()
        self.advance()
        self.remote[self.main["name"]]["status"]["phase"] = "Ok"
        self.advance()
        self.assertFalse(self.plugin.storage_changed)
        self.sync.assert_called_once()

        self.edit_storage()
        self.plugin.refresh_from_db()
        self.edit.assert_called_once()
        self.assertTrue(self.plugin.storage_changed)
        self.advance()

        self.assertFalse(self.plugin.storage_changed)
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.sync.call_count, 2)

    def test_main_switch_keeps_mark_until_target_get_and_existing_plugin_sync(self):
        self.activate()
        self.advance()
        self.assertTrue(self.plugin.storage_changed)
        self.sync.assert_not_called()
        [(name, metadata, spec)] = self.requests
        self.assertEqual(name, self.main["name"])
        self.assertEqual(metadata, self.baseline[name]["metadata"])
        expected = deepcopy(self.baseline[name]["spec"])
        expected["tableInfo"]["storage"] = self.main_new
        self.assertEqual(spec, expected)
        self.advance()
        self.assertEqual(len(self.requests), 1)
        self.sync.assert_not_called()
        self.remote[name]["status"]["phase"] = "Ok"
        self.advance()
        self.assertFalse(self.plugin.storage_changed)
        self.sync.assert_called_once()
        self.assertEqual(self.plugin.bkbase_v4_resources["storages"], {"main": self.main, "replica": self.replica})
        self.assertEqual(self.plugin.bkbase_v4_resources["retained"], {"keep": "value"})

    def test_replica_switch_updates_only_bound_replica(self):
        self.activate(cluster_id=32, cluster_mode="replica", config={"cluster_id": 32, "bkbase_cluster_id": "doris_b"})
        self.advance()
        [(name, _, spec)] = self.requests
        self.assertEqual(name, self.replica["name"])
        self.assertEqual(spec["tableInfo"]["storage"], self.replica_new)
        self.remote[name]["status"]["phase"] = "Ok"
        self.advance()
        self.assertFalse(self.plugin.storage_changed)
        self.assertEqual(self.remote[self.main["name"]], self.baseline[self.main["name"]])

    def test_unknown_storage_write_is_observed_without_repeating_and_blocks_another_activation(self):
        self.drop_response = True
        self.keep_old_remote = True
        self.activate()
        self.advance()
        with self.assertRaises(StorageChanging):
            self.activate(cluster_id=1)
        self.advance()
        self.assertEqual(len(self.requests), 1)
        self.assertTrue(self.plugin.storage_changed)
        self.sync.assert_not_called()

    def test_bklog_failure_keeps_mark_after_storage_is_confirmed(self):
        self.activate()
        self.advance()
        self.remote[self.main["name"]]["status"]["phase"] = "Ok"
        self.sync.side_effect = APIRequestError(result="lost sync receipt")
        self.advance()
        self.advance()
        self.assertEqual(len(self.requests), 1)
        self.assertTrue(self.plugin.storage_changed)
        self.sync.assert_called_once()

    def test_unknown_applied_switch_converges_from_the_exact_target_without_resending(self):
        self.drop_response = True
        self.activate()
        self.advance()
        self.remote[self.main["name"]]["status"]["phase"] = "Ok"
        self.advance()
        self.assertEqual(len(self.requests), 1)
        self.assertFalse(self.plugin.storage_changed)
        self.sync.assert_called_once()

    def test_unconfirmed_switch_cannot_consume_get_from_a_rebound_storage(self):
        self.activate()
        self.advance()
        other = self.ref("DataStorage", "other_main")
        value = deepcopy(self.remote[self.main["name"]])
        value["metadata"].update(other)
        value["status"]["phase"] = "Ok"
        self.remote[other["name"]] = value
        binding = deepcopy(self.plugin.bkbase_v4_resources)
        binding["storages"]["main"] = other
        CollectorPlugin.objects.filter(pk=self.plugin.pk).update(bkbase_v4_resources=binding)
        self.advance()
        self.assertTrue(self.plugin.storage_changed)
        self.assertEqual(len(self.requests), 1)
        self.sync.assert_not_called()
        with self.assertRaises(StorageChanging):
            self.activate(cluster_id=1)

    def test_late_bklog_success_does_not_clear_a_newer_switch(self):
        self.activate()
        self.advance()
        self.remote[self.main["name"]]["status"]["phase"] = "Ok"

        def replace_intent(**kwargs):
            latest = CollectorPlugin.objects.get(pk=self.plugin.pk)
            binding = deepcopy(latest.bkbase_v4_resources)
            binding["storage_cluster_switch"] = {"operation_id": "newer", "purpose": "main", "target": "1"}
            CollectorPlugin.objects.filter(pk=self.plugin.pk).update(bkbase_v4_resources=binding, storage_changed=True)

        self.sync.side_effect = replace_intent
        self.advance()
        self.assertTrue(self.plugin.storage_changed)
        self.assertEqual(self.plugin.bkbase_v4_resources["storage_cluster_switch"]["operation_id"], "newer")

    def test_existing_unbound_role_keeps_change_pending_without_guessing_resource(self):
        binding = deepcopy(self.plugin.bkbase_v4_resources)
        binding["storages"].pop("main")
        CollectorPlugin.objects.filter(pk=self.plugin.pk).update(bkbase_v4_resources=binding)
        self.activate()
        self.advance()
        self.assertTrue(self.plugin.storage_changed)
        self.assertIn("C08", self.plugin.bkbase_v4_resources["storage_cluster_switch"]["message"])
        self.assertEqual(self.requests, [])
        self.sync.assert_not_called()

    def enable_real_plugin_request(self):
        """保留真正Resource请求校验，隔离平台API、队列和通知出口。"""
        self.sync.side_effect = UpdatePluginResource().request
        self.enterContext(
            mock.patch.object(
                UpdatePluginResource,
                "build_in_config",
                return_value={
                    "retention": 7,
                    "allocation_min_days": 0,
                    "storage_replies": 1,
                    "storage_shards_nums": 1,
                    "storage_shards_size": 1,
                },
            )
        )
        self.bklog_write = self.enterContext(
            mock.patch.object(
                api.bk_log,
                "update_collector_plugin",
                return_value={
                    "collector_plugin_id": self.plugin.collector_plugin_id,
                    "collector_plugin_name": "synthetic",
                },
            )
        )
        self.enterContext(mock.patch.object(tasks.create_or_update_plugin_etl, "delay"))
        self.notify = self.enterContext(mock.patch.object(tasks.ErrorMsgHandler, "send"))

    def prepare_sync(self, switch):
        if switch:
            self.activate()
            self.advance()
            self.remote[self.main["name"]]["status"]["phase"] = "Ok"
            return plugin_storage_switch.SWITCH_KEY
        self.edit_storage()
        self.plugin.refresh_from_db()
        return plugin_storage_switch.UPDATE_KEY

    def assert_invalid_config_can_be_repaired_without_claiming_a_write(self, *, switch):
        self.enable_real_plugin_request()
        key = self.prepare_sync(switch)
        original = deepcopy(self.plugin.bkbase_v4_resources[key])
        storage_writes = deepcopy(self.requests)
        for invalid in (None, "   "):
            with self.subTest(invalid=invalid):
                CollectorPlugin.objects.filter(pk=self.plugin.pk).update(etl_config=invalid)
                self.advance()
                current = self.plugin.bkbase_v4_resources[key]
                self.assertNotIn("bklog_started", current)
                self.assertEqual(current["operation_id"], original["operation_id"])
                self.assertEqual(current.get("write"), original.get("write"))
                self.assertTrue(current["message"])
                self.assertTrue(self.plugin.storage_changed)
                self.assertEqual(self.requests, storage_writes)
                self.sync.assert_not_called()
                self.bklog_write.assert_not_called()
                self.notify.assert_not_called()
        CollectorPlugin.objects.filter(pk=self.plugin.pk).update(etl_config="custom_non_enum_config")
        self.advance()
        self.assertFalse(self.plugin.storage_changed)
        self.assertNotIn(key, self.plugin.bkbase_v4_resources)
        self.assertEqual(self.requests, storage_writes)
        self.assertEqual(self.bklog_write.call_args.kwargs["etl_config"], "custom_non_enum_config")
        self.bklog_write.assert_called_once()
        self.notify.assert_not_called()

    def test_config_update_validates_before_claim_and_preserves_the_repairable_intent(self):
        self.assert_invalid_config_can_be_repaired_without_claiming_a_write(switch=False)

    def test_switch_sync_validates_before_claim_and_preserves_completed_storage_work(self):
        self.assert_invalid_config_can_be_repaired_without_claiming_a_write(switch=True)

    def assert_config_changed_before_claim_is_not_sent(self, *, switch):
        key = self.prepare_sync(switch)
        original = deepcopy(self.plugin.bkbase_v4_resources[key])
        writes = deepcopy(self.requests)

        def validate_then_change(value):
            UpdatePluginResource.RequestSerializer().fields["etl_config"].run_validation(value)
            CollectorPlugin.objects.filter(pk=self.plugin.pk).update(etl_config="newer_config")
            return True

        with mock.patch.object(
            plugin_storage_switch, "_valid_bklog_etl_config", side_effect=validate_then_change, create=True
        ):
            self.advance()
        self.assertIn(key, self.plugin.bkbase_v4_resources)
        self.assertEqual(self.plugin.bkbase_v4_resources[key], original)
        self.assertTrue(self.plugin.storage_changed)
        self.assertEqual(self.requests, writes)
        self.sync.assert_not_called()

    def test_config_update_does_not_send_a_value_changed_after_local_validation(self):
        self.assert_config_changed_before_claim_is_not_sent(switch=False)

    def test_switch_sync_does_not_send_a_value_changed_after_local_validation(self):
        self.assert_config_changed_before_claim_is_not_sent(switch=True)

    def test_preexisting_unknown_claim_is_not_cleared_when_current_config_is_invalid(self):
        key = self.prepare_sync(False)
        binding = deepcopy(self.plugin.bkbase_v4_resources)
        binding[key]["bklog_started"] = True
        CollectorPlugin.objects.filter(pk=self.plugin.pk).update(bkbase_v4_resources=binding, etl_config=None)
        self.advance()
        self.assertEqual(self.plugin.bkbase_v4_resources, binding)
        self.assertTrue(self.plugin.storage_changed)
        self.sync.assert_not_called()

    def test_validation_error_after_claim_is_not_assumed_to_be_an_unsent_request(self):
        key = self.prepare_sync(False)
        self.sync.side_effect = ValidateException("synthetic response validation failure")
        with mock.patch.object(tasks.ErrorMsgHandler, "send"):
            self.advance()
            self.advance()
        self.assertTrue(self.plugin.bkbase_v4_resources[key]["bklog_started"])
        self.assertTrue(self.plugin.storage_changed)
        self.sync.assert_called_once()
