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

from bk_resource import Resource
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.utils.translation import gettext, gettext_lazy

from apps.audit.resources import AuditMixinResource
from core.sql.parser.praser import SqlQueryAnalysis
from services.web.tool.serializer import (
    SqlAnalyseRequestSerializer,
    SqlAnalyseResponseSerializer,
)
from apps.permission.handlers.actions.action import ActionEnum
from apps.permission.handlers.drf import wrapper_permission_field
from core.models import get_request_username
from services.web.tool.executor.tool import SqlQueryAnalysis, ToolExecutorFactory
from services.web.tool.models import Tool
from services.web.tool.serializers import ExecuteToolReqSerializer
from services.web.tool.serlializers import (
    ListRequestSerializer,
    ToolCreateRequestSerializer,
    ToolDeleteRetrieveRequestSerializer,
    TooListAllResponseSerializer,
    TooListResponseSerializer,
    ToolResponseSerializer,
    ToolRetrieveResponseSerializer,
    ToolUpdateRequestSerializer,
)
from services.web.tool.tool import create_tool_with_config


class ToolBase(AuditMixinResource, abc.ABC):
    tags = ["Tool"]


class ListToolTags(ToolBase):
    name = gettext_lazy("列出工具标签")

    def perform_request(self, validated_request_data):
        pass


class ListTool(ToolBase):
    name = gettext_lazy("获取工具列表")
    RequestSerializer = ListRequestSerializer
    many_response_data = True
    ResponseSerializer = TooListResponseSerializer

    def perform_request(self, validated_request_data):
        keyword = validated_request_data.get("keyword", "").strip()
        limit = validated_request_data["limit"]
        offset = validated_request_data["offset"]

        latest_tools_qs = Tool.all_latest_tools().order_by("-updated_at")
        if keyword:
            latest_tools_qs = latest_tools_qs.filter(
                Q(name__icontains=keyword) | Q(description__icontains=keyword) | Q(created_by__icontains=keyword)
            )

        paged_qs = latest_tools_qs[offset : offset + limit]

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
        Tool.objects.filter(uid=uid, is_deleted=False).delete()


class CreateTool(ToolBase):
    name = gettext_lazy("新增工具")
    RequestSerializer = ToolCreateRequestSerializer  # 统一使
    ResponseSerializer = ToolResponseSerializer

    def perform_request(self, validated_request_data):
        return create_tool_with_config(validated_request_data)


class UpdateTool(ToolBase):
    name = gettext_lazy("编辑工具")
    audit_action = ActionEnum.USE_TOOL
    RequestSerializer = ToolUpdateRequestSerializer
    ResponseSerializer = ToolResponseSerializer

    @transaction.atomic
    def perform_request(self, validated_request_data):
        uid = validated_request_data["uid"]
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
                return create_tool_with_config(new_tool_data)

        for key, value in validated_request_data.items():
            setattr(tool, key, value)
        tool.save(update_fields=validated_request_data.keys())

        return tool


class ExecuteTool(ToolBase):
    name = gettext_lazy("工具执行")
    RequestSerializer = ExecuteToolReqSerializer

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
        return executor.execute(params).model_dump()


class ListToolAll(ToolBase):
    name = gettext_lazy("工具列表(all)")
    many_response_data = True
    ResponseSerializer = TooListAllResponseSerializer

    def perform_request(self, validated_request_data):
        tool_qs = Tool.all_latest_tools().order_by("-updated_at")
        serialized_data = TooListAllResponseSerializer(tool_qs, many=True).data

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
    """解析SQL，返回引用表、变量和结果字段信息"""

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
