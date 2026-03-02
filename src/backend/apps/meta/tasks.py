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
from collections import defaultdict
from typing import Dict, List, Set, Type

from bk_resource import api
from blueapps.contrib.celery_tools.periodic import periodic_task
from blueapps.core.celery import celery_app
from blueapps.utils.logger import logger_celery
from blueapps.utils.logger import logger_celery as logger
from celery.schedules import crontab
from django.conf import settings
from django.db import transaction

from apps.meta.constants import (
    PAAS_APP_BATCH_SIZE,
    SystemDiagnosisPushStatusEnum,
    SystemSourceTypeEnum,
)
from apps.meta.handlers.system_diagnosis import SystemDiagnosisPushHandler
from apps.meta.handlers.system_sync import (
    IamSystemSyncer,
    IAMV3SystemSyncer,
    IAMV4SystemSyncer,
)
from apps.meta.models import System, SystemDiagnosisConfig
from core.lock import lock
from core.utils.data import group_by


@periodic_task(run_every=crontab(minute="*/10"), time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
@transaction.atomic
def sync_system_paas_info():
    """
    同步系统与PAAS应用关系
    """

    logger.info("[sync_system_paas_info] started")
    system_map: Dict[str, System] = {
        system.system_id: system
        for system in list(
            System.objects.all().only("system_id", "clients", "logo_url", "system_url", "updated_by", "updated_at")
        )
    }

    # 获取 Clients
    clients: Set[str] = set()
    client_system_map = dict()
    for system in system_map.values():
        system_id = system.system_id
        clients_tmp = system.clients
        clients.update(clients_tmp)
        client_system_map[system_id] = clients_tmp

    # 分组
    client_requests = defaultdict(list)
    count = 0
    for client in clients:
        count += 1
        client_requests[count // PAAS_APP_BATCH_SIZE].append(client)

    # 批量请求，API Rate 受限需要降频
    paas_systems = []
    paas_requests = [
        {"id": client, "include_deploy_info": 1, "include_market_info": "true"} for client in client_requests.values()
    ]
    resp = api.bk_paas.uni_apps_query.bulk_request(paas_requests)
    for items in resp:
        for app_info in items:
            if app_info and isinstance(app_info, dict):
                paas_systems.append(app_info)
    paas_systems = group_by(paas_systems, lambda x: x["code"])

    # 更新信息
    to_update = []
    for system_id, system_clients in client_system_map.items():
        need_update = False
        db_system = system_map.get(system_id)
        # 更新 PaaS 信息
        for client in system_clients:
            client_paas_systems = paas_systems.get(client)
            if not client_paas_systems:
                continue
            paas_system = client_paas_systems[0]
            deploy_info = paas_system.get("deploy_info") or dict()
            market_addres = paas_system.get("market_addres") or dict()
            paas_system_url = (
                deploy_info.get("prod", {}).get("url")
                or deploy_info.get("stag", {}).get("url")
                or market_addres.get("market_address")
            )
            # 更新 logo
            if db_system.logo_url != paas_system["logo_url"]:
                need_update = True
                db_system.logo_url = paas_system["logo_url"]
            # 更新系统 URL
            if (
                db_system.source_type not in SystemSourceTypeEnum.get_editable_sources()
                and db_system.system_url != paas_system_url
            ):
                need_update = True
                db_system.system_url = paas_system_url
            break
        if need_update:
            to_update.append(db_system)
    logger.info("[sync_system_paas_info] to_update => %d", len(to_update))

    # 同步DB
    if to_update:
        System.objects.bulk_update(
            to_update,
            fields=["logo_url", "system_url"],
            batch_size=PAAS_APP_BATCH_SIZE,
        )

    logger.info("[sync_system_paas_info] finished")


@celery_app.task(time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
@lock(load_lock_name=lambda cls_name, func_name, *args, **kwargs: f"celery:call_sync:{cls_name}:{func_name}")
def call_sync(cls_name: str, func_name: str, *args, **kwargs):
    """
    call syncer async
    """

    syncer = IamSystemSyncer(cls_name=cls_name)
    func = getattr(syncer, func_name, None)
    func(*args, **kwargs)


@periodic_task(run_every=crontab(minute="*/10"), time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
@lock(lock_name="sync_iam_systems")
def sync_iam_systems():
    """
    同步 IAM 系统
    """

    syncers: List[Type[IamSystemSyncer]] = [IAMV3SystemSyncer, IAMV4SystemSyncer]
    for syncer in syncers:
        try:
            syncer().sync_systems()
            syncer().sync_system_infos()
            syncer().sync_resources_actions()
        except Exception as e:  # NOCC:broad-except(需要处理所有错误)
            logger.error(f"[sync_iam_systems] sync {syncer.__name__} error: {e}")


@periodic_task(run_every=crontab(minute=0, hour=17), time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
@transaction.atomic
def update_system_diagnosis_push():
    """
    定期更新系统诊断推送
    """

    logger.info("[update_system_diagnosis_push] started")
    systems = System.objects.all().only("system_id", "enable_system_diagnosis_push")
    system_ids = systems.values_list("system_id", flat=True)
    sys_diagnosis_configs: Dict[str, SystemDiagnosisConfig] = {
        config.system_id: config
        for config in list(
            SystemDiagnosisConfig.objects.filter(system_id__in=system_ids).only("system_id", "push_uid", "push_status")
        )
    }
    for system in systems:
        config = sys_diagnosis_configs.get(system.system_id)
        if not (
            system.enable_system_diagnosis_push
            or config
            and config.push_status == SystemDiagnosisPushStatusEnum.PUSH.value
        ):
            logger_celery.info(f"[update_system_diagnosis_push] system {system.system_id} skip update")
            continue
        # 系统开启诊断推送 or 推送配置状态不一致则更新
        handler = SystemDiagnosisPushHandler(system_id=system.system_id)
        try:
            # 以系统推送状态为准进行更新
            handler.change_push_status(system.enable_system_diagnosis_push)
        except Exception as e:
            logger_celery.error(f"[update_system_diagnosis_push] system {system.system_id} push error: {e}")
