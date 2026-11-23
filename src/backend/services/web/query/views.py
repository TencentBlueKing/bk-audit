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

from bk_resource import api, resource
from bk_resource.exceptions import APIRequestError
from bk_resource.viewsets import ResourceRoute, ResourceViewSet
from django.utils.translation import gettext

from api.bk_log.default import EsQuerySearchResource
from services.web.query.mcp_views import reject_body_namespace


class EsQueryViewSet(ResourceViewSet):
    resource_routes = [
        ResourceRoute("GET", resource.query.search, endpoint="search"),
        ResourceRoute("GET", api.bk_log.index_set_operators, endpoint="operators"),
        ResourceRoute("GET", resource.query.field_map, endpoint="field_map"),
    ]

    def handle_exception(self, exc):
        response = super().handle_exception(exc)
        if (
            self.action == "search"
            and isinstance(exc, APIRequestError)
            and exc.data.get("module_name") == EsQuerySearchResource.module_name
            and exc.data.get("url") == EsQuerySearchResource.action
        ):
            # 复用通用异常处理的诊断日志，在渲染前替换所有公开错误字段。
            response.data = {
                "code": response.status_code,
                "message": gettext("日志查询失败。请核对查询条件，或提供请求 ID 联系管理员。"),
                "data": None,
            }
        return response


class CollectorQueryViewSet(ResourceViewSet):
    resource_routes = [
        ResourceRoute(
            "POST",
            resource.query.get_log_field_metadata,
            endpoint="field_metadata",
            decorators=[reject_body_namespace],
        ),
        ResourceRoute("POST", resource.query.collector_search, endpoint="search"),
        ResourceRoute("POST", resource.query.collector_search_statistic, endpoint="search_statistic"),
        ResourceRoute("GET", resource.query.collector_search_config, endpoint="search_config"),
    ]


class CollectorQueryTaskViewSet(ResourceViewSet):
    resource_routes = [
        ResourceRoute("POST", resource.query.create_collector_search_export_task),
        ResourceRoute("GET", resource.query.list_collector_search_export_task, enable_paginate=True),
        ResourceRoute("GET", resource.query.get_collector_search_export_task, pk_field="id"),
        ResourceRoute("GET", resource.query.download_collector_search_export_task, pk_field="id", endpoint="download"),
    ]
