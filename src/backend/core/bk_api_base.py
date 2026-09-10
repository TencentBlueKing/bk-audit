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

from bk_resource import BkApiResource
from django.conf import settings

from core.tenant import get_admin_username, use_multi_tenant_mode


class AuditBkApiResource(BkApiResource):
    """审计中心 API 基类：多租户 Header + 应用态 bk_admin 身份

    所有 api/* 模块的资源类由继承 BkApiResource 改为继承 AuditBkApiResource。

    多租户开关 BKPAAS_MULTI_TENANT_MODE = true 时：
      - 所有出站请求携带 X-Bk-Tenant-Id: {BK_TENANT_ID}
      - use_admin_username=True 的资源：移除 access_token，bk_username → bk_admin

    关闭时行为与改造前完全一致。
    """

    use_admin_username = False

    @staticmethod
    def use_multi_tenant_mode() -> bool:
        """多租户模式开关检测"""
        return use_multi_tenant_mode()

    def set_headers(self, headers: dict, validated_request_data: dict) -> dict:
        """子类扩展点：补充业务侧 Header。

        基类实现为空操作，子类按需覆盖：
            def set_headers(self, headers, validated_request_data):
                headers["X-Custom"] = "value"
                return headers
        """
        return headers

    def build_header(self, validated_request_data: dict) -> dict:
        """构造请求头：多租户 Header + 应用态 bk_admin 身份

        1. super().build_header() 走原生的 x-bkapi-authorization 构造逻辑
        2. 多租户模式下追加 X-Bk-Tenant-Id Header
        3. use_admin_username=True 时：
           - 移除 access_token：应用态调用不使用用户 token，与 admin 认证方式冲突
           - 替换 bk_username：平台态调用应以租户内 bk_admin 身份发起
        4. 调用 set_headers() 供子类补充业务侧 Header
        """
        headers = super().build_header(validated_request_data)

        if self.use_multi_tenant_mode():
            tenant_id = getattr(settings, "BK_TENANT_ID", "")
            headers["X-Bk-Tenant-Id"] = tenant_id

            if self.use_admin_username:
                raw_auth = headers.get("x-bkapi-authorization", "{}")
                auth = json.loads(raw_auth) if isinstance(raw_auth, str) else raw_auth
                # 移除 access_token：应用态接口不使用用户 token
                auth.pop("access_token", None)
                # 替换为租户管理员 bk_username
                admin_username = get_admin_username(tenant_id)
                if admin_username:
                    auth["bk_username"] = admin_username
                headers["x-bkapi-authorization"] = json.dumps(auth)

        return self.set_headers(headers, validated_request_data)
