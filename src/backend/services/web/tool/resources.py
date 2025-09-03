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
from collections import defaultdict
from typing import List

from bk_resource import Resource, api, resource
from django.db import transaction
from django.db.models import Count, Q
from django.utils.translation import gettext_lazy
from pypinyin import lazy_pinyin

from api.bk_base.constants import UserAuthActionEnum
from api.bk_base.serializers import UserAuthCheckRespSerializer
from apps.audit.resources import AuditMixinResource
from apps.meta.constants import NO_TAG_ID, NO_TAG_NAME
from apps.meta.models import EnumMappingRelatedType, Tag
from apps.meta.serializers import (
    EnumMappingByCollectionKeysSerializer,
    EnumMappingByCollectionSerializer,
    EnumMappingSerializer,
)
from core.models import get_request_username
from core.sql.parser.model import ParsedSQLInfo
from core.sql.parser.praser import SqlQueryAnalysis
from core.utils.page import paginate_data
from services.web.strategy_v2.models import StrategyTool
from services.web.tool.constants import (
    DataSearchConfigTypeEnum,
    SQLDataSearchConfig,
    ToolTagsEnum,
    ToolTypeEnum,
)
from services.web.tool.exceptions import ToolDoesNotExist, ToolTypeNotSupport
from services.web.tool.executor.tool import ToolExecutorFactory
from services.web.tool.models import Tool, ToolTag
from services.web.tool.permissions import ToolPermission
from services.web.tool.serializers import (
    ExecuteToolReqSerializer,
    ExecuteToolRespSerializer,
    ListRequestSerializer,
    ListToolTagsResponseSerializer,
    SqlAnalyseRequestSerializer,
    SqlAnalyseResponseSerializer,
    SqlAnalyseWithToolRequestSerializer,
    ToolCreateRequestSerializer,
    ToolListAllResponseSerializer,
    ToolListResponseSerializer,
    ToolResponseSerializer,
    ToolRetrieveRequestSerializer,
    ToolRetrieveResponseSerializer,
    ToolUpdateRequestSerializer,
    UserQueryTableAuthCheckReqSerializer,
)
from services.web.tool.tool import (
    create_tool_with_config,
    custom_sort_order,
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


class ListToolTags(ToolBase):
    name = gettext_lazy("列出工具标签")
    ResponseSerializer = ListToolTagsResponseSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        tag_count = list(ToolTag.objects.values("tag_id").annotate(tool_count=Count("tag_id")).order_by())
        tag_map = {t.tag_id: {"name": t.tag_name} for t in Tag.objects.all()}
        for t in tag_count:
            t.update({"tag_name": tag_map.get(t["tag_id"], {}).get("name", t["tag_id"])})

        tag_count.sort(key=lambda tag: [lazy_pinyin(tag["tag_name"].lower(), errors="ignore"), tag["tag_name"].lower()])

        current_user = get_request_username()
        permission = ToolPermission(username=current_user)
        authed_tool_filter = permission.authed_tool_filter
        tag_count.sort(key=lambda tag: [lazy_pinyin(tag["tag_name"].lower(), errors="ignore"), tag["tag_name"].lower()])
        tag_count = [
            {
                "tag_name": str(ToolTagsEnum.ALL_TOOLS.label),
                "tag_id": ToolTagsEnum.ALL_TOOLS.value,
                "tool_count": Tool.all_latest_tools().filter(authed_tool_filter).count(),
            },
            {
                "tag_name": str(ToolTagsEnum.MY_CREATED_TOOLS.label),
                "tag_id": ToolTagsEnum.MY_CREATED_TOOLS.value,
                "tool_count": Tool.all_latest_tools().filter(created_by=get_request_username()).count(),
            },
            {
                "tag_name": str(ToolTagsEnum.RECENTLY_USED_TOOLS.label),
                "tag_id": ToolTagsEnum.RECENTLY_USED_TOOLS.value,
                "tool_count": Tool.all_latest_tools()
                .filter(uid__in=recent_tool_usage_manager.get_recent_uids(current_user))
                .filter(authed_tool_filter)
                .count(),
            },
            {
                "tag_name": str(NO_TAG_NAME),
                "tag_id": NO_TAG_ID,
                "tool_count": Tool.all_latest_tools()
                .exclude(uid__in=ToolTag.objects.values_list("tool_uid", flat=True).distinct())
                .count(),
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
    bind_request = True

    def perform_request(self, validated_request_data):
        request = validated_request_data.pop("_request")
        tags = validated_request_data.pop("tags", [])
        keyword = validated_request_data.get("keyword", "").strip()
        my_created = validated_request_data["my_created"]
        recent_used = validated_request_data["recent_used"]
        recent_tool_uids = []

        current_user = get_request_username()
        permission = ToolPermission(username=current_user)
        authed_tool_filter = permission.authed_tool_filter
        queryset = Tool.all_latest_tools().filter(authed_tool_filter)
        if any(
            int(tag_id) in tags
            for tag_id in [
                ToolTagsEnum.ALL_TOOLS.value,
                ToolTagsEnum.MY_CREATED_TOOLS.value,
                ToolTagsEnum.RECENTLY_USED_TOOLS.value,
            ]
        ):
            tags = []
        if recent_used:
            recent_tool_uids = recent_tool_usage_manager.get_recent_uids(current_user)
            if not recent_tool_uids:
                return []
            else:
                queryset = queryset.filter(uid__in=recent_tool_uids)

        if my_created:
            queryset = queryset.filter(created_by=current_user)

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

        if recent_used and recent_tool_uids:
            queryset = custom_sort_order(queryset, "uid", recent_tool_uids)
        else:
            queryset = queryset.order_by("-updated_at")
        paged_tools, page = paginate_data(queryset=queryset, request=request)
        tool_uids = [t.uid for t in paged_tools]

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

        for tool in paged_tools:
            setattr(tool, "tags", tag_map.get(tool.uid, []))
            setattr(tool, "strategies", strategy_map.get(tool.uid, []))

        serialized_data = ToolListResponseSerializer(instance=paged_tools, many=True).data
        # 权限字段注入
        tool_tag_ids = list(tool_tags.values_list("tag_id", flat=True).distinct())
        serialized_data = permission.wrapper_tool_permission_field(tool_list=serialized_data, tool_tag_ids=tool_tag_ids)
        return page.get_paginated_response(data=serialized_data)


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
    """

    name = gettext_lazy("获取某个策略的某个集合中的某个枚举值的信息")
    RequestSerializer = EnumMappingByCollectionKeysSerializer
    ResponseSerializer = EnumMappingSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        validated_request_data["related_type"] = EnumMappingRelatedType.TOOL.value
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
    """

    name = gettext_lazy("获取某个策略的某个集合中的所有枚举值的信息")
    RequestSerializer = EnumMappingByCollectionSerializer
    ResponseSerializer = EnumMappingSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        validated_request_data["related_type"] = EnumMappingRelatedType.TOOL.value
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
        if tool.tool_type == ToolTypeEnum.DATA_SEARCH.value:
            config = validated_request_data.get("config", {})
            for output_field in config.get("output_fields", []):
                enum_mappings = output_field.get("enum_mappings")
                if enum_mappings:
                    self.updatel_enum_mappings(
                        enum_mapping=enum_mappings,
                        tool_uid=tool.uid,
                        field_name=output_field["raw_name"],
                    )
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

    def create_tool_new_version(self, old_tool: Tool, validated_request_data: dict):
        """
        创建工具新版本
        """

        new_config = validated_request_data["config"]
        new_tool_data = {
            "uid": old_tool.uid,
            "tool_type": old_tool.tool_type,
            "name": validated_request_data.get("name", old_tool.name),
            "description": validated_request_data.get("description", old_tool.description),
            "namespace": validated_request_data.get("namespace", old_tool.namespace),
            "version": old_tool.version + 1,
            "config": new_config,
            "tags": validated_request_data.get("tags"),
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
        return create_tool_with_config(new_tool_data)

    @transaction.atomic
    def perform_request(self, validated_request_data: dict):
        uid = validated_request_data["uid"]
        tool = Tool.last_version_tool(uid)
        if not tool:
            raise ToolDoesNotExist()
        # 如果配置有变更则创建新版本
        if validated_request_data.get("config") and validated_request_data.get("config") != tool.config:
            return self.create_tool_new_version(old_tool=tool, validated_request_data=validated_request_data)
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
                }
            }
            ```
        不同的变量下的输入格式:
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
            ```json
                {
                    "raw_name": "usernames",
                    "value": ["user1", "user2"]
                }
        5. time_range_select（时间范围选择器）
            ```json
                {
                    "raw_name": "datetime_range",
                    "value": ["2023-01-01 12:00:00", "2023-01-31 12:00:00"]
                }
        6. multiselect（下拉列表）
            ```json
                {
                    "raw_name": "multiselect",
                    "value": ["option1", "option2"]
                }
            ```
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
    2. tool_type 为 bk_vision
        params:
            ```json
            {
                "uid": "api_tool_123",
                "params": {}
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
    """

    name = gettext_lazy("工具执行")
    RequestSerializer = ExecuteToolReqSerializer
    ResponseSerializer = ExecuteToolRespSerializer

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
        executor = ToolExecutorFactory(sql_analyzer_cls=SqlQueryAnalysis).create_from_tool(tool)
        data = executor.execute(params).model_dump()
        recent_tool_usage_manager.record_usage(get_request_username(), uid)
        return {"data": data, "tool_type": tool.tool_type}


class ListToolAll(ToolBase):
    name = gettext_lazy("工具列表(all)")
    many_response_data = True
    ResponseSerializer = ToolListAllResponseSerializer

    def validate_response_data(self, response_data):
        return response_data

    def perform_request(self, validated_request_data):
        tool_qs = Tool.all_latest_tools().order_by("-updated_at")
        tool_uids = [tool.uid for tool in tool_qs]
        tool_tags = ToolTag.objects.filter(tool_uid__in=tool_uids)

        tag_map = defaultdict(list)
        for t in tool_tags:
            tag_map[t.tool_uid].append(str(t.tag_id))
        strategy_map = defaultdict(list)
        rows = StrategyTool.objects.filter(tool_uid__in=tool_uids).values("tool_uid", "strategy_id")
        for row in rows:
            strategy_map[row["tool_uid"]].append(row["strategy_id"])

        for tool in tool_qs:
            setattr(tool, "tags", tag_map.get(tool.uid, []))
            setattr(tool, "strategies", strategy_map.get(tool.uid, []))
        serialized_data = self.ResponseSerializer(tool_qs, many=True).data

        current_user = get_request_username()
        permission = ToolPermission(username=current_user)
        tool_tag_ids = list(tool_tags.values_list("tag_id", flat=True).distinct())
        data = permission.wrapper_tool_permission_field(tool_list=serialized_data, tool_tag_ids=tool_tag_ids)
        return data


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

    def perform_request(self, validated_request_data):
        uid = validated_request_data["uid"]
        tool = Tool.last_version_tool(uid=uid)
        if not tool:
            raise ToolDoesNotExist()

        tag_ids = list(ToolTag.objects.filter(tool_uid=tool.uid).values_list("tag_id", flat=True))
        strategies_ids = list(StrategyTool.objects.filter(tool_uid=tool.uid).values_list("strategy_id", flat=True))
        setattr(tool, "tags", [str(tid) for tid in tag_ids])
        setattr(tool, "strategies", [str(sid) for sid in strategies_ids])
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
        data = self.ResponseSerializer(instance=tool).data
        current_user = get_request_username()
        permission = ToolPermission(username=current_user)
        data = permission.wrapper_tool_permission_field(tool_list=[data], tool_tag_ids=tag_ids)[0]
        return data


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
