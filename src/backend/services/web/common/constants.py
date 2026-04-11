from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy

# ---------------------------------------------------------------------------
# Scope 相关常量
# ---------------------------------------------------------------------------


class ScopeType(models.TextChoices):
    """scope 粒度类型（场景选择器四种粒度）"""

    CROSS_SCENE = "cross_scene", gettext_lazy("跨场景")
    CROSS_SYSTEM = "cross_system", gettext_lazy("跨系统")
    SCENE = "scene", gettext_lazy("单场景")
    SYSTEM = "system", gettext_lazy("单系统")


class ScopeQueryField(models.TextChoices):
    """scope 请求协议中的 query / body 参数名"""

    SCOPE_TYPE = "scope_type", gettext_lazy("scope 粒度类型")
    SCOPE_ID = "scope_id", gettext_lazy("scope 实例 ID")


class BindingResourceType(models.TextChoices):
    """需要通过 ResourceBinding + visibility 管控可见性的资源类型

    仅报表和工具走 scope 权限组件鉴权，其他资源类型不走此链路。
    """

    PANEL = "panel", gettext_lazy("报表")
    TOOL = "tool", gettext_lazy("工具")


# ---------------------------------------------------------------------------
# 其他业务常量
# ---------------------------------------------------------------------------


class CallerResourceType(models.TextChoices):
    RISK = "risk"
