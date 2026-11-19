"""存储列表保留 V3 默认周期，并保持 V4 缺失周期的原始语义。"""
from unittest import mock

from django.test import SimpleTestCase, override_settings

from api.bk_log.constants import DEFAULT_RETENTION
from services.web.databus.storage.resources import StorageListResource


class StorageListVersionDefaultsTests(SimpleTestCase):
    def test_empty_setup_config_through_storage_list_request(self):
        row = {
            "cluster_config": {
                "cluster_id": 11,
                "cluster_name": "fixture",
                "domain_name": "storage.example.test",
                "port": 9200,
                "schema": "http",
                "custom_option": {
                    "bk_biz_id": 2,
                    "hot_warm_config": {"is_enabled": False},
                    "source_type": "es",
                    "setup_config": {},
                    "admin": [],
                    "description": "fixture",
                    "visible_config": {},
                },
                "creator": "fixture",
                "create_time": "2026-01-01T00:00:00Z",
            },
            "auth_info": {"username": "", "password": ""},
            "bk_biz_id": 2,
        }
        for version in ("v3", "v4"):
            with self.subTest(version=version), override_settings(BKBASE_API_VERSION=version):
                resource = StorageListResource()
                with mock.patch.object(resource, "perform_request", return_value=[row]):
                    response = resource.request({"namespace": "default"})
                setup = response[0]["cluster_config"]["custom_option"]["setup_config"]
                if version == "v3":
                    self.assertEqual(setup["retention_days_default"], DEFAULT_RETENTION)
                    self.assertEqual(setup["retention_days_max"], DEFAULT_RETENTION)
                else:
                    self.assertNotIn("retention_days_default", setup)
                    self.assertNotIn("retention_days_max", setup)
