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
from django.db.models import Q
from django.utils.translation import gettext_lazy
from rest_framework.exceptions import ValidationError

from apps.audit.resources import AuditMixinResource
from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.drf import wrapper_permission_field
from core.models import UUIDField
from services.web.tool.constants import (
    DataSearchConfigTypeEnum,
    SQLDataSearchConfig,
    ToolTypeEnum,
)
from services.web.tool.models import BkvisionToolConfig, DataSearchToolConfig, Tool
from services.web.tool.serlializers import (
    ToolCreateRequestSerializer,
    ToolDeleteRetrieveRequestSerializer,
    ToolListResponseSerializer,
    ToolResponseSerializer,
    ToolRetrieveResponseSerializer,
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
        keyword = validated_request_data.get("keyword", "")
        queryset = Tool.objects.all()

        if keyword:
            queryset = queryset.filter(
                Q(name__icontains=keyword) | Q(description__icontains=keyword) | Q(created_by__icontains=keyword)
            )

        queryset = queryset.order_by("-updated_at")

        results = ToolListResponseSerializer(queryset, many=True).data

        results = wrapper_permission_field(
            result_list=results, actions=[ActionEnum.USE_TOOL], id_field=lambda item: item["uid"]
        )
        return results


class DeleteTool(AuditMixinResource):
    name = gettext_lazy("删除工具")

    RequestSerializer = ToolDeleteRetrieveRequestSerializer

    @transaction.atomic
    def perform_request(self, validated_request_data):
        uid = validated_request_data["uid"]

        try:
            tool = Tool.objects.get(uid=uid, is_deleted=False)
        except Tool.DoesNotExist:
            raise ValidationError(f"工具不存在：{uid}")
        tool.delete()
        return {"uid": uid, "message": "删除成功"}


class CreateTool(ToolBase):
    name = gettext_lazy("新增工具")
    RequestSerializer = ToolCreateRequestSerializer

    def perform_request(self, validated_request_data):
        tool_type = validated_request_data["type"]
        config = validated_request_data["config"]

        if tool_type == ToolTypeEnum.DATA_SEARCH.value:
            return self._create_sql_tool(config)
        elif tool_type == ToolTypeEnum.BK_VISION.value:
            return self._create_bkvision_tool(config)
        else:
            raise ValidationError({"type": f"不支持的工具类型: {tool_type}"})

    @transaction.atomic
    def _create_sql_tool(self, config: dict):
        try:
            SQLDataSearchConfig(**config)
        except Exception:
            raise ValidationError("SQL 配置不合法")

        tool = self._create_tool_instance(
            tool_type=ToolTypeEnum.DATA_SEARCH.value,
            config=config,
            name=config.get("name", "SQL Tool"),
        )

        DataSearchToolConfig.objects.create(
            tool=tool,
            data_search_config_type=DataSearchConfigTypeEnum.SQL,
            sql=config.get("sql", ""),
        )

        return {"uid": tool.uid, "version": tool.version}

    @transaction.atomic
    def _create_bkvision_tool(self, config: dict):
        uid = config.get("uid")
        if not uid:
            raise ValidationError({"uid": "BKVision 工具缺少 uid"})

        if Tool.objects.filter(uid=uid).exists():
            raise ValidationError({"uid": f"工具 UID 已存在：{uid}"})

        panel = VisionPanel.objects.create(
            id=uid,
            vision_id=uid,
            name=uid,
            scenario=Scenario.TOOL,
        )

        tool = self._create_tool_instance(
            tool_type=ToolTypeEnum.BK_VISION.value,
            config=config,
            name=config.get("name", "BKVision Tool"),
            custom_uid=uid,
        )

        BkvisionToolConfig.objects.create(tool=tool, panel=panel)

        return {"uid": tool.uid, "version": tool.version}

    def _create_tool_instance(self, tool_type: str, config: dict, name: str, custom_uid: str = None) -> Tool:
        if custom_uid and Tool.objects.filter(uid=custom_uid).exists():
            raise ValidationError({"uid": f"工具 UID 已存在：{custom_uid}"})

        tool = Tool.objects.create(
            uid=custom_uid or UUIDField.get_default_value(),
            namespace=config.get("namespace", ""),
            name=name,
            version=1,
            description=config.get("description", ""),
            tool_type=tool_type,
            config=config,
        )

        return tool


class UpdateTool(ToolBase):
    name = gettext_lazy("编辑工具")
    RequestSerializer = ToolUpdateRequestSerializer

    def perform_request(self, validated_request_data):
        tool_type = validated_request_data["type"]
        config = validated_request_data["config"]
        uid = config.get("uid")
        try:
            tool = Tool.objects.get(uid=uid)
        except Tool.DoesNotExist:
            raise ValidationError(f"工具 uid 不存在：{uid}")

        if tool_type == ToolTypeEnum.DATA_SEARCH:
            return self._update_sql_tool(tool, config)
        elif tool_type == ToolTypeEnum.BK_VISION:
            return self._update_bkvision_tool(tool, config)
        else:
            raise ValidationError(f"不支持的工具类型: {tool_type}")

    def _update_tool_base_fields(self, tool: Tool, config: dict):
        for field in ["name", "description"]:
            if field in config:
                setattr(tool, field, config[field])

        tool.config = config
        tool.save()

    @transaction.atomic
    def _update_sql_tool(self, tool: Tool, config: dict):
        try:
            SQLDataSearchConfig(**config)
        except Exception:
            raise ValidationError("SQL 配置不合法")

        self._update_tool_base_fields(tool, config)

        DataSearchToolConfig.objects.update_or_create(
            tool=tool,
            defaults={
                "data_search_config_type": DataSearchConfigTypeEnum.SQL,
                "sql": config.get("sql", ""),
            },
        )

        return ToolResponseSerializer({"uid": tool.uid, "version": tool.version}).data

    @transaction.atomic
    def _update_bkvision_tool(self, tool: Tool, config: dict):
        uid = config.get("uid")
        if not uid:
            raise ValidationError({"uid": "缺少工具唯一标识 uid"})

        try:
            panel = VisionPanel.objects.get(id=uid, is_deleted=False)
        except VisionPanel.DoesNotExist:
            raise ValidationError({"uid": f"仪表盘（id={uid}）不存在"})

        self._update_tool_base_fields(tool, config)

        BkvisionToolConfig.objects.update_or_create(
            tool=tool,
            defaults={"panel": panel},
        )

        return ToolResponseSerializer({"uid": tool.uid, "version": tool.version}).data


class ExecuteTool(ToolBase):
    name = gettext_lazy("工具执行")

    def perform_request(self, validated_request_data):
        pass


class ListToolAll(ToolBase):
    name = gettext_lazy("工具列表(all)")

    def perform_request(self, validated_request_data):
        tool_queryset = Tool.objects.filter(is_deleted=False)

        bkvision_config_map = {
            cfg.tool_id: cfg
            for cfg in BkvisionToolConfig.objects.select_related("panel").filter(tool__in=tool_queryset)
        }

        results = []
        for tool in tool_queryset:
            tool_data = {
                "uid": tool.uid,
                "name": tool.name,
                "type": tool.tool_type,
                "version": tool.version,
                "description": tool.description,
                "config": tool.config,
            }

            if tool.tool_type == ToolTypeEnum.BK_VISION:
                panel_config = bkvision_config_map.get(tool.id)
                if panel_config:
                    panel = panel_config.panel
                    tool_data["panel"] = {
                        "vision_id": panel.vision_id,
                        "name": panel.name,
                        "scenario": panel.scenario,
                        "priority_index": panel.priority_index,
                    }
                else:
                    tool_data["panel"] = None

            results.append(tool_data)

        return results


class ExportToolData(ToolBase):
    name = gettext_lazy("工具执行数据导出")

    def perform_request(self, validated_request_data):
        pass


class GetToolDetail(ToolBase):
    name = gettext_lazy("获取工具详情")

    RequestSerializer = ToolDeleteRetrieveRequestSerializer

    def perform_request(self, validated_request_data):
        uid = validated_request_data["uid"]

        try:
            tool = Tool.objects.get(uid=uid, is_deleted=False)
        except Tool.DoesNotExist:
            raise ValidationError(f"工具不存在：{uid}")

        data = {
            "uid": tool.uid,
            "name": tool.name,
            "type": tool.tool_type,
            "version": tool.version,
            "description": tool.description,
            "namespace": tool.namespace,
            "config": tool.config,
            "panel": None,
        }

        if tool.tool_type == ToolTypeEnum.BK_VISION:
            try:
                panel_config = BkvisionToolConfig.objects.select_related("panel").get(tool=tool)
                panel = panel_config.panel
                if panel.is_deleted:
                    raise ValidationError(f"关联仪表盘已删除：{panel.vision_id}")

                data["panel"] = {
                    "vision_id": panel.vision_id,
                    "name": panel.name,
                    "scenario": panel.scenario,
                    "priority_index": panel.priority_index,
                }
            except BkvisionToolConfig.DoesNotExist:
                data["panel"] = None

        return ToolRetrieveResponseSerializer(data).data
