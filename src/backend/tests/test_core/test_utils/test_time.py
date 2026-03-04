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

from core.utils.time import format_date_string, parse_datetime


class TestFormatDateString:
    """测试 format_date_string 函数"""

    @patch("core.utils.time.timezone.get_default_timezone")
    def test_format_utc_timezone_string_replaced(self, mock_get_default_timezone):
        """测试 UTC 时区字符串（Z结尾）直接替换为本地时区，保持时间值不变"""
        local_tz = timezone.get_fixed_timezone(480)  # UTC+8
        mock_get_default_timezone.return_value = local_tz

        # 注意：带 Z 后缀的 UTC 时间，替换时区但保持时间值
        date_string = "2022-01-01T00:00:00Z"
        result = format_date_string(date_string)

        # 00:00:00 UTC 替换为 00:00:00+08:00（保持时间值）
        assert result == "2022-01-01 00:00:00"

    @patch("core.utils.time.timezone.get_default_timezone")
    def test_format_with_explicit_timezone(self, mock_get_default_timezone):
        """测试带明确时区的字符串（非 Z 结尾）转换为本地时区"""
        local_tz = timezone.get_fixed_timezone(480)  # UTC+8
        mock_get_default_timezone.return_value = local_tz

        # +00:00 与 Z 行为不同，会执行 astimezone 转换
        date_string = "2022-01-01T00:00:00+00:00"
        result = format_date_string(date_string)

        # 00:00:00+00:00 转换为 08:00:00+08:00
        assert result == "2022-01-01 08:00:00"

    @patch("core.utils.time.timezone.get_default_timezone")
    def test_format_custom_output_format(self, mock_get_default_timezone):
        """测试自定义输出格式"""
        local_tz = timezone.get_fixed_timezone(480)  # UTC+8
        mock_get_default_timezone.return_value = local_tz

        # 使用 +00:00 触发时区转换
        date_string = "2022-01-01T00:00:00+00:00"
        result = format_date_string(date_string, output_format="%Y年%m月%d日 %H:%M")

        assert result == "2022年01月01日 08:00"

    def test_format_invalid_string_returns_original(self):
        """测试无效字符串返回原值"""
        invalid_string = "not-a-date"
        result = format_date_string(invalid_string)

        assert result == invalid_string

    @patch("core.utils.time.timezone.get_default_timezone")
    def test_format_iso_string_without_timezone(self, mock_get_default_timezone):
        """测试不带时区的 ISO 格式字符串"""
        local_tz = timezone.get_fixed_timezone(480)  # UTC+8
        mock_get_default_timezone.return_value = local_tz

        date_string = "2022-01-01T16:00:00"
        result = format_date_string(date_string)

        # 无时区字符串被 arrow 解析为 UTC，替换为本地时区后保持相同时间
        assert result == "2022-01-01 16:00:00"


class TestParseDatetime:
    """测试 parse_datetime 函数"""

    def test_parse_integer_timestamp(self):
        """测试解析整数时间戳"""
        timestamp = 1640995200  # 2022-01-01 00:00:00 UTC
        result = parse_datetime(timestamp)

        assert isinstance(result, arrow.Arrow)
        assert result.timestamp() == timestamp

    def test_parse_float_timestamp(self):
        """测试解析浮点数时间戳"""
        timestamp = 1640995200.5  # 2022-01-01 00:00:00.5 UTC
        result = parse_datetime(timestamp)

        assert isinstance(result, arrow.Arrow)
        assert result.timestamp() == timestamp

    def test_parse_string_with_timezone(self):
        """测试解析带时区的字符串"""
        date_string = "2022-01-01T08:00:00+08:00"
        result = parse_datetime(date_string)

        assert isinstance(result, arrow.Arrow)
        assert result.format("YYYY-MM-DD HH:mm:ss") == "2022-01-01 08:00:00"

    @patch("core.utils.time.timezone.get_default_timezone")
    def test_parse_string_utc_timezone_replaced(self, mock_get_default_timezone):
        """测试解析UTC时区字符串时替换为本地时区"""
        # 模拟本地时区
        local_tz = timezone.get_fixed_timezone(480)  # UTC+8
        mock_get_default_timezone.return_value = local_tz

        # 创建一个UTC时间的字符串
        date_string = "2022-01-01T00:00:00Z"
        result = parse_datetime(date_string)

        assert isinstance(result, arrow.Arrow)
        # 验证时区被替换为本地时区
        assert result.tzinfo == local_tz

    def test_parse_string_without_timezone(self):
        """测试解析不带时区的字符串"""
        date_string = "2022-01-01T08:00:00"
        result = parse_datetime(date_string)

        assert isinstance(result, arrow.Arrow)
        assert result.format("YYYY-MM-DD HH:mm:ss") == "2022-01-01 08:00:00"

    def test_parse_iso_format_string(self):
        """测试解析ISO格式字符串"""
        date_string = "2022-01-01T08:00:00.123456"
        result = parse_datetime(date_string)

        assert isinstance(result, arrow.Arrow)
        assert result.year == 2022
        assert result.month == 1
        assert result.day == 1
        assert result.hour == 8
        assert result.minute == 0
        assert result.second == 0

    def test_parse_various_string_formats(self):
        """测试解析各种字符串格式"""
        test_cases = [
            "2022-01-01",
            "2022/01/01",
            "2022-01-01 08:00:00",
        ]

        for date_string in test_cases:
            result = parse_datetime(date_string)
            assert isinstance(result, arrow.Arrow)
            assert result.year == 2022
            assert result.month == 1
            assert result.day == 1

    def test_edge_cases(self):
        """测试边界情况"""
        # 测试零时间戳
        result = parse_datetime(0)
        assert isinstance(result, arrow.Arrow)
        assert result.timestamp() == 0

        # 测试负时间戳
        result = parse_datetime(-1)
        assert isinstance(result, arrow.Arrow)
        assert result.timestamp() == -1
