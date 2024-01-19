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
from typing import List

from django.conf import settings
from django.core.cache import cache
from django.utils.translation import gettext
from iam import Resource

from apps.permission.constants import PERMISSION_CACHE_EXPIRE
from core.utils.tools import group_by


class InstanceInfo(object):
    """
    实例元数据
    """

    id: str = ""
    type: str = ""

    def __init__(self, id: str, type: str):
        self.id = id
        self.type = type

    def to_json(self):
        return {
            "id": self.id,
            "type": self.type,
        }


class ResourceTypeMeta(metaclass=abc.ABCMeta):
    """
    资源类型元数据
    """

    system_id: str = ""
    id: str = ""
    name: str = ""
    selection_mode: str = ""
    related_instance_selections: List = ""

    @classmethod
    def to_json(cls):
        return {
            "system_id": cls.system_id,
            "id": cls.id,
            "selection_mode": cls.selection_mode,
            "related_instance_selections": cls.related_instance_selections,
        }

    @classmethod
    def create_simple_instance(cls, instance_id: str, attribute=None) -> Resource:
        """
        创建简单资源实例
        :param instance_id: 实例ID
        :param attribute: 属性kv对
        """
        attribute = attribute or {}
        return Resource(cls.system_id, cls.id, str(instance_id), attribute)

    @classmethod
    def create_instance(cls, instance_id: str, attribute=None) -> Resource:
        """
        创建资源实例（带实例名称）可由子类重载
        :param instance_id: 实例ID
        :param attribute: 属性kv对
        """
        return cls.create_simple_instance(instance_id, attribute)

    @classmethod
    def batch_create_instance(cls, instance_ids, actions=None):
        """
        批量创建实例
        """
        return [[cls.create_instance(instance_id, actions=actions)] for instance_id in instance_ids]

    @classmethod
    def batch_create_by_instances(cls, instances, actions=None, cache_key=None):
        """
        批量创建实例列表 用于鉴权实例数据量大的需求
        :param instances 实例列表
        :param cache_key 缓存key值
        """
        if not cache_key:
            return cls.batch_create_instance([i.id for i in instances], actions=actions)

        mapping = group_by(instances, operator.attrgetter("id"))
        instance_ids = set(mapping.keys())
        resource = cache.get(cache_key)

        res = []
        if resource:
            res.extend([[resource[_id]] for _id in instance_ids.intersection(set(resource.keys()))])
            res.extend(
                [
                    [cls.create_instance(mapping[d][0], actions=actions)]
                    for d in instance_ids.difference(set(resource.keys()))
                ]
            )
            return res

        cache_item = {}
        res.extend([[cache_item.setdefault(p.id, cls.create_instance(p, actions=actions))] for p in instances])
        cache.set(cache_key, cache_item, PERMISSION_CACHE_EXPIRE)

        return res


class System(ResourceTypeMeta):
    system_id = settings.BK_IAM_SYSTEM_ID
    id = "system"
    name = gettext("接入系统")
    selection_mode = "instance"
    related_instance_selections = [{"system_id": system_id, "id": "system"}]
