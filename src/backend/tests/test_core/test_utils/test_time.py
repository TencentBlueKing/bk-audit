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

from unittest.mock import patch

import arrow
from django.utils import timezone

from core.utils.time import parse_datetime
from tests.base import TestCase


class TestParseDatetime(TestCase):
    """测试 parse_datetime 函数"""

    def test_parse_integer_timestamp(self):
        """测试解析整数时间戳"""
        timestamp = 1640995200  # 2022-01-01 00:00:00 UTC
        result = parse_datetime(timestamp)

        self.assertIsInstance(result, arrow.Arrow)
        self.assertEqual(result.timestamp(), timestamp)

    def test_parse_float_timestamp(self):
        """测试解析浮点数时间戳"""
        timestamp = 1640995200.5  # 2022-01-01 00:00:00.5 UTC
        result = parse_datetime(timestamp)

        self.assertIsInstance(result, arrow.Arrow)
        self.assertEqual(result.timestamp(), timestamp)

    def test_parse_string_with_timezone(self):
        """测试解析带时区的字符串"""
        date_string = "2022-01-01T08:00:00+08:00"
        result = parse_datetime(date_string)

        self.assertIsInstance(result, arrow.Arrow)
        self.assertEqual(result.format("YYYY-MM-DD HH:mm:ss"), "2022-01-01 08:00:00")

    @patch('django.utils.timezone.get_default_timezone')
    def test_parse_string_utc_timezone_replaced(self, mock_get_default_timezone):
        """测试解析UTC时区字符串时替换为本地时区"""
        # 模拟本地时区
        local_tz = timezone.get_fixed_timezone(480)  # UTC+8
        mock_get_default_timezone.return_value = local_tz

        # 创建一个UTC时间的字符串
        date_string = "2022-01-01T00:00:00Z"
        result = parse_datetime(date_string)

        self.assertIsInstance(result, arrow.Arrow)
        # 验证时区被替换为本地时区
        self.assertEqual(result.tzinfo, local_tz)

    def test_parse_string_without_timezone(self):
        """测试解析不带时区的字符串"""
        date_string = "2022-01-01T08:00:00"
        result = parse_datetime(date_string)

        self.assertIsInstance(result, arrow.Arrow)
        self.assertEqual(result.format("YYYY-MM-DD HH:mm:ss"), "2022-01-01 08:00:00")

    def test_parse_iso_format_string(self):
        """测试解析ISO格式字符串"""
        date_string = "2022-01-01T08:00:00.123456"
        result = parse_datetime(date_string)

        self.assertIsInstance(result, arrow.Arrow)
        self.assertEqual(result.year, 2022)
        self.assertEqual(result.month, 1)
        self.assertEqual(result.day, 1)
        self.assertEqual(result.hour, 8)
        self.assertEqual(result.minute, 0)
        self.assertEqual(result.second, 0)

    def test_parse_various_string_formats(self):
        """测试解析各种字符串格式"""
        test_cases = [
            "2022-01-01",
            "2022/01/01",
            "2022-01-01 08:00:00",
        ]

        for date_string in test_cases:
            with self.subTest(date_string=date_string):
                result = parse_datetime(date_string)
                self.assertIsInstance(result, arrow.Arrow)
                self.assertEqual(result.year, 2022)
                self.assertEqual(result.month, 1)
                self.assertEqual(result.day, 1)

    def test_edge_cases(self):
        """测试边界情况"""
        # 测试零时间戳
        result = parse_datetime(0)
        self.assertIsInstance(result, arrow.Arrow)
        self.assertEqual(result.timestamp(), 0)

        # 测试负时间戳
        result = parse_datetime(-1)
        self.assertIsInstance(result, arrow.Arrow)
        self.assertEqual(result.timestamp(), -1)
