"""部署策略存储输入只补缺，使用隔离数据库且禁止远端请求。"""
import json
import os
from copy import deepcopy
from unittest import mock

from django.test import TestCase, override_settings

from apps.meta.models import GlobalMetaConfig
from services.web.bkbase.exceptions import BKBaseResourceMappingError


@override_settings(BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit")
class InitStrategyStorageTests(TestCase):
    keys = ("default_queue_storage_cluster", "default_hdfs_storage_cluster", "bkbase_v4_storage_clusters")

    def setUp(self):
        self.enterContext(
            mock.patch("requests.sessions.Session.request", side_effect=AssertionError("Unexpected HTTP"))
        )
        self.enterContext(mock.patch.dict(os.environ, {}, clear=False))
        os.environ.pop("BKAPP_INIT_STRATEGY_STORAGE_CONFIG", None)
        self.hdfs_ref = {"kind": "Hdfs", "tenant": "tenant_a", "namespace": "clusters", "name": "hdfs_main"}
        self.config = {
            "default": {
                "kafka": {"cluster_id": "audit-queue"},
                "hdfs": {"cluster_id": "audit-hdfs", "ref": self.hdfs_ref},
            }
        }

    def run_import(self, config=None):
        from services.web.entry.init.strategy_storage import init_strategy_storage

        if config is not None:
            os.environ["BKAPP_INIT_STRATEGY_STORAGE_CONFIG"] = json.dumps(config)
        init_strategy_storage()

    def read(self, key, space="default", default=None):
        return GlobalMetaConfig.get(key, config_level="namespace", instance_key=space, default=default)

    def save(self, key, value):
        GlobalMetaConfig.set(key, value, config_level="namespace", instance_key="default")

    def test_import_seeds_missing_config_once_and_only_in_its_namespace(self):
        self.run_import(self.config)
        self.assertEqual(self.read(self.keys[0]), "audit-queue")
        self.assertEqual(self.read(self.keys[1]), "audit-hdfs")
        self.assertEqual(self.read(self.keys[2]), {"hdfs": {"audit-hdfs": self.hdfs_ref}})
        self.assertIsNone(self.read(self.keys[1], "other"))
        changed = deepcopy(self.config)
        changed["default"]["hdfs"]["cluster_id"] = "different-hdfs"
        changed["default"]["kafka"]["cluster_id"] = "different-queue"
        self.run_import(changed)
        self.assertEqual(self.read(self.keys[0]), "audit-queue")
        self.assertEqual(self.read(self.keys[1]), "audit-hdfs")
        self.assertEqual(self.read(self.keys[2]), {"hdfs": {"audit-hdfs": self.hdfs_ref}})

    def test_import_preserves_existing_defaults_and_refs(self):
        for existing_id in ("", None, "other-hdfs", "audit-hdfs"):
            for mapping in (
                {"doris": {"old": {"name": "leave-alone"}}},
                {"hdfs": {"audit-hdfs": None}, "es": {"old": "leave-alone"}},
                {"hdfs": {"audit-hdfs": {**self.hdfs_ref, "name": "existing-hdfs"}}},
            ):
                with self.subTest(existing_id=existing_id, mapping=mapping):
                    GlobalMetaConfig.objects.filter(config_key__in=self.keys).delete()
                    self.save(self.keys[0], "")
                    self.save(self.keys[1], existing_id)
                    self.save(self.keys[2], deepcopy(mapping))
                    self.run_import(self.config)
                    self.assertEqual(self.read(self.keys[0]), "")
                    self.assertEqual(self.read(self.keys[1]), existing_id)
                    expected = deepcopy(mapping)
                    if existing_id == "audit-hdfs":
                        expected.setdefault("hdfs", {}).setdefault("audit-hdfs", self.hdfs_ref)
                    self.assertEqual(self.read(self.keys[2]), expected)

    def test_import_rejects_wrong_tenant_before_any_write(self):
        config = deepcopy(self.config)
        config["default"]["hdfs"]["ref"]["tenant"] = "other"
        with self.assertRaises(BKBaseResourceMappingError) as caught:
            self.run_import(config)
        self.assertIn("BKAPP_INIT_STRATEGY_STORAGE_CONFIG", str(caught.exception))
        self.assertFalse(GlobalMetaConfig.objects.filter(config_key__in=self.keys).exists())

    def test_import_rejects_invalid_shape_before_any_write(self):
        for config in (
            [],
            {"default": []},
            {"default": {"redis": {"cluster_id": "x"}}},
            {"default": {"kafka": {"cluster_id": ""}}},
            {"default": {"kafka": {"cluster_id": 1}}},
            {"default": {"hdfs": {"cluster_id": "x", "ref": []}}},
            {"default": {"hdfs": {"cluster_id": "x", "ref": {**self.hdfs_ref, "name": " "}}}},
            {"default": {"hdfs": {"cluster_id": "x", "ref": {**self.hdfs_ref, "kind": "Kafka"}}}},
        ):
            with self.subTest(config=config), self.assertRaises(BKBaseResourceMappingError):
                self.run_import(config)
            self.assertFalse(GlobalMetaConfig.objects.filter(config_key__in=self.keys).exists())

    def test_import_rejects_space_with_surrounding_whitespace(self):
        for space in (" default", "default "):
            with self.subTest(space=space):
                with self.assertRaises(BKBaseResourceMappingError):
                    self.run_import({space: self.config["default"]})
                self.assertFalse(GlobalMetaConfig.objects.filter(config_key__in=self.keys).exists())

    def test_import_preserves_unmergeable_mapping(self):
        for mapping in (None, "", [], {"hdfs": None}, {"hdfs": []}):
            with self.subTest(mapping=mapping):
                GlobalMetaConfig.objects.filter(config_key__in=self.keys).delete()
                self.save(self.keys[2], mapping)
                self.run_import(self.config)
                self.assertEqual(self.read(self.keys[2]), mapping)
                self.assertEqual(self.read(self.keys[1]), "audit-hdfs")

    def test_import_fills_ref_for_legacy_integer_id_without_changing_its_type(self):
        for old_value, cluster_id, expected in (
            (7, "7", True),
            (0, "0", True),
            (None, "None", False),
            (False, "False", False),
            (True, "True", False),
            (7.5, "7.5", False),
        ):
            with self.subTest(old_value=old_value):
                GlobalMetaConfig.objects.filter(config_key__in=self.keys).delete()
                self.save(self.keys[1], old_value)
                self.run_import({"default": {"hdfs": {"cluster_id": cluster_id, "ref": self.hdfs_ref}}})
                self.assertEqual(self.read(self.keys[1]), old_value)
                self.assertIs(type(self.read(self.keys[1])), type(old_value))
                self.assertEqual(self.read(self.keys[2]), {"hdfs": {cluster_id: self.hdfs_ref}} if expected else None)

    def test_import_v3_id_only_and_empty_env_is_noop(self):
        self.run_import()
        self.assertFalse(GlobalMetaConfig.objects.filter(config_key__in=self.keys).exists())
        self.run_import({})
        self.assertFalse(GlobalMetaConfig.objects.filter(config_key__in=self.keys).exists())
        with override_settings(BKBASE_API_VERSION="v3"):
            self.run_import({"default": {"kafka": {"cluster_id": "queue-v3"}, "hdfs": {"cluster_id": "hdfs-v3"}}})
        self.assertEqual(self.read(self.keys[0]), "queue-v3")
        self.assertEqual(self.read(self.keys[1]), "hdfs-v3")
        self.assertIsNone(self.read(self.keys[2]))
