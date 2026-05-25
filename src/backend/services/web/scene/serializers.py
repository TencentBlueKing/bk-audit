# -*- coding: utf-8 -*-
from collections import defaultdict

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.db.models import Count
from django.utils import timezone
from rest_framework import serializers

from core.serializers import FlexibleListField, SortListField, SortSerializerMixin
from services.web.risk.models import Risk
from services.web.scene.binding_validation import validate_platform_visibility_payload
from services.web.scene.constants import (
    SCENE_RISK_COUNT_ACTIVE_DISPLAY_STATUSES,
    SCENE_RISK_COUNT_DEFAULT_MONTHS,
    ResourceVisibilityType,
    SceneStatus,
    VisibilityScope,
)
from services.web.scene.models import (
    ResourceBinding,
    ResourceBindingScene,
    ResourceBindingSystem,
    Scene,
    SceneDataTable,
    SceneSystem,
)
from services.web.strategy_v2.constants import StrategySource, StrategyStatusChoices
from services.web.strategy_v2.models import Strategy

SCENE_LIST_SORT_FIELDS = ("scene_id", "strategy_count", "risk_count", "updated_at")
SCENE_LIST_SORT_FIELD_DESCRIPTIONS = {
    "scene_id": "场景ID",
    "strategy_count": "策略数",
    "risk_count": "风险数",
    "updated_at": "更新时间",
}
DEFAULT_SCENE_LIST_SORT = ["-scene_id"]


# ==================== 场景管理 ====================


class SceneSystemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SceneSystem
        fields = ["system_id", "is_all_systems", "filter_rules"]


class SceneDataTableSerializer(serializers.ModelSerializer):
    class Meta:
        model = SceneDataTable
        fields = ["table_id", "filter_rules"]


class SceneSystemInputSerializer(serializers.Serializer):
    system_id = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    is_all_systems = serializers.BooleanField(required=False, default=False)
    filter_rules = serializers.ListField(child=serializers.DictField(), required=False, default=list)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        system_id = attrs.get("system_id", "")
        is_all_systems = attrs.get("is_all_systems", False)

        if is_all_systems:
            attrs["system_id"] = ""
            return attrs

        if not system_id:
            raise serializers.ValidationError({"system_id": "该字段是必填项。"})

        return attrs


class SceneTableInputSerializer(serializers.Serializer):
    table_id = serializers.CharField(max_length=128)
    filter_rules = serializers.ListField(child=serializers.DictField(), required=False, default=list)


class SceneRelatedStatsMixin:
    """场景关联策略与风险统计"""

    risk_count_default_months = None
    risk_count_display_statuses = None
    risk_count_start_time_context_key = "risk_count_start_time"
    risk_count_end_time_context_key = "risk_count_end_time"
    strategy_count_statuses = None

    def _get_risk_count_time_range(self):
        start_time = self.context.get(self.risk_count_start_time_context_key)
        end_time = self.context.get(self.risk_count_end_time_context_key)
        if start_time or end_time:
            return start_time, end_time
        if not self.risk_count_default_months:
            return None, None
        # 场景详情 risk_count 默认对齐前端 ListRisk 默认时间范围：按首次发现时间统计近 6 个月风险。
        end_time = timezone.now()
        start_time = end_time - relativedelta(months=self.risk_count_default_months)
        return start_time, end_time

    def _get_scene_related_ids_map(self):
        if hasattr(self, "_scene_related_ids_map"):
            return self._scene_related_ids_map

        instance = self.instance
        if instance is None:
            self._scene_related_ids_map = {}
            return self._scene_related_ids_map

        if hasattr(instance, "__iter__") and not isinstance(instance, (dict, str, bytes)):
            scenes = list(instance)
        else:
            scenes = [instance]

        scene_ids = [scene.scene_id for scene in scenes if getattr(scene, "scene_id", None) is not None]
        if not scene_ids:
            self._scene_related_ids_map = {}
            return self._scene_related_ids_map

        raw_scene_strategy_ids_map = defaultdict(set)
        raw_strategy_ids = set()
        bindings = ResourceBindingScene.objects.filter(
            scene_id__in=scene_ids,
            scene__is_deleted=False,
            binding__resource_type=ResourceVisibilityType.STRATEGY,
        ).values_list("scene_id", "binding__resource_id")
        for scene_id, strategy_id_str in bindings:
            try:
                strategy_id = int(strategy_id_str)
            except (TypeError, ValueError):
                continue
            raw_scene_strategy_ids_map[scene_id].add(strategy_id)
            raw_strategy_ids.add(strategy_id)

        valid_strategy_ids = set()
        if raw_strategy_ids:
            valid_strategy_ids = set(
                Strategy.objects.filter(
                    strategy_id__in=raw_strategy_ids,
                    is_deleted=False,
                    namespace=settings.DEFAULT_NAMESPACE,
                )
                .exclude(source=StrategySource.SYSTEM)
                .values_list("strategy_id", flat=True)
            )

        strategy_count_ids = valid_strategy_ids
        if valid_strategy_ids and self.strategy_count_statuses:
            strategy_count_ids = set(
                Strategy.objects.filter(
                    strategy_id__in=valid_strategy_ids,
                    status__in=self.strategy_count_statuses,
                ).values_list("strategy_id", flat=True)
            )

        strategy_risk_count_map = {}
        if valid_strategy_ids:
            risk_queryset = Risk.objects.filter(strategy_id__in=valid_strategy_ids)
            if self.risk_count_display_statuses:
                risk_queryset = risk_queryset.filter(display_status__in=self.risk_count_display_statuses)
            risk_count_start_time, risk_count_end_time = self._get_risk_count_time_range()
            if risk_count_start_time:
                risk_queryset = risk_queryset.filter(event_time__gte=risk_count_start_time)
            if risk_count_end_time:
                risk_queryset = risk_queryset.filter(event_time__lt=risk_count_end_time)
            strategy_risk_count_map = {
                item["strategy_id"]: item["count"]
                for item in risk_queryset.values("strategy_id").annotate(count=Count("risk_id"))
            }

        scene_risk_count_map = {}
        for scene_id in scene_ids:
            scene_strategy_ids = sorted(raw_scene_strategy_ids_map.get(scene_id, set()) & valid_strategy_ids)
            scene_risk_count_map[scene_id] = sum(
                strategy_risk_count_map.get(strategy_id, 0) for strategy_id in scene_strategy_ids
            )

        self._scene_related_ids_map = {}
        for scene_id in scene_ids:
            scene_strategy_ids = sorted(raw_scene_strategy_ids_map.get(scene_id, set()) & valid_strategy_ids)
            display_strategy_ids = scene_strategy_ids
            if self.strategy_count_statuses:
                display_strategy_ids = sorted(set(scene_strategy_ids) & strategy_count_ids)
            self._scene_related_ids_map[scene_id] = {
                "strategy_ids": display_strategy_ids,
                "strategy_count": len(display_strategy_ids),
                "risk_count": scene_risk_count_map.get(scene_id, 0),
            }
        return self._scene_related_ids_map

    def get_strategy_ids(self, obj):
        return self._get_scene_related_ids_map().get(obj.scene_id, {}).get("strategy_ids", [])

    def get_risk_count(self, obj):
        if hasattr(obj, "risk_count"):
            return obj.risk_count or 0
        return self._get_scene_related_ids_map().get(obj.scene_id, {}).get("risk_count", 0)

    def get_strategy_count(self, obj):
        if hasattr(obj, "strategy_count"):
            return obj.strategy_count or 0
        return self._get_scene_related_ids_map().get(obj.scene_id, {}).get("strategy_count", 0)


class SceneListSerializer(SceneRelatedStatsMixin, serializers.ModelSerializer):
    """场景列表序列化器"""

    system_count = serializers.IntegerField(read_only=True)
    table_count = serializers.IntegerField(read_only=True)
    strategy_ids = serializers.SerializerMethodField()
    strategy_count = serializers.SerializerMethodField()
    risk_count = serializers.SerializerMethodField()
    is_all_systems = serializers.SerializerMethodField()

    def get_is_all_systems(self, obj):
        if hasattr(obj, "is_all_systems"):
            return bool(obj.is_all_systems)
        return SceneSystem.objects.filter(scene_id=obj.scene_id, is_all_systems=True).exists()

    class Meta:
        model = Scene
        fields = [
            "scene_id",
            "name",
            "description",
            "status",
            "managers",
            "users",
            "iam_manager_group_id",
            "iam_viewer_group_id",
            "created_by",
            "updated_by",
            "updated_at",
            "system_count",
            "table_count",
            "strategy_ids",
            "strategy_count",
            "risk_count",
            "is_all_systems",
        ]


class SceneSimpleListSerializer(serializers.ModelSerializer):
    """场景精简列表序列化器"""

    class Meta:
        model = Scene
        fields = ["scene_id", "name", "description", "status", "managers", "users"]


class SceneDetailSerializer(SceneRelatedStatsMixin, serializers.ModelSerializer):
    """场景详情序列化器"""

    risk_count_default_months = SCENE_RISK_COUNT_DEFAULT_MONTHS
    risk_count_display_statuses = SCENE_RISK_COUNT_ACTIVE_DISPLAY_STATUSES
    strategy_count_statuses = (StrategyStatusChoices.RUNNING,)

    systems = SceneSystemSerializer(source="scene_systems", many=True, read_only=True)
    tables = SceneDataTableSerializer(source="scene_tables", many=True, read_only=True)
    strategy_ids = serializers.SerializerMethodField()
    strategy_count = serializers.SerializerMethodField()
    risk_count = serializers.SerializerMethodField()

    class Meta:
        model = Scene
        fields = [
            "scene_id",
            "name",
            "description",
            "status",
            "managers",
            "users",
            "iam_manager_group_id",
            "iam_viewer_group_id",
            "systems",
            "tables",
            "strategy_ids",
            "strategy_count",
            "risk_count",
            "created_by",
            "created_at",
            "updated_by",
            "updated_at",
        ]


class SceneDetailRequestSerializer(serializers.Serializer):
    """场景详情请求参数"""

    scene_id = serializers.IntegerField()
    start_time = serializers.DateTimeField(required=False)
    end_time = serializers.DateTimeField(required=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        start_time = attrs.get("start_time")
        end_time = attrs.get("end_time")
        if start_time and end_time and start_time >= end_time:
            raise serializers.ValidationError({"end_time": "结束时间必须晚于开始时间"})
        return attrs


class CreateSceneSerializer(serializers.Serializer):
    """创建场景请求序列化器"""

    name = serializers.CharField(max_length=128)
    description = serializers.CharField(required=False, default="", allow_blank=True)
    managers = serializers.ListField(child=serializers.CharField(), min_length=1)
    users = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    systems = SceneSystemInputSerializer(many=True, required=False, default=list)
    tables = SceneTableInputSerializer(many=True, required=False, default=list)


class UpdateSceneSerializer(serializers.Serializer):
    """编辑场景请求序列化器"""

    scene_id = serializers.IntegerField()
    name = serializers.CharField(max_length=128, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    managers = serializers.ListField(child=serializers.CharField(), required=False)
    users = serializers.ListField(child=serializers.CharField(), required=False)
    systems = SceneSystemInputSerializer(many=True, required=False)
    tables = SceneTableInputSerializer(many=True, required=False)


class SceneInfoUpdateSerializer(serializers.Serializer):
    """场景管理员编辑场景基础信息"""

    scene_id = serializers.IntegerField()
    name = serializers.CharField(max_length=128, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    managers = serializers.ListField(child=serializers.CharField(), required=False)
    users = serializers.ListField(child=serializers.CharField(), required=False)


class SceneFilterSerializer(SortSerializerMixin, serializers.Serializer):
    """场景列表过滤参数"""

    scene_id = FlexibleListField(child=serializers.IntegerField(), required=False)
    status = FlexibleListField(child=serializers.ChoiceField(choices=SceneStatus.choices), required=False)
    keyword = serializers.CharField(required=False, allow_blank=True)
    name = FlexibleListField(child=serializers.CharField(allow_blank=False), required=False)
    description = FlexibleListField(child=serializers.CharField(allow_blank=True), required=False)
    manager = FlexibleListField(child=serializers.CharField(allow_blank=True), required=False)
    user = FlexibleListField(child=serializers.CharField(allow_blank=True), required=False)
    updated_by = FlexibleListField(child=serializers.CharField(allow_blank=True), required=False)
    sort = SortListField(
        allowed_fields=SCENE_LIST_SORT_FIELDS,
        default_sort=DEFAULT_SCENE_LIST_SORT,
        field_descriptions=SCENE_LIST_SORT_FIELD_DESCRIPTIONS,
    )


class SceneStatusFilterSerializer(serializers.Serializer):
    """场景精简列表过滤参数"""

    status = serializers.ChoiceField(choices=SceneStatus.choices, required=False)


class MyRolePermissionSerializer(serializers.Serializer):
    """当前用户角色相关权限。

    返回可用角色布尔值，由前端按既定规则映射角色：
    - `manage_platform` -> SaaS 管理员
    - `manage_scene` / `view_scene` -> 启用场景管理员 / 场景查看者
    - `edit_system` / `view_system` -> 已接入系统管理员 / 系统查看者
    - `show_log_search` -> 是否展示日志检索页面
    """

    manage_platform = serializers.BooleanField(help_text="是否具备平台管理权限，对应 IAM action: manage_platform。")
    manage_scene = serializers.BooleanField(help_text="是否具备至少一个启用场景的管理权限，对应 IAM action: manage_scene。")
    view_scene = serializers.BooleanField(help_text="是否具备至少一个启用场景的查看权限，对应 IAM action: view_scene。")
    edit_system = serializers.BooleanField(help_text="是否具备至少一个已接入系统的编辑权限；判定口径为本地管理员关系或 IAM action: edit_system。")
    view_system = serializers.BooleanField(
        help_text="是否具备至少一个已接入系统的查看权限；判定口径为本地管理员关系或 IAM action: view_system/edit_system。"
    )
    show_log_search = serializers.BooleanField(help_text="是否展示日志检索页面；平台管理员、有已接入系统权限、或有启用场景且场景展开后存在已接入系统时为 true。")


# ==================== 场景选择器 ====================


class SceneSelectorItemSerializer(serializers.Serializer):
    scene_id = serializers.IntegerField()
    name = serializers.CharField()
    role = serializers.CharField()


# ==================== 资源绑定关系 ====================


class ResourceBindingSceneSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourceBindingScene
        fields = ["scene_id"]


class ResourceBindingSystemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourceBindingSystem
        fields = ["system_id"]


class ResourceBindingSerializer(serializers.ModelSerializer):
    scenes = ResourceBindingSceneSerializer(source="binding_scenes", many=True, read_only=True)
    systems = ResourceBindingSystemSerializer(source="binding_systems", many=True, read_only=True)

    class Meta:
        model = ResourceBinding
        fields = ["resource_type", "resource_id", "binding_type", "visibility_type", "scenes", "systems"]


class ResourceBindingInputSerializer(serializers.Serializer):
    """绑定关系配置输入"""

    visibility_type = serializers.ChoiceField(choices=VisibilityScope.choices, required=False, default="all_visible")
    scene_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    system_ids = serializers.ListField(child=serializers.CharField(), required=False, default=list)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        try:
            validate_platform_visibility_payload(
                visibility_type=attrs.get("visibility_type", VisibilityScope.ALL_VISIBLE),
                scene_ids=attrs.get("scene_ids", []),
                system_ids=attrs.get("system_ids", []),
            )
        except ValueError:
            raise serializers.ValidationError({"visibility": "可见性配置不合法"})
        return attrs
