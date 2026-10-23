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
software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.

audit-meta MCP 的 Pydantic/DRF 协议适配。

领域模型 apps.meta.mcp_tools.schemas 是唯一协议事实，
这里仅用 drf-pydantic 生成 Serializer，并为 URL path 的 ``namespace`` 做最薄封装，
不维护平行字段定义。
"""

from collections.abc import Mapping
from copy import copy

from drf_pydantic.config import DrfConfigDict
from drf_pydantic.parse import create_serializer_from_model
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError
from rest_framework import serializers

from apps.meta.mcp_tools.schemas import (
    GetAuditSystemDetailRequest,
    GetAuditSystemDetailResponse,
    ListAuditSystemsRequest,
    ListAuditSystemsResponse,
    ListSystemActionsRequest,
    ListSystemActionsResponse,
    ListSystemResourceTypesRequest,
    ListSystemResourceTypesResponse,
)

_DRF_CONFIG = DrfConfigDict(validate_pydantic=False, backpopulate_after_validation=False)
_RESPONSE_DRF_CONFIG = DrfConfigDict(
    validate_pydantic=True, validation_error="drf", backpopulate_after_validation=False
)


class NamespacePathRequestSerializerMixin(serializers.Serializer):
    """在 DRF 丢弃未知键前校验原始 body，并只承接 Router 注入的 namespace。"""

    PydanticRequestModel: type[BaseModel]
    namespace = serializers.CharField(
        write_only=True,
        help_text="命名空间，仅由 URL path 注入；请求体不应提供该字段。",
    )

    def run_validation(self, data=serializers.empty):
        if data is not serializers.empty and not isinstance(data, Mapping):
            raise serializers.ValidationError({"body": ["请求体必须为 JSON 对象。"]})
        return super().run_validation(data)

    def to_internal_value(self, data):
        payload = copy(data)
        payload.pop("namespace", None)
        try:
            self.PydanticRequestModel.model_validate(payload)
        except PydanticValidationError as err:
            # 请求形状/取值域错误保持普通 400 字段错误；
            # 领域失败（如系统不存在）由服务层抛稳定领域码。
            errors = {}
            for item in err.errors():
                path = ".".join(str(part) for part in item["loc"]) or "body"
                message = "不允许未知字段" if item["type"] == "extra_forbidden" else item["msg"]
                errors.setdefault(path, []).append(message)
            raise serializers.ValidationError(errors) from err
        return super().to_internal_value(data)


class ListAuditSystemsRequestSerializer(
    NamespacePathRequestSerializerMixin,
    create_serializer_from_model(ListAuditSystemsRequest, _DRF_CONFIG),
):
    """系统列表请求的生成 Serializer，加上 URL path namespace。"""

    PydanticRequestModel = ListAuditSystemsRequest


class ListAuditSystemsResponseSerializer(create_serializer_from_model(ListAuditSystemsResponse, _RESPONSE_DRF_CONFIG)):
    """系统列表响应的生成 Serializer。"""


class GetAuditSystemDetailRequestSerializer(
    NamespacePathRequestSerializerMixin,
    create_serializer_from_model(GetAuditSystemDetailRequest, _DRF_CONFIG),
):
    """系统详情请求的生成 Serializer，加上 URL path namespace。"""

    PydanticRequestModel = GetAuditSystemDetailRequest


class GetAuditSystemDetailResponseSerializer(
    create_serializer_from_model(GetAuditSystemDetailResponse, _RESPONSE_DRF_CONFIG)
):
    """系统详情响应的生成 Serializer。"""


class ListSystemActionsRequestSerializer(
    NamespacePathRequestSerializerMixin,
    create_serializer_from_model(ListSystemActionsRequest, _DRF_CONFIG),
):
    """操作列表请求的生成 Serializer，加上 URL path namespace。"""

    PydanticRequestModel = ListSystemActionsRequest


class ListSystemActionsResponseSerializer(
    create_serializer_from_model(ListSystemActionsResponse, _RESPONSE_DRF_CONFIG)
):
    """操作列表响应的生成 Serializer。"""


class ListSystemResourceTypesRequestSerializer(
    NamespacePathRequestSerializerMixin,
    create_serializer_from_model(ListSystemResourceTypesRequest, _DRF_CONFIG),
):
    """资源类型列表请求的生成 Serializer，加上 URL path namespace。"""

    PydanticRequestModel = ListSystemResourceTypesRequest


class ListSystemResourceTypesResponseSerializer(
    create_serializer_from_model(ListSystemResourceTypesResponse, _RESPONSE_DRF_CONFIG)
):
    """资源类型列表响应的生成 Serializer。"""
