# -*- coding: utf-8 -*-
import abc

from django.utils.translation import gettext_lazy

from apps.audit.resources import AuditMixinResource


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


class DeleteTool(ToolBase):
    name = gettext_lazy("删除工具")

    def perform_request(self, validated_request_data):
        pass


class CreateTool(ToolBase):
    name = gettext_lazy("新增工具")

    def perform_request(self, validated_request_data):
        pass


class UpdateTool(ToolBase):
    name = gettext_lazy("编辑工具")

    def perform_request(self, validated_request_data):
        pass


class ExecuteTool(ToolBase):
    name = gettext_lazy("工具执行")

    def perform_request(self, validated_request_data):
        pass


class ListToolAll(ToolBase):
    name = gettext_lazy("工具列表(all)")

    def perform_request(self, validated_request_data):
        pass


class ExportToolData(ToolBase):
    name = gettext_lazy("工具执行数据导出")

    def perform_request(self, validated_request_data):
        pass


class GetToolDetail(ToolBase):
    name = gettext_lazy("获取工具详情")

    def perform_request(self, validated_request_data):
        pass
