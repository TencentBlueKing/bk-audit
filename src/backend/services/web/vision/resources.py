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
        from django.db.models import Q

        queryset = VisionPanel.objects.filter(scenario=validated_request_data['scenario'])

        # 按归属级别和场景过滤
        scope_type = validated_request_data.get("scope_type", "")
        scene_id = validated_request_data.get("scene_id")

        if scope_type == "platform":
            queryset = queryset.filter(scope_type="platform")
        elif scope_type == "scene" and scene_id:
            queryset = queryset.filter(scope_type="scene", scene_id=scene_id)
        elif scene_id:
            # 传了 scene_id 但没指定 scope_type，返回该场景的报表 + 平台级报表
            queryset = queryset.filter(Q(scope_type="scene", scene_id=scene_id) | Q(scope_type="platform"))

        return queryset.all()


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


class QueryTestVariable(QueryMixIn, BKVision):
    name = gettext_lazy("测试变量数据")
    audit_action = ActionEnum.VIEW_BASE_PANEL
    audit_resource_type = PANEL
    query_method = 'query_test_variable'


# ==================== 场景报表管理（Panel）====================


class CreatePlatformPanel(BKVision):
    """创建平台级报表"""

    name = gettext_lazy("创建平台级报表")

    def perform_request(self, validated_request_data):
        from django.db import transaction

        from core.utils.data import unique_id
        from services.web.scene.constants import (
            PanelStatus,
            ResourceScopeType,
            ResourceVisibilityType,
            VisibilityScope,
        )
        from services.web.scene.models import ResourceVisibility

        with transaction.atomic():
            panel = VisionPanel.objects.create(
                id=validated_request_data.get("id") or unique_id(),
                name=validated_request_data["name"],
                category=validated_request_data.get("category", ""),
                description=validated_request_data.get("description", ""),
                status=validated_request_data.get("status", PanelStatus.UNPUBLISHED),
                scope_type=ResourceScopeType.PLATFORM,
                scene_id=None,
            )

            visibility_data = validated_request_data.get("visibility")
            if visibility_data:
                ResourceVisibility.objects.update_or_create(
                    resource_type=ResourceVisibilityType.PANEL,
                    resource_id=str(panel.pk),
                    defaults={
                        "visibility_type": visibility_data.get("visibility_type", VisibilityScope.ALL_VISIBLE),
                        "scene_ids": visibility_data.get("scene_ids", []),
                        "system_ids": visibility_data.get("system_ids", []),
                    },
                )

        return {"id": panel.pk, "name": panel.name}


class UpdatePlatformPanel(BKVision):
    """编辑平台级报表"""

    name = gettext_lazy("编辑平台级报表")

    def perform_request(self, validated_request_data):
        from django.db import transaction

        from services.web.scene.constants import (
            ResourceScopeType,
            ResourceVisibilityType,
            VisibilityScope,
        )
        from services.web.scene.models import ResourceVisibility
        from services.web.vision.exceptions import ScenePanelNotExist

        panel_id = validated_request_data.pop("panel_id", None)
        try:
            panel = VisionPanel.objects.get(pk=panel_id, scope_type=ResourceScopeType.PLATFORM)
        except VisionPanel.DoesNotExist:
            raise ScenePanelNotExist()

        with transaction.atomic():
            for field in ["name", "category", "description", "status"]:
                if field in validated_request_data:
                    setattr(panel, field, validated_request_data[field])
            panel.save()

            visibility_data = validated_request_data.get("visibility")
            if visibility_data:
                ResourceVisibility.objects.update_or_create(
                    resource_type=ResourceVisibilityType.PANEL,
                    resource_id=str(panel.pk),
                    defaults={
                        "visibility_type": visibility_data.get("visibility_type", VisibilityScope.ALL_VISIBLE),
                        "scene_ids": visibility_data.get("scene_ids", []),
                        "system_ids": visibility_data.get("system_ids", []),
                    },
                )

        return {"id": panel.pk, "name": panel.name}


class DeletePlatformPanel(BKVision):
    """删除平台级报表"""

    name = gettext_lazy("删除平台级报表")

    def perform_request(self, validated_request_data):
        from services.web.scene.constants import (
            PanelStatus,
            ResourceScopeType,
            ResourceVisibilityType,
        )
        from services.web.scene.models import ResourceVisibility
        from services.web.vision.exceptions import (
            ScenePanelCannotDelete,
            ScenePanelNotExist,
        )

        panel_id = validated_request_data.get("panel_id")
        try:
            panel = VisionPanel.objects.get(pk=panel_id, scope_type=ResourceScopeType.PLATFORM)
        except VisionPanel.DoesNotExist:
            raise ScenePanelNotExist()

        if panel.status == PanelStatus.PUBLISHED:
            raise ScenePanelCannotDelete()

        ResourceVisibility.objects.filter(
            resource_type=ResourceVisibilityType.PANEL, resource_id=str(panel.pk)
        ).delete()
        panel.delete()
        return {"message": "success"}


class PublishPlatformPanel(BKVision):
    """上架/下架平台级报表"""

    name = gettext_lazy("上架/下架平台级报表")

    def perform_request(self, validated_request_data):
        from services.web.scene.constants import PanelStatus, ResourceScopeType
        from services.web.vision.exceptions import ScenePanelNotExist

        panel_id = validated_request_data.get("panel_id")
        try:
            panel = VisionPanel.objects.get(pk=panel_id, scope_type=ResourceScopeType.PLATFORM)
        except VisionPanel.DoesNotExist:
            raise ScenePanelNotExist()

        if panel.status == PanelStatus.PUBLISHED:
            panel.status = PanelStatus.UNPUBLISHED
        else:
            panel.status = PanelStatus.PUBLISHED
        panel.save()
        return {"id": panel.pk, "name": panel.name, "status": panel.status}


class CreateScenePanel(BKVision):
    """创建场景级报表"""

    name = gettext_lazy("创建场景级报表")

    def perform_request(self, validated_request_data):
        from core.utils.data import unique_id
        from services.web.scene.constants import ResourceScopeType

        scene_id = validated_request_data.get("scene_id")

        panel = VisionPanel.objects.create(
            id=validated_request_data.get("id") or unique_id(),
            name=validated_request_data["name"],
            category=validated_request_data.get("category", ""),
            description=validated_request_data.get("description", ""),
            scope_type=ResourceScopeType.SCENE,
            scene_id=int(scene_id),
        )
        return {"id": panel.pk, "name": panel.name}


class UpdateScenePanel(BKVision):
    """编辑场景级报表"""

    name = gettext_lazy("编辑场景级报表")

    def perform_request(self, validated_request_data):
        from services.web.scene.constants import ResourceScopeType
        from services.web.vision.exceptions import ScenePanelNotExist

        scene_id = validated_request_data.pop("scene_id", None)
        panel_id = validated_request_data.pop("panel_id", None)

        try:
            panel = VisionPanel.objects.get(pk=panel_id, scope_type=ResourceScopeType.SCENE, scene_id=int(scene_id))
        except VisionPanel.DoesNotExist:
            raise ScenePanelNotExist()

        for field in ["name", "category", "description"]:
            if field in validated_request_data:
                setattr(panel, field, validated_request_data[field])
        panel.save()
        return {"id": panel.pk, "name": panel.name}


class DeleteScenePanel(BKVision):
    """删除场景级报表"""

    name = gettext_lazy("删除场景级报表")

    def perform_request(self, validated_request_data):
        from services.web.scene.constants import ResourceScopeType
        from services.web.vision.exceptions import ScenePanelNotExist

        scene_id = validated_request_data.get("scene_id")
        panel_id = validated_request_data.get("panel_id")

        try:
            panel = VisionPanel.objects.get(pk=panel_id, scope_type=ResourceScopeType.SCENE, scene_id=int(scene_id))
        except VisionPanel.DoesNotExist:
            raise ScenePanelNotExist()

        panel.delete()
        return {"message": "success"}
