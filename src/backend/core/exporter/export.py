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
import tempfile

import xlsxwriter
from django.core.files import File


class BaseXlsxFileExporter(abc.ABC):
    """文件导出器基类"""

    def __init__(self, *args, **kwargs):
        self.tmp_file = tempfile.NamedTemporaryFile(delete=True, suffix=self.suffix)
        self.workbook = xlsxwriter.Workbook(self.tmp_file.name, {'constant_memory': True})

    @property
    @abc.abstractmethod
    def suffix(self) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    def write(self, *args, **kwargs):
        raise NotImplementedError

    def save(self) -> File:
        self.workbook.close()
        self.tmp_file.seek(0)  # 确保文件指针在开头
        return File(self.tmp_file)

    def close(self):
        self.tmp_file.close()
