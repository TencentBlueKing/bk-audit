"""验证日志插件 Doris 入库模型使用实际网关接受的协议值。"""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from api.bk_base_v4.default import DataStorageCreate
from services.web.bkbase import storage
from services.web.databus.collector_plugin.handlers import PluginEtlHandler
from services.web.databus.constants import (
    DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY,
    DEFAULT_STORAGE_CONFIG_KEY,
)


class DorisStorageModelTests(SimpleTestCase):
    def test_plugin_replica_uses_supported_model_in_v4_request(self):
        handler = PluginEtlHandler(plugin=SimpleNamespace(namespace="audit", collector_plugin_name_en="plugin_a"))
        config = {
            DEFAULT_STORAGE_CONFIG_KEY: 1,
            DEFAULT_REPLICA_WRITE_STORAGE_CONFIG_KEY: {"bkbase_cluster_id": "legacy_doris"},
        }
        with mock.patch.object(handler, "get_bk_data_id", return_value=11), mock.patch(
            "services.web.databus.collector_plugin.handlers.GlobalMetaConfig.get",
            side_effect=lambda key, **kwargs: config[key],
        ), mock.patch(
            "services.web.databus.collector_plugin.handlers.resource.databus.storage.storage_list",
            return_value=[{"cluster_config": {"cluster_id": 1, "custom_option": {"bkbase_cluster_id": "legacy_es"}}}],
        ):
            _, replica = handler.build_storage_config()
        spec = storage.convert_storage_config(replica)
        self.assertEqual(spec["tableInfo"]["data_model"], "duplicate_table")
        resource = DataStorageCreate()
        response = mock.Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"result": True, "code": "00", "data": {"metadata": {"name": "storage_a"}}}
        resource.session.request = mock.Mock(return_value=response)
        with mock.patch.object(resource, "build_header", return_value={}):
            resource.request(
                {"tenant": "tenant_a", "namespace": "audit", "metadata": {"name": "storage_a"}, "spec": spec}
            )
        self.assertEqual(
            resource.session.request.call_args.kwargs["json"]["spec"]["tableInfo"]["data_model"], "duplicate_table"
        )
