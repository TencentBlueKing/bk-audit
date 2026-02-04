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
from unittest import TestCase, mock

from services.web.tool.constants import (
    ApiAuthMethod,
    BkAppAuthConfig,
    BkAuthItem,
    IEOPAuthConfig,
    IEOPAuthItem,
    NoAuthItem,
)
from services.web.tool.executor.auth import (
    AuthHandlerFactory,
    BkAppAuthHandler,
    IEOPAuthHandler,
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


class TestIEOPAuthHandler(TestCase):
    """测试IEOP认证处理器"""

    def setUp(self):
        """设置测试环境"""
        self.config = IEOPAuthConfig(
            app_code="test_app_code",
            app_secret="test_app_secret",
            operator="test_operator",
            secret_id="test_secret_id",
            secret_key="test_secret_key",
        )
        self.handler = IEOPAuthHandler(self.config)

    def test_set_request_info_parses_url(self):
        """测试set_request_info从URL中正确解析host和path"""
        url = "https://api.example.com/v1/users"
        self.handler.set_request_info(url, "GET")

        self.assertEqual(self.handler.host, "api.example.com")
        self.assertEqual(self.handler.path, "/v1/users")
        self.assertEqual(self.handler.method, "GET")

    def test_set_request_info_with_post(self):
        """测试POST方法"""
        url = "https://api.example.com/v1/users"
        self.handler.set_request_info(url, "POST")
        self.assertEqual(self.handler.method, "POST")

    def test_set_request_info_method_case_insensitive(self):
        """测试method不区分大小写"""
        url = "https://api.example.com/v1/users"
        self.handler.set_request_info(url, "get")
        self.assertEqual(self.handler.method, "GET")

        self.handler.set_request_info(url, "Post")
        self.assertEqual(self.handler.method, "POST")

    def test_set_request_info_parses_url_with_port(self):
        """测试set_request_info解析带端口的URL"""
        url = "https://api.example.com:8080/v1/users"
        self.handler.set_request_info(url, "POST")

        self.assertEqual(self.handler.host, "api.example.com:8080")
        self.assertEqual(self.handler.path, "/v1/users")
        self.assertEqual(self.handler.method, "POST")

    def test_set_request_info_default_path(self):
        """测试URL没有path时默认为/"""
        url = "https://api.example.com"
        self.handler.set_request_info(url, "POST")

        self.assertEqual(self.handler.host, "api.example.com")
        self.assertEqual(self.handler.path, "/")

    def test_set_request_info_parses_complex_url(self):
        """测试解析复杂URL（带查询参数）"""
        url = "https://api.example.com/v1/users?page=1&size=10"
        self.handler.set_request_info(url, "POST")

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

        self.handler.apply_auth(headers, body={}, url=url)

        self.assertIn("Date", headers)
        self.assertIn("Authorization", headers)

    def test_apply_auth_adds_body_params(self):
        """测试apply_auth自动添加认证参数到body"""
        headers = {"Content-Type": "application/json"}
        body = {"some_param": "some_value"}
        url = "https://api.example.com/v1/users"

        self.handler.apply_auth(headers, body=body, url=url)

        self.assertEqual(body["app_code"], "test_app_code")
        self.assertEqual(body["app_secret"], "test_app_secret")
        self.assertEqual(body["operator"], "test_operator")
        self.assertEqual(body["some_param"], "some_value")

    def test_apply_auth_without_operator(self):
        """测试operator为空且获取不到当前用户时不添加到body"""
        config = IEOPAuthConfig(
            app_code="test_app",
            app_secret="test_secret",
            operator="",  # 空operator
            secret_id="test_id",
            secret_key="test_key",
        )
        handler = IEOPAuthHandler(config)
        headers = {"Content-Type": "application/json"}
        body = {}
        url = "https://api.example.com/v1/users"

        with mock.patch('services.web.tool.executor.auth.get_request_username', return_value=""):
            handler.apply_auth(headers, body=body, url=url)

        self.assertNotIn("operator", body)
        self.assertIn("app_code", body)
        self.assertIn("app_secret", body)

    def test_apply_auth_default_operator_from_current_user(self):
        """测试operator为空时自动获取当前用户"""
        config = IEOPAuthConfig(
            app_code="test_app",
            app_secret="test_secret",
            operator="",  # 空operator
            secret_id="test_id",
            secret_key="test_key",
        )
        handler = IEOPAuthHandler(config)
        headers = {"Content-Type": "application/json"}
        body = {}
        url = "https://api.example.com/v1/users"

        with mock.patch('services.web.tool.executor.auth.get_request_username', return_value="current_user"):
            handler.apply_auth(headers, body=body, url=url)

        self.assertEqual(body["operator"], "current_user")

    def test_apply_auth_prefer_config_operator(self):
        """测试配置的operator优先级高于当前用户"""
        config = IEOPAuthConfig(
            app_code="test_app",
            app_secret="test_secret",
            operator="config_operator",
            secret_id="test_id",
            secret_key="test_key",
        )
        handler = IEOPAuthHandler(config)
        headers = {"Content-Type": "application/json"}
        body = {}
        url = "https://api.example.com/v1/users"

        with mock.patch('services.web.tool.executor.auth.get_request_username', return_value="current_user"):
            handler.apply_auth(headers, body=body, url=url)

        # 应该使用配置的operator，而不是当前用户
        self.assertEqual(body["operator"], "config_operator")

    def test_apply_auth_deserializes_data_json_string(self):
        """测试apply_auth自动反序列化body中的data字段"""
        headers = {}
        body = {"data": '{"key": "value", "number": 123}'}
        url = "https://api.example.com/v1/users"

        self.handler.apply_auth(headers, body=body, url=url)

        self.assertIsInstance(body["data"], dict)
        self.assertEqual(body["data"]["key"], "value")
        self.assertEqual(body["data"]["number"], 123)

    def test_apply_auth_keeps_data_if_not_string(self):
        """测试data不是字符串时保持原样"""
        headers = {}
        body = {"data": {"already": "dict"}}
        url = "https://api.example.com/v1/users"

        self.handler.apply_auth(headers, body=body, url=url)

        self.assertEqual(body["data"], {"already": "dict"})

    def test_apply_auth_keeps_data_if_invalid_json(self):
        """测试data是无效JSON字符串时保持原样"""
        headers = {}
        body = {"data": "not valid json {"}
        url = "https://api.example.com/v1/users"

        self.handler.apply_auth(headers, body=body, url=url)

        self.assertEqual(body["data"], "not valid json {")

    def test_apply_auth_skips_body_if_none(self):
        """测试POST请求body为None时跳过body处理"""
        headers = {}
        url = "https://api.example.com/v1/users"

        # body为None时，apply_auth只处理headers，不报错
        self.handler.apply_auth(headers, body=None, url=url)

        # 验证headers被正确处理
        self.assertIn("Date", headers)
        self.assertIn("Authorization", headers)

    def test_apply_auth_get_request_adds_to_query_params(self):
        """测试GET请求时认证参数添加到query_params"""
        self.handler.method = "GET"
        headers = {"Content-Type": "application/json"}
        query_params = {"existing": "param"}
        url = "https://api.example.com/v1/users"

        self.handler.apply_auth(headers, query_params=query_params, url=url)

        self.assertEqual(query_params["app_code"], "test_app_code")
        self.assertEqual(query_params["app_secret"], "test_app_secret")
        self.assertEqual(query_params["operator"], "test_operator")
        self.assertEqual(query_params["existing"], "param")
        # headers也应该被处理
        self.assertIn("Date", headers)
        self.assertIn("Authorization", headers)

    def test_apply_auth_get_request_skips_if_query_params_none(self):
        """测试GET请求query_params为None时跳过参数处理"""
        self.handler.method = "GET"
        headers = {}
        url = "https://api.example.com/v1/users"

        # query_params为None时，apply_auth只处理headers
        self.handler.apply_auth(headers, query_params=None, url=url)

        self.assertIn("Date", headers)
        self.assertIn("Authorization", headers)

    def test_apply_auth_post_does_not_modify_query_params(self):
        """测试POST请求不修改query_params"""
        self.handler.method = "POST"
        headers = {}
        body = {}
        query_params = {"existing": "param"}
        url = "https://api.example.com/v1/users"

        self.handler.apply_auth(headers, body=body, query_params=query_params, url=url)

        # POST请求只修改body，不修改query_params
        self.assertNotIn("app_code", query_params)
        self.assertEqual(query_params, {"existing": "param"})
        # 认证参数应该在body中
        self.assertEqual(body["app_code"], "test_app_code")

    def test_apply_auth_authorization_format(self):
        """测试Authorization头的格式正确"""
        headers = {}
        url = "https://api.example.com/v1/users"

        self.handler.apply_auth(headers, body={}, url=url)

        auth_header = headers["Authorization"]
        self.assertIn('Signature keyId="test_secret_id"', auth_header)
        self.assertIn('algorithm="hmac-sha256"', auth_header)
        self.assertIn('headers="(request-target) host date"', auth_header)
        self.assertIn('signature="', auth_header)

    def test_apply_auth_uses_preset_info(self):
        """测试apply_auth使用预设的请求信息"""
        self.handler.set_request_info("https://preset.example.com/v1/data", "POST")
        headers = {}

        # 不传url，使用预设值
        self.handler.apply_auth(headers, body={})

        self.assertIn("Authorization", headers)
        # 验证使用了preset的host
        self.assertEqual(self.handler.host, "preset.example.com")
        self.assertEqual(self.handler.path, "/v1/data")

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

    def test_create_ieop_auth_handler(self):
        """测试创建IEOP认证处理器"""
        config = IEOPAuthItem(
            method=ApiAuthMethod.IEOP_AUTH.value,
            config=IEOPAuthConfig(
                app_code="test_app",
                app_secret="test_secret",
                operator="test_operator",
                secret_id="test_id",
                secret_key="test_key",
            ),
        )
        handler = AuthHandlerFactory.get_handler(config)

        self.assertIsInstance(handler, IEOPAuthHandler)
        self.assertEqual(handler.config.secret_id, "test_id")
        self.assertEqual(handler.config.app_code, "test_app")

    def test_create_ieop_handler_with_url(self):
        """测试创建IEOP认证处理器时传入URL"""
        config = IEOPAuthItem(
            method=ApiAuthMethod.IEOP_AUTH.value,
            config=IEOPAuthConfig(
                app_code="test_app", app_secret="test_secret", secret_id="test_id", secret_key="test_key"
            ),
        )
        url = "https://api.example.com/v1/users"
        handler = AuthHandlerFactory.get_handler(config, url=url, method="GET")

        self.assertIsInstance(handler, IEOPAuthHandler)
        self.assertEqual(handler.host, "api.example.com")
        self.assertEqual(handler.path, "/v1/users")
        self.assertEqual(handler.method, "GET")  # 支持GET

    def test_create_ieop_handler_with_post_method(self):
        """测试创建IEOP认证处理器时传入POST方法"""
        config = IEOPAuthItem(
            method=ApiAuthMethod.IEOP_AUTH.value,
            config=IEOPAuthConfig(
                app_code="test_app", app_secret="test_secret", secret_id="test_id", secret_key="test_key"
            ),
        )
        url = "https://api.example.com/v1/users"
        handler = AuthHandlerFactory.get_handler(config, url=url, method="POST")

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

    def test_ieop_handler_without_url(self):
        """测试创建IEOP处理器时不传URL"""
        config = IEOPAuthItem(
            method=ApiAuthMethod.IEOP_AUTH.value,
            config=IEOPAuthConfig(
                app_code="test_app", app_secret="test_secret", secret_id="test_id", secret_key="test_key"
            ),
        )
        handler = AuthHandlerFactory.get_handler(config)

        self.assertIsInstance(handler, IEOPAuthHandler)
        # 未设置URL时，host和path应为默认值
        self.assertEqual(handler.host, "")
        self.assertEqual(handler.path, "")


class TestIEOPAuthIntegration(TestCase):
    """IEOP认证集成测试"""

    def test_full_flow_with_factory(self):
        """测试完整的认证流程（通过工厂创建并应用认证）"""
        # 1. 创建认证配置
        config = IEOPAuthItem(
            method=ApiAuthMethod.IEOP_AUTH.value,
            config=IEOPAuthConfig(
                app_code="prod_app",
                app_secret="prod_secret_12345",
                operator="admin",
                secret_id="prod_secret_id",
                secret_key="prod_secret_key_12345",
            ),
        )

        # 2. 通过工厂获取处理器
        url = "https://prod-api.example.com/api/v2/blacklist"
        handler = AuthHandlerFactory.get_handler(config, url=url, method="POST")

        # 3. 应用认证
        headers = {"Content-Type": "application/json"}
        body = {"data": '{"user_id": 123}'}
        handler.apply_auth(headers, body=body)

        # 4. 验证headers
        self.assertIn("Date", headers)
        self.assertIn("Authorization", headers)

        # 5. 验证body（直接检查传入的body被修改）
        self.assertEqual(body["app_code"], "prod_app")
        self.assertEqual(body["app_secret"], "prod_secret_12345")
        self.assertEqual(body["operator"], "admin")
        # data应该被反序列化
        self.assertIsInstance(body["data"], dict)
        self.assertEqual(body["data"]["user_id"], 123)

    def test_apply_auth_twice_with_different_urls(self):
        """测试同一个handler对不同URL多次应用认证"""
        config = IEOPAuthConfig(
            app_code="test_app", app_secret="test_secret", secret_id="test_id", secret_key="test_key"
        )
        handler = IEOPAuthHandler(config)

        # 第一次请求
        headers1 = {}
        handler.apply_auth(headers1, body={}, url="https://api.example.com/v1/users")
        auth1 = headers1["Authorization"]

        # 第二次请求（不同URL）
        headers2 = {}
        handler.apply_auth(headers2, body={}, url="https://api.example.com/v1/items")
        auth2 = headers2["Authorization"]

        # 两次认证头应该不同（因为path不同）
        self.assertNotEqual(auth1, auth2)

    @mock.patch('services.web.tool.executor.auth.datetime')
    def test_date_format(self, mock_datetime):
        """测试Date头的格式正确"""
        # Mock datetime.now() 返回固定时间
        mock_now = datetime(2026, 1, 27, 12, 0, 0)
        mock_datetime.now.return_value = mock_now

        config = IEOPAuthConfig(
            app_code="test_app", app_secret="test_secret", secret_id="test_id", secret_key="test_key"
        )
        handler = IEOPAuthHandler(config)
        headers = {}
        handler.apply_auth(headers, body={}, url="https://api.example.com/test")

        # 验证Date头格式
        expected_date = mock_now.strftime('%a, %d %b %Y %H:%M:%S GMT')
        self.assertEqual(headers["Date"], expected_date)
