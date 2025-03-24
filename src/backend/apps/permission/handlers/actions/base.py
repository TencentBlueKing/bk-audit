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
from iam import Action

from apps.permission.handlers.resource_types import ResourceTypeMeta


class ActionMeta(Action):
    """
    动作定义
    """

    def __init__(
        self,
        id: str,
        name: str,
        name_en: str,
        type: str,
        version: int,
        related_resource_types: List[ResourceTypeMeta] = None,
        related_actions: List["ActionMeta"] = None,
        description: str = "",
        description_en: str = "",
        system_id: str = "",
    ):
        super(ActionMeta, self).__init__(id)
        self.name = name
        self.name_en = name_en
        self.type = type
        self.version = version
        self.related_resource_types = related_resource_types or []
        self.related_actions = related_actions or []
        self.description = description
        self.description_en = description_en
        self.system_id = system_id if system_id else settings.BK_IAM_SYSTEM_ID

    def to_json(self):
        return {
            "id": self.id,
            "name": self.name,
            "name_en": self.name_en,
            "type": self.type,
            "version": self.version,
            "related_resource_types": [resource.to_json() for resource in self.related_resource_types],
            "related_actions": [action.id for action in self.related_actions],
            "description": self.description,
            "description_en": self.description_en,
        }

    def is_read_action(self):
        """
        是否为读权限
        """
        return self.type == "view"

    def get_action_id(self):
        if self.system_id == settings.BK_IAM_SYSTEM_ID:
            return self.id
        return self.id.replace(f"_{self.system_id}", "")
