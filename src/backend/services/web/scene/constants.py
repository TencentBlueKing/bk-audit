# -*- coding: utf-8 -*-
from django.db.models import TextChoices
from django.utils.translation import gettext_lazy


class SceneStatus(TextChoices):
    """场景状态"""

    ENABLED = "enabled", gettext_lazy("启用")
    DISABLED = "disabled", gettext_lazy("停用")


class VisibilityScope(TextChoices):
    """可见范围类型"""

    ALL_VISIBLE = "all_visible", gettext_lazy("全部可见")
    ALL_SCENES = "all_scenes", gettext_lazy("全部场景")
    SPECIFIC_SCENES = "specific_scenes", gettext_lazy("指定场景")
    SPECIFIC_SYSTEMS = "specific_systems", gettext_lazy("指定系统")


class SceneRole(TextChoices):
    """场景角色"""

    MANAGER = "manager", gettext_lazy("场景管理员")
    USER = "user", gettext_lazy("场景使用者")


class ResourceScopeType(TextChoices):
    """资源归属级别"""

    PLATFORM = "platform", gettext_lazy("平台级")
    SCENE = "scene", gettext_lazy("场景级")


class ResourceVisibilityType(TextChoices):
    """资源可见范围类型（报表/工具）"""

    PANEL = "panel", gettext_lazy("报表")
    TOOL = "tool", gettext_lazy("工具")


class PanelCategory(TextChoices):
    """报表分类"""

    SECURITY_OVERVIEW = "security_overview", gettext_lazy("安全总览")
    BEHAVIOR_ANALYSIS = "behavior_analysis", gettext_lazy("行为分析")
    DATA_SECURITY = "data_security", gettext_lazy("数据安全")
    COMPLIANCE_AUDIT = "compliance_audit", gettext_lazy("合规审计")
    ASSET_SECURITY = "asset_security", gettext_lazy("资产安全")
    OPERATION_EFFICIENCY = "operation_efficiency", gettext_lazy("运营效率")
    THREAT_INTELLIGENCE = "threat_intelligence", gettext_lazy("威胁情报")
    CLOUD_SECURITY = "cloud_security", gettext_lazy("云安全")


class PanelStatus(TextChoices):
    """报表状态（仅平台级）"""

    PUBLISHED = "published", gettext_lazy("已上架")
    UNPUBLISHED = "unpublished", gettext_lazy("未上架")


class PlatformToolType(TextChoices):
    """平台级工具类型"""

    QUERY = "query", gettext_lazy("查询类")
    ACTION = "action", gettext_lazy("处置类")
    ANALYSIS = "analysis", gettext_lazy("分析类")
    NOTIFICATION = "notification", gettext_lazy("通知类")


class SceneToolType(TextChoices):
    """场景级工具类型"""

    DATA_SEARCH = "data_search", gettext_lazy("数据查询")
    API = "api", gettext_lazy("API接口")
    BK_VISION = "bk_vision", gettext_lazy("BKVision图表")
    SMART_PAGE = "smart_page", gettext_lazy("智能页面")


# 场景ID自增起始值
SCENE_ID_START = 100001

# 默认场景名称（用于存量数据迁移）
DEFAULT_SCENE_NAME = gettext_lazy("默认场景")
