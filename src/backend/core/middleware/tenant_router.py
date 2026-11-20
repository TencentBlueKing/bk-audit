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
import logging

from django.conf import settings
from django.http import HttpResponseRedirect, JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.utils.translation import gettext as _

from core.tenant import resolve_tenant_id

logger = logging.getLogger(__name__)

TENANT_ID_HEADER = "X-Bk-Tenant-Id"


class TenantCookieMiddleware(MiddlewareMixin):
    """
    租户 Cookie 中间件（多租户环境 BKPAAS_MULTI_TENANT_MODE 生效）。

    登录后解析用户租户ID写入 audit_tenant_id cookie（父域），供接入层 tenant-router 路由。
    权威以 user.tenant_id 为准（tenant-router 会回填 X-Bk-Tenant-Id，故 header 不能用作权威）。

    - process_view：落到非用户归属实例时拦截（302/409），视图不执行；
    - process_response：在归属实例上补种/覆盖 audit_tenant_id cookie。
    """

    TENANT_COOKIE_NAME = "audit_tenant_id"

    def _set_tenant_cookie(self, response, tenant_id):
        response.set_cookie(
            self.TENANT_COOKIE_NAME,
            tenant_id,
            domain=settings.SESSION_COOKIE_DOMAIN or None,
            httponly=True,
            samesite="Lax",
        )

    def _resolve_tenant_context(self, request):
        """返回 (tenant_id, cookie_matched)；无法处理时 tenant_id 为 None。"""
        # 因为没有开启多租户，说明不会有路由到错误的租户实例的可能，放行
        if not settings.BKPAAS_MULTI_TENANT_MODE:
            return None, False

        # 因为这个中间件的前面是登录中间件，所以根本不会走这个条件，如果走到这条件，说明这个中间件排到了登录中间件的前面
        # 这里直接放行，让下一个登录中间件进行登录验证
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            return None, False

        # 正常来说，只要是部署多租户环境，就有租户id，获取不到租户id，说明配置或系统出了问题，最好的方式就是放行，让下一个中间件来判断处理
        tenant_id = getattr(user, "tenant_id", "") or resolve_tenant_id(request)
        if not tenant_id:
            return None, False

        cookie_matched = request.COOKIES.get(self.TENANT_COOKIE_NAME) == tenant_id
        return tenant_id, cookie_matched

    # 用于判断租户用户是否转发到错误的租户实例上
    def process_view(self, request, view, args, kwargs):
        tenant_id, cookie_matched = self._resolve_tenant_context(request)
        if not tenant_id:
            return None

        # request租户和当前实例租户一致，放行process_view
        if tenant_id == settings.BK_TENANT_ID:
            return None

        # 租户不一致，且 cookie 尚未带对：种正确 cookie 并纠正路由。
        # 浏览器跟随 302/带新 cookie 重试时不会重发自定义 header，tenant-router 将按 cookie 转到正确实例。
        # cookie_matched 表示 cookie 携带的租户 ≠ 用户归属租户，要重定向到原来的请求url，并带上正确的租户id
        if not cookie_matched:
            if request.method in ("GET", "HEAD"):
                redirect = HttpResponseRedirect(request.get_full_path())
                self._set_tenant_cookie(redirect, tenant_id)
                return redirect
            retry = JsonResponse(
                {"result": False, "code": "TenantRouteRetry", "data": None, "message": _("租户路由未就绪，请重试")},
                status=409,
            )
            self._set_tenant_cookie(retry, tenant_id)
            return retry

        # cookie 已是用户归属租户，却仍落到错误实例。可能原因：
        #   1) 请求带了与用户归属租户冲突的 X-Bk-Tenant-Id header，tenant-router 按 header 强制路由（越权企图）；
        #   2) tenant-router 缺少该租户到 namespace 的映射（配置缺失）。
        # 两种情况都不能在错误实例上服务用户数据（会读写到其它租户），且不再重定向以避免死循环，直接报错。
        logger.error(
            "tenant route conflict: user tenant=%s but served by instance tenant=%s, "
            "header X-Bk-Tenant-Id=%s; check conflicting header or tenant-router tenants mapping",
            tenant_id,
            settings.BK_TENANT_ID,
            request.headers.get(TENANT_ID_HEADER, ""),
        )
        return JsonResponse(
            {"result": False, "code": "TenantRouteConflict", "data": None, "message": _("用户租户错误或不存在")},
            status=409,
        )

    def process_response(self, request, response):
        tenant_id, cookie_matched = self._resolve_tenant_context(request)
        if not tenant_id or tenant_id != settings.BK_TENANT_ID:
            return response

        # 当前实例即用户归属租户：cookie 缺失或不一致则种植/覆盖
        if not cookie_matched:
            self._set_tenant_cookie(response, tenant_id)
        return response
