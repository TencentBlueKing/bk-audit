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

from typing import Any, Iterable, Sequence

from django.db.models import Count, QuerySet

from services.web.scene.binding_validation import assert_binding_relation_integrity
from services.web.scene.constants import (
    BindingType,
    ResourceVisibilityType,
    VisibilityScope,
)
from services.web.scene.models import ResourceBinding, ResourceBindingScene, SceneSystem


class BindingMetadataHelper:
    """统一装配 ResourceBinding 元数据，避免业务模块各自查表。"""

    @staticmethod
    def _normalize_resource_ids(resource_ids: Iterable[Any]) -> list[str]:
        """将资源 ID 统一标准化为字符串列表，便于匹配 `ResourceBinding.resource_id`。"""
        normalized_ids = []
        for resource_id in resource_ids:
            if resource_id is None:
                continue
            normalized_ids.append(str(resource_id))
        return normalized_ids

    @classmethod
    def get_binding_map(
        cls,
        resource_type: str,
        resource_ids: Iterable[Any],
        prefetch_related: Sequence[str] = (),
    ) -> dict[str, ResourceBinding]:
        """批量读取资源绑定对象。

        Args:
            resource_type: `ResourceVisibilityType` 枚举值。
            resource_ids: 待查询的资源 ID 集合。
            prefetch_related: 需要预取的关联字段名。

        Returns:
            以字符串 `resource_id` 为 key 的绑定对象映射。
        """
        normalized_ids = cls._normalize_resource_ids(resource_ids)
        if not normalized_ids:
            return {}

        queryset = ResourceBinding.objects.filter(
            resource_type=resource_type,
            resource_id__in=normalized_ids,
        )
        if prefetch_related:
            queryset = queryset.prefetch_related(*prefetch_related)

        return {binding.resource_id: binding for binding in queryset}

    @classmethod
    def get_binding_metadata_map(
        cls,
        resource_type: str,
        resource_ids: Iterable[Any],
        fields: Sequence[str] = ("binding_type",),
    ) -> dict[str, dict[str, Any]]:
        """批量读取资源绑定元数据。

        Args:
            resource_type: `ResourceVisibilityType` 枚举值。
            resource_ids: 待查询的资源 ID 集合。
            fields: 需要暴露的 `ResourceBinding` 字段名。

        Returns:
            结构为 `resource_id -> {field: value}` 的字典。
        """
        binding_map = cls.get_binding_map(resource_type=resource_type, resource_ids=resource_ids)
        metadata_map = {}
        for resource_id in cls._normalize_resource_ids(resource_ids):
            binding = binding_map.get(resource_id)
            metadata_map[resource_id] = {
                field: getattr(binding, field, None) if binding is not None else None for field in fields
            }
        return metadata_map

    @classmethod
    def attach_binding_metadata(
        cls,
        objects: Iterable[Any],
        resource_type: str,
        id_attr: str = "id",
        fields: Sequence[str] = ("binding_type",),
    ) -> None:
        """将绑定元数据直接回填到对象属性上。

        Args:
            objects: 需要回填的对象集合。
            resource_type: `ResourceVisibilityType` 枚举值。
            id_attr: 对象上的资源 ID 属性名。
            fields: 需要回填的 `ResourceBinding` 字段名。
        """
        object_list = list(objects)
        if not object_list:
            return

        resource_ids = [getattr(obj, id_attr, None) for obj in object_list]
        metadata_map = cls.get_binding_metadata_map(
            resource_type=resource_type,
            resource_ids=resource_ids,
            fields=fields,
        )
        for obj in object_list:
            metadata = metadata_map.get(str(getattr(obj, id_attr, None)), {})
            for field in fields:
                setattr(obj, field, metadata.get(field))

    @classmethod
    def attach_scene_id_via_binding_resource(
        cls,
        objects: Iterable[Any],
        *,
        binding_resource_type: str,
        binding_resource_id_attr: str,
        target_attr: str = "scene_id",
    ) -> None:
        """通过资源绑定关系回填单个 `scene_id`。

        适用于“业务对象本身不直接绑定场景，而是经由另一类资源间接绑定场景”的场景。
        当前风险列表即通过 `strategy_id -> strategy binding -> scene_id` 回填。

        Args:
            objects: 需要回填的对象集合。
            binding_resource_type: 绑定资源类型，如 `ResourceVisibilityType.STRATEGY`。
            binding_resource_id_attr: 对象上用于匹配 `ResourceBinding.resource_id` 的属性名。
            target_attr: 回填到对象上的目标属性名，默认 `scene_id`。
        """
        object_list = list(objects)
        if not object_list:
            return

        binding_resource_ids = [
            getattr(obj, binding_resource_id_attr, None)
            for obj in object_list
            if getattr(obj, binding_resource_id_attr, None) is not None
        ]
        if not binding_resource_ids:
            return

        # 风险/策略等链路当前都是“一资源只绑定一个场景”，这里取首个 scene_id 即可。
        scene_id_map = {
            resource_id: scene_id
            for resource_id, scene_id in ResourceBindingScene.objects.filter(
                binding__resource_type=binding_resource_type,
                binding__resource_id__in=cls._normalize_resource_ids(binding_resource_ids),
            ).values_list("binding__resource_id", "scene_id")
        }
        for obj in object_list:
            binding_resource_id = getattr(obj, binding_resource_id_attr, None)
            setattr(obj, target_attr, scene_id_map.get(str(binding_resource_id)))


def _normalize_scope_values(value) -> list:
    """将单值/多值 scope 参数统一转为列表。"""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set, frozenset)):
        return [item for item in value if item is not None and item != ""]
    return [value]


def _normalize_binding_type(binding_type):
    """将 binding_type 统一归一为枚举值或 None。"""
    if binding_type in {None, ""}:
        return None

    valid_binding_types = {BindingType.PLATFORM_BINDING, BindingType.SCENE_BINDING}
    if binding_type not in valid_binding_types:
        raise ValueError(f"binding_type={binding_type} 不合法，可选值：{', '.join(sorted(valid_binding_types))}")

    return binding_type


class SceneScopeFilter:
    """简单场景过滤器

    适用于纯场景级资源（策略、联表、处理套餐、处理规则、通知组、风险），
    仅按 scene_id 过滤（场景级资源无法绑定到系统，不支持 system_id 过滤）。

    过滤逻辑：
    - 传 scene_id：通过 ResourceBindingScene 返回该场景/场景列表下的资源并集
    - 不传：返回空结果
    """

    @staticmethod
    def _assert_scene_binding_integrity(resource_type: str) -> None:
        """校验指定资源类型的 scene_binding 绑定完整性。"""
        bindings = ResourceBinding.objects.filter(
            resource_type=resource_type,
            binding_type=BindingType.SCENE_BINDING,
        ).annotate(
            scene_count=Count("binding_scenes", distinct=True),
            system_count=Count("binding_systems", distinct=True),
        )
        for binding in bindings:
            assert_binding_relation_integrity(
                binding, scene_count=binding.scene_count, system_count=binding.system_count
            )

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
                SceneScopeFilter._assert_scene_binding_integrity(ResourceVisibilityType.STRATEGY)
                strategy_ids = ResourceBindingScene.objects.filter(
                    scene_id__in=scene_ids,
                    binding__resource_type=ResourceVisibilityType.STRATEGY,
                ).values_list("binding__resource_id", flat=True)
                return queryset.filter(strategy_id__in=list(strategy_ids))
            SceneScopeFilter._assert_scene_binding_integrity(resource_type)
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

            SceneScopeFilter._assert_scene_binding_integrity(ResourceVisibilityType.STRATEGY)
            strategy_ids = ResourceBindingScene.objects.filter(
                scene_id__in=scene_ids,
                binding__resource_type=ResourceVisibilityType.STRATEGY,
            ).values_list("binding__resource_id", flat=True)
            return list(Risk.objects.filter(strategy_id__in=list(strategy_ids)).values_list("risk_id", flat=True))

        SceneScopeFilter._assert_scene_binding_integrity(resource_type)
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
        assert_binding_relation_integrity(binding)
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
        all_scene_bindings = ResourceBinding.objects.filter(
            resource_type=resource_type,
            binding_type=BindingType.SCENE_BINDING,
        ).annotate(
            scene_count=Count("binding_scenes", distinct=True),
            system_count=Count("binding_systems", distinct=True),
        )
        for binding in all_scene_bindings:
            assert_binding_relation_integrity(
                binding, scene_count=binding.scene_count, system_count=binding.system_count
            )

        binding_ids = ResourceBindingScene.objects.filter(
            scene_id__in=scene_ids,
        ).values_list("binding_id", flat=True)
        return set(all_scene_bindings.filter(id__in=binding_ids).values_list("resource_id", flat=True))

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
        ).annotate(
            scene_count=Count("binding_scenes", distinct=True),
            system_count=Count("binding_systems", distinct=True),
        )
        scene_ids = _normalize_scope_values(scene_id)
        system_ids = _normalize_scope_values(system_id)

        visible_ids = set()

        for binding in platform_bindings:
            assert_binding_relation_integrity(
                binding, scene_count=binding.scene_count, system_count=binding.system_count
            )
            if binding.visibility_type in (VisibilityScope.ALL_VISIBLE, VisibilityScope.ALL_SCENES):
                # 全部可见 / 全部场景可见
                visible_ids.add(binding.resource_id)

            elif binding.visibility_type == VisibilityScope.ALL_SYSTEMS:
                # 全系统可见：仅按 system_id 过滤时直接可见
                if system_ids:
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
        binding_type=None,
        scene_id=None,
        system_id: str = None,
        resource_type: str = "",
        pk_field: str = "pk",
    ) -> QuerySet:
        """
        按 binding_type + scene_id/system_id 组合过滤 queryset

        :param queryset: 原始 queryset
        :param binding_type: 绑定类型，BindingType 枚举值或 None（None=全部）
        :param scene_id: 场景 ID，可为 None
        :param system_id: 系统 ID，可为 None
        :param resource_type: ResourceVisibilityType 枚举值，如 "tool"、"panel" 等
        :param pk_field: queryset 中用于匹配 resource_id 的主键字段名
        :return: 过滤后的 queryset
        """
        binding_type = _normalize_binding_type(binding_type)
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
                # 未指定场景/系统时，返回全部平台级绑定资源
                platform_resource_ids = ResourceBinding.objects.filter(
                    resource_type=resource_type,
                    binding_type=BindingType.PLATFORM_BINDING,
                ).values_list("resource_id", flat=True)
                return queryset.filter(**{f"{pk_field}__in": platform_resource_ids})

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
