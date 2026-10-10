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
import math
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

# AI 导出列宽自适应参数：列宽下限与既有固定列宽一致；AUTO_FILTER 预留 Excel
# 排序/筛选下拉按钮（约 2~3 字符宽）+ 单元格左右内边距（约 1~2 字符）的渲染余量
# （实测 2026-10-10：仅预留按钮宽度时 extend_data/request_uri 等纯 ASCII 长路径
# 列的表头尾部仍被下拉按钮覆盖）；表头为加粗字体，另按粗体放大系数补偿
AI_EXPORT_MIN_COLUMN_WIDTH = 20
AI_EXPORT_AUTO_FILTER_RESERVED_WIDTH = 6
AI_EXPORT_BOLD_TITLE_SCALE = 1.1


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

        # AI 助手导出（export_config.source 标记）：单行表头「中文显示名(字段路径)」，
        # 不写"标准/系统/自定义字段"分类合并行（验收 2026-10-09：分类行不需要，
        # 表头与 AI 助手"日志检索结果"保持一致）；常规检索页导出保持两行结构不变
        if self.config.is_ai_assistant:
            self._write_title_header()
            return
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

        注：AI 助手导出已改为单行表头（_write_header 按 export_config.source
        跳过分类行，验收 2026-10-09）——本方法的 flatten_extension 分支不再被
        AI 导出触达，保留作历史兼容（非 AI 链路 flatten_extension 恒 False，
        一律返回原 label）；检索页导出的分类行文案不受影响。
        """

        if not flatten_extension or category != FieldCategoryEnum.CUSTOM:
            return category.label
        prefix = f"{EXTEND_DATA_RAW_NAME}{LOG_FIELD_KEY_JOIN_CHAR}"
        for field in fields:
            full_key = getattr(field, "full_key", "") or ""
            if not full_key.startswith(prefix):
                return category.label
        return EXTENSION_GROUP_LABEL

    @classmethod
    def _build_field_title(cls, field) -> str:
        """单行标题拼接：中文显示名(英文字段路径)，如「操作起始时间(start_time)」。

        扩展字段下钻列（full_key 形如 extend_data/{sub_key}，AI 平铺导出与检索页
        指定字段共用该形态）的 display_name 是子键名本身，拼接会得到
        「_request_url(extend_data/_request_url)」的重复语义，故只显示完整路径；
        display_name 缺失或与 full_key 相同时同样只显示 full_key，避免括号重复。
        """

        full_key = field.full_key or field.display_name
        display_name = field.display_name or full_key
        if full_key.startswith(f"{EXTEND_DATA_RAW_NAME}{LOG_FIELD_KEY_JOIN_CHAR}"):
            return full_key
        if display_name and display_name != full_key:
            return f"{display_name}({full_key})"
        return full_key

    @staticmethod
    def _calc_display_width(text) -> int:
        """近似 Excel 列宽单位：全角/CJK 等宽字符记 2，其余记 1。"""

        return sum(2 if ord(char) > 127 else 1 for char in str(text))

    def _write_title_header(self):
        """
        写入标题头（单行：中文显示名(英文字段路径)，见 _build_field_title）
        """

        titles = [self._build_field_title(f) for f in self.config.export_fields]
        self._write_row(titles, self.title_fmt)

        # 设置列宽
        if self.config.is_ai_assistant:
            # AI 助手导出：列宽按表头文本自适应——至少完整展示表头列名，并预留
            # Excel 排序/筛选下拉按钮空间（按钮渲染后表头仍完整显示），下限不窄于
            # 既有固定列宽；常规检索页导出保持固定 20 不变
            for col, title in enumerate(titles):
                # 表头为加粗字体，常规字符宽度估算对粗体偏窄（粗体约宽 10%），
                # 先按粗体放大系数补偿，再预留筛选按钮 + 内边距空间，避免长表头
                # 尾部（如 extend_data/request_uri 纯 ASCII 长路径列）被下拉按钮覆盖
                bolded_width = math.ceil(self._calc_display_width(title) * AI_EXPORT_BOLD_TITLE_SCALE)
                width = max(
                    AI_EXPORT_MIN_COLUMN_WIDTH,
                    bolded_width + AI_EXPORT_AUTO_FILTER_RESERVED_WIDTH,
                )
                self.worksheet.set_column(col, col, width)
        else:
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
