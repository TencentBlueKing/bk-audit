# -*- coding: utf-8 -*-
import os

from django.db.models import TextChoices
from django.utils.translation import gettext_lazy

from apps.permission.constants import IAMV4Role


class SceneStatus(TextChoices):
    """场景状态"""

    ENABLED = "enabled", gettext_lazy("启用")
    DISABLED = "disabled", gettext_lazy("停用")


class VisibilityScope(TextChoices):
    """可见范围类型"""

    ALL_VISIBLE = "all_visible", gettext_lazy("全部可见")
    ALL_SCENES = "all_scenes", gettext_lazy("全部场景")
    ALL_SYSTEMS = "all_systems", gettext_lazy("全系统")
    SPECIFIC_SCENES = "specific_scenes", gettext_lazy("指定场景")
    SPECIFIC_SYSTEMS = "specific_systems", gettext_lazy("指定系统")
    SCENES_AND_SYSTEMS = "scenes_and_systems", gettext_lazy("场景和系统")


class SceneRole(TextChoices):
    """场景角色"""

    MANAGER = "manager", gettext_lazy("场景管理员")
    USER = "user", gettext_lazy("场景使用者")


class ResourceScopeType(TextChoices):
    """资源归属级别"""

    PLATFORM = "platform", gettext_lazy("平台级")
    SCENE = "scene", gettext_lazy("场景级")


class BindingType(TextChoices):
    """资源绑定类型"""

    SCENE_BINDING = "scene_binding", gettext_lazy("场景级绑定")
    PLATFORM_BINDING = "platform_binding", gettext_lazy("平台级绑定")


class ResourceVisibilityType(TextChoices):
    """资源可见范围类型"""

    PANEL = "panel", gettext_lazy("报表")
    TOOL = "tool", gettext_lazy("工具")
    STRATEGY = "strategy", gettext_lazy("策略")
    LINK_TABLE = "link_table", gettext_lazy("联表")
    PROCESS_APPLICATION = "process_application", gettext_lazy("处理套餐")
    RISK_RULE = "risk_rule", gettext_lazy("处理规则")
    NOTICE_GROUP = "notice_group", gettext_lazy("通知组")
    RISK = "risk", gettext_lazy("风险")


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
    """报表状态"""

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


# 保留场景名称（迁移与运行时初始化共用）
DEFAULT_SCENE_NAME = "system_default"

# 场景ID自增起始值
SCENE_ID_START = 100001

# 场景详情 risk_count 对齐前端 ListRisk 默认传入的首次发现时间范围：近 6 个自然月。
SCENE_RISK_COUNT_DEFAULT_MONTHS = 6

# 场景详情 risk_count 统计活跃风险，状态口径与风险列表默认活跃筛选保持一致。
SCENE_RISK_COUNT_ACTIVE_DISPLAY_STATUSES = (
    "new",
    "await_deal",
    "processing",
    "for_approve",
    "auto_process",
)


# 全局配置：ITSM V4 审批流程编码
SCENE_PERMISSION_WORKFLOW_KEY = os.getenv("BKAPP_SCENE_PERMISSION_WORKFLOW_KEY", "")

# 周期任务 cron 分钟
SYNC_SCENE_PERMISSION_PERIODIC_TASK_MINUTE = os.getenv("BKAPP_SYNC_SCENE_PERMISSION_MINUTE", "*/60")

# 授权失败最大重试次数
SCENE_PERMISSION_GRANT_MAX_RETRY = int(os.getenv("BKAPP_SCENE_PERMISSION_GRANT_MAX_RETRY", "5"))

# 业务角色 → V4 role_id
SCENE_ROLE_TO_IAM_V4_ROLE = {
    SceneRole.MANAGER: IAMV4Role.SCENE_ADMIN,
    SceneRole.USER: IAMV4Role.SCENE_USER,
}


class ScenePermissionFormFields:
    """ITSM V4 流程表单字段标识。
    在 ITSM 创建审批流程时的表单模型：
    | 字段标识             | 字段类型       | 说明                         |
    |--------------------|--------------|------------------------------|
    | ticket__title      | 单行文本        | 标题（ITSM 内置，固定不可改）        |
    | applicant          | 单行文本        | 申请人                          |
    | applicant_department | 单行文本      | 申请人部门                        |
    | apply_time         | 单行文本        | 申请时间                          |
    | scene_name         | 单行文本        | 场景名称(场景ID)                    |
    | role               | 单行文本        | 申请角色                         |
    | reason             | 多行文本        | 申请理由（可选）                     |
    | approver           | 人员选择器(多选)    | 审批人（审批节点处理人取自此字段）      |
    """

    TITLE = "ticket__title"
    APPLICANT = "applicant"
    APPLICANT_DEPARTMENT = "applicant_department"
    APPLY_TIME = "apply_time"
    SCENE_NAME = "scene_name"
    ROLE = "role"
    REASON = "reason"
    APPROVER = "approver"


class ITSMV4TicketStatus(TextChoices):
    """ITSM V4 工单状态"""

    RUNNING = "running", gettext_lazy("处理中")
    FINISHED = "finished", gettext_lazy("已结束")
    TERMINATION = "termination", gettext_lazy("被终止")


class ApplicationStatus(TextChoices):
    """场景权限申请审批状态"""

    PENDING = "pending", gettext_lazy("待审批")
    APPROVED = "approved", gettext_lazy("审批通过")
    REJECTED = "rejected", gettext_lazy("已驳回")
    TERMINATED = "terminated", gettext_lazy("已终止")


class GrantStatus(TextChoices):
    """场景权限授权状态"""

    SUCCESS = "success", gettext_lazy("授权成功")
    FAILED = "failed", gettext_lazy("授权失败")
