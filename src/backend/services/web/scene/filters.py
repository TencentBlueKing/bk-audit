# -*- coding: utf-8 -*-
"""
通用场景过滤器（ScopeFilter）

提供统一的资源-场景过滤能力，消除各模块中重复的 scene 过滤样板代码。

支持两种过滤模式：
1. 简单模式（SceneScopeFilter）：按 scene_id 过滤，适用于策略、联表、处理套餐、通知组、风险等纯场景级资源
2. 组合模式（CompositeScopeFilter）：支持 binding_type + scene_id/system_id 组合过滤，适用于工具、报表等同时存在平台级和场景级的资源

过滤规则：
- 场景级资源仅支持 scene_id 过滤（场景级资源无法绑定到系统）
- 平台级资源支持 scene_id 和 system_id 过滤（通过可见范围配置）
- 都不传：返回空结果

使用示例：

    # 简单模式 — 策略列表按场景过滤
    from services.web.scene.filters import SceneScopeFilter

    class ListStrategy(StrategyV2Base):
        def perform_request(self, validated_request_data):
            scene_id = validated_request_data.pop("scene_id", None)
            queryset = Strategy.objects.all()
            queryset = SceneScopeFilter.filter_queryset(
                queryset=queryset,
                scene_id=scene_id,
                resource_type=ResourceVisibilityType.STRATEGY,
                pk_field="strategy_id",
            )
            return queryset

    # 组合模式 — 工具列表按 binding_type + scene_id/system_id 过滤
    from services.web.scene.filters import CompositeScopeFilter

    class ListTool(ToolBase):
        def perform_request(self, validated_request_data):
            binding_type = validated_request_data.get("binding_type", "")
            scene_id = validated_request_data.get("scene_id")
            system_id = validated_request_data.get("system_id")
            queryset = Tool.all_latest_tools()
            queryset = CompositeScopeFilter.filter_queryset(
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

from services.web.scene.constants import (
    BindingType,
    ResourceVisibilityType,
    VisibilityScope,
)
from services.web.scene.models import ResourceBinding, ResourceBindingScene, SceneSystem


def _normalize_scope_values(value) -> list:
    """将单值/多值 scope 参数统一转为列表。"""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set, frozenset)):
        return [item for item in value if item is not None and item != ""]
    return [value]


class SceneScopeFilter:
    """简单场景过滤器

    适用于纯场景级资源（策略、联表、处理套餐、处理规则、通知组、风险），
    仅按 scene_id 过滤（场景级资源无法绑定到系统，不支持 system_id 过滤）。

    过滤逻辑：
    - 传 scene_id：通过 ResourceBindingScene 返回该场景/场景列表下的资源并集
    - 不传：返回空结果
    """

    @staticmethod
    def filter_queryset(
        queryset: QuerySet,
        scene_id=None,
        resource_type: str = "",
        pk_field: str = "pk",
    ) -> QuerySet:
        """
        按场景过滤 queryset（场景级资源不支持 system_id 过滤）

        :param queryset: 原始 queryset
        :param scene_id: 场景 ID，为 None 时不过滤
        :param resource_type: ResourceVisibilityType 枚举值，如 "strategy"、"risk" 等
        :param pk_field: queryset 中用于匹配 resource_id 的主键字段名
        :return: 过滤后的 queryset
        """
        scene_ids = _normalize_scope_values(scene_id)
        if scene_ids:
            if resource_type == ResourceVisibilityType.RISK:
                strategy_ids = ResourceBindingScene.objects.filter(
                    scene_id__in=scene_ids,
                    binding__resource_type=ResourceVisibilityType.STRATEGY,
                ).values_list("binding__resource_id", flat=True)
                return queryset.filter(strategy_id__in=list(strategy_ids))
            # 按场景列表过滤：通过 ResourceBindingScene 查找并取并集
            bound_ids = ResourceBindingScene.objects.filter(
                scene_id__in=scene_ids,
                binding__resource_type=resource_type,
            ).values_list("binding__resource_id", flat=True)
            return queryset.filter(**{f"{pk_field}__in": list(bound_ids)})

        # 未传 scene_id，不返回任何资源
        return queryset.none()

    @staticmethod
    def get_bound_resource_ids(scene_id, resource_type: str):
        """
        获取指定场景下绑定的资源 ID 列表

        :param scene_id: 场景 ID
        :param resource_type: ResourceVisibilityType 枚举值
        :return: 资源 ID 列表
        """
        scene_ids = _normalize_scope_values(scene_id)
        if resource_type == ResourceVisibilityType.RISK:
            from services.web.risk.models import Risk

            strategy_ids = ResourceBindingScene.objects.filter(
                scene_id__in=scene_ids,
                binding__resource_type=ResourceVisibilityType.STRATEGY,
            ).values_list("binding__resource_id", flat=True)
            return list(Risk.objects.filter(strategy_id__in=list(strategy_ids)).values_list("risk_id", flat=True))

        return list(
            ResourceBindingScene.objects.filter(
                scene_id__in=scene_ids,
                binding__resource_type=resource_type,
            ).values_list("binding__resource_id", flat=True)
        )

    @staticmethod
    def create_resource_binding(
        resource_id: str,
        resource_type: str,
        scene_id,
    ) -> ResourceBinding:
        """
        创建资源的 ResourceBinding 关联（纯场景级资源专用）

        场景级资源只能绑定到场景，不支持绑定到系统。
        - 传 scene_id：创建 ResourceBinding + ResourceBindingScene
        - 不传 scene_id：抛出 ValueError

        :param resource_id: 资源 ID
        :param resource_type: ResourceVisibilityType 枚举值
        :param scene_id: 场景 ID（必传）
        :return: 创建的 ResourceBinding 实例
        """
        from services.web.scene.constants import BindingType as _BindingType

        if scene_id is None:
            raise ValueError("创建场景级资源绑定时，scene_id 为必传参数")

        binding = ResourceBinding.objects.create(
            resource_type=resource_type,
            resource_id=str(resource_id),
            binding_type=_BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=binding, scene_id=scene_id)
        return binding


class CompositeScopeFilter:
    """组合场景过滤器

    适用于同时存在平台级和场景级的资源（工具、报表），
    支持 binding_type + scene_id/system_id 组合过滤。

    过滤逻辑：
    - binding_type=platform_binding：仅返回平台级资源
    - binding_type=platform_binding + scene_id/system_id：返回对该场景/系统列表可见的平台级资源并集
    - binding_type=scene_binding + scene_id：仅返回该场景/场景列表的场景级资源并集
    - binding_type=scene_binding + system_id：不支持，场景级资源仅可关联一个场景，无法通过系统过滤
    - 仅传 scene_id（无 binding_type）：返回该场景/场景列表的场景级资源 + 对这些场景可见的平台级资源（并集）
    - 仅传 system_id（无 binding_type）：仅返回对该系统/系统列表可见的平台级资源（场景级资源无法绑定到系统）
    - 都不传：返回空结果
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
        - all_systems：所有系统可见
        - specific_scenes：仅指定场景可见（通过 ResourceBindingScene 判断）
        - specific_systems：仅指定系统可见（通过 ResourceBindingSystem 判断）
        """
        platform_bindings = ResourceBinding.objects.filter(
            resource_type=resource_type,
            binding_type=BindingType.PLATFORM_BINDING,
        )
        scene_ids = _normalize_scope_values(scene_id)
        system_ids = _normalize_scope_values(system_id)

        visible_ids = set()

        for binding in platform_bindings:
            if binding.visibility_type in (VisibilityScope.ALL_VISIBLE, VisibilityScope.ALL_SCENES):
                # 全部可见 / 全部场景可见
                visible_ids.add(binding.resource_id)

            elif binding.visibility_type == VisibilityScope.ALL_SYSTEMS:
                # 全系统可见：按 system_id 过滤时直接可见；按 scene_id 过滤时仅对有关联系统的场景可见
                if system_ids:
                    visible_ids.add(binding.resource_id)
                elif scene_ids and SceneSystem.objects.filter(scene_id__in=scene_ids).exists():
                    visible_ids.add(binding.resource_id)

            elif binding.visibility_type == VisibilityScope.SPECIFIC_SCENES:
                # 指定场景可见：检查是否绑定到目标场景
                if scene_ids:
                    if binding.binding_scenes.filter(scene_id__in=scene_ids).exists():
                        visible_ids.add(binding.resource_id)
                elif system_ids:
                    # 按系统过滤时，检查该资源绑定的可见场景中是否有关联该系统的场景
                    binding_scene_ids = set(binding.binding_scenes.values_list("scene_id", flat=True))
                    # 查找这些场景中哪些关联了目标系统
                    if binding_scene_ids:
                        matched = SceneSystem.objects.filter(
                            scene_id__in=binding_scene_ids,
                            system_id__in=system_ids,
                        ).exists()
                        if matched:
                            visible_ids.add(binding.resource_id)

            elif binding.visibility_type == VisibilityScope.SPECIFIC_SYSTEMS:
                # 指定系统可见：检查目标系统是否在可见系统列表中
                binding_system_ids = set(binding.binding_systems.values_list("system_id", flat=True))
                if system_ids:
                    # 直接判断目标系统列表是否与可见系统列表有交集
                    if set(system_ids) & binding_system_ids:
                        visible_ids.add(binding.resource_id)
                elif scene_ids:
                    # 按场景过滤时，检查这些场景关联的系统是否在可见系统列表中
                    scene_system_ids = set(
                        SceneSystem.objects.filter(
                            scene_id__in=scene_ids,
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
        scene_ids = _normalize_scope_values(scene_id)
        system_ids = _normalize_scope_values(system_id)

        if binding_type == BindingType.PLATFORM_BINDING:
            # 仅返回平台级资源
            if scene_ids or system_ids:
                # 按可见范围过滤
                visible_ids = CompositeScopeFilter._get_visible_platform_ids(
                    resource_type=resource_type,
                    scene_id=scene_ids,
                    system_id=system_ids,
                )
                return queryset.filter(**{f"{pk_field}__in": visible_ids})
            else:
                # 未指定场景/系统，不返回任何资源
                return queryset.none()

        if binding_type == BindingType.SCENE_BINDING:
            # 场景级资源仅可关联一个场景，不支持通过 system_id 过滤
            if not scene_ids and system_ids:
                raise ValueError("场景级资源仅可关联一个场景，不支持通过 system_id 过滤，" "请传入 scene_id 进行过滤")
            if scene_ids:
                scene_resource_ids = CompositeScopeFilter._get_scene_binding_ids(
                    resource_type=resource_type,
                    scene_ids=scene_ids,
                )
                return queryset.filter(**{f"{pk_field}__in": scene_resource_ids})
            # 未指定场景，不返回任何资源
            return queryset.none()

        if scene_ids or system_ids:
            # 传了 scene_id 或 system_id 但没指定 binding_type
            if scene_ids:
                # 返回这些场景的场景级资源 + 对这些场景可见的平台级资源（并集）
                scene_resource_ids = CompositeScopeFilter._get_scene_binding_ids(
                    resource_type=resource_type,
                    scene_ids=scene_ids,
                )
                platform_resource_ids = CompositeScopeFilter._get_visible_platform_ids(
                    resource_type=resource_type,
                    scene_id=scene_ids,
                )
                return queryset.filter(**{f"{pk_field}__in": scene_resource_ids | platform_resource_ids})
            else:
                # 仅传 system_id：场景级资源无法绑定到系统，只返回对这些系统可见的平台级资源
                platform_resource_ids = CompositeScopeFilter._get_visible_platform_ids(
                    resource_type=resource_type,
                    system_id=system_ids,
                )
                return queryset.filter(**{f"{pk_field}__in": platform_resource_ids})

        # 都不传，不返回任何资源
        return queryset.none()
