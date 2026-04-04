# -*- coding: utf-8 -*-


def check_scene_permission(request, scene_id: int, require_role: str = "user") -> None:
    """
    校验当前用户是否拥有指定场景的访问权限

    :param request: DRF Request 对象
    :param scene_id: 场景 ID
    :param require_role: 所需最低角色，可选值：
        - "user": 场景使用者（只读）
        - "manager": 场景管理员（增删改）
        - "admin": SaaS 管理员
    :raises PermissionDenied: 无权限时抛出

    TODO: 由权限模块同学整合实现
    """
    pass
