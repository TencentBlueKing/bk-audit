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

import base64
from abc import ABC
from collections import defaultdict
from functools import cmp_to_key

import openpyxl
import requests
from bk_resource import Resource, api, resource
from bk_resource.contrib.model import ModelResource
from bk_resource.exceptions import APIRequestError
from bk_resource.management.exceptions import ResourceModuleNotRegistered
from blueapps.utils.logger import logger
from django.conf import settings
from django.core.cache import cache as default_cache
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext, gettext_lazy
from rest_framework import serializers

from apps.audit.client import bk_audit_client
from apps.audit.models import SystemInstance
from apps.meta import models
from apps.meta.constants import (
    FETCH_INSTANCE_SCHEMA_CACHE_TIMEOUT,
    FETCH_INSTANCE_SCHEMA_METHOD,
    GET_APP_INFO_CACHE_TIMEOUT,
    IAM_MANAGER_ROLE,
    RETRIEVE_USER_TIMEOUT,
    SpaceType,
)
from apps.meta.exceptions import BKAppNotExists
from apps.meta.models import (
    Action,
    CustomField,
    DataMap,
    Field,
    GlobalMetaConfig,
    ResourceType,
    SensitiveObject,
    System,
    Tag,
)
from apps.meta.serializers import (
    ActionSerializer,
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
    ListUsersRequestSerializer,
    ListUsersResponseSerializer,
    NamespaceSerializer,
    ResourceTypeSerializer,
    RetrieveUserRequestSerializer,
    RetrieveUserResponseSerializer,
    SaveTagResponseSerializer,
    SaveTagsRequestSerializer,
    SystemInfoResponseSerializer,
    SystemListAllRequestSerializer,
    SystemListAllResponseSerializer,
    SystemListRequestSerializer,
    SystemRoleListRequestSerializer,
    SystemRoleSerializer,
    SystemSearchBaseSerialzier,
    SystemSerializer,
    UpdateCustomFieldResponseSerializer,
    UploadDataMapFileRequestSerializer,
    UploadDataMapFileResponseSerializer,
)
from apps.meta.utils.globals import Globals
from apps.permission.handlers.actions import ActionEnum, get_action_by_id
from apps.permission.handlers.drf import wrapper_permission_field
from apps.permission.handlers.resource_types import ResourceEnum
from core.models import get_request_username
from core.permissions import FetchInstancePermission, SearchLogPermission
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


class SystemAbstractResource(Meta, ModelResource, ABC):
    model = models.System
    serializer_class = SystemSerializer


class SystemListResource(SystemAbstractResource):
    name = gettext_lazy("获取系统列表")
    action = "list"
    many_response_data = True
    RequestSerializer = SystemListRequestSerializer

    @classmethod
    def sort_system_by_permission(cls, system: dict) -> (int, str):
        permission_obj = system.get("permission", {})
        priority_index = min(len([is_allowed for is_allowed in permission_obj.values() if is_allowed]), 1)
        return -priority_index, system.get("system_id") or system["id"]

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
        queryset = models.System.objects.all()
        if validated_request_data.get("keyword"):
            keyword = validated_request_data["keyword"]
            queryset = queryset.filter(
                Q(Q(name__icontains=keyword) | Q(name_en__icontains=keyword) | Q(system_id__icontains=keyword))
            )
        systems = self.serializer_class(queryset, many=self.many_response_data).data
        all_managers = resource.meta.system_role_list(role=IAM_MANAGER_ROLE)
        system_manager_map = defaultdict(list)
        for manager in all_managers:
            system_manager_map[manager["system_id"]].append(manager["username"])
        for system in systems:
            system["managers"] = system_manager_map[system["system_id"]]
        actions = [ActionEnum.VIEW_SYSTEM, ActionEnum.EDIT_SYSTEM]
        systems = wrapper_permission_field(systems, actions, id_field=lambda x: x["system_id"])
        systems.sort(key=self.sort_system_by_permission)
        bk_audit_client.add_event(action=ActionEnum.LIST_SYSTEM, resource_type=ResourceEnum.SYSTEM)
        if not systems:
            return systems
        try:
            # 绑定最后上报信息
            tail_log_time_map = resource.databus.collector.bulk_system_collectors_status(
                namespace=validated_request_data["namespace"],
                system_ids=",".join([system["system_id"] for system in systems]),
            )
        except ResourceModuleNotRegistered:
            tail_log_time_map = {}
        for system in systems:
            tail_log_item = tail_log_time_map.get(system["system_id"], {})
            system["last_time"] = tail_log_item.get("last_time")
            system["status"] = tail_log_item.get("status")
            system["status_msg"] = tail_log_item.get("status_msg")
        if validated_request_data.get("status"):
            systems = self.filter(systems, {"status": validated_request_data["status"]})
        return self.sort(systems, validated_request_data)


class SystemListAllResource(SystemAbstractResource):
    name = gettext_lazy("获取系统列表(All)")
    action = "list"
    many_response_data = True
    filter_fields = ["namespace"]
    RequestSerializer = SystemListAllRequestSerializer
    serializer_class = SystemListAllResponseSerializer

    def perform_request(self, validated_request_data: dict) -> any:
        systems = super().perform_request(validated_request_data)
        if not validated_request_data.get("action_ids"):
            return systems

        actions = [get_action_by_id(action) for action in validated_request_data["action_ids"]]
        systems = wrapper_permission_field(systems, actions)
        systems.sort(key=SystemListResource.sort_system_by_permission)
        bk_audit_client.add_event(action=ActionEnum.LIST_SYSTEM, resource_type=ResourceEnum.SYSTEM)
        return systems


class SystemInfoResource(SystemAbstractResource):
    name = gettext_lazy("获取系统详情")
    lookup_field = "system_id"
    serializer_class = SystemInfoResponseSerializer
    action = "retrieve"

    def perform_request(self, validated_request_data: dict) -> any:
        system_id = validated_request_data["system_id"]
        system_info = super().perform_request(validated_request_data)
        system_info["managers"] = [
            manager["username"]
            for manager in resource.meta.system_role_list(system_id=system_id, role=IAM_MANAGER_ROLE)
        ]
        bk_audit_client.add_event(
            action=ActionEnum.VIEW_SYSTEM,
            resource_type=ResourceEnum.SYSTEM,
            instance=SystemInstance(system_info).instance,
        )
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

        params = {"id": app_code, "include_deploy_info": 1}
        resp = api.bk_paas.uni_apps_query(params)

        if not resp:
            raise BKAppNotExists()

        app_info = resp[0]
        data.update({"app_name": app_info["name"], "developers": app_info["developers"]})

        deploy_info = app_info["deploy_info"] or dict()
        deploy_url = deploy_info.get("prod", {}).get("url") or deploy_info.get("stag", {}).get("url")
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
        request_url = (
            system.provider_config["host"].rstrip("/") + "/" + resource_type.provider_config["path"].lstrip("/")
        )
        request_body = {"type": resource_type.resource_type_id, "method": FETCH_INSTANCE_SCHEMA_METHOD}
        base64_token = base64.b64encode(
            f"{settings.FETCH_INSTANCE_USERNAME}:{system.provider_config['token']}".encode("utf-8")
        ).decode("utf-8")
        request_header = {"Authorization": f"Basic {base64_token}"}
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
            data = dict()
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
            "url": "{}{}".format(system.provider_config["host"], resource_type.provider_config["path"]),
            "token": FetchInstancePermission.build_auth(
                settings.FETCH_INSTANCE_USERNAME, system.provider_config["token"]
            ),
        }
