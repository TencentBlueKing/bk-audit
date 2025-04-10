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

from bk_resource import resource

from apps.permission.handlers.actions import ActionEnum
from core.exceptions import PermissionException


class SearchLogPermission:
    @classmethod
    def get_auth_systems(cls, namespace) -> (list, list):
        systems = resource.meta.system_list_all(namespace=namespace, action_ids=ActionEnum.SEARCH_REGULAR_EVENT.id)
        authorized_systems = [
            system["id"] for system in systems if system["permission"].get(ActionEnum.SEARCH_REGULAR_EVENT.id)
        ]
        return systems, authorized_systems

    @classmethod
    def any_search_log_permission(cls, namespace) -> None:
        if not cls.get_auth_systems(namespace)[1]:
            from apps.permission.handlers.permission import Permission

            apply_data, apply_url = Permission().get_apply_data([ActionEnum.SEARCH_REGULAR_EVENT])
            raise PermissionException(
                action_name=ActionEnum.SEARCH_REGULAR_EVENT.name,
                apply_url=apply_url,
                permission=apply_data,
            )
