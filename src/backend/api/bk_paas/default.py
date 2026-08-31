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

import requests
from django.conf import settings
from django.utils.translation import gettext_lazy

from api.constants import APIProvider
from api.domains import BK_PAAS_API_URL
from api.utils import get_endpoint
from core.bk_api_base import AuditBkApiResource


class PaaSV3BaseResource(AuditBkApiResource, abc.ABC):
    bkapi_header_authorization = False
    bkapi_data_authorization = False
    module_name = "paasv3"

    @property
    def base_url(self):
        if self.use_multi_tenant_mode():
            return get_endpoint(settings.BK_PAAS_APIGW_NAME, APIProvider.APIGW, stage="prod")
        return BK_PAAS_API_URL


class UniAppsQuery(PaaSV3BaseResource):
    name = gettext_lazy("查询多平台应用信息")
    action = "/system/uni_applications/query/by_id/"
    method = "GET"
    IS_STANDARD_FORMAT = False

    def parse_response(self, response: requests.Response):
        results = super().parse_response(response)
        return [result for result in results if result]
