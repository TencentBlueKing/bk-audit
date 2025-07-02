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

from bk_resource import Resource
from django.db import transaction
from django.db.models import Count, Q
from django.http import Http404
from django.utils.translation import gettext, gettext_lazy
from pypinyin import lazy_pinyin

from apps.audit.resources import AuditMixinResource
from apps.meta.constants import NO_TAG_ID, NO_TAG_NAME
from apps.meta.models import Tag
from apps.permission.handlers.actions.action import ActionEnum
from apps.permission.handlers.drf import wrapper_permission_field
from core.models import get_request_username
from core.sql.parser.praser import SqlQueryAnalysis
from services.web.tool.constants import ToolTypeEnum
from services.web.tool.executor.tool import ToolExecutorFactory
from services.web.tool.models import Tool, ToolTag
from services.web.tool.serializer import (
    SqlAnalyseRequestSerializer,
    SqlAnalyseResponseSerializer,
)
from services.web.tool.serializers import (
    ExecuteToolReqSerializer,
    ExecuteToolRespSerializer,
)
from services.web.tool.serlializers import (
    ListRequestSerializer,
    ListToolTagsResponseSerializer,
    ToolCreateRequestSerializer,
    ToolDeleteRetrieveRequestSerializer,
    ToolListAllResponseSerializer,
    ToolListResponseSerializer,
    ToolResponseSerializer,
    ToolRetrieveResponseSerializer,
    ToolUpdateRequestSerializer,
)
from services.web.tool.tool import create_tool_with_config, sync_resource_tags


class ToolBase(AuditMixinResource, abc.ABC):
    tags = ["Tool"]


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

        tag_count = [
            {
                "tag_name": str(NO_TAG_NAME),
                "tag_id": NO_TAG_ID,
                "tool_count": Tool.all_latest_tools()
                .exclude(uid__in=ToolTag.objects.values_list("tool_uid", flat=True).distinct())
                .count(),
            }
        ] + tag_count

        return tag_count


class ListTool(ToolBase):
    name = gettext_lazy("获取工具列表")
    RequestSerializer = ListRequestSerializer
    many_response_data = True
    ResponseSerializer = ToolListResponseSerializer

    def perform_request(self, validated_request_data):
        tags = validated_request_data.pop("tags", [])
        keyword = validated_request_data.get("keyword", "").strip()
        limit = validated_request_data["limit"]
        offset = validated_request_data["offset"]
        tools_qs = Tool.all_latest_tools().order_by("-updated_at")

        if keyword:
            tools_qs = tools_qs.filter(
                Q(name__icontains=keyword) | Q(description__icontains=keyword) | Q(created_by__icontains=keyword)
            )

        if tags:
            tool_uid_list = list(ToolTag.objects.filter(tag_id__in=tags).values_list("tool_uid", flat=True).distinct())

            tools_qs = tools_qs.filter(uid__in=tool_uid_list)

        paged_qs = tools_qs[offset : offset + limit]

        tool_uids = [tool.uid for tool in paged_qs]
        tag_map = defaultdict(list)
        for t in ToolTag.objects.filter(tool_uid__in=tool_uids):
            tag_map[t.tool_uid].append(t.tag_id)

        for tool in paged_qs:
            setattr(tool, "tags", tag_map.get(tool.uid, []))

        serialized_data = self.ResponseSerializer(paged_qs, many=True).data

        current_user = get_request_username()
        data = wrapper_permission_field(
            result_list=serialized_data,
            actions=[ActionEnum.USE_TOOL],
            id_field=lambda item: item["uid"],
            always_allowed=lambda item: item.get("created_by") == current_user,
        )
        return data


class DeleteTool(ToolBase):
    name = gettext_lazy("删除工具")
    audit_action = ActionEnum.USE_TOOL
    RequestSerializer = ToolDeleteRetrieveRequestSerializer

    @transaction.atomic
    def perform_request(self, validated_request_data):
        uid = validated_request_data["uid"]
        Tool.delete_by_uid(uid)


class CreateTool(ToolBase):
    """
    ```json
    请求参数：data_search工具类型
    {
      "tool_type": "data_search",
      "name": "xxx",
      "description": "xxx",
      "tags": ["xxx", "xxx"],
      "data_search_config_type": "sql"  # 仅data_search类型工具需要
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
            "choices": []
          }
        ],
        "output_fields": [
          {
            "raw_name": "xxx",
            "display_name": "xxx",
            "description": "xxx"
          }
        ],
        "sql": "SELECT * FROM xxx WHERE $condition",
      }
    }
    请求参数：bk_vision工具类型
    {
      "tool_type": "bk_vision",
      "name": "xxx",
      "description": "xxx",
      "tags": ["xxx"],
      "config": {
        "uid": "xxx"
      }
    }
    响应结构：
     "data": {
            "uid": "xxx",
            "version": xxx
        },
    """

    name = gettext_lazy("新增工具")
    RequestSerializer = ToolCreateRequestSerializer  # 统一使
    ResponseSerializer = ToolResponseSerializer

    def perform_request(self, validated_request_data):
        return create_tool_with_config(validated_request_data)


class UpdateTool(ToolBase):
    """
    ```json
    请求参数：data_search工具类型
    {
      "name": "xxx",
      "description": "xxx",
      "tags": ["xxx", "xxx"],
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
            "choices": []
          }
        ],
        "output_fields": [
          {
            "raw_name": "xxx",
            "display_name": "xxx",
            "description": "xxx"
          }
        ],
        "sql": "SELECT * FROM xxx WHERE $condition",
      }
    }
    请求参数：bk_vision工具类型
    {
      "name": "xxx",
      "description": "xxx",
      "tags": ["xxx"],
      "config": {
        "uid": "xxx"
      }
    }
    响应结构：
     "data": {
            "uid": "xxx",
            "version": xxx
        },
    """

    name = gettext_lazy("编辑工具")
    audit_action = ActionEnum.USE_TOOL
    RequestSerializer = ToolUpdateRequestSerializer
    ResponseSerializer = ToolResponseSerializer

    @transaction.atomic
    def perform_request(self, validated_request_data):
        uid = validated_request_data["uid"]
        tag_names = validated_request_data.pop("tags")
        tool = Tool.last_version_tool(uid)
        if not tool:
            raise Http404(gettext("Tool not found: %s") % uid)
        if "config" in validated_request_data:
            new_config = validated_request_data["config"]
            if tool.config != new_config:
                new_tool_data = {
                    "uid": tool.uid,
                    "tool_type": tool.tool_type,
                    "name": validated_request_data["name"],
                    "description": validated_request_data["description"],
                    "namespace": validated_request_data["namespace"],
                    "version": tool.version + 1,
                    "config": new_config,
                }
                if tool.tool_type == ToolTypeEnum.DATA_SEARCH:
                    new_tool_data["data_search_config_type"] = tool.data_search_config.data_search_config_type
                return create_tool_with_config(new_tool_data)
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
                            "raw_name": "time_range",
                            "value": "2023-01-01,2023-12-31"
                        }
                    ],
                    "page": 1,
                    "page_size": 100
                }
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
            raise Tool.DoesNotExist()
        executor = ToolExecutorFactory(sql_analyzer_cls=SqlQueryAnalysis).create_from_tool(tool)
        data = executor.execute(params).model_dump()
        return {"data": data, "tool_type": tool.tool_type}


class ListToolAll(ToolBase):
    name = gettext_lazy("工具列表(all)")
    many_response_data = True
    ResponseSerializer = ToolListAllResponseSerializer

    def perform_request(self, validated_request_data):
        tool_qs = Tool.all_latest_tools().order_by("-updated_at")
        serialized_data = ToolListAllResponseSerializer(tool_qs, many=True).data

        current_user = get_request_username()
        data = wrapper_permission_field(
            result_list=serialized_data,
            actions=[ActionEnum.USE_TOOL],
            id_field=lambda item: item["uid"],
            always_allowed=lambda item: item.get("created_by") == current_user,
        )
        return data


class ExportToolData(ToolBase):
    name = gettext_lazy("工具执行数据导出")

    def perform_request(self, validated_request_data):
        pass


class GetToolDetail(ToolBase):
    name = gettext_lazy("获取工具详情")
    RequestSerializer = ToolDeleteRetrieveRequestSerializer
    ResponseSerializer = ToolRetrieveResponseSerializer

    def perform_request(self, validated_request_data):
        uid = validated_request_data["uid"]
        tool = Tool.last_version_tool(uid)
        if not tool:
            raise Http404(gettext("Tool not found: %s") % uid)
        return tool


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

    def perform_request(self, validated_request_data):
        analyser = SqlQueryAnalysis(
            validated_request_data["sql"],
            dialect=validated_request_data.get("dialect") or None,
        )
        analyser.parse_sql()
        parsed = analyser.get_parsed_def()
        return parsed.model_dump()
