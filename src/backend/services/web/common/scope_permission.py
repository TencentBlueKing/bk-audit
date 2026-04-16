# -*- coding: utf-8 -*-
"""
Scope 权限组件

提供统一的 scope 解析、入口校验、资源级校验、资源筛选能力。
业务模块三类权限需求均通过本文件组件承接：
1. ScopeEntryPermission —— 仅负责挂载 scope 上下文（DRF BasePermission）
2. ScopeEntryActionPermission —— 带 action 的严格入口鉴权（DRF BasePermission）
3. ScopeInstancePermission —— 资源实例级鉴权（DRF BasePermission）
4. ScopePermission —— 通用 scope 服务类（业务主调用方式）

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from rest_framework.permissions import BasePermission

from apps.meta.converter import SystemDjangoQuerySetConverter
from apps.meta.models import System
from apps.permission.handlers.actions import ActionMeta
from apps.permission.handlers.actions.action import ActionEnum
from apps.permission.handlers.drf import InstancePermission
from apps.permission.handlers.permission import Permission
from apps.permission.handlers.resource_types import ResourceEnum
from core.exceptions import PermissionException, ValidationError
from core.models import get_request_username
from services.web.common.constants import (
    BindingResourceType,
    ScopeQueryField,
    ScopeType,
)
from services.web.scene.constants import BindingType, VisibilityScope
from services.web.scene.converter import SceneDjangoQuerySetConverter
from services.web.scene.models import (
    ResourceBinding,
    ResourceBindingScene,
    ResourceBindingSystem,
    Scene,
    SceneSystem,
)

# IAM 资源类型 ID 常量（用于判断 action 关联的 resource_type）
_SCENE_RESOURCE_TYPE_ID = ResourceEnum.SCENE.id  # "scene"
_SYSTEM_RESOURCE_TYPE_ID = ResourceEnum.SYSTEM.id  # "system"


def _is_scope_action(action: ActionMeta) -> bool:
    """判断 action 的 related_resource_types 是否为 scene 或 system

    只要 action 关联的 IAM 资源类型中包含 scene 或 system，即视为可走 check_scope_entry。
    """
    return any(rt.id in {_SCENE_RESOURCE_TYPE_ID, _SYSTEM_RESOURCE_TYPE_ID} for rt in action.related_resource_types)


def _is_scene_action(action: ActionMeta) -> bool:
    """判断 action 关联的 IAM 资源类型是否包含 scene"""
    return any(rt.id == _SCENE_RESOURCE_TYPE_ID for rt in action.related_resource_types)


def _is_system_action(action: ActionMeta) -> bool:
    """判断 action 关联的 IAM 资源类型是否包含 system"""
    return any(rt.id == _SYSTEM_RESOURCE_TYPE_ID for rt in action.related_resource_types)


# ---------------------------------------------------------------------------
# ScopeContext
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScopeContext:
    """统一承载 scope_type + scope_id 的轻量上下文

    协议约束（构造时自动校验）：
    - cross_scene / cross_system：scope_id 为空（传了也会被归一化为 None）
    - scene / system：scope_id 必填

    支持两种构造方式：
    1. 直接构造：ScopeContext("scene", "123") / ScopeContext(ScopeType.SCENE, "123")
    2. 从请求解析：ScopeContext.from_request(request)
    """

    scope_type: ScopeType
    scope_id: Optional[str] = None

    def __post_init__(self):
        # --- scope_type 归一化：接受字符串，转为 ScopeType 枚举 ---
        raw_type = self.scope_type
        if isinstance(raw_type, str) and not isinstance(raw_type, ScopeType):
            if raw_type not in ScopeType.values:
                raise ValidationError(f"scope_type 不合法，可选值：{', '.join(ScopeType.values)}")
            object.__setattr__(self, "scope_type", ScopeType(raw_type))

        # --- 协议约束校验 ---
        if self.scope_type in {ScopeType.SCENE, ScopeType.SYSTEM}:
            if not self.scope_id:
                raise ValidationError(f"scope_type={self.scope_type} 时 scope_id 为必传参数")
        else:
            # cross_scene / cross_system 不需要 scope_id，归一化为 None
            object.__setattr__(self, "scope_id", None)

    @property
    def is_scene_scope(self) -> bool:
        return self.scope_type in {ScopeType.CROSS_SCENE, ScopeType.SCENE}

    @property
    def is_system_scope(self) -> bool:
        return self.scope_type in {ScopeType.CROSS_SYSTEM, ScopeType.SYSTEM}

    @property
    def is_cross_scope(self) -> bool:
        return self.scope_type in {ScopeType.CROSS_SCENE, ScopeType.CROSS_SYSTEM}

    @classmethod
    def from_request(cls, request, view=None) -> "ScopeContext":
        """从 DRF / Django 请求中解析 scope 协议

        兼容 DRF Request（query_params）和 Django WSGIRequest（GET）。
        优先从 query_params/GET 获取，再从 request.data 获取。

        校验逻辑统一委托给 __post_init__。
        """
        params = getattr(request, "query_params", None) or getattr(request, "GET", {})
        data = getattr(request, "data", {})

        scope_type = params.get(ScopeQueryField.SCOPE_TYPE) or data.get(ScopeQueryField.SCOPE_TYPE)
        scope_id = params.get(ScopeQueryField.SCOPE_ID) or data.get(ScopeQueryField.SCOPE_ID)

        if not scope_type:
            raise ValidationError(f"{ScopeQueryField.SCOPE_TYPE} 为必传参数")

        return cls(scope_type=scope_type, scope_id=scope_id)


# ---------------------------------------------------------------------------
# ScopePermission — 通用 scope 服务类
# ---------------------------------------------------------------------------


class ScopePermission:
    """通用 scope 权限服务类

    职责：
    1. scope 合法性校验（check_scope_entry）
    2. scope 下可访问场景/系统实例集合回收（get_scene_ids / get_system_ids）
    3. 通用资源可见范围交集判断（check_resource_permission）

    实例挂载在 request.scope_permission 上，生命周期为单次请求。

    业务侧常见使用场景：
    - 入口鉴权：场景页进入"策略列表""规则管理"，系统页进入"系统检索""系统诊断"
    - 数据过滤：列表页根据当前 scope 只返回当前用户有权看到的 scene / system / 资源
    - 资源消费：详情页、执行页、切换启停等操作前，判断某个绑定资源是否对当前用户可见

    **方向约束策略：**
    get_scene_ids / get_system_ids 不再 raise，而是当 scope 方向不匹配时返回空集合。
    例如 get_scene_ids(scope=ScopeContext(CROSS_SYSTEM)) → []。
    这样入口不限制 scope_type，由数据筛选层决定返回什么。
    """

    def __init__(self, username: str):
        self.username = username
        self.permission = Permission(username)
        self._is_platform_admin: Optional[bool] = None
        # 请求级缓存：key 为 (scope_type, scope_id, action_id)
        self._scene_ids_cache: Dict[Tuple[ScopeType, Optional[str], str], List[int]] = {}
        self._system_ids_cache: Dict[Tuple[ScopeType, Optional[str], str], List[str]] = {}

    # ------------------------------------------------------------------
    # 内部工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_scope_action(scope_type: ScopeType, action: ActionMeta) -> None:
        """校验 action 的 related_resource_types 与 scope_type 方向是否匹配"""
        if scope_type in {ScopeType.CROSS_SCENE, ScopeType.SCENE}:
            if not _is_scene_action(action):
                raise ValueError(f"action={action.id} 的 related_resource_types 不包含 scene，" f"不能用于场景方向的 scope")
        elif scope_type in {ScopeType.CROSS_SYSTEM, ScopeType.SYSTEM}:
            if not _is_system_action(action):
                raise ValueError(f"action={action.id} 的 related_resource_types 不包含 system，" f"不能用于系统方向的 scope")

    @staticmethod
    def _validate_binding_type(
        scope: ScopeContext,
        binding_type: Optional[BindingType] = None,
    ):
        """仅校验 binding_type 与 scope 方向是否匹配。"""
        if scope.is_system_scope and binding_type == BindingType.SCENE_BINDING:
            raise ValueError("系统方向 scope 不支持 binding_type=scene_binding 过滤")

    # ------------------------------------------------------------------
    # 能力一：入口校验（内部能力）
    # ------------------------------------------------------------------

    def check_scope_entry(
        self,
        scope: ScopeContext,
        action: ActionMeta,
        raise_exception: bool = True,
    ) -> bool:
        """校验用户在指定 scope + action 下是否有入口权限。

        只适用于 action.related_resource_types 包含 scene 或 system 的 action。

        业务侧常见使用场景：
        - `cross_scene + LIST_STRATEGY`：用户进入场景维度的策略列表页，只要对任一场景有查看权限即可放行入口
        - `scene + MANAGE_SCENE`：用户进入某个具体场景的配置/管理页，需要对该场景实例具备权限
        - `cross_system/system + VIEW_SYSTEM`：用户进入系统视角的检索或诊断能力页，支持 IAM 与本地系统负责人双通道

        路由逻辑：
        - cross_scene: 宽松策略 has_action_any_permission
        - cross_system: IAM + 本地 managers 双通道
        - scene: IAM is_allowed 实例级
        - system: IAM is_allowed + 本地 managers 实例级
        """
        self._validate_scope_action(scope.scope_type, action)

        result = False

        if scope.scope_type == ScopeType.CROSS_SCENE:
            result = self.permission.has_action_any_permission(action)

        elif scope.scope_type == ScopeType.CROSS_SYSTEM:
            # 双通道：IAM 或 本地 managers
            iam_result = self.permission.has_action_any_permission(action)
            local_result = bool(System.get_managed_system_ids(self.username))
            result = iam_result or local_result

        elif scope.scope_type == ScopeType.SCENE:
            resource = ResourceEnum.SCENE.create_instance(scope.scope_id)
            result = self.permission.is_allowed(action, [resource], raise_exception=False)

        elif scope.scope_type == ScopeType.SYSTEM:
            # 双通道：IAM 或 本地 managers
            resource = ResourceEnum.SYSTEM.create_instance(scope.scope_id)
            iam_result = self.permission.is_allowed(action, [resource], raise_exception=False)
            local_result = System.is_manager(scope.scope_id, self.username)
            result = iam_result or local_result

        if not result and raise_exception:
            apply_data, apply_url = self.permission.get_apply_data([action])
            raise PermissionException(
                action_name=action.name,
                apply_url=apply_url,
                permission=apply_data,
            )

        return result

    # ------------------------------------------------------------------
    # 能力二：资源级校验（对齐 ResourceBinding 架构）
    # ------------------------------------------------------------------

    def check_resource_permission(
        self,
        resource_type: BindingResourceType,
        resource_id: str,
        raise_exception: bool = True,
    ) -> bool:
        """校验用户能否消费指定资源。

        不需要传 scope —— 遍历用户所有有权限的场景+系统范围做 any 匹配。

        业务侧常见使用场景：
        - 用户点开某个处理套餐、面板、工具详情前，先判断该资源是否在自己的可见范围内
        - 用户对某个资源执行启停、编辑、删除等实例操作前，先做一次资源消费权限校验
        """
        all_scene_ids = self._get_all_scene_ids()
        all_system_ids = self._get_all_system_ids()
        result = self._check_visibility_intersection(resource_type, resource_id, all_scene_ids, all_system_ids)

        if not result and raise_exception:
            raise PermissionException(
                action_name=f"访问资源({resource_type}:{resource_id})",
                apply_url="",
                permission={},
            )

        return result

    def _get_all_scene_ids(self) -> List[int]:
        """获取用户有 VIEW_SCENE 权限的所有场景 ID（内部复用缓存）"""
        return self.get_scene_ids(ScopeContext(ScopeType.CROSS_SCENE), ActionEnum.VIEW_SCENE)

    def _get_all_system_ids(self) -> List[str]:
        """获取用户有 VIEW_SYSTEM 权限的所有系统 ID（内部复用缓存）"""
        return self.get_system_ids(ScopeContext(ScopeType.CROSS_SYSTEM), ActionEnum.VIEW_SYSTEM)

    def _check_visibility_intersection(
        self,
        resource_type: BindingResourceType,
        resource_id: str,
        scene_ids: List[int],
        system_ids: List[str],
    ) -> bool:
        """校验资源的授权范围与用户可消费范围是否有交集。"""
        if not system_ids and not scene_ids:
            # 没有任一 scope 权限时，任何资源都不可见
            return False

        binding = ResourceBinding.objects.filter(
            resource_type=resource_type,
            resource_id=str(resource_id),
        ).first()
        if not binding:
            # 不存在绑定关系，直接返回 False
            return False

        # 平台级 all_visible：在已获得任一 scene/system scope 的前提下可见
        if (
            binding.binding_type == BindingType.PLATFORM_BINDING
            and binding.visibility_type == VisibilityScope.ALL_VISIBLE
        ):
            return True

        # 场景级绑定：检查 ResourceBindingScene
        if binding.binding_type == BindingType.SCENE_BINDING:
            bound_scene_ids = set(binding.binding_scenes.values_list("scene_id", flat=True))
            return bool(set(scene_ids) & bound_scene_ids)

        # 平台级绑定：按 visibility_type 分支
        if binding.visibility_type == VisibilityScope.ALL_SCENES:
            return bool(scene_ids)  # 用户有任意场景权限即可

        if binding.visibility_type == VisibilityScope.SPECIFIC_SCENES:
            bound_scene_ids = set(binding.binding_scenes.values_list("scene_id", flat=True))
            return bool(set(scene_ids) & bound_scene_ids)

        if binding.visibility_type == VisibilityScope.SPECIFIC_SYSTEMS:
            bound_system_ids = set(binding.binding_systems.values_list("system_id", flat=True))
            return bool(set(system_ids) & bound_system_ids)

        return False

    # ------------------------------------------------------------------
    # 能力三：资源筛选（业务主调用方式）
    # ------------------------------------------------------------------

    def get_scene_ids(
        self,
        scope: ScopeContext,
        action: ActionMeta,
    ) -> List[int]:
        """返回当前用户在指定 scope 下可访问的场景 ID 集合。

        - cross_scene: 返回用户有 action 权限的所有场景 ID
        - scene(scope_id=N): 校验用户在 scene=N 上有 action 权限，通过则返回 [N]
        - 系统方向 scope（cross_system / system）：返回空列表（方向不匹配不报错）

        业务侧常见使用场景：
        - 策略列表、规则列表、处理套餐列表按当前用户可见场景做过滤
        - 某个接口传 `scope_type=scene&scope_id=123` 时，先确认用户是否能访问场景 123，再继续查询

        结果缓存在请求级 _scene_ids_cache 中。

        :raise_exception: 当 scope_type=scene 时，校验用户是否有 action 权限，无权限则抛出 PermissionException
        """
        # 方向不匹配 → 空返回
        if not scope.is_scene_scope:
            return []

        cache_key = (scope.scope_type, scope.scope_id, action.id)
        if cache_key in self._scene_ids_cache:
            return self._scene_ids_cache[cache_key]

        result: List[int] = []

        if scope.scope_type == ScopeType.CROSS_SCENE:
            # 通过 IAM 获取有权限的场景策略 → 转为 Q 查询
            policies = self.permission.get_policies_for_action(action)
            if policies:
                converter = SceneDjangoQuerySetConverter()
                filters = converter.convert(policies)
                scene_qs = Scene.objects.filter(filters)
                result = list(scene_qs.values_list("scene_id", flat=True))
            else:
                result = []

        elif scope.scope_type == ScopeType.SCENE:
            # 实例级校验
            resource = ResourceEnum.SCENE.create_instance(scope.scope_id)
            if self.permission.is_allowed(action, [resource], raise_exception=False):
                result = [int(scope.scope_id)]
            else:
                apply_data, apply_url = self.permission.get_apply_data([action], [resource])
                raise PermissionException(
                    action_name=action.name,
                    apply_url=apply_url,
                    permission=apply_data,
                )

        self._scene_ids_cache[cache_key] = result
        return result

    def get_system_ids(
        self,
        scope: ScopeContext,
        action: ActionMeta,
    ) -> List[str]:
        """返回当前用户在指定 scope 下可访问的系统 ID 集合。

        系统权限双通道：IAM + 本地 managers_list，两者取并集。
        - 场景方向 scope（cross_scene / scene）：返回空列表（方向不匹配不报错）

        业务侧常见使用场景：
        - 系统检索、系统列表、系统诊断面板按当前用户可见系统做过滤
        - 某个接口传 `scope_type=system&scope_id=bk_monitor` 时，确认用户能访问该系统后再放行后续查询

        结果缓存在请求级 _system_ids_cache 中。

        :raise_exception: 当 scope_type=system 时，校验用户是否有 action 权限，无权限则抛出 PermissionException
        """
        # 方向不匹配 → 空返回
        if not scope.is_system_scope:
            return []

        cache_key = (scope.scope_type, scope.scope_id, action.id)
        if cache_key in self._system_ids_cache:
            return self._system_ids_cache[cache_key]

        result_set: set = set()

        if scope.scope_type == ScopeType.CROSS_SYSTEM:
            # IAM 通道
            policies = self.permission.get_policies_for_action(action)
            if policies:
                converter = SystemDjangoQuerySetConverter()
                filters = converter.convert(policies)
                iam_ids = set(System.objects.filter(filters).values_list("system_id", flat=True))
                result_set |= iam_ids

            # 本地 managers 通道（使用 Model 便捷方法，单条 SQL）
            local_ids = set(System.get_managed_system_ids(self.username))
            result_set |= local_ids

        elif scope.scope_type == ScopeType.SYSTEM:
            # 实例级双通道
            resource = ResourceEnum.SYSTEM.create_instance(scope.scope_id)
            iam_result = self.permission.is_allowed(action, [resource], raise_exception=False)
            local_result = System.is_manager(scope.scope_id, self.username)

            if iam_result or local_result:
                result_set.add(scope.scope_id)
            else:
                apply_data, apply_url = self.permission.get_apply_data([action], [resource])
                raise PermissionException(
                    action_name=action.name,
                    apply_url=apply_url,
                    permission=apply_data,
                )

        result = list(result_set)
        self._system_ids_cache[cache_key] = result
        return result

    def get_system_ids_for_scope(
        self,
        scope: ScopeContext,
    ) -> List[str]:
        """统一返回当前 scope 下可访问的系统 ID 列表（包括场景下授权的系统）。

        - cross_scene / scene → 先 get_scene_ids(VIEW_SCENE) → SceneSystem 反查系统 ID
        - cross_system / system → 直接 get_system_ids(VIEW_SYSTEM)
        """
        if scope.is_scene_scope:
            scene_ids = self.get_scene_ids(scope, ActionEnum.VIEW_SCENE)
            if not scene_ids:
                return []
            return list(
                SceneSystem.objects.filter(scene_id__in=scene_ids).values_list("system_id", flat=True).distinct()
            )
        else:
            return self.get_system_ids(scope, ActionEnum.VIEW_SYSTEM)

    def get_resource_ids(
        self,
        scope: ScopeContext,
        resource_type: BindingResourceType,
        binding_type: Optional[BindingType] = None,
    ) -> Set[str]:
        """返回当前用户在指定 scope 下可消费的资源 ID 集合。

        内部逻辑：
        - scene/cross_scene: 按 VIEW_SCENE 场景范围过滤
        - system/cross_system: 按 VIEW_SYSTEM 系统范围过滤，只返回该系统被授权的资源

        业务侧常见使用场景：
        - 面板、工具、处理套餐等资源列表，先算出当前 scope 可见的资源 ID，再去查业务表
        - 业务侧需要自行拼接复杂查询条件时，先拿到资源 ID 集合，再与其他筛选条件做交集

        注意：平台级绑定的可见性计算较复杂，此处仅处理直接匹配的情况。
        如果业务侧有更复杂的筛选逻辑，建议在业务层调用 get_scene_ids / get_system_ids
        自行组装查询条件。
        """
        self._validate_binding_type(scope, binding_type)
        visible_ids: Set[str] = set()

        if scope.is_scene_scope:
            scene_ids = self.get_scene_ids(scope, ActionEnum.VIEW_SCENE)
            if not scene_ids:
                return visible_ids
            visible_ids |= self._get_scene_visible_resource_ids(resource_type, scene_ids, binding_type=binding_type)

        elif scope.is_system_scope:
            system_ids = self.get_system_ids(scope, ActionEnum.VIEW_SYSTEM)
            if not system_ids:
                return visible_ids
            visible_ids |= self._get_system_visible_resource_ids(resource_type, system_ids, binding_type=binding_type)

        return visible_ids

    # ------------------------------------------------------------------
    # get_resource_ids 内部拆分方法（便于业务侧按需组合或覆写）
    # ------------------------------------------------------------------

    @staticmethod
    def _get_scene_visible_resource_ids(
        resource_type: BindingResourceType,
        scene_ids: List[int],
        binding_type: Optional[BindingType] = None,
    ) -> Set[str]:
        """场景方向：获取对指定场景可见的资源 ID 集合。"""
        if not scene_ids:
            return set()

        visible_ids: Set[str] = set()

        # 场景级绑定
        if binding_type in {None, BindingType.SCENE_BINDING}:
            scene_binding_ids = set(
                ResourceBindingScene.objects.filter(
                    scene_id__in=scene_ids,
                    binding__resource_type=resource_type,
                    binding__binding_type=BindingType.SCENE_BINDING,
                ).values_list("binding__resource_id", flat=True)
            )
            visible_ids |= scene_binding_ids

        if binding_type == BindingType.SCENE_BINDING:
            return visible_ids

        always_visible_ids = set(
            ResourceBinding.objects.filter(
                resource_type=resource_type,
                binding_type=BindingType.PLATFORM_BINDING,
                visibility_type__in=[VisibilityScope.ALL_VISIBLE, VisibilityScope.ALL_SCENES],
            ).values_list("resource_id", flat=True)
        )
        visible_ids |= always_visible_ids

        specific_scene_ids = set(
            ResourceBindingScene.objects.filter(
                scene_id__in=scene_ids,
                binding__resource_type=resource_type,
                binding__binding_type=BindingType.PLATFORM_BINDING,
                binding__visibility_type=VisibilityScope.SPECIFIC_SCENES,
            ).values_list("binding__resource_id", flat=True)
        )
        visible_ids |= specific_scene_ids

        if SceneSystem.objects.filter(scene_id__in=scene_ids).exists():
            all_systems_ids = set(
                ResourceBinding.objects.filter(
                    resource_type=resource_type,
                    binding_type=BindingType.PLATFORM_BINDING,
                    visibility_type=VisibilityScope.ALL_SYSTEMS,
                ).values_list("resource_id", flat=True)
            )
            visible_ids |= all_systems_ids

        scene_system_ids = set(
            SceneSystem.objects.filter(scene_id__in=scene_ids).exclude(system_id="").values_list("system_id", flat=True)
        )
        if scene_system_ids:
            specific_system_ids = set(
                ResourceBindingSystem.objects.filter(
                    system_id__in=scene_system_ids,
                    binding__resource_type=resource_type,
                    binding__binding_type=BindingType.PLATFORM_BINDING,
                    binding__visibility_type=VisibilityScope.SPECIFIC_SYSTEMS,
                ).values_list("binding__resource_id", flat=True)
            )
            visible_ids |= specific_system_ids

        return visible_ids

    @staticmethod
    def _get_system_visible_resource_ids(
        resource_type: BindingResourceType,
        system_ids: List[str],
        binding_type: Optional[BindingType] = None,
    ) -> Set[str]:
        """系统方向：获取对指定系统可见的资源 ID 集合。"""
        if binding_type == BindingType.SCENE_BINDING:
            return set()

        if not system_ids:
            return set()

        visible_ids: Set[str] = set(
            ResourceBinding.objects.filter(
                resource_type=resource_type,
                binding_type=BindingType.PLATFORM_BINDING,
                visibility_type=VisibilityScope.ALL_VISIBLE,
            ).values_list("resource_id", flat=True)
        )

        common_platform_ids = set(
            ResourceBinding.objects.filter(
                resource_type=resource_type,
                binding_type=BindingType.PLATFORM_BINDING,
                visibility_type__in=[VisibilityScope.ALL_SCENES, VisibilityScope.ALL_SYSTEMS],
            ).values_list("resource_id", flat=True)
        )
        visible_ids |= common_platform_ids

        specific_system_ids = set(
            ResourceBindingSystem.objects.filter(
                system_id__in=system_ids,
                binding__resource_type=resource_type,
                binding__binding_type=BindingType.PLATFORM_BINDING,
                binding__visibility_type=VisibilityScope.SPECIFIC_SYSTEMS,
            ).values_list("binding__resource_id", flat=True)
        )
        visible_ids |= specific_system_ids

        related_scene_ids = set(SceneSystem.objects.filter(system_id__in=system_ids).values_list("scene_id", flat=True))
        if related_scene_ids:
            specific_scene_ids = set(
                ResourceBindingScene.objects.filter(
                    scene_id__in=related_scene_ids,
                    binding__resource_type=resource_type,
                    binding__binding_type=BindingType.PLATFORM_BINDING,
                    binding__visibility_type=VisibilityScope.SPECIFIC_SCENES,
                ).values_list("binding__resource_id", flat=True)
            )
            visible_ids |= specific_scene_ids

        return visible_ids


# ---------------------------------------------------------------------------
# ScopeEntryPermission / ScopeEntryActionPermission — DRF 入口权限
# ---------------------------------------------------------------------------


class ScopeEntryPermission(BasePermission):
    """基础 scope 入口挂载器。

    职责仅包括：
    - 解析并校验 scope 参数
    - 创建 ScopePermission 实例
    - 将 scope 与 scope_permission 挂载到 request 上供后续 Resource 层复用

    不负责 action 鉴权，因此不会主动抛出 403。

    业务侧常见使用场景：
    - 列表页、筛选页、统计页这类"无权限时返回空结果"的接口
    - 需要让后续 serializer / resource / filter 通过 `request.scope_permission` 继续做数据过滤的接口

    使用示例：
        permission_classes = [ScopeEntryPermission]
    """

    def __init__(self, allowed_scope_types: Optional[List[ScopeType]] = None):
        """可选限制入口允许的 scope_type。"""
        self.allowed_scope_types = allowed_scope_types

    def _validate_allowed_scope_type(self, scope: ScopeContext) -> None:
        if not self.allowed_scope_types:
            return

        if scope.scope_type in self.allowed_scope_types:
            return

        allowed_values = [scope_type.value for scope_type in ScopeType if scope_type in self.allowed_scope_types]
        raise ValidationError(f"scope_type={scope.scope_type.value} 不支持，允许值：{', '.join(allowed_values)}")

    def has_permission(self, request, view) -> bool:
        scope = ScopeContext.from_request(request, view)
        self._validate_allowed_scope_type(scope)

        username = get_request_username()
        scope_perm = ScopePermission(username)

        request.scope_permission = scope_perm
        request.scope = scope
        return True


class ScopeEntryActionPermission(ScopeEntryPermission):
    """带 action 的严格入口鉴权。

    业务侧常见使用场景：
    - 创建、编辑、删除、启停等必须在入口阶段明确返回 403 的场景/系统接口
    - 进入场景管理页、系统详情页、策略配置页这类"没有权限就不应进入"的操作页

    说明：
    - 只接受 scene/system 方向的 action
    - 非 scene/system action 应直接使用普通 IAM 权限类，不应混入 scope 入口权限
    """

    def __init__(self, action: ActionMeta, allowed_scope_types: Optional[List[ScopeType]] = None):
        super().__init__(allowed_scope_types=allowed_scope_types)
        if not _is_scope_action(action):
            raise ValueError("ScopeEntryActionPermission 仅支持 scene/system 方向的 action")
        self.action = action

    def has_permission(self, request, view) -> bool:
        super().has_permission(request, view)
        scope = request.scope
        scope_perm = request.scope_permission
        return scope_perm.check_scope_entry(scope=scope, action=self.action, raise_exception=True)


# ---------------------------------------------------------------------------
# ScopeInstancePermission — DRF 资源实例级鉴权
# ---------------------------------------------------------------------------


class ScopeInstancePermission(InstancePermission):
    """资源实例级鉴权基类。

    各模块继承后配置 resource_type / resource_id_field。
    只服务于通过 ResourceBinding + visibility 管理可见性的平台级资源（panel、tool、处理套餐等）。

    业务侧常见使用场景：
    - 资源详情、编辑、删除、启停等"URL 上已经带了资源 ID"的实例接口
    - 不适合资源列表接口；列表接口应该先按 scope 过滤出可见资源集合，而不是对不存在的单个实例做鉴权

    使用示例：
        panel_scope_permission = ScopeInstancePermission(BindingResourceType.PANEL)
    """

    def __init__(self, resource_type: BindingResourceType, *args, **kwargs):
        self.resource_type = resource_type
        super().__init__(*args, **kwargs)

    def has_permission(self, request, view) -> bool:
        resource_id = self._get_instance_id(request, view)
        scope_perm = ScopePermission(get_request_username())
        return scope_perm.check_resource_permission(
            resource_type=self.resource_type,
            resource_id=str(resource_id),
            raise_exception=True,
        )
