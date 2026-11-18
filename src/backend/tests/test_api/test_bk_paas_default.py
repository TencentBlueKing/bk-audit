# -*- coding: utf-8 -*-
import json
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from api.bk_paas.default import UniAppsQuery


class TestPaaSV3BuildHeader(SimpleTestCase):
    """PaaS 应用态鉴权请求头回归测试

    验证 PaaSV3BaseResource.build_header 在两种模式下均正确注入
    x-bkapi-authorization 应用凭证头，且多租户模式额外携带 X-Bk-Tenant-Id。
    """

    def test_non_multi_tenant_injects_app_credential(self):
        """非多租户模式：仅注入应用凭证头，不含租户头"""
        resource = UniAppsQuery()

        with mock.patch("core.bk_api_base.use_multi_tenant_mode", return_value=False):
            headers = resource.build_header({})

        auth = json.loads(headers["x-bkapi-authorization"])
        self.assertEqual(auth["bk_app_code"], settings.APP_CODE)
        self.assertEqual(auth["bk_app_secret"], settings.SECRET_KEY)
        self.assertNotIn("X-Bk-Tenant-Id", headers)

    def test_multi_tenant_injects_app_credential_and_tenant_id(self):
        """多租户模式：注入应用凭证头 + 租户头（不依赖 admin 身份替换）"""
        resource = UniAppsQuery()

        with mock.patch("core.bk_api_base.use_multi_tenant_mode", return_value=True), override_settings(
            BK_TENANT_ID="tenant-1"
        ):
            headers = resource.build_header({})

        # 应用凭证头始终由 PaaS 基类注入，覆盖任何 admin 身份改写
        auth = json.loads(headers["x-bkapi-authorization"])
        self.assertEqual(auth["bk_app_code"], settings.APP_CODE)
        self.assertEqual(auth["bk_app_secret"], settings.SECRET_KEY)
        self.assertNotIn("bk_username", auth)

        # 多租户模式自动合并租户头
        self.assertEqual(headers["X-Bk-Tenant-Id"], "tenant-1")

    def test_app_credential_overrides_admin_username_rewrite(self):
        """即使基类在多租户下改写 admin 身份，PaaS 仍以应用凭证头发起请求"""
        resource = UniAppsQuery()
        resource.use_admin_username = True

        with mock.patch("core.bk_api_base.use_multi_tenant_mode", return_value=True), mock.patch(
            "core.bk_api_base.get_admin_username", return_value="bk_admin"
        ), override_settings(BK_TENANT_ID="tenant-2"):
            headers = resource.build_header({})

        auth = json.loads(headers["x-bkapi-authorization"])
        # 应用凭证头未被 admin 身份逻辑污染
        self.assertEqual(auth["bk_app_code"], settings.APP_CODE)
        self.assertNotIn("bk_username", auth)
        self.assertEqual(headers["X-Bk-Tenant-Id"], "tenant-2")
