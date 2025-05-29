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

import json
from typing import Any, List

from bk_resource.base import Empty

from core.utils.data import extract_nested_value
from services.web.query.export.model import ExportConfig


class DataProcessor:
    """
    数据处理模块
    """

    def __init__(self, config: ExportConfig):
        self.config = config

    def format_value(self, value: Any) -> str:
        """
        格式化值
        """

        if isinstance(value, Empty):
            formatted_value = self.config.empty_value
        elif isinstance(value, (dict, list)):
            formatted_value = json.dumps(value, ensure_ascii=False)
        else:
            formatted_value = str(value)
        return formatted_value

    def format_data(self, data: dict) -> dict:
        """
        格式化数据
        """

        formatted = {}
        for field in self.config.export_fields:
            value = extract_nested_value(data.get(field.raw_name), field.keys)
            formatted[field.full_key] = self.format_value(value)
        return formatted

    def batch_format_data(self, batch_data: List[dict]) -> List[dict]:
        """
        批量格式化数据
        """

        return [self.format_data(log) for log in batch_data]
