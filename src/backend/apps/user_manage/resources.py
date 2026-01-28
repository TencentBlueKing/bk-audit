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

from bk_resource import CacheResource, api
from bk_resource.exceptions import APIRequestError
from bk_resource.utils.cache import CacheTypeItem
from django.utils.translation import gettext_lazy


class RetrieveLeader(CacheResource):
    name = gettext_lazy("获取单个用户的leader信息")
    cache_type = CacheTypeItem(key="retrieve_leader", timeout=60 * 60, user_related=False)

    def perform_request(self, validated_request_data):
        try:
            # 获取用户信息&解析出leader信息
            user_info = api.user_manage.retrieve_user({"bk_username": validated_request_data["id"]})
            return user_info.get("leader", [])[0].get("username", "")
        except (IndexError, APIRequestError):
            return ""
