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

from bk_resource import BkApiResource
from bk_resource.exceptions import APIRequestError
from bk_resource.settings import bk_resource_settings
from django.utils.translation import gettext_lazy
from requests.exceptions import HTTPError

from api.bk_iam_v4.constants import FETCH_ALL_SYSTEMS_MAX_PAGE_SIZE
from api.bk_iam_v4.serializers import (
    AddAuthorizationRequestSerializer,
    BatchCreateRoleRequestSerializer,
    DeleteRoleRequestSerializer,
    DirectAuthByActionsRequestSerializer,
    DirectAuthByResourcesRequestSerializer,
    DirectAuthRequestSerializer,
    GeneratePermApplyUrlRequestSerializer,
    ListAuthorizationSubjectRequestSerializer,
    ListAuthorizedResourceRequestSerializer,
    ListSystemRequestSerializer,
    RetrieveSystemRequestSerializer,
    RevokeAuthorizationRequestSerializer,
)
from api.domains import BK_IAM_V4_API_URL


class IAMV4BaseResource(BkApiResource, abc.ABC):
    base_url = BK_IAM_V4_API_URL
    module_name = "bk_iam_v4"

    def parse_response(self, response):
        try:
            result_json = response.json()
        except Exception:
            result_json = None

        try:
            response.raise_for_status()
        except HTTPError as err:
            if isinstance(result_json, dict):
                error = result_json.get("error") or {}
                code = error.get("code") or result_json.get("code")
                message = error.get("message") or result_json.get("message")
                if code or message:
                    raise APIRequestError(
                        module_name=self.module_name,
                        url=self.action,
                        status_code=response.status_code,
                        result={
                            "code": code,
                            "message": message,
                            "request_id": result_json.get("request_id"),
                        },
                    ) from err
            raise

        return super().parse_response(response)

    def build_url(self, validated_request_data):
        url = super().build_url(validated_request_data)
        for key in self.url_keys:
            validated_request_data.pop(key, None)
        return url


class IAMV4OperatorResource(IAMV4BaseResource, abc.ABC):
    operator_field = "operator"

    def build_header(self, validated_request_data: dict) -> dict:
        headers = super().build_header(validated_request_data)
        headers["X-Bkiam-Operator"] = (
            validated_request_data.get(self.operator_field) or bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME
        )
        return headers

    def before_request(self, kwargs: dict) -> dict:
        kwargs = super().before_request(kwargs)
        body = kwargs.get("json")
        if isinstance(body, dict):
            body.pop(self.operator_field, None)
        return kwargs


class IAMV4AuthorizationResource(IAMV4OperatorResource, abc.ABC):
    def before_request(self, kwargs: dict) -> dict:
        kwargs = super().before_request(kwargs)
        body = kwargs.get("json")
        if isinstance(body, dict):
            kwargs["json"] = body["authorizations"]
        return kwargs


class ListSystemResource(IAMV4BaseResource):
    name = gettext_lazy("获取IAM系统列表")
    action = "/api/v1/open/rbac/share/model/systems/"
    method = "GET"
    RequestSerializer = ListSystemRequestSerializer

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
    RequestSerializer = RetrieveSystemRequestSerializer


class DirectAuthResource(IAMV4BaseResource):
    name = gettext_lazy("IAM V4 直接鉴权")
    action = "/api/v1/open/rbac/authorization/systems/{system_id}/auth/"
    method = "POST"
    url_keys = ["system_id"]
    RequestSerializer = DirectAuthRequestSerializer


class DirectAuthByActionsResource(IAMV4BaseResource):
    name = gettext_lazy("IAM V4 批量操作直接鉴权")
    action = "/api/v1/open/rbac/authorization/systems/{system_id}/auth-by-actions/"
    method = "POST"
    url_keys = ["system_id"]
    RequestSerializer = DirectAuthByActionsRequestSerializer


class DirectAuthByResourcesResource(IAMV4BaseResource):
    name = gettext_lazy("IAM V4 批量资源直接鉴权")
    action = "/api/v1/open/rbac/authorization/systems/{system_id}/auth-by-resources/"
    method = "POST"
    url_keys = ["system_id"]
    RequestSerializer = DirectAuthByResourcesRequestSerializer


class ListAuthorizedResourceResource(IAMV4BaseResource):
    name = gettext_lazy("IAM V4 获取有权限的资源实例列表")
    action = "/api/v1/open/rbac/authorization/systems/{system_id}/relation/authorized-resources/"
    method = "POST"
    url_keys = ["system_id"]
    RequestSerializer = ListAuthorizedResourceRequestSerializer


class GeneratePermApplyUrlResource(IAMV4BaseResource):
    name = gettext_lazy("IAM V4 生成权限申请链接")
    action = "/api/v1/open/application/permission-apply-urls/"
    method = "POST"
    RequestSerializer = GeneratePermApplyUrlRequestSerializer


class BatchCreateRoleResource(IAMV4BaseResource):
    name = gettext_lazy("IAM V4 批量创建角色")
    action = "/api/v1/open/rbac/model/systems/{system_id}/roles/"
    method = "POST"
    url_keys = ["system_id"]
    RequestSerializer = BatchCreateRoleRequestSerializer

    def before_request(self, kwargs: dict) -> dict:
        body = kwargs.get("json")
        if isinstance(body, dict):
            kwargs["json"] = body.get("roles", [])
        return kwargs


class DeleteRoleResource(IAMV4BaseResource):
    name = gettext_lazy("IAM V4 删除角色")
    action = "/api/v1/open/rbac/model/systems/{system_id}/roles/{role_id}/"
    method = "DELETE"
    url_keys = ["system_id", "role_id"]
    RequestSerializer = DeleteRoleRequestSerializer

    def parse_response(self, response):
        if response.status_code == 204 and not response.content:
            response.raise_for_status()
            return None
        return super().parse_response(response)


class AddAuthorizationResource(IAMV4AuthorizationResource):
    name = gettext_lazy("IAM V4 角色授权")
    action = "/api/v1/open/rbac/mgmt/systems/{system_id}/authorizations/"
    method = "POST"
    url_keys = ["system_id"]
    RequestSerializer = AddAuthorizationRequestSerializer


class RevokeAuthorizationResource(IAMV4AuthorizationResource):
    name = gettext_lazy("IAM V4 撤销角色授权")
    action = "/api/v1/open/rbac/mgmt/systems/{system_id}/authorizations/"
    method = "DELETE"
    url_keys = ["system_id"]
    RequestSerializer = RevokeAuthorizationRequestSerializer

    def parse_response(self, response):
        if response.status_code == 204 and not response.content:
            response.raise_for_status()
            return None
        return super().parse_response(response)


class ListAuthorizationSubjectResource(IAMV4BaseResource):
    name = gettext_lazy("IAM V4 查询角色授权用户列表")
    action = "/api/v1/open/rbac/mgmt/systems/{system_id}/authorizations/query-subject/"
    method = "POST"
    url_keys = ["system_id"]
    RequestSerializer = ListAuthorizationSubjectRequestSerializer
