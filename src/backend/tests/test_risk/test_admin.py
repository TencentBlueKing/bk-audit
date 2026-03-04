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

from unittest import mock

import pytest

from services.web.risk.admin import RiskAdmin
from services.web.risk.models import Risk


class TestRiskAdminTruncateMethods:
    """测试 RiskAdmin 的截断展示方法"""

    @pytest.fixture
    def risk_admin(self):
        """创建 RiskAdmin 实例用于测试"""
        return RiskAdmin(model=Risk, admin_site=None)

    # _truncate_text_field 测试
    def test_truncate_text_field_empty(self, risk_admin):
        """测试空字符串"""
        assert risk_admin._truncate_text_field("") == ""
        assert risk_admin._truncate_text_field(None) == ""

    def test_truncate_text_field_short(self, risk_admin):
        """测试短文本不截断"""
        text = "短文本"
        assert risk_admin._truncate_text_field(text) == text

    def test_truncate_text_field_long(self, risk_admin):
        """测试长文本截断"""
        text = "a" * 150
        result = risk_admin._truncate_text_field(text)
        assert len(result) == risk_admin.TRUNCATE_MAX_LENGTH + 3  # +3 for "..."
        assert result.endswith("...")

    def test_truncate_text_field_custom_length(self, risk_admin):
        """测试自定义截断长度"""
        text = "a" * 50
        result = risk_admin._truncate_text_field(text, max_length=20)
        assert result == "a" * 20 + "..."

    # _truncate_json_field 测试
    def test_truncate_json_field_empty(self, risk_admin):
        """测试空值"""
        assert risk_admin._truncate_json_field(None) == ""
        assert risk_admin._truncate_json_field([]) == ""
        assert risk_admin._truncate_json_field({}) == ""

    def test_truncate_json_field_list_short(self, risk_admin):
        """测试短列表不截断"""
        value = ["user1", "user2"]
        result = risk_admin._truncate_json_field(value)
        assert result == "user1, user2"

    def test_truncate_json_field_list_long(self, risk_admin):
        """测试长列表截断显示数量"""
        value = ["user1", "user2", "user3", "user4", "user5"]
        result = risk_admin._truncate_json_field(value)
        assert "user1, user2, user3" in result
        assert "(+2)" in result

    def test_truncate_json_field_dict(self, risk_admin):
        """测试字典转字符串"""
        value = {"key": "value"}
        result = risk_admin._truncate_json_field(value)
        assert "key" in result

    def test_truncate_json_field_custom_items(self, risk_admin):
        """测试自定义最大元素数"""
        value = ["a", "b", "c", "d", "e"]
        result = risk_admin._truncate_json_field(value, max_items=2)
        assert "a, b" in result
        assert "(+3)" in result

    # 展示方法测试
    def test_title_short(self, risk_admin):
        """测试 title_short 展示方法"""
        obj = mock.Mock(spec=Risk)
        obj.title = "测试风险标题"
        assert risk_admin.title_short(obj) == "测试风险标题"

    def test_operator_short(self, risk_admin):
        """测试 operator_short 展示方法"""
        obj = mock.Mock(spec=Risk)
        obj.operator = ["admin", "tester"]
        result = risk_admin.operator_short(obj)
        assert "admin" in result
        assert "tester" in result

    def test_current_operator_short(self, risk_admin):
        """测试 current_operator_short 展示方法"""
        obj = mock.Mock(spec=Risk)
        obj.current_operator = ["handler1"]
        assert risk_admin.current_operator_short(obj) == "handler1"

    def test_notice_users_short(self, risk_admin):
        """测试 notice_users_short 展示方法"""
        obj = mock.Mock(spec=Risk)
        obj.notice_users = ["watcher1", "watcher2", "watcher3", "watcher4"]
        result = risk_admin.notice_users_short(obj)
        assert "(+1)" in result


class TestRiskAdminQuerySet:
    """测试 RiskAdmin 的 get_queryset 方法"""

    @pytest.fixture
    def risk_admin(self):
        """创建 RiskAdmin 实例用于测试"""
        return RiskAdmin(model=Risk, admin_site=None)

    def test_get_queryset_defers_large_fields(self, risk_admin):
        """测试 get_queryset 延迟加载大字段"""
        request = mock.Mock()
        qs = risk_admin.get_queryset(request)

        # 检查 deferred_loading 包含期望的字段
        deferred_fields = qs.query.deferred_loading[0]
        assert "event_content" in deferred_fields
        assert "event_evidence" in deferred_fields
        assert "event_data" in deferred_fields

    def test_get_queryset_select_related_strategy(self, risk_admin):
        """测试 get_queryset 使用 select_related 加载 strategy"""
        request = mock.Mock()
        qs = risk_admin.get_queryset(request)

        # 检查 select_related 包含 strategy
        assert "strategy" in qs.query.select_related
