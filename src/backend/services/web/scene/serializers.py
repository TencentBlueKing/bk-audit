# -*- coding: utf-8 -*-
from rest_framework import serializers

from services.web.scene.constants import SceneStatus, VisibilityScope
from services.web.scene.models import (
    ResourceVisibility,
    Scene,
    SceneDataTable,
    SceneSystem,
)

# ==================== 场景管理 ====================


class SceneSystemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SceneSystem
        fields = ["system_id", "is_all_systems", "filter_rules"]


class SceneDataTableSerializer(serializers.ModelSerializer):
    class Meta:
        model = SceneDataTable
        fields = ["table_id", "filter_rules"]


class SceneListSerializer(serializers.ModelSerializer):
    """场景列表序列化器"""

    class Meta:
        model = Scene
        fields = [
            "scene_id",
            "name",
            "description",
            "status",
            "managers",
            "users",
            "created_by",
            "updated_by",
            "updated_at",
        ]


class SceneDetailSerializer(serializers.ModelSerializer):
    """场景详情序列化器"""

    systems = SceneSystemSerializer(source="scene_systems", many=True, read_only=True)
    tables = SceneDataTableSerializer(source="scene_tables", many=True, read_only=True)

    class Meta:
        model = Scene
        fields = [
            "scene_id",
            "name",
            "description",
            "status",
            "managers",
            "users",
            "systems",
            "tables",
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
    systems = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    tables = serializers.ListField(child=serializers.DictField(), required=False, default=list)


class UpdateSceneSerializer(serializers.Serializer):
    """编辑场景请求序列化器"""

    scene_id = serializers.IntegerField()
    name = serializers.CharField(max_length=128, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    managers = serializers.ListField(child=serializers.CharField(), required=False)
    users = serializers.ListField(child=serializers.CharField(), required=False)
    systems = serializers.ListField(child=serializers.DictField(), required=False)
    tables = serializers.ListField(child=serializers.DictField(), required=False)


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


# ==================== 场景选择器 ====================


class SceneSelectorItemSerializer(serializers.Serializer):
    scene_id = serializers.IntegerField()
    name = serializers.CharField()
    role = serializers.CharField()


# ==================== 资源可见范围 ====================


class ResourceVisibilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourceVisibility
        fields = ["resource_type", "resource_id", "visibility_type", "scene_ids", "system_ids"]


class ResourceVisibilityInputSerializer(serializers.Serializer):
    """可见范围配置输入"""

    visibility_type = serializers.ChoiceField(choices=VisibilityScope.choices)
    scene_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    system_ids = serializers.ListField(child=serializers.CharField(), required=False, default=list)
