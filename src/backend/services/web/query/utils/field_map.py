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

from apps.meta.utils.fields import ACCESS_TYPE, RESULT_CODE, USER_IDENTIFY_TYPE
from core.utils.data import choices_to_select_list
from services.web.query.constants import (
    AccessTypeChoices,
    ResultCodeChoices,
    UserIdentifyTypeChoices,
)


class FieldMapHandler:
    def __init__(self, fields: list, timedelta: int, namespace: str):
        self.fields = fields
        self.timedelta = timedelta
        self.namespace = namespace

    @property
    def field_map(self):
        return self.get_db_fields()

    @property
    def query_fields(self) -> list:
        return [field for field in self.fields if field not in self.db_field_func_map.keys()]

    @property
    def db_fields(self) -> list:
        return [field for field in self.fields if field in self.db_field_func_map.keys()]

    def get_db_fields(self) -> dict:
        if not self.db_fields:
            return dict()
        return {field: self.get_db_field_items(field) for field in self.db_fields}

    @property
    def db_field_func_map(self) -> dict:
        return {
            ACCESS_TYPE.field_name: self._get_access_type,
            USER_IDENTIFY_TYPE.field_name: self._get_user_identify_type,
            RESULT_CODE.field_name: self._get_result_code,
        }

    def get_db_field_items(self, db_field: str):
        func = self.db_field_func_map.get(db_field)
        return func()

    def _get_access_type(self):
        return choices_to_select_list(AccessTypeChoices)

    def _get_user_identify_type(self):
        return choices_to_select_list(UserIdentifyTypeChoices)

    def _get_result_code(self):
        return choices_to_select_list(ResultCodeChoices)
