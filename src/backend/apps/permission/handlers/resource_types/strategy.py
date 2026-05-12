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

from django.conf import settings
from django.utils.translation import gettext
from iam import Resource
from iam.eval.constants import KEYWORD_BK_IAM_PATH

from apps.permission.handlers.resource_types import ResourceTypeMeta
from services.web.scene.constants import ResourceVisibilityType
from services.web.scene.models import ResourceBindingScene
from services.web.strategy_v2.models import LinkTable as LinkTableModel
from services.web.strategy_v2.models import Strategy as StrategyModel


class Strategy(ResourceTypeMeta):
    system_id = settings.BK_IAM_SYSTEM_ID
    id = "strategy"
    name = gettext("审计策略")
    selection_mode = "instance"
    related_instance_selections = [{"system_id": system_id, "id": "strategy"}]

    @classmethod
    def create_instance(cls, instance_id: str, attribute=None) -> Resource:
        return cls.batch_create_instance([instance_id], attribute=attribute)[0][0]

    @classmethod
    def batch_create_instance(cls, instance_ids, attribute=None) -> List[List[Resource]]:
        strategies = StrategyModel.objects.filter(strategy_id__in=instance_ids).only("strategy_id", "strategy_name")
        strategy_map = {str(strategy.strategy_id): strategy for strategy in strategies}
        scene_bindings = ResourceBindingScene.objects.filter(
            scene__is_deleted=False,
            binding__resource_type=ResourceVisibilityType.STRATEGY,
            binding__resource_id__in=[str(instance_id) for instance_id in instance_ids],
        ).values_list("binding__resource_id", "scene_id")
        strategy_scene_map = {resource_id: str(scene_id) for resource_id, scene_id in scene_bindings}

        resources = []
        for instance_id in instance_ids:
            resource = cls.create_simple_instance(instance_id, attribute)
            instance_key = str(instance_id)
            strategy = strategy_map.get(instance_key)
            instance_name = strategy.strategy_name if strategy else instance_key
            scene_id = strategy_scene_map.get(instance_key, "")
            resource.attribute = {
                "id": instance_key,
                "name": instance_name,
                KEYWORD_BK_IAM_PATH: f"/scene,{scene_id}/",
            }
            resources.append([resource])
        return resources


class LinkTable(ResourceTypeMeta):
    system_id = settings.BK_IAM_SYSTEM_ID
    id = "link_table"
    name = gettext("联表")
    selection_mode = "instance"
    related_instance_selections = [{"system_id": system_id, "id": "link_table"}]

    @classmethod
    def create_instance(cls, instance_id: str, attribute=None) -> Resource:
        return cls.batch_create_instance([instance_id], attribute=attribute)[0][0]

    @classmethod
    def batch_create_instance(cls, instance_ids, attribute=None) -> List[List[Resource]]:
        link_tables = LinkTableModel.list_max_version_link_table().filter(uid__in=instance_ids).only("uid", "name")
        link_table_map = {link_table.uid: link_table for link_table in link_tables}
        scene_bindings = ResourceBindingScene.objects.filter(
            scene__is_deleted=False,
            binding__resource_type=ResourceVisibilityType.LINK_TABLE,
            binding__resource_id__in=[str(instance_id) for instance_id in instance_ids],
        ).values_list("binding__resource_id", "scene_id")
        link_table_scene_map = {resource_id: str(scene_id) for resource_id, scene_id in scene_bindings}

        resources = []
        for instance_id in instance_ids:
            resource = cls.create_simple_instance(instance_id, attribute)
            instance_key = str(instance_id)
            link_table = link_table_map.get(instance_key)
            instance_name = link_table.name if link_table else instance_key
            scene_id = link_table_scene_map.get(instance_key, "")
            resource.attribute = {
                "id": instance_key,
                "name": instance_name,
                KEYWORD_BK_IAM_PATH: f"/scene,{scene_id}/",
            }
            resources.append([resource])
        return resources


class StrategyTag(ResourceTypeMeta):
    system_id = settings.BK_IAM_SYSTEM_ID
    id = "strategy_tag"
    name = gettext("策略标签")
    selection_mode = "instance"
    related_instance_selections: list = []

    @classmethod
    def create_instance(cls, instance_id: str, attribute=None) -> Resource:
        from services.web.strategy_v2.models import StrategyTag as StrategyTagModel

        resource = cls.create_simple_instance(instance_id, attribute)

        instance_name = str(instance_id)
        strategy_tag = StrategyTagModel.objects.select_related("tag").filter(pk=int(instance_id)).first()

        if strategy_tag and strategy_tag.tag:
            instance_name = strategy_tag.tag.tag_name

        resource.attribute = {"id": str(instance_id), "name": instance_name}
        return resource
