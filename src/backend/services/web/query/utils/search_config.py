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
import dataclasses
from functools import cached_property
from typing import Dict, List

from apps.meta.models import Field
from core.choices import register_choices
from core.sql.constants import Operator

# 检索条件操作符
QueryConditionOperator: Operator = register_choices("query_condition_operator")(Operator)


@dataclasses.dataclass
class FieldSearchConfig:
    """
    字段搜索配置模型
    """

    field: Field
    allow_operators: List[QueryConditionOperator]


@dataclasses.dataclass
class CollectorSearchConfig:
    """
    日志搜索配置
    """

    field_configs: list[FieldSearchConfig]
    field_category_map = {}

    @cached_property
    def allowed_operator_choices(self) -> list[tuple[str, str]]:
        """
        允许的操作符
        """

        return QueryConditionOperator.choices

    @cached_property
    def allowed_query_field_choices(self) -> list[tuple[str, str]]:
        """
        允许查询的字段
        """

        return [(field.field.field_name, field.field.description) for field in self.field_configs]

    def to_json(self) -> List[dict]:
        """
        转换为 JSON 对象
        """

        from services.web.query.constants import FieldCategoryEnum, LogExportField

        return [
            {
                "field": field_config.field.to_json(),
                "allow_operators": [operator for operator in field_config.allow_operators],
                "category": FieldCategoryEnum.get_category_by_field(
                    LogExportField(
                        raw_name=field_config.field.field_name,
                    )
                ),
            }
            for field_config in self.field_configs
        ]

    @cached_property
    def query_field_map(self) -> Dict[str, FieldSearchConfig]:
        """
        查询字段映射
        """

        return {config.field.field_name: config for config in self.field_configs}

    def judge_operator(self, field_name: str, keys: List[str], operator: str) -> bool:
        """
        判断操作符是否合法
        """

        # 不对嵌套字段进行校验
        if keys:
            return True
        if field := self.query_field_map.get(field_name):
            return operator in field.allow_operators
        return False
