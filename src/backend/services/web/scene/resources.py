# -*- coding: utf-8 -*-
import abc
import uuid
from collections.abc import Collection

from bk_resource import api, resource
from bk_resource.settings import bk_resource_settings
from blueapps.utils.logger import logger
from django.conf import settings
from django.db import transaction
from django.db.models import (
    Case,
    CharField,
    Count,
    Exists,
    IntegerField,
    OuterRef,
    Prefetch,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Cast, Coalesce
from django.utils import timezone
from django.utils.translation import gettext, gettext_lazy
from rest_framework import serializers

from apps.audit.resources import AuditMixinResource
from apps.meta.constants import SystemAuditStatusEnum
from apps.meta.handlers.iam_group import IAMGroupManager
from apps.meta.models import System
from apps.permission.handlers.actions import ActionEnum
from apps.permission.handlers.service import PermissionService
from core.models import get_request_username
from services.web.common.constants import ScopeType
from services.web.common.scope_permission import ScopeContext, ScopePermission
from services.web.risk.models import Risk
from services.web.scene.binding_validation import assert_binding_relation_integrity
from services.web.scene.constants import (
    SCENE_PERMISSION_CALLBACK_URL,
    SCENE_PERMISSION_WORKFLOW_KEY,
    ApplicationStatus,
    ITSMV4TicketStatus,
    ResourceVisibilityType,
    ScenePermissionFormFields,
    SceneRole,
    SceneStatus,
)
from services.web.scene.exceptions import (
    AlreadyHasPermission,
    ApplicationPending,
    ApproveServiceNotConfigured,
    SceneDispatchRuleNotDisabled,
    SceneException,
    SceneNotEnabled,
    SceneNotExist,
    SceneStrategyNotDisabled,
)
from services.web.scene.models import (
    ResourceBindingScene,
    Scene,
    SceneDataTable,
    ScenePermissionApplication,
    SceneSystem,
)
from services.web.scene.permission import (
    _extract_reject_reason_from_logs,
    already_has_role,
    apply_ticket_result,
    parse_itsm_ticket,
)
from services.web.scene.serializers import (
    ApplyScenePermissionRequestSerializer,
    CreateSceneSerializer,
    MyRolePermissionSerializer,
    SceneDetailRequestSerializer,
    SceneDetailSerializer,
    SceneFilterSerializer,
    SceneInfoUpdateSerializer,
    SceneListSerializer,
    ScenePermissionApplicationSerializer,
    ScenePermissionCallbackResponseSerializer,
    SceneSimpleListSerializer,
    SceneStatusFilterSerializer,
    SceneWithPermissionAndApplicationSerializer,
    UpdateSceneSerializer,
)
from services.web.strategy_v2.constants import StrategySource, StrategyStatusChoices
from services.web.strategy_v2.models import DispatchRule, Strategy


class SceneResource(AuditMixinResource, abc.ABC):
    """场景模块 Resource 基类"""

    tags = ["Scene"]

    @classmethod
    def _refresh_scene_members_from_iam(cls, scene, save=True):
        """从 IAM 刷新场景成员到 DB"""
        return IAMGroupManager.refresh_scene_members(scene, save=save)

    @classmethod
    def _sync_iam_group_members(cls, scene, validated_request_data):
        """当 managers 或 users 变更时，同步到 IAM 成员授权。"""
        IAMGroupManager.sync_scene_members(scene, validated_request_data, operator=get_request_username())


class SceneDetailResponseContextMixin:
    """场景详情响应序列化上下文"""

    def _set_scene_detail_serializer_context(self, validated_request_data):
        self.scene_detail_serializer_context = {
            "risk_count_start_time": validated_request_data.get("start_time"),
            "risk_count_end_time": validated_request_data.get("end_time"),
        }

    def validate_response_data(self, response_data):
        response_serializer = self.ResponseSerializer(
            response_data,
            context=getattr(self, "scene_detail_serializer_context", {}),
        )
        self._response_serializer = response_serializer
        return response_serializer.data


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
        is_all_systems_queryset = SceneSystem.objects.filter(scene_id=OuterRef("scene_id"), is_all_systems=True)
        accessed_system_count_queryset = (
            System.objects.filter(audit_status=SystemAuditStatusEnum.ACCESSED)
            .exclude(system_id="")
            .order_by()
            .values("audit_status")
            .annotate(count=Count("system_id", distinct=True))
            .values("count")[:1]
        )
        queryset = queryset.annotate(
            table_count=Count("scene_tables", distinct=True),
            is_all_systems=Exists(is_all_systems_queryset),
        ).annotate(
            system_count=Case(
                When(
                    is_all_systems=True,
                    then=Coalesce(Subquery(accessed_system_count_queryset, output_field=IntegerField()), Value(0)),
                ),
                default=Count("scene_systems", distinct=True),
                output_field=IntegerField(),
            ),
        )
        if not include_related_stats:
            return queryset

        valid_strategy_ids = (
            Strategy.objects.filter(is_deleted=False, namespace=settings.DEFAULT_NAMESPACE)
            .exclude(source=StrategySource.SYSTEM)
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
                        Risk.objects.filter(
                            strategy_id=OuterRef("strategy_id_int"),
                            strategy__is_deleted=False,
                        )
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
        if validated_request_data.get("status"):
            queryset = queryset.filter(status__in=validated_request_data["status"])

        def apply_multi_value_filter(field_name, values, lookup='icontains'):
            q_filter = Q()
            for value in values:
                if value:
                    q_filter |= Q(**{f"{field_name}__{lookup}": value})
            return queryset.filter(q_filter)

        if validated_request_data.get("name"):
            queryset = apply_multi_value_filter("name", validated_request_data.get("name"))
        if validated_request_data.get("description"):
            queryset = apply_multi_value_filter("description", validated_request_data.get("description"))
        if validated_request_data.get("updated_by"):
            queryset = apply_multi_value_filter("updated_by", validated_request_data.get("updated_by"))
        if validated_request_data.get("manager"):
            manager_filter = Q()
            for manager in validated_request_data["manager"]:
                manager_filter |= Q(managers__contains=[manager])
            queryset = queryset.filter(manager_filter)
        if validated_request_data.get("user"):
            user_filter = Q()
            for user in validated_request_data["user"]:
                user_filter |= Q(users__contains=[user])
            queryset = queryset.filter(user_filter)
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

    @staticmethod
    def _has_accessed_system(system_ids: Collection[str]) -> bool:
        if not system_ids:
            return False
        return System.objects.filter(
            system_id__in=system_ids,
            audit_status=SystemAuditStatusEnum.ACCESSED,
        ).exists()

    def perform_request(self, validated_request_data: dict) -> dict[str, bool]:
        username: str = get_request_username()
        permission = PermissionService(username=username)
        scope_permission = ScopePermission(username)

        cross_scene_scope = ScopeContext(ScopeType.CROSS_SCENE)
        cross_system_scope = ScopeContext(ScopeType.CROSS_SYSTEM)

        manage_scene_ids = scope_permission.get_scene_ids(cross_scene_scope, ActionEnum.MANAGE_SCENE)
        view_scene_ids = scope_permission.get_scene_ids(cross_scene_scope, ActionEnum.VIEW_SCENE)
        edit_system_ids = scope_permission.get_system_ids(cross_system_scope, ActionEnum.EDIT_SYSTEM)
        view_system_ids = scope_permission.get_system_ids(cross_system_scope, ActionEnum.VIEW_SYSTEM)
        scene_scope_system_ids = scope_permission.get_system_ids_for_scope(cross_scene_scope)

        # 角色布尔值按实际可用实例收口，避免停用场景或待接入系统让前端展示不可用入口。
        # SaaS 管理员仍按平台 action 判定；场景/系统角色必须回收到至少一个可用实例。
        manage_platform = permission.has_action_any_permission(ActionEnum.MANAGE_PLATFORM)
        manage_scene = bool(manage_scene_ids)
        view_scene = bool(view_scene_ids)
        edit_system = self._has_accessed_system(edit_system_ids)
        view_system = edit_system or self._has_accessed_system(view_system_ids)
        # 日志检索入口要求存在真实可检索范围：平台视角、已接入系统，或启用场景展开后的已接入系统。
        show_log_search = (
            manage_platform or self._has_accessed_system(scene_scope_system_ids) or edit_system or view_system
        )

        return {
            "manage_platform": manage_platform,
            "manage_scene": manage_scene,
            "view_scene": view_scene,
            "edit_system": edit_system,
            "view_system": view_system,
            "show_log_search": show_log_search,
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
        # 创建 IAM 成员授权；底层 V3 用户组/V4 Role 授权由 IAMGroupManager 屏蔽
        IAMGroupManager.create_scene_member_permissions(scene, operator=get_request_username())
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
        next_priority_index = SceneReportGroupItem.get_next_priority_index(platform_group.id)
        to_create = []
        for panel in panels:
            if panel.id in existing_panel_ids:
                continue
            to_create.append(
                SceneReportGroupItem(group=platform_group, panel=panel, priority_index=next_priority_index)
            )
            next_priority_index += 1
        if to_create:
            SceneReportGroupItem.objects.bulk_create(to_create, ignore_conflicts=True)


class RetrieveScene(SceneDetailResponseContextMixin, SceneResource):
    """场景详情"""

    name = gettext_lazy("场景详情")
    RequestSerializer = SceneDetailRequestSerializer
    ResponseSerializer = SceneDetailSerializer

    def perform_request(self, validated_request_data):
        self._set_scene_detail_serializer_context(validated_request_data)
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

        with IAMGroupManager.scene_member_sync_context():
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

        # 检查是否有启用策略的活动分派规则引用该场景作为目标场景。
        # 全局策略 direct / after_confirm 的分派结果会把 Risk 绑定到 DispatchRule.target_scene，
        dispatch_strategy_ids = list(
            DispatchRule.objects.filter(
                target_scene=scene,
                is_deleted=False,
                strategy__is_deleted=False,
            )
            .exclude(strategy__status=StrategyStatusChoices.DISABLED)
            .order_by("strategy_id")
            .values_list("strategy_id", flat=True)
            .distinct()
        )
        if dispatch_strategy_ids:
            raise SceneDispatchRuleNotDisabled(strategy_ids=dispatch_strategy_ids)

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


class GetSceneInfo(SceneDetailResponseContextMixin, SceneResource):
    """场景信息（场景管理员可查看）"""

    name = gettext_lazy("获取场景信息")
    RequestSerializer = SceneDetailRequestSerializer
    ResponseSerializer = SceneDetailSerializer

    def perform_request(self, validated_request_data):
        self._set_scene_detail_serializer_context(validated_request_data)
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

        def save_and_sync():
            for field in ["name", "description", "managers", "users"]:
                if field in validated_request_data:
                    setattr(scene, field, validated_request_data[field])
            scene.save()
            self._sync_iam_group_members(scene, validated_request_data)

        with IAMGroupManager.scene_member_sync_context():
            save_and_sync()

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

    try:
        return IAMGroupManager.get_scene_members(scene)
    except Exception:
        return []


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


# ==================== 场景权限自动化审批授权 ====================


class ApplyScenePermission(SceneResource):
    """提交场景权限申请"""

    name = gettext_lazy("提交场景权限申请")
    RequestSerializer = ApplyScenePermissionRequestSerializer
    ResponseSerializer = ScenePermissionApplicationSerializer

    def perform_request(self, validated_request_data):
        applicant = get_request_username()
        scene_id = validated_request_data["scene_id"]
        role = validated_request_data["role"]
        reason = validated_request_data.get("reason", "")

        # 1. 校验场景(是否存在、是否已启用)
        try:
            scene = Scene.objects.get(scene_id=scene_id)
        except Scene.DoesNotExist:
            raise SceneNotExist()
        if scene.status != SceneStatus.ENABLED:
            raise SceneNotEnabled()

        # 2. 校验是否已有该场景的使用/管理权限
        if already_has_role(scene, role, applicant):
            raise AlreadyHasPermission()

        # 3. 校验是否有在途 PENDING 单
        if ScenePermissionApplication.objects.filter(
            scene_id=scene_id,
            applicant=applicant,
            role=role,
            status=ApplicationStatus.PENDING,
        ).exists():
            raise ApplicationPending()

        # 4. 校验审批流程已配置
        if not SCENE_PERMISSION_WORKFLOW_KEY:
            raise ApproveServiceNotConfigured()

        # 5. 取审批人（场景管理员优先，为空时回退到admin）
        approvers = list(scene.managers or [])
        if not approvers:
            approvers = list(settings.SYSTEM_ADMIN)

        # 6. 生成回调 Token
        callback_token = str(uuid.uuid4())

        # 7. 校验回调地址已配置
        if not SCENE_PERMISSION_CALLBACK_URL:
            logger.error("[ApplyScenePermission] BKAPP_BKAUDIT_CALLBACK_URL_PREFIX 未配置，无法创建 ITSM 工单")
            raise ApproveServiceNotConfigured()

        # 8. 建 ITSM V4 单（operator=申请人）
        ticket = self._create_itsm_ticket(
            applicant=applicant,
            scene=scene,
            role=role,
            reason=reason,
            approvers=approvers,
            callback_token=callback_token,
        )

        # 9. 落库
        itsm_ticket_id = ticket.get("id", "")
        if not itsm_ticket_id:
            logger.error(
                "[ApplyScenePermission] ITSM 未返回 ticket id， sn=%s, applicant=%s, scene=%s",
                ticket.get("sn", ""),
                applicant,
                scene.scene_id,
            )
            raise SceneException(message=gettext("ITSM 未返回工单ID，无法创建申请单"))
        try:
            return ScenePermissionApplication.objects.create(
                scene=scene,
                applicant=applicant,
                role=role,
                reason=reason,
                itsm_sn=ticket.get("sn", ""),
                itsm_ticket_id=itsm_ticket_id,
                itsm_ticket_url=ticket.get("frontend_url", ""),
                callback_token=callback_token,
                status=ApplicationStatus.PENDING,
                approvers=approvers,
                created_by=applicant,
                updated_by=applicant,
            )
        except Exception:
            logger.exception(
                "[ApplyScenePermission] DB 写入失败， ITSM 单 sn=%s, applicant=%s, scene=%s",
                ticket.get("sn", ""),
                applicant,
                scene.scene_id,
            )
            raise

    @staticmethod
    def _create_itsm_ticket(applicant, scene, role, reason, approvers, callback_token) -> dict:
        """建 ITSM V4 审批单。字段标识见 ScenePermissionFormFields。"""
        role_label = str(dict(SceneRole.choices).get(role, role))

        # 获取申请人部门（主岗全称）
        applicant_department = ""
        try:
            departments = api.user_manage.list_user_departments(id=applicant)
            if departments:
                applicant_department = departments[0].get("full_name", "")
        except Exception:  # pylint: disable=broad-except
            logger.warning("[_create_itsm_ticket] 获取用户部门失败, applicant=%s", applicant)

        form_data = {
            ScenePermissionFormFields.TITLE: str(gettext("【审计中心】%s 申请 %s %s权限")) % (applicant, scene.name, role_label),
            ScenePermissionFormFields.APPLICANT: applicant,
            ScenePermissionFormFields.APPLICANT_DEPARTMENT: applicant_department,
            ScenePermissionFormFields.APPLY_TIME: timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
            ScenePermissionFormFields.SCENE_NAME: f"{scene.name}({scene.scene_id})",
            ScenePermissionFormFields.ROLE: role_label,
            ScenePermissionFormFields.APPROVER: approvers,
            ScenePermissionFormFields.REASON: reason,
        }
        # 获取回调 URL
        callback_url = SCENE_PERMISSION_CALLBACK_URL
        logger.info(
            "[_create_itsm_ticket] workflow_key=%s, operator=%s, callback_url=%s, form_data=%s",
            SCENE_PERMISSION_WORKFLOW_KEY,
            applicant,
            callback_url,
            form_data,
        )
        try:
            return api.bk_itsm_v4.ticket_create(
                operator=applicant,
                workflow_key=SCENE_PERMISSION_WORKFLOW_KEY,
                form_data=form_data,
                is_submit=True,
                callback_url=callback_url,
                callback_token=callback_token,
            )
        except Exception:
            logger.exception(
                "[_create_itsm_ticket] ITSM V4 ticket_create failed, workflow_key=%s, operator=%s, form_data=%s",
                SCENE_PERMISSION_WORKFLOW_KEY,
                applicant,
                form_data,
            )
            raise


class ListMyScenePermissionApplications(SceneResource):
    """我的场景列表（含申请信息）"""

    name = gettext_lazy("我的场景列表（含申请状态）")
    ResponseSerializer = SceneWithPermissionAndApplicationSerializer
    many_response_data = True

    class RequestSerializer(serializers.Serializer):
        scene_id = serializers.IntegerField(label=gettext_lazy("场景ID"), required=False)

    def perform_request(self, validated_request_data):
        applicant = get_request_username()
        scene_id = validated_request_data.get("scene_id")

        # 1. 构造子查询：每个 scene 对应最新申请单 ID
        latest_application_id = (
            ScenePermissionApplication.objects.filter(
                applicant=applicant,
                scene_id=OuterRef("scene_id"),
            )
            .order_by("-id")
            .values("id")[:1]
        )

        # 2. 实际需要 prefetch 的申请单
        latest_applications = ScenePermissionApplication.objects.filter(
            applicant=applicant,
            id=Subquery(latest_application_id),
        )

        # 3. 查询启用的场景，并 prefetch 最新申请单
        scenes = Scene.objects.filter(is_deleted=False, status=SceneStatus.ENABLED,).prefetch_related(
            Prefetch(
                "permission_applications",
                queryset=latest_applications,
                to_attr="latest_permission_applications",
            )
        )

        if scene_id:
            scenes = scenes.filter(scene_id=scene_id)

        return scenes


class ScenePermissionApplicationCallback(SceneResource):
    """ITSM 工单回调接口
    ITSM 审批完成后主动回调此接口，更新申请单状态并触发授权。
    """

    name = gettext_lazy("ITSM工单回调")
    ResponseSerializer = ScenePermissionCallbackResponseSerializer

    class RequestSerializer(serializers.Serializer):
        callback_token = serializers.CharField(label=gettext_lazy("回调鉴权Token"))
        ticket = serializers.DictField(label=gettext_lazy("工单详情"))

    def perform_request(self, validated_request_data):
        callback_token = validated_request_data.get("callback_token", "")
        ticket_data = validated_request_data.get("ticket", {})

        # 1. 提取工单信息
        ticket_id = ticket_data.get("id", "")

        if not ticket_id:
            logger.warning("[ScenePermissionApplicationCallback] 回调缺少工单ID")
            return {"result": False, "message": "missing ticket id"}

        # 2. 查找申请单
        try:
            application = ScenePermissionApplication.objects.select_related("scene").get(itsm_ticket_id=ticket_id)
        except ScenePermissionApplication.DoesNotExist:
            logger.warning("[ScenePermissionApplicationCallback] 未找到申请单, ticket_id=%s", ticket_id)
            return {"result": False, "message": "application not found"}

        # 3. 验证 callback_token
        if not callback_token or application.callback_token != callback_token:
            logger.warning("[ScenePermissionApplicationCallback] Token验证失败, ticket_id=%s", ticket_id)
            return {"result": False, "message": "invalid token"}

        # 4. 幂等校验：已终态则跳过
        if application.is_terminal:
            return {"result": True, "message": "already processed"}

        # 5. 处理回调
        try:
            # 如果审批被拒绝/终止，需要查日志获取理由
            reject_reason = ""
            parsed = parse_itsm_ticket(ticket_data)
            if parsed["status"] in (ITSMV4TicketStatus.FINISHED, ITSMV4TicketStatus.TERMINATION):
                if not parsed["approve_result"]:
                    logs_data = api.bk_itsm_v4.ticket_logs(ticket_id=ticket_id)
                    reject_reason = _extract_reject_reason_from_logs(logs_data)

            with transaction.atomic():
                application = ScenePermissionApplication.objects.select_for_update().get(id=application.id)
                if application.is_terminal:
                    return {"result": True, "message": "already processed"}

                operator = bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME
                apply_ticket_result(application, parsed, operator=operator, reject_reason=reject_reason)
                application.save()
        except Exception as err:
            logger.exception(
                "[ScenePermissionApplicationCallback] 处理回调失败, ticket_id=%s, error=%s",
                ticket_id,
                err,
            )
            return {"result": False, "message": str(err)}

        return {"result": True, "message": "success"}
