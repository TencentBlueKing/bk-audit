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
import gc
from typing import Any, Dict, List

from core.exporter.constants import ExportField
from core.exporter.export import BaseXlsxFileExporter


class MultiSheetRiskExporterXlsx(BaseXlsxFileExporter):
    """
    用于导出风险数据的多 Sheet Excel 文件导出器。
    每个 Sheet 代表一个策略。
    """

    suffix = ".xlsx"
    header_format = {'bold': True, 'border': 1, 'bg_color': '#D3D3D3'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.header_fmt = self.workbook.add_format(self.header_format)

    def write(self, sheets_data: Dict[str, List[Dict[str, Any]]], sheets_headers: Dict[str, List[ExportField]]):
        """
        将数据写入多个 Sheet。
        :param sheets_data: 每个 sheet 的数据. 格式: {"sheet_name": [row_dict_1, row_dict_2]}
        :param sheets_headers: 每个 sheet 的表头. 格式: {"sheet_name": [ExportField_1, ExportField_2]}
        """

        sheet_names = sorted(sheets_headers.keys())

        for sheet_name in sheet_names:
            headers = sheets_headers[sheet_name]
            data_rows = sheets_data.get(sheet_name, [])

            # Excel 的 sheet 名称有长度限制 (31个字符)，并且不能包含某些特殊字符
            safe_sheet_name = (
                sheet_name.replace('[', '')
                .replace(']', '')
                .replace('*', '')
                .replace(':', '')
                .replace('?', '')
                .replace('/', '\\')
            )
            safe_sheet_name = safe_sheet_name[:31]

            worksheet = self.workbook.add_worksheet(safe_sheet_name)

            # 写入表头
            display_headers = [field.display_name for field in headers]
            worksheet.write_row(0, 0, display_headers, self.header_fmt)

            # 设置列宽
            worksheet.set_column(0, len(display_headers) - 1, 20)

            # 写入数据
            if not data_rows:
                continue

            raw_field_names = [field.raw_name for field in headers]
            for row_num, row_data in enumerate(data_rows, start=1):
                # 按表头顺序提取数据
                row_values = [str(row_data.get(raw_name, "")) for raw_name in raw_field_names]
                worksheet.write_row(row_num, 0, row_values)
            gc.collect()
