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
import os

from django.utils.translation import gettext_lazy
from rest_framework.permissions import BasePermission

from core.models import get_request_username


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


class IsCreator(BasePermission):
    """判断是否为创建者"""

    def has_object_permission(self, request, view, obj):
        return obj.created_by == get_request_username()
