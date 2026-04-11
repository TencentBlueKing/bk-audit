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


class Risk(ResourceTypeMeta):
    system_id = settings.BK_IAM_SYSTEM_ID
    id = "risk"
    name = gettext("风险")
    selection_mode = "instance"
    related_instance_selections = [{"system_id": system_id, "id": "risk"}]

    @classmethod
    def create_instance(cls, instance_id: str, attribute=None) -> Resource:
        return cls.batch_create_instance([instance_id], attribute)[0][0]

    @classmethod
    def batch_create_instance(cls, instance_ids, attribute=None) -> List[List[Resource]]:
        from services.web.risk.models import Risk as RiskModel

        risks = RiskModel.objects.filter(risk_id__in=instance_ids).distinct().order_by().only("risk_id", "strategy_id")
        risk_map = {risk.risk_id: risk for risk in risks}

        # 收集所有 risk 对应的 strategy_id，通过策略绑定的场景反查 scene_id
        strategy_ids = {str(risk.strategy_id) for risk in risks if risk.strategy_id}
        scene_bindings = ResourceBindingScene.objects.filter(
            binding__resource_type=ResourceVisibilityType.STRATEGY,
            binding__resource_id__in=list(strategy_ids),
        ).values_list("binding__resource_id", "scene_id")
        # strategy_id → scene_id 映射（业务约束：一个策略只绑定一个场景）
        strategy_scene_map = {rid: str(sid) for rid, sid in scene_bindings}

        resources = []
        for instance_id in instance_ids:
            resource = cls.create_simple_instance(instance_id, attribute)
            instance_name = instance_id
            risk = risk_map.get(instance_id)
            if risk:
                instance_name = risk.risk_id
            # 通过策略找到场景：risk.strategy_id → strategy_scene_map
            scene_id = ""
            if risk and risk.strategy_id:
                scene_id = strategy_scene_map.get(str(risk.strategy_id), "")
            resource.attribute = {
                "id": str(resource.id),
                "name": instance_name,
                KEYWORD_BK_IAM_PATH: f"/scene,{scene_id}/risk,{instance_id}/",
            }
            resources.append([resource])
        return resources


class TicketPermission(ResourceTypeMeta):
    system_id = settings.BK_IAM_SYSTEM_ID
    id = "ticket_permission"
    name = gettext("风险工单权限")
    selection_mode = "instance"
    related_instance_selections = [{"system_id": system_id, "id": id}]


class TicketNode(ResourceTypeMeta):
    system_id = settings.BK_IAM_SYSTEM_ID
    id = "ticket_node"
    name = gettext("风险处理记录")
    selection_mode = "instance"
    related_instance_selections = [{"system_id": system_id, "id": id}]


class ManualEvent(ResourceTypeMeta):
    system_id = settings.BK_IAM_SYSTEM_ID
    id = "manual_event"
    name = gettext("手工事件")
    selection_mode = "instance"
    related_instance_selections = [{"system_id": system_id, "id": "manual_event"}]

    @classmethod
    def create_instance(cls, instance_id: str, attribute=None) -> Resource:
        return cls.batch_create_instance([instance_id], attribute)[0][0]

    @classmethod
    def batch_create_instance(cls, instance_ids, attribute=None) -> List[List[Resource]]:
        from services.web.risk.models import ManualEvent as ManualEventModel

        manual_events = (
            ManualEventModel.objects.filter(manual_event_id__in=instance_ids)
            .distinct()
            .order_by()
            .only("manual_event_id", "raw_event_id", "strategy_id")
        )
        event_map = {str(event.manual_event_id): event for event in manual_events}

        # 收集所有 manual_event 对应的 strategy_id，通过策略绑定的场景反查 scene_id
        strategy_ids = {str(event.strategy_id) for event in manual_events if event.strategy_id}
        scene_bindings = ResourceBindingScene.objects.filter(
            binding__resource_type=ResourceVisibilityType.STRATEGY,
            binding__resource_id__in=list(strategy_ids),
        ).values_list("binding__resource_id", "scene_id")
        # strategy_id → scene_id 映射（业务约束：一个策略只绑定一个场景）
        strategy_scene_map = {rid: str(sid) for rid, sid in scene_bindings}

        resources = []
        for instance_id in instance_ids:
            resource = cls.create_simple_instance(instance_id, attribute)
            manual_event = event_map.get(str(instance_id))
            # 通过策略找到场景
            scene_id = ""
            if manual_event and manual_event.strategy_id:
                scene_id = strategy_scene_map.get(str(manual_event.strategy_id), "")
            resource.attribute = {
                "id": str(resource.id),
                "name": (manual_event.raw_event_id if manual_event and manual_event.raw_event_id else str(resource.id)),
                KEYWORD_BK_IAM_PATH: f"/scene,{scene_id}/manual_event,{instance_id}/",
            }
            resources.append([resource])
        return resources
