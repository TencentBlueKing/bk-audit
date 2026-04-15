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
from bk_resource import BkApiResource
from django.utils.translation import gettext_lazy

from api.domains import BK_IAM_API_URL


class IAMBaseResource(BkApiResource, abc.ABC):
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


class CreateGradeManagerGroups(IAMBaseResource):
    """分级管理员批量创建用户组"""

    name = gettext_lazy("分级管理员批量创建用户组")
    action = "/api/v2/open/management/systems/{system_id}/grade_managers/{id}/groups/"
    method = "POST"
    url_keys = ["system_id", "id"]

    def build_request_data(self, validated_request_data: dict) -> dict:
        """构建请求数据，将 groups 作为请求体"""
        data = {"groups": validated_request_data.pop("groups", [])}
        if "sync_subject_template" in validated_request_data:
            data["sync_subject_template"] = validated_request_data.pop("sync_subject_template")
        return data


class GrantGroupPolicies(IAMBaseResource):
    """用户组授权

    通过管理类API为用户组添加权限，创建用户组后调用此接口为用户组授予对应的操作权限
    """

    name = gettext_lazy("用户组授权")
    action = "/api/v2/open/management/systems/{system_id}/groups/{id}/policies/"
    method = "POST"
    url_keys = ["system_id", "id"]

    def build_request_data(self, validated_request_data: dict) -> dict:
        """构建请求数据，提取 actions 和 resources"""
        return {
            "actions": validated_request_data.pop("actions", []),
            "resources": validated_request_data.pop("resources", []),
        }


class GetGroupMembers(IAMBaseResource):
    name = gettext_lazy("用户组成员列表")
    action = "/api/v2/open/management/systems/{system_id}/groups/{id}/members/"
    method = "GET"
    url_keys = ["system_id", "id"]


class AddGroupMembers(IAMBaseResource):
    """
    添加用户组成员
    """

    name = gettext_lazy("添加用户组成员")
    action = "/api/v2/open/management/systems/{system_id}/groups/{id}/members/"
    method = "POST"
    url_keys = ["system_id", "id"]

    def build_request_data(self, validated_request_data: dict) -> dict:
        """构建请求数据，提取 members 和 expired_at"""
        return {
            "members": validated_request_data.pop("members", []),
            "expired_at": validated_request_data.pop("expired_at", 0),
        }


class DeleteGroupMembers(IAMBaseResource):
    """
    删除用户组成员
    """

    name = gettext_lazy("删除用户组成员")
    action = "/api/v2/open/management/systems/{system_id}/groups/{id}/members/"
    method = "DELETE"
    url_keys = ["system_id", "id"]

    def build_request_data(self, validated_request_data: dict) -> dict:
        """构建请求数据，提取 type 和 ids 作为请求体"""
        return {
            "type": validated_request_data.pop("type", ""),
            "ids": validated_request_data.pop("ids", []),
        }
