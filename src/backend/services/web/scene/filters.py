# -*- coding: utf-8 -*-
"""
通用场景过滤器（ScopeFilter）

提供统一的资源-场景过滤能力，消除各模块中重复的 scene 过滤样板代码。

支持两种过滤模式：
1. 简单模式（SceneScopeFilter）：按 scene_id 或 system_id 过滤，适用于策略、联表、处理套餐、通知组、风险等纯场景级资源
2. 组合模式（BindingScopeFilter）：支持 binding_type + scene_id/system_id 组合过滤，适用于工具、报表等同时存在平台级和场景级的资源

过滤规则：
- 传 scene_id：通过 ResourceBindingScene 查找绑定到该场景的资源
- 传 system_id：通过 ResourceBindingSystem 查找绑定到该系统的资源
  （注意：SceneSystem 中的 system_id 代表场景下资源可以绑定的系统，并非默认授予权限）
- 都不传：返回全部资源（兼容存量，不做过滤）

使用示例：

    # 简单模式 — 策略列表按场景过滤
    from services.web.scene.filters import SceneScopeFilter

    class ListStrategy(StrategyV2Base):
        def perform_request(self, validated_request_data):
            scene_id = validated_request_data.pop("scene_id", None)
            system_id = validated_request_data.pop("system_id", None)
            queryset = Strategy.objects.all()
            queryset = SceneScopeFilter.filter_queryset(
                queryset=queryset,
                scene_id=scene_id,
                system_id=system_id,
                resource_type=ResourceVisibilityType.STRATEGY,
                pk_field="strategy_id",
            )
            return queryset

    # 组合模式 — 工具列表按 binding_type + scene_id/system_id 过滤
    from services.web.scene.filters import BindingScopeFilter

    class ListTool(ToolBase):
        def perform_request(self, validated_request_data):
            binding_type = validated_request_data.get("binding_type", "")
            scene_id = validated_request_data.get("scene_id")
            system_id = validated_request_data.get("system_id")
            queryset = Tool.all_latest_tools()
            queryset = BindingScopeFilter.filter_queryset(
                queryset=queryset,
                binding_type=binding_type,
                scene_id=scene_id,
                system_id=system_id,
                resource_type=ResourceVisibilityType.TOOL,
                pk_field="uid",
            )
            return queryset
"""

from django.db.models import QuerySet

from services.web.scene.constants import BindingType, VisibilityScope
from services.web.scene.models import (
    ResourceBinding,
    ResourceBindingScene,
    ResourceBindingSystem,
    SceneSystem,
)


def _get_resource_ids_by_system(system_id: str, resource_type: str) -> list:
    """根据 system_id 通过 ResourceBindingSystem 查找绑定到该系统的资源 ID 列表"""
    return list(
        ResourceBindingSystem.objects.filter(
            system_id=system_id,
            binding__resource_type=resource_type,
        ).values_list("binding__resource_id", flat=True)
    )


class SceneScopeFilter:
    """简单场景过滤器

    适用于纯场景级资源（策略、联表、处理套餐、处理规则、通知组、风险），
    按 scene_id 或 system_id 过滤。

    过滤逻辑：
    - 传 scene_id：通过 ResourceBindingScene 返回该场景下的资源
    - 传 system_id：通过 ResourceBindingSystem 返回绑定到该系统的资源
    - 都不传：返回全部资源（兼容存量，不做过滤）
    - scene_id 优先级高于 system_id（两者同时传时以 scene_id 为准）
    """

    @staticmethod
    def filter_queryset(
        queryset: QuerySet,
        scene_id=None,
        system_id: str = None,
        resource_type: str = "",
        pk_field: str = "pk",
    ) -> QuerySet:
        """
        按场景或系统过滤 queryset

        :param queryset: 原始 queryset
        :param scene_id: 场景 ID，为 None 时不按场景过滤
        :param system_id: 系统 ID，为 None 时不按系统过滤
        :param resource_type: ResourceVisibilityType 枚举值，如 "strategy"、"risk" 等
        :param pk_field: queryset 中用于匹配 resource_id 的主键字段名
        :return: 过滤后的 queryset
        """
        if scene_id is not None:
            # 按单个场景过滤：通过 ResourceBindingScene 查找
            bound_ids = ResourceBindingScene.objects.filter(
                scene_id=scene_id,
                binding__resource_type=resource_type,
            ).values_list("binding__resource_id", flat=True)
            return queryset.filter(**{f"{pk_field}__in": list(bound_ids)})

        if system_id:
            # 按系统过滤：通过 ResourceBindingSystem 查找绑定到该系统的资源
            bound_ids = _get_resource_ids_by_system(system_id, resource_type)
            if not bound_ids:
                return queryset.none()
            return queryset.filter(**{f"{pk_field}__in": bound_ids})

        # 都不传，返回全部资源（兼容存量，不做过滤）
        return queryset

    @staticmethod
    def get_bound_resource_ids(scene_id, resource_type: str):
        """
        获取指定场景下绑定的资源 ID 列表

        :param scene_id: 场景 ID
        :param resource_type: ResourceVisibilityType 枚举值
        :return: 资源 ID 列表
        """
        return list(
            ResourceBindingScene.objects.filter(
                scene_id=scene_id,
                binding__resource_type=resource_type,
            ).values_list("binding__resource_id", flat=True)
        )

    @staticmethod
    def create_resource_binding(
        resource_id: str,
        resource_type: str,
        scene_id=None,
        system_id: str = None,
    ) -> ResourceBinding:
        """
        创建资源的 ResourceBinding 关联（纯场景级资源专用）

        根据传入的 scene_id 或 system_id 创建对应的绑定关系：
        - 传 scene_id：创建 ResourceBinding + ResourceBindingScene
        - 传 system_id：创建 ResourceBinding + ResourceBindingSystem
        - 两者都传：创建 ResourceBinding + ResourceBindingScene + ResourceBindingSystem
        - 两者都不传：抛出 ValueError

        :param resource_id: 资源 ID
        :param resource_type: ResourceVisibilityType 枚举值
        :param scene_id: 场景 ID
        :param system_id: 系统 ID
        :return: 创建的 ResourceBinding 实例
        """
        from services.web.scene.constants import BindingType as _BindingType

        if scene_id is None and not system_id:
            raise ValueError("创建资源绑定时，scene_id 和 system_id 至少传一个")

        binding = ResourceBinding.objects.create(
            resource_type=resource_type,
            resource_id=str(resource_id),
            binding_type=_BindingType.SCENE_BINDING,
        )
        if scene_id is not None:
            ResourceBindingScene.objects.create(binding=binding, scene_id=scene_id)
        if system_id:
            ResourceBindingSystem.objects.create(binding=binding, system_id=system_id)
        return binding


class BindingScopeFilter:
    """组合场景过滤器

    适用于同时存在平台级和场景级的资源（工具、报表），
    支持 binding_type + scene_id/system_id 组合过滤。

    过滤逻辑：
    - binding_type=platform_binding：仅返回平台级资源
    - binding_type=platform_binding + scene_id/system_id：返回对该场景/系统可见的平台级资源
    - binding_type=scene_binding + scene_id：仅返回该场景的场景级资源
    - binding_type=scene_binding + system_id：不支持，场景级资源仅可关联一个场景，无法通过系统过滤
    - 仅传 scene_id（无 binding_type）：返回该场景的场景级资源 + 对该场景可见的平台级资源（并集）
    - 仅传 system_id（无 binding_type）：仅返回对该系统可见的平台级资源（场景级资源无法绑定到系统）
    - 都不传：返回全部资源（兼容存量，不做过滤）
    """

    @staticmethod
    def _get_scene_binding_ids(resource_type: str, scene_ids: list) -> set:
        """获取指定场景列表中的场景级绑定资源 ID"""
        binding_ids = ResourceBindingScene.objects.filter(
            scene_id__in=scene_ids,
        ).values_list("binding_id", flat=True)
        return set(
            ResourceBinding.objects.filter(
                id__in=binding_ids,
                resource_type=resource_type,
                binding_type=BindingType.SCENE_BINDING,
            ).values_list("resource_id", flat=True)
        )

    @staticmethod
    def _get_visible_platform_ids(
        resource_type: str,
        scene_id=None,
        system_id: str = None,
    ) -> set:
        """获取对指定场景/系统可见的平台级资源 ID

        根据 visibility_type 判断可见性：
        - all_visible：所有人可见
        - all_scenes：所有场景可见
        - specific_scenes：仅指定场景可见（通过 ResourceBindingScene 判断）
        - specific_systems：仅指定系统可见（通过 ResourceBindingSystem 判断）
        """
        platform_bindings = ResourceBinding.objects.filter(
            resource_type=resource_type,
            binding_type=BindingType.PLATFORM_BINDING,
        )

        visible_ids = set()

        for binding in platform_bindings:
            if binding.visibility_type in (VisibilityScope.ALL_VISIBLE, VisibilityScope.ALL_SCENES):
                # 全部可见 / 全部场景可见
                visible_ids.add(binding.resource_id)

            elif binding.visibility_type == VisibilityScope.SPECIFIC_SCENES:
                # 指定场景可见：检查是否绑定到目标场景
                if scene_id is not None:
                    if binding.binding_scenes.filter(scene_id=scene_id).exists():
                        visible_ids.add(binding.resource_id)
                elif system_id:
                    # 按系统过滤时，检查该资源绑定的可见场景中是否有关联该系统的场景
                    binding_scene_ids = set(binding.binding_scenes.values_list("scene_id", flat=True))
                    # 查找这些场景中哪些关联了目标系统
                    if binding_scene_ids:
                        matched = SceneSystem.objects.filter(
                            scene_id__in=binding_scene_ids,
                            system_id=system_id,
                        ).exists()
                        if matched:
                            visible_ids.add(binding.resource_id)

            elif binding.visibility_type == VisibilityScope.SPECIFIC_SYSTEMS:
                # 指定系统可见：检查目标系统是否在可见系统列表中
                binding_system_ids = set(binding.binding_systems.values_list("system_id", flat=True))
                if system_id:
                    # 直接判断该系统是否在可见系统列表中
                    if system_id in binding_system_ids:
                        visible_ids.add(binding.resource_id)
                elif scene_id is not None:
                    # 按场景过滤时，检查该场景关联的系统是否在可见系统列表中
                    scene_system_ids = set(
                        SceneSystem.objects.filter(
                            scene_id=scene_id,
                        ).values_list("system_id", flat=True)
                    )
                    if scene_system_ids & binding_system_ids:
                        visible_ids.add(binding.resource_id)

        return visible_ids

    @staticmethod
    def filter_queryset(
        queryset: QuerySet,
        binding_type: str,
        scene_id=None,
        system_id: str = None,
        resource_type: str = "",
        pk_field: str = "pk",
    ) -> QuerySet:
        """
        按 binding_type + scene_id/system_id 组合过滤 queryset

        :param queryset: 原始 queryset
        :param binding_type: 绑定类型，BindingType 枚举值或空字符串
        :param scene_id: 场景 ID，可为 None
        :param system_id: 系统 ID，可为 None
        :param resource_type: ResourceVisibilityType 枚举值，如 "tool"、"panel" 等
        :param pk_field: queryset 中用于匹配 resource_id 的主键字段名
        :return: 过滤后的 queryset
        """
        if binding_type == BindingType.PLATFORM_BINDING:
            # 仅返回平台级资源
            if scene_id is not None or system_id:
                # 按可见范围过滤
                visible_ids = BindingScopeFilter._get_visible_platform_ids(
                    resource_type=resource_type,
                    scene_id=scene_id,
                    system_id=system_id,
                )
                return queryset.filter(**{f"{pk_field}__in": visible_ids})
            else:
                # 未指定场景/系统，返回所有平台级资源（管理员查看）
                platform_ids = set(
                    ResourceBinding.objects.filter(
                        resource_type=resource_type,
                        binding_type=BindingType.PLATFORM_BINDING,
                    ).values_list("resource_id", flat=True)
                )
                return queryset.filter(**{f"{pk_field}__in": platform_ids})

        if binding_type == BindingType.SCENE_BINDING:
            # 场景级资源仅可关联一个场景，不支持通过 system_id 过滤
            if scene_id is None and system_id:
                raise ValueError("场景级资源仅可关联一个场景，不支持通过 system_id 过滤，" "请传入 scene_id 进行过滤")
            if scene_id is not None:
                scene_resource_ids = BindingScopeFilter._get_scene_binding_ids(
                    resource_type=resource_type,
                    scene_ids=[scene_id],
                )
                return queryset.filter(**{f"{pk_field}__in": scene_resource_ids})
            # 未指定场景，不返回任何资源
            return queryset.none()

        if scene_id is not None or system_id:
            # 传了 scene_id 或 system_id 但没指定 binding_type
            if scene_id is not None:
                # 返回该场景的场景级资源 + 对该场景可见的平台级资源（并集）
                scene_resource_ids = BindingScopeFilter._get_scene_binding_ids(
                    resource_type=resource_type,
                    scene_ids=[scene_id],
                )
                platform_resource_ids = BindingScopeFilter._get_visible_platform_ids(
                    resource_type=resource_type,
                    scene_id=scene_id,
                )
                return queryset.filter(**{f"{pk_field}__in": scene_resource_ids | platform_resource_ids})
            else:
                # 仅传 system_id：场景级资源无法绑定到系统，只返回对该系统可见的平台级资源
                platform_resource_ids = BindingScopeFilter._get_visible_platform_ids(
                    resource_type=resource_type,
                    system_id=system_id,
                )
                return queryset.filter(**{f"{pk_field}__in": platform_resource_ids})

        # 都不传，返回全部资源（兼容存量，不做过滤）
        return queryset
