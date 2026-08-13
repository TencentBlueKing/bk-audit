from django.db.models import TextChoices
from django.utils.translation import gettext_lazy

DEFAULT_CONVERSATION_TITLE = "新对话"


class ExecutionStatus(TextChoices):
    """消息和附件的执行状态。"""

    PROCESSING = "PROCESSING", gettext_lazy("处理中")
    SUCCESS = "SUCCESS", gettext_lazy("成功")
    FAILED = "FAILED", gettext_lazy("失败")


class MessageType(TextChoices):
    """平台首期支持的消息类型。"""

    SYSTEM_SELECTION = "SYSTEM_SELECTION", gettext_lazy("系统选择")
    NATURAL_LANGUAGE_SEARCH = "NATURAL_LANGUAGE_SEARCH", gettext_lazy("自然语言检索")
    LOG_SEARCH = "LOG_SEARCH", gettext_lazy("日志检索")


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
