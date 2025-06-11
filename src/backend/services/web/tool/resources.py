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


class DeleteTool(AuditMixinResource):
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
