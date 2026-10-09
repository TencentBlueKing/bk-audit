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

from django.utils.translation import gettext_lazy

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
    def collector_field_map(self) -> dict:
        """Collector 选项均代表字面值，避免复用 ES 的“其他=反选”语义。

        选项不是允许值白名单；未知结果码/访问方式仍可直接作为过滤值。
        """
        options = self.field_map
        for field_name, other_value, label in (
            (RESULT_CODE.field_name, ResultCodeChoices.FAILED.value, gettext_lazy("结果码 -1")),
            (ACCESS_TYPE.field_name, AccessTypeChoices.OTHER.value, gettext_lazy("访问方式 -1")),
        ):
            for item in options.get(field_name, []):
                if str(item["id"]) == other_value:
                    item["name"] = str(label)
        return options

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
