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
import os

from bk_resource import resource
from django.conf import settings
from django.utils.translation import gettext_lazy
from rest_framework.permissions import BasePermission

from apps.permission.handlers.actions import ActionEnum
from core.exceptions import PermissionException


class Permission(BasePermission):
    code = 403
    message = gettext_lazy("Permission Denied")


class IsStaffPermission(Permission):
    message = gettext_lazy("Staff Required")

    def has_permission(self, request, view):
        if request.user.is_staff:
            return True
        return False


class IsAdminPermission(Permission):
    message = gettext_lazy("Admin Required")

    def has_permission(self, request, view):
        if request.user.is_superuser:
            return True
        return False


class SwaggerPermission(IsStaffPermission):
    # 为 Swagger 使用的 HtmlRenderer 做兼容，传递 Object
    message = {"message": IsStaffPermission.message}


class TokenSwaggerPermission(BasePermission):
    """Swagger Token 获取方式"""

    message = gettext_lazy("Token Invalid")

    def has_permission(self, request, view):
        _token = os.getenv("BKAPP_SWAGGER_TOKEN")
        # 未配置 Token 默认不开放
        if not _token:
            return False
        # 获取用户传递的 Token
        token = request.GET.get("token")
        # 比对 Token
        if token == _token:
            return True
        return False


class SearchLogPermission:
    @classmethod
    def get_auth_systems(cls, namespace) -> (list, list):
        systems = resource.meta.system_list_all(namespace=namespace, action_ids=ActionEnum.SEARCH_REGULAR_EVENT.id)
        authorized_systems = [
            system["id"] for system in systems if system["permission"].get(ActionEnum.SEARCH_REGULAR_EVENT.id)
        ]
        return systems, authorized_systems

    @classmethod
    def any_search_log_permission(cls, namespace) -> None:
        if not cls.get_auth_systems(namespace)[1]:
            from apps.permission.handlers.permission import Permission

            apply_data, apply_url = Permission().get_apply_data([ActionEnum.SEARCH_REGULAR_EVENT])
            raise PermissionException(
                action_name=ActionEnum.SEARCH_REGULAR_EVENT.name,
                apply_url=apply_url,
                permission=apply_data,
            )


class FetchInstancePermission(BasePermission):
    @classmethod
    def build_auth(cls, username, token):
        base64_token = base64.b64encode(f"{username}:{token}".encode("utf-8")).decode("utf-8")
        system_token = f"Basic {base64_token}"
        return system_token

    def has_permission(self, request, view):
        system_token = self.build_auth(settings.FETCH_INSTANCE_USERNAME, settings.FETCH_INSTANCE_TOKEN)
        user_auth_token = request.META.get("HTTP_AUTHORIZATION")
        if system_token == user_auth_token:
            return True
        return False
