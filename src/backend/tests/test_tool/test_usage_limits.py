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

from django.test import TestCase
from pydantic import ValidationError

from services.web.tool.constants import (
    PROFILE_ACCOUNT_TYPES,
    SmartPageToolConfig,
    UsageLimits,
)
from services.web.tool.resources import GetToolDetail


class UsageLimitsModelTest(TestCase):
    """测试 UsageLimits 模型校验逻辑"""

    def test_valid_account_type_values(self):
        """合法账号类型值应通过校验"""
        limits = UsageLimits(
            scenes={
                "1001": {"account_type": ["ctx", "openid"]},
                "1002": {"account_type": ["form_wechat"]},
            }
        )
        self.assertEqual(len(limits.scenes), 2)
        self.assertEqual(limits.scenes["1001"]["account_type"], ["ctx", "openid"])

    def test_invalid_account_type_value(self):
        """非法账号类型值应抛出异常"""
        with self.assertRaises(ValidationError) as cm:
            UsageLimits(scenes={"1001": {"account_type": ["wechat"]}})  # 非法值，应为 form_wechat
        error_msg = str(cm.exception)
        self.assertIn("无效的账号类型", error_msg)
        self.assertIn("wechat", error_msg)

    def test_empty_account_type_list(self):
        """空列表表示全部禁止，应通过校验"""
        limits = UsageLimits(scenes={"1001": {"account_type": []}})
        self.assertEqual(limits.scenes["1001"]["account_type"], [])

    def test_account_type_must_be_list(self):
        """account_type 必须是列表"""
        with self.assertRaises(ValidationError):
            UsageLimits(scenes={"1001": {"account_type": "ctx"}})  # 字符串而非列表

    def test_no_account_type_limit(self):
        """不配置 account_type 时应通过"""
        limits = UsageLimits(scenes={"1001": {"other_field": ["value"]}})
        self.assertEqual(limits.scenes["1001"]["other_field"], ["value"])

    def test_systems_validation(self):
        """systems 字段也应进行相同的校验"""
        with self.assertRaises(ValidationError):
            UsageLimits(systems={"sys001": {"account_type": ["invalid_type"]}})


class SmartPageToolConfigWithUsageLimitsTest(TestCase):
    """测试 SmartPageToolConfig 支持 usage_limits"""

    def test_create_with_usage_limits(self):
        """创建带 usage_limits 的配置"""
        config = SmartPageToolConfig(
            usage_limits=UsageLimits(scenes={"1001": {"account_type": ["ctx"]}}),
        )
        self.assertEqual(config.usage_limits.scenes["1001"]["account_type"], ["ctx"])

    def test_model_validate_with_usage_limits(self):
        """使用 model_validate 解析带 usage_limits 的配置"""
        config_dict = {
            "usage_limits": {
                "scenes": {
                    "1001": {"account_type": ["openid", "form_wechat"]},
                },
                "systems": {
                    "sys001": {"account_type": ["ctx"]},
                },
            },
        }
        config = SmartPageToolConfig.model_validate(config_dict)
        self.assertEqual(config.usage_limits.scenes["1001"]["account_type"], ["openid", "form_wechat"])
        self.assertEqual(config.usage_limits.systems["sys001"]["account_type"], ["ctx"])

    def test_default_usage_limits(self):
        """默认 usage_limits 应为空"""
        config = SmartPageToolConfig()
        self.assertEqual(config.usage_limits.scenes, {})
        self.assertEqual(config.usage_limits.systems, {})


class GetAllowedAccountTypesTest(TestCase):
    """测试 GetToolDetail._get_allowed_account_types 方法"""

    def _make_tool(self, usage_limits=None):
        """创建模拟工具对象"""
        tool = mock.MagicMock()
        tool.config = {}
        if usage_limits:
            tool.config["usage_limits"] = usage_limits
        return tool

    def test_no_usage_limits(self):
        """无 usage_limits 配置时返回全部账号类型"""
        tool = self._make_tool()
        resource = GetToolDetail()
        result = resource._get_allowed_account_types(tool, scene_id="1001")
        self.assertEqual(result, PROFILE_ACCOUNT_TYPES)

    def test_empty_usage_limits(self):
        """usage_limits 为空字典时返回全部账号类型"""
        tool = self._make_tool(usage_limits={})
        resource = GetToolDetail()
        result = resource._get_allowed_account_types(tool, scene_id="1001")
        self.assertEqual(result, PROFILE_ACCOUNT_TYPES)

    def test_scene_configured(self):
        """场景配置了限制时返回限制内的账号类型"""
        tool = self._make_tool(
            usage_limits={
                "scenes": {
                    "1001": {"account_type": ["ctx", "openid"]},
                }
            }
        )
        resource = GetToolDetail()
        result = resource._get_allowed_account_types(tool, scene_id="1001")
        self.assertEqual(result, ["ctx", "openid"])

    def test_scene_not_configured(self):
        """场景未配置限制时返回全部账号类型"""
        tool = self._make_tool(
            usage_limits={
                "scenes": {
                    "1001": {"account_type": ["ctx"]},
                }
            }
        )
        resource = GetToolDetail()
        result = resource._get_allowed_account_types(tool, scene_id="9999")
        self.assertEqual(result, PROFILE_ACCOUNT_TYPES)

    def test_system_configured(self):
        """系统配置了限制时返回限制内的账号类型"""
        tool = self._make_tool(
            usage_limits={
                "systems": {
                    "sys001": {"account_type": ["form_wechat", "form_qq"]},
                }
            }
        )
        resource = GetToolDetail()
        result = resource._get_allowed_account_types(tool, system_id="sys001")
        self.assertEqual(result, ["form_wechat", "form_qq"])

    def test_scene_and_system_both_configured(self):
        """场景和系统同时配置时，场景优先（互斥，不再取并集）"""
        tool = self._make_tool(
            usage_limits={
                "scenes": {
                    "1001": {"account_type": ["ctx"]},
                },
                "systems": {
                    "sys001": {"account_type": ["openid"]},
                },
            }
        )
        resource = GetToolDetail()
        result = resource._get_allowed_account_types(tool, scene_id="1001", system_id="sys001")
        self.assertEqual(result, ["ctx"])

    def test_scene_empty_account_type_list(self):
        """场景配置空列表时返回空列表（全部禁止）"""
        tool = self._make_tool(
            usage_limits={
                "scenes": {
                    "1001": {"account_type": []},
                }
            }
        )
        resource = GetToolDetail()
        result = resource._get_allowed_account_types(tool, scene_id="1001")
        self.assertEqual(result, [])

    def test_order_preserved(self):
        """返回顺序应与 PROFILE_ACCOUNT_TYPES 一致"""
        tool = self._make_tool(
            usage_limits={
                "scenes": {
                    "1001": {"account_type": ["form_qq", "ctx", "openid"]},
                }
            }
        )
        resource = GetToolDetail()
        result = resource._get_allowed_account_types(tool, scene_id="1001")
        # 应保持 PROFILE_ACCOUNT_TYPES 的顺序：ctx, openid, form_wechat, form_qq
        self.assertEqual(result, ["ctx", "openid", "form_qq"])

    def test_no_scene_id_no_system_id(self):
        """不传 scene_id 和 system_id 时返回全部"""
        tool = self._make_tool(
            usage_limits={
                "scenes": {
                    "1001": {"account_type": ["ctx"]},
                }
            }
        )
        resource = GetToolDetail()
        result = resource._get_allowed_account_types(tool)
        self.assertEqual(result, PROFILE_ACCOUNT_TYPES)
