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

from blueapps.utils.logger import logger
from django.db.models import QuerySet

from apps.meta.models import Action, DataMap, ResourceType, System
from apps.meta.utils.fields import SNAPSHOT_USER_INFO
from core.utils.data import choices_to_dict
from services.web.query.constants import AccessTypeChoices, UserIdentifyTypeChoices


class FieldValueHandler:
    """
    Load Value for Fields
    """

    value_key = "value"
    label_key = "label"

    def __init__(self, field_name: str, namespace: str, system_id: str = None):
        self.field_name = field_name
        self.namespace = namespace
        self.system_id = system_id
        self._values = []
        self._load_values()
        self._values.sort(key=lambda item: [item.get(self.label_key), item.get(self.value_key)])

    @property
    def values(self) -> List[dict]:
        return self._values

    def _load_values(self) -> None:
        # snapshot user info handler
        if self.field_name.find(SNAPSHOT_USER_INFO.field_name) != -1:
            handler_func = self._load_snapshot_user_info_field
        # load handler
        else:
            handler_func = getattr(self, f"_load_field_{self.field_name}", None)
        # check handler
        if handler_func is None or not callable(handler_func):
            logger.info("[FieldValueHandlerUnsupported] Field => %s", self.field_name)
            return
        # load value
        handler_func()

    def _load_field_system_id(self) -> None:
        self._values = self._db_data_to_list(
            System.objects.filter(namespace=self.namespace),
            get_id=lambda item: item.system_id,
            get_name=lambda item: f"{item.name}({item.system_id})",
        )

    def _load_field_resource_type_id(self) -> None:
        if self.system_id:
            self._values = self._db_data_to_list(
                ResourceType.objects.filter(system_id=self.system_id),
                get_id=lambda item: item.resource_type_id,
                get_name=lambda item: f"{item.name}({item.resource_type_id})",
            )
            return
        self._values = self._db_data_with_system_to_list(
            ResourceType.objects.all(),
            get_id=lambda item: item.resource_type_id,
            get_name=lambda item: f"{item.name}({item.resource_type_id})",
        )

    def _load_field_action_id(self) -> None:
        if self.system_id:
            self._values = self._db_data_to_list(
                Action.objects.filter(system_id=self.system_id),
                get_id=lambda item: item.action_id,
                get_name=lambda item: f"{item.name}({item.action_id})",
            )
            return
        self._values = self._db_data_with_system_to_list(
            Action.objects.all(),
            get_id=lambda item: item.action_id,
            get_name=lambda item: f"{item.name}({item.action_id})",
        )

    def _load_field_user_identify_type(self) -> None:
        self._values = choices_to_dict(UserIdentifyTypeChoices, self.value_key, self.label_key)

    def _load_field_access_type(self) -> None:
        self._values = choices_to_dict(AccessTypeChoices, self.value_key, self.label_key)

    def _db_data_to_list(
        self, data: QuerySet, get_id: callable = lambda item: item.id, get_name: callable = lambda item: item.name
    ) -> List[dict]:
        return [{self.value_key: get_id(instance), self.label_key: get_name(instance)} for instance in data]

    def _db_data_with_system_to_list(
        self, data: QuerySet, get_id: callable = lambda item: item.id, get_name: callable = lambda item: item.name
    ) -> List[dict]:
        data_map = {
            system.system_id: {
                self.label_key: f"{system.name}({system.system_id})",
                self.value_key: system.system_id,
                "children": [],
            }
            for system in System.objects.all()
        }
        for instance in data:
            data_map[instance.system_id]["children"].append(
                {self.value_key: get_id(instance), self.label_key: get_name(instance)}
            )
        return [value for value in data_map.values()]

    def _load_snapshot_user_info_field(self) -> None:
        data_field = self.field_name.replace(".", "__")
        data_map = DataMap.objects.filter(data_field=data_field)
        self._values = self._db_data_to_list(
            data_map, get_id=lambda item: item.data_key, get_name=lambda item: item.data_alias
        )
