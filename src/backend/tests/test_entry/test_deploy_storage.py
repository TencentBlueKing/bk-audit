"""严格部署输入只在显式入口生效，不探测三方平台。"""
import json
import os
from copy import deepcopy
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from apps.meta.models import GlobalMetaConfig, Namespace
from services.web.bkbase.exceptions import BKBaseResourceMappingError


def deployment_env(version="v4"):
    """测试声明均为合成值，不包含现场资源。"""

    def ref(kind, name):
        return {"kind": kind, "tenant": "tenant_a", "namespace": "clusters", "name": name}

    storages = {
        kind: {"cluster_id": name, **({"ref": ref(ref_kind, name)} if version == "v4" else {})}
        for kind, ref_kind, name in (("kafka", "Kafka", "queue"), ("hdfs", "Hdfs", "hdfs"))
    }
    return {
        "BKAPP_INIT_SYSTEM": "true",
        "BKAPP_INIT_STRATEGY_STORAGE_CONFIG": json.dumps({"default": storages}),
        "BKAPP_INIT_KAFKA_CONFIG": json.dumps({"bootstrap_servers": ["kafka.example:9092"], "group_id": "audit"}),
        "BKAPP_INIT_ES_CONFIG": json.dumps(
            [
                {
                    "namespace": "default",
                    "pre_defined": True,
                    "pre_defined_extra_config": {"cluster_id": 11, "bkbase_cluster_id": "es"},
                }
            ]
        ),
        "BKAPP_INIT_DORIS_CONFIG": json.dumps(
            [
                {
                    "namespace": "default",
                    "pre_defined": True,
                    "pre_defined_extra_config": {"bkbase_cluster_id": "doris"},
                }
            ]
        ),
        "BKAPP_INIT_REDIS_CONFIG": json.dumps(
            [
                {
                    "namespace": "default",
                    "redis_name_en": "redis",
                    "redis_name": "redis",
                    "version": "6",
                    "connection_info": {"host": "redis.example", "port": 6379, "password": "synthetic"},
                }
            ]
        ),
        "BKAPP_INIT_BKBASE_V4_CONFIG": json.dumps(
            {
                "default": {
                    "storage_refs": {
                        "es": {"es": ref("ElasticSearch", "es")},
                        "doris": {"doris": ref("Doris", "doris")},
                    },
                    "flow_config": {"operation_config": {}},
                }
            }
        ),
    }


@override_settings(
    BKBASE_API_VERSION="v4",
    BKBASE_V4_TENANT="tenant_a",
    BKBASE_V4_NAMESPACE="audit",
    BKBASE_V4_STREAM_CLUSTER="StreamCluster/audit/primary",
    ASSET_RT_STORAGE_CLUSTER="hdfs",
    BKAPP_ENABLE_ITSM_V4=False,
)
class StrictDeployPreflightTests(SimpleTestCase):
    def setUp(self):
        self.env = deployment_env()
        self.enterContext(mock.patch.dict(os.environ, self.env))
        self.enterContext(
            mock.patch("requests.sessions.Session.request", side_effect=AssertionError("Unexpected HTTP"))
        )

    def test_check_only_does_not_read_db_or_call_platform(self):
        call_command("init_system", strict=True, check_only=True)

    def test_first_install_requires_refs_in_declaration_before_db(self):
        for kind, cluster_id in (("es", "es"), ("doris", "doris"), ("hdfs", "asset-hdfs")):
            with self.subTest(kind=kind), override_settings(
                ASSET_RT_STORAGE_CLUSTER="asset-hdfs" if kind == "hdfs" else "hdfs"
            ):
                config = json.loads(self.env["BKAPP_INIT_BKBASE_V4_CONFIG"])
                config["default"]["storage_refs"].pop(kind, None)
                os.environ["BKAPP_INIT_BKBASE_V4_CONFIG"] = json.dumps(config)
                with self.assertRaisesRegex(CommandError, rf"space=default, field=storage_refs\.{kind}\.{cluster_id}"):
                    call_command("init_system", "--strict", "--check-only", "--first-install")
                # 常规预检不查库，允许后续阶段复用原绑定。
                call_command("init_system", strict=True, check_only=True)

    def test_first_install_reuses_strategy_hdfs_ref(self):
        call_command("init_system", "--strict", "--check-only", "--first-install")

    def test_first_install_accepts_independent_asset_hdfs_ref(self):
        config = json.loads(self.env["BKAPP_INIT_BKBASE_V4_CONFIG"])
        config["default"]["storage_refs"]["hdfs"] = {
            "asset-hdfs": {"kind": "Hdfs", "tenant": "tenant_a", "namespace": "clusters", "name": "asset-hdfs"}
        }
        os.environ["BKAPP_INIT_BKBASE_V4_CONFIG"] = json.dumps(config)
        with override_settings(ASSET_RT_STORAGE_CLUSTER="asset-hdfs"):
            call_command("init_system", "--strict", "--check-only", "--first-install")

    def test_first_install_uses_stream_environment_without_flow_profile(self):
        config = json.loads(self.env["BKAPP_INIT_BKBASE_V4_CONFIG"])
        del config["default"]["flow_config"]
        os.environ["BKAPP_INIT_BKBASE_V4_CONFIG"] = json.dumps(config)
        call_command("init_system", "--strict", "--check-only", "--first-install")

    @override_settings(BKBASE_V4_STREAM_CLUSTER="")
    def test_first_install_requires_stream_cluster_before_db(self):
        with self.assertRaisesRegex(CommandError, "BKAPP_BKBASE_V4_STREAM_CLUSTER"):
            call_command("init_system", "--strict", "--check-only", "--first-install")

    @override_settings(BKBASE_V4_STREAM_CLUSTER="")
    def test_first_install_allows_declared_legacy_stream_cluster(self):
        config = json.loads(self.env["BKAPP_INIT_BKBASE_V4_CONFIG"])
        config["default"]["flow_config"]["operation_config"]["stream_sql_deploy_config"] = {
            "cluster": "StreamCluster/audit/legacy"
        }
        os.environ["BKAPP_INIT_BKBASE_V4_CONFIG"] = json.dumps(config)
        call_command("init_system", "--strict", "--check-only", "--first-install")

    def test_first_install_flag_cannot_run_initialization_phase(self):
        with self.assertRaisesRegex(CommandError, "--first-install requires --strict --check-only"):
            call_command("init_system", "--strict", "--phase", "bootstrap", "--first-install")

    def test_strict_rejects_missing_kafka_or_hdfs_before_write(self):
        for version in ("v3", "v4"):
            for storage in ("kafka", "hdfs"):
                for value in (None, {}, {"cluster_id": ""}):
                    config = json.loads(deployment_env(version)["BKAPP_INIT_STRATEGY_STORAGE_CONFIG"])
                    if value is None:
                        config["default"].pop(storage)
                    else:
                        config["default"][storage] = value
                    with self.subTest(version=version, storage=storage, value=value), override_settings(
                        BKBASE_API_VERSION=version
                    ):
                        os.environ["BKAPP_INIT_STRATEGY_STORAGE_CONFIG"] = json.dumps(config)
                        with self.assertRaises(CommandError) as caught:
                            call_command("init_system", strict=True, check_only=True)
                        self.assertIn("BKAPP_INIT_STRATEGY_STORAGE_CONFIG", str(caught.exception))
                        self.assertIn(storage, str(caught.exception))

    def test_strict_v4_rejects_managed_es_before_write(self):
        os.environ["BKAPP_INIT_ES_CONFIG"] = json.dumps([{"namespace": "default", "pre_defined": False}])
        with self.assertRaises(CommandError) as caught:
            call_command("init_system", strict=True, check_only=True)
        self.assertIn("BKAPP_INIT_ES_CONFIG", str(caught.exception))

    def test_strict_disabled_fails_but_legacy_still_skips(self):
        os.environ["BKAPP_INIT_SYSTEM"] = "false"
        with self.assertRaises(CommandError):
            call_command("init_system", strict=True, check_only=True)
        call_command("init_system")

    def test_wrong_tenant_and_consumer_protocol_missing_fields_are_rejected(self):
        mapping = json.loads(self.env["BKAPP_INIT_BKBASE_V4_CONFIG"])
        mapping["default"]["storage_refs"]["es"]["es"]["tenant"] = "other"
        os.environ["BKAPP_INIT_BKBASE_V4_CONFIG"] = json.dumps(mapping)
        with self.assertRaises(CommandError):
            call_command("init_system", strict=True, check_only=True)
        os.environ["BKAPP_INIT_BKBASE_V4_CONFIG"] = self.env["BKAPP_INIT_BKBASE_V4_CONFIG"]
        os.environ["BKAPP_INIT_KAFKA_CONFIG"] = json.dumps(
            {"bootstrap_servers": "kafka.example:9092", "group_id": "audit", "security_protocol": "SASL_PLAINTEXT"}
        )
        with self.assertRaises(CommandError) as caught:
            call_command("init_system", strict=True, check_only=True)
        self.assertIn("BKAPP_INIT_KAFKA_CONFIG", str(caught.exception))

    def test_strict_v4_write_refs_and_supplemental_ref_fields_are_required(self):
        original = deployment_env()
        for kind in ("kafka", "hdfs"):
            config = json.loads(original["BKAPP_INIT_STRATEGY_STORAGE_CONFIG"])
            config["default"][kind].pop("ref")
            os.environ["BKAPP_INIT_STRATEGY_STORAGE_CONFIG"] = json.dumps(config)
            with self.assertRaises(CommandError):
                call_command("init_system", strict=True, check_only=True)
        os.environ.update(original)
        for value in (None, 1, "", " "):
            config = json.loads(original["BKAPP_INIT_BKBASE_V4_CONFIG"])
            config["default"]["storage_refs"]["es"]["es"]["name"] = value
            os.environ["BKAPP_INIT_BKBASE_V4_CONFIG"] = json.dumps(config)
            with self.assertRaises(CommandError):
                call_command("init_system", strict=True, check_only=True)

    def test_redis_outside_declared_spaces_and_missing_fallback_candidate_are_rejected(self):
        redis = json.loads(self.env["BKAPP_INIT_REDIS_CONFIG"])
        redis[0]["namespace"] = "outside"
        os.environ["BKAPP_INIT_REDIS_CONFIG"] = json.dumps(redis)
        with self.assertRaises(CommandError) as caught:
            call_command("init_system", strict=True, check_only=True)
        self.assertIn("BKAPP_INIT_REDIS_CONFIG", str(caught.exception))

    def test_explicit_snapshot_redis_refs_do_not_require_default_candidate(self):
        # 非默认审计空间可登记 Redis；当前 IAM 快照使用明确 Ref 时不要求额外造一个 default 候选。
        config = json.loads(self.env["BKAPP_INIT_STRATEGY_STORAGE_CONFIG"])
        config["other"] = deepcopy(config["default"])
        os.environ["BKAPP_INIT_STRATEGY_STORAGE_CONFIG"] = json.dumps(config)
        for env in ("BKAPP_INIT_ES_CONFIG", "BKAPP_INIT_DORIS_CONFIG"):
            values = json.loads(self.env[env])
            values.append({**deepcopy(values[0]), "namespace": "other"})
            os.environ[env] = json.dumps(values)
        v4 = json.loads(self.env["BKAPP_INIT_BKBASE_V4_CONFIG"])
        v4["other"] = deepcopy(v4["default"])
        os.environ["BKAPP_INIT_BKBASE_V4_CONFIG"] = json.dumps(v4)
        redis = json.loads(self.env["BKAPP_INIT_REDIS_CONFIG"])
        redis[0]["namespace"] = "other"
        os.environ["BKAPP_INIT_REDIS_CONFIG"] = json.dumps(redis)
        with self.assertRaises(CommandError):
            call_command("init_system", strict=True, check_only=True)
        ref = {"kind": "Redis", "tenant": "tenant_a", "namespace": "clusters", "name": "redis"}
        with override_settings(
            BKBASE_V4_SYSTEM_SNAPSHOT_CREATE={"action": {"redis": ref}, "resource_type": {"redis": ref}},
            SNAPSHOT_USERINFO_RESOURCE_URL="",
        ):
            call_command("init_system", strict=True, check_only=True)
            os.environ["BKAPP_INIT_REDIS_CONFIG"] = "[]"
            call_command("init_system", strict=True, check_only=True)
        with override_settings(
            BKBASE_V4_SYSTEM_SNAPSHOT_CREATE={"action": {"redis": ref}, "resource_type": {"redis": ref}},
            SNAPSHOT_USERINFO_RESOURCE_URL="https://users.example",
        ):
            with self.assertRaises(CommandError):
                call_command("init_system", strict=True, check_only=True)
        with override_settings(
            BKBASE_V4_SYSTEM_SNAPSHOT_CREATE={kind: {"redis": ref} for kind in ("action", "resource_type", "user")},
            SNAPSHOT_USERINFO_RESOURCE_URL="https://users.example",
        ):
            call_command("init_system", strict=True, check_only=True)

    def test_v3_multiple_redis_declarations_still_allowed(self):
        redis = json.loads(self.env["BKAPP_INIT_REDIS_CONFIG"])
        redis.append({**deepcopy(redis[0]), "redis_name_en": "redis_two"})
        os.environ.update(deployment_env("v3"))
        os.environ["BKAPP_INIT_REDIS_CONFIG"] = json.dumps(redis)
        with override_settings(BKBASE_API_VERSION="v3"):
            call_command("init_system", strict=True, check_only=True)


@override_settings(
    BKBASE_API_VERSION="v4",
    BKBASE_V4_TENANT="tenant_a",
    BKBASE_V4_NAMESPACE="audit",
    ASSET_RT_STORAGE_CLUSTER="hdfs",
    BKAPP_ENABLE_ITSM_V4=False,
)
class DeployStorageImportTests(TestCase):
    def setUp(self):
        self.enterContext(mock.patch.dict(os.environ, deployment_env()))
        self.enterContext(
            mock.patch("requests.sessions.Session.request", side_effect=AssertionError("Unexpected HTTP"))
        )

    def apply(self):
        from services.web.entry.init.deploy_storage import validate_deployment

        validate_deployment().apply()

    def read(self, key):
        return GlobalMetaConfig.get(key, config_level="namespace", instance_key="default", default=None)

    def test_complete_storage_input_adds_no_remote_probes(self):
        self.apply()
        self.assertEqual(self.read("default_cluster_id"), 11)
        self.assertEqual(self.read("default_queue_storage_cluster"), "queue")
        self.assertEqual(self.read("default_hdfs_storage_cluster"), "hdfs")
        self.assertEqual(self.read("default_replica_write_cluster_id"), {"bkbase_cluster_id": "doris"})
        self.assertEqual(self.read("bkbase_v4_flow_config"), {"operation_config": {}})
        self.assertEqual(self.read("bkbase_v4_storage_clusters")["es"]["es"]["name"], "es")
        self.assertTrue(Namespace.objects.filter(namespace="default").exists())

    def test_same_storage_refs_reused_and_conflicts_rollback(self):
        self.apply()
        original = deepcopy(self.read("bkbase_v4_storage_clusters"))
        self.apply()
        self.assertEqual(self.read("bkbase_v4_storage_clusters"), original)
        GlobalMetaConfig.objects.filter(config_key="default_queue_storage_cluster").delete()
        changed = deepcopy(original)
        changed["doris"]["doris"]["name"] = "other"
        GlobalMetaConfig.set("bkbase_v4_storage_clusters", changed, config_level="namespace", instance_key="default")
        with self.assertRaises(BKBaseResourceMappingError):
            self.apply()
        self.assertIsNone(self.read("default_queue_storage_cluster"))
        self.assertEqual(self.read("bkbase_v4_storage_clusters"), changed)

    def test_redeploy_reuses_refs_already_registered(self):
        self.apply()
        previous = deepcopy(self.read("bkbase_v4_storage_clusters"))
        config = json.loads(os.environ["BKAPP_INIT_BKBASE_V4_CONFIG"])
        del config["default"]["storage_refs"]
        os.environ["BKAPP_INIT_BKBASE_V4_CONFIG"] = json.dumps(config)
        self.apply()
        self.assertEqual(self.read("bkbase_v4_storage_clusters"), previous)

    def test_redeploy_without_flow_profile_preserves_registered_configuration(self):
        self.apply()
        legacy = {"operation_config": {"stream_sql_deploy_config": {"cluster": "StreamCluster/audit/legacy"}}}
        GlobalMetaConfig.set("bkbase_v4_flow_config", legacy, config_level="namespace", instance_key="default")
        os.environ.pop("BKAPP_INIT_BKBASE_V4_CONFIG")
        self.apply()
        self.assertEqual(self.read("bkbase_v4_flow_config"), legacy)

    def test_asset_hdfs_reuses_strategy_ref_when_same_id(self):
        self.apply()
        self.assertEqual(
            self.read("bkbase_v4_storage_clusters")["hdfs"],
            {"hdfs": {"kind": "Hdfs", "tenant": "tenant_a", "namespace": "clusters", "name": "hdfs"}},
        )

    def test_missing_ref_and_empty_existing_defaults_are_not_adopted(self):
        mapping = json.loads(os.environ["BKAPP_INIT_BKBASE_V4_CONFIG"])
        mapping["default"]["storage_refs"].pop("es")
        os.environ["BKAPP_INIT_BKBASE_V4_CONFIG"] = json.dumps(mapping)
        with self.assertRaises(BKBaseResourceMappingError):
            self.apply()
        self.assertIsNone(self.read("default_queue_storage_cluster"))
        os.environ.update(deployment_env())
        GlobalMetaConfig.set("default_hdfs_storage_cluster", "", config_level="namespace", instance_key="default")
        with self.assertRaises(BKBaseResourceMappingError):
            self.apply()
        self.assertEqual(self.read("default_hdfs_storage_cluster"), "")
