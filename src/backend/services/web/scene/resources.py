# -*- coding: utf-8 -*-
import abc

from bk_resource import resource
from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q
from django.utils.translation import gettext_lazy
from rest_framework import serializers

from apps.audit.resources import AuditMixinResource
from apps.meta.handlers.iam_group import (
    SCENE_MANAGER_GROUP_ACTIONS,
    SCENE_VIEWER_GROUP_ACTIONS,
    IAMGroupManager,
)
from apps.meta.models import System
from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.permission import Permission
from core.models import get_request_username
from services.web.scene.binding_validation import assert_binding_relation_integrity
from services.web.scene.constants import SceneStatus
from services.web.scene.exceptions import (
    RelatedResourceDetail,
    SceneHasRelatedResources,
    SceneNotExist,
)
from services.web.scene.models import Scene, SceneDataTable, SceneSystem
from services.web.scene.serializers import (
    CreateSceneSerializer,
    MyRolePermissionSerializer,
    SceneDetailSerializer,
    SceneFilterSerializer,
    SceneInfoUpdateSerializer,
    SceneListSerializer,
    SceneSimpleListSerializer,
    SceneStatusFilterSerializer,
    UpdateSceneSerializer,
)


class SceneResource(AuditMixinResource, abc.ABC):
    """场景模块 Resource 基类"""

    tags = ["Scene"]

    @staticmethod
    def _sync_iam_group_members(scene, validated_request_data):
        """当 managers 或 users 变更时，同步到对应的 IAM 用户组；若用户组尚未创建则先创建"""

        update_fields = []

        if "managers" in validated_request_data:
            new_group_id = IAMGroupManager.sync_group_members(
                group_id=scene.iam_manager_group_id,
                members=validated_request_data["managers"],
                group_name=f"{scene.name}-管理用户组",
                group_description=f"{scene.name} 场景管理用户组，拥有查看和管理场景权限",
                group_actions=SCENE_MANAGER_GROUP_ACTIONS,
                scene_id=str(scene.scene_id),
                scene_name=scene.name,
            )
            if new_group_id is not None:
                scene.iam_manager_group_id = new_group_id
                update_fields.append("iam_manager_group_id")

        if "users" in validated_request_data:
            new_group_id = IAMGroupManager.sync_group_members(
                group_id=scene.iam_viewer_group_id,
                members=validated_request_data["users"],
                group_name=f"{scene.name}-使用用户组",
                group_description=f"{scene.name} 场景使用用户组，拥有查看场景权限",
                group_actions=SCENE_VIEWER_GROUP_ACTIONS,
                scene_id=str(scene.scene_id),
                scene_name=scene.name,
            )
            if new_group_id is not None:
                scene.iam_viewer_group_id = new_group_id
                update_fields.append("iam_viewer_group_id")

        if update_fields:
            scene.save(update_fields=update_fields)


# ==================== 场景管理 ====================


class ListScene(SceneResource):
    """场景列表"""

    name = gettext_lazy("场景列表")
    RequestSerializer = SceneFilterSerializer
    ResponseSerializer = SceneListSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        queryset = Scene.objects.annotate(
            system_count=Count("scene_systems", distinct=True),
            table_count=Count("scene_tables", distinct=True),
        )
        if "status" in validated_request_data:
            queryset = queryset.filter(status=validated_request_data["status"])
        if validated_request_data.get("keyword"):
            keyword = validated_request_data["keyword"]
            queryset = queryset.filter(Q(name__icontains=keyword) | Q(description__icontains=keyword))
        return queryset


class ListAllScene(SceneResource):
    """场景精简列表"""

    name = gettext_lazy("场景精简列表")
    RequestSerializer = SceneStatusFilterSerializer
    ResponseSerializer = SceneSimpleListSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        queryset = Scene.objects.all()
        if "status" in validated_request_data:
            queryset = queryset.filter(status=validated_request_data["status"])
        return queryset


class GetMyRolePermissions(SceneResource):
    """获取当前用户角色相关权限"""

    name = gettext_lazy("获取当前用户角色相关权限")
    ResponseSerializer = MyRolePermissionSerializer

    def perform_request(self, validated_request_data):
        username = get_request_username()
        permission = Permission(username=username)
        has_local_system_manage_permission = bool(System.get_managed_system_ids(username))

        edit_system = has_local_system_manage_permission or permission.has_action_any_permission(ActionEnum.EDIT_SYSTEM)

        return {
            "manage_platform": permission.has_action_any_permission(ActionEnum.MANAGE_PLATFORM),
            "manage_scene": permission.has_action_any_permission(ActionEnum.MANAGE_SCENE),
            "view_scene": permission.has_action_any_permission(ActionEnum.VIEW_SCENE),
            "edit_system": edit_system,
            "view_system": edit_system or permission.has_action_any_permission(ActionEnum.VIEW_SYSTEM),
        }


class CreateScene(SceneResource):
    """创建场景"""

    name = gettext_lazy("创建场景")
    RequestSerializer = CreateSceneSerializer
    ResponseSerializer = SceneDetailSerializer

    @transaction.atomic
    def perform_request(self, validated_request_data):
        scene = Scene.objects.create(
            name=validated_request_data["name"],
            description=validated_request_data.get("description", ""),
        )

        # 创建系统关联
        self._save_systems(scene, validated_request_data.get("systems", []))
        # 创建数据表关联
        self._save_tables(scene, validated_request_data.get("tables", []))
        # 自动创建"场景管理员通知组"
        self._create_scene_manager_notice_group(scene, validated_request_data["managers"])
        # 创建 IAM 用户组、授权并添加成员（分别创建管理用户组和使用用户组）
        scene.iam_manager_group_id = IAMGroupManager.create_single_group_with_members(
            group_name=f"{scene.name}-管理用户组",
            group_description=f"{scene.name} 场景管理用户组，拥有查看和管理场景权限",
            group_actions=SCENE_MANAGER_GROUP_ACTIONS,
            members=validated_request_data["managers"],
            scene_id=str(scene.scene_id),
            scene_name=scene.name,
        )
        scene.iam_viewer_group_id = IAMGroupManager.create_single_group_with_members(
            group_name=f"{scene.name}-使用用户组",
            group_description=f"{scene.name} 场景使用用户组，拥有查看场景权限",
            group_actions=SCENE_VIEWER_GROUP_ACTIONS,
            members=validated_request_data.get("users", []),
            scene_id=str(scene.scene_id),
            scene_name=scene.name,
        )
        scene.save(update_fields=["iam_manager_group_id", "iam_viewer_group_id"])
        # 新场景补齐全可见平台报表的分组映射
        self._sync_all_visible_platform_panels(scene)

        return scene

    @staticmethod
    def _save_systems(scene, systems):
        for system_data in systems:
            SceneSystem.objects.create(
                scene=scene,
                system_id=system_data.get("system_id", ""),
                is_all_systems=system_data.get("is_all_systems", False),
                filter_rules=system_data.get("filter_rules", []),
            )

    @staticmethod
    def _save_tables(scene, tables):
        for table_data in tables:
            SceneDataTable.objects.create(
                scene=scene,
                table_id=table_data.get("table_id", ""),
                filter_rules=table_data.get("filter_rules", []),
            )

    @staticmethod
    def _create_scene_manager_notice_group(scene, managers):
        """创建场景时自动创建场景管理员通知组"""
        from apps.notice.constants import get_default_notice_config
        from apps.notice.models import NoticeGroup
        from services.web.scene.constants import BindingType, ResourceVisibilityType
        from services.web.scene.models import ResourceBinding, ResourceBindingScene

        notice_group = NoticeGroup.objects.create(
            group_name=f"{scene.name}-场景管理员通知组",
            group_member=managers,
            notice_config=get_default_notice_config(),
            description=f"场景「{scene.name}」的管理员通知组（系统自动创建）",
        )
        # 创建 ResourceBinding 关联
        binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.NOTICE_GROUP,
            resource_id=str(notice_group.group_id),
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=binding, scene_id=scene.scene_id)
        assert_binding_relation_integrity(binding)

    @staticmethod
    def _sync_all_visible_platform_panels(scene):
        from services.web.scene.constants import (
            BindingType,
            ResourceVisibilityType,
            VisibilityScope,
        )
        from services.web.scene.models import ResourceBinding
        from services.web.vision.constants import (
            PLATFORM_REPORT_GROUP_NAME,
            PLATFORM_REPORT_GROUP_PRIORITY,
            ReportGroupType,
        )
        from services.web.vision.models import (
            SceneReportGroup,
            SceneReportGroupItem,
            VisionPanel,
        )

        platform_group, _ = SceneReportGroup.objects.get_or_create(
            scene=scene,
            name=PLATFORM_REPORT_GROUP_NAME,
            defaults={"group_type": ReportGroupType.PLATFORM, "priority_index": PLATFORM_REPORT_GROUP_PRIORITY},
        )
        platform_bindings = ResourceBinding.objects.filter(
            resource_type=ResourceVisibilityType.PANEL,
            binding_type=BindingType.PLATFORM_BINDING,
            visibility_type__in=[VisibilityScope.ALL_VISIBLE, VisibilityScope.ALL_SCENES],
        ).values_list("resource_id", flat=True)
        panels = VisionPanel.objects.filter(id__in=list(platform_bindings))
        existing_panel_ids = set(
            SceneReportGroupItem.objects.filter(
                group=platform_group, panel_id__in=panels.values_list("id", flat=True)
            ).values_list("panel_id", flat=True)
        )
        to_create = [
            SceneReportGroupItem(group=platform_group, panel=panel, priority_index=0)
            for panel in panels
            if panel.id not in existing_panel_ids
        ]
        if to_create:
            SceneReportGroupItem.objects.bulk_create(to_create, ignore_conflicts=True)


class RetrieveScene(SceneResource):
    """场景详情"""

    name = gettext_lazy("场景详情")
    ResponseSerializer = SceneDetailSerializer

    def perform_request(self, validated_request_data):
        scene_id = validated_request_data["scene_id"]
        try:
            scene = Scene.objects.get(scene_id=scene_id)
        except Scene.DoesNotExist:
            raise SceneNotExist()
        return scene


class UpdateScene(SceneResource):
    """编辑场景"""

    name = gettext_lazy("编辑场景")
    RequestSerializer = UpdateSceneSerializer
    ResponseSerializer = SceneDetailSerializer

    @transaction.atomic
    def perform_request(self, validated_request_data):
        scene_id = validated_request_data.pop("scene_id", None)
        try:
            scene = Scene.objects.get(scene_id=scene_id)
        except Scene.DoesNotExist:
            raise SceneNotExist()

        # 更新基础字段
        for field in ["name", "description"]:
            if field in validated_request_data:
                setattr(scene, field, validated_request_data[field])
        scene.save()

        # 更新系统关联
        if "systems" in validated_request_data:
            SceneSystem.objects.filter(scene=scene).delete()
            for system_data in validated_request_data["systems"]:
                SceneSystem.objects.create(
                    scene=scene,
                    system_id=system_data.get("system_id", ""),
                    is_all_systems=system_data.get("is_all_systems", False),
                    filter_rules=system_data.get("filter_rules", []),
                )

        # 更新数据表关联
        if "tables" in validated_request_data:
            SceneDataTable.objects.filter(scene=scene).delete()
            for table_data in validated_request_data["tables"]:
                SceneDataTable.objects.create(
                    scene=scene,
                    table_id=table_data.get("table_id", ""),
                    filter_rules=table_data.get("filter_rules", []),
                )

        # 同步 IAM 用户组成员
        self._sync_iam_group_members(scene, validated_request_data)

        return scene


class DeleteScene(SceneResource):
    """删除场景"""

    name = gettext_lazy("删除场景")

    @staticmethod
    def _get_related_resource_details(scene_id: int) -> list[RelatedResourceDetail]:
        from services.web.scene.constants import ResourceVisibilityType
        from services.web.scene.models import ResourceBindingScene

        resource_type_labels = {value: str(label) for value, label in ResourceVisibilityType.choices}
        related_resources: list[RelatedResourceDetail] = []
        binding_scenes = ResourceBindingScene.objects.filter(scene_id=scene_id).select_related("binding")
        for binding_scene in binding_scenes:
            binding = binding_scene.binding
            resource_type = binding.resource_type
            related_resources.append(
                {
                    "resource_type": resource_type,
                    "resource_type_name": resource_type_labels.get(resource_type, resource_type),
                    "resource_id": binding.resource_id,
                }
            )
        return related_resources

    @transaction.atomic
    def perform_request(self, validated_request_data):
        scene_id = validated_request_data["scene_id"]
        try:
            scene = Scene.objects.get(scene_id=scene_id)
        except Scene.DoesNotExist:
            raise SceneNotExist()

        # 检查是否有关联资源
        from services.web.scene.constants import ResourceVisibilityType
        from services.web.scene.models import ResourceBinding
        from services.web.strategy_v2.models import Strategy

        valid_strategy_ids = Strategy.objects.filter(is_deleted=False).values_list("strategy_id", flat=True)
        ResourceBinding.objects.filter(
            resource_type=ResourceVisibilityType.STRATEGY,
            binding_scenes__scene_id=scene.scene_id,
        ).exclude(resource_id__in=[str(strategy_id) for strategy_id in valid_strategy_ids]).delete()

        # 通过 ResourceBindingScene 检查是否有绑定到该场景的资源
        related_resources = self._get_related_resource_details(scene.scene_id)
        if related_resources:
            raise SceneHasRelatedResources(related_resources=related_resources)

        # 删除关联数据
        SceneSystem.objects.filter(scene=scene).delete()
        SceneDataTable.objects.filter(scene=scene).delete()
        scene.delete()
        return {"message": "success"}


class DisableScene(SceneResource):
    """停用场景"""

    name = gettext_lazy("停用场景")
    ResponseSerializer = SceneListSerializer

    def perform_request(self, validated_request_data):
        scene_id = validated_request_data["scene_id"]
        try:
            scene = Scene.objects.get(scene_id=scene_id)
        except Scene.DoesNotExist:
            raise SceneNotExist()
        scene.status = SceneStatus.DISABLED
        scene.save()
        return scene


class EnableScene(SceneResource):
    """启用场景"""

    name = gettext_lazy("启用场景")
    ResponseSerializer = SceneListSerializer

    def perform_request(self, validated_request_data):
        scene_id = validated_request_data["scene_id"]
        try:
            scene = Scene.objects.get(scene_id=scene_id)
        except Scene.DoesNotExist:
            raise SceneNotExist()
        scene.status = SceneStatus.ENABLED
        scene.save()
        return scene


class GetSceneInfo(SceneResource):
    """场景信息（场景管理员可查看）"""

    name = gettext_lazy("获取场景信息")
    ResponseSerializer = SceneDetailSerializer

    def perform_request(self, validated_request_data):
        scene_id = validated_request_data["scene_id"]
        try:
            scene = Scene.objects.get(scene_id=scene_id)
        except Scene.DoesNotExist:
            raise SceneNotExist()
        return scene


class UpdateSceneInfo(SceneResource):
    """编辑场景基础信息（场景管理员）"""

    name = gettext_lazy("编辑场景基础信息")
    RequestSerializer = SceneInfoUpdateSerializer
    ResponseSerializer = SceneDetailSerializer

    def perform_request(self, validated_request_data):
        scene_id = validated_request_data.pop("scene_id", None)
        try:
            scene = Scene.objects.get(scene_id=scene_id)
        except Scene.DoesNotExist:
            raise SceneNotExist()

        for field in ["name", "description"]:
            if field in validated_request_data:
                setattr(scene, field, validated_request_data[field])
        scene.save()

        # 同步 IAM 用户组成员
        self._sync_iam_group_members(scene, validated_request_data)

        return scene


class GetScenePermissionSystems(SceneResource):
    """获取场景下有权限的系统列表"""

    name = gettext_lazy("获取场景下有权限的系统列表")
    audit_action = ActionEnum.VIEW_SCENE
    many_response_data = True

    class RequestSerializer(serializers.Serializer):
        scene_id = serializers.IntegerField(label=gettext_lazy("场景ID"), required=True)

    class ResponseSerializer(serializers.Serializer):
        system_id = serializers.CharField(label=gettext_lazy("系统ID"))
        system_name = serializers.CharField(label=gettext_lazy("系统名称"))

    def perform_request(self, validated_request_data):
        scene_id = validated_request_data["scene_id"]

        # 通过 SystemListAllResource 的 scope 能力获取当前用户在该场景下有权限的系统列表
        systems = resource.meta.system_list_all(
            namespace=settings.DEFAULT_NAMESPACE,
            scope_type="scene",
            scope_id=str(scene_id),
        )

        return [
            {
                "system_id": system["system_id"],
                "system_name": system["name"],
            }
            for system in systems
        ]


def get_scene_members_data(scene_id):
    """
    获取场景成员数据
    """
    try:
        scene = Scene.objects.get(scene_id=scene_id)
    except Scene.DoesNotExist:
        return []

    members = []

    # 获取管理用户组成员
    if scene.iam_manager_group_id:
        try:
            manager_members = IAMGroupManager.get_all_group_members(group_id=scene.iam_manager_group_id)
            for member in manager_members:
                members.append(
                    {
                        "type": member.get("type", ""),
                        "id": member.get("id", ""),
                        "name": member.get("name", ""),
                        "role": "manager",
                    }
                )
        except Exception:
            pass

    # 获取使用用户组成员
    if scene.iam_viewer_group_id:
        try:
            viewer_members = IAMGroupManager.get_all_group_members(group_id=scene.iam_viewer_group_id)
            for member in viewer_members:
                members.append(
                    {
                        "type": member.get("type", ""),
                        "id": member.get("id", ""),
                        "name": member.get("name", ""),
                        "role": "user",
                    }
                )
        except Exception:
            pass

    return members


class GetSceneMembers(SceneResource):
    """获取场景下用户组成员列表"""

    name = gettext_lazy("获取场景下用户组成员列表")
    many_response_data = True

    class RequestSerializer(serializers.Serializer):
        scene_id = serializers.IntegerField(label=gettext_lazy("场景ID"), required=True)

    class ResponseSerializer(serializers.Serializer):
        type = serializers.CharField(label=gettext_lazy("成员类型"))
        id = serializers.CharField(label=gettext_lazy("成员ID"))
        name = serializers.CharField(label=gettext_lazy("成员名称"), required=False, default="")
        role = serializers.CharField(label=gettext_lazy("角色"), help_text="manager 或 user")

    def perform_request(self, validated_request_data):
        scene_id = validated_request_data["scene_id"]
        return get_scene_members_data(scene_id)
