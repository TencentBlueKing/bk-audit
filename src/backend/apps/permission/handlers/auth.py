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

from apps.permission.exceptions import (
    ActionNotExistError,
    ActionSystemConfuse,
    ResourceAttrTypeConfuse,
    ResourceAttrTypeNotExists,
    ResourceNotExistError,
)
from apps.permission.handlers.actions import ActionMeta, get_action_by_id
from apps.permission.handlers.resource_types import get_resource_by_id
from apps.permission.handlers.resource_types.base import InstanceInfo, ResourceTypeMeta


class AuthInfo:
    system_id: str
    actions: List[ActionMeta]
    resource_type_meta: ResourceTypeMeta
    instances: List[InstanceInfo]

    def __init__(
        self,
        system_id: str,
        actions: List[ActionMeta],
        resource_type_meta: ResourceTypeMeta = None,
        instances: List[InstanceInfo] = None,
    ):
        self.system_id = system_id
        self.actions = actions
        self.resource_type_meta = resource_type_meta if resource_type_meta else []
        self.instances = instances if instances else []


class AuthHandler(object):
    @classmethod
    def get_auth_info(cls, action_ids: List[str], instance_ids: List[str]):
        # step 1: 获取资源类型ID
        resource_type_id = ""
        system_id = ""
        actions = []
        for action_id in action_ids:
            action = get_action_by_id(action_id)
            if not action:
                raise ActionNotExistError()

            # 判断系统是否冲突
            if system_id != "" and action.system_id != system_id:
                raise ActionSystemConfuse()
            system_id = action.system_id

            # 判断资源类型是否冲突
            if action.related_resource_types:
                if resource_type_id and resource_type_id != action.related_resource_types[0].id:
                    raise ResourceAttrTypeConfuse()
                resource_type_id = action.related_resource_types[0].id
            actions.append(action)

        # step 2: 构造资源信息
        if resource_type_id and not instance_ids:
            raise ResourceNotExistError()

        # step 3: 不需要关联实例直接返回
        if not resource_type_id:
            return AuthInfo(system_id=system_id, actions=actions)

        # step 4: 返回带实例信息
        resource_type_meta = get_resource_by_id(resource_type_id)
        if not resource_type_meta:
            raise ResourceAttrTypeNotExists(attr_type=resource_type_id)

        instances = []
        if instance_ids:
            instances = [InstanceInfo(id, resource_type_id) for id in instance_ids]

        return AuthInfo(
            system_id=system_id, actions=actions, resource_type_meta=resource_type_meta, instances=instances
        )
