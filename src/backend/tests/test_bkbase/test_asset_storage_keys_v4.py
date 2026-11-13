"""资产入库字段转换只适配请求，不解除组合写入保护。"""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, override_settings

from services.web.databus.collector.snapshot.join.etl_storage import (
    AssetEtlStorageHandler,
)


class AssetStorageKeyTests(SimpleTestCase):
    def build(self, kind):
        handler = AssetEtlStorageHandler(
            data_id=11,
            system=SimpleNamespace(system_id="sample"),
            resource_type=SimpleNamespace(resource_type_id="server"),
            storage_type=kind,
        )
        with mock.patch.object(handler, "get_storage_cluster", return_value="legacy"), mock.patch.object(
            handler, "get_storage_expires", return_value="7d"
        ), mock.patch.object(AssetEtlStorageHandler, "storage_fields", new_callable=mock.PropertyMock, return_value=[]):
            return handler.storage_config

    @override_settings(BKBASE_API_VERSION="v4")
    def test_v4_asset_keys_are_field_names_for_all_three_storages(self):
        for kind in ("hdfs", "redis", "doris"):
            with self.subTest(kind=kind):
                config = self.build(kind)
                self.assertEqual(config["key_fields"], ["id", "resource_type_id", "system_id"])
                self.assertNotIn("index_fields", config)

    @override_settings(BKBASE_API_VERSION="v3")
    def test_v3_keeps_existing_index_descriptor(self):
        for kind in ("hdfs", "redis", "doris"):
            with self.subTest(kind=kind):
                config = self.build(kind)
                self.assertEqual(
                    [field["physical_field"] for field in config["index_fields"]],
                    ["id", "resource_type_id", "system_id"],
                )
                self.assertNotIn("key_fields", config)
