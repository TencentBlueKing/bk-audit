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

from django.db import transaction
from django.utils.translation import gettext_lazy
from rest_framework.exceptions import ValidationError

from apps.audit.resources import AuditMixinResource
from services.web.tool.constants import (
    DataSearchConfigTypeEnum,
    SQLDataSearchConfig,
    ToolTypeEnum,
)
from services.web.tool.models import BkvisionToolConfig, DataSearchToolConfig, Tool
from services.web.tool.serlializers import (
    ToolCreateRequestSerializer,
    ToolDeleteRetrieveRequestSerializer,
    TooListAllRetrieveResponseSerializer,
    ToolResponseSerializer,
    ToolUpdateRequestSerializer,
)
from services.web.vision.models import Scenario, VisionPanel


class ToolBase(AuditMixinResource, abc.ABC):
    tags = ["Tool"]


class ListToolTags(ToolBase):
    name = gettext_lazy("列出工具标签")

    def perform_request(self, validated_request_data):
        pass


class ListTool(ToolBase):
    name = gettext_lazy("获取工具列表")

    def perform_request(self, validated_request_data):
        pass


class DeleteTool(AuditMixinResource):
    name = gettext_lazy("删除工具")
    RequestSerializer = ToolDeleteRetrieveRequestSerializer

    @transaction.atomic
    def perform_request(self, validated_request_data):
        uid = validated_request_data["uid"]
        tool = Tool.objects.filter(uid=uid, is_deleted=False).first()

        if not tool:
            raise ValidationError({"uid": f"工具不存在: {uid}"})

        if tool.tool_type == ToolTypeEnum.DATA_SEARCH.value:
            tool.delete()
        elif tool.tool_type == ToolTypeEnum.BK_VISION.value:
            VisionPanel.objects.filter(id=tool.config.get("uid")).delete()
            tool.delete()
        else:
            raise ValidationError({"type": f"不支持的工具类型: {tool.tool_type}"})

        return {"uid": uid, "message": "删除成功"}


class CreateTool(ToolBase):
    name = gettext_lazy("新增工具")
    RequestSerializer = ToolCreateRequestSerializer  # 统一使
    ResponseSerializer = ToolResponseSerializer

    @transaction.atomic
    def perform_request(self, validated_request_data):
        tool = Tool.objects.create(
            namespace=validated_request_data["namespace"],
            version=1,
            name=validated_request_data["name"],
            tool_type=validated_request_data["type"],
            description=validated_request_data["description"],
            config=validated_request_data["config"],
        )
        if tool.tool_type == ToolTypeEnum.DATA_SEARCH.value:
            return self._create_sql_tool(tool)
        elif tool.tool_type == ToolTypeEnum.BK_VISION.value:
            return self._create_bkvision_tool(tool)
        else:
            raise ValidationError({"type": f"不支持的工具类型: {tool.tool_type}"})

    @transaction.atomic
    def _create_sql_tool(self, tool: Tool):
        config = tool.config
        try:
            SQLDataSearchConfig(**config)
        except Exception:
            raise ValidationError({"config": "SQL 配置格式不合法，请检查配置字段和格式"})

        DataSearchToolConfig.objects.create(
            tool=tool,
            data_search_config_type=DataSearchConfigTypeEnum.SQL,
            sql=config.get("sql", ""),
        )

        return tool

    @transaction.atomic
    def _create_bkvision_tool(self, tool: Tool):
        config = tool.config
        uid = config.get("uid")

        if VisionPanel.objects.filter(id=uid).exists():
            raise ValidationError({"config": f"BK Vision 图表 ID 已存在: {uid}"})

        panel = VisionPanel.objects.create(
            id=uid,
            vision_id=uid,
            name=tool.name,
            scenario=Scenario.TOOL,
        )

        BkvisionToolConfig.objects.create(tool=tool, panel=panel)

        return tool


class UpdateTool(ToolBase):
    name = gettext_lazy("编辑工具")
    RequestSerializer = ToolUpdateRequestSerializer
    ResponseSerializer = ToolResponseSerializer

    @transaction.atomic
    def perform_request(self, validated_request_data):
        uid = validated_request_data["uid"]
        try:
            tool = Tool.objects.get(uid=uid, is_deleted=False)
        except Tool.DoesNotExist:
            raise ValidationError(f"工具不存在: {uid}")

        tool.name = validated_request_data["name"]
        tool.description = validated_request_data["description"]
        tool.config = validated_request_data["config"]
        tool.namespace = validated_request_data["namespace"]
        tool.save()

        if tool.tool_type == ToolTypeEnum.DATA_SEARCH.value:
            return self._update_sql_tool(tool, validated_request_data["config"])
        elif tool.tool_type == ToolTypeEnum.BK_VISION.value:
            return tool
        else:
            raise ValidationError(f"不支持的工具类型: {tool.tool_type}")

    @transaction.atomic
    def _update_sql_tool(self, tool: Tool, config: dict):
        try:
            SQLDataSearchConfig(**config)
        except Exception:
            raise ValidationError("SQL 配置不合法")

        DataSearchToolConfig.objects.update_or_create(
            tool=tool,
            defaults={
                "data_search_config_type": DataSearchConfigTypeEnum.SQL,
                "sql": config.get("sql", ""),
            },
        )

        return tool


class ExecuteTool(ToolBase):
    name = gettext_lazy("工具执行")

    def perform_request(self, validated_request_data):
        pass


class ListToolAll(ToolBase):
    name = gettext_lazy("工具列表(all)")
    many_response_data = True
    ResponseSerializer = TooListAllRetrieveResponseSerializer

    def perform_request(self, validated_request_data):
        tool_data = Tool.objects.filter(is_deleted=False)
        return tool_data


class ExportToolData(ToolBase):
    name = gettext_lazy("工具执行数据导出")

    def perform_request(self, validated_request_data):
        pass


class GetToolDetail(ToolBase):
    name = gettext_lazy("获取工具详情")
    RequestSerializer = ToolDeleteRetrieveRequestSerializer
    ResponseSerializer = TooListAllRetrieveResponseSerializer

    def perform_request(self, validated_request_data):
        uid = validated_request_data["uid"]
        try:
            tool = Tool.objects.get(uid=uid, is_deleted=False)
        except Tool.DoesNotExist:
            raise ValidationError(f"工具不存在：{uid}")

        return tool
