# -*- coding: utf-8 -*-
"""
工具管理默认值权限校验

"""

from typing import Any, Dict, List, Optional, Set, Tuple

from core.models import get_request_username


def _is_none_or_empty_string(value) -> bool:
    """判断值是否为 None 或空字符串"""
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def _is_empty_list(value) -> bool:
    """判断值是否为空数组"""
    return isinstance(value, list) and len(value) == 0


def _normalize_value_for_comparison(value: Any, field_category: Optional[str] = None) -> Any:
    """
    标准化值用于比较

    Args:
        value: 待比较的值
        field_category: 字段类型分类

    Returns:
        标准化后的值

    处理规则:
        - person_select/multiselect: 数组顺序无关、逗号分隔字符串等价、空值统一为 None
        - input/number/time 等其他类型：严格比较，None 和空字符串视为 None，空数组保持为 []
    """
    # 只对 person_select/multiselect 做宽松比较
    if field_category in ['person_select', 'multiselect']:
        # 空值处理（None、空字符串、空数组都视为 None）
        if _is_none_or_empty_string(value) or _is_empty_list(value):
            return None

        # 字符串转数组（按逗号分割）
        if isinstance(value, str):
            parts = [v.strip() for v in value.split(",") if v.strip()]
            return sorted(parts) if parts else None  # 如果没有有效内容，返回 None

        # 数组/元组处理
        if isinstance(value, (list, tuple)):
            if len(value) == 0:
                return None
            return sorted([str(v) for v in value if v is not None and str(v).strip()])

        # 其他类型保持不变
        return value
    else:
        # input/number/time 等类型：严格比较
        # 只把 None 和空字符串视为 None，空数组保持为 []
        if _is_none_or_empty_string(value):
            return None
        # 空数组 [] 保持不变，不转为 None
        return value


def _values_are_equal_for_empty(val1: Any, val2: Any, field_category: Optional[str] = None) -> bool:
    """
    比较两个值是否相等

    Args:
        val1: 值 1
        val2: 值 2
        field_category: 字段类型分类

    Returns:
        是否相等

    比较规则:
        - person_select/multiselect: 空值等价 (None/""/[] 都视为 None)、字符串/数组等价、数组顺序无关
        - input/number/time 等其他类型: 严格比较 (None 和 [] 不等价、"" 和 [] 不等价)
    """
    normalized1 = _normalize_value_for_comparison(val1, field_category)
    normalized2 = _normalize_value_for_comparison(val2, field_category)
    return normalized1 == normalized2


class DefaultValueValidator:
    """默认值权限校验器"""

    def __init__(self):
        """
        初始化校验器
        """
        self.username = get_request_username()

    def get_accessible_scopes(
        self,
        resource_type: str,
        resource_id: str,
        user_allowed_scene_ids: Set[str],
        user_allowed_system_ids: Set[str],
    ) -> Tuple[Set[str], Set[str]]:
        """
        获取用户实际可访问的范围（用户权限 ∩ 资源授权）

        Args:
            resource_type: 资源类型
            resource_id: 资源 ID
            user_allowed_scene_ids: 用户有权限的场景 ID 集合
            user_allowed_system_ids: 用户有权限的系统 ID 集合

        Returns:
            tuple: (accessible_scenes, accessible_systems)

        处理规则:
            - ALL_VISIBLE: 返回用户所有有权的 scenes + systems
            - ALL_SCENES: 只返回用户有权的 scenes
            - ALL_SYSTEMS: 只返回用户有权的 systems
            - SPECIFIC_SCENES: 只返回绑定的 scenes 与用户有权 scenes 的交集
            - SPECIFIC_SYSTEMS: 只返回绑定的 systems 与用户有权 systems 的交集
            - SCENES_AND_SYSTEMS: 返回 scenes 和 systems 的交集
        """
        from services.web.scene.constants import BindingType, VisibilityScope
        from services.web.scene.models import ResourceBinding

        binding = (
            ResourceBinding.objects.filter(
                resource_type=resource_type,
                resource_id=str(resource_id),
            )
            .prefetch_related('binding_scenes__scene', 'binding_systems')
            .first()
        )

        if not binding:
            return set(), set()

        # 场景级绑定：只返回场景交集
        if binding.binding_type == BindingType.SCENE_BINDING:
            bound_scene_ids = {
                str(scene_id)
                for scene_id in binding.binding_scenes.filter(scene__is_deleted=False).values_list(
                    'scene_id', flat=True
                )
            }
            return user_allowed_scene_ids & bound_scene_ids, set()

        # 平台级绑定：按 visibility_type 展开
        if binding.visibility_type == VisibilityScope.ALL_VISIBLE:
            # 全部可见：返回用户所有有权的 scenes + systems
            return user_allowed_scene_ids, user_allowed_system_ids

        elif binding.visibility_type == VisibilityScope.ALL_SCENES:
            # 全部场景：只返回用户有权的 scenes
            return user_allowed_scene_ids, set()

        elif binding.visibility_type == VisibilityScope.ALL_SYSTEMS:
            # 全部系统：只返回用户有权的 systems
            return set(), user_allowed_system_ids

        elif binding.visibility_type == VisibilityScope.SPECIFIC_SCENES:
            # 指定场景：取绑定场景与用户有权场景的交集
            bound_scene_ids = {
                str(scene_id)
                for scene_id in binding.binding_scenes.filter(scene__is_deleted=False).values_list(
                    'scene_id', flat=True
                )
            }
            return user_allowed_scene_ids & bound_scene_ids, set()

        elif binding.visibility_type == VisibilityScope.SPECIFIC_SYSTEMS:
            # 指定系统：取绑定系统与用户有权系统的交集
            bound_system_ids = set(binding.binding_systems.values_list('system_id', flat=True))
            return set(), user_allowed_system_ids & bound_system_ids

        elif binding.visibility_type == VisibilityScope.SCENES_AND_SYSTEMS:
            # 场景和系统：分别取交集
            bound_scene_ids = {
                str(scene_id)
                for scene_id in binding.binding_scenes.filter(scene__is_deleted=False).values_list(
                    'scene_id', flat=True
                )
            }
            bound_system_ids = set(binding.binding_systems.values_list('system_id', flat=True))
            return (user_allowed_scene_ids & bound_scene_ids, user_allowed_system_ids & bound_system_ids)

        # 默认返回空
        return set(), set()

    def collect_allowed_defaults(
        self,
        default_value_overrides: Dict,
        accessible_scenes: Set[str],
        accessible_systems: Set[str],
    ) -> Tuple[Dict[str, List[Any]], Set[str]]:
        """
        收集用户实际可访问的场景/系统允许的默认值

        Args:
            default_value_overrides: 默认值覆盖配置
                {
                    "scenes": {"scene_id": {"raw_name": value}},
                    "systems": {"system_id": {"raw_name": value}}
                }
            accessible_scenes: 可访问的场景 ID 集合
            accessible_systems: 可访问的系统 ID 集合

        Returns:
            tuple: (allowed_defaults, uncovered_raw_names)
                - allowed_defaults: {raw_name: [allowed_values]}
                - uncovered_raw_names: 存在至少一个可访问 scope 未覆盖的 raw_name 集合
        """
        allowed_defaults: Dict[str, List[Any]] = {}
        scenes_overrides = default_value_overrides.get("scenes", {})
        systems_overrides = default_value_overrides.get("systems", {})

        # 收集场景级别的默认值
        for scene_id in accessible_scenes:
            overrides = scenes_overrides.get(scene_id)
            if not overrides or not isinstance(overrides, dict):
                continue
            for raw_name, default_value in overrides.items():
                if raw_name:
                    allowed_defaults.setdefault(raw_name, []).append(default_value)

        # 收集系统级别的默认值
        for system_id in accessible_systems:
            overrides = systems_overrides.get(system_id)
            if not overrides or not isinstance(overrides, dict):
                continue
            for raw_name, default_value in overrides.items():
                if raw_name:
                    allowed_defaults.setdefault(raw_name, []).append(default_value)

        # 按 raw_name 维度计算 uncovered_raw_names，再用户可访问的范围中收集raw_name
        # uncovered_raw_names: 存在至少一个可访问 scope 未覆盖该 raw_name
        all_raw_names: Set[str] = set()
        for scene_id in accessible_scenes:
            overrides = scenes_overrides.get(scene_id)
            if isinstance(overrides, dict):
                all_raw_names.update(k for k in overrides.keys() if k)
        for system_id in accessible_systems:
            overrides = systems_overrides.get(system_id)
            if isinstance(overrides, dict):
                all_raw_names.update(k for k in overrides.keys() if k)

        uncovered_raw_names: Set[str] = set()

        # 对每个 raw_name，检查是否存在可访问 scope 未覆盖它
        for raw_name in all_raw_names:
            is_fully_covered = True

            # 检查场景维度：该 raw_name 是否在所有可访问场景中都有覆盖
            for scene_id in accessible_scenes:
                scene_overrides = scenes_overrides.get(scene_id, {})
                if raw_name not in scene_overrides:
                    is_fully_covered = False
                    break

            if not is_fully_covered:
                uncovered_raw_names.add(raw_name)
                continue

            # 检查系统维度：该 raw_name 是否在所有可访问系统中都有覆盖
            for system_id in accessible_systems:
                system_overrides = systems_overrides.get(system_id, {})
                if raw_name not in system_overrides:
                    is_fully_covered = False
                    break

            if not is_fully_covered:
                uncovered_raw_names.add(raw_name)

        return allowed_defaults, uncovered_raw_names

    def validate_variable_value(
        self,
        raw_name: str,
        value: Any,
        field_category: Optional[str],
        original_default: Any,
        allowed_defaults: Dict[str, List[Any]],
        uncovered_raw_names: Set[str],
    ) -> bool:
        """
        校验变量值是否合法

        Args:
            raw_name: 变量原始名称
            value: 实际传入的值
            field_category: 字段类型分类
            original_default: 变量原始默认值
            allowed_defaults: 允许的默认值字典 {raw_name: [allowed_values]}
            uncovered_raw_names: 存在至少一个可访问 scope 未覆盖的 raw_name 集合

        Returns:
            bool: 是否校验通过

        校验规则:
            - raw_name 不在 allowed_defaults 中：只能用原始默认值
            - raw_name 在 uncovered_raw_names 中（部分 scope 未覆盖）：允许覆盖值 OR 原始默认值
            - raw_name 完全覆盖（不在 uncovered_raw_names 中）：只能用覆盖值
        """
        if raw_name not in allowed_defaults:
            # 无覆盖配置，只能用原始默认值
            return _values_are_equal_for_empty(value, original_default, field_category)

        elif raw_name in uncovered_raw_names:
            # 该 raw_name 存在未覆盖的 scope，允许：覆盖值 OR 原始默认值
            is_allowed = any(
                _values_are_equal_for_empty(value, allowed_value, field_category)
                for allowed_value in allowed_defaults[raw_name]
            )
            if not is_allowed:
                is_allowed = _values_are_equal_for_empty(value, original_default, field_category)
            return is_allowed

        else:
            return any(
                _values_are_equal_for_empty(value, allowed_value, field_category)
                for allowed_value in allowed_defaults[raw_name]
            )

    def _should_skip_validation(self, raw_name: str, var_config: dict) -> bool:
        """
        判断是否跳过某个变量的校验

        Args:
            raw_name: 变量原始名称
            var_config: 变量配置

        Returns:
            bool: 是否应该跳过校验

        跳过规则:
            - is_show=True: 用户可见的参数，由用户自行填写，无需校验
            - time_range_select/time-ranger: 时间范围选择器，支持相对时间表达式，豁免校验
        """
        # is_show=True 的参数，用户可见，无需校验
        if var_config.get("is_show", True):
            return True

        # 豁免时间范围选择器
        field_category = var_config.get("field_category")
        if field_category in ["time_range_select", "time-ranger"]:
            return True

        return False

    def validate_tool_default_values(
        self,
        tool_config: dict,
        tool_variables: List[dict],
        resource_type: str,
        resource_id: str,
        user_allowed_scene_ids: Set[str],
        user_allowed_system_ids: Set[str],
    ):
        """
        完整校验工具默认值权限

        Args:
            tool_config: 工具配置（包含 input_variable 和 default_value_overrides）
            tool_variables: 工具变量列表
            resource_type: 资源类型
            resource_id: 资源 ID
            user_allowed_scene_ids: 用户有权限的场景 ID 集合
            user_allowed_system_ids: 用户有权限的系统 ID 集合

        校验流程:
            1. 获取用户实际可访问的范围（用户权限 ∩ 资源授权）
            2. 收集允许的默认值和每个 raw_name 的覆盖状态
            3. 遍历工具变量，校验每个变量的值是否合法
            4. 如果校验失败，直接抛出 PermissionException

        异常:
            PermissionException: 校验失败时抛出
        """
        from django.utils.translation import gettext, gettext_lazy

        from core.exceptions import PermissionException

        # 1. 获取可访问范围
        accessible_scenes, accessible_systems = self.get_accessible_scopes(
            resource_type=resource_type,
            resource_id=resource_id,
            user_allowed_scene_ids=user_allowed_scene_ids,
            user_allowed_system_ids=user_allowed_system_ids,
        )

        # 如果没有可访问范围，跳过校验
        if not accessible_scenes and not accessible_systems:
            return

        # 2. 收集允许的默认值
        default_value_overrides = tool_config.get("default_value_overrides", {})
        if not default_value_overrides:
            # 没有覆盖配置，无需校验
            return

        allowed_defaults, uncovered_raw_names = self.collect_allowed_defaults(
            default_value_overrides=default_value_overrides,
            accessible_scenes=accessible_scenes,
            accessible_systems=accessible_systems,
        )

        # 3. 构建输入变量配置映射
        input_variables = tool_config.get("input_variable", [])
        input_var_map = {var["raw_name"]: var for var in input_variables if var.get("raw_name")}

        # 4. 遍历工具变量，校验每个变量
        for var in tool_variables:
            raw_name = var.get("raw_name")
            if not raw_name:
                continue

            value = var.get("value")
            var_config = input_var_map.get(raw_name, {})

            # 跳过不需要校验的变量
            if self._should_skip_validation(raw_name, var_config):
                continue

            # 校验变量值
            original_default = var_config.get("default_value")
            field_category = var_config.get("field_category")

            is_valid = self.validate_variable_value(
                raw_name=raw_name,
                value=value,
                field_category=field_category,
                original_default=original_default,
                allowed_defaults=allowed_defaults,
                uncovered_raw_names=uncovered_raw_names,
            )

            if not is_valid:
                use_original_message = raw_name not in allowed_defaults
                if use_original_message:
                    action_name = gettext_lazy("使用隐藏参数 %(var_name)s 的默认值") % {"var_name": raw_name}
                    permission = gettext("参数 %(var_name)s 不可见，只能使用默认值") % {"var_name": raw_name}
                else:
                    action_name = gettext_lazy("使用隐藏参数 %(var_name)s 的默认值") % {"var_name": raw_name}
                    permission = gettext("参数 %(var_name)s 的默认值不存在") % {"var_name": raw_name}
                raise PermissionException(action_name=action_name, permission=permission)
