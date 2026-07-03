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
import datetime
import traceback
from collections import defaultdict
from copy import deepcopy
from typing import List, Tuple

from bk_resource import Resource, api, resource
from bk_resource.utils.common_utils import get_md5
from blueapps.utils.logger import logger
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q
from django.utils.translation import gettext, gettext_lazy
from pypinyin import lazy_pinyin
from rest_framework import serializers as drf_serializers

from api.bk_base.constants import UserAuthActionEnum
from api.bk_base.serializers import UserAuthCheckRespSerializer
from apps.audit.resources import AuditMixinResource
from apps.meta.constants import NO_TAG_ID, NO_TAG_NAME
from apps.meta.models import EnumMappingRelatedType, System, Tag
from apps.meta.serializers import EnumMappingSerializer
from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.permission import Permission
from apps.permission.handlers.resource_types import ResourceEnum
from core.exceptions import PermissionException
from core.models import get_request_username
from core.sql.parser.model import ParsedSQLInfo
from core.sql.parser.praser import SqlQueryAnalysis
from core.utils.data import preserved_order_sort
from core.utils.tools import get_app_info
from services.web.common.caller_permission import (
    CurrentType,
    should_skip_permission_from,
)
from services.web.common.constants import ScopeType
from services.web.common.scope_permission import ScopeContext, ScopePermission
from services.web.scene.binding_validation import assert_binding_relation_integrity
from services.web.scene.constants import (
    BindingType,
    PanelStatus,
    ResourceVisibilityType,
    SceneStatus,
)
from services.web.scene.data_filter import SceneDataFilter
from services.web.scene.filters import BindingMetadataHelper, CompositeScopeFilter
from services.web.scene.models import (
    ResourceBinding,
    ResourceBindingScene,
    ResourceBindingSystem,
    Scene,
)
from services.web.strategy_v2.models import StrategyTool
from services.web.strategy_v2.serializers import (
    EnumMappingByCollectionKeysWithCallerSerializer,
    EnumMappingByCollectionWithCallerSerializer,
)
from services.web.tool.constants import (
    ApiToolConfig,
    DataSearchConfigTypeEnum,
    SQLDataSearchConfig,
    TableFieldTypeConfig,
    ToolTagsEnum,
    ToolTypeEnum,
)
from services.web.tool.exceptions import (
    DataSearchTablePermission,
    ToolDoesNotExist,
    ToolNotPublished,
    ToolTypeNotSupport,
)
from services.web.tool.executor.tool import ToolExecutorFactory
from services.web.tool.models import Tool, ToolFavorite, ToolTag
from services.web.tool.serializers import (
    ExecuteToolReqSerializer,
    ExecuteToolRespSerializer,
    GetToolDetailByNameAPIGWRequestSerializer,
    GetToolDetailByNameAPIGWResponseSerializer,
    ListRequestSerializer,
    ListToolAllRequestSerializer,
    ListToolTagsRequestSerializer,
    ListToolTagsResponseSerializer,
    PlatformSceneToolCreateRequestSerializer,
    PlatformSceneToolPublishRequestSerializer,
    PlatformSceneToolUpdateRequestSerializer,
    SceneScopeToolCreateRequestSerializer,
    SceneScopeToolDeleteRequestSerializer,
    SceneScopeToolPublishRequestSerializer,
    SceneScopeToolUpdateRequestSerializer,
    SqlAnalyseRequestSerializer,
    SqlAnalyseResponseSerializer,
    SqlAnalyseWithToolRequestSerializer,
    ToolCreateRequestSerializer,
    ToolExecuteDebugSerializer,
    ToolFavoriteReqSerializer,
    ToolFavoriteRespSerializer,
    ToolListAllResponseSerializer,
    ToolListResponseSerializer,
    ToolPublishResponseSerializer,
    ToolResponseSerializer,
    ToolRetrieveRequestSerializer,
    ToolRetrieveResponseSerializer,
    ToolUpdateRequestSerializer,
    UserQueryTableAuthCheckReqSerializer,
)
from services.web.tool.tasks import update_bkvision_config
from services.web.tool.tool import (
    create_tool_with_config,
    recent_tool_usage_manager,
    sync_resource_tags,
)


class ToolBase(AuditMixinResource, abc.ABC):
    tags = ["Tool"]

    def updatel_enum_mappings(
        self,
        enum_mapping: dict,
        tool_uid: str,
        field_name: str,
    ):
        """
        Generate immutable collection_id based on tool_id, field_category, and field_name,
        then batch update enum mappings.
        """
        # override collection_id to ensure uniqueness and immutability
        enum_mapping['collection_id'] = f"tool_{tool_uid}_output_fields_{field_name}"
        enum_mapping['related_object_id'] = tool_uid
        enum_mapping['related_type'] = EnumMappingRelatedType.TOOL.value
        resource.meta.batch_update_enum_mappings(**enum_mapping)

    def deletel_enum_mappings(self, tool_uid: str):
        collection_ids = resource.meta.get_enum_mappings_relation(
            related_object_id=tool_uid, related_type=EnumMappingRelatedType.TOOL.value
        )
        for collection_id in collection_ids:
            resource.meta.batch_update_enum_mappings(
                collection_id=collection_id,
                related_type=EnumMappingRelatedType.TOOL.value,
                related_object_id=tool_uid,
                mappings=[],
            )

    def _generate_api_field_key(self, group_name, field):
        """生成 API 字段的唯一标识"""
        # 组合关键信息
        raw_str = f"{group_name}-{field.json_path}-{field.raw_name}"
        # 生成 MD5
        return get_md5(raw_str)

    def _handle_api_enum_mappings(self, tool_uid: str, config: ApiToolConfig):
        """
        处理 API 工具的枚举映射（包含嵌套的表格字段）
        """
        # 遍历分组
        for group in config.output_config.groups:
            # 遍历分组下的字段
            for field in group.output_fields:
                # 1. 处理第一层字段的枚举
                if field.enum_mappings:
                    unique_key = self._generate_api_field_key(group.name, field)
                    self.updatel_enum_mappings(
                        enum_mapping=field.enum_mappings.model_dump(),
                        tool_uid=tool_uid,
                        field_name=unique_key,
                    )

                # 2. 处理嵌套表格中的字段枚举
                field_config = field.field_config
                # 直接通过 isinstance 判断是否为表格类型配置
                if isinstance(field_config, TableFieldTypeConfig):
                    for sub_field in field_config.output_fields:
                        if sub_field.enum_mappings:
                            unique_key = self._generate_api_field_key(group.name, sub_field)
                            self.updatel_enum_mappings(
                                enum_mapping=sub_field.enum_mappings.model_dump(),
                                tool_uid=tool_uid,
                                field_name=unique_key,
                            )

    @staticmethod
    def _ensure_binding_integrity_or_raise(binding):
        try:
            assert_binding_relation_integrity(binding)
        except ValueError:
            raise drf_serializers.ValidationError({"binding": gettext_lazy("资源绑定关系不合法")})

    def filter_queryset_by_scope(self, queryset, validated_request_data: dict, username: str):
        scope_type = validated_request_data.get("scope_type")
        binding_type = validated_request_data.get("binding_type")
        if not scope_type:
            binding_filter = binding_type or BindingType.PLATFORM_BINDING
            bindings = ResourceBinding.objects.filter(
                resource_type=ResourceVisibilityType.TOOL,
                binding_type=binding_filter,
            )
            if binding_filter == BindingType.SCENE_BINDING:
                bindings = bindings.filter(binding_scenes__scene__is_deleted=False)
            tool_uids = bindings.values_list("resource_id", flat=True)
            return queryset.filter(uid__in=tool_uids)

        scope = ScopeContext(
            scope_type=scope_type,
            scope_id=validated_request_data.get("scope_id"),
        )
        scope_permission = ScopePermission(username=username)
        scene_ids = scope_permission.get_scene_ids(scope, ActionEnum.VIEW_SCENE)
        system_ids = scope_permission.get_system_ids(scope, ActionEnum.VIEW_SYSTEM)

        return CompositeScopeFilter.filter_queryset(
            queryset=queryset,
            binding_type=binding_type,
            scene_id=scene_ids,
            system_id=system_ids,
            resource_type=ResourceVisibilityType.TOOL,
            pk_field="uid",
        )

    @staticmethod
    def attach_visibility_metadata(tools: List[Tool]) -> None:
        """批量回填工具绑定可见范围，供前端按 binding/visibility 自行展示。"""
        tool_uids = [tool.uid for tool in tools]
        bindings = list(
            ResourceBinding.objects.filter(
                resource_type=ResourceVisibilityType.TOOL,
                resource_id__in=tool_uids,
            ).values("id", "resource_id", "binding_type", "visibility_type")
        )
        binding_map = {binding["resource_id"]: binding for binding in bindings}
        binding_ids = [binding["id"] for binding in bindings]
        scene_id_map = defaultdict(list)
        for binding_id, scene_id in ResourceBindingScene.objects.filter(
            binding_id__in=binding_ids,
            scene__is_deleted=False,
        ).values_list("binding_id", "scene_id"):
            scene_id_map[binding_id].append(scene_id)

        system_id_map = defaultdict(list)
        for binding_id, system_id in ResourceBindingSystem.objects.filter(binding_id__in=binding_ids).values_list(
            "binding_id", "system_id"
        ):
            system_id_map[binding_id].append(system_id)

        for tool in tools:
            binding = binding_map.get(str(tool.uid))
            visibility = {
                "binding_type": None,
                "visibility_type": None,
                "scene_ids": [],
                "system_ids": [],
            }
            if binding is not None:
                visibility = {
                    "binding_type": binding["binding_type"],
                    "visibility_type": binding["visibility_type"],
                    "scene_ids": scene_id_map[binding["id"]],
                    "system_ids": system_id_map[binding["id"]],
                }
            setattr(tool, "visibility", visibility)


class ListToolTags(ToolBase):
    name = gettext_lazy("列出工具标签")
    RequestSerializer = ListToolTagsRequestSerializer
    ResponseSerializer = ListToolTagsResponseSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        current_user = get_request_username()
        scoped_tools = self.filter_queryset_by_scope(Tool.all_latest_tools(), validated_request_data, current_user)
        status = validated_request_data.get("status")
        if status:
            scoped_tools = scoped_tools.filter(status=status)

        tag_count = list(
            ToolTag.objects.filter(tool_uid__in=scoped_tools.values_list("uid", flat=True))
            .values("tag_id")
            .annotate(tool_count=Count("tag_id"))
            .order_by()
        )
        tag_map = {t.tag_id: {"name": t.tag_name} for t in Tag.objects.all()}
        for t in tag_count:
            t.update({"tag_name": tag_map.get(t["tag_id"], {}).get("name", t["tag_id"])})

        tag_count.sort(key=lambda tag: [lazy_pinyin(tag["tag_name"].lower(), errors="ignore"), tag["tag_name"].lower()])

        tag_count = [
            {
                "tag_name": str(ToolTagsEnum.ALL_TOOLS.label),
                "tag_id": ToolTagsEnum.ALL_TOOLS.value,
                "tool_count": scoped_tools.count(),
            },
            {
                "tag_name": str(ToolTagsEnum.MY_CREATED_TOOLS.label),
                "tag_id": ToolTagsEnum.MY_CREATED_TOOLS.value,
                "tool_count": scoped_tools.filter(created_by=current_user).count(),
            },
            {
                "tag_name": str(ToolTagsEnum.RECENTLY_USED_TOOLS.label),
                "tag_id": ToolTagsEnum.RECENTLY_USED_TOOLS.value,
                "tool_count": scoped_tools.filter(
                    uid__in=recent_tool_usage_manager.get_recent_uids(current_user)
                ).count(),
            },
            {
                "tag_name": str(ToolTagsEnum.FAVORITE_TOOLS.label),
                "tag_id": ToolTagsEnum.FAVORITE_TOOLS.value,
                "tool_count": ToolFavorite.objects.filter(
                    username=current_user,
                    tool_uid__in=scoped_tools.values_list("uid", flat=True),
                ).count(),
            },
            {
                "tag_name": str(NO_TAG_NAME),
                "tag_id": NO_TAG_ID,
                "tool_count": scoped_tools.exclude(
                    uid__in=ToolTag.objects.values_list("tool_uid", flat=True).distinct()
                ).count(),
            },
        ] + tag_count
        return tag_count


class ListTool(ToolBase):
    """
    keyword：模糊搜索关键词（创建人/工具名称/工具描述）
    tags：[xx.xx]
    my_created：是否只显示我创建的 布尔
    recent_used：是否只显示最近使用 布尔
    tool_type=data_search：响应结构
    ```json
    [
      {
        "uid": "xxx",
        "name": "xxx",
        "tool_type": "data_search",
        "version": 1,
        "description": "xxx",
        "namespace": "xxx",
        "tags": ["xx", "xx"],
        "created_by": "xxx",
        "created_at": "xxx",
        "permission": {
          "use_tool": true, // 是否有使用权限
          "manage_tool": true // 是否有管理权限
        }
      }
    ]
    ```
    tool_type=bk_vision：响应结构
    ```
    [
      {
        "uid": "xxx",
        "name": "xxx",
        "tool_type": "bk_vision",
        "version": 1,
        "description": "xxx",
        "namespace": "xxx",
        "tags": ["xx", "xx"],
        "created_by": "xxx",
        "created_at": "xxx",
        "permission": {
          "use_tool": true, // 是否有使用权限
          "manage_tool": true // 是否有管理权限
        }
      }
    ]
    ```
    """

    name = gettext_lazy("获取工具列表")
    RequestSerializer = ListRequestSerializer
    ResponseSerializer = ToolListResponseSerializer
    many_response_data = True
    bind_request = True

    def perform_request(self, validated_request_data):
        validated_request_data.pop("_request", None)
        tags = validated_request_data.pop("tags", [])
        keyword = validated_request_data.get("keyword", "").strip()
        name = validated_request_data.get("name", [])
        description = validated_request_data.get("description", [])
        tool_type = validated_request_data.get("tool_type", [])
        updated_by = validated_request_data.get("updated_by", [])
        my_created = validated_request_data["my_created"]
        recent_used = validated_request_data["recent_used"]
        order_fields = validated_request_data.pop("order_fields", [])
        status = validated_request_data.get("status")
        recent_tool_uids = []

        # 判断是否筛选收藏的工具（通过虚拟标签 FAVORITE_TOOLS）
        favorite = int(ToolTagsEnum.FAVORITE_TOOLS.value) in tags

        current_user = get_request_username()

        # 构建收藏状态子查询（使用 tool_uid 关联，确保版本更新后收藏状态正确）
        favorite_subquery = ToolFavorite.objects.filter(tool_uid=OuterRef("uid"), username=current_user)
        queryset = Tool.all_latest_tools().annotate(favorite=Exists(favorite_subquery))
        queryset = self.filter_queryset_by_scope(queryset, validated_request_data, current_user)

        # 处理虚拟标签：清空 tags 以避免后续按普通标签筛选
        if any(
            int(tag_id) in tags
            for tag_id in [
                ToolTagsEnum.ALL_TOOLS.value,
                ToolTagsEnum.MY_CREATED_TOOLS.value,
                ToolTagsEnum.RECENTLY_USED_TOOLS.value,
                ToolTagsEnum.FAVORITE_TOOLS.value,
            ]
        ):
            tags = []

        # 筛选收藏的工具
        if favorite:
            queryset = queryset.filter(favorite=True)

        if recent_used:
            recent_tool_uids = recent_tool_usage_manager.get_recent_uids(current_user)

            if not recent_tool_uids:
                return []
            else:
                queryset = queryset.filter(uid__in=recent_tool_uids)

        if my_created:
            queryset = queryset.filter(created_by=current_user)

        if status:
            queryset = queryset.filter(status__in=status)

        def apply_multi_value_filter(field_name, values, lookup='icontains'):
            q_filter = Q()
            for value in values:
                if value:
                    q_filter |= Q(**{f"{field_name}__{lookup}": value})
            return queryset.filter(q_filter)

        if name:
            queryset = apply_multi_value_filter("name", name)
        if description:
            queryset = apply_multi_value_filter("description", description)

        if tool_type:
            queryset = queryset.filter(tool_type__in=tool_type)
        if updated_by:
            queryset = queryset.filter(updated_by__in=updated_by)
        if keyword:
            keyword_filter = (
                Q(name__icontains=keyword) | Q(description__icontains=keyword) | Q(created_by__icontains=keyword)
            )
            queryset = queryset.filter(keyword_filter)
        if int(NO_TAG_ID) in tags:
            tagged_tool_uids = ToolTag.objects.values_list("tool_uid", flat=True).distinct()
            queryset = queryset.exclude(uid__in=tagged_tool_uids)
        elif tags:
            tagged_tool_uids = ToolTag.objects.filter(tag_id__in=tags).values_list("tool_uid", flat=True).distinct()
            queryset = queryset.filter(uid__in=tagged_tool_uids)

        # 排序逻辑：查询最近使用时保持原 Redis 顺序；否则显式 sort 优先，默认保持旧逻辑
        if recent_used and recent_tool_uids:
            queryset = preserved_order_sort(
                queryset,
                ordering_field="uid",
                value_list=recent_tool_uids,
            )
        elif order_fields:
            queryset = queryset.order_by(*order_fields)
        else:
            queryset = queryset.order_by("-favorite", "name")

        tools = list(queryset)
        tool_uids = [t.uid for t in tools]

        # 查询 tags
        tool_tags = ToolTag.objects.filter(tool_uid__in=tool_uids)
        tag_map = defaultdict(list)
        for t in tool_tags:
            tag_map[t.tool_uid].append(str(t.tag_id))

        # 查询关联策略
        strategy_map = defaultdict(list)
        rows = StrategyTool.objects.filter(tool_uid__in=tool_uids).values("tool_uid", "strategy_id")
        for row in rows:
            strategy_map[row["tool_uid"]].append(row["strategy_id"])

        for tool in tools:
            setattr(tool, "tags", tag_map.get(tool.uid, []))
            setattr(tool, "strategies", strategy_map.get(tool.uid, []))
        BindingMetadataHelper.attach_binding_metadata(
            tools,
            resource_type=ResourceVisibilityType.TOOL,
            id_attr="uid",
        )
        self.attach_visibility_metadata(tools)

        return ToolListResponseSerializer(instance=tools, many=True).data


class DeleteTool(ToolBase):
    name = gettext_lazy("删除工具")
    RequestSerializer = ToolRetrieveRequestSerializer

    @transaction.atomic
    def perform_request(self, validated_request_data):
        uid = validated_request_data["uid"]
        self.deletel_enum_mappings(tool_uid=uid)
        Tool.delete_by_uid(uid)


class GetToolEnumMappingByCollectionKeys(ToolBase):
    """
    获取某个工具的某个集合中的某个枚举值的信息。可以一次性获取多个不同集合中的多个枚举值的信息。
    请求：
    ```
        {
            "collection_keys": [
                {"collection_id": "status_collection_112233", "key": "1"},
                {"collection_id": "user_collection_112233", "key": "2"},
            ],
            "related_type": "tool",
            "related_object_id": 1 # 工具UID
        }
    ```
    响应：
    ```
    [{"collection_id":"status_collection_112233","key": "1", "name": "未处理"},
    {"collection_id":"user_collection_112233","key": "2", "name": "张三"}]
    ```

    可选权限上下文（调用方透传）：
    - caller_resource_type：调用方资源类型（当前支持：risk）
    - caller_resource_id：调用方资源ID（如风险ID）
    行为：若提供且鉴权通过，则基于调用方上下文放行（跳过原有权限）；若鉴权失败，返回标准权限异常。
    """

    name = gettext_lazy("获取某个策略的某个集合中的某个枚举值的信息")
    RequestSerializer = EnumMappingByCollectionKeysWithCallerSerializer
    ResponseSerializer = EnumMappingSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        validated_request_data["related_type"] = EnumMappingRelatedType.TOOL.value
        # 特殊权限分支：当来自调用方上下文（目前支持 risk）时，校验其权限
        validated_request_data["current_type"] = CurrentType.TOOL.value
        validated_request_data["current_object_id"] = validated_request_data["related_object_id"]
        should_skip_permission_from(validated_request_data, get_request_username())
        return resource.meta.get_enum_mapping_by_collection_keys(**validated_request_data)


class GetToolEnumMappingByCollection(ToolBase):
    """
    获取某个工具的某个集合中的所有枚举值的信息。
    请求：
    ```
    {
        "collection_id": "status_collection_112233",
        "related_type": "tool",
        "related_object_id": 1 工具UID
    }
    ```
    响应：
    ```
    [{"collection_id":"status_collection_112233","key": "1", "name": "未处理"},
    {"collection_id":"status_collection_112233","key": "2", "name": "已处理"}]
    ```

    可选权限上下文（调用方透传）：
    - caller_resource_type：调用方资源类型（当前支持：risk）
    - caller_resource_id：调用方资源ID（如风险ID）
    行为：若提供且鉴权通过，则基于调用方上下文放行（跳过原有权限）；若鉴权失败，返回标准权限异常。
    """

    name = gettext_lazy("获取某个策略的某个集合中的所有枚举值的信息")
    RequestSerializer = EnumMappingByCollectionWithCallerSerializer
    ResponseSerializer = EnumMappingSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        validated_request_data["related_type"] = EnumMappingRelatedType.TOOL.value
        # 特殊权限分支：当来自调用方上下文（目前支持 risk）时，校验其权限
        validated_request_data["current_type"] = CurrentType.TOOL.value
        validated_request_data["current_object_id"] = validated_request_data["related_object_id"]
        should_skip_permission_from(validated_request_data, get_request_username())
        return resource.meta.get_enum_mapping_by_collection(**validated_request_data)


class CreateTool(ToolBase):
    """
    ```json
    请求参数：data_search 工具类型
    {
      "tool_type": "data_search",
      "name": "xxx",
      "description": "xxx",
      "tags": ["xxx", "xxx"],
      "data_search_config_type": "sql",  // 仅 data_search 类型工具需要
      "config": {
        "referenced_tables": [
          {
            "table_name": "xxx"
          },
          {
            "table_name": "xxx"
          }
        ],
        "input_variable": [
          {
            "raw_name": "xxx",
            "display_name": "xxx",
            "description": "xxx",
            "required": false,
            "field_category": "input",
            "choices": [{"key": "xxx", "name": "xxx"}, {"key": "xxx", "name": "xxx"}]  key不可以重复
            "default_value": "xxx"
          }
        ],
        "output_fields": [
          {
            "raw_name": "xxx",
            "display_name": "xxx",
            "description": "xxx",
             "enum_mappings": {
                "mappings": [
                    {"key": "1", "name": "Running"},
                    {"key": "0", "name": "Stopped"}
                 ]
             }
            "drill_config": {
              "tool": {
                "uid": "XXX",
                "version": 1
              },
              "config": [
                {
             "target_value_type": "field",
             "target_value": "ip_address"  默认 None
             "source_field": "username"

                }
              ]
            }
          }
        ],
        "sql": "SELECT * FROM xxx WHERE $condition"
      }
    }
    请求参数：bk_vision 工具类型
    {
      "tool_type": "bk_vision",
      "name": "xxx",
      "description": "xxx",
      "tags": ["xxx"],
      "config": {
        "uid": "xxx",
        "input_variable": [
          {
            "raw_name": "test_field",
            "display_name": "测试字段",
            "description": "字段描述",
            "field_category": "button",
            "required": true,
            "default_value": "default_val"
          }
        ]
      }
    }
    响应结构：
    {
      "data": {
        "uid": "xxx",
        "version": xxx
      }
    }
    """

    name = gettext_lazy("新增工具")
    RequestSerializer = ToolCreateRequestSerializer
    ResponseSerializer = ToolResponseSerializer

    def perform_request(self, validated_request_data):
        validated_request_data["permission_owner"] = get_request_username()
        tool = create_tool_with_config(validated_request_data)
        config = validated_request_data.get("config", {})
        if tool.tool_type == ToolTypeEnum.DATA_SEARCH.value:
            # 使用 Pydantic 模型校验
            config_obj = SQLDataSearchConfig.model_validate(config)
            for output_field in config_obj.output_fields:
                enum_mappings = output_field.enum_mappings
                if enum_mappings:
                    self.updatel_enum_mappings(
                        enum_mapping=enum_mappings.model_dump(),
                        tool_uid=tool.uid,
                        field_name=output_field.raw_name,
                    )
        elif tool.tool_type == ToolTypeEnum.API.value:
            config_obj = ApiToolConfig.model_validate(config)
            self._handle_api_enum_mappings(tool.uid, config_obj)
        return tool


class UpdateTool(ToolBase):
    """
    ```json
    除了tags必须传，其他可修改字段改什么传什么
    响应结构：
     "data": {
            "uid": "xxx",
            "version": xxx
        },
    """

    name = gettext_lazy("编辑工具")
    RequestSerializer = ToolUpdateRequestSerializer
    ResponseSerializer = ToolResponseSerializer

    def create_tool_new_version(self, old_tool: Tool, validated_request_data: dict, updated_time: datetime):
        """
        创建工具新版本
        """

        new_config = validated_request_data["config"]
        new_name = validated_request_data.get("name", old_tool.name)
        new_tool_data = {
            "uid": old_tool.uid,
            "tool_type": old_tool.tool_type,
            "name": new_name,
            "description": validated_request_data.get("description", old_tool.description),
            "namespace": validated_request_data.get("namespace", old_tool.namespace),
            "version": old_tool.version + 1,
            "status": validated_request_data.get("status", old_tool.status),
            "config": new_config,
            "tags": validated_request_data.get("tags"),
            # 保持创建人与旧版本一致，避免因新版本创建导致创建人变更为当前操作者
            "created_by": old_tool.created_by,
            # 保持创建时间与旧版本一致
            "created_at": old_tool.created_at,
            "updated_time": updated_time,
        }
        change_permission_owner = old_tool.has_change_permission_owner(new_config)
        new_tool_data["permission_owner"] = (
            get_request_username() if change_permission_owner else old_tool.get_permission_owner()
        )
        if old_tool.tool_type == ToolTypeEnum.DATA_SEARCH:
            new_config_obj = SQLDataSearchConfig.model_validate(new_config)
            new_tool_data["data_search_config_type"] = old_tool.data_search_config.data_search_config_type
            for output_field in new_config_obj.output_fields:
                enum_mappings = output_field.enum_mappings
                if enum_mappings:
                    self.updatel_enum_mappings(
                        enum_mapping=enum_mappings.model_dump(),
                        tool_uid=old_tool.uid,
                        field_name=output_field.raw_name,
                    )
        elif old_tool.tool_type == ToolTypeEnum.API:
            new_config_obj = ApiToolConfig.model_validate(new_config)
            self._handle_api_enum_mappings(old_tool.uid, new_config_obj)

        return create_tool_with_config(new_tool_data)

    @transaction.atomic
    def perform_request(self, validated_request_data: dict):
        uid = validated_request_data["uid"]
        tool = Tool.last_version_tool(uid)
        updated_time = validated_request_data.pop("updated_time", None)
        if not tool:
            raise ToolDoesNotExist()
        # 如果配置有变更则创建新版本
        if validated_request_data.get("config") and validated_request_data.get("config") != tool.config:
            new_tool = self.create_tool_new_version(
                old_tool=tool, validated_request_data=validated_request_data, updated_time=updated_time
            )
            if tool.is_bkvision:
                update_bkvision_config(tool_uid=uid)
            return new_tool
        # 配置未变更则更新原版本
        tag_names = validated_request_data.pop("tags")
        for key, value in validated_request_data.items():
            setattr(tool, key, value)
        tool.save(update_fields=validated_request_data.keys())

        sync_resource_tags(
            resource_uid=tool.uid,
            tag_names=tag_names,
            relation_model=ToolTag,
            relation_resource_field="tool_uid",
        )
        return tool


class ExecuteTool(ToolBase):
    """
    工具执行

    通用变量输入格式说明：
    1. input（输入框）
        ```json
            {
                "raw_name": "string",
                "value": "admin"
            }
        ```
    2. number_input（数字输入框）
        ```json
            {
                "raw_name": "number",
                "value": 123
            }
        ```
    3. time_select（时间选择器）
        ```json
            {
                "raw_name": "datetime",
                "value": "2023-01-01 12:00:00" // 默认+8时间，实际 SQL 中会转为毫秒时间戳
            }
        ```
    4. person_select（人员选择器）
        多值传递采用列表
        ```json
            {
                "raw_name": "usernames",
                "value": ["user1", "user2"]
            }
        ```
        单值也可以直接传递
        ```json
            {
                "raw_name": "usernames",
                "value": "user1" // 单个值会自动转为列表 ["user1"]
            }
        ```
        注意：对于 tool_type 为 api 的工具，人员选择器的值会转换为逗号拼接的字符串传递给三方接口
        （例如：["user1", "user2"] 会转为 "user1,user2"）
    5. time_range_select（时间范围选择器）
        ```json
            {
                "raw_name": "datetime_range",
                "value": ["2023-01-01 12:00:00", "2023-01-31 12:00:00"]
            }
        ```
    6. multiselect（下拉列表）
        ```json
            {
                "raw_name": "multiselect",
                "value": ["option1", "option2"]
            }
        ```

    重要提示：
    - 对于非必填变量，如果用户未输入值，前端应传入 `value: null`（或 JSON 中的 `null`）来表示用户未输入
    - 后台会忽略 `value` 为 `null` 的非必填变量，不会进行变量替换或校验
    - 必填变量必须提供有效的值，不能为 `null`

    1. tool_type 为 data_search
        params:
        ```json
        {
            "uid": "sql_tool_123",
            "params": {
                "tool_variables": [
                    {
                        "raw_name": "username",
                        "value": "admin"
                    }
                ],
                "page": 1,
                "page_size": 100
            },
            "caller_resource_type": "risk",
            "caller_resource_id": "R123"
        }
        ```
        response:
        ```json
        {
            "data": {
                "query_sql": "SELECT * FROM mocked_table",
                "count_sql": "SELECT COUNT(*) FROM mocked_table",
                "results": [
                    {
                        "field1": "value1"
                    },
                    {
                        "field2": "value2"
                    }
                ],
                "total": 2,
                "num_pages": 100,
                "page": 1
            },
            "tool_type": "data_search"
        }
        ```

    2. tool_type 为 api
        params:
        ```json
        {
            "uid": "api_tool_123",
            "params": {
                "tool_variables": [
                    {"raw_name": "path_id", "value": 123, "position": "path"},
                    {"raw_name": "query_param", "value": "test", "position": "query"}
                ]
            }
        }
        ```
        response:
        ```json
        {
            "data": {
                "status_code": 200,
                "result": {
                    "key": "value"
                }
            },
            "tool_type": "api"
        }
        ```

    3. tool_type 为 bk_vision
        params:
        ```json
        {
            "uid": "vision_tool_123",
            "params": {},
            "caller_resource_type": "risk",
            "caller_resource_id": "R123"
        }
        ```
        response:
        ```json
        {
            "data": {
                "panel_id": "panel_123"
            },
            "tool_type": "bk_vision"
        }
        ```

    4. 权限上下文（可选）
        - 携带调用方上下文时，系统将基于调用方资源做统一鉴权：
            - `caller_resource_type`：调用方资源类型（当前支持：`risk`）
            - `caller_resource_id`：调用方资源实例 ID（如风险ID）
            - `drill_field`：指定使用哪个字段的 drill_config 进行变量值校验
            - `event_start_time`/`event_end_time`：事件时间范围（用于 list_event 获取事件数据）
        - 行为说明：
            - 命中且有权限：跳过原有工具权限校验，直接执行
            - 命中但无权限：返回标准权限异常（包含可申请信息）
    """

    name = gettext_lazy("工具执行")
    RequestSerializer = ExecuteToolReqSerializer
    ResponseSerializer = ExecuteToolRespSerializer

    def _get_user_allowed_scopes(self, username: str) -> Tuple[List[str], List[str]]:
        """
        获取用户有权限的场景和系统列表。
        """
        scope_permission = ScopePermission(username=username)
        scene_ids = scope_permission.get_scene_ids(ScopeContext(ScopeType.CROSS_SCENE), ActionEnum.VIEW_SCENE)
        system_ids = scope_permission.get_system_ids(ScopeContext(ScopeType.CROSS_SYSTEM), ActionEnum.VIEW_SYSTEM)

        return [str(scene_id) for scene_id in scene_ids], list(system_ids)

    def _validate_default_value_permissions(self, tool, params, username):
        """校验执行时默认值的权限

        校验规则：
        1. 仅对 is_show=False（用户不可见）的参数做校验；is_show=True 的参数
           用户可自由修改，无需校验（用户可见场景）。
        2. 允许用户使用其权限范围内场景/系统配置的默认值覆盖。
        """
        config = tool.config
        if not config:
            return

        default_value_overrides = config.get("default_value_overrides", {})
        if not default_value_overrides:
            return

        # 获取用户有权限的场景/系统列表
        user_allowed_scene_ids, user_allowed_system_ids = self._get_user_allowed_scopes(username)

        # 获取工具的输入变量配置
        input_variables_config = config.get("input_variable", [])

        # 获取用户输入的变量值
        tool_variables = params.get("tool_variables", [])

        # 收集用户有权限的场景/系统允许的默认值
        allowed_defaults = {}

        # 场景级别的默认值
        scenes_overrides = default_value_overrides.get("scenes", {})
        for scene_id, overrides in scenes_overrides.items():
            if scene_id in user_allowed_scene_ids and isinstance(overrides, dict):
                for raw_name, default_value in overrides.items():
                    if raw_name:
                        allowed_defaults.setdefault(raw_name, []).append(default_value)

        # 系统级别的默认值
        systems_overrides = default_value_overrides.get("systems", {})
        for system_id, overrides in systems_overrides.items():
            if system_id in user_allowed_system_ids and isinstance(overrides, dict):
                for raw_name, default_value in overrides.items():
                    if raw_name:
                        allowed_defaults.setdefault(raw_name, []).append(default_value)

        input_variable_map = {}
        for var in tool_variables:
            raw_name = var.get("raw_name")
            if not raw_name:
                continue
            input_variable_map[raw_name] = var.get("value")
        input_var_config_map = {}
        for var in input_variables_config:
            raw_name = var.get("raw_name")
            if raw_name:
                input_var_config_map[raw_name] = var

        # 校验 is_show=False 的参数
        for raw_name, value in input_variable_map.items():

            input_var_config = input_var_config_map.get(raw_name, {})
            # 仅校验 is_show=False 的参数
            if not input_var_config.get("is_show", True):
                # 获取工具的原始默认值
                original_default = input_var_config.get("default_value")

                # 如果用户在允许的场景/系统下有默认值覆盖，则允许使用覆盖值
                # 如果用户传入的值不在允许的范围内，则提示越权
                if raw_name in allowed_defaults:
                    if value not in allowed_defaults[raw_name] and value != original_default:
                        raise PermissionException(
                            action_name=gettext_lazy("使用隐藏参数 %(var_name)s 的默认值") % {"var_name": raw_name},
                            permission=gettext("参数 %(var_name)s 的默认值不存在") % {"var_name": raw_name},
                        )

                else:
                    if value != original_default:
                        raise PermissionException(
                            action_name=gettext_lazy("使用隐藏参数 %(var_name)s 的默认值") % {"var_name": raw_name},
                            permission=gettext("参数 %(var_name)s 不可见，只能使用默认值") % {"var_name": raw_name},
                        )

    def perform_request(self, validated_request_data):
        """
        1. 获取工具
        2. 执行工具
        """

        uid = validated_request_data["uid"]
        params = validated_request_data["params"]
        tool: Tool = Tool.last_version_tool(uid=uid)
        if not tool:
            raise ToolDoesNotExist()

        # 特殊权限分支：当来自调用方上下文（目前支持 risk）时，校验其权限，命中则跳过原有工具权限校验
        check_request_data = deepcopy(validated_request_data)
        check_request_data["caller_validated"] = True
        check_request_data["current_type"] = CurrentType.TOOL.value
        check_request_data["current_object_id"] = uid
        check_request_data["tool_variables"] = params.get("tool_variables", [])
        should_skip_permission_from(check_request_data, get_request_username())
        # 校验默认值的权限
        self._validate_default_value_permissions(tool, params, get_request_username())

        current_user = get_request_username()
        try:
            recent_tool_usage_manager.record_usage(current_user, uid)
        except Exception as e:  # NOCC:broad-except(需要处理所有错误)
            logger.error(
                f"[record_tool_usage] Uid:{uid}; Current User:{current_user}; "
                f"Err: {e}; Detail: {traceback.format_exc()}"
            )
        executor = ToolExecutorFactory(sql_analyzer_cls=SqlQueryAnalysis).create_from_tool(tool)

        data = executor.execute(params).model_dump()
        return {"data": data, "tool_type": tool.tool_type}


class ExecuteToolAPIGW(ExecuteTool):
    """
    工具执行(APIGW)，仅校验 app_code
    """

    def perform_request(self, validated_request_data):
        get_app_info()
        uid = validated_request_data["uid"]
        params = validated_request_data["params"]
        tool: Tool = Tool.last_version_tool(uid=uid)
        if not tool:
            raise ToolDoesNotExist()
        if tool.status != PanelStatus.PUBLISHED:
            raise ToolNotPublished()

        current_user = "admin"
        try:
            recent_tool_usage_manager.record_usage(current_user, uid)
        except Exception as e:  # NOCC:broad-except(需要处理所有错误)
            logger.error(
                f"[record_tool_usage] Uid:{uid}; Current User:{current_user}; "
                f"Err: {e}; Detail: {traceback.format_exc()}"
            )
        executor = ToolExecutorFactory(sql_analyzer_cls=SqlQueryAnalysis).create_from_tool(tool)

        data = executor.execute(params).model_dump()
        return {"data": data, "tool_type": tool.tool_type}


class ToolExecuteDebug(ToolBase):
    """
    工具执行调试

    允许用户在不保存工具的情况下基于配置直接调试执行。
    请求参数：
    - tool_type：工具类型（目前支持 data_search/sql、api）
    - config：与工具保存时一致的配置
    - params：与正式执行时一致的入参
    响应结构与 ExecuteTool 相同。
    """

    name = gettext_lazy("工具执行调试")
    RequestSerializer = ToolExecuteDebugSerializer
    ResponseSerializer = ExecuteToolRespSerializer

    def perform_request(self, validated_request_data):
        tool_type = validated_request_data["tool_type"]
        config = validated_request_data["config"]
        params = validated_request_data["params"]

        executor_factory = ToolExecutorFactory(sql_analyzer_cls=SqlQueryAnalysis)
        executor = executor_factory.create_from_config(tool_type=tool_type, config=config)
        data = executor.execute(params).model_dump()
        return {"data": data, "tool_type": tool_type}


class ListToolAll(ToolBase):
    name = gettext_lazy("工具列表(all)")
    RequestSerializer = ListToolAllRequestSerializer
    many_response_data = True
    ResponseSerializer = ToolListAllResponseSerializer

    def validate_response_data(self, response_data):
        return response_data

    def filter_queryset_by_scope_relation(self, queryset, validated_request_data: dict):
        """按 scope 关联关系过滤全量工具，不校验当前用户权限。"""
        scope_type = validated_request_data.get("scope_type")
        binding_type = validated_request_data.get("binding_type")
        if not scope_type:
            binding_filter = binding_type or BindingType.PLATFORM_BINDING
            bindings = ResourceBinding.objects.filter(
                resource_type=ResourceVisibilityType.TOOL,
                binding_type=binding_filter,
            )
            if binding_filter == BindingType.SCENE_BINDING:
                bindings = bindings.filter(binding_scenes__scene__is_deleted=False)
            tool_uids = bindings.values_list("resource_id", flat=True)
            return queryset.filter(uid__in=tool_uids)

        scope = ScopeContext(
            scope_type=scope_type,
            scope_id=validated_request_data.get("scope_id"),
        )
        scene_ids: List[int] = []
        system_ids: List[str] = []
        if scope.scope_type == ScopeType.SCENE:
            scene_ids = [int(scope.scope_id)]
        elif scope.scope_type == ScopeType.CROSS_SCENE:
            scene_ids = list(Scene.objects.values_list("scene_id", flat=True))
        elif scope.scope_type == ScopeType.SYSTEM:
            system_ids = [str(scope.scope_id)]
        elif scope.scope_type == ScopeType.CROSS_SYSTEM:
            system_ids = list(System.objects.values_list("system_id", flat=True))

        return CompositeScopeFilter.filter_queryset(
            queryset=queryset,
            binding_type=binding_type,
            scene_id=scene_ids,
            system_id=system_ids,
            resource_type=ResourceVisibilityType.TOOL,
            pk_field="uid",
        )

    def perform_request(self, validated_request_data):
        current_user = get_request_username()

        # 构建收藏状态子查询（使用 tool_uid 关联，确保版本更新后收藏状态正确）
        favorite_subquery = ToolFavorite.objects.filter(tool_uid=OuterRef("uid"), username=current_user)
        tool_qs = Tool.all_latest_tools().annotate(favorite=Exists(favorite_subquery))
        tool_qs = self.filter_queryset_by_scope_relation(tool_qs, validated_request_data).order_by("name")
        status = validated_request_data.get("status")
        if status:
            tool_qs = tool_qs.filter(status=status)

        name_list = validated_request_data.get("name", [])
        description_list = validated_request_data.get("description", [])
        tool_type_list = validated_request_data.get("tool_type", [])
        created_by_list = validated_request_data.get("created_by", [])
        updated_by_list = validated_request_data.get("updated_by", [])

        def apply_multi_value_filter(qs, field_name, values, lookup='icontains'):
            q_filter = Q()
            for value in values:
                if value:
                    q_filter |= Q(**{f"{field_name}__{lookup}": value})
            return qs.filter(q_filter) if q_filter else qs

        if name_list:
            tool_qs = apply_multi_value_filter(tool_qs, "name", name_list)
        if description_list:
            tool_qs = apply_multi_value_filter(tool_qs, "description", description_list)
        if tool_type_list:
            tool_qs = tool_qs.filter(tool_type__in=tool_type_list)
        if created_by_list:
            tool_qs = tool_qs.filter(created_by__in=created_by_list)
        if updated_by_list:
            tool_qs = tool_qs.filter(updated_by__in=updated_by_list)

        tools = list(tool_qs)

        tool_uids = [tool.uid for tool in tools]
        tool_tags = ToolTag.objects.filter(tool_uid__in=tool_uids)

        tag_map = defaultdict(list)
        for t in tool_tags:
            tag_map[t.tool_uid].append(str(t.tag_id))
        strategy_map = defaultdict(list)
        rows = StrategyTool.objects.filter(tool_uid__in=tool_uids).values("tool_uid", "strategy_id")
        for row in rows:
            strategy_map[row["tool_uid"]].append(row["strategy_id"])

        for tool in tools:
            setattr(tool, "tags", tag_map.get(tool.uid, []))
            setattr(tool, "strategies", strategy_map.get(tool.uid, []))
        BindingMetadataHelper.attach_binding_metadata(
            tools,
            resource_type=ResourceVisibilityType.TOOL,
            id_attr="uid",
        )
        serialized_data = self.ResponseSerializer(tools, many=True).data
        return serialized_data


class ExportToolData(ToolBase):
    name = gettext_lazy("工具执行数据导出")

    def perform_request(self, validated_request_data):
        pass


class GetToolDetail(ToolBase):
    name = gettext_lazy("获取工具详情")
    RequestSerializer = ToolRetrieveRequestSerializer
    ResponseSerializer = ToolRetrieveResponseSerializer

    def validate_response_data(self, response_data):
        return response_data

    def _is_tool_manager(self, username: str, tool_uid: str) -> bool:
        binding = ResourceBinding.objects.filter(
            resource_type=ResourceVisibilityType.TOOL,
            resource_id=tool_uid,
        ).first()
        if not binding:
            return False

        permission = Permission(username=username)

        if binding.binding_type == BindingType.PLATFORM_BINDING:
            return permission.has_action_any_permission(ActionEnum.MANAGE_PLATFORM)

        if binding.binding_type == BindingType.SCENE_BINDING:
            scene_id = (
                binding.binding_scenes.filter(scene__is_deleted=False, scene__status=SceneStatus.ENABLED)
                .values_list("scene_id", flat=True)
                .first()
            )
            if not scene_id:
                return False
            scene_resource = ResourceEnum.SCENE.create_instance(scene_id)
            return permission.is_allowed(ActionEnum.MANAGE_SCENE, [scene_resource], raise_exception=False)

        return False

    def perform_request(self, validated_request_data):
        uid = validated_request_data["uid"]
        tool = Tool.last_version_tool(uid=uid)
        if not tool:
            raise ToolDoesNotExist()

        current_user = get_request_username()

        tag_ids = list(ToolTag.objects.filter(tool_uid=tool.uid).values_list("tag_id", flat=True))
        strategies_ids = list(StrategyTool.objects.filter(tool_uid=tool.uid).values_list("strategy_id", flat=True))
        setattr(tool, "tags", [str(tid) for tid in tag_ids])
        setattr(tool, "strategies", [str(sid) for sid in strategies_ids])

        # 查询当前用户对该工具的收藏状态（使用 tool_uid 关联）
        favorite = ToolFavorite.objects.filter(tool_uid=tool.uid, username=current_user).exists()
        setattr(tool, "favorite", favorite)

        # 如果是SQL工具且有引用表，检查表权限
        if tool.tool_type == ToolTypeEnum.DATA_SEARCH and tool.config.get("referenced_tables"):
            tables = [table["table_name"] for table in tool.config["referenced_tables"]]
            auth_results = {
                item["object_id"]: item
                for item in resource.tool.user_query_table_auth_check(
                    {"tables": tables, "username": tool.get_permission_owner()}
                )
            }
            # 将权限信息添加到每个表
            for table in tool.config["referenced_tables"]:
                table["permission"] = auth_results.get(table["table_name"], {})

        # 获取场景和系统信息
        scene_id = validated_request_data.get("scene_id")
        system_id = validated_request_data.get("system_id")
        # 根据场景/系统ID动态覆盖默认值
        if scene_id or system_id:
            self._override_default_values(tool, scene_id, system_id)

        data = self.ResponseSerializer(instance=tool).data

        # 权限判定仅用于 API 配置脱敏：平台工具需平台管理员，场景工具需对应场景管理员
        is_tool_manager = self._is_tool_manager(current_user, tool.uid)

        if not is_tool_manager and tool.tool_type == ToolTypeEnum.API.value:
            if "config" in data and "api_config" in data["config"]:
                data["config"]["api_config"] = None

        return data

    def _override_default_values(self, tool, scene_id, system_id):
        """根据场景/系统ID动态覆盖默认值

        default_value_overrides 位于 config 层级，结构：
        {
            "scenes": {
                "场景ID1": {"raw_name1": "默认值1", "raw_name2": "默认值2"}
            },
            "systems": {
                "系统ID1": {"raw_name1": "默认值3"}
            }
        }
        """
        # 如果没有场景或系统信息，直接返回
        if not scene_id and not system_id:
            return

        # 获取工具配置
        config = tool.config
        if not config:
            return

        # 从 config 层级获取 default_value_overrides
        default_value_overrides = config.get("default_value_overrides", {})
        if not default_value_overrides:
            return

        # 获取输入变量配置
        input_variables = config.get("input_variable", [])
        if not input_variables:
            return

        # 收集当前场景/系统的默认值覆盖映射
        # 结构: {raw_name: overridden_default_value}
        overridden_defaults = {}

        # 优先检查场景级别的参数覆盖
        if scene_id:
            scene_id_str = str(scene_id)
            scene_overrides = default_value_overrides.get("scenes", {})
            if scene_id_str in scene_overrides:
                # scene_overrides[scene_id_str] 是 {raw_name: default_value} 字典
                scene_defaults = scene_overrides[scene_id_str]
                if isinstance(scene_defaults, dict):
                    overridden_defaults.update(scene_defaults)

        # 其次检查系统级别的参数覆盖（会覆盖场景级别的同名参数）
        if system_id:
            system_overrides = default_value_overrides.get("systems", {})
            if system_id in system_overrides:
                # system_overrides[system_id] 是 {raw_name: default_value} 字典
                system_defaults = system_overrides[system_id]
                if isinstance(system_defaults, dict):
                    overridden_defaults.update(system_defaults)

        # 根据收集到的映射，覆盖输入变量的默认值
        for var_config in input_variables:
            raw_name = var_config.get("raw_name")
            if not raw_name:
                continue

            if raw_name in overridden_defaults:
                var_config["default_value"] = overridden_defaults[raw_name]


class SqlAnalyseResource(ToolBase, Resource):
    """SQL解析接口

    接口功能:
        解析SQL语句，返回引用的表、变量和结果字段的详细信息

    请求示例:
        {
            "sql": "SELECT u.id, u.name FROM users u WHERE u.age > :min_age",
            "dialect": "mysql"
        }

    响应示例:
        {
            "referenced_tables": [
                {
                    "table_name": "users",
                    "alias": "u"
                }
            ],
            "sql_variables": [
                {
                    "raw_name": ":min_age",
                    "description": null,
                    "required": true,
                    "display_name": null
                }
            ],
            "result_fields": [
                {
                    "display_name": "id",
                    "raw_name": "id"
                },
                {
                    "display_name": "name",
                    "raw_name": "name"
                }
            ],
            "original_sql": "SELECT u.id, u.name FROM users u WHERE u.age > :min_age",
            "dialect": "mysql"
        }
    """

    name = gettext_lazy("SQL解析")
    RequestSerializer = SqlAnalyseRequestSerializer
    ResponseSerializer = SqlAnalyseResponseSerializer

    def get_permission_owner(self, validated_request_data: dict, parsed_def: ParsedSQLInfo) -> str:
        return get_request_username()

    def perform_request(self, validated_request_data):
        analyser = SqlQueryAnalysis(
            validated_request_data["sql"],
            dialect=validated_request_data.get("dialect") or None,
        )
        analyser.parse_sql()
        parsed_def = analyser.get_parsed_def()
        result = parsed_def.model_dump()

        # 场景表权限校验：场景授权的表 OR 工具责任人有权限的表
        scene_id = validated_request_data.get("scene_id")
        if scene_id and result['referenced_tables']:
            authorized = set(SceneDataFilter.get_table_ids(scene_id))
            tables_need_check = [
                t['table_name'] for t in result['referenced_tables'] if t['table_name'] not in authorized
            ]
            if tables_need_check:
                user_id = self.get_permission_owner(validated_request_data, parsed_def)
                bulk_resp = resource.tool.user_query_table_auth_check(
                    {"tables": tables_need_check, "username": user_id}
                )
                for rt in bulk_resp:
                    if not rt.get("result"):
                        raise DataSearchTablePermission(rt.get("user_id"), rt.get("object_id"))

        # 检查用户对引用表的查询权限
        if validated_request_data["with_permission"] and result['referenced_tables']:
            tables = [table['table_name'] for table in result['referenced_tables']]
            auth_results = {
                item["object_id"]: item
                for item in resource.tool.user_query_table_auth_check(
                    {"tables": tables, "username": self.get_permission_owner(validated_request_data, parsed_def)}
                )
            }
            for table in result['referenced_tables']:
                table['permission'] = auth_results[table['table_name']]
        return result


class SqlAnalyseWithToolResource(SqlAnalyseResource):
    name = gettext_lazy("SQL解析(编辑工具)")
    RequestSerializer = SqlAnalyseWithToolRequestSerializer

    def get_permission_owner(self, validated_request_data: dict, parsed_def: ParsedSQLInfo) -> str:
        tool = Tool.last_version_tool(uid=validated_request_data["uid"])
        if not tool:
            raise ToolDoesNotExist()
        if (
            tool.tool_type != ToolTypeEnum.DATA_SEARCH
            and tool.data_search_config.data_search_config_type != DataSearchConfigTypeEnum.SQL.value
        ):
            raise ToolTypeNotSupport()
        old_sql_parsed_def = SqlQueryAnalysis(sql=tool.data_search_config.sql).get_parsed_def()
        old_sql_tables = {table.table_name for table in old_sql_parsed_def.referenced_tables}
        new_sql_tables = {table.table_name for table in parsed_def.referenced_tables}
        if new_sql_tables - old_sql_tables:
            return get_request_username()
        return tool.get_permission_owner()


class UserQueryTableAuthCheck(ToolBase):
    """
    用户查询权限校验
    """

    name = gettext_lazy("用户查询权限批量校验")
    RequestSerializer = UserQueryTableAuthCheckReqSerializer
    many_response_data = True
    ResponseSerializer = UserAuthCheckRespSerializer

    def perform_request(self, validated_request_data):
        tables: List[str] = validated_request_data["tables"]
        username = validated_request_data.get("username") or get_request_username()
        permissions = [
            {
                "user_id": username,
                "action_id": UserAuthActionEnum.RT_QUERY.value,
                "object_id": table,
            }
            for table in tables
        ]
        return api.bk_base.user_auth_batch_check({"permissions": permissions})


class FavoriteTool(ToolBase):
    """收藏/取消收藏工具"""

    name = gettext_lazy("收藏工具")
    RequestSerializer = ToolFavoriteReqSerializer
    ResponseSerializer = ToolFavoriteRespSerializer

    def perform_request(self, validated_request_data):
        uid = validated_request_data["uid"]
        favorite = validated_request_data["favorite"]
        username = get_request_username()

        tool = Tool.last_version_tool(uid=uid)
        if not tool:
            raise ToolDoesNotExist()

        if favorite:
            ToolFavorite.objects.get_or_create(tool_uid=tool.uid, username=username)
        else:
            ToolFavorite.objects.filter(tool_uid=tool.uid, username=username).delete()

        return {"favorite": favorite}


class GetToolDetailByNameAPIGW(ToolBase):
    """
    通过工具名称获取工具详情(APIGW)

    仅做应用权限校验，不校验用户权限。
    支持 lite_mode 模式，默认只返回 input_variable 定义。

    请求参数：
    ```json
    {
        "name": "工具名称",
        "lite_mode": true  // 可选，默认 true，只返回 input_variable
    }
    ```

    响应结构（lite_mode=true）：
    ```json
    {
        "uid": "xxx",
        "name": "xxx",
        "tool_type": "data_search",
        "version": 1,
        "description": "xxx",
        "namespace": "xxx",
        "config": {
            "input_variable": [...]
        }
    }
    ```

    响应结构（lite_mode=false）：返回完整的工具配置
    """

    name = gettext_lazy("通过名称获取工具详情(APIGW)")
    RequestSerializer = GetToolDetailByNameAPIGWRequestSerializer
    ResponseSerializer = GetToolDetailByNameAPIGWResponseSerializer

    def validate_response_data(self, response_data):
        return response_data

    def perform_request(self, validated_request_data):
        from core.utils.tools import get_app_info

        # 仅做应用权限校验
        get_app_info()

        tool_name = validated_request_data["name"]
        lite_mode = validated_request_data.get("lite_mode", True)

        # 通过名称查找最新版本的工具
        tool = Tool.all_latest_tools().filter(name=tool_name).first()
        if not tool:
            raise ToolDoesNotExist()
        if tool.status != PanelStatus.PUBLISHED:
            raise ToolNotPublished()

        serializer = GetToolDetailByNameAPIGWResponseSerializer(tool, lite_mode=lite_mode)
        return serializer.data


# ==================== 场景工具管理 ====================


class CreatePlatformSceneTool(CreateTool):
    """创建平台级场景工具（继承 CreateTool，复用核心创建逻辑）"""

    name = gettext_lazy("创建平台级场景工具")
    RequestSerializer = PlatformSceneToolCreateRequestSerializer

    def perform_request(self, validated_request_data):
        from services.web.scene.constants import (
            BindingType,
            PanelStatus,
            ResourceVisibilityType,
            VisibilityScope,
        )
        from services.web.scene.models import (
            ResourceBinding,
            ResourceBindingScene,
            ResourceBindingSystem,
        )

        visibility_data = validated_request_data.pop("visibility", None) or {}
        validated_request_data.setdefault("status", PanelStatus.UNPUBLISHED)

        with transaction.atomic():
            # 复用父类 CreateTool 的核心创建逻辑
            tool = super().perform_request(validated_request_data)

            # 创建平台级绑定关系
            binding = ResourceBinding.objects.create(
                resource_type=ResourceVisibilityType.TOOL,
                resource_id=tool.uid,
                binding_type=BindingType.PLATFORM_BINDING,
                visibility_type=VisibilityScope.ALL_VISIBLE,
            )

            # 处理可见范围配置
            if visibility_data:
                binding.visibility_type = visibility_data.get("visibility_type", VisibilityScope.ALL_VISIBLE)
                binding.save(update_fields=["visibility_type"])
                for sid in visibility_data.get("scene_ids", []):
                    ResourceBindingScene.objects.create(binding=binding, scene_id=sid)
                for sys_id in visibility_data.get("system_ids", []):
                    ResourceBindingSystem.objects.create(binding=binding, system_id=sys_id)
            self._ensure_binding_integrity_or_raise(binding)

        return tool


class UpdatePlatformSceneTool(UpdateTool):
    """编辑平台级场景工具（继承 UpdateTool，复用核心更新逻辑）"""

    name = gettext_lazy("编辑平台级场景工具")
    RequestSerializer = PlatformSceneToolUpdateRequestSerializer

    def perform_request(self, validated_request_data):
        from services.web.scene.constants import (
            BindingType,
            ResourceVisibilityType,
            VisibilityScope,
        )
        from services.web.scene.models import (
            ResourceBinding,
            ResourceBindingScene,
            ResourceBindingSystem,
        )
        from services.web.tool.exceptions import SceneToolNotExist

        uid = validated_request_data.get("uid")
        # 通过 ResourceBinding 确认是平台级工具
        try:
            binding = ResourceBinding.objects.get(
                resource_type=ResourceVisibilityType.TOOL,
                resource_id=uid,
                binding_type=BindingType.PLATFORM_BINDING,
            )
        except ResourceBinding.DoesNotExist:
            raise SceneToolNotExist()

        visibility_data = validated_request_data.pop("visibility", None)
        with transaction.atomic():
            # 复用父类 UpdateTool 的核心更新逻辑
            result = super().perform_request(validated_request_data)

            # 处理可见范围配置
            if visibility_data:
                binding.visibility_type = visibility_data.get("visibility_type", VisibilityScope.ALL_VISIBLE)
                binding.save(update_fields=["visibility_type"])
                binding.binding_scenes.all().delete()
                for sid in visibility_data.get("scene_ids", []):
                    ResourceBindingScene.objects.create(binding=binding, scene_id=sid)
                binding.binding_systems.all().delete()
                for sys_id in visibility_data.get("system_ids", []):
                    ResourceBindingSystem.objects.create(binding=binding, system_id=sys_id)
            self._ensure_binding_integrity_or_raise(binding)

        return result


class DeletePlatformSceneTool(DeleteTool):
    """删除平台级场景工具（继承 DeleteTool，复用核心删除逻辑）"""

    name = gettext_lazy("删除平台级场景工具")

    @transaction.atomic
    def perform_request(self, validated_request_data):
        from services.web.scene.constants import (
            BindingType,
            PanelStatus,
            ResourceVisibilityType,
        )
        from services.web.scene.models import ResourceBinding
        from services.web.tool.exceptions import (
            SceneToolCannotDelete,
            SceneToolNotExist,
        )

        uid = validated_request_data.get("uid")
        # 通过 ResourceBinding 确认是平台级工具
        try:
            binding = ResourceBinding.objects.get(
                resource_type=ResourceVisibilityType.TOOL,
                resource_id=uid,
                binding_type=BindingType.PLATFORM_BINDING,
            )
        except ResourceBinding.DoesNotExist:
            raise SceneToolNotExist()
        self._ensure_binding_integrity_or_raise(binding)

        tool = Tool.last_version_tool(uid)
        if tool and tool.status == PanelStatus.PUBLISHED:
            raise SceneToolCannotDelete()

        # 删除绑定关系（级联删除关联的场景和系统）
        BindingMetadataHelper.delete_resource_binding(
            resource_id=uid,
            resource_type=ResourceVisibilityType.TOOL,
        )

        # 复用父类 DeleteTool 的核心删除逻辑（包含 enum mapping 清理）
        return super().perform_request(validated_request_data)


class PublishPlatformSceneTool(ToolBase):
    """上架/下架平台级场景工具"""

    name = gettext_lazy("上架/下架平台级场景工具")
    RequestSerializer = PlatformSceneToolPublishRequestSerializer
    ResponseSerializer = ToolPublishResponseSerializer

    def perform_request(self, validated_request_data):
        from services.web.scene.constants import (
            BindingType,
            PanelStatus,
            ResourceVisibilityType,
        )
        from services.web.scene.models import ResourceBinding
        from services.web.tool.exceptions import SceneToolNotExist

        uid = validated_request_data.get("uid")
        status = validated_request_data.get("status")
        # 通过 ResourceBinding 确认是平台级工具
        binding = ResourceBinding.objects.filter(
            resource_type=ResourceVisibilityType.TOOL,
            resource_id=uid,
            binding_type=BindingType.PLATFORM_BINDING,
        ).first()
        if not binding:
            raise SceneToolNotExist()

        tool = Tool.last_version_tool(uid)
        if not tool:
            raise SceneToolNotExist()

        tool.status = status or (
            PanelStatus.UNPUBLISHED if tool.status == PanelStatus.PUBLISHED else PanelStatus.PUBLISHED
        )
        tool.save(update_fields=["status"])
        return tool


class CreateSceneScopeTool(CreateTool):
    """创建场景级工具（继承 CreateTool，复用核心创建逻辑）"""

    name = gettext_lazy("创建场景级工具")
    RequestSerializer = SceneScopeToolCreateRequestSerializer

    def perform_request(self, validated_request_data):
        from services.web.scene.constants import BindingType, ResourceVisibilityType
        from services.web.scene.models import ResourceBinding, ResourceBindingScene

        scene_id = int(validated_request_data.pop("scene_id"))
        if not Scene.objects.filter(scene_id=scene_id).exists():
            raise ValueError("scene_id 不存在或已删除")
        if not Scene.objects.filter(scene_id=scene_id, status=SceneStatus.ENABLED).exists():
            raise ValueError("scene_id 不存在、已删除或已停用")

        with transaction.atomic():
            # 复用父类 CreateTool 的核心创建逻辑
            tool = super().perform_request(validated_request_data)

            # 创建场景级绑定关系（有且仅有一个场景关联）
            binding = ResourceBinding.objects.create(
                resource_type=ResourceVisibilityType.TOOL,
                resource_id=tool.uid,
                binding_type=BindingType.SCENE_BINDING,
            )
            ResourceBindingScene.objects.create(binding=binding, scene_id=scene_id)
            self._ensure_binding_integrity_or_raise(binding)

        return tool


class UpdateSceneScopeTool(UpdateTool):
    """编辑场景级工具（继承 UpdateTool，复用核心更新逻辑）"""

    name = gettext_lazy("编辑场景级工具")
    RequestSerializer = SceneScopeToolUpdateRequestSerializer

    def perform_request(self, validated_request_data):
        from services.web.scene.constants import BindingType, ResourceVisibilityType
        from services.web.scene.models import ResourceBinding
        from services.web.tool.exceptions import SceneToolNotExist

        scene_id = validated_request_data.pop("scene_id", None)
        uid = validated_request_data.get("uid")
        # 通过 ResourceBinding + ResourceBindingScene 确认是该场景的工具
        try:
            binding = ResourceBinding.objects.get(
                resource_type=ResourceVisibilityType.TOOL,
                resource_id=uid,
                binding_type=BindingType.SCENE_BINDING,
            )
        except ResourceBinding.DoesNotExist:
            raise SceneToolNotExist()
        self._ensure_binding_integrity_or_raise(binding)

        if not binding.binding_scenes.filter(
            scene_id=int(scene_id),
            scene__is_deleted=False,
            scene__status=SceneStatus.ENABLED,
        ).exists():
            raise SceneToolNotExist()

        # 复用父类 UpdateTool 的核心更新逻辑
        return super().perform_request(validated_request_data)


class DeleteSceneScopeTool(DeleteTool):
    """删除场景级工具（继承 DeleteTool，复用核心删除逻辑）"""

    name = gettext_lazy("删除场景级工具")
    RequestSerializer = SceneScopeToolDeleteRequestSerializer

    @transaction.atomic
    def perform_request(self, validated_request_data):
        from services.web.scene.constants import BindingType, ResourceVisibilityType
        from services.web.scene.models import ResourceBinding
        from services.web.tool.exceptions import SceneToolNotExist

        scene_id = validated_request_data.get("scene_id")
        uid = validated_request_data.get("uid")
        # 通过 ResourceBinding + ResourceBindingScene 确认是该场景的工具
        try:
            binding = ResourceBinding.objects.get(
                resource_type=ResourceVisibilityType.TOOL,
                resource_id=uid,
                binding_type=BindingType.SCENE_BINDING,
            )
        except ResourceBinding.DoesNotExist:
            raise SceneToolNotExist()
        self._ensure_binding_integrity_or_raise(binding)

        if not binding.binding_scenes.filter(
            scene_id=int(scene_id),
            scene__is_deleted=False,
            scene__status=SceneStatus.ENABLED,
        ).exists():
            raise SceneToolNotExist()

        # 删除绑定关系（级联删除关联的场景）
        BindingMetadataHelper.delete_resource_binding(
            resource_id=uid,
            resource_type=ResourceVisibilityType.TOOL,
        )

        # 复用父类 DeleteTool 的核心删除逻辑（包含 enum mapping 清理）
        return super().perform_request(validated_request_data)


class PublishSceneScopeTool(ToolBase):
    """上架/下架场景级工具"""

    name = gettext_lazy("上架/下架场景级工具")
    RequestSerializer = SceneScopeToolPublishRequestSerializer
    ResponseSerializer = ToolPublishResponseSerializer

    def perform_request(self, validated_request_data):
        from services.web.scene.constants import (
            BindingType,
            PanelStatus,
            ResourceVisibilityType,
        )
        from services.web.scene.models import ResourceBinding
        from services.web.tool.exceptions import SceneToolNotExist

        scene_id = validated_request_data["scene_id"]
        uid = validated_request_data.get("uid")
        status = validated_request_data.get("status")

        # 通过 ResourceBinding + ResourceBindingScene 确认是该场景的工具
        binding = ResourceBinding.objects.filter(
            resource_type=ResourceVisibilityType.TOOL,
            resource_id=uid,
            binding_type=BindingType.SCENE_BINDING,
        ).first()
        if not binding:
            raise SceneToolNotExist()
        self._ensure_binding_integrity_or_raise(binding)

        if not binding.binding_scenes.filter(
            scene_id=int(scene_id),
            scene__is_deleted=False,
            scene__status=SceneStatus.ENABLED,
        ).exists():
            raise SceneToolNotExist()

        tool = Tool.last_version_tool(uid)
        if not tool:
            raise SceneToolNotExist()

        tool.status = status or (
            PanelStatus.UNPUBLISHED if tool.status == PanelStatus.PUBLISHED else PanelStatus.PUBLISHED
        )
        tool.save(update_fields=["status"])
        return tool
