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

from bk_resource import api, resource
from blueapps.utils.request_provider import get_request_username
from django.utils.translation import gettext_lazy

from api.bk_log.constants import INDEX_SET_ID
from apps.audit.resources import AuditMixinResource
from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig, SensitiveObject
from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.permission import Permission
from apps.permission.handlers.resource_types import ResourceEnum
from core.exceptions import PermissionException
from core.permissions import SearchLogPermission
from services.web.databus.constants import DEFAULT_STORAGE_CONFIG_KEY
from services.web.esquery.serializers import (
    EsQueryAttrSerializer,
    EsQuerySearchAttrSerializer,
    EsQuerySearchResponseSerializer,
    FieldMapRequestSerializer,
)
from services.web.esquery.utils.field_map import FieldMapHandler
from services.web.esquery.utils.formatter import HitsFormatter


class EsQueryBaseResource(AuditMixinResource, abc.ABC):
    tags = ["EsQuery"]


class EsQueryResource(EsQueryBaseResource):
    RequestSerializer = EsQueryAttrSerializer

    def perform_request(self, validated_request_data):
        validated_request_data.update(
            {
                "storage_cluster_id": int(
                    validated_request_data.get("storage_cluster_id")
                    or GlobalMetaConfig.get(
                        DEFAULT_STORAGE_CONFIG_KEY,
                        config_level=ConfigLevelChoices.NAMESPACE.value,
                        instance_key=validated_request_data["namespace"],
                    )
                ),
                "index_set_id": (
                    validated_request_data.get("index_set_id")
                    or GlobalMetaConfig.get(
                        INDEX_SET_ID,
                        config_level=ConfigLevelChoices.NAMESPACE.value,
                        instance_key=validated_request_data["namespace"],
                    )
                ),
                "use_time_range": True,
            }
        )
        return api.bk_log.es_query_search(**validated_request_data)


class SearchAllResource(EsQueryBaseResource):
    name = gettext_lazy("搜索(All)")
    RequestSerializer = EsQuerySearchAttrSerializer
    serializer_class = EsQuerySearchResponseSerializer

    def parse_hits(self, hits: list) -> list:
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
        return [HitsFormatter(hit["_source"], [*sensitive_objs, *private_sensitive_objs]).value for hit in hits]

    def perform_request(self, validated_request_data):
        # 调用BK-LOG查询事件
        page = validated_request_data.pop("page")
        num_pages = validated_request_data.pop("page_size")
        resp = resource.esquery.es_query(**validated_request_data)
        total = resp.get("hits", {}).get("total", 0)
        hits = self.parse_hits(resp.get("hits", {}).get("hits", []))
        # 补充系统信息
        if validated_request_data["bind_system_info"]:
            systems = resource.meta.system_list(namespace=validated_request_data["namespace"])
            system_map = {system["system_id"]: system for system in systems}
            for hit in hits:
                hit["system_info"] = system_map.get(hit.get("system_id"), dict())
        # 响应
        return {
            "page": page,
            "num_pages": num_pages,
            "total": total,
            "results": hits,
            "scroll_id": resp.get("_scroll_id"),
        }


class SearchResource(SearchAllResource):
    name = gettext_lazy("搜索")
    RequestSerializer = EsQuerySearchAttrSerializer
    serializer_class = EsQuerySearchResponseSerializer
    audit_action = ActionEnum.SEARCH_REGULAR_EVENT

    def validate_request_data(self, request_data):
        validated_request_data = super().validate_request_data(request_data)

        # 过滤有权限的系统
        systems, authorized_systems = SearchLogPermission.get_auth_systems(validated_request_data["namespace"])
        if not authorized_systems:
            apply_data, apply_url = Permission().get_apply_data([ActionEnum.SEARCH_REGULAR_EVENT])
            raise PermissionException(
                action_name=ActionEnum.SEARCH_REGULAR_EVENT.name,
                apply_url=apply_url,
                permission=apply_data,
            )
        if len(systems) != len(authorized_systems):
            validated_request_data["filter"].append(
                {
                    "field": "system_id",
                    "operator": "is one of",
                    "value": authorized_systems,
                    "condition": "and",
                    "type": "field",
                }
            )
        return validated_request_data


class FieldMapResource(EsQueryBaseResource):
    name = gettext_lazy("字段列表")
    RequestSerializer = FieldMapRequestSerializer

    def perform_request(self, validated_request_data):
        SearchLogPermission.any_search_log_permission(validated_request_data["namespace"])
        return FieldMapHandler(**validated_request_data).field_map
