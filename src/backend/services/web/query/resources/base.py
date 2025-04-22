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

import abc
from typing import List

from bk_resource.contrib.model import ModelResource
from blueapps.utils.request_provider import get_request_username
from django.utils.translation import gettext_lazy

from apps.audit.resources import AuditMixinResource
from apps.meta.models import SensitiveObject
from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.permission import Permission
from apps.permission.handlers.resource_types import ResourceEnum
from services.web.query.models import FavoriteSearch
from services.web.query.serializers import FavoriteSearchSerializer
from services.web.query.utils.formatter import HitsFormatter


class QueryBaseResource(AuditMixinResource, abc.ABC):
    tags = ["Query"]


class SearchDataParser:
    def parse_data(self, data: List[dict]) -> list:
        # 获取敏感字段列表
        private_sensitive_objs = list(SensitiveObject._objects.filter(is_private=True))
        sensitive_objs = list(SensitiveObject.objects.all())
        # 获取用户信息，用于判断敏感权限
        if sensitive_objs:
            username = get_request_username()
            if username:
                permissions = Permission(username).batch_is_allowed(
                    actions=[ActionEnum.ACCESS_AUDIT_SENSITIVE_INFO],
                    resources=[[ResourceEnum.SENSITIVE_OBJECT.create_instance(so.id)] for so in sensitive_objs],
                )
            else:
                permissions = {so.id: {ActionEnum.ACCESS_AUDIT_SENSITIVE_INFO: False} for so in sensitive_objs}
            for so in sensitive_objs:
                setattr(
                    so,
                    "_has_permission",
                    permissions.get(so.id, {}).get(ActionEnum.ACCESS_AUDIT_SENSITIVE_INFO.id, False),
                )
        # parse
        return [HitsFormatter(value, [*sensitive_objs, *private_sensitive_objs]).value for value in data]


class CreateFavouriteSearchResource(QueryBaseResource, ModelResource):
    name = gettext_lazy("创建查询收藏")
    lookup_field = "id"
    model = FavoriteSearch
    action = "list"
    serializer_class = FavoriteSearchSerializer


class UpdateFavouriteSearchResource(QueryBaseResource, ModelResource):
    name = gettext_lazy("更新查询收藏")
    lookup_field = "id"
    model = FavoriteSearch
    action = "update"
    serializer_class = FavoriteSearchSerializer


class DeleteFavouriteSearchResource(QueryBaseResource, ModelResource):
    name = gettext_lazy("删除查询收藏")
    lookup_field = "id"
    model = FavoriteSearch
    action = "destroy"
    serializer_class = FavoriteSearchSerializer


class ListFavouriteSearchResource(QueryBaseResource, ModelResource):
    """支持过滤查询收藏列表，支持的filter参数有：name、created_by"""

    name = gettext_lazy("查询收藏列表")
    model = FavoriteSearch
    filter_fields = ["name", "created_by"]
    action = "list"
    serializer_class = FavoriteSearchSerializer
