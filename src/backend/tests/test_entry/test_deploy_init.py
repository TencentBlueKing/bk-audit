"""严格两段初始化的依赖边界和续跑行为。"""
import os
from unittest import mock

from bk_resource import resource
from django.conf import settings
from django.test import TestCase, override_settings

from apps.meta.models import GlobalMetaConfig
from apps.meta.utils.builtin_assets import get_builtin_asset_system_id
from apps.permission.handlers.resource_types import ResourceEnum
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.constants import (
    COLLECTOR_PLUGIN_ID,
    DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY,
    PluginSceneChoices,
)
from services.web.databus.models import CollectorPlugin, Snapshot
from services.web.entry.constants import INIT_SYSTEM_RULE_AUDIT_STRATEGY_ID_KEY
from services.web.entry.init.base import SystemInitHandler
from services.web.strategy_v2.constants import (
    StrategySource,
    StrategyStatusChoices,
    StrategyType,
)
from services.web.strategy_v2.models import Strategy
from tests.test_entry.test_deploy_storage import deployment_env


@override_settings(
    BKBASE_API_VERSION="v4",
    BKBASE_V4_TENANT="tenant_a",
    BKBASE_V4_NAMESPACE="audit",
    ASSET_RT_STORAGE_CLUSTER="hdfs",
    BKAPP_ENABLE_ITSM_V4=False,
)
class StrictDeployInitTests(TestCase):
    def setUp(self):
        self.enterContext(mock.patch.dict(os.environ, deployment_env()))
        self.enterContext(
            mock.patch("requests.sessions.Session.request", side_effect=AssertionError("Unexpected HTTP"))
        )
        from services.web.entry.init.deploy import StrictSystemInit
        from services.web.entry.init.deploy_storage import validate_deployment

        self.handler = SystemInitHandler()
        self.init = StrictSystemInit(self.handler, validate_deployment())

    def plugin(self, plugin_id, scene):
        return CollectorPlugin.objects.create(
            namespace=settings.DEFAULT_NAMESPACE,
            collector_plugin_id=plugin_id,
            plugin_scene=scene,
            collector_plugin_name=f"test-{plugin_id}",
            collector_plugin_name_en=f"test_{plugin_id}",
            bkdata_biz_id=1,
            table_id=0,
            index_set_id=0,
        )

    def test_bootstrap_does_not_call_current_release_api_or_wait_for_puller(self):
        forbidden = ("init_snapshot", "init_asset", "init_event", "init_system_rule_audit", "init_es", "init_doris")
        calls = [
            self.enterContext(mock.patch.object(self.handler, method, side_effect=AssertionError(method)))
            for method in forbidden
        ]
        with mock.patch.object(self.handler, "init_redis"), mock.patch.object(
            self.handler, "init_standard_fields"
        ), mock.patch.object(self.handler, "init_global_meta_config"):
            self.init.bootstrap()
        self.assertEqual(GlobalMetaConfig.get("event_es_cluster_id"), 11)
        self.assertFalse(any(call.called for call in calls))

    def test_finalize_initializes_both_bklog_plugins_and_reuses_saved_ids(self):
        regular = self.plugin(101, PluginSceneChoices.COLLECTOR)
        GlobalMetaConfig.set(
            COLLECTOR_PLUGIN_ID,
            regular.collector_plugin_id,
            config_level="namespace",
            instance_key=settings.DEFAULT_NAMESPACE,
        )
        self.plugin(102, PluginSceneChoices.EVENT)
        with mock.patch(
            "services.web.entry.init.deploy.resource.databus.collector_plugin.create_plugin"
        ) as create, mock.patch.object(self.handler, "init_event") as create_event:
            self.assertEqual([p.collector_plugin_id for p in self.init.ensure_plugins()], [101, 102])
        create.assert_not_called()
        create_event.assert_not_called()
        regular.delete()
        with self.assertRaises(BKBaseResourceMappingError):
            self.init.ensure_plugins()

    def test_finalize_retries_unknown_bklog_create_only_without_saved_id(self):
        with mock.patch(
            "services.web.entry.init.deploy.resource.databus.collector_plugin.create_plugin",
            side_effect=TimeoutError("lost response"),
        ):
            with self.assertRaises(TimeoutError):
                self.init.ensure_plugins()
        self.assertFalse(CollectorPlugin.objects.exists())

        def create(**kwargs):
            self.plugin(201, PluginSceneChoices.COLLECTOR)
            GlobalMetaConfig.set(
                COLLECTOR_PLUGIN_ID, 201, config_level="namespace", instance_key=settings.DEFAULT_NAMESPACE
            )

        def event():
            self.plugin(202, PluginSceneChoices.EVENT)

        with mock.patch(
            "services.web.entry.init.deploy.resource.databus.collector_plugin.create_plugin", side_effect=create
        ), mock.patch("services.web.entry.init.deploy.EventHandler.update_or_create_rt", side_effect=event), mock.patch(
            "services.web.entry.init.deploy.EventHandler.__init__", return_value=None
        ):
            self.assertEqual([p.collector_plugin_id for p in self.init.ensure_plugins()], [201, 202])

    def test_finalize_waits_for_event_storage_and_manual_snapshot_before_default_flow(self):
        plugin = self.plugin(301, PluginSceneChoices.EVENT)
        plugin.bkbase_v4_resources = {"ready": True}
        plugin.has_storage = True
        plugin.save()
        Snapshot.objects.create(
            system_id=get_builtin_asset_system_id(),
            resource_type_id=ResourceEnum.MANUAL_EVENT.id,
            status="running",
            bkbase_table_id="manual_rt",
            join_data_type="asset",
        )
        with mock.patch.object(self.handler, "init_system_rule_audit", side_effect=AssertionError("too early")):
            self.assertIn("event physical table", self.init.rule_pending())

    def test_finalize_required_failure_is_not_success(self):
        Snapshot.objects.create(
            system_id=get_builtin_asset_system_id(),
            resource_type_id=ResourceEnum.RISK.id,
            status="failed",
            join_data_type="asset",
            status_msg="synthetic rejected",
        )
        with self.assertRaises(BKBaseResourceMappingError):
            self.init.assets_pending()

    def test_manual_snapshot_not_running_blocks_even_when_old_flow_marker_exists(self):
        plugin = self.plugin(401, PluginSceneChoices.EVENT)
        plugin.has_storage = True
        plugin.bkbase_v4_resources = {"ready": True}
        plugin.save()
        GlobalMetaConfig.set(
            DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY,
            "events",
            config_level="namespace",
            instance_key=settings.DEFAULT_NAMESPACE,
        )
        with mock.patch.object(
            self.handler, "init_system_rule_audit", side_effect=AssertionError("manual snapshot missing")
        ):
            self.assertIn("manual event snapshot", self.init.rule_pending())

    def test_plugin_hard_error_is_raised_only_for_strict_caller(self):
        from services.web.databus.collector_plugin.handlers import PluginEtlHandler

        plugin = self.plugin(501, PluginSceneChoices.COLLECTOR)
        with mock.patch(
            "services.web.bkbase.clean._configure_plugin",
            side_effect=BKBaseResourceMappingError(message="synthetic API rejection"),
        ):
            self.assertIsNone(PluginEtlHandler(plugin=plugin).create_or_update())
            with self.assertRaises(BKBaseResourceMappingError):
                self.init.plugins_pending([plugin])

    def test_strict_asset_creation_error_is_propagated_without_changing_legacy(self):
        with mock.patch.object(self.handler, "_precheck_builtin_assets"), mock.patch(
            "services.web.entry.init.base.resource.databus.collector.toggle_join_data",
            side_effect=BKBaseResourceMappingError(message="synthetic 404"),
        ):
            self.handler.init_asset()
            with self.assertRaises(BKBaseResourceMappingError):
                self.handler.init_asset(strict=True)

    def test_finalize_resumes_same_binding_after_callback_ready(self):
        from apps.meta.utils.builtin_assets import BUILTIN_ASSET_RESOURCE_TYPES

        self.init.deployment.apply()
        for plugin_id, scene in ((601, PluginSceneChoices.COLLECTOR), (602, PluginSceneChoices.EVENT)):
            plugin = self.plugin(plugin_id, scene)
            plugin.has_storage = True
            plugin.bkbase_v4_resources = {"ready": True}
            plugin.save()
        GlobalMetaConfig.set(
            COLLECTOR_PLUGIN_ID, 601, config_level="namespace", instance_key=settings.DEFAULT_NAMESPACE
        )
        GlobalMetaConfig.set(
            DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY,
            "events",
            config_level="namespace",
            instance_key=settings.DEFAULT_NAMESPACE,
        )
        for asset in BUILTIN_ASSET_RESOURCE_TYPES:
            Snapshot.objects.create(
                system_id=get_builtin_asset_system_id(),
                resource_type_id=asset.id,
                status="running",
                bkbase_table_id=f"rt_{asset.id}",
                join_data_type="asset",
            )
        strategy = Strategy.objects.create(
            strategy_name="registered default",
            namespace=settings.DEFAULT_NAMESPACE,
            strategy_type=StrategyType.RULE,
            source=StrategySource.SYSTEM,
            status=StrategyStatusChoices.STARTING,
            configs={"data_source": {"rt_id": f"rt_{ResourceEnum.MANUAL_EVENT.id}"}},
        )
        GlobalMetaConfig.set(INIT_SYSTEM_RULE_AUDIT_STRATEGY_ID_KEY, strategy.strategy_id)

        def worker_tick(_seconds):
            Strategy.objects.filter(pk=strategy.pk).update(status=StrategyStatusChoices.RUNNING)

        with mock.patch.object(self.handler, "init_snapshot"), mock.patch.object(
            self.handler, "init_system"
        ), mock.patch.object(self.handler, "init_asset"), mock.patch(
            "services.web.databus.collector_plugin.handlers.PluginEtlHandler.create_or_update",
            return_value={"task_state": "running"},
        ), mock.patch(
            "services.web.entry.init.v4_wait.sleep", side_effect=worker_tick
        ):
            self.init.finalize()
            self.init.finalize()
        self.assertEqual(
            list(CollectorPlugin.objects.order_by("collector_plugin_id").values_list("collector_plugin_id", flat=True)),
            [601, 602],
        )
        self.assertEqual(Strategy.objects.count(), 1)
        self.assertEqual(GlobalMetaConfig.get(INIT_SYSTEM_RULE_AUDIT_STRATEGY_ID_KEY), strategy.strategy_id)

    def test_strict_reuses_preparing_asset_without_acceptance_marker(self):
        Snapshot.objects.create(
            system_id=get_builtin_asset_system_id(),
            resource_type_id=ResourceEnum.RISK.id,
            status="preparing",
            join_data_type="asset",
        )

        def toggle(params):
            if params["resource_type_id"] == ResourceEnum.RISK.id:
                raise AssertionError("原资产仍在初始化，不得再次 toggle")

        with mock.patch.object(self.handler, "_precheck_builtin_assets"), mock.patch(
            "services.web.entry.init.base.resource.databus.collector.toggle_join_data", side_effect=toggle
        ):
            self.handler.init_asset(strict=True)
        self.assertEqual(Snapshot.objects.filter(resource_type_id=ResourceEnum.RISK.id).count(), 1)

    def test_first_collector_index_failure_rolls_back_local_plugin_binding(self):
        plugin_resource = type(resource.databus.collector_plugin.create_plugin)

        built = {
            "collector_plugin_name": "synthetic",
            "collector_plugin_name_en": "synthetic",
            "retention": 7,
            "allocation_min_days": 0,
            "storage_replies": 1,
            "storage_shards_nums": 1,
            "storage_shards_size": 1,
        }
        with mock.patch.object(plugin_resource, "build_in_config", return_value=built), mock.patch(
            "services.web.databus.collector_plugin.resources.api.bk_log.create_collector_plugin",
            return_value={"collector_plugin_id": 701, "collector_plugin_name": "synthetic"},
        ), mock.patch.object(plugin_resource, "replace_index_set", side_effect=RuntimeError("synthetic index failure")):
            with self.assertRaises(RuntimeError):
                self.init.ensure_plugins()
        self.assertFalse(CollectorPlugin.objects.filter(collector_plugin_id=701).exists())
        self.assertIsNone(
            GlobalMetaConfig.get(
                COLLECTOR_PLUGIN_ID, config_level="namespace", instance_key=settings.DEFAULT_NAMESPACE, default=None
            )
        )

    def test_bootstrap_explicit_snapshot_refs_skip_missing_redis_declaration(self):
        from services.web.entry.init.deploy import StrictSystemInit
        from services.web.entry.init.deploy_storage import validate_deployment

        ref = {"kind": "Redis", "tenant": "tenant_a", "namespace": "clusters", "name": "redis"}
        os.environ.pop("BKAPP_INIT_REDIS_CONFIG", None)
        with override_settings(
            BKBASE_V4_SYSTEM_SNAPSHOT_CREATE={kind: {"redis": ref} for kind in ("action", "resource_type")},
            SNAPSHOT_USERINFO_RESOURCE_URL="",
        ), mock.patch.object(self.handler, "init_redis", side_effect=AssertionError("无需注册额外 Redis")), mock.patch.object(
            self.handler, "init_standard_fields"
        ), mock.patch.object(
            self.handler, "init_global_meta_config"
        ):
            StrictSystemInit(self.handler, validate_deployment()).bootstrap()
