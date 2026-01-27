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
import base64
import hashlib
import hmac
import json
from datetime import datetime
from unittest import mock

from django.test import TestCase

from apps.meta.constants import SENSITIVE_REPLACE_VALUE
from services.web.tool.constants import (
    ApiAuthMethod,
    BkAppAuthConfig,
    BkAuthItem,
    HmacSignatureAuthConfig,
    HmacSignatureAuthItem,
    NoAuthItem,
)
from services.web.tool.executor.auth import (
    AuthHandlerFactory,
    BkAppAuthHandler,
    HmacSignatureAuthHandler,
    NoAuthHandler,
)


class TestNoAuthHandler(TestCase):
    """测试无认证处理器"""

    def test_apply_auth_does_nothing(self):
        """测试apply_auth不修改请求头"""
        handler = NoAuthHandler()
        headers = {"Content-Type": "application/json"}
        handler.apply_auth(headers)
        self.assertEqual(headers, {"Content-Type": "application/json"})

    def test_mask_headers_returns_copy(self):
        """测试mask_headers返回请求头的副本"""
        handler = NoAuthHandler()
        headers = {"Content-Type": "application/json"}
        masked = handler.mask_headers(headers)
        self.assertEqual(masked, headers)
        # 确保是副本
        masked["X-Test"] = "test"
        self.assertNotIn("X-Test", headers)


class TestBkAppAuthHandler(TestCase):
    """测试蓝鲸应用认证处理器"""

    def setUp(self):
        """设置测试环境"""
        self.config = BkAppAuthConfig(bk_app_code="test_app", bk_app_secret="test_secret_12345")
        self.handler = BkAppAuthHandler(self.config)

    def test_apply_auth_adds_authorization_header(self):
        """测试apply_auth添加X-Bkapi-Authorization头"""
        headers = {"Content-Type": "application/json"}
        self.handler.apply_auth(headers)

        self.assertIn("X-Bkapi-Authorization", headers)
        auth_data = json.loads(headers["X-Bkapi-Authorization"])
        self.assertEqual(auth_data["bk_app_code"], "test_app")
        self.assertEqual(auth_data["bk_app_secret"], "test_secret_12345")

    def test_mask_headers_hides_secret(self):
        """测试mask_headers隐藏敏感信息"""
        headers = {"Content-Type": "application/json"}
        self.handler.apply_auth(headers)
        masked = self.handler.mask_headers(headers)

        auth_data = json.loads(masked["X-Bkapi-Authorization"])
        self.assertEqual(auth_data["bk_app_code"], "test_app")
        self.assertEqual(auth_data["bk_app_secret"], SENSITIVE_REPLACE_VALUE)


class TestHmacSignatureAuthHandler(TestCase):
    """测试HMAC签名认证处理器"""

    def setUp(self):
        """设置测试环境"""
        self.config = HmacSignatureAuthConfig(
            secret_id="test_secret_id", secret_key="test_secret_key", app_code="test_app_code"
        )
        self.handler = HmacSignatureAuthHandler(self.config)

    def test_set_request_info_parses_url(self):
        """测试set_request_info从URL中正确解析host和path"""
        url = "https://api.example.com/v1/users"
        self.handler.set_request_info(url, "POST")

        self.assertEqual(self.handler.host, "api.example.com")
        self.assertEqual(self.handler.path, "/v1/users")
        self.assertEqual(self.handler.method, "POST")

    def test_set_request_info_parses_url_with_port(self):
        """测试set_request_info解析带端口的URL"""
        url = "https://api.example.com:8080/v1/users"
        self.handler.set_request_info(url, "GET")

        self.assertEqual(self.handler.host, "api.example.com:8080")
        self.assertEqual(self.handler.path, "/v1/users")
        self.assertEqual(self.handler.method, "GET")

    def test_set_request_info_default_path(self):
        """测试URL没有path时默认为/"""
        url = "https://api.example.com"
        self.handler.set_request_info(url, "POST")

        self.assertEqual(self.handler.host, "api.example.com")
        self.assertEqual(self.handler.path, "/")

    def test_set_request_info_parses_complex_url(self):
        """测试解析复杂URL（带查询参数）"""
        url = "https://api.example.com/v1/users?page=1&size=10"
        self.handler.set_request_info(url, "GET")

        self.assertEqual(self.handler.host, "api.example.com")
        self.assertEqual(self.handler.path, "/v1/users")

    def test_generate_signature(self):
        """测试签名生成算法"""
        self.handler.host = "api.example.com"
        date = "Mon, 27 Jan 2026 08:00:00 GMT"

        signature = self.handler._generate_signature("POST", "/v1/users", date)

        # 手动计算预期签名
        signing_str = "(request-target): post /v1/users\n"
        signing_str += "host: api.example.com\n"
        signing_str += f"date: {date}"
        expected_digest = hmac.new(
            self.config.secret_key.encode('utf-8'), signing_str.encode('utf-8'), hashlib.sha256
        ).digest()
        expected_signature = base64.b64encode(expected_digest).decode('utf-8')

        self.assertEqual(signature, expected_signature)

    def test_apply_auth_adds_headers(self):
        """测试apply_auth添加所有必要的请求头"""
        headers = {"Content-Type": "application/json"}
        url = "https://api.example.com/v1/users"

        self.handler.apply_auth(headers, url=url, method="POST")

        self.assertIn("X-APP-CODE", headers)
        self.assertEqual(headers["X-APP-CODE"], "test_app_code")
        self.assertIn("Date", headers)
        self.assertIn("Authorization", headers)

    def test_apply_auth_without_app_code(self):
        """测试app_code为空时不添加X-APP-CODE头"""
        config = HmacSignatureAuthConfig(
            secret_id="test_secret_id", secret_key="test_secret_key", app_code=""  # 空app_code
        )
        handler = HmacSignatureAuthHandler(config)
        headers = {"Content-Type": "application/json"}
        url = "https://api.example.com/v1/users"

        handler.apply_auth(headers, url=url, method="POST")

        self.assertNotIn("X-APP-CODE", headers)
        self.assertIn("Date", headers)
        self.assertIn("Authorization", headers)

    def test_apply_auth_authorization_format(self):
        """测试Authorization头的格式正确"""
        headers = {}
        url = "https://api.example.com/v1/users"

        self.handler.apply_auth(headers, url=url, method="POST")

        auth_header = headers["Authorization"]
        self.assertIn('Signature keyId="test_secret_id"', auth_header)
        self.assertIn('algorithm="hmac-sha256"', auth_header)
        self.assertIn('headers="(request-target) host date"', auth_header)
        self.assertIn('signature="', auth_header)

    def test_apply_auth_uses_preset_info(self):
        """测试apply_auth使用预设的请求信息"""
        self.handler.set_request_info("https://preset.example.com/v1/data", "GET")
        headers = {}

        # 不传url和method，使用预设值
        self.handler.apply_auth(headers)

        self.assertIn("Authorization", headers)
        # 验证使用了preset的host
        self.assertEqual(self.handler.host, "preset.example.com")
        self.assertEqual(self.handler.path, "/v1/data")

    def test_mask_headers_hides_authorization(self):
        """测试mask_headers隐藏Authorization头"""
        headers = {"Content-Type": "application/json"}
        url = "https://api.example.com/v1/users"

        self.handler.apply_auth(headers, url=url, method="POST")
        masked = self.handler.mask_headers(headers)

        self.assertEqual(masked["Authorization"], SENSITIVE_REPLACE_VALUE)
        # 确保原始headers未被修改
        self.assertNotEqual(headers["Authorization"], SENSITIVE_REPLACE_VALUE)

    def test_signature_varies_with_method(self):
        """测试不同HTTP方法产生不同签名"""
        self.handler.host = "api.example.com"
        date = "Mon, 27 Jan 2026 08:00:00 GMT"

        sig_post = self.handler._generate_signature("POST", "/v1/users", date)
        sig_get = self.handler._generate_signature("GET", "/v1/users", date)

        self.assertNotEqual(sig_post, sig_get)

    def test_signature_varies_with_path(self):
        """测试不同路径产生不同签名"""
        self.handler.host = "api.example.com"
        date = "Mon, 27 Jan 2026 08:00:00 GMT"

        sig_users = self.handler._generate_signature("POST", "/v1/users", date)
        sig_items = self.handler._generate_signature("POST", "/v1/items", date)

        self.assertNotEqual(sig_users, sig_items)


class TestAuthHandlerFactory(TestCase):
    """测试认证处理器工厂"""

    def test_create_no_auth_handler(self):
        """测试创建无认证处理器"""
        config = NoAuthItem(method=ApiAuthMethod.NONE.value)
        handler = AuthHandlerFactory.get_handler(config)

        self.assertIsInstance(handler, NoAuthHandler)

    def test_create_bk_app_auth_handler(self):
        """测试创建蓝鲸应用认证处理器"""
        config = BkAuthItem(
            method=ApiAuthMethod.BK_APP_AUTH.value,
            config=BkAppAuthConfig(bk_app_code="test_app", bk_app_secret="test_secret"),
        )
        handler = AuthHandlerFactory.get_handler(config)

        self.assertIsInstance(handler, BkAppAuthHandler)
        self.assertEqual(handler.config.bk_app_code, "test_app")

    def test_create_hmac_signature_handler(self):
        """测试创建HMAC签名认证处理器"""
        config = HmacSignatureAuthItem(
            method=ApiAuthMethod.HMAC_SIGNATURE.value,
            config=HmacSignatureAuthConfig(secret_id="test_id", secret_key="test_key", app_code="test_code"),
        )
        handler = AuthHandlerFactory.get_handler(config)

        self.assertIsInstance(handler, HmacSignatureAuthHandler)
        self.assertEqual(handler.config.secret_id, "test_id")

    def test_create_hmac_handler_with_url(self):
        """测试创建HMAC签名处理器时传入URL"""
        config = HmacSignatureAuthItem(
            method=ApiAuthMethod.HMAC_SIGNATURE.value,
            config=HmacSignatureAuthConfig(secret_id="test_id", secret_key="test_key"),
        )
        url = "https://api.example.com/v1/users"
        handler = AuthHandlerFactory.get_handler(config, url=url, method="POST")

        self.assertIsInstance(handler, HmacSignatureAuthHandler)
        self.assertEqual(handler.host, "api.example.com")
        self.assertEqual(handler.path, "/v1/users")
        self.assertEqual(handler.method, "POST")

    def test_unknown_auth_method_returns_no_auth(self):
        """测试未知认证方法返回无认证处理器"""
        # 创建一个模拟的配置对象，使用未知的method值
        # 由于 NoAuthItem 的 method 是 Literal 类型，无法直接传入未知值
        # 这里使用 mock 对象来模拟未知方法的情况
        mock_config = mock.MagicMock()
        mock_config.method = "unknown_method"
        handler = AuthHandlerFactory.get_handler(mock_config)

        self.assertIsInstance(handler, NoAuthHandler)

    def test_hmac_handler_without_url(self):
        """测试创建HMAC处理器时不传URL"""
        config = HmacSignatureAuthItem(
            method=ApiAuthMethod.HMAC_SIGNATURE.value,
            config=HmacSignatureAuthConfig(secret_id="test_id", secret_key="test_key"),
        )
        handler = AuthHandlerFactory.get_handler(config)

        self.assertIsInstance(handler, HmacSignatureAuthHandler)
        # 未设置URL时，host和path应为默认值
        self.assertEqual(handler.host, "")
        self.assertEqual(handler.path, "")


class TestHmacSignatureIntegration(TestCase):
    """HMAC签名认证集成测试"""

    def test_full_flow_with_factory(self):
        """测试完整的认证流程（通过工厂创建并应用认证）"""
        # 1. 创建认证配置
        config = HmacSignatureAuthItem(
            method=ApiAuthMethod.HMAC_SIGNATURE.value,
            config=HmacSignatureAuthConfig(
                secret_id="prod_secret_id", secret_key="prod_secret_key_12345", app_code="prod_app"
            ),
        )

        # 2. 通过工厂获取处理器
        url = "https://prod-api.example.com/api/v2/blacklist"
        handler = AuthHandlerFactory.get_handler(config, url=url, method="POST")

        # 3. 应用认证
        headers = {"Content-Type": "application/json"}
        handler.apply_auth(headers)

        # 4. 验证结果
        self.assertIn("X-APP-CODE", headers)
        self.assertIn("Date", headers)
        self.assertIn("Authorization", headers)
        self.assertEqual(headers["X-APP-CODE"], "prod_app")

    def test_apply_auth_twice_with_different_urls(self):
        """测试同一个handler对不同URL多次应用认证"""
        config = HmacSignatureAuthConfig(secret_id="test_id", secret_key="test_key")
        handler = HmacSignatureAuthHandler(config)

        # 第一次请求
        headers1 = {}
        handler.apply_auth(headers1, url="https://api.example.com/v1/users", method="GET")
        auth1 = headers1["Authorization"]

        # 第二次请求（不同URL）
        headers2 = {}
        handler.apply_auth(headers2, url="https://api.example.com/v1/items", method="POST")
        auth2 = headers2["Authorization"]

        # 两次认证头应该不同（因为path和method都不同）
        self.assertNotEqual(auth1, auth2)

    @mock.patch('services.web.tool.executor.auth.datetime')
    def test_date_format(self, mock_datetime):
        """测试Date头的格式正确"""
        # Mock datetime.now() 返回固定时间
        mock_now = datetime(2026, 1, 27, 12, 0, 0)
        mock_datetime.now.return_value = mock_now

        config = HmacSignatureAuthConfig(secret_id="test_id", secret_key="test_key")
        handler = HmacSignatureAuthHandler(config)
        headers = {}
        handler.apply_auth(headers, url="https://api.example.com/test", method="POST")

        # 验证Date头格式
        expected_date = mock_now.strftime('%a, %d %b %Y %H:%M:%S GMT')
        self.assertEqual(headers["Date"], expected_date)
