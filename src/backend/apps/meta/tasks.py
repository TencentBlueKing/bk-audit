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

import operator
from collections import defaultdict
from typing import List

from bk_resource import api
from bk_resource.settings import bk_resource_settings
from bk_resource.utils.common_utils import ignored
from blueapps.contrib.celery_tools.periodic import periodic_task
from blueapps.utils.logger import logger_celery as logger
from celery.schedules import crontab
from django.conf import settings
from django.db import transaction
from django.db.models import Q

from apps.meta.constants import (
    IAM_ACTION_BATCH_SIZE,
    IAM_MANAGER_ROLE,
    IAM_RESOURCE_BATCH_SIZE,
    IAM_SYSTEM_BATCH_SIZE,
    PAAS_APP_BATCH_SIZE,
)
from apps.meta.models import Action, Namespace, ResourceType, System, SystemRole
from core.utils.tools import group_by


@periodic_task(run_every=crontab(minute="*/1"), soft_time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
@transaction.atomic
@ignored(Exception)
def sync_iam_systems():
    """
    同步IAM系统列表
    """
    logger.info("[sync_iam_systems] start")
    bk_username = bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME

    # step 1：判断默认空间是否存在，如果不存在则直接创建
    default_ns = settings.DEFAULT_NAMESPACE
    namespace = Namespace.objects.filter(namespace=default_ns)
    if not namespace.exists():
        namespace_info = {
            "namespace": default_ns,
            "name": default_ns,
            "created_by": bk_username,
            "updated_by": bk_username,
        }
        ns = Namespace.objects.create(**namespace_info)
        if not ns:
            logger.exception("[sync_iam_systems] 创建默认NS异常 NamespaceInfo => %s", namespace_info)
            return

    # step 2：获取所有系统，并比较IAM系统列表进行增删改
    db_systems = group_by(System.objects.all(), operator.attrgetter("system_id"))
    iam_systems = group_by(api.bk_iam.get_systems(), operator.itemgetter("id"))

    # step 3: 确认需要处理的系统信息
    to_insert = []
    to_delete = set(db_systems)
    to_update = []
    for (system_id, systems) in iam_systems.items():
        iam_system_instance = systems[0]
        if system_id in db_systems:
            db_system_instance = db_systems[system_id][0]
            to_delete.remove(system_id)
            if any(
                [
                    db_system_instance.name_en != iam_system_instance["name"],
                ]
            ):
                db_system_instance.name_en = iam_system_instance["name"]
                to_update.append(db_system_instance)
            continue
        to_insert.append(
            System(
                namespace=default_ns,
                system_id=iam_system_instance["id"],
                name_en=iam_system_instance.get("name"),
                created_by=bk_username,
                updated_by=bk_username,
            )
        )
    logger.info(
        "[sync_iam_systems] to_insert => %d, to_update => %d, to_delete => %d",
        len(to_insert),
        len(to_update),
        len(to_delete),
    )

    # step 4: 同步db
    if to_insert:
        System.objects.bulk_create(to_insert)

    if to_update:
        System.objects.bulk_update(to_update, fields=["name", "name_en"], batch_size=IAM_SYSTEM_BATCH_SIZE)

    if to_delete:
        System.objects.filter(system_id__in=to_delete).delete()

    logger.info("[sync_iam_systems] finished")

    # step 5: 串行同步IAM系统角色信息
    sync_iam_system_roles(iam_systems)


def sync_iam_system_roles(iam_systems):
    """
    同步IAM系统角色
    """
    if not iam_systems:
        return
    logger.info("[sync_iam_system_roles] start")
    # step 1: 获取 IAM 系统角色
    db_roles = group_by(SystemRole.objects.filter(role=IAM_MANAGER_ROLE), operator.attrgetter("system_id"))
    iam_requests = [{"system_id": system_id} for system_id in set(iam_systems)]
    iam_roles = group_by(api.bk_iam.get_system_roles.bulk_request(iam_requests), operator.itemgetter("id"))

    # step 2: 确认需要处理的系统信息
    bk_username = bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME
    for _, item in enumerate(iam_requests):
        system_id = item["system_id"]
        iam_system_info = iam_roles.get(system_id, [{}])[0]
        # 兼容IAM的同步信息
        system_iam_roles = iam_system_info.get(IAM_MANAGER_ROLE) or []
        if system_iam_roles and isinstance(system_iam_roles[0], dict):
            system_iam_roles = [iam_role["username"] for iam_role in system_iam_roles]
        system_iam_roles = set(system_iam_roles)
        system_db_roles = set()
        if db_roles.get(system_id):
            system_db_roles = {system.username for system in db_roles.get(system_id)}

        to_insert = system_iam_roles - system_db_roles
        to_delete = system_db_roles - system_iam_roles

        if not to_insert and not to_delete:
            continue

        logger.info("[sync_iam_system_roles] to_insert => %d, to_delete => %d", len(to_insert), len(to_delete))

        if to_insert:
            SystemRole.objects.bulk_create(
                [
                    SystemRole(
                        system_id=system_id,
                        role=IAM_MANAGER_ROLE,
                        username=username,
                        created_by=bk_username,
                        updated_by=bk_username,
                    )
                    for username in to_insert
                ]
            )

        if to_delete:
            SystemRole.objects.filter(username__in=to_delete).delete()
    logger.info("[sync_iam_system_roles] finished")


@periodic_task(run_every=crontab(minute="*/10"), soft_time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
@transaction.atomic
@ignored(Exception)
def sync_system_infos():
    logger.info("[sync_system_infos] started")

    systems = System.objects.all()
    system_info_requests = [{"system_id": system.system_id} for system in systems]
    system_infos = api.bk_iam.get_system_info.bulk_request(system_info_requests)

    # 获取 Clients
    clients = set()
    client_system_map = dict()
    system_info_map = dict()
    for system_info in system_infos:
        system_id = system_info["base_info"]["id"]
        clients_tmp = system_info["base_info"].get("clients", [])
        clients.update(clients_tmp)
        client_system_map[system_id] = clients_tmp
        system_info_map[system_id] = system_info
    # 分组
    client_requests = defaultdict(list)
    count = 0
    for client in clients:
        count += 1
        client_requests[count // PAAS_APP_BATCH_SIZE].append(client)

    # 批量请求，API Rate 受限需要降频
    paas_systems = []
    paas_requests = [{"id": client, "include_deploy_info": 1} for client in client_requests.values()]
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
        db_system = systems.get(system_id=system_id)
        # 更新 IAM 信息
        base_info = system_info_map[system_id]["base_info"]
        if any(
            [
                db_system.name != base_info["name"],
                db_system.description != base_info["description"],
                db_system.provider_config != base_info["provider_config"],
                db_system.clients != base_info["clients"],
            ]
        ):
            db_system.name = base_info["name"]
            db_system.description = base_info["description"]
            db_system.provider_config = base_info["provider_config"]
            db_system.clients = base_info["clients"]
            need_update = True
        # 更新 PaaS 信息
        for client in system_clients:
            client_paas_systems = paas_systems.get(client)
            if not client_paas_systems:
                continue
            paas_system = client_paas_systems[0]
            deploy_info = paas_system.get("deploy_info") or dict()
            paas_system_url = deploy_info.get("prod", {}).get("url") or deploy_info.get("stag", {}).get("url")
            if any(
                [
                    db_system.logo_url != paas_system["logo_url"],
                    db_system.system_url != paas_system_url,
                ]
            ):
                db_system.logo_url = paas_system["logo_url"]
                db_system.system_url = paas_system_url
                need_update = True
            break
        if need_update:
            to_update.append(db_system)
    logger.info("[sync_system_infos] to_update => %d", len(to_update))

    # 同步DB
    if to_update:
        System.objects.bulk_update(
            to_update,
            fields=["name", "description", "provider_config", "clients", "logo_url", "system_url"],
            batch_size=PAAS_APP_BATCH_SIZE,
        )

    logger.info("[sync_system_infos] finished")


def update_instance_attrs(instance, obj: dict, attrs: list) -> (bool, object):
    need_update = False
    for attr in attrs:
        if getattr(instance, attr, None) != obj[attr]:
            setattr(instance, attr, obj[attr])
            need_update = True
    return need_update, instance


def sync_iam_objects(
    system_id: str, iam_objects: List[dict], db_model, db_id_field: str, fields: List[str]
) -> (list, list, list):
    """
    return: to_insert, to_update, to_delete
    to_insert: 待新建的DB实例列表
    to_update: 待更新的DB实例列表
    to_delete: 待删除的DB实例PK列表
    """
    bk_username = bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME
    # 获取数据库存储实例
    db_objects = db_model.objects.filter(system_id=system_id)
    db_object_ids = db_objects.values_list(db_id_field, flat=True)
    # 构造新增、更新、删除列表
    to_insert = []
    to_update = []
    to_delete = set(db_object_ids)
    # 遍历 IAM Instances
    for iam_object in iam_objects:
        # 获取基本参数
        object_id = iam_object["id"]
        # 存在则判断更新
        if object_id in db_object_ids:
            db_object = db_objects.get(**{db_id_field: object_id})
            to_delete.remove(object_id)
            need_update, db_object = update_instance_attrs(db_object, iam_object, fields)
            if need_update:
                to_update.append(db_object)
            continue
        # 不存在则新增
        to_insert.append(
            db_model(
                system_id=system_id,
                created_by=bk_username,
                updated_by=bk_username,
                **{db_id_field: object_id},
                **{field: iam_object[field] for field in fields},
            )
        )
    to_delete = db_objects.filter(**{f"{db_id_field}__in": to_delete}).values_list("id", flat=True)
    return to_insert, to_update, to_delete


@periodic_task(run_every=crontab(minute="*/10"), soft_time_limit=settings.DEFAULT_CACHE_LOCK_TIMEOUT)
@transaction.atomic
@ignored(Exception)
def sync_iam_resources_actions():
    logger.info("[sync_iam_resources_and_actions] started")

    # 获取系统信息
    systems = System.objects.all()
    system_info_requests = [{"system_id": system.system_id} for system in systems]
    system_infos = api.bk_iam.get_system_info.bulk_request(system_info_requests)

    # 构造 IAM 所有资源与操作信息
    resources = defaultdict(list)
    actions = defaultdict(list)
    resource_fields = ["name", "name_en", "sensitivity", "provider_config", "version", "description"]
    action_fields = ["name", "name_en", "sensitivity", "type", "version", "description"]
    for system_info in system_infos:
        system_id = system_info["base_info"]["id"]
        # 资源
        to_insert, to_update, to_delete = sync_iam_objects(
            system_id, system_info.get("resource_types", []), ResourceType, "resource_type_id", resource_fields
        )
        resources["to_insert"].extend(to_insert)
        resources["to_update"].extend(to_update)
        resources["to_delete"].extend(to_delete)
        # 操作
        to_insert, to_update, to_delete = sync_iam_objects(
            system_id, system_info.get("actions", []), Action, "action_id", action_fields
        )
        actions["to_insert"].extend(to_insert)
        actions["to_update"].extend(to_update)
        actions["to_delete"].extend(to_delete)
    logger.info(
        "[sync_iam_resources] to_insert => %d, to_update => %d, to_delete => %d",
        len(resources["to_insert"]),
        len(resources["to_update"]),
        len(resources["to_delete"]),
    )
    logger.info(
        "[sync_iam_actions] to_insert => %d, to_update => %d, to_delete => %d",
        len(actions["to_insert"]),
        len(actions["to_update"]),
        len(actions["to_delete"]),
    )

    # 同步 DB
    sync_db_params = [
        (actions, Action, action_fields, IAM_ACTION_BATCH_SIZE),
        (resources, ResourceType, resource_fields, IAM_RESOURCE_BATCH_SIZE),
    ]
    for param in sync_db_params:
        instance_map, db_model, fields, batch_size = param
        if instance_map["to_insert"]:
            db_model.objects.bulk_create(instance_map["to_insert"])
        if instance_map["to_update"]:
            db_model.objects.bulk_update(instance_map["to_update"], fields=fields, batch_size=batch_size)
        db_model.objects.filter(
            Q(Q(id__in=instance_map["to_delete"]) | ~Q(system_id__in=systems.values("system_id")))
        ).delete()

    logger.info("[sync_iam_resources_and_actions] finished")
