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
import sys
import unittest
from pathlib import Path
from unittest import mock

import yaml
from bk_resource import api
from bk_resource.exceptions import APIRequestError
from django.conf import settings
from django.test import override_settings

from api.bk_plugins_ai_agent.default import ChatCompletion as BaseChatCompletion
from api.bk_plugins_ai_audit_analyse.default import (
    ChatCompletion as AnalyseChatCompletion,
)
from api.bk_plugins_ai_audit_report.default import ChatCompletion
from api.constants import AIAgentCode
from api.utils import get_agent_base_url
from tests.base import TestCase

from .constants import CHAT_COMPLETION_PARAMS, CHAT_COMPLETION_RESPONSE

BACKEND_DIR = Path(__file__).resolve().parents[2]


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
        with override_settings(AI_AGENT_APP_CODE="", AI_AUDIT_REPORT_APP_CODE=""):
            self.assertEqual(self.resource.app_code, settings.APP_CODE)

    def test_app_code_custom(self):
        """测试统一 AI_AGENT_APP_CODE 优先于旧审计报告 APP_CODE"""
        with override_settings(AI_AGENT_APP_CODE="agent_app", AI_AUDIT_REPORT_APP_CODE="report_app"):
            self.assertEqual(self.resource.app_code, "agent_app")

    def test_app_code_fallback_to_report(self):
        """测试 APP_CODE 回退到 AI_AUDIT_REPORT_APP_CODE"""
        with override_settings(AI_AGENT_APP_CODE="", AI_AUDIT_REPORT_APP_CODE="report_app"):
            self.assertEqual(self.resource.app_code, "report_app")

    def test_secret_key_default(self):
        """测试默认 SECRET_KEY（未配置自定义值时使用系统默认值）"""
        with override_settings(AI_AGENT_SECRET_KEY="", AI_AUDIT_REPORT_SECRET_KEY=""):
            self.assertEqual(self.resource.secret_key, settings.SECRET_KEY)

    def test_secret_key_custom(self):
        """测试统一 AI_AGENT_SECRET_KEY 优先于旧审计报告 SECRET_KEY"""
        with override_settings(AI_AGENT_SECRET_KEY="agent_secret", AI_AUDIT_REPORT_SECRET_KEY="report_secret"):
            self.assertEqual(self.resource.secret_key, "agent_secret")

    def test_secret_key_fallback_to_report(self):
        """测试 SECRET_KEY 回退到 AI_AUDIT_REPORT_SECRET_KEY"""
        with override_settings(AI_AGENT_SECRET_KEY="", AI_AUDIT_REPORT_SECRET_KEY="report_secret"):
            self.assertEqual(self.resource.secret_key, "report_secret")

    @mock.patch("api.bk_plugins_ai_agent.default.is_backend", return_value=True)
    @mock.patch.object(ChatCompletion, "add_platform_auth_params", side_effect=lambda params, **kwargs: params)
    def test_add_esb_info_backend_with_custom_auth(self, mock_platform_auth, mock_is_backend):
        """测试后台模式下使用自定义认证信息"""
        custom_app_code = "custom_ai_audit_app"
        custom_secret_key = "custom_ai_audit_secret"

        with override_settings(
            AI_AGENT_APP_CODE="",
            AI_AGENT_SECRET_KEY="",
            AI_AUDIT_REPORT_APP_CODE=custom_app_code,
            AI_AUDIT_REPORT_SECRET_KEY=custom_secret_key,
        ):
            params = {"test_param": "value"}
            result = self.resource.add_esb_info_before_request(params)

            # 验证使用了自定义的认证信息
            self.assertEqual(result.get("bk_app_code"), custom_app_code)
            self.assertEqual(result.get("bk_app_secret"), custom_secret_key)

    @mock.patch("api.bk_plugins_ai_agent.default.is_backend", return_value=True)
    @mock.patch.object(ChatCompletion, "add_platform_auth_params", side_effect=lambda params, **kwargs: params)
    def test_add_esb_info_backend_with_default_auth(self, mock_platform_auth, mock_is_backend):
        """测试后台模式下使用默认认证信息"""
        with override_settings(
            AI_AGENT_APP_CODE="",
            AI_AGENT_SECRET_KEY="",
            AI_AUDIT_REPORT_APP_CODE="",
            AI_AUDIT_REPORT_SECRET_KEY="",
        ):
            params = {"test_param": "value"}
            result = self.resource.add_esb_info_before_request(params)

            # 验证使用了系统默认的认证信息
            self.assertEqual(result.get("bk_app_code"), settings.APP_CODE)
            self.assertEqual(result.get("bk_app_secret"), settings.SECRET_KEY)

    @mock.patch("api.bk_plugins_ai_agent.default.is_backend", return_value=True)
    @mock.patch.object(ChatCompletion, "add_platform_auth_params", side_effect=lambda params, **kwargs: params)
    def test_add_esb_info_backend_removes_internal_params(self, mock_platform_auth, mock_is_backend):
        """测试后台模式下移除内部参数"""
        params = {"_is_backend": True, "_request": mock.Mock(), "test_param": "value"}
        result = self.resource.add_esb_info_before_request(params)

        # 验证内部参数已被移除
        self.assertNotIn("_is_backend", result)
        self.assertNotIn("_request", result)

    @mock.patch("api.bk_plugins_ai_agent.default.is_backend", return_value=False)
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
            AI_AGENT_APP_CODE="",
            AI_AGENT_SECRET_KEY="",
            AI_AUDIT_REPORT_APP_CODE=custom_app_code,
            AI_AUDIT_REPORT_SECRET_KEY=custom_secret_key,
        ):
            params = {"test_param": "value"}
            result = self.resource.add_esb_info_before_request(params)

            # 验证使用了自定义的认证信息
            self.assertEqual(result.get("bk_app_code"), custom_app_code)
            self.assertEqual(result.get("bk_app_secret"), custom_secret_key)

    @mock.patch("api.bk_plugins_ai_agent.default.is_backend", return_value=False)
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


class TestAIAuditAnalyseAuth(TestCase):
    """测试AI分析智能体复用通用 Agent 能力并使用共享认证信息"""

    def setUp(self):
        self.resource = AnalyseChatCompletion()

    def test_reuses_base_chat_completion(self):
        self.assertIsInstance(self.resource, BaseChatCompletion)

    def test_app_code_uses_shared_agent_config(self):
        with override_settings(
            AI_AGENT_APP_CODE="agent_app",
            AI_AUDIT_REPORT_APP_CODE="report_app",
        ):
            self.assertEqual(self.resource.app_code, "agent_app")

    def test_secret_key_uses_shared_agent_config(self):
        with override_settings(
            AI_AGENT_SECRET_KEY="agent_secret",
            AI_AUDIT_REPORT_SECRET_KEY="report_secret",
        ):
            self.assertEqual(self.resource.secret_key, "agent_secret")


class TestAIAuditReportStream(TestCase):
    """测试AI审计报告智能体流式返回"""

    def setUp(self):
        self.resource = ChatCompletion()

    @mock.patch.object(ChatCompletion, "build_url", return_value="http://example.com")
    @mock.patch.object(ChatCompletion, "build_header", return_value={})
    def test_stream_returns_text_content_when_text_and_done_present(self, mock_build_header, mock_build_url):
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

        self.assertEqual(result, "hello ")

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
    def test_stream_prefers_text_content_when_done_present(self, mock_build_header, mock_build_url):
        mock_response = mock.MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"Content-Type": "text/event-stream"}
        mock_response.iter_lines.return_value = [
            "data: " + json.dumps({"event": "text", "content": "# 报告\n## 一、行为链分析\n", "cover": False}),
            "data: " + json.dumps({"event": "text", "content": "## 二、风险关联分析\n", "cover": False}),
            "data: " + json.dumps({"event": "done", "content": "done 完整内容", "cover": False}),
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

        self.assertEqual(result, "# 报告\n## 一、行为链分析\n## 二、风险关联分析\n")

    @mock.patch.object(ChatCompletion, "build_url", return_value="http://example.com")
    @mock.patch.object(ChatCompletion, "build_header", return_value={})
    def test_stream_removes_thinking_placeholder_from_text_content(self, mock_build_header, mock_build_url):
        mock_response = mock.MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"Content-Type": "text/event-stream"}
        mock_response.iter_lines.return_value = [
            "data: " + json.dumps({"event": "text", "content": "正在思考...\n\n ## Analysis Plan\n", "cover": False}),
            "data: " + json.dumps({"event": "text", "content": "# 风险态势总结报告\n## 一、态势概览\n", "cover": False}),
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

        self.assertEqual(result, "\n\n ## Analysis Plan\n# 风险态势总结报告\n## 一、态势概览\n")

    @mock.patch.object(ChatCompletion, "build_url", return_value="http://example.com")
    @mock.patch.object(ChatCompletion, "build_header", return_value={})
    def test_stream_prefers_text_content_over_done_cover(self, mock_build_header, mock_build_url):
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

        self.assertEqual(result, "prefix ")

    @mock.patch.object(ChatCompletion, "build_url", return_value="http://example.com")
    @mock.patch.object(ChatCompletion, "build_header", return_value={})
    def test_stream_fallbacks_to_done_when_cleaned_text_content_empty(self, mock_build_header, mock_build_url):
        mock_response = mock.MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"Content-Type": "text/event-stream"}
        mock_response.iter_lines.return_value = [
            f"data: {json.dumps({'event': 'text', 'content': '正在思考...', 'cover': False})}",
            "data: " + json.dumps({"event": "text", "content": "\n\n  ", "cover": False}),
            f"data: {json.dumps({'event': 'done', 'content': '完整最终报告', 'cover': False})}",
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

        self.assertEqual(result, "完整最终报告")

    @mock.patch("api.bk_plugins_ai_agent.default.logger.info")
    @mock.patch.object(ChatCompletion, "build_url", return_value="http://example.com")
    @mock.patch.object(ChatCompletion, "build_header", return_value={})
    def test_stream_logs_text_done_and_final_previews_without_short_truncation(
        self, mock_build_header, mock_build_url, mock_logger_info
    ):
        long_text = "正在思考...\n\n" + ("x" * 260)
        long_done = "done-" + ("y" * 260)
        mock_response = mock.MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"Content-Type": "text/event-stream"}
        mock_response.iter_lines.return_value = [
            f"data: {json.dumps({'event': 'text', 'content': long_text, 'cover': False})}",
            f"data: {json.dumps({'event': 'done', 'content': long_done, 'cover': False})}",
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

        preview_calls = [
            call
            for call in mock_logger_info.call_args_list
            if call.args and call.args[0] == "AI stream content preview: part=%s, size=%s, preview=%s"
        ]
        previews = {call.args[1]: call.args[3] for call in preview_calls}
        self.assertEqual(set(previews), {"text", "done", "final"})
        self.assertIn("x" * 260, previews["text"])
        self.assertIn("y" * 260, previews["done"])
        self.assertIn("x" * 260, previews["final"])
        self.assertNotIn("正在思考...", result)
        self.assertNotIn("正在思考...", previews["final"])

    @mock.patch.object(ChatCompletion, "build_url", return_value="http://example.com")
    @mock.patch.object(ChatCompletion, "build_header", return_value={})
    def test_stream_fallbacks_to_done_content_when_text_missing(self, mock_build_header, mock_build_url):
        mock_response = mock.MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"Content-Type": "text/event-stream"}
        mock_response.iter_lines.return_value = [
            f"data: {json.dumps({'event': 'think', 'content': 'thinking', 'cover': False})}",
            f"data: {json.dumps({'event': 'done', 'content': 'final answer', 'cover': False})}",
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

        self.assertEqual(result, "final answer")

    @mock.patch.object(ChatCompletion, "build_url", return_value="http://example.com")
    @mock.patch.object(ChatCompletion, "build_header", return_value={})
    def test_stream_raises_when_only_think_events_without_terminal_event(self, mock_build_header, mock_build_url):
        mock_response = mock.MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_response.raise_for_status.return_value = None
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "text/event-stream"}
        mock_response.iter_lines.return_value = [
            f"data: {json.dumps({'event': 'think', 'content': 'thinking', 'cover': False})}",
            f"data: {json.dumps({'event': 'think', 'content': 'still thinking', 'cover': False})}",
        ]
        self.resource.session.request = mock.Mock(return_value=mock_response)

        with self.assertRaises(APIRequestError):
            self.resource.perform_request(
                {
                    "user": "admin",
                    "input": "test",
                    "chat_history": [],
                    "execute_kwargs": {"stream": True},
                }
            )

    @mock.patch.object(ChatCompletion, "build_url", return_value="http://example.com")
    @mock.patch.object(ChatCompletion, "build_header", return_value={})
    def test_stream_raises_when_text_events_without_terminal_event(self, mock_build_header, mock_build_url):
        mock_response = mock.MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_response.raise_for_status.return_value = None
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "text/event-stream"}
        mock_response.iter_lines.return_value = [
            f"data: {json.dumps({'event': 'text', 'content': 'part1', 'cover': False})}",
            f"data: {json.dumps({'event': 'text', 'content': 'part2', 'cover': False})}",
        ]
        self.resource.session.request = mock.Mock(return_value=mock_response)

        with self.assertRaises(APIRequestError):
            self.resource.perform_request(
                {
                    "user": "admin",
                    "input": "test",
                    "chat_history": [],
                    "execute_kwargs": {"stream": True},
                }
            )

    @mock.patch.object(ChatCompletion, "build_url", return_value="http://example.com")
    @mock.patch.object(ChatCompletion, "build_header", return_value={})
    def test_stream_raises_when_terminal_seen_but_content_empty(self, mock_build_header, mock_build_url):
        mock_response = mock.MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_response.raise_for_status.return_value = None
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "text/event-stream"}
        mock_response.iter_lines.return_value = [
            f"data: {json.dumps({'event': 'think', 'content': 'thinking', 'cover': False})}",
            f"data: {json.dumps({'event': 'done', 'content': '   ', 'cover': False})}",
            "data: [DONE]",
        ]
        self.resource.session.request = mock.Mock(return_value=mock_response)

        with self.assertRaises(APIRequestError):
            self.resource.perform_request(
                {
                    "user": "admin",
                    "input": "test",
                    "chat_history": [],
                    "execute_kwargs": {"stream": True},
                }
            )

    @mock.patch.object(ChatCompletion, "build_url", return_value="http://example.com")
    @mock.patch.object(ChatCompletion, "build_header", return_value={})
    def test_stream_appends_ag_ui_text_message_content(self, mock_build_header, mock_build_url):
        mock_response = mock.MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"Content-Type": "text/event-stream"}
        mock_response.iter_lines.return_value = [
            f"data: {json.dumps({'type': 'TEXT_MESSAGE_START', 'messageId': 'msg', 'role': 'assistant'})}",
            "data: "
            + json.dumps({"type": "THINKING_TEXT_MESSAGE_CONTENT", "messageId": "thinking", "delta": "ignore"}),
            f"data: {json.dumps({'type': 'TEXT_MESSAGE_CONTENT', 'messageId': 'msg', 'delta': 'hello '})}",
            f"data: {json.dumps({'type': 'TEXT_MESSAGE_CONTENT', 'messageId': 'msg', 'delta': 'world'})}",
            f"data: {json.dumps({'type': 'TEXT_MESSAGE_END', 'messageId': 'msg'})}",
            f"data: {json.dumps({'type': 'RUN_FINISHED', 'threadId': 'thread', 'runId': 'run'})}",
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

        self.assertEqual(result, "hello world")

    @mock.patch.object(ChatCompletion, "build_url", return_value="http://example.com")
    @mock.patch.object(ChatCompletion, "build_header", return_value={})
    def test_stream_decodes_ag_ui_text_message_content_as_utf8(self, mock_build_header, mock_build_url):
        text = "根据已获取的数据"
        event = "data: " + json.dumps(
            {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg", "delta": text},
            ensure_ascii=False,
        )

        mock_response = mock.MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"Content-Type": "text/event-stream"}

        def iter_lines(decode_unicode=False):
            if decode_unicode:
                return [
                    event.encode("utf-8").decode("latin1"),
                    ("data: " + json.dumps({"type": "RUN_FINISHED", "threadId": "thread", "runId": "run"}))
                    .encode("utf-8")
                    .decode("latin1"),
                ]
            return [
                event.encode("utf-8"),
                ("data: " + json.dumps({"type": "RUN_FINISHED", "threadId": "thread", "runId": "run"})).encode("utf-8"),
            ]

        mock_response.iter_lines.side_effect = iter_lines
        self.resource.session.request = mock.Mock(return_value=mock_response)

        result = self.resource.perform_request(
            {
                "user": "admin",
                "input": "test",
                "chat_history": [],
                "execute_kwargs": {"stream": True},
            }
        )

        self.assertEqual(result, text)

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

    @mock.patch.object(ChatCompletion, "build_url", return_value="http://example.com")
    @mock.patch.object(ChatCompletion, "build_header", return_value={})
    def test_non_stream_parses_choices_delta(self, mock_build_header, mock_build_url):
        """非流式响应：choices[0].delta.content 格式（AI 开发平台实际返回格式）"""
        mock_response = mock.MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {
            "result": True,
            "data": {
                "choices": [{"delta": {"role": "assistant", "content": '{"risk_level": "HIGH"}'}}],
                "model": "qwen3-nothinking",
            },
            "code": "success",
            "message": "ok",
        }
        self.resource.session.request = mock.Mock(return_value=mock_response)

        result = self.resource.perform_request(
            {
                "user": "admin",
                "input": "test",
                "chat_history": [],
                "execute_kwargs": {"stream": False},
            }
        )

        self.assertEqual(result, '{"risk_level": "HIGH"}')

    @mock.patch.object(ChatCompletion, "build_url", return_value="http://example.com")
    @mock.patch.object(ChatCompletion, "build_header", return_value={})
    def test_non_stream_parses_choices_message(self, mock_build_header, mock_build_url):
        """非流式响应：choices[0].message.content 格式（OpenAI 标准格式）"""
        mock_response = mock.MagicMock()
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {
            "result": True,
            "data": {
                "choices": [{"message": {"role": "assistant", "content": "hello world"}}],
            },
            "code": 0,
        }
        self.resource.session.request = mock.Mock(return_value=mock_response)

        result = self.resource.perform_request(
            {
                "user": "admin",
                "input": "test",
                "chat_history": [],
                "execute_kwargs": {"stream": False},
            }
        )

        self.assertEqual(result, "hello world")


class TestGetAgentBaseUrl(TestCase):
    """测试 get_agent_base_url 三层优先级"""

    def test_priority1_env_api_url(self):
        """优先级 1：BKAPP_AI_{CODE}_API_URL 直接返回"""
        with mock.patch.dict("os.environ", {"BKAPP_AI_AUDIT_REPORT_API_URL": "http://custom-url"}):
            result = get_agent_base_url(AIAgentCode.AUDIT_REPORT)
            self.assertEqual(result, "http://custom-url")

    @mock.patch.dict(
        "os.environ", {"BKAPP_AI_RISK_SEARCH_API_URL": "", "BKAPP_AI_RISK_SEARCH_APIGW_NAME": "my-custom-gw"}
    )
    def test_priority2_env_apigw_name(self):
        """优先级 2：BKAPP_AI_{CODE}_APIGW_NAME 覆盖网关名"""
        result = get_agent_base_url(AIAgentCode.RISK_SEARCH)
        self.assertIn("my-custom-gw", result)

    @mock.patch.dict("os.environ", {"BKAPP_AI_AUDIT_REPORT_API_URL": "", "BKAPP_AI_AUDIT_REPORT_APIGW_NAME": ""})
    def test_priority3_default_apigw_name(self):
        """优先级 3：使用枚举 value 作为默认网关名"""
        result = get_agent_base_url(AIAgentCode.AUDIT_REPORT)
        self.assertIn("bp-ai-audit-report", result)

    def test_priority1_overrides_priority2(self):
        """API_URL 优先于 APIGW_NAME"""
        with mock.patch.dict(
            "os.environ",
            {"BKAPP_AI_RISK_SEARCH_API_URL": "http://direct", "BKAPP_AI_RISK_SEARCH_APIGW_NAME": "other-gw"},
        ):
            result = get_agent_base_url(AIAgentCode.RISK_SEARCH)
            self.assertEqual(result, "http://direct")


class TestAIAuditReportAPIGWConfig(TestCase):
    """测试 AI 审计报告 APIGW/MCP 配置"""

    def test_audit_report_mcp_uses_report_risk_resource(self):
        definition = (BACKEND_DIR / "support-files/apigw/definition.yaml").read_text(encoding="utf-8")

        self.assertIn("list_analyse_report_risk_apigw", definition)
        self.assertNotIn("list_risk_apigw", definition)

    def test_report_risk_apigw_resource_defined(self):
        resources = yaml.safe_load((BACKEND_DIR / "support-files/apigw/resources.yaml").read_text(encoding="utf-8"))
        resource = resources["paths"]["/analyse_report_apigw/{report_id}/risks/"]["post"]

        self.assertEqual(resource["operationId"], "list_analyse_report_risk_apigw")
        self.assertEqual(
            resource["x-bk-apigateway-resource"]["backend"]["path"],
            "/api/v1/analyse_report_apigw/{report_id}/risks/",
        )
        detail_schema = resource["responses"]["200"]["schema"]["properties"]["results"]["items"]["properties"]["detail"]
        detail_properties = detail_schema["properties"]
        self.assertIn("risk_id", detail_properties)
        self.assertIn("event_content", detail_properties)
        self.assertIn("event_data", detail_properties)
        self.assertIn("has_report", detail_properties)
        self.assertNotIn("report", detail_properties)

    def test_yaml_read_with_utf8_encoding_succeeds(self):
        """L1: 验证 read_text(encoding="utf-8") 修复 - 显式传 encoding 后能正确解析 yaml

        修复前: read_text() 走系统默认编码, Windows 上 GBK 解析 UTF-8 YAML 失败
        修复后: 显式传 encoding="utf-8", 任何平台都能正确解析
        """
        yaml_path = BACKEND_DIR / "support-files/apigw/definition.yaml"
        # 模拟修复后代码的调用方式: 显式传 encoding
        content = yaml_path.read_text(encoding="utf-8")
        # 验证读到非空字符串, 包含 list_analyse_report_risk_apigw (说明 UTF-8 解析成功)
        self.assertIsInstance(content, str)
        self.assertGreater(len(content), 0)
        self.assertIn("list_analyse_report_risk_apigw", content)

    @unittest.skipUnless(sys.platform == "win32", "仅在 Windows 真实环境验证 GBK 默认编码修复")
    def test_yaml_default_encoding_raises_on_windows(self):
        """L2a: 反例验证 - Windows 上不传 encoding 走系统默认 GBK, 解析 UTF-8 YAML 会 UnicodeDecodeError

        修复前: read_text() 走系统默认编码 (Windows=GBK), 解析 UTF-8 YAML 失败
        修复后: 显式传 encoding="utf-8", 修复代码不会再现此问题
        本测试: 故意不传 encoding, 验证 Windows 上确实会失败 (作为修复基线)
        """
        yaml_path = BACKEND_DIR / "support-files/apigw/definition.yaml"
        with self.assertRaises(UnicodeDecodeError):
            yaml_path.read_text()  # 不传 encoding, Windows 默认 GBK
