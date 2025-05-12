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
import abc
import operator
from collections import defaultdict
from typing import Dict, List

from bk_resource import api
from bk_resource.settings import bk_resource_settings
from blueapps.utils.logger import logger_celery as logger
from django.conf import settings
from django.db import transaction

from apps.meta.constants import (
    IAM_ACTION_BATCH_SIZE,
    IAM_MANAGER_ROLE,
    IAM_RESOURCE_BATCH_SIZE,
    IAM_SYSTEM_BATCH_SIZE,
    SYSTEM_SYNC_BATCH_SIZE,
    SystemSourceTypeEnum,
)
from apps.meta.models import Action, Namespace, ResourceType, System, SystemRole
from core.utils.data import group_by


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


class IamSystemSyncer(abc.ABC):
    """
    IAM系统同步器
    """

    def __init__(self, cls_name: str, *args, **kwargs):
        self.bk_username = bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME
        self.default_ns = settings.DEFAULT_NAMESPACE

    def __new__(cls, cls_name: str, *args, **kwargs) -> "IamSystemSyncer":
        if cls.__name__ != IamSystemSyncer.__name__:
            return super().__new__(cls)
        sub_cls = {sub_cls.cls_name(): sub_cls for sub_cls in cls.__subclasses__()}
        return sub_cls[cls_name](cls_name, *args, **kwargs)

    @property
    @abc.abstractmethod
    def source_type(self) -> SystemSourceTypeEnum:
        """
        系统来源类型
        """

        raise NotImplementedError()

    @abc.abstractmethod
    def get_iam_systems(self) -> Dict[str, List[dict]]:
        """
        获取IAM系统列表
        """

        raise NotImplementedError()

    @property
    @abc.abstractmethod
    def system_info_fields(self) -> List[str]:
        """
        系统信息更新字段
        """

        raise NotImplementedError()

    @property
    @abc.abstractmethod
    def action_fields(self) -> List[str]:
        """
        需要更新的 action 字段
        """

        raise NotImplementedError()

    @property
    @abc.abstractmethod
    def resource_type_fields(self) -> List[str]:
        """
        需要更新的 resource_type 字段
        """

        raise NotImplementedError()

    @abc.abstractmethod
    def get_resources_actions(self, instance_ids: List[str]) -> Dict[str, dict]:
        """
        获取资源与操作
        """

        raise NotImplementedError()

    @abc.abstractmethod
    def get_system_info_map(self, instance_ids: List[str]) -> Dict[str, dict]:
        """
        构建系统信息映射
        """

        raise NotImplementedError()

    @classmethod
    def cls_name(cls) -> str:
        """
        获取类名
        """

        return cls.__name__

    def get_db_systems(self) -> Dict[str, List[System]]:
        """
        获取DB系统列表
        """

        return group_by(System.objects.filter(source_type=self.source_type), operator.attrgetter("instance_id"))

    @transaction.atomic
    def sync_systems(self):
        """
        同步IAM系统列表
        """
        logger.info(f"[{self.cls_name}] start")

        # step 1：判断默认空间是否存在，如果不存在则直接创建
        namespace = Namespace.objects.filter(namespace=self.default_ns)
        if not namespace.exists():
            namespace_info = {
                "namespace": self.default_ns,
                "name": self.default_ns,
                "created_by": self.bk_username,
                "updated_by": self.bk_username,
            }
            ns = Namespace.objects.create(**namespace_info)
            if not ns:
                logger.exception(f"[{self.cls_name}] 创建默认NS异常 NamespaceInfo => %s", namespace_info)
                return

        # step 2：获取所有系统，并比较IAM系统列表进行增删改
        db_systems = self.get_db_systems()
        iam_systems = self.get_iam_systems()

        # step 3: 确认需要处理的系统信息
        to_insert = []
        to_delete = set(db_systems)
        to_update = []
        for (instance_id, systems) in iam_systems.items():
            iam_system = systems[0]
            if instance_id in db_systems:
                db_system_instance = db_systems[instance_id][0]
                to_delete.remove(instance_id)
                if any(
                    [
                        db_system_instance.name_en != iam_system["name"],
                    ]
                ):
                    db_system_instance.name_en = iam_system["name"]
                    to_update.append(db_system_instance)
                continue
            instance_id = iam_system["id"]
            to_insert.append(
                System(
                    namespace=self.default_ns,
                    system_id=System.build_system_id(self.source_type, instance_id),
                    source_type=self.source_type,
                    instance_id=instance_id,
                    name=iam_system["name"],
                    name_en=iam_system["name"],
                    created_by=self.bk_username,
                    updated_by=self.bk_username,
                )
            )
        logger.info(
            f"[{self.cls_name}] to_insert => %d, to_update => %d, to_delete => %d",
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
            # 删除系统同时需要删除其下的资源
            to_delete_systems = System.objects.filter(
                source_type=self.source_type, instance_id__in=to_delete
            ).values_list("system_id", flat=True)
            System.bulk_delete_with_resources(to_delete_systems)

        logger.info(f"[{self.cls_name}] finished")

        return iam_systems

    @transaction.atomic
    def sync_resources_actions(self):
        """
        同步资源与操作
        """

        logger.info(f"[{self.cls_name}] started")

        # 获取系统信息
        systems = self.get_db_systems()
        system_infos = self.get_resources_actions(list(systems.keys()))

        # 构造 IAM 所有资源与操作信息
        resources = defaultdict(list)
        actions = defaultdict(list)
        resource_fields = self.resource_type_fields
        action_fields = self.action_fields
        for instance_id, system_info in system_infos.items():
            system_id = System.build_system_id(source_type=self.source_type, instance_id=instance_id)
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
            f"[{self.cls_name}] to_insert => %d, to_update => %d, to_delete => %d",
            len(resources["to_insert"]),
            len(resources["to_update"]),
            len(resources["to_delete"]),
        )
        logger.info(
            f"[{self.cls_name}] to_insert => %d, to_update => %d, to_delete => %d",
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
            db_model.objects.filter(id__in=instance_map["to_delete"]).delete()

        logger.info(f"[{self.cls_name}] finished")

    def _update_system_info(self, db_system: System, base_info: dict) -> bool:
        """
        更新系统信息
        """

        need_update = False
        for field in self.system_info_fields:
            if hasattr(db_system, field) and getattr(db_system, field) != base_info[field]:
                setattr(db_system, field, base_info[field])
                need_update = True
        return need_update

    @transaction.atomic
    def sync_system_infos(self):
        """
        同步系统信息
        """
        logger.info(f"[{self.cls_name}] started")

        db_systems = self.get_db_systems()
        system_info_map = self.get_system_info_map(list(db_systems.keys()))

        # 更新信息
        to_update = []
        for system_id in system_info_map.keys():
            if not db_systems.get(system_id):
                continue
            db_system = db_systems.get(system_id)[0]
            if self._update_system_info(db_system, system_info_map[system_id]):
                to_update.append(db_system)
        logger.info(f"[{self.cls_name}] to_update => %d", len(to_update))

        # 同步DB
        if to_update:
            System.objects.bulk_update(
                to_update,
                fields=self.system_info_fields,
                batch_size=SYSTEM_SYNC_BATCH_SIZE,
            )

        logger.info(f"[{self.cls_name}] finished")


class IAMV3SystemSyncer(IamSystemSyncer):
    source_type = SystemSourceTypeEnum.IAM_V3
    system_info_fields = ["name", "description", "clients", "callback_url", "auth_token", "provider_config"]
    resource_type_fields = ["name", "name_en", "sensitivity", "path", "version", "description", "provider_config"]
    action_fields = ["name", "name_en", "sensitivity", "type", "version", "description"]

    def get_iam_systems(self) -> Dict[str, List[dict]]:
        return group_by(api.bk_iam.get_systems(), operator.itemgetter("id"))

    @transaction.atomic
    def sync_systems(self):
        iam_systems = super().sync_systems()
        # 串行同步IAM V3系统角色信息
        sync_iam_v3_system_roles(iam_systems)

    def get_system_info_map(self, instance_ids: List[str]) -> Dict[str, dict]:
        system_info_requests = [{"system_id": system_id} for system_id in instance_ids]
        system_infos = api.bk_iam.get_system_info.bulk_request(system_info_requests)
        system_info_map = dict()
        for system_info in system_infos:
            base_info = system_info["base_info"]
            system_info_map[system_info["base_info"]["id"]] = {
                "name": base_info["name"],
                "description": base_info["description"],
                "clients": base_info["clients"],
                "provider_config": base_info["provider_config"],
                "callback_url": base_info["provider_config"].get("host"),
                "auth_token": base_info["provider_config"].get("token"),
            }
        return system_info_map

    def get_resources_actions(self, instance_ids: List[str]) -> Dict[str, dict]:
        system_info_requests = [{"system_id": system_id} for system_id in instance_ids]
        system_infos = api.bk_iam.get_system_info.bulk_request(system_info_requests)
        data = {}
        for i in range(len(system_infos)):
            system_info = system_infos[i]
            system_id = instance_ids[i]
            data[system_id] = {
                "resource_types": [
                    {
                        "id": resource_type["id"],
                        "name": resource_type["name"],
                        "name_en": resource_type["name_en"],
                        "sensitivity": resource_type["sensitivity"],
                        "provider_config": resource_type["provider_config"],
                        "path": resource_type["provider_config"].get("path", ""),
                        "version": resource_type["version"],
                        "description": resource_type["description"],
                    }
                    for resource_type in system_info["resource_types"]
                ],
                "actions": system_info["actions"],
            }
        return data


class IAMV4SystemSyncer(IamSystemSyncer):
    source_type = SystemSourceTypeEnum.IAM_V4
    system_info_fields = ["name", "description", "clients", "callback_url", "auth_token", "managers"]
    resource_type_fields = ["name", "name_en", "ancestors"]
    action_fields = ["name", "name_en", "resource_type_ids"]

    def get_iam_systems(self) -> Dict[str, dict]:
        return group_by(api.bk_iam_v4.list_system.fetch_all(), operator.itemgetter("id"))

    def get_system_info_map(self, instance_ids: List[str]) -> Dict[str, dict]:
        system_info_requests = [{"system_id": system_id, "fields": "system_info"} for system_id in instance_ids]
        bulk_resp = api.bk_iam_v4.retrieve_system.bulk_request(system_info_requests)
        system_info_map = dict()
        for resp in bulk_resp:
            system_info = resp["system_info"]
            system_info_map[system_info["id"]] = {
                "name": system_info["name"],
                "description": system_info["description"],
                "callback_url": system_info["callback_url"],
                "auth_token": system_info["auth_token"],
                "clients": system_info["clients"],
                "managers": system_info["managers"],
            }
        return system_info_map

    def get_resources_actions(self, instance_ids: List[str]) -> Dict[str, dict]:
        system_info_requests = [
            {"system_id": system_id, "fields": "resource_types,actions"} for system_id in instance_ids
        ]
        bulk_resp = api.bk_iam_v4.retrieve_system.bulk_request(system_info_requests)
        data = {}
        for i in range(len(bulk_resp)):
            system_info = bulk_resp[i]
            system_id = instance_ids[i]
            data[system_id] = {
                "resource_types": [
                    {
                        "id": resource_type["id"],
                        "name": resource_type["name"],
                        "name_en": resource_type["name"],
                        'ancestors': resource_type['ancestors'],
                    }
                    for resource_type in system_info["resource_types"]
                ],
                "actions": [
                    {
                        "id": action["id"],
                        "name": action["name"],
                        "name_en": action["name"],
                        'resource_type_ids': [action['resource_type_id']] if action['resource_type_id'] else [],
                    }
                    for action in system_info["actions"]
                ],
            }

        return data


def sync_iam_v3_system_roles(iam_systems):
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
