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

import openpyxl
import requests
from bk_resource import CacheResource, Resource, api, resource
from bk_resource.contrib.model import ModelResource
from bk_resource.exceptions import APIRequestError
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

from apps.audit.resources import AuditMixinResource
from apps.meta import models
from apps.meta.constants import (
    FETCH_INSTANCE_SCHEMA_CACHE_TIMEOUT,
    FETCH_INSTANCE_SCHEMA_METHOD,
    GET_APP_INFO_CACHE_TIMEOUT,
    IAM_MANAGER_ROLE,
    RETRIEVE_USER_TIMEOUT,
    SpaceType,
    SystemAuditStatusEnum,
    SystemSourceTypeEnum,
)
from apps.meta.exceptions import (
    ActionHasExist,
    BKAppNotExists,
    SystemHasExist,
    SystemNotEditable,
)
from apps.meta.handlers.system_diagnosis import SystemDiagnosisPushHandler
from apps.meta.models import (
    Action,
    CustomField,
    DataMap,
    Field,
    GlobalMetaConfig,
    ResourceType,
    ResourceTypeActionRelation,
    SensitiveObject,
    System,
    SystemFavorite,
    SystemInstance,
    Tag,
)
from apps.meta.permissions import SearchLogPermission
from apps.meta.serializers import (
    ActionCreateSerializer,
    ActionSerializer,
    ActionUpdateSerializer,
    BulkActionCreateSerializer,
    ChangeSystemDiagnosisPushReqSerializer,
    ChangeSystemDiagnosisPushRespSerializer,
    CreateSystemReqSerializer,
    DeleteSystemDiagnosisPushReqSerializer,
    FieldListRequestSerializer,
    FieldListSerializer,
    GetAppInfoRequestSerializer,
    GetAppInfoResponseSerializer,
    GetAssetPullInfoRequestSerializer,
    GetCustomFieldsRequestSerializer,
    GetGlobalsResponseSerializer,
    GetResourceTypeSchemaRequestSerializer,
    GetSensitiveObjRequestSerializer,
    GetSensitiveObjResponseSerializer,
    GetSpacesMineResponseSerializer,
    GlobalMetaConfigInfoSerializer,
    GlobalMetaConfigListSerializer,
    GlobalMetaConfigPostSerializer,
    ListAllTagsRespSerializer,
    ListUsersRequestSerializer,
    ListUsersResponseSerializer,
    NamespaceSerializer,
    ResourceTypeSerializer,
    RetrieveUserRequestSerializer,
    RetrieveUserResponseSerializer,
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
            always_allowed=lambda sys: username in system_managers.get(sys["system_id"]),
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
    name = gettext_lazy("获取系统列表(All)")
    action = "list"
    many_response_data = True
    filter_fields = {
        "namespace": ["exact"],
        "audit_status": ["in"],
        "source_type": ["in"],
    }
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
                systems, actions, always_allowed=lambda sys: is_system_manager(sys["system_id"])
            )

        # 排序
        sort_keys = validated_request_data.get("sort_keys", [])  # 默认用权限
        systems.sort(key=get_system_sort_key(sort_keys))
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
        system_id = validated_request_data["system_id"]
        system_info = super().perform_request(validated_request_data)
        system_info["managers"] = [
            manager["username"]
            for manager in resource.meta.system_role_list(system_id=system_id, role=IAM_MANAGER_ROLE)
        ]
        # 增加最后上报信息数据
        system_info = wrapper_system_status(namespace=system_info["namespace"], systems=[system_info])[0]
        self.add_audit_instance_to_context(instance=SystemInstance(system_info).instance)
        return system_info


class SystemAttrAbstractResource(Meta, ModelResource, ABC):
    action = "list"
    filter_fields = ["system_id"]
    many_response_data = True


class ResourceTypeListResource(SystemAttrAbstractResource):
    name = gettext_lazy("资源类型列表")
    model = models.ResourceType
    serializer_class = ResourceTypeSerializer


class ActionListResource(SystemAttrAbstractResource):
    name = gettext_lazy("操作列表")
    model = models.Action
    serializer_class = ActionSerializer

    def perform_request(self, validated_request_data: dict) -> any:
        data = super().perform_request(validated_request_data)
        system_id = validated_request_data["system_id"]
        resource_type_id_map = Action.get_resource_type_id_map(system_id)
        for action in data:
            action["resource_type_ids"] = resource_type_id_map.get(action["action_id"], [])
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
            data = web.post(url=request_url, json=request_body, headers=request_header).json()["data"]["properties"]
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


class ListUsersResource(Meta, Resource):
    name = gettext_lazy("获取用户列表")
    RequestSerializer = ListUsersRequestSerializer
    serializer_class = ListUsersResponseSerializer

    def perform_request(self, validated_request_data):
        return api.user_manage.list_users(validated_request_data)


class RetrieveUserResource(Meta, CacheMixin, Resource):
    name = gettext_lazy("获取用户详情")
    RequestSerializer = RetrieveUserRequestSerializer
    ResponseSerializer = RetrieveUserResponseSerializer
    cache = default_cache

    def generate_cache_key(self, username) -> str:
        return f"api:{self.__class__.__name__}:{username}"

    def perform_request(self, validated_request_data):
        cache_data = self.get_cache({"username": validated_request_data["id"]})
        if cache_data is not None:
            return cache_data
        try:
            data = api.user_manage.retrieve_user(validated_request_data)
        except APIRequestError:
            data = {"username": validated_request_data["id"], "display_name": gettext("未知用户")}
        self.set_cache({"username": validated_request_data["id"]}, data, RETRIEVE_USER_TIMEOUT)
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


class CreateSystem(Meta, SystemAuditMixinResource):
    name = gettext_lazy("创建系统")
    RequestSerializer = CreateSystemReqSerializer
    ResponseSerializer = SystemInfoResponseSerializer
    audit_action = ActionEnum.CREATE_SYSTEM

    def update_system_audit_status(self, system: System) -> System:
        """
        更新系统审计状态
        """

        system.audit_status = SystemAuditStatusEnum.ACCESSED.value
        system.save(update_fields=["audit_status"])
        return system

    def create_audit_system(self, validated_request_data: dict) -> System:
        """
        创建审计系统
        """

        source_type = validated_request_data["source_type"]
        instance_id = validated_request_data["instance_id"]
        namespace = validated_request_data["namespace"]
        validated_request_data["auth_token"] = System.gen_auth_token()
        validated_request_data["audit_status"] = SystemAuditStatusEnum.ACCESSED.value
        system, is_created = System.objects.get_or_create(
            namespace=namespace, source_type=source_type, instance_id=instance_id, defaults=validated_request_data
        )
        if not is_created:
            raise SystemHasExist(source_type=source_type, instance_id=instance_id)
        return system

    def perform_request(self, validated_request_data: dict):
        source_type = validated_request_data["source_type"]
        if source_type not in SystemSourceTypeEnum.get_editable_sources():
            # 不可编辑来源的系统仅修改其系统审计状态
            instance_id = validated_request_data["instance_id"]
            system: System = get_object_or_404(System, source_type=source_type, instance_id=instance_id)
            return self.update_system_audit_status(system)
        else:
            return self.create_audit_system(validated_request_data)


class SystemEditValidatorBase(abc.ABC):
    """
    系统编辑验证基类
    """

    def _validate_system_edit(self, system_id) -> System:
        """
        验证系统是否可编辑
        """

        system: System = get_object_or_404(System, system_id=system_id)
        if system.source_type not in SystemSourceTypeEnum.get_editable_sources():
            raise SystemNotEditable(system_id=system_id)
        return system


class UpdateSystem(Meta, SystemAuditMixinResource, SystemEditValidatorBase):
    name = gettext_lazy("更新系统")
    RequestSerializer = UpdateSystemReqSerializer
    ResponseSerializer = SystemInfoResponseSerializer
    audit_action = ActionEnum.EDIT_SYSTEM

    def update_join_data(self, system: System):
        """
        更新关联数据(异步)
        """

        try:
            from services.web.databus.tasks import refresh_system_snapshots
        except ImportError:
            return

        refresh_system_snapshots.delay(system_id=system.system_id)

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
        system: System = self._validate_system_edit(system_id)
        result = self.update_system(system, validated_request_data)
        system = result["system"]
        need_update_join_data = result["need_update_join_data"]
        if need_update_join_data:
            self.update_join_data(system)
        return system


class FavoriteSystem(Meta, Resource):
    name = gettext_lazy("更新系统收藏")
    RequestSerializer = SystemFavoriteReqSerializer

    def perform_request(self, validated_request_data):
        system_id = validated_request_data["system_id"]
        favorite = validated_request_data["favorite"]
        username = get_request_username()
        SystemFavorite.objects.update_or_create(system_id=system_id, username=username, defaults={"favorite": favorite})


class CreateResourceType(Meta, Resource):
    name = gettext_lazy("创建资源类型")

    def perform_request(self, validated_request_data):
        pass


class UpdateResourceType(Meta, Resource):
    name = gettext_lazy("更新资源类型")

    def perform_request(self, validated_request_data):
        """
        TODO: 需要判断是否需要更新后端资源拉取任务
        """
        pass


class BulkUpdateResourceType(Meta, Resource):
    name = gettext_lazy("批量更新资源类型")

    def perform_request(self, validated_request_data):
        pass


class DeleteResourceType(Meta, Resource):
    name = gettext_lazy("删除资源类型")

    def perform_request(self, validated_request_data):
        """
        TODO: 需要判断是否需要删除/停用后端资源拉取任务
        """
        pass


class CreateAction(Meta, SystemAuditMixinResource, SystemEditValidatorBase):
    name = gettext_lazy("创建操作")
    RequestSerializer = ActionCreateSerializer
    ResponseSerializer = ActionSerializer
    audit_action = ActionEnum.EDIT_SYSTEM

    @transaction.atomic
    def create_audit_action(self, system: System, validated_request_data: dict) -> Action:
        """
        创建审计操作
        """

        resource_type_ids = validated_request_data.pop("resource_type_ids", [])
        if resource_type_ids:
            resource_type_ids = ResourceType.objects.filter(
                system_id=system.system_id, resource_type_id__in=resource_type_ids
            ).values_list("resource_type_id", flat=True)
        action_id = validated_request_data["action_id"]
        action, is_created = Action.objects.get_or_create(
            system_id=system.system_id, action_id=action_id, defaults=validated_request_data
        )
        if not is_created:
            raise ActionHasExist(action_id=action_id)
        if resource_type_ids:
            action.set_resource_type_ids(resource_type_ids)
        return action

    def perform_request(self, validated_request_data):
        system_id = validated_request_data["system_id"]
        system: System = self._validate_system_edit(system_id)
        return self.create_audit_action(system, validated_request_data)


class UpdateAction(Meta, SystemAuditMixinResource, ModelResource, SystemEditValidatorBase):
    name = gettext_lazy("更新操作")
    RequestSerializer = ActionUpdateSerializer
    ResponseSerializer = ActionSerializer
    audit_action = ActionEnum.EDIT_SYSTEM

    @transaction.atomic
    def update_system_action(self, system: System, action: Action, validated_request_data: dict) -> Action:
        resource_type_ids = validated_request_data.pop("resource_type_ids", None)
        if resource_type_ids is not None:
            resource_type_ids = ResourceType.objects.filter(
                system_id=system.system_id, resource_type_id__in=resource_type_ids
            ).values_list("resource_type_id", flat=True)
        for key, value in validated_request_data.items():
            setattr(action, key, value)
            action.save(update_fields=validated_request_data.keys())
        if resource_type_ids is not None:
            action.set_resource_type_ids(resource_type_ids)
        return action

    def perform_request(self, validated_request_data):
        unique_id = validated_request_data["unique_id"]
        action: Action = get_object_or_404(Action, unique_id=unique_id)
        system = self._validate_system_edit(action.system_id)
        return self.update_system_action(system, action, validated_request_data)


class BulkCreateAction(Meta, SystemAuditMixinResource, SystemEditValidatorBase):
    name = gettext_lazy("批量创建操作")
    RequestSerializer = BulkActionCreateSerializer
    ResponseSerializer = ActionSerializer
    many_response_data = True
    audit_action = ActionEnum.EDIT_SYSTEM

    @transaction.atomic
    def perform_request(self, validated_request_data):
        system_id = validated_request_data["system_id"]
        self._validate_system_edit(system_id)
        actions = validated_request_data["actions"]

        # 步骤1: 批量创建操作对象
        action_instances = []

        # 预查询已存在的操作避免冲突
        existing_action_ids = Action.objects.filter(
            system_id=system_id, action_id__in=[a["action_id"] for a in actions]
        ).values_list("action_id", flat=True)
        existing_actions = set(existing_action_ids)

        # 准备批量创建数据
        for action_data in actions:
            action_id = action_data["action_id"]

            # 跳过已存在的操作
            if action_id in existing_actions:
                continue

            action_instances.append(
                Action(
                    unique_id=Action.gen_unique_id(system_id, action_id),
                    **{k: v for k, v in action_data.items() if k != "resource_type_ids"},
                )
            )

        # 批量创建操作
        created_actions = Action.objects.bulk_create(action_instances)

        # 步骤2: 批量设置资源类型关系
        relations_to_set = []
        action_id_to_instance = {action.action_id: action for action in created_actions}

        for action_data in actions:
            if action_data["action_id"] not in action_id_to_instance:
                continue

            resource_type_ids = action_data.get("resource_type_ids", [])
            if resource_type_ids:
                relations_to_set.append(
                    {
                        "system_id": system_id,
                        "action_id": action_data["action_id"],
                        "resource_type_ids": resource_type_ids,
                    }
                )

        # 批量设置资源类型关系
        if relations_to_set:
            Action.bulk_set_resource_types(relations_to_set)

        return Action.objects.filter(system_id=system_id)


class DeleteAction(Meta, SystemAuditMixinResource, SystemEditValidatorBase):
    name = gettext_lazy("删除操作")
    audit_action = ActionEnum.EDIT_SYSTEM

    @transaction.atomic
    def perform_request(self, validated_request_data):
        unique_id = validated_request_data["unique_id"]
        action: Action = get_object_or_404(Action, unique_id=unique_id)
        self._validate_system_edit(system_id=action.system_id)

        # 1. 删除操作资源类型关联
        ResourceTypeActionRelation.objects.filter(system_id=action.system_id, action_id=action.action_id).delete()
        # 2: 删除操作对象
        Action.objects.filter(system_id=action.system_id, action_id=action.action_id).delete()
