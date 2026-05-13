# -*- coding: utf-8 -*-
import abc

from bk_resource import resource
from django.conf import settings
from django.db import transaction
from django.db.models import (
    CharField,
    Count,
    Exists,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
)
from django.db.models.functions import Cast, Coalesce
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
from services.web.risk.models import Risk
from services.web.scene.binding_validation import assert_binding_relation_integrity
from services.web.scene.constants import ResourceVisibilityType, SceneStatus
from services.web.scene.exceptions import SceneNotExist, SceneStrategyNotDisabled
from services.web.scene.models import (
    ResourceBindingScene,
    Scene,
    SceneDataTable,
    SceneSystem,
)
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
from services.web.strategy_v2.constants import StrategyStatusChoices
from services.web.strategy_v2.models import Strategy


class SceneResource(AuditMixinResource, abc.ABC):
    """场景模块 Resource 基类"""

    tags = ["Scene"]

    @classmethod
    def _refresh_scene_members_from_iam(cls, scene, save=True):
        """从 IAM 刷新场景成员到 DB"""
        manager_members = list(scene.managers or [])
        if scene.iam_manager_group_id:
            manager_members = [
                member.get("id", "")
                for member in IAMGroupManager.get_all_group_members(group_id=scene.iam_manager_group_id)
                if member.get("id", "")
            ]

        user_members = list(scene.users or [])
        if scene.iam_viewer_group_id:
            user_members = [
                member.get("id", "")
                for member in IAMGroupManager.get_all_group_members(group_id=scene.iam_viewer_group_id)
                if member.get("id", "")
            ]

        if save and (scene.managers != manager_members or scene.users != user_members):
            scene.managers = manager_members
            scene.users = user_members
            scene.save(update_fields=["managers", "users"])
        else:
            scene.managers = manager_members
            scene.users = user_members

        return {"manager": manager_members, "user": user_members}

    @classmethod
    def _sync_iam_group_members(cls, scene, validated_request_data):
        """当 managers 或 users 变更时，同步到对应的 IAM 用户组；若用户组尚未创建则先创建"""

        update_fields = []

        if "managers" in validated_request_data:
            new_group_id = IAMGroupManager.sync_group_members(
                group_id=scene.iam_manager_group_id,
                members=scene.managers,
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
                members=scene.users,
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
    RELATED_STATS_SORT_FIELDS = {"strategy_count", "risk_count"}

    @staticmethod
    def _should_annotate_related_stats(order_fields):
        return any(order_field.lstrip("-") in ListScene.RELATED_STATS_SORT_FIELDS for order_field in order_fields)

    @staticmethod
    def _annotate_list_queryset(queryset, include_related_stats=True):
        queryset = queryset.annotate(
            system_count=Count("scene_systems", distinct=True),
            table_count=Count("scene_tables", distinct=True),
            is_all_systems=Exists(SceneSystem.objects.filter(scene_id=OuterRef("scene_id"), is_all_systems=True)),
        )
        if not include_related_stats:
            return queryset

        valid_strategy_ids = (
            Strategy.objects.filter(is_deleted=False)
            .annotate(strategy_id_str=Cast("strategy_id", output_field=CharField()))
            .values("strategy_id_str")
        )
        bound_strategy_queryset = ResourceBindingScene.objects.filter(
            scene_id=OuterRef("scene_id"),
            scene__is_deleted=False,
            binding__resource_type=ResourceVisibilityType.STRATEGY,
            binding__resource_id__in=valid_strategy_ids,
        )
        strategy_count_subquery = (
            bound_strategy_queryset.values("scene_id")
            .annotate(count=Count("binding__resource_id", distinct=True))
            .values("count")[:1]
        )
        risk_count_subquery = (
            bound_strategy_queryset.values("scene_id", "binding__resource_id")
            .distinct()
            .annotate(strategy_id_int=Cast("binding__resource_id", output_field=IntegerField()))
            .annotate(
                risk_count=Coalesce(
                    Subquery(
                        Risk.objects.filter(strategy_id=OuterRef("strategy_id_int"), strategy__is_deleted=False)
                        .values("strategy_id")
                        .annotate(count=Count("risk_id"))
                        .values("count")[:1],
                        output_field=IntegerField(),
                    ),
                    Value(0),
                )
            )
            .values("scene_id")
            .annotate(total=Sum("risk_count"))
            .values("total")[:1]
        )
        return queryset.annotate(
            strategy_count=Coalesce(Subquery(strategy_count_subquery, output_field=IntegerField()), Value(0)),
            risk_count=Coalesce(Subquery(risk_count_subquery, output_field=IntegerField()), Value(0)),
        )

    def perform_request(self, validated_request_data):
        queryset = Scene.objects.all()
        if validated_request_data.get("scene_id"):
            queryset = queryset.filter(scene_id__in=validated_request_data["scene_id"])
        if "status" in validated_request_data:
            queryset = queryset.filter(status=validated_request_data["status"])
        if validated_request_data.get("name"):
            queryset = queryset.filter(name__icontains=validated_request_data["name"])
        if validated_request_data.get("description"):
            queryset = queryset.filter(description__icontains=validated_request_data["description"])
        if validated_request_data.get("manager"):
            queryset = queryset.filter(managers__contains=[validated_request_data["manager"]])
        if validated_request_data.get("user"):
            queryset = queryset.filter(users__contains=[validated_request_data["user"]])
        if validated_request_data.get("updated_by"):
            queryset = queryset.filter(updated_by=validated_request_data["updated_by"])
        if validated_request_data.get("keyword"):
            keyword = validated_request_data["keyword"]
            queryset = queryset.filter(Q(name__icontains=keyword) | Q(description__icontains=keyword))
        order_fields = validated_request_data["order_fields"]
        queryset = self._annotate_list_queryset(
            queryset, include_related_stats=self._should_annotate_related_stats(order_fields)
        )
        return queryset.order_by(*order_fields)


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
            managers=validated_request_data["managers"],
            users=validated_request_data.get("users", []),
        )

        # 创建系统关联
        self._save_systems(scene, validated_request_data.get("systems", []))
        # 创建数据表关联
        self._save_tables(scene, validated_request_data.get("tables", []))
        # 自动创建"场景管理员通知组"
        self._create_scene_manager_notice_group(scene)
        # 创建 IAM 用户组、授权并添加成员（分别创建管理用户组和使用用户组）
        scene.iam_manager_group_id = IAMGroupManager.create_single_group_with_members(
            group_name=f"{scene.name}-管理用户组",
            group_description=f"{scene.name} 场景管理用户组，拥有查看和管理场景权限",
            group_actions=SCENE_MANAGER_GROUP_ACTIONS,
            members=scene.managers,
            scene_id=str(scene.scene_id),
            scene_name=scene.name,
        )
        scene.iam_viewer_group_id = IAMGroupManager.create_single_group_with_members(
            group_name=f"{scene.name}-使用用户组",
            group_description=f"{scene.name} 场景使用用户组，拥有查看场景权限",
            group_actions=SCENE_VIEWER_GROUP_ACTIONS,
            members=scene.users,
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
    def _create_scene_manager_notice_group(scene):
        """创建场景时自动创建场景管理员通知组"""
        from apps.notice.constants import get_default_notice_config
        from apps.notice.models import NoticeGroup
        from services.web.scene.constants import BindingType, ResourceVisibilityType
        from services.web.scene.models import ResourceBinding, ResourceBindingScene

        notice_group = NoticeGroup.objects.create(
            group_name=f"{scene.name}-场景管理员通知组",
            group_member=scene.managers,
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
        for field in ["name", "description", "managers", "users"]:
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

    @transaction.atomic
    def perform_request(self, validated_request_data):
        scene_id = validated_request_data["scene_id"]
        try:
            scene = Scene.objects.get(scene_id=scene_id)
        except Scene.DoesNotExist:
            raise SceneNotExist()

        bound_strategy_resource_ids = (
            ResourceBindingScene.objects.filter(
                scene_id=scene.scene_id,
                scene__is_deleted=False,
                binding__resource_type=ResourceVisibilityType.STRATEGY,
            )
            .values_list("binding__resource_id", flat=True)
            .distinct()
        )
        bound_strategy_ids = set()
        for resource_id in bound_strategy_resource_ids:
            try:
                bound_strategy_ids.add(int(resource_id))
            except (TypeError, ValueError):
                continue

        active_strategy_ids = list(
            Strategy.objects.filter(strategy_id__in=bound_strategy_ids, is_deleted=False)
            .exclude(status=StrategyStatusChoices.DISABLED)
            .order_by("strategy_id")
            .values_list("strategy_id", flat=True)
        )
        if active_strategy_ids:
            raise SceneStrategyNotDisabled(strategy_ids=active_strategy_ids)

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

        for field in ["name", "description", "managers", "users"]:
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
