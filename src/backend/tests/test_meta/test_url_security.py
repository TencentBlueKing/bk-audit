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
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the specific language
governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from apps.meta.models import ResourceType, System
from apps.meta.serializers import (
    BulkCreateResourceTypeSerializer,
    CreateSystemReqSerializer,
    ResourceTypeSerializer,
    UpdateSystemReqSerializer,
)
from core.utils.url_security import (
    URLSecurityError,
    mask_authorization,
    validate_request_url,
    validate_resource_path,
)
from tests.base import TestCase


class URLSecurityUtilsTest(TestCase):
    """core.utils.url_security 纯函数测试"""

    def test_validate_request_url_valid(self):
        validate_request_url("https://host.example.com/path")
        validate_request_url("http://host:8080/path")
        # 端口不在高危黑名单即放行（内网地址/回环的禁用属二期黑名单范围，本期不拦）
        validate_request_url("http://127.0.0.1:8000/api")
        # 空值默认放行（空值场景由调用方容错/出口兜底）
        validate_request_url("")
        validate_request_url(None)

    def test_validate_request_url_empty_forbidden(self):
        with self.assertRaises(URLSecurityError):
            validate_request_url("", allow_empty=False)

    def test_validate_request_url_invalid_scheme(self):
        for url in ["ftp://host/path", "file:///etc/passwd", "javascript:alert(1)", "not-a-url", "//host/path"]:
            with self.assertRaises(URLSecurityError):
                validate_request_url(url)

    def test_validate_request_url_missing_netloc(self):
        with self.assertRaises(URLSecurityError):
            validate_request_url("http://")

    def test_validate_request_url_high_risk_port(self):
        # 6379 在默认高危端口黑名单中
        with self.assertRaises(URLSecurityError):
            validate_request_url("http://host:6379/path")

    def test_validate_request_url_malformed_port(self):
        # urlparse 惰性解析端口，畸形端口应转为 URLSecurityError 而非 ValueError
        with self.assertRaises(URLSecurityError):
            validate_request_url("http://host:abc/path")

    def test_validate_request_url_malformed_ipv6(self):
        # urlparse 调用本身对畸形 IPv6 形式（缺右方括号）抛 ValueError，应统一转为 URLSecurityError
        for url in ["http://[::1", "https://[invalid"]:
            with self.assertRaises(URLSecurityError):
                validate_request_url(url)

    def test_validate_resource_path_valid(self):
        validate_resource_path("")
        validate_resource_path("api/v1/resource/")
        # 前导单斜杠无害（拼接时 lstrip 处理）
        validate_resource_path("/api/v1")
        validate_resource_path("resource")

    def test_validate_resource_path_invalid(self):
        for path in ["?x=1", "#fragment", "//evil.com", "a://b", "a b", "a\tb", "a\nb"]:
            with self.assertRaises(URLSecurityError):
                validate_resource_path(path)

    def test_mask_authorization(self):
        masked = mask_authorization({"Authorization": "Basic dXNlcjpwYXNz", "Content-Type": "application/json"})
        self.assertEqual(masked["Authorization"], "Basic ***")
        self.assertNotIn("dXNlcjpwYXNz", masked["Authorization"])
        self.assertEqual(masked["Content-Type"], "application/json")
        # 原 dict 不被修改
        headers = {"Authorization": "Basic abc"}
        mask_authorization(headers)
        self.assertEqual(headers["Authorization"], "Basic abc")
        # 无 Authorization 原样返回
        self.assertEqual(mask_authorization({"X-Token": "1"}), {"X-Token": "1"})


class GetSchemaSecurityTest(TestCase):
    """ResourceTypeSchema.get_schema 发送侧防护测试"""

    def setUp(self):
        self.system = System.objects.create(
            system_id="bk_audit_urlsec",
            source_type="bk_audit",
            instance_id="urlsec",
            namespace="default",
            name="URLSec",
            callback_url="https://callback.example.com",
        )
        self.resource_type = ResourceType.objects.create(
            system_id=self.system.system_id,
            resource_type_id="host",
            unique_id=f"{self.system.system_id}:host",
            name="host",
            path="api/v1/host/",
        )
        # 缓存恒 miss + 屏蔽写缓存副作用
        patcher_get = mock.patch("meta.resources.default_cache.get", mock.Mock(return_value=None))
        patcher_set = mock.patch("meta.resources.default_cache.set", mock.Mock(return_value=None))
        patcher_get.start()
        patcher_set.start()
        self.addCleanup(patcher_get.stop)
        self.addCleanup(patcher_set.stop)

    def _call_schema(self):
        return self.resource.meta.resource_type_schema(
            system_id=self.system.system_id, resource_type_id=self.resource_type.resource_type_id
        )

    def test_block_illegal_url(self):
        """非法 scheme 的 callback_url：返回空列表且不发起请求"""
        self.system.callback_url = "ftp://evil.example.com"
        self.system.save(update_fields=["callback_url"])
        with mock.patch("meta.resources.requests.session") as mock_session:
            result = self._call_schema()
        self.assertEqual(result, [])
        mock_session.return_value.post.assert_not_called()

    def test_block_high_risk_port(self):
        """高危端口：返回空列表且不发起请求（存量脏数据由出口兜底）"""
        self.system.callback_url = "https://callback.example.com:6379"
        self.system.save(update_fields=["callback_url"])
        with mock.patch("meta.resources.requests.session") as mock_session:
            result = self._call_schema()
        self.assertEqual(result, [])
        mock_session.return_value.post.assert_not_called()

    def test_request_kwargs_security(self):
        """合法 URL：外发必须禁重定向并携带 settings 超时"""
        with mock.patch("meta.resources.requests.session") as mock_session:
            mock_session.return_value.post.return_value.json.return_value = {
                "data": {"properties": {"host_id": {"type": "string", "description": "host"}}}
            }
            result = self._call_schema()
        kwargs = mock_session.return_value.post.call_args.kwargs
        self.assertIs(kwargs["allow_redirects"], False)
        self.assertEqual(kwargs["timeout"], settings.FETCH_INSTANCE_SCHEMA_TIMEOUT)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "host_id")

    @override_settings(FETCH_INSTANCE_SCHEMA_TIMEOUT=17)
    def test_timeout_from_settings(self):
        """超时取值经 settings 可调（参照 AI_AGENT_API_TIMEOUT_SECONDS 模式）"""
        with mock.patch("meta.resources.requests.session") as mock_session:
            mock_session.return_value.post.return_value.json.return_value = {"data": {"properties": {}}}
            self._call_schema()
        self.assertEqual(mock_session.return_value.post.call_args.kwargs["timeout"], 17)

    def test_log_masked_on_failure(self):
        """外发失败：异常日志的请求头必须经 mask_authorization 脱敏"""
        with mock.patch("meta.resources.requests.session") as mock_session, mock.patch(
            "meta.resources.mask_authorization", return_value={"Authorization": "Basic ***"}
        ) as mock_mask:
            mock_session.return_value.post.side_effect = ConnectionError("boom")
            result = self._call_schema()
        self.assertEqual(result, [])
        mock_mask.assert_called_once()
        # 传入脱敏的必须是完整请求头（含真实 Authorization）
        self.assertIn("Authorization", mock_mask.call_args[0][0])


class SerializerURLSecurityTest(TestCase):
    """写入侧序列化校验测试（callback_url / path / 拼接）"""

    CREATE_SYSTEM_DATA = {
        "instance_id": "urlsec_sys",
        "namespace": "default",
        "name": "URLSec System",
        "clients": ["app_code1"],
        "managers": ["admin"],
    }

    def test_create_system_serializer_rejects_bad_callback_url(self):
        for bad_url in ["ftp://host", "javascript:alert(1)", "not-a-url", "http://host:9200"]:
            data = dict(self.CREATE_SYSTEM_DATA, callback_url=bad_url)
            serializer = CreateSystemReqSerializer(data=data)
            self.assertFalse(serializer.is_valid(), bad_url)
            self.assertIn("callback_url", serializer.errors, bad_url)

    def test_create_system_serializer_rejects_malformed_callback_url(self):
        """urlparse 解析异常（畸形 IPv6）统一转为 400 参数错误而非 500"""
        data = dict(self.CREATE_SYSTEM_DATA, callback_url="http://[::1")
        serializer = CreateSystemReqSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("callback_url", serializer.errors)

    def test_create_system_serializer_accepts_valid_callback_url(self):
        data = dict(self.CREATE_SYSTEM_DATA, callback_url="https://host.example.com/")
        self.assertTrue(CreateSystemReqSerializer(data=data).is_valid())

    def test_create_system_serializer_accepts_empty_callback_url(self):
        data = dict(self.CREATE_SYSTEM_DATA, callback_url="")
        self.assertTrue(CreateSystemReqSerializer(data=data).is_valid())

    def test_update_system_serializer_rejects_bad_callback_url(self):
        data = {"system_id": "bk_audit_urlsec", "namespace": "default", "callback_url": "ftp://host"}
        serializer = UpdateSystemReqSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("callback_url", serializer.errors)

    def test_update_system_serializer_accepts_valid_callback_url(self):
        data = {"system_id": "bk_audit_urlsec", "namespace": "default", "callback_url": "https://host.example.com/"}
        self.assertTrue(UpdateSystemReqSerializer(data=data).is_valid())

    def _resource_type_data(self, **kwargs):
        return {
            "system_id": "bk_audit_urlsec",
            "resource_type_id": "host",
            "name": "host",
            "path": "api/v1/host/",
            **kwargs,
        }

    def test_resource_type_serializer_rejects_bad_path(self):
        for bad_path in ["?x=1", "#frag", "//evil.com", "a://b", "a b"]:
            serializer = ResourceTypeSerializer(data=self._resource_type_data(path=bad_path))
            self.assertFalse(serializer.is_valid(), bad_path)
            self.assertIn("path", serializer.errors, bad_path)

    def test_resource_type_serializer_accepts_valid_path(self):
        self.assertTrue(ResourceTypeSerializer(data=self._resource_type_data()).is_valid())

    def test_resource_type_serializer_combined_url_validation(self):
        """存量系统 callback_url 含高危端口时，写入新 path 触发拼接校验拦截"""
        System.objects.create(
            system_id="bk_audit_urlsec",
            source_type="bk_audit",
            instance_id="urlsec",
            namespace="default",
            name="URLSec",
            callback_url="http://legacy.example.com:6379",
        )
        serializer = ResourceTypeSerializer(data=self._resource_type_data(path="api"))
        self.assertFalse(serializer.is_valid())
        self.assertIn("path", serializer.errors)

    def test_resource_type_serializer_skip_combined_when_path_absent(self):
        """仅改名称等字段（未传 path）不触发拼接校验，存量脏 path 不阻塞编辑"""
        data = {"system_id": "bk_audit_urlsec", "resource_type_id": "host", "name": "new name"}
        serializer = ResourceTypeSerializer(data=data, partial=True)
        self.assertTrue(serializer.is_valid())

    def test_bulk_create_resource_type_serializer_rejects_bad_path(self):
        """bulk_create 与单条创建走同一序列化器，校验同样生效"""
        serializer = BulkCreateResourceTypeSerializer(
            data={"resource_types": [self._resource_type_data(path="//evil.com")]}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("resource_types", serializer.errors)


class ScanURLSecurityCommandTest(TestCase):
    """存量扫描管理命令测试（发布门禁）"""

    def _create_system(self, callback_url):
        return System.objects.create(
            system_id="bk_audit_urlsec",
            source_type="bk_audit",
            instance_id="urlsec",
            namespace="default",
            name="URLSec",
            callback_url=callback_url,
        )

    def test_clean_data_passes(self):
        system = self._create_system("https://callback.example.com")
        ResourceType.objects.create(
            system_id=system.system_id,
            resource_type_id="host",
            unique_id=f"{system.system_id}:host",
            name="host",
            path="api/v1/host/",
        )
        call_command("scan_url_security")  # 不抛异常即通过

    def test_dirty_callback_url_raises(self):
        self._create_system("ftp://evil.example.com")
        with self.assertRaises(CommandError):
            call_command("scan_url_security")

    def test_malformed_callback_url_scanned_not_crash(self):
        """urlparse 解析异常（畸形 IPv6）在扫描中计入清单而非中断"""
        self._create_system("http://[::1")
        with self.assertRaises(CommandError) as ctx:
            call_command("scan_url_security")
        self.assertIn("bk_audit_urlsec", str(ctx.exception))

    def test_dirty_path_raises(self):
        system = self._create_system("https://callback.example.com")
        ResourceType.objects.create(
            system_id=system.system_id,
            resource_type_id="host",
            unique_id=f"{system.system_id}:host",
            name="host",
            path="//evil.com",
        )
        with self.assertRaises(CommandError):
            call_command("scan_url_security")

    def test_dirty_combined_url_raises(self):
        """拼接后命中高危端口（单项各自合法形态）"""
        system = self._create_system("https://callback.example.com:6379")
        ResourceType.objects.create(
            system_id=system.system_id,
            resource_type_id="host",
            unique_id=f"{system.system_id}:host",
            name="host",
            path="api/v1/host/",
        )
        with self.assertRaises(CommandError):
            call_command("scan_url_security")
