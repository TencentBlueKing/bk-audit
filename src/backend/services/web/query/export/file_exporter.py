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
import abc
import gc
import tempfile
from datetime import datetime
from functools import cached_property
from typing import List

import xlsxwriter
from blueapps.utils.logger import logger_celery
from django.core.files import File
from django.utils.translation import gettext_lazy

from core.utils.data import unique_id
from services.web.query.constants import LOG_FIELD_KEY_JOIN_CHAR, FieldCategoryEnum
from services.web.query.export.model import ExportConfig

# AI 日志检索导出的"扩展字段"分组文案（仅 flatten_extension 平铺开启时生效）：
# 拓展数据容器在所有白名单外，平铺后子键列落 CUSTOM 兜底分组（_write_category_header
# 按分类渲染合并表头）。flatten_extension 是 AI 助手导出专属参数（检索页导出永不传），
# 以此作渲染开关——检索页与非平铺 AI 导出的 CUSTOM 分组保持"自定义字段"label 不变，
# 避免影响既有日志检索的字段导出文案；全属 extend_data 容器系列（产品语义"拓展字段"
# 专指 extend_data 下钻，09-10 限定）的 CUSTOM 分组才渲染为"扩展字段"。
EXTEND_DATA_RAW_NAME = "extend_data"
EXTENSION_GROUP_LABEL = gettext_lazy("扩展字段")


class FileExporter(abc.ABC):
    """
    文件导出模块
    """

    def __init__(
        self,
        config: ExportConfig,
    ):
        self.config = config

    @property
    @abc.abstractmethod
    def suffix(self) -> str:
        """
        文件后缀名
        """

        raise NotImplementedError()

    @cached_property
    def file_name(self) -> str:
        """
        获取文件名: 审计检索日志-{YYYYMMDD-HH:MM:SS}-{唯一ID}.suffix
        """

        date_str = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"审计检索日志-{date_str}-{unique_id()}{self.suffix}"

    @abc.abstractmethod
    def write(self, data: List[dict]):
        """
        将数据写入文件
        """

        raise NotImplementedError()

    @abc.abstractmethod
    def save(self) -> File:
        """
        保存文件
        """

        raise NotImplementedError()

    @abc.abstractmethod
    def close(self):
        """
        关闭文件
        """

        raise NotImplementedError()


class XLSXExporter(FileExporter):
    category_format = {'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1}
    display_format = {'bold': True, 'align': 'center', 'valign': 'vcenter', 'bg_color': '#D3D3D3', 'border': 1}
    full_key_format = {'bold': False, 'align': 'center', 'valign': 'vcenter', 'bg_color': '#D3D3D3', 'border': 1}
    data_format = {'border': 0}
    suffix = ".xlsx"

    def __init__(self, config: ExportConfig, max_row=65536):
        super().__init__(config)
        self.tmp_file = tempfile.NamedTemporaryFile(delete=True, suffix=self.suffix)
        logger_celery.info(f"{self.__class__.__name__} init tmp file, file_name: {self.tmp_file.name}")
        self.workbook = xlsxwriter.Workbook(self.tmp_file.name, {'constant_memory': True})
        self.title_fmt = self.workbook.add_format(self.display_format)
        self.key_fmt = self.workbook.add_format(self.full_key_format)
        self.data_fmt = self.workbook.add_format(self.data_format)
        self.category_header_fmts = {
            category: self.workbook.add_format(
                {
                    **self.category_format,
                    'bg_color': category.color,
                }
            )
            for category in FieldCategoryEnum.get_orders()
        }

        self.max_row = max_row
        self._init_worksheet()

    def _init_worksheet(self):
        """
        初始化工作表
        """

        self.row = 0
        self.worksheet = self.workbook.add_worksheet()
        self._write_header()

    def _write_header(self):
        """
        写入表头
        """

        self._write_category_header()
        self._write_title_header()

    def _write_row(self, row: list, *args, **kwargs):
        """
        写入数据
        """

        self.worksheet.write_row(self.row, 0, row, *args, **kwargs)
        self.row += 1

    def _write_category_header(self):
        """
        写入分类头
        """

        current_col = 0
        for category in FieldCategoryEnum.get_orders():
            fields = self.config.category_fields.get(category, [])
            if not fields:
                continue

            label = self._resolve_category_label(category, fields, flatten_extension=self.config.flatten_extension)
            span = len(fields)
            fmt = self.category_header_fmts.get(category)

            if span > 1:
                self.worksheet.merge_range(self.row, current_col, self.row, current_col + span - 1, str(label), fmt)
            else:
                self.worksheet.write(self.row, current_col, str(label), fmt)
            current_col += span
        self.row += 1

    @staticmethod
    def _resolve_category_label(category, fields, *, flatten_extension: bool = False):
        """解析分类合并表头文案：仅 AI 导出平铺（flatten_extension，检索页不传）且
        CUSTOM 分组全属 extend_data 容器系列时渲染为"扩展字段"。

        extend_data 容器原列在 STANDARD 分组；平铺后子键列（full_key 形如
        extend_data/{sub_key}）不在三个白名单 map 内，落 CUSTOM 兜底。兜底分组
        是通用语义（其他真正自定义字段也归这里），不替换 label 会让真正自定义
        字段与 extend_data 容器共用"自定义字段"表头，违背产品语义"拓展字段"
        专指 extend_data 下钻（09-10 限定）。混合分组（既有 extend_data 子键列
        又有其他兜底字段）保守保持"自定义字段"——不强行拆分避免视觉混乱；
        flatten_extension 关闭/缺省（检索页导出、AI 非平铺）一律保持原 label，
        不影响既有日志检索的字段导出文案。
        """

        if not flatten_extension or category != FieldCategoryEnum.CUSTOM:
            return category.label
        prefix = f"{EXTEND_DATA_RAW_NAME}{LOG_FIELD_KEY_JOIN_CHAR}"
        for field in fields:
            full_key = getattr(field, "full_key", "") or ""
            if not full_key.startswith(prefix):
                return category.label
        return EXTENSION_GROUP_LABEL

    def _write_title_header(self):
        """
        写入标题头
        """

        # 第一行标题（显示名称）
        titles = [f.display_name or f.full_key for f in self.config.export_fields]
        self._write_row(titles, self.title_fmt)

        # 第二行标题（字段路径）
        keys = [f.full_key or f.display_name for f in self.config.export_fields]
        self._write_row(keys, self.key_fmt)

        # 设置列宽
        self.worksheet.set_column(0, len(titles) - 1, 20)

    def write(self, formatted_logs: List[dict]):
        for log in formatted_logs:
            row_data = [log.get(field.full_key, self.config.empty_value) for field in self.config.export_fields]
            self._write_row(row_data, self.data_fmt)
            # 如果超出最大行数，则新建一个工作表
            if self.row >= self.max_row:
                self._init_worksheet()
        # 手动垃圾回收
        gc.collect()

    def save(self) -> File:
        self.workbook.close()
        return File(self.tmp_file)

    def close(self):
        self.tmp_file.close()
