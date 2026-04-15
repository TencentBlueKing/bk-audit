# -*- coding: utf-8 -*-
from services.web.scene.constants import BindingType, VisibilityScope


def _normalize_values(values) -> list:
    if values is None:
        return []
    if isinstance(values, (list, tuple, set, frozenset)):
        return [v for v in values if v not in ("", None)]
    return [values] if values not in ("", None) else []


def validate_platform_visibility_payload(visibility_type: str, scene_ids=None, system_ids=None) -> None:
    """
    校验平台级绑定可见范围配置。

    规则：
    - visibility_type=specific_scenes 时，scene_ids 必须非空
    - visibility_type=specific_systems 时，system_ids 必须非空
    """
    normalized_scene_ids = _normalize_values(scene_ids)
    normalized_system_ids = _normalize_values(system_ids)

    if visibility_type == VisibilityScope.SPECIFIC_SCENES and not normalized_scene_ids:
        raise ValueError("platform_binding 的 visibility_type 为 specific_scenes 时，scene_ids 不能为空")
    if visibility_type == VisibilityScope.SPECIFIC_SYSTEMS and not normalized_system_ids:
        raise ValueError("platform_binding 的 visibility_type 为 specific_systems 时，system_ids 不能为空")


def assert_binding_relation_integrity(binding, scene_count: int = None, system_count: int = None) -> None:
    """
    校验绑定关系完整性。

    规则：
    - scene_binding：必须且仅能关联 1 个 scene；且不允许绑定 system
    - platform_binding + specific_scenes：必须关联至少 1 个 scene
    - platform_binding + specific_systems：必须关联至少 1 个 system
    """
    if scene_count is None:
        scene_count = binding.binding_scenes.count()
    if system_count is None:
        system_count = binding.binding_systems.count()

    if binding.binding_type == BindingType.SCENE_BINDING:
        if scene_count != 1:
            raise ValueError("scene_binding 必须且仅能关联一个 scene")
        if system_count != 0:
            raise ValueError("scene_binding 不允许关联 system")
        return

    if binding.binding_type == BindingType.PLATFORM_BINDING:
        if binding.visibility_type == VisibilityScope.SPECIFIC_SCENES and scene_count == 0:
            raise ValueError("platform_binding 的 visibility_type 为 specific_scenes 时，必须关联至少一个 scene")
        if binding.visibility_type == VisibilityScope.SPECIFIC_SYSTEMS and system_count == 0:
            raise ValueError("platform_binding 的 visibility_type 为 specific_systems 时，必须关联至少一个 system")
