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
from django.utils.translation import gettext_lazy

from api.base import CommonBkApiResource
from api.domains import BK_IAM_API_URL


class IAMBaseResource(CommonBkApiResource, abc.ABC):
    base_url = BK_IAM_API_URL
    module_name = "iam"


class GetSystems(IAMBaseResource):
    name = gettext_lazy("获取IAM系统列表")
    action = "/api/v1/open/admin/systems"
    method = "GET"


class GetSystemRoles(IAMBaseResource):
    name = gettext_lazy("获取IAM系统角色信息")
    action = "/api/v1/open/admin/roles/system_managers/systems/{system_id}/members/"
    method = "GET"
    url_keys = ["system_id"]

    def perform_request(self, validated_request_data):
        data = super().perform_request(validated_request_data)
        data["id"] = validated_request_data["system_id"]
        return data


class GetSystemInfo(IAMBaseResource):
    name = gettext_lazy("获取IAM系统信息")
    action = "/api/v1/model/share/systems/{system_id}/query"
    method = "GET"
    url_keys = ["system_id"]

    def parse_response(self, response: requests.Response):
        result_json = super().parse_response(response)
        if result_json.get("base_info", {}).get("clients"):
            clients = result_json["base_info"].get("clients") or ""
            result_json["base_info"]["clients"] = [client for client in clients.split(",") if client]
        return result_json
