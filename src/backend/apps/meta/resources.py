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
from abc import ABC
from collections import defaultdict
from enum import EnumMeta
from functools import cmp_to_key
from itertools import chain
from typing import Set

import django_filters as df
import openpyxl
import requests
from bk_resource import CacheResource, Resource, api, resource
from bk_resource.contrib.model import ModelResource
from blueapps.utils.logger import logger
from django.conf import settings
from django.core.cache import cache as default_cache
from django.db import transaction
from django.db.models import Exists, OuterRef, Q, QuerySet
from django.db.models.enums import ChoicesMeta
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext, gettext_lazy
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers
from rest_framework.response import Response

from apps.audit.resources import AuditMixinResource
from apps.meta import models
from apps.meta.comopents import DBEnumMappingAdapter
from apps.meta.constants import (
    FETCH_INSTANCE_SCHEMA_CACHE_TIMEOUT,
    FETCH_INSTANCE_SCHEMA_METHOD,
    GET_APP_INFO_CACHE_TIMEOUT,
    IAM_MANAGER_ROLE,
    SpaceType,
    SystemAuditStatusEnum,
)
from apps.meta.exceptions import (
    ActionHasExist,
    BKAppNotExists,
    EnumMappingRelationInvalid,
    SystemHasExist,
)
from apps.meta.handlers.system_diagnosis import SystemDiagnosisPushHandler
from apps.meta.models import (
    Action,
    CustomField,
    DataMap,
    EnumMappingCollectionRelation,
    Field,
    GeneralConfig,
    GlobalMetaConfig,
    ResourceType,
    ResourceTypeActionRelation,
    ResourceTypeTreeNode,
    SensitiveObject,
    System,
    SystemFavorite,
    SystemInstance,
    Tag,
)
from apps.meta.permissions import SearchLogPermission, SystemPermissionHandler
from apps.meta.serializers import (
    ActionCreateSerializer,
    ActionListReqSerializer,
    ActionSerializer,
    ActionUpdateSerializer,
    BatchUpdateEnumMappingSerializer,
    BulkActionCreateSerializer,
    BulkCreateResourceTypeSerializer,
    ChangeSystemDiagnosisPushReqSerializer,
    ChangeSystemDiagnosisPushRespSerializer,
    CreateSystemReqSerializer,
    DeleteGeneralConfigReqSerializer,
    DeleteResourceTypeRequestSerializer,
    DeleteSystemDiagnosisPushReqSerializer,
    EnumMappingByCollectionKeysSerializer,
    EnumMappingByCollectionSerializer,
    EnumMappingRelation,
    EnumMappingSerializer,
    FieldListRequestSerializer,
    FieldListSerializer,
    GeneralConfigSerializer,
    GetAppInfoRequestSerializer,
    GetAppInfoResponseSerializer,
    GetAssetPullInfoRequestSerializer,
    GetCustomFieldsRequestSerializer,
    GetGlobalsResponseSerializer,
    GetResourceTypeRequestSerializer,
    GetResourceTypeSchemaRequestSerializer,
    GetSensitiveObjRequestSerializer,
    GetSensitiveObjResponseSerializer,
    GetSpacesMineResponseSerializer,
    GlobalMetaConfigInfoSerializer,
    GlobalMetaConfigListSerializer,
    GlobalMetaConfigPostSerializer,
    ListAllTagsRespSerializer,
    ListGeneralConfigReqSerializer,
    ListResourceTypeSerializer,
    NamespaceSerializer,
    ResourceTypeListSerializer,
    ResourceTypeSerializer,
    ResourceTypeTreeReqSerializer,
    ResourceTypeTreeSerializer,
    SaveTagResponseSerializer,
    SaveTagsRequestSerializer,
    SystemFavoriteReqSerializer,
    SystemInfoResponseSerializer,
    SystemListAllRequestSerializer,
    SystemListAllResponseSerializer,
    SystemListRequestSerializer,
    SystemListSerializer,
    SystemRoleListRequestSerializer,
    SystemRoleSerializer,
    SystemSearchBaseSerialzier,
    SystemSerializer,
    UpdateCustomFieldResponseSerializer,
    UpdateGeneralConfigSerializer,
    UpdateResourceTypeSerializer,
    UpdateSystemReqSerializer,
    UploadDataMapFileRequestSerializer,
    UploadDataMapFileResponseSerializer,
)
from apps.meta.utils.globals import Globals
from apps.meta.utils.system import (
    PermissionSorter,
    get_system_sort_key,
    is_system_manager_func,
    wrapper_system_status,
)
from apps.permission.handlers.actions import ActionEnum, get_action_by_id
from apps.permission.handlers.drf import wrapper_permission_field
from apps.permission.handlers.resource_types import ResourceEnum
from core.choices import list_registered_choices
from core.constants import OrderTypeChoices
from core.models import get_request_username
from core.utils.cache import CacheMixin
from core.utils.tools import get_app_info


class Meta:
    tags = ["Meta"]


class NamespaceListResource(Meta, ModelResource):
    name = gettext_lazy("获取 Namespace 列表")
    model = models.Namespace
    serializer_class = NamespaceSerializer
    action = "list"
    many_response_data = True


class SystemAuditMixinResource(AuditMixinResource, abc.ABC):
    audit_resource_type = ResourceEnum.SYSTEM


class SystemAbstractResource(Meta, SystemAuditMixinResource, ModelResource, ABC):
    model = models.System
    serializer_class = SystemSerializer


class SystemListResource(SystemAbstractResource, CacheResource):
    """
    获取系统列表
    1. 获取已接入审计中心的系统列表:
    ```json
    ?audit_status=accessed&order_field=created_at&order_type=desc
    ```
    """

    name = gettext_lazy("获取系统列表")
    action = "list"
    many_response_data = True
    RequestSerializer = SystemListRequestSerializer
    audit_action = ActionEnum.LIST_SYSTEM
    serializer_class = SystemListSerializer

    def sort(self, systems: list, validated_request_data: dict):
        sort_keys = validated_request_data.get("sort", [])
        if not sort_keys:
            return systems

        def _sort(system0: dict, system1: dict):
            result = 0
            for key in sort_keys:
                reverse = key.startswith("-")
                key = key[1:] if reverse else key
                if system0[key] < system1[key]:
                    result = -1
                elif system0[key] == system1[key]:
                    result = 0
                elif system0[key] > system1[key]:
                    result = 1
                if reverse:
                    result = -result
                if result != 0:
                    break
            return result

        systems.sort(key=cmp_to_key(_sort))
        return systems

    def filter(self, systems: list, filter_map: dict):
        _systems = []
        for system in systems:
            flag = True
            for key, val in filter_map.items():
                if system.get(key) not in val:
                    flag = False
                    break
            if flag:
                _systems.append(system)
        return _systems

    def perform_request(self, validated_request_data: dict) -> any:
        # 添加聚合注释
        queryset = System.objects.with_action_resource_type_count()
        if validated_request_data.get("keyword"):
            keyword = validated_request_data["keyword"]
            queryset = queryset.filter(
                Q(Q(name__icontains=keyword) | Q(name_en__icontains=keyword) | Q(system_id__icontains=keyword))
            )
        if validated_request_data.get("source_type"):
            queryset = queryset.filter(source_type__in=validated_request_data["source_type"])
        if validated_request_data.get("audit_status"):
            queryset = queryset.filter(audit_status__in=validated_request_data["audit_status"])
        systems = self.serializer_class(queryset, many=self.many_response_data).data
        all_managers = resource.meta.system_role_list(role=IAM_MANAGER_ROLE)
        system_manager_map = defaultdict(list)
        for manager in all_managers:
            system_manager_map[manager["system_id"]].append(manager["username"])
        for system in systems:
            system["managers"] = system["managers"] or system_manager_map[system["system_id"]]

        system_managers = {system["system_id"]: system["managers"] for system in systems}
        username = get_request_username()
        actions = [ActionEnum.VIEW_SYSTEM, ActionEnum.EDIT_SYSTEM]
        systems = wrapper_permission_field(
            systems,
            actions,
            id_field=lambda x: x["system_id"],
            always_allowed=lambda sys, action_id: username in system_managers.get(sys["system_id"]),
        )
        systems.sort(key=PermissionSorter.sort_key)
        if not systems:
            return systems

        # 绑定系统状态
        systems = wrapper_system_status(namespace=validated_request_data["namespace"], systems=systems)

        # 数据过滤
        if validated_request_data.get("status"):
            systems = self.filter(systems, {"status": validated_request_data["status"]})
        if validated_request_data.get("system_status"):
            systems = self.filter(systems, {"system_status": validated_request_data["system_status"]})
        return self.sort(systems, validated_request_data)


class SystemListAllResource(SystemAbstractResource, CacheResource):
    """
    获取系统列表(All)
    1. 待接入的系统
    ```json
    输入：?sort_keys=audit_status,name
    输出：
    {
        "data": [
            {
                "id": "xxx",
                "name": "xxx",
                "source_type": "iam_v3",
                "audit_status": "accessed",
                "system_id": "xxx"
            }
        ]
    }
    ```
    2. 系统列表(快速切换)
    ```json
    输入：?action_ids=view_system&audit_status__in=accessed&with_favorite=true&with_system_status=true&sort_keys=favorite,permission,name'
    输出：
    {
        "data": [
            {
              "id": "xxx",
              "name": "xxx",
              "source_type": "bk_audit",
              "audit_status": "accessed",
              "favorite": true,
              "system_id": "xxx",
              "last_time": "",
              "status": "unset",
              "status_msg": "未配置",
              "system_status": "incomplete",
              "permission": {
                "view_system": true
              }
            }
        ]
    }
    """

    name = gettext_lazy("获取系统列表(All)")
    action = "list"
    many_response_data = True
    filter_fields = {"namespace": ["exact"], "audit_status": ["in"], "source_type": ["in"], "permission_type": ["in"]}
    filter_backends = [DjangoFilterBackend]
    RequestSerializer = SystemListAllRequestSerializer
    serializer_class = SystemListAllResponseSerializer
    audit_action = ActionEnum.LIST_SYSTEM

    def validate_request_data(self, request_data):
        self.validated_data = super().validate_request_data(request_data)
        return self.validated_data

    def build_favorite_queryset(self, queryset: QuerySet[System]) -> QuerySet[System]:
        # 构造收藏状态的子查询
        username = get_request_username()
        # 构造收藏状态的Exists表达式
        favorite_exists = SystemFavorite.objects.filter(
            system_id=OuterRef('system_id'), username=username, favorite=True
        )
        # 构造主查询集
        queryset = queryset.annotate(
            favorite=Exists(favorite_exists),
        ).order_by('-favorite', 'name')
        return queryset

    @property
    def queryset(self):
        qs = super().queryset
        if self.validated_data.get("with_favorite"):
            qs = self.build_favorite_queryset(qs)
        return qs

    def perform_request(self, validated_request_data: dict) -> any:
        systems = super().perform_request(validated_request_data)
        # 绑定系统状态
        namespace = validated_request_data["namespace"]

        if validated_request_data.get("with_system_status"):
            wrapper_system_status(namespace, systems)

        if validated_request_data.get("action_ids"):
            username = get_request_username()
            system_ids = [system["system_id"] for system in systems]
            is_system_manager = is_system_manager_func(system_ids, username)
            actions = [get_action_by_id(action) for action in validated_request_data["action_ids"]]
            systems = wrapper_permission_field(
                systems, actions, always_allowed=lambda sys, action_id: is_system_manager(sys["system_id"])
            )

        # 排序
        sort_keys = validated_request_data.get("sort_keys", [])
        order_type = validated_request_data["order_type"]
        systems.sort(key=get_system_sort_key(sort_keys), reverse=order_type == OrderTypeChoices.DESC.value)
        return systems


class SystemInfoResource(SystemAbstractResource):
    name = gettext_lazy("获取系统详情")
    lookup_field = "system_id"
    serializer_class = SystemInfoResponseSerializer
    action = "retrieve"
    audit_action = ActionEnum.VIEW_SYSTEM

    @property
    def queryset(self):
        return System.objects.with_action_resource_type_count()

    def perform_request(self, validated_request_data: dict) -> any:
        system_info = super().perform_request(validated_request_data)
        self.add_audit_instance_to_context(instance=SystemInstance(system_info).instance)
        return system_info


class SystemAttrAbstractResource(Meta, ModelResource, ABC):
    action = "list"
    filter_fields = ["system_id"]
    many_response_data = True


class ResourceTypeFilter(df.FilterSet):
    # ────────────── 直接字段 ──────────────
    system_id = df.CharFilter(lookup_expr="exact")
    resource_type_id = df.CharFilter(lookup_expr="icontains")  # 模糊
    name = df.CharFilter(lookup_expr="icontains")  # 模糊
    name_en = df.CharFilter(lookup_expr="icontains")  # 模糊
    sensitivity = df.NumberFilter()  # 精确匹配 (也可以用 RangeFilter)

    # ────────────── 自定义：按 action_id 筛 ──────────────
    actions = df.CharFilter(method="filter_by_actions")

    # 约定 URL 传参: actions=edit,delete,view

    class Meta:
        model = ResourceType
        fields = ["resource_type_id", "name", "name_en", "sensitivity", "actions"]

    # ---------------- 核心逻辑 ----------------
    def filter_by_actions(self, queryset, name, value):
        """
        只保留『包含任意一个给定 action_id』的资源类型：
        ?actions=edit,delete
        """
        action_ids = [v.strip() for v in value.split(",") if v.strip()]
        if not action_ids:
            return queryset

        rel_qs = ResourceTypeActionRelation.objects.filter(
            system_id=OuterRef("system_id"),
            resource_type_id=OuterRef("resource_type_id"),
            action_id__in=action_ids,
        )
        return queryset.filter(Exists(rel_qs))


class ResourceTypeListResource(SystemAttrAbstractResource):
    name = gettext_lazy("资源类型列表")
    model = models.ResourceType
    serializer_class = ResourceTypeSerializer
    RequestSerializer = ResourceTypeListSerializer
    view_set_attrs = {"filterset_class": ResourceTypeFilter}

    def list(self, params: dict) -> list:
        request, view_set = self.build_request_and_view_set(method="GET", params=params)
        return self.list_in_view(view_set, request, params).data

    @staticmethod
    def list_in_view(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            resource_types_page = page
        else:
            resource_types_page = queryset

        system_ids = {rt.system_id for rt in resource_types_page}
        resource_type_ids_set = {rt.resource_type_id for rt in resource_types_page}
        all_related_actions = Action.objects.filter(system_id__in=system_ids)
        resource_type_id_map = Action.get_resource_type_id_map(list(system_ids))
        actions_lookup = defaultdict(list)
        for action in all_related_actions:
            for rt_id in resource_type_id_map.get(action.system_id, {}).get(action.action_id, []):
                if rt_id in resource_type_ids_set:
                    key = (action.system_id, rt_id)
                    actions_lookup[key].append(action)

        serializer_context = {
            'request': request,
            'actions_lookup': actions_lookup,
        }
        serializer = self.get_serializer(resource_types_page, many=True, context=serializer_context)

        # 返回分页或普通列表响应
        if page is not None:
            return self.get_paginated_response(serializer.data)

        return Response(serializer.data)


class ListResourceType(Meta, ModelResource):
    action = "list"
    name = gettext_lazy("查询资源类型")
    model = ResourceType
    serializer_class = ResourceTypeSerializer
    filter_fields = ["system_id", "name", "name_en"]
    RequestSerializer = ListResourceTypeSerializer
    many_response_data = True


class GetResourceTypeTree(Meta, Resource):
    """获取完整的资源类型树,
    每个节点都包含其基本信息和 `children` 字段，`children` 字段是一个包含其所有直接子节点的数组。
    如果一个节点没有子节点，其 `children` 数组为空 `[]`。

    ```json
    [
      {
        "system_id": "iam",
        "resource_type_id": "system",
        "unique_id": "iam:system",
        "name": "权限中心",
        "name_en": "IAM",
        "description": "蓝鲸权限中心系统",
        "children": [
          {
            "system_id": "iam",
            "resource_type_id": "user",
            "unique_id": "iam:user",
            "name": "用户",
            "name_en": "User",
            "description": "权限中心的用户资源",
            "children": []
          }
        ]
      }
    ]
    """

    name = gettext_lazy("获取完整的资源类型树")
    serializer_class = ResourceTypeTreeSerializer
    ResponseSerializer = ResourceTypeTreeSerializer
    RequestSerializer = ResourceTypeTreeReqSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        root_nodes = (
            ResourceTypeTreeNode.get_root_nodes()
            .select_related('related')
            .filter(related__system_id=validated_request_data['system_id'])
        )
        resource_type_ids_qs = root_nodes.values_list('related_id', flat=True)
        return ResourceType.objects.filter(pk__in=resource_type_ids_qs)


class GetResourceType(Meta, ModelResource):
    """获取资源类型，unique_id为'{系统ID}:{资源类型ID}'"""

    action = "retrieve"
    name = gettext_lazy("获取资源类型")
    model = ResourceType
    serializer_class = ResourceTypeSerializer
    RequestSerializer = GetResourceTypeRequestSerializer
    lookup_field = "unique_id"


class CreateResourceType(Meta, ModelResource):
    """新增资源类型ResourceType，参数样例：

    ```json
    {
      "system_id": "bk_paas",
      "resource_type_id": "app",
      "unique_id": "bk_paas:app",
      "name": "应用",
      "name_en": "Application",
      "sensitivity": 1,
      "provider_config": {"url": "/api/v1/iam/resources/"},
      "path": "/api/v1/iam/resources/",
      "version": 1,
      "description": "蓝鲸PaaS平台的应用资源类型",
      "ancestor": ["parent_app"]
    }
    ```
    """

    action = "create"
    name = gettext_lazy("新建资源类型")
    model = ResourceType
    serializer_class = ResourceTypeSerializer
    RequestSerializer = ResourceTypeSerializer
    ResponseSerializer = ResourceTypeSerializer
    lookup_field = "unique_id"

    def perform_request(self, validated_request_data):
        actions = validated_request_data.pop("actions_to_create", [])
        with transaction.atomic():
            resource_type = ResourceType.objects.create(**validated_request_data)
            for action in actions:
                resource.meta.create_action(action)
        return ResourceType.objects.get(pk=resource_type.pk)


class BulkCreateResourceType(Meta, Resource):
    """批量创建资源类型, 传入的参数为{"resource_types": [{$ResourceType},{$ResourceType}]}, 单个ResourceType样例详见新建资源类型接口"""

    name = gettext_lazy("批量创建资源类型")
    serializer_class = ResourceTypeSerializer
    RequestSerializer = BulkCreateResourceTypeSerializer
    ResponseSerializer = ResourceTypeSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        resource_types = []
        actions_map = []
        for rt_data in validated_request_data["resource_types"]:
            actions = rt_data.pop("actions_to_create", [])
            rt = ResourceType(**rt_data)
            resource_types.append(rt)
            actions_map.append(actions)
        system_ids = {rt.system_id for rt in resource_types}
        for p in chain.from_iterable(
            SystemPermissionHandler.system_edit_permissions(lambda: system_id) for system_id in system_ids
        ):
            p.has_permission(None, None)
        with transaction.atomic():
            for rt, acts in zip(resource_types, actions_map):
                rt.save()
                for action in acts:
                    resource.meta.create_action(action)
        return ResourceType.objects.filter(pk__in=[rt.pk for rt in resource_types])


class UpdateResourceType(Meta, ModelResource):
    """更新资源类型"""

    action = "update"
    name = gettext_lazy("更新资源类型")
    model = ResourceType
    serializer_class = ResourceTypeSerializer
    RequestSerializer = UpdateResourceTypeSerializer
    lookup_field = "unique_id"


class DeleteResourceType(Meta, ModelResource):
    """删除资源类型，unique_id为'{系统ID}:{资源类型ID}'"""

    action = "destroy"
    name = gettext_lazy("删除资源类型")
    model = ResourceType
    serializer_class = DeleteResourceTypeRequestSerializer
    RequestSerializer = DeleteResourceTypeRequestSerializer
    lookup_field = "unique_id"


class ActionListResource(SystemAttrAbstractResource):
    """
    操作列表
    1. 获取指定系统下的操作列表
    ```json
    返回:
    {
        "data": [
            {
                "action_id": "xxx",
                "name": "xxx",
                "name_en": "xxx",
                "sensitivity": 0,
                "type": null,
                "version": 0,
                "description": null,
                "unique_id": "xxx",
                "resource_type_ids": [
                    "xxx1"
                ]
            }
        ]
    }
    ```
    """

    name = gettext_lazy("操作列表")
    model = models.Action
    RequestSerializer = ActionListReqSerializer
    serializer_class = ActionSerializer
    filter_fields = {
        "system_id": ["exact"],
        "action_id": ["exact"],
        "sensitivity": ["exact"],
        "name": ["icontains"],
        "name_en": ["icontains"],
        "type": ["exact"],
    }
    filter_backends = [DjangoFilterBackend]

    def perform_request(self, validated_request_data: dict) -> any:
        data = super().perform_request(validated_request_data)
        resource_type_ids: Set[str] = set(validated_request_data.get("resource_type_ids", []))
        system_id: str = validated_request_data["system_id"]
        resource_type_id_map = Action.get_resource_type_id_map([system_id])
        for action in data:
            action["resource_type_ids"] = resource_type_id_map.get(system_id, {}).get(action["action_id"], [])
        # 根据 resource_type_ids 过滤
        if resource_type_ids:
            data = [action for action in data if set(action["resource_type_ids"]) & resource_type_ids]
        return data


class SystemFilter(Meta, Resource, ABC):
    model = None
    instance_id_field = None
    instance_name_field = None
    RequestSerializer = SystemSearchBaseSerialzier

    def perform_request(self, validated_request_data):
        authorized_systems = SearchLogPermission.get_auth_systems(validated_request_data["namespace"])[1]
        if not validated_request_data.get("system_ids"):
            validated_request_data["system_ids"] = authorized_systems
        else:
            validated_request_data["system_ids"] = [
                system_id for system_id in validated_request_data["system_ids"] if system_id in authorized_systems
            ]
        query_params = {"system_id__in": validated_request_data["system_ids"]}
        instances = self.model.objects.filter(**query_params).order_by(self.instance_id_field)
        data = defaultdict(set)
        for instance in instances:
            instance_id = getattr(instance, self.instance_id_field)
            instance_name = getattr(instance, self.instance_name_field)
            data[instance_id].add(instance_name)
        return [
            {"id": instance_id, "name": f"{','.join(names)} ({instance_id})"} for instance_id, names in data.items()
        ]


class ResourceTypeSearchList(SystemFilter):
    name = gettext_lazy("资源类型列表(搜索)")
    model = ResourceType
    instance_id_field = "resource_type_id"
    instance_name_field = "name"


class ActionSearchList(SystemFilter):
    name = gettext_lazy("操作列表(搜索)")
    model = Action
    instance_id_field = "action_id"
    instance_name_field = "name"


class SystemRoleListResource(SystemAttrAbstractResource):
    name = gettext_lazy("系统成员列表")
    model = models.SystemRole
    filter_fields = ["system_id", "role"]
    serializer_class = SystemRoleSerializer
    RequestSerializer = SystemRoleListRequestSerializer


class GetGlobalsResource(Meta, Resource):
    name = gettext_lazy("获取全局配置")
    serializer_class = GetGlobalsResponseSerializer

    def perform_request(self, validated_request_data):
        return Globals().globals


class GetStandardFieldsResource(Meta, ModelResource):
    name = gettext_lazy("获取标准字段")
    model = Field
    action = "list"
    many_response_data = True
    RequestSerializer = FieldListRequestSerializer
    serializer_class = FieldListSerializer

    def perform_request(self, validated_request_data: dict) -> any:
        fields = super().perform_request(validated_request_data)
        for field in fields:
            field["description"] = gettext(field["description"])
        if validated_request_data.get("is_etl"):
            return [field for field in fields if field["is_display"]]
        return fields


class GetCustomFieldsResource(Meta, Resource):
    name = gettext_lazy("获取用户字段")
    RequestSerializer = GetCustomFieldsRequestSerializer

    def perform_request(self, validated_request_data):
        username = get_request_username()
        route_path = validated_request_data["route_path"]
        try:
            return CustomField.objects.get(username=username, route_path=route_path).fields
        except CustomField.DoesNotExist:
            return None


class UpdateCustomFieldsResource(Meta, Resource):
    name = gettext_lazy("更新用户字段")
    RequestSerializer = UpdateCustomFieldResponseSerializer

    def perform_request(self, validated_request_data):
        username = get_request_username()
        route_path = validated_request_data["route_path"]
        fields = validated_request_data["fields"]
        custom_field, _ = CustomField.objects.get_or_create(username=username, route_path=route_path)
        custom_field.fields = fields
        custom_field.save()


class GetAppInfoResource(Meta, CacheMixin, Resource):
    name = gettext_lazy("获取多平台应用信息")
    RequestSerializer = GetAppInfoRequestSerializer
    ResponseSerializer = GetAppInfoResponseSerializer
    cache = default_cache

    def generate_cache_key(self, app_code: str) -> str:
        return f"resource:{self.__class__.__name__}:{app_code}"

    def perform_request(self, validated_request_data):
        SearchLogPermission.any_search_log_permission(validated_request_data["namespace"])
        # 获取缓存
        cache_data = self.get_cache({"app_code": validated_request_data["app_code"]})
        if cache_data is not None:
            return cache_data
        # 获取应用信息
        app_code = validated_request_data["app_code"]
        data = {
            "app_code": app_code,
            "app_name": str(),
            "developers": list(),
            "status": False,
            "status_msg": gettext("未找到"),
            "system_url": str(),
        }

        params = {"id": app_code, "include_deploy_info": 1, "include_market_info": "true"}
        resp = api.bk_paas.uni_apps_query(params)

        if not resp:
            raise BKAppNotExists()

        app_info = resp[0]
        data.update({"app_name": app_info["name"], "developers": app_info["developers"]})

        deploy_info = app_info["deploy_info"] or dict()
        market_addres = app_info.get("market_addres") or dict()
        deploy_url = (
            deploy_info.get("prod", {}).get("url")
            or deploy_info.get("stag", {}).get("url")
            or market_addres.get("market_address")
        )
        if not deploy_url:
            deploy_url = ""
        data.update(
            {"status": True, "system_url": deploy_url, "status_msg": gettext("正常") if deploy_url else gettext("未部署")}
        )
        self.set_cache({"app_code": validated_request_data["app_code"]}, data, GET_APP_INFO_CACHE_TIMEOUT)
        return data


class ResourceTypeSchema(Meta, CacheMixin, Resource):
    name = gettext_lazy("获取资源类型结构")
    RequestSerializer = GetResourceTypeSchemaRequestSerializer
    serializer_class = serializers.JSONField
    cache = default_cache

    def generate_cache_key(self, system: System, resource_type: ResourceType) -> str:
        return f"resource:{self.__class__.__name__}:{system.system_id}:{resource_type.resource_type_id}"

    def get_schema(self, system: System, resource_type: ResourceType) -> list:
        # 获取缓存
        cache_data = self.get_cache({"system": system, "resource_type": resource_type})
        if cache_data is not None:
            return cache_data
        #  拼接请求参数
        request_url = resource_type.resource_request_url(system)
        request_body = {"type": resource_type.resource_type_id, "method": FETCH_INSTANCE_SCHEMA_METHOD}
        request_header = {"Authorization": system.base64_token}
        # 请求数据
        web = requests.session()
        try:
            resp = web.post(url=request_url, json=request_body, headers=request_header).json()
            logger.info("[Get ResourceType Schema Success] Response => %s", resp)
            data = resp["data"]["properties"]
        except Exception as err:  # NOCC:broad-except(需要处理所有错误)
            logger.exception(
                "[Get ResourceType Schema Failed] "
                "RequestURL => %s; "
                "RequestHeader => %s; "
                "RequestBody => %s; "
                "Err => %s",
                request_url,
                request_header,
                request_body,
                err,
            )
            return []
        response_data = [
            {
                "id": key,
                "type": val.get("type"),
                "description_en": val.get("description_en") or val.get("description"),
                "description": val.get("description"),
                "is_index": val.get("is_index", False),
            }
            for key, val in data.items()
        ]
        self.set_cache(
            {"system": system, "resource_type": resource_type}, response_data, FETCH_INSTANCE_SCHEMA_CACHE_TIMEOUT
        )
        return response_data

    def perform_request(self, validated_request_data):
        if not validated_request_data.get("system_id") or not validated_request_data.get("resource_type_id"):
            return []
        system = System.objects.get(system_id=validated_request_data["system_id"])
        try:
            resource_type = ResourceType.objects.get(
                system_id=system.system_id, resource_type_id=validated_request_data["resource_type_id"]
            )
        except ResourceType.DoesNotExist:
            return []
        return self.get_schema(system, resource_type)


class GetGlobalMetaConfigsResource(Meta, ModelResource):
    name = gettext_lazy("获取本地全局配置")
    action = "list"
    model = GlobalMetaConfig
    serializer_class = GlobalMetaConfigListSerializer


class GetGlobalMetaConfigInfoResource(Meta, Resource):
    name = gettext_lazy("获取本地全局配置详情")
    model = GlobalMetaConfig
    RequestSerializer = GlobalMetaConfigInfoSerializer
    ResponseSerializer = GlobalMetaConfigListSerializer

    def perform_request(self, validated_request_data):
        return GlobalMetaConfig.objects.get(**validated_request_data)


class SetGlobalMetaConfigResource(Meta, Resource):
    name = gettext_lazy("设置本地全局配置")
    RequestSerializer = GlobalMetaConfigPostSerializer
    ResponseSerializer = GlobalMetaConfigListSerializer

    def perform_request(self, validated_request_data):
        return GlobalMetaConfig.set(**validated_request_data)


class GetSpacesMineResource(Resource):
    name = gettext_lazy("获取空间列表")
    tags = ["Space"]
    many_response_data = True
    ResponseSerializer = GetSpacesMineResponseSerializer

    def perform_request(self, validated_request_data):
        # V2版本 空间
        if settings.BKLOG_PERMISSION_VERSION == "2":
            return api.bk_log.get_spaces_mine()
        # V1版本 业务列表
        data = api.bk_log.bizs_list()
        for biz in data:
            biz.update({"space_type_id": SpaceType.BIZ.value, "space_type_name": str(SpaceType.BIZ.label)})
        return data


class GetSensitiveObj(Meta, Resource):
    name = gettext_lazy("获取敏感对象")
    RequestSerializer = GetSensitiveObjRequestSerializer
    ResponseSerializer = GetSensitiveObjResponseSerializer

    def perform_request(self, validated_request_data):
        return get_object_or_404(
            SensitiveObject,
            system_id=validated_request_data["system_id"],
            resource_type=validated_request_data["resource_type"],
            resource_id=validated_request_data["resource_id"],
        )


class UploadDataMapFile(Meta, Resource):
    name = gettext_lazy("上传数据字典文件")
    RequestSerializer = UploadDataMapFileRequestSerializer
    ResponseSerializer = UploadDataMapFileResponseSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        # 读取文件
        file = validated_request_data["file"]
        data = openpyxl.load_workbook(file)
        # 校验数据
        if not data.worksheets:
            raise serializers.ValidationError(gettext("数据表格不存在，请检查"))
        # 读取表格
        sheet = data.worksheets[0]
        # 更新数据
        keys = set()
        data_maps = []
        for index, line in enumerate(sheet.values):
            if index == 0:
                continue
            if len(line) != 3:
                raise serializers.ValidationError(gettext("字段不匹配，请按照模板文件配置"))
            keys.add(line[0])
            data_field, data_key, data_alias = line
            data_maps.append(DataMap(data_field=data_field, data_key=data_key, data_alias=data_alias))
        with transaction.atomic():
            DataMap.objects.filter(data_field__in=keys).delete()
            DataMap.objects.bulk_create(data_maps)
        return DataMap.objects.filter(data_field__in=keys)


class SaveTags(Meta, Resource):
    name = gettext_lazy("Save Tags")
    RequestSerializer = SaveTagsRequestSerializer
    ResponseSerializer = SaveTagResponseSerializer
    many_request_data = True
    many_response_data = True

    def perform_request(self, validated_request_data):
        tag_names = [t["tag_name"] for t in validated_request_data]
        Tag.objects.bulk_create([Tag(tag_name=t) for t in tag_names], ignore_conflicts=True)
        tags = Tag.objects.filter(tag_name__in=tag_names)
        return tags


class GetAssetPullInfo(Meta, Resource):
    name = gettext_lazy("获取资源拉取信息")
    RequestSerializer = GetAssetPullInfoRequestSerializer

    def perform_request(self, validated_request_data):
        # 检查身份
        get_app_info()
        # 获取系统
        system_id = validated_request_data["system_id"]
        system = System.objects.get(system_id=system_id)
        # 获取资源类型
        resource_type_id = validated_request_data["resource_type_id"]
        resource_type = ResourceType.objects.get(system_id=system_id, resource_type_id=resource_type_id)
        # 响应
        return {
            "system_id": system.system_id,
            "system_name": system.name,
            "resource_type_id": resource_type.resource_type_id,
            "resource_type_name": resource_type.name,
            "url": resource_type.resource_request_url(system),
            "token": system.base64_token,
        }


class ListAllTags(Meta, Resource):
    name = gettext_lazy("获取所有标签")
    ResponseSerializer = ListAllTagsRespSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        return Tag.objects.all()


class GetGlobalChoices(Meta, Resource):
    name = gettext_lazy("获取全局枚举值配置")

    @property
    def globals(self) -> dict:
        """获得所有注册的配置 ."""
        # 获得注册的下拉配置
        choices_dict = {}
        for name, choices_enum in list_registered_choices().items():
            if isinstance(choices_enum, ChoicesMeta):
                choices_dict[name] = [{"id": value, "name": label} for value, label in choices_enum.choices]
            elif isinstance(choices_enum, EnumMeta):
                choices_dict[name] = [
                    {"id": name, "name": member.value} for name, member in choices_enum.__members__.items()
                ]
        return choices_dict

    def perform_request(self, validated_request_data):
        return self.globals


class ChangeSystemDiagnosisPush(Meta, Resource):
    name = gettext_lazy("切换系统诊断推送")
    RequestSerializer = ChangeSystemDiagnosisPushReqSerializer
    ResponseSerializer = ChangeSystemDiagnosisPushRespSerializer

    def perform_request(self, validated_request_data):
        system_id = validated_request_data["system_id"]
        enable = validated_request_data["enable"]
        success = SystemDiagnosisPushHandler(system_id=system_id).change_push_status(enable_push=enable)
        return {
            "success": success,
        }


class DeleteSystemDiagnosisPush(Meta, Resource):
    name = gettext_lazy("删除系统诊断推送")
    RequestSerializer = DeleteSystemDiagnosisPushReqSerializer

    def perform_request(self, validated_request_data):
        system_id = validated_request_data["system_id"]
        SystemDiagnosisPushHandler(system_id=system_id).delete_push()


class CreateGeneralConfigResource(Meta, ModelResource):
    name = gettext_lazy("创建通用配置")
    lookup_field = "id"
    model = GeneralConfig
    action = "create"
    serializer_class = GeneralConfigSerializer
    RequestSerializer = GeneralConfigSerializer


class UpdateGeneralConfigResource(Meta, ModelResource):
    name = gettext_lazy("更新通用配置")
    lookup_field = "id"
    model = GeneralConfig
    action = "update"
    serializer_class = GeneralConfigSerializer
    RequestSerializer = UpdateGeneralConfigSerializer


class DeleteGeneralConfigResource(Meta, ModelResource):
    name = gettext_lazy("删除通用配置")
    lookup_field = "id"
    model = GeneralConfig
    action = "destroy"
    serializer_class = GeneralConfigSerializer
    RequestSerializer = DeleteGeneralConfigReqSerializer


class ListGeneralConfigResource(Meta, ModelResource):
    """支持过滤查询通用配置列表，支持的filter参数有：scene、config_name、created_by"""

    name = gettext_lazy("通用配置列表")
    model = GeneralConfig
    filter_fields = ["scene", "config_name", "created_by"]
    action = "list"
    serializer_class = GeneralConfigSerializer
    RequestSerializer = ListGeneralConfigReqSerializer


class BatchUpdateEnumMappings(Meta, Resource):
    """
    批量更新枚举映射，并在提供 related_type 和 related_object_id 时创建关联关系
    """

    name = gettext_lazy("批量更新枚举映射")
    RequestSerializer = BatchUpdateEnumMappingSerializer

    adapter_cls = DBEnumMappingAdapter

    def perform_request(self, validated_request_data):
        mappings = validated_request_data['mappings']
        collection_id = validated_request_data['collection_id']
        related_type = validated_request_data.get('related_type')
        related_object_id = validated_request_data.get('related_object_id')

        adapter = self.adapter_cls()
        adapter.batch_update_enum_mappings(collection_id, mappings)
        if related_type and related_object_id:
            if mappings:
                adapter.add_relation(related_type, collection_id, related_object_id)
            else:
                adapter.delete_relation(related_type, collection_id, related_object_id)
        return 'success'


class GetEnumMappingsRelation(Meta, Resource):
    name = gettext_lazy("获取枚举映射关联关系")
    RequestSerializer = EnumMappingRelation

    def perform_request(self, validated_request_data):
        related_type = validated_request_data['related_type']
        related_object_id = validated_request_data['related_object_id']
        result = list(
            item["collection_id"]
            for item in EnumMappingCollectionRelation.objects.filter(
                related_type=related_type, related_object_id=related_object_id
            ).values('collection_id')
        )
        return result


class GetEnumMappingByCollectionKeys(Meta, Resource):
    """
    根据多个 collection_id 和 key 获取对应的 name
    """

    name = gettext_lazy("根据多个 collection_id 和 key 获取对应的 name")
    RequestSerializer = EnumMappingByCollectionKeysSerializer
    ResponseSerializer = EnumMappingSerializer
    many_response_data = True

    adapter_cls = DBEnumMappingAdapter

    def perform_request(self, validated_request_data):
        collection_keys = validated_request_data['collection_keys']
        related_type = validated_request_data.get('related_type')
        related_object_id = validated_request_data.get('related_object_id')

        # 如果提供了 related_type 或 related_object_id，先检查所有 collection_id 是否有对应的关联关系
        if related_type or related_object_id:
            collection_ids = {collection_key['collection_id'] for collection_key in collection_keys}
            if not self.check_relations_exists(collection_ids, related_type, related_object_id):
                raise EnumMappingRelationInvalid()
        # 后续adapter_cls会根据validated_request_data定
        adapter = self.adapter_cls()
        mappings = adapter.get_enum_mappings_by_collection_keys(collection_keys)
        return mappings

    def check_relations_exists(self, collection_ids, related_type, related_object_id):
        """
        检查是否所有的 collection_ids 都有对应的关联关系
        如果提供了 related_type 和 related_object_id，检查这两个字段。
        """
        filter_conditions = {'collection_id__in': collection_ids}

        if related_type:
            filter_conditions['related_type'] = related_type
        if related_object_id:
            filter_conditions['related_object_id'] = related_object_id

        # 批量查询关联关系
        relations = EnumMappingCollectionRelation.objects.filter(**filter_conditions)
        # 返回存在的集合关系数量是否与传入的集合数量一致
        return relations.count() == len(collection_ids)


class GetEnumMappingByCollection(Meta, Resource):
    """
    通过 collection_id 获取所有的枚举映射，并检查关联关系
    """

    name = gettext_lazy("通过 collection_id 获取所有的枚举映射")
    RequestSerializer = EnumMappingByCollectionSerializer
    ResponseSerializer = EnumMappingSerializer
    many_response_data = True

    adapter_cls = DBEnumMappingAdapter

    def perform_request(self, validated_request_data):
        collection_id = validated_request_data['collection_id']
        related_type = validated_request_data.get('related_type')
        related_object_id = validated_request_data.get('related_object_id')

        # 如果提供了 related_type 和 related_object_id，检查是否存在关联关系
        if related_type and related_object_id:
            if not self.check_relation(collection_id, related_type, related_object_id):
                raise EnumMappingRelationInvalid()

        # 获取枚举映射
        adapter = self.adapter_cls()
        mappings = adapter.get_all_enum_mappings(collection_id)
        return mappings

    def check_relation(self, collection_id, related_type, related_object_id):
        """
        检查是否存在有效的关联关系
        """
        # 查询关联关系是否存在
        relation_exists = EnumMappingCollectionRelation.objects.filter(
            collection_id=collection_id, related_type=related_type, related_object_id=related_object_id
        ).exists()

        return relation_exists


class CreateSystem(SystemAbstractResource, Meta):
    """
    创建审计中心系统
    """

    name = gettext_lazy("创建系统")
    RequestSerializer = CreateSystemReqSerializer
    ResponseSerializer = SystemInfoResponseSerializer
    audit_action = ActionEnum.CREATE_SYSTEM

    def perform_request(self, validated_request_data: dict):
        namespace = validated_request_data["namespace"]
        system_id = validated_request_data["system_id"]
        system, is_created = System.objects.get_or_create(
            namespace=namespace, system_id=system_id, defaults=validated_request_data
        )
        if not is_created:
            raise SystemHasExist(system_id=system_id)
        return system


class UpdateSystemAuditStatus(Meta, SystemAuditMixinResource):
    """
    更新系统审计状态为已接入
    """

    name = gettext_lazy("更新系统审计状态")

    def perform_request(self, validated_request_data):
        system_id = validated_request_data["system_id"]
        system: System = get_object_or_404(System, system_id=system_id)
        system.audit_status = SystemAuditStatusEnum.ACCESSED.value
        system.save(update_fields=["audit_status"])


class UpdateSystem(Meta, SystemAuditMixinResource):
    name = gettext_lazy("更新系统")
    RequestSerializer = UpdateSystemReqSerializer
    ResponseSerializer = SystemInfoResponseSerializer
    audit_action = ActionEnum.EDIT_SYSTEM

    @transaction.atomic
    def update_system(self, system: System, validated_request_data: dict) -> dict:
        need_update_join_data = False
        for key, value in validated_request_data.items():
            if key == "callback_url" and value != system.callback_url:
                need_update_join_data = True
            setattr(system, key, value)
        system.save(update_fields=validated_request_data.keys())
        return {
            "system": system,
            "need_update_join_data": need_update_join_data,
        }

    def perform_request(self, validated_request_data):
        system_id = validated_request_data["system_id"]
        system: System = get_object_or_404(System, system_id=system_id)
        result = self.update_system(system, validated_request_data)
        system, need_update_join_data = result["system"], result["need_update_join_data"]
        if need_update_join_data:
            system.update_join_data()
        return system


class FavoriteSystem(Meta, Resource):
    name = gettext_lazy("更新系统收藏")
    RequestSerializer = SystemFavoriteReqSerializer

    def perform_request(self, validated_request_data):
        system_id = validated_request_data["system_id"]
        favorite = validated_request_data["favorite"]
        username = get_request_username()
        SystemFavorite.objects.update_or_create(system_id=system_id, username=username, defaults={"favorite": favorite})


class CreateAction(Meta, SystemAuditMixinResource):
    name = gettext_lazy("创建操作")
    RequestSerializer = ActionCreateSerializer
    ResponseSerializer = ActionSerializer
    audit_action = ActionEnum.EDIT_SYSTEM

    def perform_request(self, validated_request_data):
        system_id = validated_request_data["system_id"]
        action_id = validated_request_data["action_id"]
        action, is_created = Action.objects.get_or_create(
            unique_id=validated_request_data["unique_id"], defaults=validated_request_data
        )
        if not is_created:
            raise ActionHasExist(system_id=system_id, action_id=action_id)
        return action


class UpdateAction(Meta, ModelResource, SystemAuditMixinResource):
    name = gettext_lazy("更新操作")
    model = Action
    action = "update"
    lookup_field = "unique_id"
    audit_action = ActionEnum.EDIT_SYSTEM
    serializer_class = ActionUpdateSerializer
    RequestSerializer = ActionUpdateSerializer


class DeleteAction(Meta, ModelResource, SystemAuditMixinResource):
    name = gettext_lazy("删除操作")
    audit_action = ActionEnum.EDIT_SYSTEM
    model = Action
    action = "destroy"
    lookup_field = "unique_id"


class BulkCreateAction(Meta, ModelResource, SystemAuditMixinResource):
    name = gettext_lazy("批量创建操作")
    RequestSerializer = BulkActionCreateSerializer
    audit_action = ActionEnum.EDIT_SYSTEM

    @transaction.atomic
    def perform_request(self, validated_request_data):
        actions = validated_request_data["actions"]
        for action in actions:
            resource.meta.create_action(action)
