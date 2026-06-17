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

from apps.notice.models import NoticeGroup as NoticeGroupModel
from apps.permission.constants import IAMV4Role
from apps.permission.handlers.resource_types import ResourceTypeMeta
from services.web.scene.constants import ResourceVisibilityType
from services.web.scene.models import ResourceBindingScene


class NoticeGroup(ResourceTypeMeta):
    system_id = settings.BK_IAM_SYSTEM_ID
    id = "notice_group"
    name = gettext("通知组")
    selection_mode = "instance"
    related_instance_selections = [{"system_id": system_id, "id": "notice_group"}]
    iam_v4_batch_scope = True
    iam_v4_creator_role_id = IAMV4Role.SCENE_ADMIN

    @classmethod
    def create_instance(cls, instance_id: str, attribute=None) -> Resource:
        return cls.batch_create_instance([instance_id], attribute=attribute)[0][0]

    @classmethod
    def batch_create_instance(cls, instance_ids, attribute=None) -> List[List[Resource]]:
        notice_groups = NoticeGroupModel.objects.filter(group_id__in=instance_ids).only("group_id", "group_name")
        notice_group_map = {str(notice_group.group_id): notice_group for notice_group in notice_groups}

        scene_bindings = ResourceBindingScene.objects.filter(
            scene__is_deleted=False,
            binding__resource_type=ResourceVisibilityType.NOTICE_GROUP,
            binding__resource_id__in=[str(instance_id) for instance_id in instance_ids],
        ).values_list("binding__resource_id", "scene_id")
        notice_group_scene_map = {resource_id: str(scene_id) for resource_id, scene_id in scene_bindings}

        resources = []
        for instance_id in instance_ids:
            resource = cls.create_simple_instance(instance_id, attribute)
            instance_key = str(instance_id)
            notice_group = notice_group_map.get(instance_key)
            instance_name = notice_group.group_name if notice_group else instance_key
            scene_id = notice_group_scene_map.get(instance_key, "")
            resource.attribute = {
                "id": instance_key,
                "name": instance_name,
                KEYWORD_BK_IAM_PATH: f"/scene,{scene_id}/",
            }
            resources.append([resource])
        return resources

    @classmethod
    def get_iam_v4_creator_authorization_resource(cls, resource: Resource) -> Resource:
        scene_id = (
            ResourceBindingScene.objects.filter(
                scene__is_deleted=False,
                binding__resource_type=ResourceVisibilityType.NOTICE_GROUP,
                binding__resource_id=str(resource.id),
            )
            .values_list("scene_id", flat=True)
            .first()
        )
        if not scene_id:
            raise ValueError(f"resource {resource.type}:{resource.id} has no active scene binding")
        return Resource(settings.BK_IAM_SYSTEM_ID, "scene", str(scene_id), {"name": str(scene_id)})
