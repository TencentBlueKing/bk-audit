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

from dataclasses import dataclass
from typing import List

from bk_resource import api
from bk_resource.exceptions import APIRequestError
from iam import OP
from iam.contrib.converter.base import Converter
from iam.eval.expression import field_value_convert

from services.web.vision.exceptions import VisionPermissionInvalid


@dataclass
class DeptMatch:
    method: str = OP.EQ
    value: List[str] = None

    def __post_init__(self):
        self.value = self.value or []


class DeptConvertor(Converter):
    """
    转换为组织架构
    """

    def convert(self, data: dict) -> DeptMatch:
        op = data["op"]

        if op == OP.AND:
            return self._and(data["content"])
        elif op == OP.OR:
            return self._or(data["content"])

        value = data["value"]
        field = data["field"]

        op_func = {
            OP.EQ: self._starts_with,
            OP.STARTS_WITH: self._starts_with,
            OP.IN: self._in,
        }.get(op)

        if op_func is None:
            raise VisionPermissionInvalid()

        # 权限中心保留字预处理
        field, value = field_value_convert(op, field, value)

        # key mapping
        if self.key_mapping and field in self.key_mapping:
            field = self.key_mapping.get(field)

        # value hooks
        dept_info: DeptMatch = op_func(field, value)
        dept_info.value = [self._get_dept_name(dept) for dept in dept_info.value]
        return dept_info

    def _get_dept_name(self, dept_id: str) -> str:
        """
        获取组织架构名称
        """

        # 获取部门信息
        try:
            departments_data = api.user_manage.retrieve_department(department_id=dept_id)
        except APIRequestError:
            departments_data = {}

        # 解析数据
        return departments_data.get("full_name", dept_id)

    def _and(self, content) -> DeptMatch:
        data = DeptMatch()
        results = [self.convert(c) for c in content]
        for result in results:
            if not data.value or result.method == OP.IN:
                data.value = result.value
        return data

    def _or(self, content) -> DeptMatch:
        data = DeptMatch()
        results: List[DeptMatch] = [self.convert(c) for c in content]
        for result in results:
            data.value.extend(result.value)
        return data

    def _starts_with(self, left, right) -> DeptMatch:
        # 最后一层直接返回
        if right.isdigit():
            return DeptMatch(method=OP.STARTS_WITH, value=[right])
        # 多层只需要最后一层组织架构
        dept_id = right.split("/")[-2].split(",")[-1]
        return DeptMatch(method=OP.STARTS_WITH, value=[dept_id])

    def _in(self, left, right) -> DeptMatch:
        return DeptMatch(method=OP.IN, value=right)

    def _eq(self, left, right):
        raise VisionPermissionInvalid()

    def _not_eq(self, left, right):
        raise VisionPermissionInvalid()

    def _not_in(self, left, right):
        raise VisionPermissionInvalid()

    def _contains(self, left, right):
        raise VisionPermissionInvalid()

    def _not_contains(self, left, right):
        raise VisionPermissionInvalid()

    def _not_starts_with(self, left, right):
        raise VisionPermissionInvalid()

    def _ends_with(self, left, right):
        raise VisionPermissionInvalid()

    def _not_ends_with(self, left, right):
        raise VisionPermissionInvalid()

    def _lt(self, left, right):
        raise VisionPermissionInvalid()

    def _lte(self, left, right):
        raise VisionPermissionInvalid()

    def _gt(self, left, right):
        raise VisionPermissionInvalid()

    def _gte(self, left, right):
        raise VisionPermissionInvalid()

    def _any(self, left, right):
        raise VisionPermissionInvalid()
