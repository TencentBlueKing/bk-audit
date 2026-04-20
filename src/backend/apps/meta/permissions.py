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
from typing import List

from bk_resource import resource
from django.shortcuts import get_object_or_404
from rest_framework.permissions import BasePermission

from apps.meta.constants import SystemSourceTypeEnum
from apps.meta.exceptions import SystemNotEditable
from apps.meta.models import System
from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.drf import (
    AnyOfPermissions,
    InstanceActionPermission,
    InstancePermission,
)
from apps.permission.handlers.resource_types import ResourceEnum
from core.exceptions import PermissionException
from core.models import get_request_username
from services.web.common.constants import ScopeType


class SearchLogPermission:
    @classmethod
    def raise_system_view_permission_exception(cls) -> None:
        from apps.permission.handlers.permission import Permission

        apply_data, apply_url = Permission().get_apply_data([ActionEnum.VIEW_SYSTEM])
        raise PermissionException(
            action_name=ActionEnum.VIEW_SYSTEM.name,
            apply_url=apply_url,
            permission=apply_data,
        )

    @classmethod
    def _get_scene_scope_system_ids(cls, username: str) -> set[str]:
        from services.web.common.scope_permission import ScopeContext, ScopePermission

        scene_scope = ScopeContext(scope_type=ScopeType.CROSS_SCENE)
        return {str(system_id) for system_id in ScopePermission(username).get_system_ids_for_scope(scene_scope)}

    @classmethod
    def _get_system_scope_system_ids(cls, username: str, scope=None) -> set[str]:
        from services.web.common.scope_permission import ScopeContext, ScopePermission

        target_scope = scope or ScopeContext(scope_type=ScopeType.CROSS_SYSTEM)
        return {str(system_id) for system_id in ScopePermission(username).get_system_ids_for_scope(target_scope)}

    @classmethod
    def has_system_search_permission(cls, system_id: str, username: str) -> bool:
        if not system_id:
            return False

        target_system_id = str(system_id)
        if target_system_id in cls._get_system_scope_system_ids(username):
            return True
        return target_system_id in cls._get_scene_scope_system_ids(username)

    @classmethod
    def get_auth_systems(cls, namespace) -> (list, list):
        username = get_request_username()
        scoped_system_ids = cls._get_system_scope_system_ids(username) | cls._get_scene_scope_system_ids(username)
        systems = resource.meta.system_list_all(namespace=namespace)
        system_ids = {str(system["id"]) for system in systems}
        authorized_systems = [system_id for system_id in scoped_system_ids if system_id in system_ids]
        return systems, authorized_systems

    @classmethod
    def any_search_log_permission(cls, namespace) -> None:
        if not cls.get_auth_systems(namespace)[1]:
            cls.raise_system_view_permission_exception()

    @classmethod
    def get_scope_auth_systems(cls, scope_type: str, scope_id: str | None, username: str) -> list[str]:
        from services.web.common.scope_permission import ScopeContext, ScopePermission

        scope = ScopeContext(scope_type=scope_type, scope_id=scope_id)
        scoped_system_ids = {str(system_id) for system_id in ScopePermission(username).get_system_ids_for_scope(scope)}

        if not scoped_system_ids:
            cls.raise_system_view_permission_exception()
        return list(scoped_system_ids)


class SearchLogSystemSearchPermission(InstancePermission):
    """系统检索权限：系统查看权限 OR 可查看场景下授权系统。"""

    def has_permission(self, request, view) -> bool:
        system_id = self._get_instance_id(request, view)
        if SearchLogPermission.has_system_search_permission(system_id=system_id, username=get_request_username()):
            return True
        SearchLogPermission.raise_system_view_permission_exception()


class SystemManagerPermission(InstancePermission):
    def has_permission(self, request, view) -> bool:
        system_id = self._get_instance_id(request, view)
        system: System = get_object_or_404(System, system_id=system_id)
        username = get_request_username()
        return username in system.managers_list


class SystemEditPermission(InstancePermission):
    def has_permission(self, request, view) -> bool:
        system_id = self._get_instance_id(request, view)
        system: System = get_object_or_404(System, system_id=system_id)
        if system.source_type not in SystemSourceTypeEnum.get_editable_sources():
            raise SystemNotEditable(system_id=system.system_id)
        return True


class SystemPermissionHandler:
    @classmethod
    def _generate_permission(cls, action_enums, lookup_field=None, get_instance_id=None) -> BasePermission:
        """
        通用的权限生成方法，接收一个动作类型（如 VIEW 或 EDIT），
        根据这个生成相应的权限
        """

        return AnyOfPermissions(
            SystemManagerPermission(get_instance_id=get_instance_id),
            InstanceActionPermission(
                actions=action_enums,
                resource_meta=ResourceEnum.SYSTEM,
                lookup_field=lookup_field,
                get_instance_id=get_instance_id,
            ),
        )

    @classmethod
    def system_edit_permissions(cls, get_instance_id=None, lookup_field=None) -> List[BasePermission]:
        """
        获取编辑系统权限
        """

        return [
            SystemPermissionHandler._generate_permission(
                [ActionEnum.EDIT_SYSTEM], lookup_field=lookup_field, get_instance_id=get_instance_id
            ),
            SystemEditPermission(lookup_field=lookup_field, get_instance_id=get_instance_id),
        ]

    @classmethod
    def system_view_permissions(cls, get_instance_id=None, lookup_field=None) -> List[BasePermission]:
        """
        获取查看系统权限
        """

        return [
            SystemPermissionHandler._generate_permission(
                [ActionEnum.VIEW_SYSTEM], lookup_field=lookup_field, get_instance_id=get_instance_id
            )
        ]
