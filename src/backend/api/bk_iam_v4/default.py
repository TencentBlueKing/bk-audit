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
import math

from django.utils.translation import gettext_lazy

from api.base import CommonBkApiResource
from api.bk_iam_v4.constants import FETCH_ALL_SYSTEMS_MAX_PAGE_SIZE
from api.domains import BK_IAM_V4_API_URL


class IAMV4BaseResource(CommonBkApiResource, abc.ABC):
    base_url = BK_IAM_V4_API_URL
    module_name = "bk_iam_v4"


class ListSystemResource(IAMV4BaseResource):
    name = gettext_lazy("获取IAM系统列表")
    action = "/api/v1/open/rbac/share/model/systems/"
    method = "GET"

    def fetch_all(self, *args, **kwargs):
        data = self.request({"page": 1, "page_size": 1})
        total = data["count"]
        resp_data = []
        for i in range(0, math.ceil(total / FETCH_ALL_SYSTEMS_MAX_PAGE_SIZE)):
            params = {"page": i + 1, "page_size": FETCH_ALL_SYSTEMS_MAX_PAGE_SIZE}
            data = self.request(params)
            resp_data.extend(data["results"])
        return resp_data


class RetrieveSystemResource(IAMV4BaseResource):
    name = gettext_lazy("获取IAM系统详情")
    action = "/api/v1/open/rabc/share/model/systems/{system_id}/"
    method = "GET"
    url_keys = ["system_id"]
