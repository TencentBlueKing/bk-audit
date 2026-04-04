# -*- coding: utf-8 -*-
import abc

from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext_lazy

from apps.audit.resources import AuditMixinResource
from services.web.scene.constants import SceneStatus
from services.web.scene.exceptions import SceneHasRelatedResources, SceneNotExist
from services.web.scene.models import Scene, SceneDataTable, SceneSystem
from services.web.scene.serializers import (
    CreateSceneSerializer,
    SceneDetailSerializer,
    SceneFilterSerializer,
    SceneInfoUpdateSerializer,
    SceneListSerializer,
    UpdateSceneSerializer,
)


class SceneResource(AuditMixinResource, abc.ABC):
    """场景模块 Resource 基类"""

    tags = ["Scene"]


# ==================== 场景管理 ====================


class ListScene(SceneResource):
    """场景列表"""

    name = gettext_lazy("场景列表")
    RequestSerializer = SceneFilterSerializer
    ResponseSerializer = SceneListSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        queryset = Scene.objects.all()
        if "status" in validated_request_data:
            queryset = queryset.filter(status=validated_request_data["status"])
        if validated_request_data.get("keyword"):
            keyword = validated_request_data["keyword"]
            queryset = queryset.filter(Q(name__icontains=keyword) | Q(description__icontains=keyword))
        return queryset


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
        from apps.notice.models import NoticeGroup
        from services.web.scene.constants import BindingType, ResourceVisibilityType
        from services.web.scene.models import ResourceBinding, ResourceBindingScene

        notice_group = NoticeGroup.objects.create(
            group_name=f"{scene.name}-场景管理员通知组",
            group_member=scene.managers,
            notice_config=[],
            description=f"场景「{scene.name}」的管理员通知组（系统自动创建）",
        )
        # 创建 ResourceBinding 关联
        binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.NOTICE_GROUP,
            resource_id=str(notice_group.group_id),
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=binding, scene_id=scene.scene_id)


class RetrieveScene(SceneResource):
    """场景详情"""

    name = gettext_lazy("场景详情")
    ResponseSerializer = SceneDetailSerializer

    def perform_request(self, validated_request_data):
        scene_id = validated_request_data["scene_id"]
        try:
            return Scene.objects.get(scene_id=scene_id)
        except Scene.DoesNotExist:
            raise SceneNotExist()


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

        # 检查是否有关联资源
        from services.web.scene.models import ResourceBindingScene

        # 通过 ResourceBindingScene 检查是否有绑定到该场景的资源
        has_resources = ResourceBindingScene.objects.filter(scene_id=scene.scene_id).exists()
        if has_resources:
            raise SceneHasRelatedResources()

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
            return Scene.objects.get(scene_id=scene_id)
        except Scene.DoesNotExist:
            raise SceneNotExist()


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
        return scene


class ListMyScenes(SceneResource):
    """用户场景列表"""

    name = gettext_lazy("用户场景列表")

    def perform_request(self, validated_request_data):
        from core.models import get_request_username

        username = get_request_username()
        if not username:
            return []

        scenes = Scene.objects.filter(
            Q(managers__contains=username) | Q(users__contains=username),
            status=SceneStatus.ENABLED,
        )

        return [
            {
                "scene_id": scene.scene_id,
                "name": scene.name,
                "role": "manager" if username in scene.managers else "user",
            }
            for scene in scenes
        ]


class GetSceneSelector(SceneResource):
    """场景选择器数据"""

    name = gettext_lazy("场景选择器数据")

    def perform_request(self, validated_request_data):
        from core.models import get_request_username

        username = get_request_username()
        result = {"scenes": [], "systems": []}

        if not username:
            return result

        scenes = Scene.objects.filter(
            Q(managers__contains=username) | Q(users__contains=username),
            status=SceneStatus.ENABLED,
        )
        for scene in scenes:
            role = "manager" if username in scene.managers else "user"
            result["scenes"].append(
                {
                    "scene_id": scene.scene_id,
                    "name": scene.name,
                    "role": role,
                }
            )

        return result


# ==================== 菜单与引导 ====================


class ListMenus(SceneResource):
    """返回用户可见菜单"""

    name = gettext_lazy("菜单列表")

    def perform_request(self, validated_request_data):
        from core.models import get_request_username

        menus = [
            {"id": "risk", "name": "风险"},
            {"id": "search", "name": "检索"},
            {"id": "report", "name": "报表"},
            {"id": "tool", "name": "工具广场"},
            {"id": "scene_config", "name": "场景配置"},
            {"id": "system", "name": "系统接入"},
        ]

        username = get_request_username()
        if username:
            menus.append({"id": "platform", "name": "平台管理"})

        return menus


class GetPermissionGuide(SceneResource):
    """无权限引导页"""

    name = gettext_lazy("无权限引导")

    def perform_request(self, validated_request_data):
        module = validated_request_data.get("module", "")
        return {
            "has_permission": False,
            "guide": {
                "title": f"暂无 {module} 模块的访问权限",
                "description": "请联系场景管理员或 SaaS 管理员获取权限",
                "action_url": "",
            },
        }
