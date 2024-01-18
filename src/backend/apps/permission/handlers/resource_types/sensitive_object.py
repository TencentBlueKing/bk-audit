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

from typing import Type, Union

from django.conf import settings
from django.utils.translation import gettext
from iam import Resource

from apps.meta.constants import SensitiveResourceTypeEnum
from apps.meta.models import Action, ResourceType
from apps.meta.models import SensitiveObject as SensitiveObjectModel
from apps.permission.handlers.resource_types import ResourceTypeMeta


class SensitiveObject(ResourceTypeMeta):
    system_id = settings.BK_IAM_SYSTEM_ID
    id = "sensitive_object"
    name = gettext("敏感信息对象")
    selection_mode = "instance"
    related_instance_selections = [
        {"system_id": system_id, "id": "sensitive_action_list"},
        {"system_id": system_id, "id": "sensitive_resource_type_list"},
    ]

    @classmethod
    def _create_instance(
        cls,
        instance_id: str,
        filter_dict: dict,
        attribute: dict = None,
        get_id: callable = None,
        get_name: callable = None,
        get_path: callable = None,
    ) -> Resource:
        sensitive_obj = SensitiveObjectModel.objects.filter(**filter_dict).first()

        if not sensitive_obj:
            return cls.create_simple_instance(
                instance_id=instance_id, attribute=attribute or {"id": str(instance_id), "name": str(instance_id)}
            )

        return cls.create_simple_instance(
            instance_id=instance_id,
            attribute={
                "id": get_id(sensitive_obj),
                "name": get_name(sensitive_obj),
                "_bk_iam_path_": get_path(sensitive_obj),
            },
        )

    @classmethod
    def create_instance(cls, instance_id: str, attribute=None) -> Resource:
        from apps.permission.handlers.resource_types import ResourceEnum

        return cls._create_instance(
            instance_id=instance_id,
            filter_dict={"id": instance_id},
            attribute=attribute,
            get_id=lambda sensitive_obj: str(sensitive_obj.id),
            get_name=lambda sensitive_obj: str(sensitive_obj.name),
            get_path=lambda sensitive_obj: "/{},{}/{},{}/".format(
                ResourceEnum.SYSTEM.id,
                sensitive_obj.system_id,
                "sensitive_resource_type"
                if sensitive_obj.resource_type == SensitiveResourceTypeEnum.RESOURCE.value
                else "sensitive_action",
                sensitive_obj.resource_id,
            ),
        )


class SensitiveObjectInstance(SensitiveObject):
    @classmethod
    def create_instance(
        cls,
        instance_id: str,
        attribute=None,
        resource_type: str = None,
        model_class: Union[Type[Action], Type[ResourceType]] = None,
    ) -> Resource:
        from apps.permission.handlers.resource_types import ResourceEnum

        return cls._create_instance(
            instance_id=instance_id,
            filter_dict={"resource_type": resource_type, "resource_id": instance_id},
            attribute=attribute,
            get_id=lambda sensitive_obj: str(sensitive_obj.resource_id),
            get_name=lambda sensitive_obj: model_class.get_name(
                system_id=sensitive_obj.system_id,
                instance_id=sensitive_obj.resource_id,
                default=sensitive_obj.resource_id,
            ),
            get_path=lambda sensitive_obj: "/{},{}/".format(
                ResourceEnum.SYSTEM.id,
                sensitive_obj.system_id,
            ),
        )


class SensitiveAction(SensitiveObjectInstance):
    id = "sensitive_action"
    name = gettext("敏感操作")
    related_instance_selections = []

    @classmethod
    def create_instance(cls, instance_id: str, attribute=None, *args, **kwargs) -> Resource:
        return super().create_instance(
            instance_id=instance_id,
            attribute=attribute,
            resource_type=SensitiveResourceTypeEnum.ACTION.value,
            model_class=Action,
        )


class SensitiveResourceType(SensitiveObjectInstance):
    id = "sensitive_resource_type"
    name = gettext("敏感资源类型")
    related_instance_selections = []

    @classmethod
    def create_instance(cls, instance_id: str, attribute=None, *args, **kwargs) -> Resource:
        return super().create_instance(
            instance_id=instance_id,
            attribute=attribute,
            resource_type=SensitiveResourceTypeEnum.RESOURCE.value,
            model_class=ResourceType,
        )
