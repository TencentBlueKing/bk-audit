"""AI 助手资源 Scope 的归一化与查询可见范围。

该模块复用平台 ScopeContext 和 ScopePermission，不查询 AI 助手业务对象。
Conversation 与 ConversationGroup 保存的始终是单一 concrete scope。
具体 Scope 的访问权限由 HTTP 入口检查；本层只构造过滤范围。
cross scope 解析为当前用户可见的具体 ID 集合，供集合查询使用。
"""

from dataclasses import dataclass
from typing import Sequence

from apps.permission.handlers.actions.action import ActionEnum
from core.exceptions import ValidationError
from services.web.common.constants import ScopeType
from services.web.common.scope_permission import ScopeContext, ScopePermission


@dataclass(frozen=True, slots=True)
class ScopeVisibility:
    """描述查询方向、用户可见的具体 ID 及其是否为聚合查询。"""

    scope_type: ScopeType
    scope_ids: Sequence[str]
    is_cross: bool


def normalize_concrete_scope(*, scope_type: str, scope_id: str | None) -> ScopeContext:
    """校验 AI 资源的具体归属，并规范化场景 ID。"""

    scope = ScopeContext(scope_type=scope_type, scope_id=scope_id)
    if scope.is_cross_scope:
        raise ValidationError("会话资源 scope 必须是具体场景或具体系统")
    if scope.scope_type == ScopeType.SCENE:
        return ScopeContext(scope_type=scope.scope_type, scope_id=str(int(scope.scope_id)))
    if not scope.scope_id.strip():
        raise ValidationError("系统 scope_id 不能为空")
    return scope


def resolve_scope_visibility(*, permission: ScopePermission, scope_type: str, scope_id: str | None) -> ScopeVisibility:
    """具体范围复用入口鉴权，cross 范围枚举授权 ID 后供 SQL 过滤。"""

    scope = ScopeContext(scope_type=scope_type, scope_id=scope_id)
    if not scope.is_cross_scope:
        scope = normalize_concrete_scope(scope_type=scope.scope_type, scope_id=scope.scope_id)
        return ScopeVisibility(scope.scope_type, (scope.scope_id,), False)

    if scope.is_scene_scope:
        scope_ids = permission.get_scene_ids(scope, ActionEnum.VIEW_SCENE)
        concrete_type = ScopeType.SCENE
    else:
        scope_ids = permission.get_system_ids(scope, ActionEnum.VIEW_SYSTEM)
        concrete_type = ScopeType.SYSTEM

    return ScopeVisibility(
        scope_type=concrete_type,
        scope_ids=tuple(str(scope_id) for scope_id in scope_ids),
        is_cross=scope.is_cross_scope,
    )
