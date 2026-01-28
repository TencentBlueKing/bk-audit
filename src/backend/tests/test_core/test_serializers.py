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

from datetime import datetime
from datetime import timezone as dt_timezone
from unittest.mock import patch

from django.db.models import TextChoices
from django.utils import timezone
from django.utils.translation import gettext_lazy
from rest_framework import serializers

from core.serializers import ChoiceDisplayField, FriendlyDateTimeField


class MockRiskLabel(TextChoices):
    NORMAL = "normal", gettext_lazy("正常")
    MISREPORT = "misreport", gettext_lazy("误报")


class TestChoiceDisplayField:
    """测试 ChoiceDisplayField 枚举翻译字段"""

    def test_to_representation_returns_label(self):
        """测试正常值返回对应的 label"""
        field = ChoiceDisplayField(choices=MockRiskLabel)
        assert field.to_representation("normal") == "正常"
        assert field.to_representation("misreport") == "误报"

    def test_to_representation_with_none(self):
        """测试 None 值返回 None"""
        field = ChoiceDisplayField(choices=MockRiskLabel)
        assert field.to_representation(None) is None

    def test_to_representation_with_unknown_value(self):
        """测试未知值返回原始值"""
        field = ChoiceDisplayField(choices=MockRiskLabel)
        assert field.to_representation("unknown") == "unknown"

    def test_in_serializer_context(self):
        """测试在 Serializer 中使用"""

        class TestSerializer(serializers.Serializer):
            status = ChoiceDisplayField(choices=MockRiskLabel)

        serializer = TestSerializer({"status": "normal"})
        assert serializer.data["status"] == "正常"


class TestFriendlyDateTimeField:
    """测试 FriendlyDateTimeField 友好时间字段"""

    @patch("django.utils.timezone.get_default_timezone")
    def test_to_representation_utc_to_local(self, mock_get_default_timezone):
        """测试 UTC 时间转换为本地时区"""
        # 模拟本地时区 UTC+8
        local_tz = timezone.get_fixed_timezone(480)
        mock_get_default_timezone.return_value = local_tz

        field = FriendlyDateTimeField()
        # UTC 时间 13:00 应该转换为本地 21:00
        utc_time = datetime(2025, 1, 19, 13, 0, 0, tzinfo=dt_timezone.utc)
        result = field.to_representation(utc_time)
        assert result == "2025-01-19 21:00:00"

    def test_to_representation_with_none(self):
        """测试 None 值返回 None"""
        field = FriendlyDateTimeField()
        assert field.to_representation(None) is None

    @patch("django.utils.timezone.get_default_timezone")
    def test_custom_format(self, mock_get_default_timezone):
        """测试自定义格式"""
        local_tz = timezone.get_fixed_timezone(480)
        mock_get_default_timezone.return_value = local_tz

        field = FriendlyDateTimeField(format="%Y年%m月%d日 %H:%M")
        utc_time = datetime(2025, 1, 19, 13, 0, 0, tzinfo=dt_timezone.utc)
        result = field.to_representation(utc_time)
        assert result == "2025年01月19日 21:00"

    @patch("django.utils.timezone.get_default_timezone")
    def test_in_serializer_context(self, mock_get_default_timezone):
        """测试在 Serializer 中使用"""
        local_tz = timezone.get_fixed_timezone(480)
        mock_get_default_timezone.return_value = local_tz

        class TestSerializer(serializers.Serializer):
            event_time = FriendlyDateTimeField()

        utc_time = datetime(2025, 1, 19, 13, 30, 45, tzinfo=dt_timezone.utc)
        serializer = TestSerializer({"event_time": utc_time})
        assert serializer.data["event_time"] == "2025-01-19 21:30:45"
