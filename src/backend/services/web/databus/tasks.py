# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import datetime
import os
import time
import traceback
from typing import Dict, Optional, Type

import requests
from bk_resource import api, resource
from bk_resource.exceptions import APIRequestError
from blueapps.contrib.celery_tools.periodic import periodic_task
from blueapps.core.celery import celery_app
from blueapps.utils.logger import logger
from celery.schedules import crontab
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext

from api.bk_base.constants import StorageType
from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig, ResourceType, System
from apps.notice.handlers import ErrorMsgHandler
from apps.permission.handlers.resource_types import ResourceEnum, ResourceTypeMeta
from core.lock import lock
from services.web.databus.collector.check.handlers import ReportCheckHandler
from services.web.databus.collector.etl.base import EtlClean
from services.web.databus.collector.handlers import TailLogHandler
from services.web.databus.collector.snapshot.join.base import (
    AssetHandler,
    BasicJoinHandler,
)
from services.web.databus.collector.snapshot.join.http_pull import HttpPullHandler
from services.web.databus.collector_plugin.handlers import (
    EventCollectorEtlHandler,
    PluginEtlHandler,
)
from services.web.databus.constants import (
    API_PUSH_ETL_RETRY_TIMES,
    API_PUSH_ETL_RETRY_WAIT_TIME,
    ASSET_RISK_BKBASE_RT_ID_KEY,
    ASSET_STRATEGY_BKBASE_RT_ID_KEY,
    ASSET_STRATEGY_TAG_BKBASE_RT_ID_KEY,
    ASSET_TICKET_NODE_BKBASE_RT_ID_KEY,
    ASSET_TICKET_PERMISSION_BKBASE_RT_ID_KEY,
    COLLECTOR_PLUGIN_ID,
    PULL_HANDLER_PRE_CHECK_TIMEOUT,
    EtlConfigEnum,
    JoinDataType,
    PluginSceneChoices,
    SnapshotRunningStatus,
)
from services.web.databus.models import (
    CollectorConfig,
    CollectorPlugin,
    Snapshot,
    SnapshotCheckStatistic,
)


@periodic_task(run_every=crontab(minute="*/1"), time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
@lock(lock_name="celery:start_snapshot")
def start_snapshot():
    # 获取所有的启动中快照并逐个运行 (Redis)
    snapshots = Snapshot.objects.filter(
        status__in=(SnapshotRunningStatus.PREPARING.value,),
    )
    for snapshot in snapshots:
        logger.info(
            "[start_snapshot] SystemID => %s; ResourceTypeID => %s", snapshot.system_id, snapshot.resource_type_id
        )

        try:
            ResourceType.objects.get(system_id=snapshot.system_id, resource_type_id=snapshot.resource_type_id)
        except ResourceType.DoesNotExist:
            logger.error(
                "[start_snapshot] System %s ResourceType Not Found => %s", snapshot.system_id, snapshot.resource_type_id
            )
            continue

        storage_types = snapshot.storages.values_list('storage_type', flat=True)

        for storage_type in storage_types:
            logger.info(f"[start_snapshot] Handling storage_type => {storage_type}")

            ret = None
            if snapshot.join_data_type == "basic":
                ret = BasicJoinHandler(snapshot.system_id, snapshot.resource_type_id, storage_type).start(
                    multiple_storage=True
                )
            elif snapshot.join_data_type == "asset":
                ret = AssetHandler(snapshot.system_id, snapshot.resource_type_id, storage_type).start(
                    multiple_storage=True
                )
            else:
                logger.warning(f"[start_snapshot] Unknown join_data_type: {snapshot.join_data_type}")
            if not ret:
                break
        else:
            # 这里同步下状态，避免状态被其他任务修改
            snapshot.refresh_from_db()
            snapshot.status = SnapshotRunningStatus.RUNNING.value
            snapshot.status_msg = ""
            snapshot.save(update_fields=["status", "status_msg"])


@periodic_task(run_every=crontab(minute="*/10"), time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
@lock(lock_name="celery:sync_tail_log_time")
def sync_tail_log_time():
    collectors = CollectorConfig.objects.all()
    for collector in collectors:
        TailLogHandler.get_instance(collector).sync()


@periodic_task(run_every=crontab(minute="*/1"), time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
@lock(lock_name="celery:change_storage_cluster")
def change_storage_cluster():
    def change_plugin_storage():
        collector_plugins = CollectorPlugin.objects.filter(storage_changed=True)
        for collector_plugin in collector_plugins:
            try:
                default_plugin_id = GlobalMetaConfig.get(
                    COLLECTOR_PLUGIN_ID,
                    config_level=ConfigLevelChoices.NAMESPACE.value,
                    instance_key=collector_plugin.namespace,
                )
                resource.databus.collector_plugin.update_plugin(
                    namespace=collector_plugin.namespace,
                    etl_config=collector_plugin.etl_config,
                    etl_params=collector_plugin.etl_params,
                    is_default=str(default_plugin_id) == str(collector_plugin.collector_plugin_id),
                    collector_plugin_id=collector_plugin.collector_plugin_id,
                )
                collector_plugin.refresh_from_db()
                collector_plugin.storage_changed = False
                collector_plugin.save()
            except Exception as err:  # NOCC:broad-except(需要处理所有错误)
                title = gettext("ChangePluginStorageFailed")
                content = gettext("Error: %s") % str(err)
                ErrorMsgHandler(title, content).send()
                logger.exception(
                    "[Change Plugin Storage Failed] CollectorPluginID => %s; Err => %s",
                    collector_plugin.collector_plugin_id,
                    err,
                )

    def change_config_storage():
        collectors = CollectorConfig.objects.filter(storage_changed=True, is_deleted=False)
        for collector in collectors:
            try:
                system = System.objects.get(system_id=collector.system_id)
                etl_storage: EtlClean = EtlClean.get_instance(collector.etl_config)
                etl_storage.update_or_create(
                    collector.collector_config_id,
                    collector.etl_params,
                    collector.fields,
                    system.namespace,
                )
                collector.refresh_from_db()
                collector.storage_changed = False
                collector.save()
            except Exception as err:  # NOCC:broad-except(需要处理所有错误)
                title = gettext("ChangeCollectorStorageFailed")
                content = gettext("Error: %s") % str(err)
                ErrorMsgHandler(title, content).send()
                logger.exception("[Change Collector Storage Failed] CollectorID => %s; Err => %s", collector.id, err)

    change_plugin_storage()
    change_config_storage()


@periodic_task(run_every=crontab(minute="0", hour="0"), time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
@lock(lock_name="celery:refresh_snapshot")
def refresh_snapshot():
    # 获取所有的运行中快照
    snapshots = Snapshot.objects.filter(status=SnapshotRunningStatus.RUNNING.value).order_by("updated_at")
    snapshots_count = snapshots.count()
    logger.info(f"[Refresh Snapshot] Snapshots Count => {snapshots_count}")
    if not snapshots_count:
        return
    # 计算需要更新的数量
    ex_days = int(settings.HTTP_PULL_REDIS_TIMEOUT.replace("d", ""))
    past_days = (timezone.now() - snapshots.first().updated_at).days
    updated_count = int(snapshots_count * (past_days / ex_days))
    logger.info(f"[Refresh Snapshot] ex_days => {ex_days}; past_days => {past_days}; updated_count => {updated_count}")
    if not updated_count:
        return
    # 更新状态
    snapshot_ids = [snapshot.id for snapshot in snapshots[:updated_count]]
    Snapshot.objects.filter(id__in=snapshot_ids).update(status=SnapshotRunningStatus.PREPARING.value)


@celery_app.task(time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
def create_api_push_etl(collector_config_id: int):
    """
    创建 API PUSH 对应的数据清洗入库链路
    """

    logger.info("[create_api_push_etl] Start %s", datetime.datetime.now())

    collector = CollectorConfig.objects.get(collector_config_id=collector_config_id)
    namespace = CollectorPlugin.objects.get(collector_plugin_id=collector.collector_plugin_id).namespace

    # 创建清洗策略
    fields = [
        {
            **_field,
            "option": {
                "key": f"attributes/{_field['field_name']}",
                "path": f"attributes/{_field['field_name']}",
                "val": None,
            },
        }
        for _field in resource.meta.get_standard_fields()
    ]
    etl_params = {
        "namespace": namespace,
        "collector_config_id": collector.collector_config_id,
        "etl_config": EtlConfigEnum.BK_LOG_JSON.value,
        "etl_params": {"retain_original_text": True},
        "fields": fields,
        "ignore_check": True,
    }

    # Delay 任务不会及时到 BkBase，需要增加 Retry
    retry = 1
    time.sleep(API_PUSH_ETL_RETRY_WAIT_TIME)
    while retry <= API_PUSH_ETL_RETRY_TIMES:
        retry += 1
        try:
            resource.databus.collector.collector_etl(**etl_params)
            retry = API_PUSH_ETL_RETRY_TIMES + 1
            logger.info("[CreateApiPushEtlSuccess] Retry => %s; Collector => %s", retry, collector.collector_config_id)
        except Exception as err:  # NOCC:broad-except(需要处理所有错误)
            logger.exception(
                "[CreateApiPushEtlError] Retry => %s; Error => %s; Detail %s;", retry, str(err), traceback.format_exc()
            )
            if isinstance(err, APIRequestError):
                time.sleep(API_PUSH_ETL_RETRY_WAIT_TIME)
            else:
                break

    logger.info("[create_api_push_etl] End %s", datetime.datetime.now())


@lock(lock_name="celery:check_report_continues")
def check_report_continues(end_time: datetime.datetime = None, time_period: int = None, time_range: int = None):
    """检查上报数据是否连续"""

    if not os.getenv("BKAPP_COLLECTOR_CHECK_REPORT_ACCESS_TOKEN"):
        return

    namespaces = CollectorPlugin.objects.all().order_by().values_list("namespace", flat=True).distinct()

    for namespace in namespaces:
        try:
            ReportCheckHandler(
                namespace=namespace, end_time=end_time, time_period=time_period, time_range=time_range
            ).check()
        except Exception as err:  # NOCC:broad-except(需要处理所有错误)
            logger.error(
                "[ReportCheckRunFailed] "
                "Namespace => %s; "
                "end_time => %s; "
                "time_period => %s; "
                "time_range => %s; "
                "Err => %s",
                namespace,
                end_time,
                time_period,
                time_range,
                err,
            )


@periodic_task(run_every=crontab(minute="*/1"), time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
@lock(lock_name="celery:create_or_update_plugin_etl")
def create_or_update_plugin_etl(collector_plugin_id: int = None):
    """创建或更新采集插件清洗入库"""

    if collector_plugin_id:
        plugins = CollectorPlugin.objects.filter(collector_plugin_id=collector_plugin_id)
    else:
        # 仅为日志/事件采集插件创建入库
        plugins = CollectorPlugin.objects.filter(
            plugin_scene__in=[PluginSceneChoices.EVENT.value, PluginSceneChoices.COLLECTOR.value],
            bkbase_table_id__isnull=True,
        )
    # 创建或更新
    handler_map = {
        PluginSceneChoices.EVENT.value: EventCollectorEtlHandler,
        PluginSceneChoices.COLLECTOR.value: PluginEtlHandler,
    }
    for plugin in plugins:
        handler = handler_map.get(plugin.plugin_scene)
        if not handler:
            logger.error("[PluginEtlHandlerNotFound] PluginScene => %s", plugin.plugin_scene)
            continue
        handler(collector_plugin_id=plugin.collector_plugin_id).create_or_update()


@periodic_task(run_every=crontab(minute="0", hour="5"), time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
@lock(lock_name="celery:check_join_data")
def check_join_data():
    # 获取所有状态为 'running' 的快照记录
    snapshots = Snapshot.objects.filter(status=SnapshotRunningStatus.RUNNING)

    # 遍历每个快照记录并执行检查
    for snapshot in snapshots:
        system_id = snapshot.system_id
        resource_type_id = snapshot.resource_type_id
        join_data_type = snapshot.join_data_type

        # 获取系统和资源类型信息
        system = System.objects.get(system_id=system_id)
        try:
            resource_type = ResourceType.objects.get(system_id=system_id, resource_type_id=resource_type_id)
        except ResourceType.DoesNotExist:
            logger.error("[JoinDataCheckFailed] System %s ResourceType Not Found => %s", system_id, resource_type_id)
            continue

        # 构建请求体
        body = {
            "type": resource_type_id,
            "method": "fetch_instance_list",
            "filter": {"start_time": 0, "end_time": int(datetime.datetime.now().timestamp()) * 1000},
            "page": {"offset": 0, "limit": 1},
        }

        try:
            # 设置 HttpPullHandler
            pull_handler = HttpPullHandler(system, resource_type, Snapshot(), join_data_type)
            # 执行 HTTP 请求
            web = requests.session()
            resp = web.post(
                pull_handler.url,
                json=body,
                headers={"Authorization": pull_handler.authorization},
                timeout=PULL_HANDLER_PRE_CHECK_TIMEOUT,
            )
            resp.raise_for_status()  # 检查请求是否成功
            content = resp.json()
            result = content.get("result", True)
            http_pull_count = content.get("data", {}).get("count", 0)
        except Exception as e:  # NOCC:broad-except(需要处理所有错误)
            # 如果发生异常，将 storage_count 设置为 0，并且 result 设置为 False
            logger.exception("[JoinDataCheckFailed] Error while querying storage: %s", e)
            http_pull_count = 0
            result = False
        # 请求存储中的数据总数
        count_sql = f"select count(*) as count from {snapshot.bkbase_table_id} limit 1"
        bulk_req_params = [
            {
                "sql": count_sql,
                "prefer_storage": StorageType.DORIS.value,
            },
            {
                "sql": count_sql,
                "prefer_storage": StorageType.HDFS.value,
            },
        ]

        try:
            # 尝试发送请求获取存储中的 count 数据
            bulk_resp = api.bk_base.query_sync.bulk_request(bulk_req_params)
            doris_count_resp, hdfs_count_resp = bulk_resp
            doris_storage_count = doris_count_resp.get("list", [{}])[0].get("count", 0)
            hdfs_storage_count = hdfs_count_resp.get("list", [{}])[0].get("count", 0)
        except Exception as e:  # NOCC:broad-except(需要处理所有错误)
            # 如果发生异常，将 storage_count 设置为 0，并且 result 设置为 False
            logger.exception("[JoinDataCheckFailed] Error while querying storage: %s", e)
            doris_storage_count = 0
            hdfs_storage_count = 0
            result = False

        # 将结果保存到 JoinDataCheckStatistic 表
        SnapshotCheckStatistic.objects.update_or_create(
            system_id=system_id,
            resource_type_id=resource_type_id,
            join_data_type=join_data_type,
            defaults={
                "http_pull_count": http_pull_count,
                "doris_storage_count": doris_storage_count,
                "hdfs_storage_count": hdfs_storage_count,
                "result": result,
            },
        )


@celery_app.task(soft_time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
@lock(load_lock_name=lambda system_id: f"restart_resource_snapshots:{system_id}")
def refresh_system_snapshots(system_id: int):
    """
    刷新当前系统下运行中的资源快照
    """

    logger.info("[restart_resource_types] system_id %s Start", system_id)

    system = System.objects.filter(system_id=system_id).first()
    if not system:
        logger.info("[restart_resource_types] system_id %s Not Found", system_id)
        return

    # 仅修改当前系统下存在的资源类型的快照
    resource_type_ids = ResourceType.objects.filter(system_id=system_id).values_list("resource_type_id", flat=True)

    updated_count = Snapshot.objects.filter(
        system_id=system_id,
        resource_type_id__in=resource_type_ids,
        status=SnapshotRunningStatus.RUNNING.value,
    ).update(status=SnapshotRunningStatus.PREPARING.value)

    logger.info("[restart_resource_types] system_id %s Updated %s", system_id, updated_count)


@periodic_task(run_every=crontab(minute="0", hour="*"), soft_time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
@lock(lock_name="celery:sync_asset_bkbase_rt_ids")
def sync_asset_bkbase_rt_ids():
    """
    同步资产快照的 bkbase_table_id 到全局配置
    """

    asset_configs: Dict[Type[ResourceTypeMeta], str] = {
        ResourceEnum.RISK: ASSET_RISK_BKBASE_RT_ID_KEY,
        ResourceEnum.STRATEGY: ASSET_STRATEGY_BKBASE_RT_ID_KEY,
        ResourceEnum.STRATEGY_TAG: ASSET_STRATEGY_TAG_BKBASE_RT_ID_KEY,
        ResourceEnum.TICKET_PERMISSION: ASSET_TICKET_PERMISSION_BKBASE_RT_ID_KEY,
        ResourceEnum.TICKET_NODE: ASSET_TICKET_NODE_BKBASE_RT_ID_KEY,
    }

    # TODO: 当前只有一个 namespace，直接使用 settings.DEFAULT_NAMESPACE，后续需要支持多 namespace
    for resource_cls, config_key in asset_configs.items():
        result_table_id = GlobalMetaConfig.get(
            config_key,
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key=settings.DEFAULT_NAMESPACE,
            default="",
        )
        if result_table_id:
            logger.info(
                "[sync_asset_bkbase_rt_ids] config_key:%s already exists, result_table_id:%s",
                config_key,
                result_table_id,
            )
            continue

        snapshot: Optional[Snapshot] = (
            Snapshot.objects.filter(
                system_id=resource_cls.system_id,
                resource_type_id=resource_cls.id,
                status=SnapshotRunningStatus.RUNNING.value,
                bkbase_data_id__isnull=False,
                join_data_type=JoinDataType.ASSET.value,
            )
            .order_by("-updated_at")
            .first()
        )
        if not snapshot or not snapshot.bkbase_table_id:
            logger.info("[sync_asset_bkbase_rt_ids] config_key:%s, snapshot not found", config_key)
            continue

        logger.info(
            "[sync_asset_bkbase_rt_ids] config_key:%s, snapshot found, result_table_id:%s",
            config_key,
            snapshot.bkbase_table_id,
        )
        GlobalMetaConfig.set(
            config_key,
            str(snapshot.bkbase_table_id),
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key=settings.DEFAULT_NAMESPACE,
        )
