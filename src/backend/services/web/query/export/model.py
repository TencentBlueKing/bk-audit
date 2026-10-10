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

from services.web.query.ai_assistant.constants import AI_ASSISTANT_EXPORT_SOURCE
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
    def is_ai_assistant(self) -> bool:
        """AI 助手导出标记（export_config.source）：驱动单行表头/保序列宽等 AI 专属样式。

        常规日志检索导出（检索页）永不携带该标记，两行表头与固定列宽保持不变。
        """

        return self.task.export_config.get("source") == AI_ASSISTANT_EXPORT_SOURCE

    @cached_property
    def _scope_fields(self) -> List[LogExportField]:
        """按 field_scope 取原始导出字段（未分类排序）。"""

        if self.task.export_config["field_scope"] == LogExportFieldScope.SPECIFIED.value:
            return [
                LogExportField(raw_name=field["raw_name"], display_name=field["display_name"], keys=field["keys"])
                for field in self.task.export_config.get("fields", [])
            ]
        source_fields = LogExportFieldScope.get_fields(self.task.export_config["field_scope"])
        return [
            LogExportField(raw_name=str(field.field_name), display_name=str(field.description), keys=[])
            for field in source_fields
        ]

    @cached_property
    def category_fields(self) -> Dict[FieldCategoryEnum, List[LogExportField]]:
        """
        获取分类字段(指定字段，全部字段，标准字段)
        """

        # 分类字段
        category_fields: Dict[FieldCategoryEnum, List[LogExportField]] = defaultdict(list)
        for field in self._scope_fields:
            category = FieldCategoryEnum.get_category_by_field(field)
            category_fields[category].append(field)

        return category_fields

    @cached_property
    def flatten_extension(self) -> bool:
        """
        扩展字段平铺开关（任务 export_config.flatten_extension）
        """

        return bool(self.task.export_config.get("flatten_extension"))

    @cached_property
    def extension_keys(self) -> List[str]:
        """
        扩展字段平铺子键清单（任务 export_config.extension_keys）；
        元素为非空字符串，过滤非字符串/空值，保留给定顺序。
        """

        raw_keys = self.task.export_config.get("extension_keys") or []
        return [key for key in raw_keys if isinstance(key, str) and key]

    @cached_property
    def export_fields(self) -> List[LogExportField]:
        """
        获取导出字段(按分类顺序排序)
        """

        if self.is_ai_assistant:
            # AI 助手导出：保持给定字段顺序（SPECIFIED=前端"日志检索结果"列序/用户选择序；
            # 非分类重排——分类重排会打乱与前端结果表一致的展示顺序）
            ordered_fields = list(self._scope_fields)
        else:
            ordered_fields = []
            for category in FieldCategoryEnum.get_orders():
                ordered_fields.extend(self.category_fields.get(category, []))

        # 扩展字段平铺：把 extend_data 单列在**原位**替换为每个子键单独一列
        # （保持与前端结果列一致的顺序——拓展数据列在"操作（完整日志）"之前，
        # 验收 2026-10-09；字段集不含 extend_data 列时子键列按原行为追加尾部）
        if self.flatten_extension and self.extension_keys:
            extension_fields = [
                LogExportField(raw_name="extend_data", display_name=key, keys=[key]) for key in self.extension_keys
            ]
            if any(field.raw_name == "extend_data" and not field.keys for field in ordered_fields):
                flattened: List[LogExportField] = []
                for field in ordered_fields:
                    if field.raw_name == "extend_data" and not field.keys:
                        flattened.extend(extension_fields)
                    else:
                        flattened.append(field)
                ordered_fields = flattened
            else:
                ordered_fields.extend(extension_fields)

        return ordered_fields
