# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at https://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import abc

from bk_resource import api
from django.utils.translation import gettext_lazy
from rest_framework.generics import get_object_or_404

from apps.audit.resources import AuditMixinResource
from apps.permission.handlers.actions import ActionEnum
from services.web.vision.constants import PANEL
from services.web.vision.handlers.query import VisionHandler
from services.web.vision.models import VisionPanel, VisionPanelInstance
from services.web.vision.serializers import (
    QueryMetaReqSerializer,
    QueryShareDetailSerializer,
    VisionPanelInfoQuerySerializer,
    VisionPanelInfoSerializer,
)


class BKVision(AuditMixinResource, abc.ABC):
    tags = ["BKVision"]


class ListPanels(BKVision):
    name = gettext_lazy("仪表盘列表")
    ResponseSerializer = VisionPanelInfoSerializer
    RequestSerializer = VisionPanelInfoQuerySerializer
    many_response_data = True
    audit_action = ActionEnum.LIST_BASE_PANEL

    def perform_request(self, validated_request_data):
        return VisionPanel.objects.filter(scenario=validated_request_data['scenario']).all()


class QueryMixIn(AuditMixinResource, abc.ABC):
    def perform_request(self, validated_request_data):
        panel = get_object_or_404(VisionPanel, id=validated_request_data.get("share_uid"))
        self.add_audit_instance_to_context(instance=VisionPanelInstance(panel).instance)
        if panel.vision_id:
            validated_request_data["share_uid"] = panel.vision_id
        return getattr(panel.get_vision_handler_class()(), self.query_method)(params=validated_request_data)

    @property
    @abc.abstractmethod
    def query_method(self) -> str:
        pass


class QueryMeta(QueryMixIn, BKVision):
    """查询视图配置（Meta）

    可选权限上下文（调用方透传，用于统一鉴权并可在通过时跳过原有权限校验）：
    - caller_resource_type：调用方资源类型（当前支持：risk）
    - caller_resource_id：调用方资源ID（如风险ID）
    行为：若提供且鉴权通过，则放行；若鉴权失败，返回标准权限异常。
    """

    name = gettext_lazy("查询视图配置")
    RequestSerializer = QueryMetaReqSerializer
    audit_action = ActionEnum.VIEW_BASE_PANEL
    audit_resource_type = PANEL
    query_method = 'query_meta'


class QueryDataset(QueryMixIn, BKVision):
    name = gettext_lazy("获取面板视图数据")
    audit_action = ActionEnum.VIEW_BASE_PANEL
    audit_resource_type = PANEL
    query_method = 'query_dataset'


class QueryFieldData(QueryMixIn, BKVision):
    name = gettext_lazy("获取字段数据")
    audit_action = ActionEnum.VIEW_BASE_PANEL
    audit_resource_type = PANEL
    query_method = 'query_field_data'


class QueryVariableData(QueryMixIn, BKVision):
    name = gettext_lazy("查询变量数据")
    audit_action = ActionEnum.VIEW_BASE_PANEL
    audit_resource_type = PANEL
    query_method = 'query_variable_data'


class QueryShareList(BKVision):
    name = gettext_lazy("获取有权限的图表列表")

    def perform_request(self, validated_request_data):
        return api.bk_vision.get_share_list(**validated_request_data)


class QueryShareDetail(BKVision):
    name = gettext_lazy("获取图表元数据")
    RequestSerializer = QueryShareDetailSerializer

    def perform_request(self, validated_request_data):
        return VisionHandler().query_meta(params=validated_request_data)


class TestVariable(QueryMixIn, BKVision):
    name = gettext_lazy("测试变量数据")

    def perform_request(self, validated_request_data):
        return api.bk_vision.test_variable(**validated_request_data)
