from django.db.models import TextChoices
from django.utils.translation import gettext_lazy

MYSQL_DEADLOCK_ERROR_CODE = 1213


class ExecutionMode(TextChoices):
    """消息处理器固定的执行方式。"""

    SYNC = "SYNC", gettext_lazy("同步")
    ASYNC = "ASYNC", gettext_lazy("异步")


class ExecutionStatus(TextChoices):
    """消息和附件的执行状态。"""

    PROCESSING = "PROCESSING", gettext_lazy("处理中")
    SUCCESS = "SUCCESS", gettext_lazy("成功")
    FAILED = "FAILED", gettext_lazy("失败")


class MessageErrorCode(TextChoices):
    """平台消息执行链路写入快照的稳定错误码。"""

    TASK_DISPATCH_FAILED = "TASK_DISPATCH_FAILED", gettext_lazy("任务投递失败")
    TASK_EXECUTION_FAILED = "TASK_EXECUTION_FAILED", gettext_lazy("任务执行失败")


class AttachmentErrorCode(TextChoices):
    """平台附件执行链路写入快照的稳定错误码。"""

    TASK_DISPATCH_FAILED = "TASK_DISPATCH_FAILED", gettext_lazy("附件任务投递失败")
    TASK_EXECUTION_FAILED = "TASK_EXECUTION_FAILED", gettext_lazy("附件任务执行失败")
    OUTPUT_VALIDATION_FAILED = "OUTPUT_VALIDATION_FAILED", gettext_lazy("附件产物格式错误")


class MessageType(TextChoices):
    """平台首期支持的消息类型。"""

    SYSTEM_SELECTION = "SYSTEM_SELECTION", gettext_lazy("系统选择")
    NATURAL_LANGUAGE_SEARCH = "NATURAL_LANGUAGE_SEARCH", gettext_lazy("自然语言检索")
    LOG_SEARCH = "LOG_SEARCH", gettext_lazy("日志检索")


class MessageHistoryDirection(TextChoices):
    """消息历史相对锚点的滚动方向。"""

    BEFORE = "BEFORE", gettext_lazy("锚点之前")
    AFTER = "AFTER", gettext_lazy("锚点之后")


class AttachmentType(TextChoices):
    """日志检索消息下可挂载的产物类型。"""

    FIELD_STATISTICS = "FIELD_STATISTICS", gettext_lazy("字段统计")
    AI_STATISTICS = "AI_STATISTICS", gettext_lazy("AI 统计")
    AI_ANALYSIS = "AI_ANALYSIS", gettext_lazy("AI 分析")


class FeedbackSourceType(TextChoices):
    """反馈支持关联的平台对象类型。"""

    MESSAGE = "MESSAGE", gettext_lazy("消息")
    ATTACHMENT = "ATTACHMENT", gettext_lazy("附件")


class FeedbackType(TextChoices):
    """用户对平台对象的反馈类型。"""

    LIKE = "LIKE", gettext_lazy("赞")
    DISLIKE = "DISLIKE", gettext_lazy("踩")


class SidebarNodeType(TextChoices):
    """会话侧栏中的节点类型。"""

    GROUP = "GROUP", gettext_lazy("分组")
    CONVERSATION = "CONVERSATION", gettext_lazy("会话")
