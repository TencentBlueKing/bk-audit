"""普通插件维护保留已有周期，副Doris新建由存储侧维护保留期。

使用实际 Handler、Plugin 编排、存储转换和 API 序列化，
只替换外部配置、清洗和平台传输，不访问真实业务资源。
"""

import json
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

import requests
from bk_resource import api
from bk_resource.exceptions import ValidateException
from django.conf import settings
from django.test import TestCase, override_settings

from api.bk_base_v4.default import BkBaseV4Resource
from services.web.bkbase import clean, storage
from services.web.bkbase.constants import BKBASE_V4_STORAGE_CLUSTER_MAP
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.bkbase.plugin_storage_switch import UPDATE_KEY
from services.web.databus import tasks
from services.web.databus.collector_plugin.handlers import (
    EventCollectorEtlHandler,
    PluginEtlHandler,
)
from services.web.databus.collector_plugin.resources import UpdatePluginResource
from services.web.databus.constants import (
    COLLECTOR_PLUGIN_ID,
    DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
    DEFAULT_STORAGE_CONFIG_KEY,
    DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY,
    DORIS_EVENT_STORAGE_CONFIG_KEY,
    EtlConfigEnum,
    PluginSceneChoices,
)
from services.web.databus.models import CollectorPlugin
from services.web.databus.storage.resources import (
    StorageListResource,
    UpdateStorageResource,
)


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit")
class PluginStorageRetentionTests(TestCase):
    def test_new_main_es_target_uses_existing_business_naming_rule_and_replica_stays_implicit(self):
        self.plugin.bkbase_v4_resources.pop("storages")
        self.plugin.has_storage = False
        main, replica = self.handler.build_storage_config()
        self.assertEqual(main["physical_table_name"], f"write_%Y%m%d_{settings.DEFAULT_BK_BIZ_ID}_bklog_plugin_a")
        self.assertNotIn("physical_table_name", replica)

    def test_real_post_and_put_keep_es_template_and_do_not_declare_datastorage_timezone(self):
        for kind in ("es", "doris"):
            for existing in (True, False):
                with self.subTest(kind=kind, existing=existing):
                    purpose = "main" if kind == "es" else "replica"
                    self.plugin.bkbase_v4_resources = {"result_table": self.rt, "storages": self.refs.copy()}
                    target = "write_%Y%m%d_synthetic" if kind == "es" else "synthetic_db.events"
                    remote = deepcopy(self.remote[self.refs[purpose]["name"]])
                    if not existing:
                        self.plugin.bkbase_v4_resources["storages"].pop(purpose)
                        self.remote.pop(self.refs[purpose]["name"])
                    self.plugin.save(update_fields=["bkbase_v4_resources"])
                    storage.configure_storage(
                        self.plugin,
                        {
                            "storage_type": kind,
                            "storage_cluster": "legacy_" + kind,
                            "physical_table_name": target,
                            "expires": 14,
                        },
                        purpose=purpose,
                    )
                    request = self.sent[-1]
                    self.assertEqual(request["method"], "PUT" if existing else "POST")
                    self.assertEqual(request["body"]["spec"]["tableInfo"]["physical_table_name"], target)
                    self.assertNotIn("timezone", request["body"]["spec"]["tableInfo"])
                    self.remote[self.refs[purpose]["name"]] = remote

    def test_event_saved_global_target_wins_over_regenerated_name(self):
        self.config[DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY] = "existing_db.existing_events"
        handler = EventCollectorEtlHandler(plugin=self.plugin)
        config = handler.build_event_storage_config()
        self.assertEqual(config["physical_table_name"], "existing_db.existing_events")
        self.config.pop(DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY)
        self.config[DORIS_EVENT_STORAGE_CONFIG_KEY] = {"physical_table_name": "saved_config.events"}
        self.assertEqual(handler.build_event_storage_config()["physical_table_name"], "saved_config.events")

    def setUp(self):
        self.rt = {"kind": "ResultTable", "tenant": "tenant_a", "namespace": "audit", "name": "input_a"}
        self.clusters = {
            kind: {"kind": resource_kind, "tenant": "tenant_a", "namespace": "clusters", "name": kind + "_a"}
            for kind, resource_kind in (("es", "ElasticSearch"), ("doris", "Doris"))
        }
        self.refs = {
            purpose: {"kind": "DataStorage", "tenant": "tenant_a", "namespace": "audit", "name": purpose + "_a"}
            for purpose in ("main", "replica")
        }
        self.plugin = CollectorPlugin.objects.create(
            namespace="audit",
            collector_plugin_id=1,
            collector_plugin_name="synthetic plugin",
            collector_plugin_name_en="plugin_a",
            bkdata_biz_id=1,
            table_id=1,
            index_set_id=1,
            retention=7,
            etl_config=EtlConfigEnum.BK_LOG_JSON.value,
            bkbase_v4_resources={
                "result_table": self.rt,
                "result_table_id": "1_plugin_a",
                "clean_role": "owner",
                "storages": self.refs,
            },
        )
        self.handler = PluginEtlHandler(plugin=self.plugin)
        self.config = {
            DEFAULT_STORAGE_CONFIG_KEY: 7,
            COLLECTOR_PLUGIN_ID: self.plugin.collector_plugin_id,
            DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY: {"bkbase_cluster_id": "legacy_doris"},
            BKBASE_V4_STORAGE_CLUSTER_MAP: {kind: {"legacy_" + kind: ref} for kind, ref in self.clusters.items()},
        }
        self.remote = {
            self.refs[purpose]["name"]: {
                "metadata": {**self.refs[purpose], "labels": {"keep": "original"}},
                "spec": {
                    "tableInfo": {
                        "source": self.rt,
                        "storage": self.clusters[kind],
                        "expire": 1,
                        **options,
                    },
                    "taskFieldSetting": {},
                    "autoOffsetReset": "earliest",
                    "description": "retain remote attributes",
                },
                "status": {"phase": "Ok"},
            }
            for purpose, kind, options in (
                ("main", "es", {"has_unique_key": True}),
                (
                    "replica",
                    "doris",
                    {"dimension_table": False, "data_model": "duplicate_table", "is_profiling": False},
                ),
            )
        }
        self.remote[self.refs["main"]["name"]]["spec"]["tableInfo"]["expire"] = 3
        self.sent = []
        for name, result in (
            ("get_bk_data_id", 11),
            ("get_es_fields", []),
            ("get_doris_fields", []),
            ("build_clean_config", {}),
        ):
            self.enterContext(mock.patch.object(PluginEtlHandler, name, return_value=result))
        self.enterContext(mock.patch.object(clean, "configure_clean", return_value={"task_state": "running"}))
        self.enterContext(mock.patch.object(clean, "_verified_result_table_ref", return_value=self.rt))
        self.enterContext(
            mock.patch.object(
                storage.GlobalMetaConfig,
                "get",
                side_effect=lambda *args, **kwargs: self.config.get(
                    args[0] if args else kwargs["config_key"], kwargs.get("default")
                ),
            )
        )
        self.cluster_list = [
            {
                "cluster_config": {
                    "cluster_id": 7,
                    "custom_option": {
                        "bkbase_cluster_id": "legacy_es",
                        "setup_config": {
                            "retention_days_default": 3,
                            "number_of_replicas_default": 1,
                        },
                    },
                }
            }
        ]
        self.enterContext(
            mock.patch(
                "services.web.databus.collector_plugin.handlers.resource.databus.storage.storage_list",
                return_value=self.cluster_list,
            )
        )
        self.enterContext(mock.patch.object(storage, "resource_lock"))
        self.enterContext(
            mock.patch.object(
                storage,
                "get_resource_or_none",
                side_effect=lambda endpoint, **params: deepcopy(self.remote.get(params["name"])),
            )
        )
        self.enterContext(mock.patch.object(BkBaseV4Resource, "build_header", return_value={}))
        self.enterContext(mock.patch("requests.sessions.Session.request", side_effect=self.transport))

    def transport(self, method, url, **kwargs):
        """记录真实 SDK 请求体并回送独立的受理快照。"""
        if method == "GET":
            if url.endswith("/resulttables/input_a/"):
                value = {
                    "kind": "ResultTable",
                    "metadata": {**self.rt, "labels": {"result_table_id": "1_plugin_a"}},
                    "spec": {},
                }
            else:
                value = {"kind": "DataStorage", **deepcopy(self.remote[url.rstrip("/").rsplit("/", 1)[1]])}
        else:
            self.assertIn(method, ("POST", "PUT"))
            self.assertIn("/v4/tenants/tenant_a/namespaces/audit/datastorages/", url)
            body = deepcopy(kwargs["json"])
            self.sent.append({"method": method, "body": body})
            value = {"metadata": body["metadata"], "spec": body["spec"], "status": {"phase": "Pending"}}
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps({"result": True, "code": "00", "data": value}).encode()
        response.url = url
        response.request = requests.Request(method, url).prepare()
        return response

    def unbind(self, purpose):
        """测试中仅移除本地及远端合成存储，模拟尚未创建。"""
        self.remote.pop(self.refs[purpose]["name"], None)
        self.plugin.bkbase_v4_resources["storages"].pop(purpose, None)
        self.plugin.save(update_fields=["bkbase_v4_resources"])

    def test_existing_main_and_replica_keep_remote_retention_without_republishing(self):
        for expire in (1, 14, None, -1):
            with self.subTest(expire=expire):
                self.remote[self.refs["replica"]["name"]]["spec"]["tableInfo"]["expire"] = expire
                original = deepcopy(self.remote)
                result = self.handler.create_or_update()
                self.assertEqual(result["task_state"], "running")
                self.assertEqual(self.sent, [])
                self.assertEqual(self.remote, original)
                self.plugin.refresh_from_db()
                self.assertTrue(self.plugin.bkbase_v4_resources["ready"])
                self.assertTrue(self.plugin.has_storage)
                self.assertTrue(self.plugin.has_replica_storage)

    def test_other_config_changes_preserve_current_expire_in_the_serialized_put(self):
        self.remote[self.refs["main"]["name"]]["spec"]["tableInfo"]["has_unique_key"] = False
        original = deepcopy(self.remote[self.refs["main"]["name"]])
        self.handler.create_or_update()
        self.assertEqual(len(self.sent), 1)
        submitted = self.sent[0]
        expected = deepcopy(original["spec"])
        expected["tableInfo"]["has_unique_key"] = True
        self.assertEqual(submitted["method"], "PUT")
        self.assertEqual(submitted["body"]["spec"], expected)
        self.assertEqual(submitted["body"]["metadata"], original["metadata"])

    def test_new_main_uses_current_metadata_instead_of_legacy_plugin_default(self):
        self.config[DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY] = {}
        self.unbind("main")
        self.handler.create_or_update()
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.sent[0]["method"], "POST")
        self.assertEqual(self.sent[0]["body"]["spec"]["tableInfo"]["expire"], 3)

    def test_new_replica_omits_retention_through_the_real_plugin_storage_chain(self):
        self.unbind("replica")
        result = self.handler.create_or_update()
        self.assertEqual(len(self.sent), 1)
        self.assertIsNone(result["task_state"])
        submitted = self.sent[0]
        self.assertEqual(submitted["method"], "POST")
        self.assertEqual(
            submitted["body"]["spec"]["tableInfo"],
            {
                "source": self.rt,
                "storage": self.clusters["doris"],
                "dimension_table": False,
                "data_model": "duplicate_table",
                "is_profiling": False,
            },
        )
        self.plugin.refresh_from_db()
        ref = self.plugin.bkbase_v4_resources["storages"]["replica"]
        self.assertEqual(ref["name"], submitted["body"]["metadata"]["name"])
        self.assertFalse(self.plugin.bkbase_v4_resources["ready"])
        self.remote[ref["name"]] = {**deepcopy(submitted["body"]), "status": {"phase": "Ok"}}
        self.assertEqual(self.handler.create_or_update()["task_state"], "running")
        self.assertEqual(len(self.sent), 1)
        self.plugin.refresh_from_db()
        self.assertTrue(self.plugin.has_replica_storage)
        self.assertTrue(self.plugin.bkbase_v4_resources["ready"])

    def test_replica_field_updates_preserve_the_storage_managed_retention(self):
        for expire in (1, 14, None, -1, "missing"):
            with self.subTest(expire=expire):
                remote = self.remote[self.refs["replica"]["name"]]
                remote["spec"]["tableInfo"].update(dimension_table=True, expire=expire)
                if expire == "missing":
                    remote["spec"]["tableInfo"].pop("expire")
                original = deepcopy(remote)
                self.sent.clear()
                self.handler.create_or_update()
                expected = deepcopy(original["spec"])
                expected["tableInfo"]["dimension_table"] = False
                self.assertEqual(len(self.sent), 1)
                self.assertEqual(self.sent[0]["method"], "PUT")
                self.assertEqual(self.sent[0]["body"]["spec"], expected)
                self.assertEqual(self.sent[0]["body"]["metadata"], original["metadata"])
                self.assertEqual(remote, original)

    def test_missing_retention_gate_still_applies_outside_ordinary_replica_doris(self):
        self.remote.clear()
        context = {"tenant": "tenant_a", "namespace": "audit"}
        for purpose, cluster, owner in (
            ("main", self.clusters["doris"], self.plugin),
            ("replica", self.clusters["es"], self.plugin),
            ("replica", self.clusters["doris"], SimpleNamespace(bkbase_v4_resources={})),
        ):
            with self.subTest(purpose=purpose, cluster=cluster["kind"], owner=type(owner).__name__):
                with self.assertRaises(BKBaseResourceMappingError):
                    storage.ensure_storage(
                        context,
                        owner,
                        rt_ref=self.rt,
                        cluster_ref=cluster,
                        purpose=purpose,
                        config={},
                        preserve_existing_retention=True,
                    )
        self.plugin.plugin_scene = PluginSceneChoices.EVENT
        with self.assertRaises(BKBaseResourceMappingError):
            storage.ensure_storage(
                context,
                self.plugin,
                rt_ref=self.rt,
                cluster_ref=self.clusters["doris"],
                purpose="replica",
                config={},
                preserve_existing_retention=True,
            )
        self.assertEqual(self.sent, [])

    def test_explicit_invalid_retention_is_not_silently_ignored_for_new_replica(self):
        self.remote.clear()
        for expire in (None, 0, -2, True):
            with self.subTest(expire=expire):
                with self.assertRaises(BKBaseResourceMappingError):
                    storage.ensure_storage(
                        {"tenant": "tenant_a", "namespace": "audit"},
                        self.plugin,
                        rt_ref=self.rt,
                        cluster_ref=self.clusters["doris"],
                        purpose="replica",
                        config={"tableInfo": {"expire": expire}},
                        preserve_existing_retention=True,
                    )
        self.assertEqual(self.sent, [])

    def test_explicit_null_retention_is_rejected_through_new_replica_parameter_conversion(self):
        self.unbind("replica")
        _, replica = self.handler.build_storage_config()
        replica["expires"] = None
        with self.assertRaises(BKBaseResourceMappingError):
            storage.configure_storage(self.plugin, replica, purpose="replica", preserve_existing_retention=True)
        self.assertEqual(self.sent, [])

    def test_explicit_null_retention_preserves_existing_replica_during_other_changes(self):
        remote = self.remote[self.refs["replica"]["name"]]
        remote["spec"]["tableInfo"].update(dimension_table=True, expire=14)
        original = deepcopy(remote)
        _, replica = self.handler.build_storage_config()
        replica["expires"] = None
        storage.configure_storage(self.plugin, replica, purpose="replica", preserve_existing_retention=True)
        expected = deepcopy(original["spec"])
        expected["tableInfo"]["dimension_table"] = False
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.sent[0]["method"], "PUT")
        self.assertEqual(self.sent[0]["body"]["spec"], expected)
        self.assertEqual(self.sent[0]["body"]["metadata"], original["metadata"])

    def test_new_main_rejects_missing_or_invalid_metadata_retention_before_creation(self):
        self.config[DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY] = {}
        self.unbind("main")
        for retention in (None, 0, -2):
            with self.subTest(retention=retention):
                self.cluster_list[0]["cluster_config"]["custom_option"]["setup_config"][
                    "retention_days_default"
                ] = retention
                with self.assertRaises(BKBaseResourceMappingError):
                    clean._configure_plugin(self.handler)
                self.assertEqual(self.sent, [])

    def test_explicit_unlimited_business_retention_is_not_confused_with_missing_configuration(self):
        self.config[DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY] = {}
        self.unbind("main")
        self.cluster_list[0]["cluster_config"]["custom_option"]["setup_config"]["retention_days_default"] = -1
        self.handler.create_or_update()
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.sent[0]["body"]["spec"]["tableInfo"]["expire"], -1)

    def test_explicit_service_update_can_still_change_retention(self):
        main, _ = self.handler.build_storage_config()
        main["expires"] = "2d"
        original = deepcopy(self.remote[self.refs["main"]["name"]])
        result = storage.configure_storage(self.plugin, main, purpose="main")
        expected = deepcopy(original["spec"])
        expected["tableInfo"]["expire"] = 2
        self.assertEqual(
            self.sent, [{"method": "PUT", "body": {"metadata": original["metadata"], "spec": expected, "status": None}}]
        )
        self.assertIsNone(result["task_state"])

    def test_missing_metadata_keeps_existing_main_instead_of_legacy_default(self):
        self.cluster_list[0]["cluster_config"]["custom_option"]["setup_config"] = {}
        self.remote[self.refs["main"]["name"]]["spec"]["tableInfo"]["expire"] = 30
        self.handler.create_or_update()
        self.assertEqual(self.sent, [])

    def test_storage_list_preserves_missing_retention_without_inserting_request_defaults(self):
        row = {
            "bk_biz_id": 1,
            "auth_info": {"username": "", "password": ""},
            "cluster_config": {
                "cluster_id": 7,
                "cluster_name": "synthetic",
                "domain_name": "storage.example.test",
                "port": 9200,
                "schema": "https",
                "creator": "synthetic",
                "create_time": "2026-01-01T00:00:00Z",
                "custom_option": {
                    "bk_biz_id": 1,
                    "hot_warm_config": {"is_enabled": False},
                    "source_type": "custom",
                    "setup_config": {},
                    "admin": [],
                    "description": "synthetic",
                    "visible_config": {},
                    "cluster_namespace": "audit",
                    "bkbase_cluster_id": "legacy_es",
                },
            },
        }
        with mock.patch.object(api.bk_log, "get_storages", return_value=[row]):
            result = StorageListResource().request(namespace="audit")
        setup = result[0]["cluster_config"]["custom_option"]["setup_config"]
        self.assertNotIn("retention_days_default", setup)
        self.assertIn("number_of_replicas_default", setup)
        self.assertEqual(setup["number_of_replicas_default"], 1)
        self.assertEqual(setup["number_of_replicas_max"], 1)
        self.cluster_list[:] = result
        self.remote[self.refs["main"]["name"]]["spec"]["tableInfo"]["expire"] = 30
        self.handler.create_or_update()
        self.assertEqual(self.sent, [])
        row["cluster_config"]["custom_option"].pop("setup_config")
        with mock.patch.object(api.bk_log, "get_storages", return_value=[row]), self.assertRaises(ValidateException):
            StorageListResource().request(namespace="audit")

    @override_settings(EVENT_DORIS_EXPIRES="2d")
    def test_event_plugin_explicit_retention_updates_existing_storage_through_its_handler(self):
        self.plugin.plugin_scene = PluginSceneChoices.EVENT
        self.plugin.save(update_fields=["plugin_scene"])
        self.remote[self.refs["main"]["name"]] = deepcopy(self.remote[self.refs["replica"]["name"]])
        self.remote[self.refs["main"]["name"]]["metadata"] = {**self.refs["main"], "labels": {"keep": "original"}}
        original_replica = deepcopy(self.remote[self.refs["replica"]["name"]])
        result = EventCollectorEtlHandler(plugin=self.plugin).create_or_update()
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.sent[0]["method"], "PUT")
        self.assertEqual(self.sent[0]["body"]["metadata"]["name"], self.refs["main"]["name"])
        self.assertEqual(self.sent[0]["body"]["spec"]["tableInfo"]["expire"], 2)
        self.assertEqual(self.remote[self.refs["replica"]["name"]], original_replica)
        self.assertIsNone(result["task_state"])

    def test_real_storage_update_syncs_metadata_and_main_retention_through_etl(self):
        self.cluster_list[0]["cluster_config"]["custom_option"]["setup_config"]["retention_days_default"] = 2
        with mock.patch.object(
            api.bk_log, "update_storage", return_value={"cluster_config": {"cluster_id": 7}}
        ), mock.patch.object(api.bk_log, "get_storages", return_value=self.cluster_list), mock.patch.object(
            api.bk_log, "batch_connectivity_detect", return_value={"7": {"cluster_stats": {"data_node_count": 1}}}
        ), mock.patch.object(
            api.bk_log, "update_collector_plugin", return_value={"collector_plugin_id": 1}
        ), mock.patch.object(
            tasks.resource.databus.collector_plugin, "update_plugin", side_effect=UpdatePluginResource().request
        ), mock.patch.object(
            tasks.create_or_update_plugin_etl, "delay"
        ), mock.patch(
            "core.lock.CacheLock"
        ) as task_lock, mock.patch.object(
            tasks.logger, "exception"
        ) as task_errors, mock.patch.object(
            tasks.ErrorMsgHandler, "send"
        ) as notify:
            task_lock.return_value.locked = False
            UpdateStorageResource().request(
                {
                    "namespace": "audit",
                    "cluster_id": 7,
                    "domain_name": "storage.example.test",
                    "port": 9200,
                    "schema": "https",
                    "auth_info": {"username": "", "password": ""},
                    "setup_config": {"retention_days_default": 2},
                    "source_type": "custom",
                    "admin": [],
                    "description": "synthetic",
                }
            )
            self.plugin.refresh_from_db()
            self.assertTrue(self.plugin.storage_changed)
            tasks.change_storage_cluster.run()
            if task_errors.call_args is not None:
                raise task_errors.call_args.args[-1]
            self.plugin.refresh_from_db()
            self.assertEqual(
                self.plugin.retention, 2, self.plugin.bkbase_v4_resources.get(UPDATE_KEY, {}).get("message")
            )
            tasks.create_or_update_plugin_etl.run(collector_plugin_id=1)
            notify.assert_not_called()
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.sent[0]["method"], "PUT")
        self.assertEqual(self.sent[0]["body"]["metadata"]["name"], self.refs["main"]["name"])
        self.assertEqual(self.sent[0]["body"]["spec"]["tableInfo"]["expire"], 2)

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_retains_legacy_plugin_parameters(self):
        main, replica = self.handler.build_storage_config()
        self.assertEqual(main["expires"], "7d")
        self.assertEqual(replica["expires"], "365d")

    def test_plugin_maintenance_does_not_reset_existing_consumption_position(self):
        for value in self.remote.values():
            value["spec"]["autoOffsetReset"] = "latest"
        result = self.handler.create_or_update()
        self.assertEqual(self.sent, [])
        self.assertEqual(result["task_state"], "running")

    def test_storage_config_change_keeps_unspecified_existing_position(self):
        for value in self.remote.values():
            value["spec"]["autoOffsetReset"] = "latest"
        self.remote[self.refs["main"]["name"]]["spec"]["tableInfo"]["has_unique_key"] = False
        original = deepcopy(self.remote[self.refs["main"]["name"]])
        self.handler.create_or_update()
        expected = deepcopy(original["spec"])
        expected["tableInfo"]["has_unique_key"] = True
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.sent[0]["body"]["spec"], expected)

    def test_explicit_service_position_still_changes_the_existing_task(self):
        self.remote[self.refs["main"]["name"]]["spec"]["autoOffsetReset"] = "latest"
        main, _ = self.handler.build_storage_config()
        main["auto_offset_reset"] = "earliest"
        storage.configure_storage(self.plugin, main)
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.sent[0]["body"]["spec"]["autoOffsetReset"], "earliest")

    def test_new_task_uses_platform_position_default_without_redeclaring_it_on_retry(self):
        self.config[DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY] = {}
        self.unbind("main")
        self.handler.create_or_update()
        self.assertEqual(len(self.sent), 1)
        body = self.sent[0]["body"]
        self.assertNotIn("autoOffsetReset", body["spec"])
        saved = deepcopy(body)
        saved["spec"]["autoOffsetReset"] = "earliest"
        saved["status"] = {"phase": "Ok"}
        self.remote[body["metadata"]["name"]] = saved
        result = self.handler.create_or_update()
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(result["task_state"], "running")

    def test_default_cluster_requires_one_match_with_a_bkbase_mapping(self):
        original = deepcopy(self.cluster_list[0])
        unmapped = deepcopy(original)
        unmapped["cluster_config"]["custom_option"].pop("bkbase_cluster_id")
        for rows in ([], [{"cluster_config": {"cluster_id": 8}}], [original, deepcopy(original)], [unmapped]):
            with self.subTest(rows=rows):
                self.cluster_list[:] = deepcopy(rows)
                try:
                    self.handler.build_storage_config()
                except BKBaseResourceMappingError:
                    continue
                except Exception as error:
                    self.fail(f"Unclassified storage configuration failure: {type(error).__name__}")
                self.fail("Invalid default storage configuration was accepted")
        self.assertEqual(self.sent, [])

    def test_bad_default_cluster_does_not_abort_the_next_plugin_in_the_real_task(self):
        self.plugin.namespace = "audit_bad"
        self.plugin.save(update_fields=["namespace"])
        good_rt = {**self.rt, "name": "input_good"}
        good_refs = {purpose: {**ref, "name": ref["name"] + "_good"} for purpose, ref in self.refs.items()}
        good = CollectorPlugin.objects.create(
            namespace="audit",
            collector_plugin_id=2,
            collector_plugin_name="good plugin",
            collector_plugin_name_en="plugin_good",
            bkdata_biz_id=1,
            table_id=2,
            index_set_id=2,
            etl_config=EtlConfigEnum.BK_LOG_JSON,
            bkbase_v4_resources={
                "result_table": good_rt,
                "result_table_id": "1_good",
                "storages": good_refs,
            },
        )
        for purpose, ref in good_refs.items():
            remote = deepcopy(self.remote[self.refs[purpose]["name"]])
            remote["metadata"] = {**ref, "labels": {"keep": "original"}}
            remote["spec"]["tableInfo"]["source"] = good_rt
            self.remote[ref["name"]] = remote
        with mock.patch(
            "services.web.databus.collector_plugin.handlers.resource.databus.storage.storage_list",
            side_effect=lambda *, namespace: self.cluster_list if namespace == "audit" else [],
        ), mock.patch("core.lock.CacheLock") as task_lock:
            task_lock.return_value.locked = False
            try:
                tasks.create_or_update_plugin_etl.run()
            except Exception as error:
                self.fail(f"One bad plugin aborted the task: {type(error).__name__}")
        self.plugin.refresh_from_db()
        good.refresh_from_db()
        self.assertTrue(self.plugin.bkbase_v4_resources["message"])
        self.assertFalse(self.plugin.bkbase_v4_resources["ready"])
        self.assertTrue(good.bkbase_v4_resources["ready"])
        self.assertEqual(self.sent, [])
