"""核验管理员配置到入库及计算存储节点的资源引用传递。

仅使用合成配置；真实配置序列化、测试库持久化与Service消费保持启用。
外部集群列表和HTTP传输替换为受控响应，不读取或写入真实资源。
"""
from copy import deepcopy
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from api.bk_base_v4.default import DataStorageCreate
from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from apps.meta.resources import SetGlobalMetaConfigResource
from services.web.analyze.constants import (
    DEFAULT_HDFS_STORAGE_CLUSTER_KEY,
    DEFAULT_QUEUE_STORAGE_CLUSTER_KEY,
)
from services.web.analyze.storage_node import (
    DorisStorageNode,
    ESStorageNode,
    HDFSStorageNode,
    QueueStorageNode,
)
from services.web.bkbase import flow, storage
from services.web.bkbase.constants import BKBASE_V4_STORAGE_CLUSTER_MAP
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.collector_plugin.handlers import PluginEtlHandler
from services.web.databus.constants import (
    DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
    DEFAULT_STORAGE_CONFIG_KEY,
)
from services.web.databus.models import CollectorPlugin


class StorageClusterValidationTests(SimpleTestCase):
    def test_invalid_cluster_mapping_is_rejected_before_request(self):
        context = {"tenant": "tenant_a", "namespace": "audit"}
        ref = {"kind": "Doris", "tenant": "tenant_a", "namespace": "clusters", "name": "cluster_a"}
        for mapping in (
            {"doris": {"old": {**ref, "kind": "DataSource"}}},
            {"doris": {"old": {**ref, "kind": "DorisCluster"}}},
            {"doris": {"old": {**ref, "tenant": "other"}}},
            {"doris": {"old": {**ref, "name": ""}}},
            {"doris": []},
            {"doris": {"old": "Doris/clusters/cluster_a"}},
        ):
            with self.subTest(mapping=mapping), mock.patch.object(GlobalMetaConfig, "get", return_value=mapping):
                with self.assertRaises(BKBaseResourceMappingError):
                    storage.resolve_storage_cluster(
                        context, audit_namespace="audit", storage_type="doris", legacy_cluster_id="old"
                    )


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit")
class StorageConfigurationPathTests(TestCase):
    def setUp(self):
        transport = mock.patch("requests.sessions.Session.request", side_effect=AssertionError("Unexpected HTTP"))
        transport.start()
        self.addCleanup(transport.stop)
        self.refs = {
            key: {"kind": kind, "tenant": "tenant_a", "namespace": "clusters", "name": key + "_a"}
            for key, kind in (
                ("es", "ElasticSearch"),
                ("doris", "Doris"),
                ("kafka", "Kafka"),
                ("hdfs", "Hdfs"),
                ("redis", "Redis"),
            )
        }
        self.save_config(BKBASE_V4_STORAGE_CLUSTER_MAP, {key: {"legacy_" + key: ref} for key, ref in self.refs.items()})
        self.save_config(DEFAULT_STORAGE_CONFIG_KEY, 7)
        self.save_config(DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY, {"bkbase_cluster_id": "legacy_doris"})
        self.save_config(DEFAULT_QUEUE_STORAGE_CLUSTER_KEY, "legacy_kafka")
        self.save_config(DEFAULT_HDFS_STORAGE_CLUSTER_KEY, "legacy_hdfs")
        self.cluster_list = [{"cluster_config": {"cluster_id": 7, "custom_option": {"bkbase_cluster_id": "legacy_es"}}}]

    def save_config(self, key, value, namespace="audit"):
        SetGlobalMetaConfigResource().request(
            config_level=ConfigLevelChoices.NAMESPACE,
            instance_key=namespace,
            config_key=key,
            config_value=deepcopy(value),
        )

    def test_plugin_main_and_replica_read_saved_mapping_into_v4_requests(self):
        rt = {"kind": "ResultTable", "tenant": "tenant_a", "namespace": "tables", "name": "rt_a"}
        plugin = CollectorPlugin.objects.create(
            namespace="audit",
            collector_plugin_id=1,
            collector_plugin_name="plugin",
            collector_plugin_name_en="plugin_a",
            bkdata_biz_id=1,
            table_id=1,
            index_set_id=1,
            bkbase_v4_resources={"result_table": rt},
        )
        handler = PluginEtlHandler(plugin=plugin)
        with mock.patch.object(handler, "get_bk_data_id", return_value=11), mock.patch.object(
            handler, "get_es_fields", return_value=[{"field_name": "value"}]
        ), mock.patch.object(handler, "get_doris_fields", return_value=[{"field_name": "value"}]), mock.patch(
            "services.web.databus.collector_plugin.handlers.resource.databus.storage.storage_list",
            return_value=self.cluster_list,
        ):
            main, replica = handler.build_storage_config()
        for purpose, config, kind, cluster in (
            ("main", main, "ElasticSearch", "es_a"),
            ("replica", replica, "Doris", "doris_a"),
        ):
            with self.subTest(purpose=purpose):
                endpoint = DataStorageCreate()
                response = mock.Mock(status_code=200, history=[])
                response.raise_for_status.return_value = None
                response.json.return_value = {"result": True, "code": "00", "data": {"status": {"phase": "Pending"}}}
                endpoint.session.request = mock.Mock(return_value=response)
                with mock.patch.object(endpoint, "build_header", return_value={}), mock.patch.object(
                    storage, "resource_lock"
                ), mock.patch.object(storage, "get_resource_or_none", return_value=None), mock.patch.object(
                    storage.api.bk_base_v4, "data_storage_create", endpoint.request
                ):
                    observed = storage.configure_storage(plugin, config, purpose=purpose)
                table = endpoint.session.request.call_args.kwargs["json"]["spec"]["tableInfo"]
                self.assertEqual(table["source"], rt)
                self.assertEqual(
                    table["storage"], {"kind": kind, "tenant": "tenant_a", "namespace": "clusters", "name": cluster}
                )
                self.assertIsNone(observed["task_state"])
        plugin.refresh_from_db()
        self.assertEqual(set(plugin.bkbase_v4_resources["storages"]), {"main", "replica"})
        self.assertEqual(plugin.bkbase_v4_resources["result_table"], rt)

    def test_flow_nodes_read_same_namespace_config_and_canonical_kinds(self):
        strategy = SimpleNamespace(namespace="audit", strategy_id=7)
        context = {"tenant": "tenant_a", "namespace": "audit"}
        with mock.patch(
            "services.web.analyze.storage_node.resource.databus.storage.storage_list", return_value=self.cluster_list
        ):
            for node_class, expected_kind, node_kind, cluster_name in (
                (ESStorageNode, "ElasticSearch", "EsStorageNode", "es_a"),
                (DorisStorageNode, "Doris", "DorisStorageNode", "doris_a"),
                (QueueStorageNode, "Kafka", "QueueStorageNode", "kafka_a"),
                (HDFSStorageNode, "Hdfs", "HdfsStorageNode", "hdfs_a"),
            ):
                with self.subTest(node=node_kind):
                    node = node_class("audit")
                    result = flow._storage_node(
                        context,
                        strategy,
                        {"node_type": node.node_type, "cluster": node.cluster, "expires": "7d"},
                        {"doris_databases": {"doris_a": "synthetic_db"}},
                    )
                    self.assertEqual(result["kind"], node_kind)
                    self.assertEqual(
                        result["storage"],
                        {"kind": expected_kind, "tenant": "tenant_a", "namespace": "clusters", "name": cluster_name},
                    )
        self.assertEqual(
            storage.resolve_storage_cluster(
                context, audit_namespace="audit", storage_type="redis", legacy_cluster_id="legacy_redis"
            ),
            {"kind": "Redis", "tenant": "tenant_a", "namespace": "clusters", "name": "redis_a"},
        )
        with self.assertRaises(BKBaseResourceMappingError):
            storage.resolve_storage_cluster(
                context, audit_namespace="other_audit", storage_type="doris", legacy_cluster_id="legacy_doris"
            )
