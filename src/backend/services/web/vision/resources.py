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
from collections import defaultdict
from typing import Dict, List

from bk_resource import api
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils.translation import gettext_lazy
from rest_framework import serializers as drf_serializers
from rest_framework.generics import get_object_or_404

from apps.audit.resources import AuditMixinResource
from apps.permission.handlers.actions import ActionEnum
from core.models import get_request_username
from services.web.common.constants import ScopeType
from services.web.common.scope_permission import ScopeContext, ScopePermission
from services.web.scene.binding_validation import assert_binding_relation_integrity
from services.web.scene.constants import (
    BindingType,
    PanelStatus,
    ResourceVisibilityType,
    VisibilityScope,
)
from services.web.scene.filters import CompositeScopeFilter
from services.web.scene.models import (
    ResourceBinding,
    ResourceBindingScene,
    ResourceBindingSystem,
    Scene,
)
from services.web.vision.constants import (
    PANEL,
    PLATFORM_REPORT_GROUP_NAME,
    PLATFORM_REPORT_GROUP_PRIORITY,
    ReportGroupType,
)
from services.web.vision.handlers.query import VisionHandler
from services.web.vision.models import (
    ReportUserPreference,
    Scenario,
    SceneReportGroup,
    SceneReportGroupItem,
    UserPanelFavorite,
    VisionPanel,
    VisionPanelInstance,
)
from services.web.vision.serializers import (
    CreatePlatformPanelRequestSerializer,
    CreateScenePanelRequestSerializer,
    CreateSceneReportGroupRequestSerializer,
    DeleteScenePanelRequestSerializer,
    DeleteSceneReportGroupRequestSerializer,
    PanelGroupListQuerySerializer,
    PanelPreferenceSerializer,
    PanelPublishResponseSerializer,
    PanelSquareListItemSerializer,
    PanelSquareListQuerySerializer,
    PlatformPanelListItemSerializer,
    PlatformPanelListQuerySerializer,
    PlatformPanelOperateRequestSerializer,
    QueryMetaReqSerializer,
    QueryShareDetailSerializer,
    ScenePanelListItemSerializer,
    ScenePanelListQuerySerializer,
    ScenePanelOperateRequestSerializer,
    SceneReportGroupListItemSerializer,
    SceneReportGroupOrderRequestSerializer,
    SceneReportGroupPanelOrderRequestSerializer,
    SceneReportGroupSerializer,
    TogglePanelFavoriteRequestSerializer,
    TogglePanelFavoriteResponseSerializer,
    UpdatePanelPreferenceRequestSerializer,
    UpdatePlatformPanelRequestSerializer,
    UpdateScenePanelRequestSerializer,
    UpdateSceneReportGroupRequestSerializer,
)


class BKVision(AuditMixinResource, abc.ABC):
    tags = ["BKVision"]

    @staticmethod
    def _ensure_binding_integrity_or_raise(binding: ResourceBinding) -> None:
        try:
            assert_binding_relation_integrity(binding)
        except ValueError:
            raise drf_serializers.ValidationError({"binding": gettext_lazy("资源绑定关系不合法")})

    @classmethod
    def _get_or_create_platform_group(cls, scene_id: int) -> SceneReportGroup:
        group, _ = SceneReportGroup.objects.get_or_create(
            scene_id=scene_id,
            name=PLATFORM_REPORT_GROUP_NAME,
            defaults={
                "group_type": ReportGroupType.PLATFORM,
                "priority_index": PLATFORM_REPORT_GROUP_PRIORITY,
            },
        )
        if group.group_type != ReportGroupType.PLATFORM:
            group.group_type = ReportGroupType.PLATFORM
            group.priority_index = PLATFORM_REPORT_GROUP_PRIORITY
            group.save(update_fields=["group_type", "priority_index"])
        return group

    @staticmethod
    def _resolve_binding_visible_scene_ids(binding: ResourceBinding) -> List[int]:
        """根据绑定配置解析“当前可见场景”集合。"""
        if binding.visibility_type in {VisibilityScope.ALL_VISIBLE, VisibilityScope.ALL_SCENES}:
            return list(Scene.objects.values_list("scene_id", flat=True))
        if binding.visibility_type == VisibilityScope.SPECIFIC_SCENES:
            return list(binding.binding_scenes.values_list("scene_id", flat=True))
        return []

    @classmethod
    def _sync_platform_panel_scene_group_items(cls, panel_id: str, scene_ids: List[int], prune: bool = False) -> None:
        """将平台报表分配到可见场景的平台分组；prune=True 时清理不可见场景归组。"""
        target_scene_ids = sorted({int(item) for item in scene_ids})

        if target_scene_ids:
            panel_scene_ids = set(
                SceneReportGroupItem.objects.filter(
                    panel_id=panel_id,
                    group__scene_id__in=target_scene_ids,
                ).values_list("group__scene_id", flat=True)
            )
            to_create = []
            for scene_id in target_scene_ids:
                if scene_id in panel_scene_ids:
                    continue
                group = cls._get_or_create_platform_group(scene_id=scene_id)
                to_create.append(SceneReportGroupItem(panel_id=panel_id, group=group, priority_index=0))
            if to_create:
                SceneReportGroupItem.objects.bulk_create(to_create, ignore_conflicts=True)

        if prune:
            stale_qs = SceneReportGroupItem.objects.filter(panel_id=panel_id, group__scene_id__isnull=False)
            if target_scene_ids:
                stale_qs = stale_qs.exclude(group__scene_id__in=target_scene_ids)
            stale_qs.delete()

    @classmethod
    def _get_binding_map(cls, panel_ids: List[str]) -> Dict[str, ResourceBinding]:
        return {
            binding.resource_id: binding
            for binding in ResourceBinding.objects.filter(
                resource_type=ResourceVisibilityType.PANEL,
                resource_id__in=panel_ids,
            )
            .prefetch_related("binding_scenes", "binding_systems")
            .all()
        }

    @staticmethod
    def _upsert_single_scene_group_item(scene_id: int, panel: VisionPanel, target_group: SceneReportGroup) -> None:
        """业务层保证：同一场景下，一个报表仅保留一个归组关系。"""
        items = list(
            SceneReportGroupItem.objects.select_for_update()
            .filter(group__scene_id=scene_id, panel=panel)
            .order_by("id")
        )
        if not items:
            SceneReportGroupItem.objects.create(group=target_group, panel=panel, priority_index=0)
            return

        primary = items[0]
        if primary.group_id != target_group.id:
            primary.group = target_group
            primary.save(update_fields=["group_id"])

        if len(items) > 1:
            SceneReportGroupItem.objects.filter(id__in=[item.id for item in items[1:]]).delete()


class ListPanels(BKVision):
    name = gettext_lazy("报告广场报表列表")
    ResponseSerializer = PanelSquareListItemSerializer
    RequestSerializer = PanelSquareListQuerySerializer
    many_response_data = True
    audit_action = ActionEnum.LIST_BASE_PANEL

    def perform_request(self, validated_request_data):
        scope_type = validated_request_data["scope_type"]
        scope = ScopeContext(
            scope_type=scope_type,
            scope_id=validated_request_data.get("scope_id"),
        )
        scope_permission = ScopePermission(username=get_request_username())
        scene_ids = scope_permission.get_scene_ids(scope, ActionEnum.VIEW_SCENE)
        system_ids = scope_permission.get_system_ids(scope, ActionEnum.VIEW_SYSTEM)
        queryset = CompositeScopeFilter.filter_queryset(
            queryset=VisionPanel.objects.filter(scenario=validated_request_data.get("scenario", Scenario.DEFAULT)),
            binding_type=validated_request_data.get("binding_type"),
            scene_id=scene_ids,
            system_id=system_ids,
            resource_type=ResourceVisibilityType.PANEL,
            pk_field="id",
        ).order_by("-updated_at", "id")
        keyword = validated_request_data.get("keyword", "")
        status = validated_request_data.get("status")
        if keyword:
            queryset = queryset.filter(Q(name__icontains=keyword) | Q(description__icontains=keyword))
        if status:
            queryset = queryset.filter(status=status)

        panels = list(queryset)
        panel_ids = [str(panel.id) for panel in panels]
        group_map = defaultdict(list)
        group_items = (
            SceneReportGroupItem.objects.filter(panel_id__in=panel_ids, group__scene_id__in=scene_ids)
            .values("panel_id", "group_id")
            .order_by("-group__priority_index", "-priority_index", "id")
        )
        for item in group_items:
            group_map[str(item["panel_id"])].append(item["group_id"])
        favorite_map = {
            str(item["panel_id"]): item["created_at"]
            for item in UserPanelFavorite.objects.filter(
                username=get_request_username(),
                panel_id__in=panel_ids,
            ).values("panel_id", "created_at")
        }

        data = []
        for panel in panels:
            panel_id = str(panel.id)
            data.append(
                {
                    "id": panel.id,
                    "name": panel.name or "",
                    "status": panel.status,
                    "category": panel.category,
                    "description": panel.description,
                    "group_ids": group_map.get(panel_id, []),
                    "favorite_created_at": favorite_map.get(panel_id),
                }
            )
        return data


class ListSceneReportGroup(BKVision):
    """报表分组列表。

    入参：scope_type/scope_id。
    规则：system/cross_system 视角固定返回空列表；scene/cross_scene 返回有权限场景分组。
    """

    name = gettext_lazy("报表分组列表")
    RequestSerializer = PanelGroupListQuerySerializer
    ResponseSerializer = SceneReportGroupListItemSerializer
    many_response_data = True
    audit_action = ActionEnum.LIST_BASE_PANEL

    def perform_request(self, validated_request_data):
        scope_type = validated_request_data["scope_type"]
        if scope_type in {ScopeType.SYSTEM, ScopeType.CROSS_SYSTEM}:
            return []

        scope = ScopeContext(
            scope_type=scope_type,
            scope_id=validated_request_data.get("scope_id"),
        )
        scope_permission = ScopePermission(username=get_request_username())
        scene_ids = scope_permission.get_scene_ids(scope, ActionEnum.VIEW_SCENE)
        if not scene_ids:
            return []

        return list(
            SceneReportGroup.objects.filter(scene_id__in=scene_ids)
            .order_by("-priority_index", "id")
            .values("id", "scene_id", "name", "group_type", "priority_index")
        )


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
    RequestSerializer = CreatePlatformPanelRequestSerializer

    def perform_request(self, validated_request_data):
        from core.utils.data import unique_id
        from services.web.scene.constants import PanelStatus

        visibility_data = validated_request_data.pop("visibility", None) or {}
        with transaction.atomic():
            panel = VisionPanel.objects.create(
                id=unique_id(),
                vision_id=validated_request_data.get("vision_id"),
                name=validated_request_data["name"],
                category=validated_request_data.get("category", ""),
                description=validated_request_data.get("description", ""),
                status=validated_request_data.get("status", PanelStatus.UNPUBLISHED),
            )

            # 创建平台级绑定关系
            binding = ResourceBinding.objects.create(
                resource_type=ResourceVisibilityType.PANEL,
                resource_id=str(panel.pk),
                binding_type=BindingType.PLATFORM_BINDING,
                visibility_type=VisibilityScope.ALL_VISIBLE,
            )

            # 处理可见范围配置
            if visibility_data:
                binding.visibility_type = visibility_data.get("visibility_type", VisibilityScope.ALL_VISIBLE)
                binding.save(update_fields=["visibility_type"])
                # 创建场景关联
                for sid in visibility_data.get("scene_ids", []):
                    ResourceBindingScene.objects.create(binding=binding, scene_id=sid)
                # 创建系统关联
                for sys_id in visibility_data.get("system_ids", []):
                    ResourceBindingSystem.objects.create(binding=binding, system_id=sys_id)
            self._ensure_binding_integrity_or_raise(binding)
            self._sync_platform_panel_scene_group_items(
                panel_id=str(panel.pk),
                scene_ids=self._resolve_binding_visible_scene_ids(binding),
                prune=True,
            )

        return {"id": panel.pk, "name": panel.name}


class UpdatePlatformPanel(BKVision):
    """编辑平台级报表"""

    name = gettext_lazy("编辑平台级报表")
    RequestSerializer = UpdatePlatformPanelRequestSerializer

    def perform_request(self, validated_request_data):
        from services.web.vision.exceptions import ScenePanelNotExist

        panel_id = validated_request_data.pop("panel_id", None)
        # 通过 ResourceBinding 确认是平台级报表
        try:
            binding = ResourceBinding.objects.get(
                resource_type=ResourceVisibilityType.PANEL,
                resource_id=str(panel_id),
                binding_type=BindingType.PLATFORM_BINDING,
            )
        except ResourceBinding.DoesNotExist:
            raise ScenePanelNotExist()

        try:
            panel = VisionPanel.objects.get(pk=panel_id)
        except VisionPanel.DoesNotExist:
            raise ScenePanelNotExist()

        visibility_data = validated_request_data.pop("visibility", None)
        with transaction.atomic():
            for field in ["name", "category", "description", "status", "vision_id"]:
                if field in validated_request_data:
                    setattr(panel, field, validated_request_data[field])
            panel.save()

            if visibility_data:
                binding.visibility_type = visibility_data.get("visibility_type", VisibilityScope.ALL_VISIBLE)
                binding.save(update_fields=["visibility_type"])
                # 重建场景关联
                binding.binding_scenes.all().delete()
                for sid in visibility_data.get("scene_ids", []):
                    ResourceBindingScene.objects.create(binding=binding, scene_id=sid)
                # 重建系统关联
                binding.binding_systems.all().delete()
                for sys_id in visibility_data.get("system_ids", []):
                    ResourceBindingSystem.objects.create(binding=binding, system_id=sys_id)
            self._ensure_binding_integrity_or_raise(binding)

            if visibility_data is not None:
                self._sync_platform_panel_scene_group_items(
                    panel_id=str(panel.pk),
                    scene_ids=self._resolve_binding_visible_scene_ids(binding),
                    prune=True,
                )

        return {"id": panel.pk, "name": panel.name}


class DeletePlatformPanel(BKVision):
    """删除平台级报表"""

    name = gettext_lazy("删除平台级报表")
    RequestSerializer = PlatformPanelOperateRequestSerializer

    def perform_request(self, validated_request_data):
        from services.web.scene.constants import PanelStatus
        from services.web.vision.exceptions import (
            ScenePanelCannotDelete,
            ScenePanelNotExist,
        )

        panel_id = validated_request_data.get("panel_id")
        # 通过 ResourceBinding 确认是平台级报表
        try:
            binding = ResourceBinding.objects.get(
                resource_type=ResourceVisibilityType.PANEL,
                resource_id=str(panel_id),
                binding_type=BindingType.PLATFORM_BINDING,
            )
        except ResourceBinding.DoesNotExist:
            raise ScenePanelNotExist()

        try:
            panel = VisionPanel.objects.get(pk=panel_id)
        except VisionPanel.DoesNotExist:
            raise ScenePanelNotExist()
        self._ensure_binding_integrity_or_raise(binding)

        if panel.status == PanelStatus.PUBLISHED:
            raise ScenePanelCannotDelete()

        # 删除绑定关系（级联删除关联的场景和系统）
        binding.delete()
        panel.delete()
        return {"message": "success"}


class PublishPlatformPanel(BKVision):
    """上架/下架平台级报表"""

    name = gettext_lazy("上架/下架平台级报表")
    RequestSerializer = PlatformPanelOperateRequestSerializer
    ResponseSerializer = PanelPublishResponseSerializer

    def perform_request(self, validated_request_data):
        from services.web.scene.constants import PanelStatus
        from services.web.vision.exceptions import ScenePanelNotExist

        panel_id = validated_request_data.get("panel_id")
        # 通过 ResourceBinding 确认是平台级报表
        binding = ResourceBinding.objects.filter(
            resource_type=ResourceVisibilityType.PANEL,
            resource_id=str(panel_id),
            binding_type=BindingType.PLATFORM_BINDING,
        ).first()
        if not binding:
            raise ScenePanelNotExist()
        self._ensure_binding_integrity_or_raise(binding)

        try:
            panel = VisionPanel.objects.get(pk=panel_id)
        except VisionPanel.DoesNotExist:
            raise ScenePanelNotExist()

        if panel.status == PanelStatus.PUBLISHED:
            panel.status = PanelStatus.UNPUBLISHED
        else:
            panel.status = PanelStatus.PUBLISHED
        panel.save(update_fields=["status"])
        return panel


class CreateScenePanel(BKVision):
    """创建场景级报表"""

    name = gettext_lazy("创建场景级报表")
    RequestSerializer = CreateScenePanelRequestSerializer

    def perform_request(self, validated_request_data):
        from core.utils.data import unique_id

        scene_id = validated_request_data.get("scene_id")
        group_id = validated_request_data.get("group_id")
        group = get_object_or_404(SceneReportGroup, id=group_id, scene_id=int(scene_id))

        with transaction.atomic():
            panel = VisionPanel.objects.create(
                id=unique_id(),
                vision_id=validated_request_data.get("vision_id"),
                name=validated_request_data["name"],
                category=validated_request_data.get("category", ""),
                description=validated_request_data.get("description", ""),
            )

            # 创建场景级绑定关系（有且仅有一个场景关联）
            binding = ResourceBinding.objects.create(
                resource_type=ResourceVisibilityType.PANEL,
                resource_id=str(panel.pk),
                binding_type=BindingType.SCENE_BINDING,
            )
            ResourceBindingScene.objects.create(binding=binding, scene_id=int(scene_id))
            self._ensure_binding_integrity_or_raise(binding)
            self._upsert_single_scene_group_item(scene_id=int(scene_id), panel=panel, target_group=group)

        return {"id": panel.pk, "name": panel.name}


class UpdateScenePanel(BKVision):
    """编辑场景级报表。

    入参：scene_id、panel_id、group_id 及可选 name/category/description。
    行为：更新报表基础信息，并将该报表在场景内归组更新为目标分组（单场景单分组）。
    """

    name = gettext_lazy("编辑场景级报表")
    RequestSerializer = UpdateScenePanelRequestSerializer

    @transaction.atomic
    def perform_request(self, validated_request_data):
        from services.web.vision.exceptions import ScenePanelNotExist

        scene_id = validated_request_data.pop("scene_id", None)
        group_id = validated_request_data.pop("group_id", None)
        panel_id = validated_request_data.pop("panel_id", None)

        # 通过 ResourceBinding + ResourceBindingScene 确认是该场景的报表
        try:
            binding = ResourceBinding.objects.get(
                resource_type=ResourceVisibilityType.PANEL,
                resource_id=str(panel_id),
                binding_type=BindingType.SCENE_BINDING,
            )
        except ResourceBinding.DoesNotExist:
            raise ScenePanelNotExist()
        self._ensure_binding_integrity_or_raise(binding)

        if not binding.binding_scenes.filter(scene_id=int(scene_id)).exists():
            raise ScenePanelNotExist()

        try:
            panel = VisionPanel.objects.get(pk=panel_id)
        except VisionPanel.DoesNotExist:
            raise ScenePanelNotExist()

        for field in ["name", "category", "description", "vision_id"]:
            if field in validated_request_data:
                setattr(panel, field, validated_request_data[field])
        panel.save()

        target_group = get_object_or_404(SceneReportGroup, id=group_id, scene_id=int(scene_id))
        self._upsert_single_scene_group_item(scene_id=int(scene_id), panel=panel, target_group=target_group)
        return {"id": panel.pk, "name": panel.name}


class DeleteScenePanel(BKVision):
    """删除场景级报表"""

    name = gettext_lazy("删除场景级报表")
    RequestSerializer = DeleteScenePanelRequestSerializer

    def perform_request(self, validated_request_data):
        from services.web.vision.exceptions import ScenePanelNotExist

        scene_id = validated_request_data.get("scene_id")
        panel_id = validated_request_data.get("panel_id")

        # 通过 ResourceBinding + ResourceBindingScene 确认是该场景的报表
        try:
            binding = ResourceBinding.objects.get(
                resource_type=ResourceVisibilityType.PANEL,
                resource_id=str(panel_id),
                binding_type=BindingType.SCENE_BINDING,
            )
        except ResourceBinding.DoesNotExist:
            raise ScenePanelNotExist()
        self._ensure_binding_integrity_or_raise(binding)

        if not binding.binding_scenes.filter(scene_id=int(scene_id)).exists():
            raise ScenePanelNotExist()

        try:
            panel = VisionPanel.objects.get(pk=panel_id)
        except VisionPanel.DoesNotExist:
            raise ScenePanelNotExist()

        # 删除绑定关系（级联删除关联的场景）
        binding.delete()
        panel.delete()
        return {"message": "success"}


class PublishScenePanel(BKVision):
    """场景管理侧上架/下架报表（仅场景级报表）。

    入参：scene_id、panel_id。
    出参：id、name、status。
    """

    name = gettext_lazy("上架/下架场景报表")
    RequestSerializer = ScenePanelOperateRequestSerializer
    ResponseSerializer = PanelPublishResponseSerializer

    def perform_request(self, validated_request_data):
        from services.web.vision.exceptions import ScenePanelNotExist

        scene_id = int(validated_request_data.get("scene_id"))
        panel_id = validated_request_data.get("panel_id")

        try:
            binding = ResourceBinding.objects.get(
                resource_type=ResourceVisibilityType.PANEL,
                resource_id=str(panel_id),
                binding_type=BindingType.SCENE_BINDING,
            )
        except ResourceBinding.DoesNotExist:
            raise ScenePanelNotExist()
        self._ensure_binding_integrity_or_raise(binding)

        if not binding.binding_scenes.filter(scene_id=scene_id).exists():
            raise ScenePanelNotExist()

        try:
            panel = VisionPanel.objects.get(pk=panel_id)
        except VisionPanel.DoesNotExist:
            raise ScenePanelNotExist()

        if panel.status == PanelStatus.PUBLISHED:
            panel.status = PanelStatus.UNPUBLISHED
        else:
            panel.status = PanelStatus.PUBLISHED
        panel.save(update_fields=["status"])
        return panel


class ListPlatformPanels(BKVision):
    """平台管理侧报表列表。"""

    name = gettext_lazy("平台管理报表列表")
    RequestSerializer = PlatformPanelListQuerySerializer
    ResponseSerializer = PlatformPanelListItemSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        binding_qs = ResourceBinding.objects.filter(
            resource_type=ResourceVisibilityType.PANEL,
            binding_type=BindingType.PLATFORM_BINDING,
        )
        panel_ids = list(binding_qs.values_list("resource_id", flat=True))
        queryset = VisionPanel.objects.filter(id__in=panel_ids)

        status = validated_request_data.get("status")
        name = validated_request_data.get("name") or ""
        description = validated_request_data.get("description") or ""
        if status:
            queryset = queryset.filter(status=status)
        if name:
            queryset = queryset.filter(name__icontains=name)
        if description:
            queryset = queryset.filter(description__icontains=description)

        bindings = self._get_binding_map(panel_ids=list(queryset.values_list("id", flat=True)))
        data = []
        for panel in queryset.order_by("-updated_at", "id"):
            binding = bindings.get(str(panel.id))
            if not binding:
                continue
            data.append(
                {
                    "id": panel.id,
                    "name": panel.name or "",
                    "status": panel.status,
                    "category": panel.category,
                    "description": panel.description,
                    "visibility_type": binding.visibility_type,
                    "scene_ids": list(binding.binding_scenes.values_list("scene_id", flat=True)),
                    "system_ids": list(binding.binding_systems.values_list("system_id", flat=True)),
                }
            )
        return data


class ListScenePanels(BKVision):
    """场景管理侧报表列表（扁平）。"""

    name = gettext_lazy("场景报表列表")
    RequestSerializer = ScenePanelListQuerySerializer
    ResponseSerializer = ScenePanelListItemSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        scene_id = int(validated_request_data["scene_id"])
        keyword = validated_request_data.get("keyword") or ""
        status = validated_request_data.get("status")

        queryset = CompositeScopeFilter.filter_queryset(
            queryset=VisionPanel.objects.all(),
            scene_id=[scene_id],
            system_id=[],
            resource_type=ResourceVisibilityType.PANEL,
            pk_field="id",
        )
        if keyword:
            queryset = queryset.filter(Q(name__icontains=keyword) | Q(description__icontains=keyword))
        if status:
            queryset = queryset.filter(status=status)

        panels = list(queryset)
        panel_ids = [str(item.id) for item in panels]
        binding_map = self._get_binding_map(panel_ids=panel_ids)
        scene_items = {
            str(item.panel_id): item
            for item in SceneReportGroupItem.objects.filter(group__scene_id=scene_id, panel_id__in=panel_ids)
            .select_related("group")
            .order_by("-group__priority_index", "-priority_index", "id")
        }
        data = []
        for panel in panels:
            item = scene_items.get(str(panel.id))
            binding = binding_map.get(str(panel.id))
            data.append(
                {
                    "id": panel.id,
                    "name": panel.name or "",
                    "status": panel.status,
                    "category": panel.category,
                    "description": panel.description,
                    "group_id": item.group_id if item else None,
                    "group_name": item.group.name if item else "",
                    "group_type": item.group.group_type if item else "",
                    "binding_type": binding.binding_type if binding else "",
                }
            )
        return data


class CreateSceneReportGroup(BKVision):
    name = gettext_lazy("创建场景报表分组")
    RequestSerializer = CreateSceneReportGroupRequestSerializer
    ResponseSerializer = SceneReportGroupSerializer

    def perform_request(self, validated_request_data):
        try:
            group = SceneReportGroup.objects.create(
                scene_id=validated_request_data["scene_id"],
                name=validated_request_data["name"],
                group_type=ReportGroupType.CUSTOM,
                priority_index=validated_request_data.get("priority_index", 0),
            )
        except IntegrityError:
            raise drf_serializers.ValidationError({"name": "同一场景下分组名称已存在"})
        return group


class UpdateSceneReportGroup(BKVision):
    name = gettext_lazy("更新场景报表分组")
    RequestSerializer = UpdateSceneReportGroupRequestSerializer
    ResponseSerializer = SceneReportGroupSerializer

    def perform_request(self, validated_request_data):
        group = get_object_or_404(
            SceneReportGroup,
            id=validated_request_data["group_id"],
            scene_id=validated_request_data["scene_id"],
        )
        if group.group_type == ReportGroupType.PLATFORM and "name" in validated_request_data:
            raise drf_serializers.ValidationError({"name": "平台报表分组不支持重命名"})
        if "name" in validated_request_data:
            group.name = validated_request_data["name"]
        if "priority_index" in validated_request_data:
            group.priority_index = validated_request_data["priority_index"]
        try:
            group.save()
        except IntegrityError:
            raise drf_serializers.ValidationError({"name": "同一场景下分组名称已存在"})
        return group


class DeleteSceneReportGroup(BKVision):
    """删除场景报表分组。

    仅允许删除空分组；分组下仍存在报表时返回校验错误，避免报表处于无分组状态。
    """

    name = gettext_lazy("删除场景报表分组")
    RequestSerializer = DeleteSceneReportGroupRequestSerializer

    def perform_request(self, validated_request_data):
        group = get_object_or_404(
            SceneReportGroup,
            id=validated_request_data["group_id"],
            scene_id=validated_request_data["scene_id"],
        )
        if group.items.exists():
            raise drf_serializers.ValidationError({"group_id": "分组下仍有报表，无法删除"})
        group.delete()
        return {"message": "success"}


class UpdateSceneReportGroupOrder(BKVision):
    name = gettext_lazy("更新场景分组排序")
    RequestSerializer = SceneReportGroupOrderRequestSerializer

    @transaction.atomic
    def perform_request(self, validated_request_data):
        scene_id = validated_request_data["scene_id"]
        order_list = validated_request_data["groups"]
        group_ids = [item["group_id"] for item in order_list]
        groups = {group.id: group for group in SceneReportGroup.objects.filter(id__in=group_ids, scene_id=scene_id)}
        missing_groups = set(group_ids) - set(groups.keys())
        if missing_groups:
            raise drf_serializers.ValidationError({"groups": f"group not found: {sorted(missing_groups)}"})

        to_update = []
        for item in order_list:
            group = groups[item["group_id"]]
            group.priority_index = item["priority_index"]
            to_update.append(group)
        SceneReportGroup.objects.bulk_update(to_update, fields=["priority_index"], update_record=False)
        return {"message": "success"}


class UpdateSceneReportGroupPanelOrder(BKVision):
    """批量更新场景内报表归组及排序。

    入参 items=[{panel_id, group_id, priority_index}]，会在事务内完成移动与排序。
    """

    name = gettext_lazy("更新场景报表归组排序")
    RequestSerializer = SceneReportGroupPanelOrderRequestSerializer

    @transaction.atomic
    def perform_request(self, validated_request_data):
        scene_id = validated_request_data["scene_id"]
        order_list = validated_request_data["items"]
        panel_ids = [item["panel_id"] for item in order_list]
        group_ids = [item["group_id"] for item in order_list]
        groups = {group.id: group for group in SceneReportGroup.objects.filter(id__in=group_ids, scene_id=scene_id)}
        missing_groups = set(group_ids) - set(groups.keys())
        if missing_groups:
            raise drf_serializers.ValidationError({"items": f"group not found: {sorted(missing_groups)}"})

        accessible_panel_ids = set(
            CompositeScopeFilter.filter_queryset(
                queryset=VisionPanel.objects.filter(id__in=panel_ids),
                scene_id=[scene_id],
                system_id=[],
                resource_type=ResourceVisibilityType.PANEL,
                pk_field="id",
            ).values_list("id", flat=True)
        )
        missing_panels = set(panel_ids) - {str(item) for item in accessible_panel_ids}
        if missing_panels:
            raise drf_serializers.ValidationError({"items": f"panel not found: {sorted(missing_panels)}"})

        items_in_scene = SceneReportGroupItem.objects.filter(group__scene_id=scene_id, panel_id__in=panel_ids).order_by(
            "id"
        )
        item_map: Dict[str, SceneReportGroupItem] = {}
        duplicate_ids = []
        for item in items_in_scene:
            panel_key = str(item.panel_id)
            if panel_key in item_map:
                duplicate_ids.append(item.id)
                continue
            item_map[panel_key] = item
        if duplicate_ids:
            SceneReportGroupItem.objects.filter(id__in=duplicate_ids).delete()

        to_create = []
        to_update = []
        for item in order_list:
            panel_id = str(item["panel_id"])
            target_group = groups[item["group_id"]]
            existing = item_map.get(panel_id)
            if existing:
                existing.group = target_group
                existing.priority_index = item["priority_index"]
                to_update.append(existing)
                continue
            to_create.append(
                SceneReportGroupItem(
                    panel_id=panel_id,
                    group=target_group,
                    priority_index=item["priority_index"],
                )
            )
        if to_create:
            SceneReportGroupItem.objects.bulk_create(to_create)
        if to_update:
            SceneReportGroupItem.objects.bulk_update(
                to_update,
                fields=["group_id", "priority_index"],
                update_record=False,
            )
        return {"message": "success"}


class TogglePanelFavorite(BKVision):
    name = gettext_lazy("收藏/取消收藏报表")
    RequestSerializer = TogglePanelFavoriteRequestSerializer
    ResponseSerializer = TogglePanelFavoriteResponseSerializer

    def perform_request(self, validated_request_data):
        username = get_request_username()
        panel = get_object_or_404(VisionPanel, id=validated_request_data["panel_id"])
        favorite = validated_request_data["favorite"]
        if favorite:
            UserPanelFavorite.objects.get_or_create(username=username, panel=panel)
        else:
            UserPanelFavorite.objects.filter(username=username, panel=panel).delete()
        return {"favorite": favorite}


class GetPanelPreference(BKVision):
    name = gettext_lazy("获取报表偏好")
    ResponseSerializer = PanelPreferenceSerializer

    def perform_request(self, validated_request_data):
        pref, _ = ReportUserPreference.objects.get_or_create(username=get_request_username())
        return pref


class UpdatePanelPreference(BKVision):
    name = gettext_lazy("更新报表偏好")
    RequestSerializer = UpdatePanelPreferenceRequestSerializer
    ResponseSerializer = PanelPreferenceSerializer

    def perform_request(self, validated_request_data):
        pref, _ = ReportUserPreference.objects.update_or_create(
            username=get_request_username(),
            defaults={"config": validated_request_data["config"]},
        )
        return pref
