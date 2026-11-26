"""严格初始化按依赖分两段；只有 finalize 的实际资源就绪才算完成。"""
from bk_resource import resource
from django.conf import settings
from django.db import transaction

from apps.meta.models import GlobalMetaConfig
from apps.meta.utils.builtin_assets import (
    BUILTIN_ASSET_RESOURCE_TYPES,
    get_builtin_asset_system_id,
)
from apps.permission.handlers.resource_types import ResourceEnum
from services.web.bkbase.common import get_bkbase_version
from services.web.bkbase.constants import BKBaseVersion, TaskState
from services.web.bkbase.exceptions import BKBaseResourceMappingError
from services.web.databus.collector_plugin.handlers import (
    EventCollectorEtlHandler,
    PluginEtlHandler,
)
from services.web.databus.constants import (
    COLLECTOR_PLUGIN_ID,
    DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY,
    JoinDataType,
    PluginSceneChoices,
    SnapshotRunningStatus,
)
from services.web.databus.models import CollectorPlugin, Snapshot
from services.web.entry.constants import INIT_SYSTEM_RULE_AUDIT_STRATEGY_ID_KEY
from services.web.entry.init.itsm_approval import init_itsm_approval
from services.web.entry.init.v4_wait import V4InitWait
from services.web.risk.handlers import EventHandler
from services.web.strategy_v2.constants import (
    StrategySource,
    StrategyStatusChoices,
    StrategyType,
)
from services.web.strategy_v2.models import Strategy


class StrictSystemInit:
    """复用原初始化动作和登记，不引入另一套资源状态机。"""

    def __init__(self, handler, deployment):
        self.handler = handler
        self.deployment = deployment
        self.namespace = settings.DEFAULT_NAMESPACE

    def bootstrap(self):
        """迁移后只做不依赖本次 API/Puller 的工作。"""
        self.deployment.apply()
        self.handler.init_standard_fields()
        if get_bkbase_version() == BKBaseVersion.V3:
            self.handler.init_es()
            self.handler.init_doris()
            self.handler.init_redis()
        else:
            # 预定义 ES/Doris 已在 apply 写入本地绑定，不再次注册或修改集群。
            if self.deployment.redis:
                self.handler.init_redis(v4_wait=V4InitWait.from_settings())
        self.handler.init_global_meta_config()
        init_itsm_approval(self.deployment.approval)

    def finalize(self):
        """本次工作负载可达后推进原登记；所有 Pending 共用一次等待预算。"""
        self.deployment.apply()
        wait = V4InitWait.from_settings()
        if get_bkbase_version() == BKBaseVersion.V4:
            self.handler.init_snapshot(v4_wait=wait)
        else:
            self.handler.init_snapshot()
        self.handler.init_system()
        self.handler.init_asset(strict=True)
        plugins = self.ensure_plugins()

        def advance():
            pending = self.plugins_pending(plugins)
            pending.update(self.assets_pending())
            # Flow 可启动的依赖只看事件入库和手工快照，不强求无关资产抢先完成。
            pending.update(self.rule_pending())
            return pending

        wait.until_ready("deployment finalize", advance)
        print("[InitSystem] Finalize 完成：默认采集、事件入库、内置资产和默认策略已就绪")

    def ensure_plugins(self):
        """只认正式登记 ID；未落库的 BKLog 创建允许下次 finalize 重试。"""
        plugin_id = GlobalMetaConfig.get(
            COLLECTOR_PLUGIN_ID, config_level="namespace", instance_key=self.namespace, default=None
        )
        if plugin_id is None:
            # 索引集失败时一并回滚本地插件和默认 ID，下次允许重建未绑定插件。
            with transaction.atomic():
                resource.databus.collector_plugin.create_plugin(namespace=self.namespace, is_default=True)
            plugin_id = GlobalMetaConfig.get(
                COLLECTOR_PLUGIN_ID, config_level="namespace", instance_key=self.namespace, default=None
            )
        regular = list(
            CollectorPlugin.objects.filter(
                collector_plugin_id=plugin_id,
                namespace=self.namespace,
                plugin_scene=PluginSceneChoices.COLLECTOR,
            )
        )
        if len(regular) != 1:
            raise BKBaseResourceMappingError(message="Default collector plugin binding is missing or mismatched")
        events = list(CollectorPlugin.objects.filter(namespace=self.namespace, plugin_scene=PluginSceneChoices.EVENT))
        if not events:
            # 旧完成标记不是插件 ID，严格模式不能据此跳过实际创建。
            EventHandler().update_or_create_rt()
            events = list(
                CollectorPlugin.objects.filter(namespace=self.namespace, plugin_scene=PluginSceneChoices.EVENT)
            )
        if len(events) != 1:
            raise BKBaseResourceMappingError(message="Event collector plugin binding is missing or ambiguous")
        return [regular[0], events[0]]

    @staticmethod
    def plugins_pending(plugins):
        """使用原清洗入库推进，但明确错误向部署命令传播，不等成超时。"""
        pending = {}
        for original in plugins:
            plugin = CollectorPlugin.objects.get(pk=original.pk)
            handler = EventCollectorEtlHandler if plugin.plugin_scene == PluginSceneChoices.EVENT else PluginEtlHandler
            observed = handler(plugin=plugin).create_or_update(raise_errors=True)
            plugin.refresh_from_db()
            if observed and observed.get("task_state") == TaskState.FAILED:
                raise BKBaseResourceMappingError(message=f"Collector plugin {plugin.collector_plugin_id} failed")
            ready = (
                (plugin.bkbase_v4_resources or {}).get("ready")
                if get_bkbase_version() == BKBaseVersion.V4
                else plugin.has_storage
            )
            if not ready:
                pending[f"plugin {plugin.collector_plugin_id}"] = "clean/storage pending"
        return pending

    @staticmethod
    def assets_pending():
        """检查六项实际快照，不用 init_asset 的接受标记代替运行态。"""
        pending = {}
        for asset in BUILTIN_ASSET_RESOURCE_TYPES:
            snapshot = Snapshot.objects.filter(
                system_id=get_builtin_asset_system_id(), resource_type_id=asset.id, join_data_type=JoinDataType.ASSET
            ).first()
            if snapshot and snapshot.status == SnapshotRunningStatus.FAILED:
                raise BKBaseResourceMappingError(
                    message=f"Built-in asset {asset.id} failed; fix the cause and rerun finalize"
                )
            if not snapshot or snapshot.status != SnapshotRunningStatus.RUNNING or not snapshot.bkbase_table_id:
                pending[f"asset {asset.id}"] = "snapshot/RT pending"
        return pending

    def rule_pending(self):
        """Doris 事件物理表及手工事件快照就绪后才允许创建默认 Flow。"""
        physical = GlobalMetaConfig.get(
            DORIS_EVENT_PHYSICAL_TABLE_NAME_KEY, config_level="namespace", instance_key=self.namespace, default=None
        )
        event = CollectorPlugin.objects.filter(namespace=self.namespace, plugin_scene=PluginSceneChoices.EVENT).first()
        ready = event and event.has_storage
        if get_bkbase_version() == BKBaseVersion.V4:
            ready = ready and (event.bkbase_v4_resources or {}).get("ready")
        if not ready or not isinstance(physical, str) or not physical.strip():
            return {"event physical table": "Doris storage pending"}
        snapshot = Snapshot.objects.filter(
            system_id=get_builtin_asset_system_id(),
            resource_type_id=ResourceEnum.MANUAL_EVENT.id,
            join_data_type=JoinDataType.ASSET,
            status=SnapshotRunningStatus.RUNNING,
        ).first()
        if not snapshot or not isinstance(snapshot.bkbase_table_id, str) or not snapshot.bkbase_table_id.strip():
            return {"manual event snapshot": "snapshot/RT pending"}
        self.handler.init_system_rule_audit()
        strategy_id = GlobalMetaConfig.get(INIT_SYSTEM_RULE_AUDIT_STRATEGY_ID_KEY, default=None)
        if strategy_id is None:
            return {"default Flow": "manual event snapshot/RT pending"}
        strategy = Strategy.objects.filter(
            strategy_id=strategy_id,
            namespace=self.namespace,
            source=StrategySource.SYSTEM,
            strategy_type=StrategyType.RULE,
        ).first()
        if strategy is None:
            raise BKBaseResourceMappingError(message="Default Flow strategy binding is missing or mismatched")
        if ((strategy.configs or {}).get("data_source") or {}).get("rt_id") != snapshot.bkbase_table_id:
            raise BKBaseResourceMappingError(message="Default Flow input does not match the registered manual snapshot")
        if strategy.status in (
            StrategyStatusChoices.START_FAILED,
            StrategyStatusChoices.UPDATE_FAILED,
            StrategyStatusChoices.FAILED,
        ):
            raise BKBaseResourceMappingError(
                message=f"Default Flow {strategy_id} failed; fix the cause and rerun finalize"
            )
        return {} if strategy.status == StrategyStatusChoices.RUNNING else {"default Flow": "waiting for running"}
