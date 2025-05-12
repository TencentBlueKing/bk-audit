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
from collections import defaultdict
from dataclasses import dataclass
from functools import cached_property
from typing import Dict, List

from services.web.query.constants import (
    FieldCategoryEnum,
    LogExportField,
    LogExportFieldScope,
)
from services.web.query.models import LogExportTask


@dataclass
class ExportConfig:
    """
    导出配置模块
    """

    task: LogExportTask
    empty_value: str = ""

    @cached_property
    def category_fields(self) -> Dict[FieldCategoryEnum, List[LogExportField]]:
        """
        获取分类字段(指定字段，全部字段，标准字段)
        """

        # 获取原始字段配置
        if self.task.export_config["field_scope"] == LogExportFieldScope.SPECIFIED.value:
            fields = [
                LogExportField(raw_name=field["raw_name"], display_name=field["display_name"], keys=field["keys"])
                for field in self.task.export_config.get("fields", [])
            ]
        else:
            source_fields = LogExportFieldScope.get_fields(self.task.export_config["field_scope"])
            fields = [
                LogExportField(raw_name=str(field.field_name), display_name=str(field.description), keys=[])
                for field in source_fields
            ]

        # 分类字段
        category_fields: Dict[FieldCategoryEnum, List[LogExportField]] = defaultdict(list)
        for field in fields:
            category = FieldCategoryEnum.get_category_by_field(field)
            category_fields[category].append(field)

        return category_fields

    @cached_property
    def export_fields(self) -> List[LogExportField]:
        """
        获取导出字段(按分类顺序排序)
        """

        ordered_fields = []
        for category in FieldCategoryEnum.get_orders():
            ordered_fields.extend(self.category_fields.get(category, []))

        return ordered_fields
