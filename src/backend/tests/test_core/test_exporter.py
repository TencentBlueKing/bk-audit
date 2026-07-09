# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at https://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import io
import sys
import unittest
from unittest import mock

import openpyxl

from core.exporter import export as exporter_module
from core.exporter.export import BaseXlsxFileExporter
from services.web.risk.handlers.risk_export import MultiSheetRiskExporterXlsx
from tests.base import TestCase


class _MinimalExporter(BaseXlsxFileExporter):
    """最小化具体子类, 仅用于直接测试 BaseXlsxFileExporter 自身行为"""

    suffix = "xlsx"

    def write(self):
        pass


class TestBaseXlsxFileExporter(TestCase):
    """L1 (代码契约, 任何平台跑): 验证 BaseXlsxFileExporter 行为符合预期, 防止回退到 NamedTemporaryFile"""

    def _make_exporter(self):
        return _MinimalExporter()

    def test_init_uses_in_memory_bytes_io(self):
        """验证 __init__ 使用 io.BytesIO, 不是 NamedTemporaryFile (跨平台修复核心)"""
        exporter = self._make_exporter()
        self.assertIsInstance(exporter.tmp_file, io.BytesIO)

    def test_save_returns_django_file_with_valid_xlsx(self):
        """验证 save() 返回的 File 内容是有效 xlsx (zip 格式, 头 2 字节 PK)"""
        exporter = self._make_exporter()
        sheet = exporter.workbook.add_worksheet("test")
        sheet.write_row(0, 0, ["col1", "col2"])
        sheet.write_row(1, 0, ["a", "b"])

        file = exporter.save()
        content = file.read()

        self.assertTrue(
            content.startswith(b"PK"),
            f"xlsx file should start with PK (zip header), got {content[:10]!r}",
        )

    def test_save_resets_file_pointer_to_start(self):
        """验证 save() 后能 seek(0) 读到全部字节, 防止指针错位"""
        exporter = self._make_exporter()
        sheet = exporter.workbook.add_worksheet("test")
        sheet.write_row(0, 0, ["col1"])
        sheet.write_row(1, 0, ["data"])

        file = exporter.save()
        first_read = file.read()
        self.assertTrue(first_read.startswith(b"PK"))

        # 关键: save() 内部应执行 seek(0), 二次 read 仍能从头读
        file.seek(0)
        second_read = file.read()
        self.assertEqual(first_read, second_read)

    def test_close_is_idempotent(self):
        """验证 close() 二次调用不抛 ValueError, 防止 Windows 句柄已关闭后再 close"""
        exporter = self._make_exporter()
        exporter.close()
        # 二次 close 必须幂等, 不能抛 "I/O operation on closed file"
        exporter.close()

    def test_uses_constant_memory_option(self):
        """验证 xlsxwriter 创建时使用 constant_memory: True (大文件内存优化)"""
        with mock.patch.object(exporter_module.xlsxwriter, "Workbook") as mock_wb:
            mock_wb.return_value = mock.MagicMock()
            self._make_exporter()

            self.assertEqual(mock_wb.call_args.args[1], {"constant_memory": True})

    def test_concrete_subclass_save_writes_valid_xlsx(self):
        """端到端验证: 用真实子类 MultiSheetRiskExporterXlsx 实例化 + save, 用 openpyxl 读出有效 xlsx"""
        exporter = MultiSheetRiskExporterXlsx()
        file = exporter.save()

        workbook = openpyxl.load_workbook(io.BytesIO(file.read()))
        # 至少 workbook 可被 openpyxl 解析, 证明 xlsx 字节流格式正确
        self.assertIsNotNone(workbook)


class TestBaseXlsxFileExporterWindowsOnly(unittest.TestCase):
    """L2a (仅 Windows 真实环境跑): 验证 Windows 上不再报 NamedTemporaryFile 句柄冲突"""

    @unittest.skipUnless(sys.platform == "win32", "仅在 Windows 验证 NamedTemporaryFile 句柄冲突修复")
    def test_concurrent_multi_sheet_export_no_handle_conflict(self):
        """真实 Windows: 连续 5 次实例化 MultiSheetRiskExporterXlsx 并 save + read, 不报 PermissionError

        修复前: Windows 上 NamedTemporaryFile 句柄未释放, 第 2 次 save 报
                "PermissionError: [WinError 32] 另一个程序正在使用此文件"
        修复后: 用 io.BytesIO 无句柄, 连续 5 次都能 save + read
        """
        for i in range(5):
            exporter = MultiSheetRiskExporterXlsx()
            file = exporter.save()
            content = file.read()
            self.assertTrue(
                content.startswith(b"PK"),
                f"第 {i+1} 次导出 xlsx 文件头不是 PK, 可能是空文件/损坏 (Windows 句柄冲突可能未修复)",
            )

    @unittest.skipUnless(sys.platform == "win32", "仅在 Windows 验证 close 幂等性")
    def test_close_does_not_raise_after_windows_handle_released(self):
        """真实 Windows: 验证 close() 幂等 (句柄已被 OS 回收场景)"""
        exporter = MultiSheetRiskExporterXlsx()
        file = exporter.save()
        file.close()  # 先关闭 Django File wrapper
        # 关键: BytesIO 关闭后再次 close 不会因 Windows 句柄已释放抛错
        exporter.close()
        exporter.close()  # 二次 close 必须幂等
