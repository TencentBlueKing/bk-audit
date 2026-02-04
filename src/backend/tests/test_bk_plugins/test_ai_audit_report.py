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

import json
from unittest import mock

from bk_resource import api
from django.conf import settings
from django.test import override_settings

from api.bk_plugins_ai_audit_report.default import ChatCompletion
from tests.base import TestCase

from .constants import CHAT_COMPLETION_PARAMS, CHAT_COMPLETION_RESPONSE


class TestAIAuditReport(TestCase):
    """测试AI审计报告智能体API接口"""

    @mock.patch(
        "api.bk_plugins_ai_audit_report.default.ChatCompletion.perform_request",
        mock.Mock(return_value=CHAT_COMPLETION_RESPONSE["data"]["content"]),
    )
    def test_chat_completion(self):
        """测试智能体对话接口"""
        result = api.bk_plugins_ai_audit_report.chat_completion(**CHAT_COMPLETION_PARAMS)
        self.assertIsInstance(result, str)
        self.assertEqual(result, CHAT_COMPLETION_RESPONSE["data"]["content"])


class TestAIAuditReportAuth(TestCase):
    """测试AI审计报告智能体API认证信息"""

    def setUp(self):
        """初始化测试实例"""
        self.resource = ChatCompletion()

    def test_app_code_default(self):
        """测试默认 APP_CODE（未配置自定义值时使用系统默认值）"""
        with override_settings(AI_AUDIT_REPORT_APP_CODE=""):
            self.assertEqual(self.resource.app_code, settings.APP_CODE)

    def test_app_code_custom(self):
        """测试自定义 APP_CODE"""
        custom_app_code = "custom_ai_audit_app"
        with override_settings(AI_AUDIT_REPORT_APP_CODE=custom_app_code):
            self.assertEqual(self.resource.app_code, custom_app_code)

    def test_secret_key_default(self):
        """测试默认 SECRET_KEY（未配置自定义值时使用系统默认值）"""
        with override_settings(AI_AUDIT_REPORT_SECRET_KEY=""):
            self.assertEqual(self.resource.secret_key, settings.SECRET_KEY)

    def test_secret_key_custom(self):
        """测试自定义 SECRET_KEY"""
        custom_secret_key = "custom_ai_audit_secret"
        with override_settings(AI_AUDIT_REPORT_SECRET_KEY=custom_secret_key):
            self.assertEqual(self.resource.secret_key, custom_secret_key)

    @mock.patch("api.bk_plugins_ai_audit_report.default.is_backend", return_value=True)
    @mock.patch.object(ChatCompletion, "add_platform_auth_params", side_effect=lambda params, **kwargs: params)
    def test_add_esb_info_backend_with_custom_auth(self, mock_platform_auth, mock_is_backend):
        """测试后台模式下使用自定义认证信息"""
        custom_app_code = "custom_ai_audit_app"
        custom_secret_key = "custom_ai_audit_secret"

        with override_settings(
            AI_AUDIT_REPORT_APP_CODE=custom_app_code,
            AI_AUDIT_REPORT_SECRET_KEY=custom_secret_key,
        ):
            params = {"test_param": "value"}
            result = self.resource.add_esb_info_before_request(params)

            # 验证使用了自定义的认证信息
            self.assertEqual(result.get("bk_app_code"), custom_app_code)
            self.assertEqual(result.get("bk_app_secret"), custom_secret_key)

    @mock.patch("api.bk_plugins_ai_audit_report.default.is_backend", return_value=True)
    @mock.patch.object(ChatCompletion, "add_platform_auth_params", side_effect=lambda params, **kwargs: params)
    def test_add_esb_info_backend_with_default_auth(self, mock_platform_auth, mock_is_backend):
        """测试后台模式下使用默认认证信息"""
        with override_settings(
            AI_AUDIT_REPORT_APP_CODE="",
            AI_AUDIT_REPORT_SECRET_KEY="",
        ):
            params = {"test_param": "value"}
            result = self.resource.add_esb_info_before_request(params)

            # 验证使用了系统默认的认证信息
            self.assertEqual(result.get("bk_app_code"), settings.APP_CODE)
            self.assertEqual(result.get("bk_app_secret"), settings.SECRET_KEY)

    @mock.patch("api.bk_plugins_ai_audit_report.default.is_backend", return_value=True)
    @mock.patch.object(ChatCompletion, "add_platform_auth_params", side_effect=lambda params, **kwargs: params)
    def test_add_esb_info_backend_removes_internal_params(self, mock_platform_auth, mock_is_backend):
        """测试后台模式下移除内部参数"""
        params = {"_is_backend": True, "_request": mock.Mock(), "test_param": "value"}
        result = self.resource.add_esb_info_before_request(params)

        # 验证内部参数已被移除
        self.assertNotIn("_is_backend", result)
        self.assertNotIn("_request", result)

    @mock.patch("api.bk_plugins_ai_audit_report.default.is_backend", return_value=False)
    @mock.patch("blueapps.utils.request_provider.get_local_request", return_value=None)
    @mock.patch.object(ChatCompletion, "add_platform_auth_params", side_effect=lambda params: params)
    @mock.patch.object(ChatCompletion, "build_auth_args", return_value={})
    def test_add_esb_info_frontend_with_custom_auth(
        self, mock_build_auth, mock_platform_auth, mock_get_request, mock_is_backend
    ):
        """测试前端模式下使用自定义认证信息"""
        custom_app_code = "custom_ai_audit_app"
        custom_secret_key = "custom_ai_audit_secret"

        with override_settings(
            AI_AUDIT_REPORT_APP_CODE=custom_app_code,
            AI_AUDIT_REPORT_SECRET_KEY=custom_secret_key,
        ):
            params = {"test_param": "value"}
            result = self.resource.add_esb_info_before_request(params)

            # 验证使用了自定义的认证信息
            self.assertEqual(result.get("bk_app_code"), custom_app_code)
            self.assertEqual(result.get("bk_app_secret"), custom_secret_key)

    @mock.patch("api.bk_plugins_ai_audit_report.default.is_backend", return_value=False)
    @mock.patch("blueapps.utils.request_provider.get_local_request")
    @mock.patch.object(ChatCompletion, "add_platform_auth_params", side_effect=lambda params: params)
    @mock.patch.object(ChatCompletion, "build_auth_args", return_value={"bk_token": "test_token"})
    def test_add_esb_info_frontend_with_user(
        self, mock_build_auth, mock_platform_auth, mock_get_request, mock_is_backend
    ):
        """测试前端模式下添加用户信息"""
        # 模拟请求对象
        mock_request = mock.Mock()
        mock_user = mock.Mock()
        mock_user.username = "test_user"
        mock_user.bk_username = "test_bk_user"
        mock_request.user = mock_user
        mock_get_request.return_value = mock_request

        params = {"test_param": "value"}
        result = self.resource.add_esb_info_before_request(params)

        # 验证用户信息已添加
        self.assertEqual(result.get("bk_username"), "test_bk_user")


class TestAIAuditReportStream(TestCase):
    """测试AI审计报告智能体流式返回"""

    def setUp(self):
        self.resource = ChatCompletion()

    @mock.patch.object(ChatCompletion, "build_url", return_value="http://example.com")
    @mock.patch.object(ChatCompletion, "build_header", return_value={})
    def test_stream_returns_done_content(self, mock_build_header, mock_build_url):
        mock_response = mock.MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"Content-Type": "text/event-stream"}
        mock_response.iter_lines.return_value = [
            f"data: {json.dumps({'event': 'text', 'content': 'hello ', 'cover': False})}",
            f"data: {json.dumps({'event': 'done', 'content': 'final', 'cover': False})}",
            "data: [DONE]",
        ]
        self.resource.session.request = mock.Mock(return_value=mock_response)

        result = self.resource.perform_request(
            {
                "user": "admin",
                "input": "test",
                "chat_history": [],
                "execute_kwargs": {"stream": True},
            }
        )

        self.assertEqual(result, "hello final")

    @mock.patch.object(ChatCompletion, "build_url", return_value="http://example.com")
    @mock.patch.object(ChatCompletion, "build_header", return_value={})
    def test_stream_fallbacks_to_text_when_done_missing(self, mock_build_header, mock_build_url):
        mock_response = mock.MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"Content-Type": "text/event-stream"}
        mock_response.iter_lines.return_value = [
            f"data: {json.dumps({'event': 'text', 'content': 'part1', 'cover': False})}",
            f"data: {json.dumps({'event': 'text', 'content': 'part2', 'cover': False})}",
            "data: [DONE]",
        ]
        self.resource.session.request = mock.Mock(return_value=mock_response)

        result = self.resource.perform_request(
            {
                "user": "admin",
                "input": "test",
                "chat_history": [],
                "execute_kwargs": {"stream": True},
            }
        )

        self.assertEqual(result, "part1part2")

    @mock.patch.object(ChatCompletion, "build_url", return_value="http://example.com")
    @mock.patch.object(ChatCompletion, "build_header", return_value={})
    def test_stream_done_cover_overrides_text(self, mock_build_header, mock_build_url):
        mock_response = mock.MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"Content-Type": "text/event-stream"}
        mock_response.iter_lines.return_value = [
            f"data: {json.dumps({'event': 'text', 'content': 'prefix ', 'cover': False})}",
            f"data: {json.dumps({'event': 'done', 'content': 'override', 'cover': True})}",
            "data: [DONE]",
        ]
        self.resource.session.request = mock.Mock(return_value=mock_response)

        result = self.resource.perform_request(
            {
                "user": "admin",
                "input": "test",
                "chat_history": [],
                "execute_kwargs": {"stream": True},
            }
        )

        self.assertEqual(result, "override")

    def test_before_request_sets_stream_flag(self):
        kwargs = {"json": {"execute_kwargs": {"stream": True}}}

        result = self.resource.before_request(kwargs)

        self.assertTrue(result.get("stream"))

    @mock.patch.object(ChatCompletion, "build_url", return_value="http://example.com")
    @mock.patch.object(ChatCompletion, "build_header", return_value={})
    def test_non_stream_parses_content(self, mock_build_header, mock_build_url):
        mock_response = mock.MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"result": True, "data": {"content": "plain"}, "code": 0}
        self.resource.session.request = mock.Mock(return_value=mock_response)

        result = self.resource.perform_request(
            {
                "user": "admin",
                "input": "test",
                "chat_history": [],
                "execute_kwargs": {"stream": False},
            }
        )

        self.assertEqual(result, "plain")
