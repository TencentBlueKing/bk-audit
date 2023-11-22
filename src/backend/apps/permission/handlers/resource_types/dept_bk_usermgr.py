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

from bk_resource import api
from bk_resource.exceptions import APIRequestError
from django.utils.translation import gettext
from iam import Resource

from apps.permission.handlers.resource_types import ResourceTypeMeta


class DeptBKUsermgr(ResourceTypeMeta):
    system_id = "bk_usermgr"
    id = "department"
    name = gettext("组织架构")
    selection_mode = "instance"
    related_instance_selections = [{"system_id": system_id, "id": "department"}]

    @classmethod
    def create_instance(cls, instance_id: str, attribute=None) -> Resource:
        full_name = instance_id

        try:
            params = {"exact_lookups": instance_id.split("/")[-1], "lookup_field": "name"}
            data = api.user_manage.list_departments(**params)["results"]
        except APIRequestError:
            data = []

        for dept in data:
            if dept["full_name"] == instance_id:
                instance_id = dept["id"]

        resource = cls.create_simple_instance(instance_id, attribute)
        resource.attribute = {"id": str(instance_id), "name": full_name}
        return resource
