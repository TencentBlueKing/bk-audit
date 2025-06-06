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
from typing import Callable, Dict, List, Tuple

from blueapps.utils.logger import logger

from apps.meta.constants import SystemAuditStatusEnum, SystemSortFieldEnum
from apps.meta.models import System


def wrapper_system_status(namespace: str, systems: List[dict]) -> List[dict]:
    """
    绑定系统状态
    """

    try:
        from services.web.databus.handler.system_status import fetch_system_status

        system_status_map: Dict[str, dict] = fetch_system_status(namespace, [system["system_id"] for system in systems])
    except ImportError as e:
        logger.warning(f"Failed to fetch system status: {e}")
        system_status_map = {}
    for system in systems:
        # 日志上报状态
        status_map = system_status_map.get(system["system_id"], {})
        tail_log_time_map = status_map.get("tail_log_time_map", {})
        system_status = status_map.get("system_status")
        system["last_time"] = tail_log_time_map.get("last_time")
        system["status"] = tail_log_time_map.get("status")
        system["status_msg"] = tail_log_time_map.get("status_msg")
        # 系统状态
        system["system_status"] = system_status
    return systems


def is_system_manager_func(system_ids: List[str], username: str) -> Callable[[str], bool]:
    """
    判断是否是系统管理员
    """

    systems = System.objects.filter(system_id__in=system_ids).values("system_id", "managers")
    sys_dict = {system["system_id"]: system for system in systems}

    def _is_system_manager(system_id: str) -> bool:
        managers = sys_dict.get(system_id).get("managers", [])
        return username in managers

    return _is_system_manager


class BaseSystemSorter(abc.ABC):
    """系统排序规则基类"""

    @classmethod
    @abc.abstractmethod
    def sort_key(cls, system: Dict) -> Tuple:
        """返回排序key"""
        raise NotImplementedError()


class PermissionSorter(BaseSystemSorter):
    @classmethod
    def sort_key(cls, system: dict) -> Tuple:
        permission_obj = system.get("permission", {})
        priority_index = min(len([p for p in permission_obj.values() if p]), 1)
        return -priority_index, system.get("system_id") or system.get("id")


class FavoriteSorter(BaseSystemSorter):
    @classmethod
    def sort_key(cls, system: dict) -> Tuple:
        return (-int(system.get("favorite", False)),)


class AuditStatusSorter(BaseSystemSorter):
    @classmethod
    def sort_key(cls, system: Dict) -> Tuple:
        status_value = system.get("audit_status", "")
        return (-SystemAuditStatusEnum.get_order_value(status_value),)


# 排序规则注册表
SYSTEM_SORT_REGISTRY = {
    SystemSortFieldEnum.PERMISSION: PermissionSorter,
    SystemSortFieldEnum.FAVORITE: FavoriteSorter,
    SystemSortFieldEnum.AUDIT_STATUS: AuditStatusSorter,
}


def get_system_sort_key(sort_keys: list[str]) -> Callable[[dict], Tuple]:
    sort_classes = [SYSTEM_SORT_REGISTRY[key] for key in sort_keys if key in SYSTEM_SORT_REGISTRY]

    def sort_key(system: dict):
        # 拼接多个排序规则的 key
        return tuple(k for cls in sort_classes for k in cls.sort_key(system))

    return sort_key
