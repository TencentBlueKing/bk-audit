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

audit-meta 工具集（系统接入元数据探索）的用户态 APIGW ViewSet。
"""

from collections.abc import Mapping
from functools import wraps

from bk_resource import resource
from bk_resource.viewsets import ResourceRoute
from rest_framework.exceptions import ValidationError

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
from core.utils.spectacular import MCPToolAutoSchema
from core.view_sets import UserAPIGWViewSet


def reject_body_namespace(view_func):
    """在 ResourceViewSet 合并 path 参数前拒绝 body 中的 namespace。"""

    @wraps(view_func)
    def wrapper(view, request, *args, **kwargs):
        if not isinstance(request.data, Mapping):
            raise ValidationError({"body": ["请求体必须为 JSON 对象。"]})
        if "namespace" in request.data:
            raise ValidationError({"namespace": ["只能通过 URL path 提供。"]})
        return view_func(view, request, *args, **kwargs)

    return wrapper


class MCPMetaAutoSchema(MCPToolAutoSchema):
    """为四个对 Agent 稳定暴露的元数据工具固定 OpenAPI operationId。"""

    _OPERATION_IDS = {
        "systems": "mcp_list_audit_systems",
        "system_detail": "mcp_get_audit_system_detail",
        "actions": "mcp_list_system_actions",
        "resource_types": "mcp_list_system_resource_types",
    }
    _PYDANTIC_MODELS = {
        "systems": (ListAuditSystemsRequest, ListAuditSystemsResponse),
        "system_detail": (GetAuditSystemDetailRequest, GetAuditSystemDetailResponse),
        "actions": (ListSystemActionsRequest, ListSystemActionsResponse),
        "resource_types": (ListSystemResourceTypesRequest, ListSystemResourceTypesResponse),
    }
    _ERROR_STATUS_CODES = (400, 403, 413, 502, 504)
    _ERROR_CODE_DESCRIPTION = (
        "audit-meta 工具稳定领域错误码：2927001 目标系统不存在或不可访问，请核对可信当前系统或系统列表中的 system_id；"
        "2927002 元数据查询失败，请稍后重试；"
        "也可能返回 IAM 或平台通用错误码。"
    )


class MCPUserMetaViewSet(UserAPIGWViewSet):
    """Agent 系统接入元数据探索的用户态工具入口，仅暴露四个只读 POST 操作。"""

    schema = MCPMetaAutoSchema()
    resource_routes = [
        ResourceRoute(
            "POST",
            resource.meta.mcp_list_audit_systems,
            endpoint="systems",
            decorators=[reject_body_namespace],
        ),
        ResourceRoute(
            "POST",
            resource.meta.mcp_get_audit_system_detail,
            endpoint="system_detail",
            decorators=[reject_body_namespace],
        ),
        ResourceRoute(
            "POST",
            resource.meta.mcp_list_system_actions,
            endpoint="actions",
            decorators=[reject_body_namespace],
        ),
        ResourceRoute(
            "POST",
            resource.meta.mcp_list_system_resource_types,
            endpoint="resource_types",
            decorators=[reject_body_namespace],
        ),
    ]
