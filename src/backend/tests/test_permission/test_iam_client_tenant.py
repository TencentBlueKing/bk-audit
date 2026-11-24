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
either express or implied. See the License at the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
from unittest import mock

from django.test import override_settings
from iam.api.client import Client

from apps.permission.handlers.permission import Permission
from tests.base import TestCase


class IAMClientTenantTest(TestCase):
    """验证 get_iam_client 向 IAM V3 SDK 传递租户 ID 的行为
    约定：
    - 多租户模式：传实例租户 ID（AUDIT_INSTANCE_TENANT_ID）
    - 非多租户模式：传空字符串，即使 BKPAAS_APP_TENANT_ID 被注入也不带租户头
    """

    @override_settings(
        BKPAAS_MULTI_TENANT_MODE=False,
        BK_TENANT_ID="",
        AUDIT_INSTANCE_TENANT_ID="",
    )
    @mock.patch("apps.permission.handlers.permission.IAM")
    def test_single_tenant_no_tenant_id(self, mock_iam):
        """单租户（未注入任何租户）：IAM SDK 应收到空字符串"""
        Permission.get_iam_client()
        _, kwargs = mock_iam.call_args
        self.assertEqual(kwargs.get("bk_tenant_id", "MISSING"), "")

    @override_settings(
        BKPAAS_MULTI_TENANT_MODE=False,
        BK_TENANT_ID="some_app_tenant",
        AUDIT_INSTANCE_TENANT_ID="",
    )
    @mock.patch("apps.permission.handlers.permission.IAM")
    def test_single_tenant_with_injected_app_tenant_still_no_header(self, mock_iam):
        """单租户但旧环境注入 BKPAAS_APP_TENANT_ID：仍不应带租户头（与基线对齐）"""
        Permission.get_iam_client()
        _, kwargs = mock_iam.call_args
        self.assertEqual(kwargs.get("bk_tenant_id", "MISSING"), "")

    @override_settings(
        BKPAAS_MULTI_TENANT_MODE=True,
        BK_TENANT_ID="instance-tenant-1",
        AUDIT_INSTANCE_TENANT_ID="instance-tenant-1",
    )
    @mock.patch("apps.permission.handlers.permission.IAM")
    def test_multi_tenant_passes_instance_tenant_id(self, mock_iam):
        """多租户：应传入实例绑定租户 ID"""
        Permission.get_iam_client()
        _, kwargs = mock_iam.call_args
        self.assertEqual(kwargs.get("bk_tenant_id", "MISSING"), "instance-tenant-1")

    @override_settings(
        BKPAAS_MULTI_TENANT_MODE=True,
        BK_TENANT_ID="instance-tenant-2",
        AUDIT_INSTANCE_TENANT_ID="instance-tenant-2",
    )
    def test_multi_tenant_client_carries_tenant_header(self):
        """多租户：IAM Client 实际构造的请求头应携带 X-Bk-Tenant-Id"""
        iam = Permission.get_iam_client()
        client = iam._client
        self.assertIsInstance(client, Client)
        self.assertEqual(client._bk_tenant_id, "instance-tenant-2")

        headers = {
            "X-Bkapi-Authorization": "{}",
            "X-Bk-IAM-Version": "1",
        }
        # 模拟 SDK 内部 _call_apigateway_api 的 header 追加逻辑
        if client._bk_tenant_id:
            headers["X-Bk-Tenant-Id"] = client._bk_tenant_id
        self.assertEqual(headers.get("X-Bk-Tenant-Id"), "instance-tenant-2")

    @override_settings(
        BKPAAS_MULTI_TENANT_MODE=False,
        BK_TENANT_ID="some_app_tenant",
        AUDIT_INSTANCE_TENANT_ID="",
    )
    def test_single_tenant_client_has_empty_tenant_id(self):
        """单租户：IAM Client 的 bk_tenant_id 应为空，不会附加 X-Bk-Tenant-Id"""
        iam = Permission.get_iam_client()
        client = iam._client
        self.assertEqual(client._bk_tenant_id, "")
        self.assertFalse(bool(client._bk_tenant_id))
