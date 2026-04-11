# -*- coding: utf-8 -*-
"""
Scope 权限组件

提供统一的 scope 解析、入口校验、资源级校验、资源筛选能力。
业务模块两类权限需求均通过本文件组件承接：
1. ScopeEntryPermission  —— ViewSet 入口鉴权（DRF BasePermission）
2. ScopeInstancePermission —— 资源实例级鉴权（DRF BasePermission）
3. ScopePermission —— 通用 scope 服务类（业务主调用方式）

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from rest_framework.permissions import BasePermission

from apps.meta.converter import SystemDjangoQuerySetConverter
from apps.meta.models import System
from apps.permission.handlers.actions import ActionMeta
from apps.permission.handlers.actions.action import ActionEnum
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

    协议约束：
    - cross_scene / cross_system：scope_id 为空
    - scene / system：scope_id 必填
    """

    scope_type: ScopeType
    scope_id: Optional[str] = None

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
        """统一解析并校验 scope 协议

        兼容 DRF Request（query_params）和 Django WSGIRequest（GET）。
        优先从 query_params/GET 获取，再从 request.data 获取。
        """
        params = getattr(request, "query_params", None) or getattr(request, "GET", {})
        data = getattr(request, "data", {})

        scope_type = params.get(ScopeQueryField.SCOPE_TYPE) or data.get(ScopeQueryField.SCOPE_TYPE)
        scope_id = params.get(ScopeQueryField.SCOPE_ID) or data.get(ScopeQueryField.SCOPE_ID)

        if not scope_type:
            raise ValidationError(f"{ScopeQueryField.SCOPE_TYPE} 为必传参数")

        if scope_type not in ScopeType.values:
            raise ValidationError(f"{ScopeQueryField.SCOPE_TYPE} 不合法，可选值：{', '.join(ScopeType.values)}")

        # 转为枚举
        scope_type = ScopeType(scope_type)

        # 协议约束校验
        if scope_type in {ScopeType.SCENE, ScopeType.SYSTEM}:
            if not scope_id:
                raise ValidationError(f"{ScopeQueryField.SCOPE_TYPE}={scope_type} 时 {ScopeQueryField.SCOPE_ID} 为必传参数")
        else:
            # cross_scene / cross_system 不需要 scope_id
            scope_id = None

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
    # 平台管理员识别
    # ------------------------------------------------------------------

    @property
    def is_platform_admin(self) -> bool:
        """缓存 manage_platform IAM 判断结果，仅用于识别平台管理员身份"""
        if self._is_platform_admin is None:
            self._is_platform_admin = self.permission.is_allowed(
                action=ActionEnum.MANAGE_PLATFORM, resources=[], raise_exception=False
            )
        return self._is_platform_admin

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

        只要 action 的 related_resource_types 包含 scene 或 system 即可走此方法。

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
        binding = ResourceBinding.objects.filter(
            resource_type=resource_type,
            resource_id=str(resource_id),
        ).first()
        if not binding:
            return False

        # 短路：all_visible 直接通过
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

        结果缓存在请求级 _scene_ids_cache 中。
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

        结果缓存在请求级 _system_ids_cache 中。
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
        """统一返回当前 scope 下可访问的系统 ID 列表（便捷方法）。

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
    ) -> Set[str]:
        """返回当前用户在指定 scope 下可消费的资源 ID 集合。

        内部逻辑：
        - scene/cross_scene: 按 VIEW_SCENE 场景范围过滤
        - system/cross_system: 按 VIEW_SYSTEM 系统范围过滤，只返回该系统被授权的资源

        注意：平台级绑定的可见性计算较复杂，此处仅处理直接匹配的情况。
        如果业务侧有更复杂的筛选逻辑，建议在业务层调用 get_scene_ids / get_system_ids
        自行组装查询条件。
        """
        visible_ids: Set[str] = set()

        if scope.is_scene_scope:
            scene_ids = self.get_scene_ids(scope, ActionEnum.VIEW_SCENE)
            if not scene_ids:
                return visible_ids
            visible_ids |= self._get_scene_visible_resource_ids(resource_type, scene_ids)

        elif scope.is_system_scope:
            system_ids = self.get_system_ids(scope, ActionEnum.VIEW_SYSTEM)
            if not system_ids:
                return visible_ids
            visible_ids |= self._get_system_visible_resource_ids(resource_type, system_ids)

        return visible_ids

    # ------------------------------------------------------------------
    # get_resource_ids 内部拆分方法（便于业务侧按需组合或覆写）
    # ------------------------------------------------------------------

    @staticmethod
    def _get_scene_visible_resource_ids(
        resource_type: BindingResourceType,
        scene_ids: List[int],
    ) -> Set[str]:
        """场景方向：获取对指定场景可见的资源 ID 集合

        包含：
        1. 场景级绑定（SCENE_BINDING）的资源
        2. 平台级绑定（PLATFORM_BINDING）中 all_visible / all_scenes / specific_scenes 匹配的资源
        """
        visible_ids: Set[str] = set()

        # 1. 场景级绑定资源
        scene_binding_ids = set(
            ResourceBindingScene.objects.filter(
                scene_id__in=scene_ids,
                binding__resource_type=resource_type,
            ).values_list("binding__resource_id", flat=True)
        )
        visible_ids |= scene_binding_ids

        # 2. 平台级绑定：all_visible + all_scenes
        always_visible_ids = set(
            ResourceBinding.objects.filter(
                resource_type=resource_type,
                binding_type=BindingType.PLATFORM_BINDING,
                visibility_type__in=[VisibilityScope.ALL_VISIBLE, VisibilityScope.ALL_SCENES],
            ).values_list("resource_id", flat=True)
        )
        visible_ids |= always_visible_ids

        # 3. 平台级绑定：specific_scenes 匹配
        specific_scene_ids = set(
            ResourceBindingScene.objects.filter(
                scene_id__in=scene_ids,
                binding__resource_type=resource_type,
                binding__binding_type=BindingType.PLATFORM_BINDING,
                binding__visibility_type=VisibilityScope.SPECIFIC_SCENES,
            ).values_list("binding__resource_id", flat=True)
        )
        visible_ids |= specific_scene_ids

        return visible_ids

    @staticmethod
    def _get_system_visible_resource_ids(
        resource_type: BindingResourceType,
        system_ids: List[str],
    ) -> Set[str]:
        """系统方向：获取对指定系统可见的资源 ID 集合

        指定系统 → 只返回这些系统被直接授权的资源：
        1. all_visible 对所有人可见
        2. specific_systems 且系统在列表中
        """
        visible_ids: Set[str] = set()

        # 1. all_visible
        all_visible_ids = set(
            ResourceBinding.objects.filter(
                resource_type=resource_type,
                binding_type=BindingType.PLATFORM_BINDING,
                visibility_type=VisibilityScope.ALL_VISIBLE,
            ).values_list("resource_id", flat=True)
        )
        visible_ids |= all_visible_ids

        # 2. specific_systems 匹配
        from services.web.scene.models import ResourceBindingSystem

        specific_system_ids = set(
            ResourceBindingSystem.objects.filter(
                system_id__in=system_ids,
                binding__resource_type=resource_type,
                binding__binding_type=BindingType.PLATFORM_BINDING,
                binding__visibility_type=VisibilityScope.SPECIFIC_SYSTEMS,
            ).values_list("binding__resource_id", flat=True)
        )
        visible_ids |= specific_system_ids

        return visible_ids


# ---------------------------------------------------------------------------
# ScopeEntryPermission — DRF 入口鉴权
# ---------------------------------------------------------------------------


class ScopeEntryPermission(BasePermission):
    """ViewSet 入口鉴权

    设计：
    - action 的 related_resource_types 包含 scene 或 system → 走 check_scope_entry
    - 其他 action（如 MANAGE_PLATFORM 等非 scope action）→ 直接走 IAM

    入口不限制 scope_type，由数据筛选层（get_scene_ids / get_system_ids）决定返回什么。
    scope 方向不匹配时数据筛选返回空集合。

    使用示例：
        permission_classes = [ScopeEntryPermission(action=ActionEnum.VIEW_SCENE)]
    """

    def __init__(self, action: ActionMeta):
        self.action = action

    def has_permission(self, request, view) -> bool:
        scope = ScopeContext.from_request(request, view)

        username = get_request_username()
        scope_perm = ScopePermission(username)

        # 挂到 request 上供 Resource 层复用
        request.scope_permission = scope_perm
        request.scope = scope

        # action 校验路由
        if _is_scope_action(self.action):
            # action 关联 scene/system → 走 check_scope_entry
            return scope_perm.check_scope_entry(scope=scope, action=self.action, raise_exception=True)
        else:
            # 非 scope action → 直接走 IAM
            return self._check_business_action(scope, scope_perm)

    def _check_business_action(self, scope: ScopeContext, scope_perm: ScopePermission) -> bool:
        """业务 action 直接走 IAM，不经过 check_scope_entry"""
        if scope.is_cross_scope:
            # 聚合模式：宽松策略
            result = scope_perm.permission.has_action_any_permission(self.action)
            if not result:
                apply_data, apply_url = scope_perm.permission.get_apply_data([self.action])
                raise PermissionException(
                    action_name=self.action.name,
                    apply_url=apply_url,
                    permission=apply_data,
                )
            return True

        # 单实例模式：构造资源实例走 IAM is_allowed
        if scope.scope_type == ScopeType.SCENE:
            resource = ResourceEnum.SCENE.create_instance(scope.scope_id)
        elif scope.scope_type == ScopeType.SYSTEM:
            resource = ResourceEnum.SYSTEM.create_instance(scope.scope_id)
        else:
            return False

        return scope_perm.permission.is_allowed(self.action, [resource], raise_exception=True)


# ---------------------------------------------------------------------------
# ScopeInstancePermission — DRF 资源实例级鉴权
# ---------------------------------------------------------------------------


class ScopeInstancePermission(BasePermission):
    """资源实例级鉴权基类

    各模块继承后配置 resource_type / resource_id_field。
    只服务于通过 ResourceBinding + visibility 管理可见性的平台级资源（panel、tool）。

    使用示例：
        class PanelScopePermission(ScopeInstancePermission):
            resource_type = BindingResourceType.PANEL
            resource_id_field = "pk"
    """

    resource_type: BindingResourceType = BindingResourceType.PANEL
    resource_id_field: str = "pk"

    def has_permission(self, request, view) -> bool:
        resource_id = self._get_resource_id(request, view)
        if not resource_id:
            return True  # 列表接口不走资源级校验

        # 复用 request 上已有的 ScopePermission 实例
        scope_perm = getattr(request, "scope_permission", None)
        if scope_perm is None:
            username = get_request_username()
            scope_perm = ScopePermission(username)

        return scope_perm.check_resource_permission(
            resource_type=self.resource_type,
            resource_id=str(resource_id),
            raise_exception=True,
        )

    def _get_resource_id(self, request, view):
        """从 view kwargs 提取资源 ID"""
        lookup_field = self.resource_id_field
        return view.kwargs.get(lookup_field)
