# -*- coding: utf-8 -*-
from collections import defaultdict

from django.db.models import Count
from rest_framework import serializers

from services.web.scene.binding_validation import validate_platform_visibility_payload
from services.web.scene.constants import (
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


class FlexibleListField(serializers.ListField):
    """兼容单值、数组、重复查询参数的列表字段"""

    def get_value(self, dictionary):
        if hasattr(dictionary, "getlist"):
            values = dictionary.getlist(self.field_name)
            if len(values) > 1:
                return values
            if len(values) == 1:
                return values[0]
        return super().get_value(dictionary)

    def to_internal_value(self, data):
        if data in (None, ""):
            data = []
        elif not isinstance(data, (list, tuple, set, frozenset)):
            data = [data]
        else:
            data = list(data)

        normalized = []
        for item in data:
            if item is None:
                continue
            if isinstance(item, str):
                parts = [part.strip() for part in item.split(",")]
                normalized.extend([part for part in parts if part != ""])
            elif item != "":
                normalized.append(item)

        return super().to_internal_value(normalized)


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
    system_id = serializers.CharField(max_length=64)
    is_all_systems = serializers.BooleanField(required=False, default=False)
    filter_rules = serializers.ListField(child=serializers.DictField(), required=False, default=list)


class SceneTableInputSerializer(serializers.Serializer):
    table_id = serializers.CharField(max_length=128)
    filter_rules = serializers.ListField(child=serializers.DictField(), required=False, default=list)


class SceneRelatedStatsMixin:
    """场景关联策略与风险统计"""

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
            from services.web.strategy_v2.models import Strategy

            valid_strategy_ids = set(
                Strategy.objects.filter(strategy_id__in=raw_strategy_ids).values_list("strategy_id", flat=True)
            )

        strategy_risk_count_map = {}
        if valid_strategy_ids:
            from services.web.risk.models import Risk

            strategy_risk_count_map = {
                item["strategy_id"]: item["count"]
                for item in Risk.objects.filter(strategy_id__in=valid_strategy_ids)
                .values("strategy_id")
                .annotate(count=Count("risk_id"))
            }

        self._scene_related_ids_map = {}
        for scene_id in scene_ids:
            scene_strategy_ids = sorted(raw_scene_strategy_ids_map.get(scene_id, set()) & valid_strategy_ids)
            scene_risk_count = sum(strategy_risk_count_map.get(strategy_id, 0) for strategy_id in scene_strategy_ids)
            self._scene_related_ids_map[scene_id] = {
                "strategy_ids": scene_strategy_ids,
                "risk_count": scene_risk_count,
            }
        return self._scene_related_ids_map

    def get_strategy_ids(self, obj):
        return self._get_scene_related_ids_map().get(obj.scene_id, {}).get("strategy_ids", [])

    def get_risk_count(self, obj):
        return self._get_scene_related_ids_map().get(obj.scene_id, {}).get("risk_count", 0)


class SceneListSerializer(SceneRelatedStatsMixin, serializers.ModelSerializer):
    """场景列表序列化器"""

    system_count = serializers.IntegerField(read_only=True)
    table_count = serializers.IntegerField(read_only=True)
    strategy_ids = serializers.SerializerMethodField()
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
            "created_by",
            "updated_by",
            "updated_at",
            "system_count",
            "table_count",
            "strategy_ids",
            "risk_count",
        ]


class SceneSimpleListSerializer(serializers.ModelSerializer):
    """场景精简列表序列化器"""

    class Meta:
        model = Scene
        fields = ["scene_id", "name", "status"]


class SceneDetailSerializer(SceneRelatedStatsMixin, serializers.ModelSerializer):
    """场景详情序列化器"""

    systems = SceneSystemSerializer(source="scene_systems", many=True, read_only=True)
    tables = SceneDataTableSerializer(source="scene_tables", many=True, read_only=True)
    strategy_ids = serializers.SerializerMethodField()
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
            "risk_count",
            "created_by",
            "created_at",
            "updated_by",
            "updated_at",
        ]


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


class SceneFilterSerializer(serializers.Serializer):
    """场景列表过滤参数"""

    status = serializers.ChoiceField(choices=SceneStatus.choices, required=False)
    keyword = serializers.CharField(required=False, allow_blank=True)


class SceneStatusFilterSerializer(serializers.Serializer):
    """场景精简列表过滤参数"""

    status = serializers.ChoiceField(choices=SceneStatus.choices, required=False)


class MyRolePermissionSerializer(serializers.Serializer):
    """当前用户角色相关权限。

    返回 action 级布尔值，由前端按既定规则映射角色：
    - `manage_platform` -> SaaS 管理员
    - `manage_scene` / `view_scene` -> 场景管理员 / 场景查看者
    - `edit_system` / `view_system` -> 系统管理员 / 系统查看者
    """

    manage_platform = serializers.BooleanField(help_text="是否具备平台管理权限，对应 IAM action: manage_platform。")
    manage_scene = serializers.BooleanField(help_text="是否具备任一场景的管理权限，对应 IAM action: manage_scene。")
    view_scene = serializers.BooleanField(help_text="是否具备任一场景的查看权限，对应 IAM action: view_scene。")
    edit_system = serializers.BooleanField(help_text="是否具备任一系统的编辑权限；判定口径为本地系统管理员关系或 IAM action: edit_system。")
    view_system = serializers.BooleanField(
        help_text="是否具备任一系统的查看权限；判定口径为本地系统管理员关系或 IAM action: view_system/edit_system。"
    )


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
