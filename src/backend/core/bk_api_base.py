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
import traceback

from bk_resource import BkApiResource
from blueapps.utils.logger import logger
from django.conf import settings

from core.tenant import get_admin_username, get_bk_tenant_id, use_multi_tenant_mode


class AuditBkApiResource(BkApiResource):
    """审计中心 API 基类：多租户 Header + 身份分流

    所有 api/* 模块的资源类由继承 BkApiResource 改为继承 AuditBkApiResource。

    单租户模式：完全沿用 SDK 原生逻辑，platform_authorization 在该维度生效，行为不变。

    多租户开关 BKPAAS_MULTI_TENANT_MODE = true 时，不再参考 platform_authorization，
    只按 use_admin_username 分流（基类默认 False）：
      - 所有出站请求携带 X-Bk-Tenant-Id: {BK_TENANT_ID}
      - use_admin_username=True（应用态/系统态）：bk_username → bk_admin，移除 access_token
      - use_admin_username=False/未配（用户态）：以真实登录用户身份发起，不借用平台账号
    """

    use_admin_username = False

    def before_request(self, kwargs: dict) -> dict:
        """从最终 GET query 中剥离已被 URL 路径占位符消费的 url_keys。

        SDK 的 build_url 只读取 url_keys 用于路径 format，不会移除它们。本类刻意
        不覆写 build_url：build_header / set_headers / perform_request 仍依赖同一份
        请求数据（如 NamespacesList.build_header 读取 tenant、bk_iam
        GetSystemRoles 读取 system_id），提前弹出会造成 KeyError 或请求体丢字段。

        剥离放在 before_request：此时路径与 Header 均已构造完成，且只重建 params
        字典而非原地修改，perform_request 的后置逻辑仍可读到原始请求数据。
        json / data 请求体不剥离：部分接口（如 bk_iam V3 管理类 API）会显式把
        url_keys 放进请求体，统一移除会改变既有协议。
        """
        params = kwargs.get("params")
        if isinstance(params, dict) and self.url_keys:
            kwargs["params"] = {key: value for key, value in params.items() if key not in self.url_keys}
        return super().before_request(kwargs)

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

    def _build_user_state_params(self, params: dict) -> dict:
        """多租户 + 用户态 headers 参数"""
        from blueapps.utils.request_provider import get_local_request

        request = params.pop("_request", None) or get_local_request()
        user = getattr(request, "user", None)
        username = getattr(user, "bk_username", None) or getattr(user, "username", None)
        if not username or not getattr(user, "is_authenticated", False):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied("Authenticated user required for personal BK resource")
        params.pop("_is_backend", None)
        params.pop("bk_username", None)
        params.update(
            {
                "bk_app_code": settings.APP_CODE,
                "bk_app_secret": settings.SECRET_KEY,
                "bk_username": username,
            }
        )
        params.update(self.build_auth_args(request))
        return params

    def add_esb_info_before_request(self, params: dict) -> dict:
        """构造 body 鉴权信息（含后台/异步任务强制平台鉴权路径）。

        分流规则：
          - 单租户：完全走 SDK 原生逻辑（platform_authorization 在该维度生效），行为不变。
          - 多租户：不再参考 platform_authorization，只按 use_admin_username 分流：
              * use_admin_username=True（应用态/系统态，如 ITSM V4、bk_log 系统操作）：
                以「应用凭据 + 租户管理员 bk_admin」组装，绕过已清空的旧平台凭据。
                覆盖前端路径与后台/异步任务强制平台鉴权路径。
              * use_admin_username=False 或未配（用户态，基类默认 False）：以「应用凭据 +
                真实登录用户」组装，不借用平台账号，确保后台路径不会因旧凭据为空而抛错
                或丢失用户身份。
        """
        if not self.use_multi_tenant_mode():
            return super().add_esb_info_before_request(params)

        if self.use_admin_username:
            params.pop("access_token", None)
            params.pop("bk_username", None)
            params.pop("_request", None)
            params.pop("_is_backend", None)
            params.update(
                {
                    "bk_app_code": settings.APP_CODE,
                    "bk_app_secret": settings.SECRET_KEY,
                    "bk_username": get_admin_username(get_bk_tenant_id()),
                }
            )
            return params

        return self._build_user_state_params(params)

    def build_header(self, validated_request_data: dict) -> dict:
        """构造请求头：多租户追加 X-Bk-Tenant-Id。

        鉴权身份（应用态 bk_admin / 用户态真实登录用户）已由 add_esb_info_before_request
        统一构造——前端 header 路径（bkapi_header_authorization=True）与后台 body 路径
        （bkapi_data_authorization=True）共用该方法。因此此处不再重复处理
        x-bkapi-authorization，只负责追加租户 Header 并暴露给子类扩展点 set_headers()。
        """
        headers = super().build_header(validated_request_data)

        if self.use_multi_tenant_mode():
            headers["X-Bk-Tenant-Id"] = get_bk_tenant_id()

        # 打印最终生效的鉴权身份，便于部署时确认使用的是哪个虚拟用户
        _auth = headers.get("x-bkapi-authorization", "{}")
        _auth = json.loads(_auth) if isinstance(_auth, str) else _auth
        logger.info(
            "[AuditBkApiResource] 出站请求鉴权身份: module=%s action=%s use_admin_username=%s "
            "multi_tenant=%s bk_username=%s has_access_token=%s",
            getattr(self, "module_name", ""),
            getattr(self, "action", ""),
            self.use_admin_username,
            self.use_multi_tenant_mode(),
            _auth.get("bk_username"),
            "access_token" in _auth,
        )

        return self.set_headers(headers, validated_request_data)

    def perform_request(self, validated_request_data: dict):
        """统一捕获出站请求的真实异常并打印完整 traceback。

        bk_resource 在捕获底层异常（如 requests 抛出的 TypeError）后，
        仅用 err.__doc__（例如 "Inappropriate argument type."）构造 APIRequestError，
        导致真实错误原因和堆栈丢失，难以排查。

        此处在不改变原有调用链的前提下，先执行原生请求逻辑，
        若发生异常则打印 module/action/url 上下文、真实错误信息及完整堆栈，再原样抛出，
        从而让部署/初始化（如 bk-audit-system-init）场景能看到具体失败原因。
        """
        try:
            return super().perform_request(validated_request_data)
        except Exception as err:
            # 已关闭原始请求日志的资源由脱敏 mixin 记录，不再输出异常原文和 traceback。
            if not self.support_data_collect:
                raise
            logger.error(
                "[AuditBkApiResource] 出站请求失败: module=%s action=%s url=%s error_type=%s error=%s\n%s",
                getattr(self, "module_name", ""),
                getattr(self, "action", ""),
                getattr(self, "url", ""),
                err.__class__.__name__,
                err,
                traceback.format_exc(),
            )
            raise
