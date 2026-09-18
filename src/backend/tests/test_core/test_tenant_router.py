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
from unittest.mock import MagicMock

from django.test import RequestFactory, SimpleTestCase, override_settings

from core.middleware.tenant_router import TENANT_ID_HEADER, TenantCookieMiddleware

# 当前实例（部署）绑定租户
INSTANCE_TENANT = "system"
# 用户归属（被路由）租户
USER_TENANT = "tencent"

# 多租户模式统一配置（覆盖默认非多租户）
MT_SETTINGS = {
    "BKPAAS_MULTI_TENANT_MODE": True,
    "BK_TENANT_ID": INSTANCE_TENANT,
}


class _FakeUser:
    """模拟 blueapps 写入的已登录用户，携带 tenant_id。"""

    is_authenticated = True

    def __init__(self, tenant_id):
        self.tenant_id = tenant_id


def _build_request(method, *, tenant_id=None, cookies=None, headers=None):
    """构造一个带（可选）登录用户/ cookie/ header 的请求。"""
    factory = RequestFactory()
    handler = getattr(factory, method.lower())
    request = handler("/audit/some/path/")
    request.COOKIES = dict(cookies or {})
    if tenant_id is not None:
        request.user = _FakeUser(tenant_id)
    if headers:
        for key, value in headers.items():
            request.META["HTTP_" + key.upper().replace("-", "_")] = value
    return request


class _ViewSpy:
    """记录视图是否被调用的可执行视图。"""

    def __init__(self):
        self.executed = False

    def __call__(self, request, *args, **kwargs):
        self.executed = True
        return MagicMock()


class TestTenantCookieMiddleware(SimpleTestCase):
    """覆盖租户路由中间件的隔离与重定向逻辑。"""

    # ---- 1. 非多租户模式完全放行 ----
    @override_settings(BKPAAS_MULTI_TENANT_MODE=False, BK_TENANT_ID=INSTANCE_TENANT)
    def test_non_multi_tenant_mode_passes_through(self):
        mw = TenantCookieMiddleware(lambda req: None)
        request = _build_request("get", tenant_id=USER_TENANT)
        spy = _ViewSpy()
        # 即便用户租户与实例租户不一致，也应完全放行
        self.assertIsNone(mw.process_view(request, spy, (), {}))
        self.assertFalse(spy.executed)
        # 响应也应原样返回（不补种 cookie）
        resp = MagicMock()
        self.assertIs(mw.process_response(request, resp), resp)
        self.assertFalse(resp.set_cookie.called)

    # ---- 2. 未登录请求不触发租户逻辑 ----
    @override_settings(**MT_SETTINGS)
    def test_anonymous_request_skips_tenant_logic(self):
        mw = TenantCookieMiddleware(lambda req: None)
        # 不带 user（或 user 未认证）应直接放行
        request = RequestFactory().get("/audit/")
        self.assertIsNone(mw.process_view(request, _ViewSpy(), (), {}))

        # user 未认证同样放行
        class _AnonUser:
            is_authenticated = False
            tenant_id = USER_TENANT

        request.user = _AnonUser()
        self.assertIsNone(mw.process_view(request, _ViewSpy(), (), {}))

    # ---- 3. system 实例首次落地 tencent：GET 302 + Set-Cookie / 非幂等 409 ----
    @override_settings(**MT_SETTINGS)
    def test_wrong_instance_get_redirects_with_set_cookie(self):
        mw = TenantCookieMiddleware(lambda req: None)
        # 首次落地：无 audit_tenant_id cookie
        request = _build_request("get", tenant_id=USER_TENANT)
        spy = _ViewSpy()
        resp = mw.process_view(request, spy, (), {})

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], request.get_full_path())
        # Set-Cookie 中应写入用户归属租户
        self.assertEqual(resp.cookies.get(mw.TENANT_COOKIE_NAME).value, USER_TENANT)
        # 视图不应执行
        self.assertFalse(spy.executed)

    @override_settings(**MT_SETTINGS)
    def test_wrong_instance_non_idempotent_returns_409(self):
        mw = TenantCookieMiddleware(lambda req: None)
        for method in ("post", "put", "patch", "delete"):
            request = _build_request(method, tenant_id=USER_TENANT)
            spy = _ViewSpy()
            resp = mw.process_view(request, spy, (), {})
            self.assertEqual(resp.status_code, 409)
            self.assertEqual(json.loads(resp.content)["code"], "TenantRouteRetry")
            self.assertEqual(resp.cookies.get(mw.TENANT_COOKIE_NAME).value, USER_TENANT)
            self.assertFalse(spy.executed)

    # ---- 4. 正确实例补种 cookie ----
    @override_settings(BKPAAS_MULTI_TENANT_MODE=True, BK_TENANT_ID=USER_TENANT)
    def test_correct_instance_reseeds_cookie_on_response(self):
        mw = TenantCookieMiddleware(lambda req: None)
        # 落到正确实例、但 cookie 缺失或不一致
        request = _build_request("get", tenant_id=USER_TENANT)
        spy = _ViewSpy()
        self.assertIsNone(mw.process_view(request, spy, (), {}))  # 放行视图
        self.assertFalse(spy.executed)
        # 响应阶段应补种/覆盖 cookie
        resp = MagicMock()
        mw.process_response(request, resp)
        set_cookie_calls = {c.args[0]: c.args[1] for c in resp.set_cookie.call_args_list}
        self.assertEqual(set_cookie_calls.get(mw.TENANT_COOKIE_NAME), USER_TENANT)

    @override_settings(BKPAAS_MULTI_TENANT_MODE=True, BK_TENANT_ID=USER_TENANT)
    def test_correct_instance_existing_cookie_no_reseed(self):
        mw = TenantCookieMiddleware(lambda req: None)
        # cookie 已正确：响应阶段不应重复 set_cookie
        request = _build_request("get", tenant_id=USER_TENANT, cookies={mw.TENANT_COOKIE_NAME: USER_TENANT})
        resp = MagicMock()
        mw.process_response(request, resp)
        self.assertFalse(resp.set_cookie.called)

    # ---- 5. cookie/header 冲突、缺失路由映射返回 409 ----
    @override_settings(**MT_SETTINGS)
    def test_cookie_matched_but_wrong_instance_returns_409_conflict(self):
        mw = TenantCookieMiddleware(lambda req: None)
        # cookie 携带的是用户归属租户（=USER_TENANT），却仍落到 system 实例：
        # 即 tenant-router 按冲突的 X-Bk-Tenant-Id 强制路由，或缺失租户→namespace 映射。
        request = _build_request(
            "get",
            tenant_id=USER_TENANT,
            cookies={mw.TENANT_COOKIE_NAME: USER_TENANT},
            headers={TENANT_ID_HEADER: "other"},
        )
        spy = _ViewSpy()
        resp = mw.process_view(request, spy, (), {})
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(json.loads(resp.content)["code"], "TenantRouteConflict")
        self.assertFalse(spy.executed)

    # ---- 6. process_view 返回响应后视图不执行 ----
    @override_settings(**MT_SETTINGS)
    def test_process_view_response_prevents_view_execution(self):
        mw = TenantCookieMiddleware(lambda req: None)
        spy = _ViewSpy()
        request = _build_request("get", tenant_id=USER_TENANT)
        resp = mw.process_view(request, spy, (), {})
        # 返回了重定向响应，视图不应被调用
        self.assertIsNotNone(resp)
        self.assertFalse(spy.executed)
