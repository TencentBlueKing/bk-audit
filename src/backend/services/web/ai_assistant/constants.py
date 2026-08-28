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


class ExecutionObjectType(TextChoices):
    """平台异步执行与可观测性使用的对象类型。"""

    MESSAGE = "MESSAGE", gettext_lazy("消息")
    ATTACHMENT = "ATTACHMENT", gettext_lazy("附件")


class MessageErrorCode(TextChoices):
    """平台消息执行链路写入快照的稳定错误码。"""

    TASK_DISPATCH_FAILED = "TASK_DISPATCH_FAILED", gettext_lazy("任务投递失败")
    TASK_EXECUTION_FAILED = "TASK_EXECUTION_FAILED", gettext_lazy("任务执行失败")
    TASK_EXECUTION_TIMEOUT = "TASK_EXECUTION_TIMEOUT", gettext_lazy("任务执行超时")


class AttachmentErrorCode(TextChoices):
    """平台附件执行链路写入快照的稳定错误码。"""

    TASK_DISPATCH_FAILED = "TASK_DISPATCH_FAILED", gettext_lazy("附件任务投递失败")
    TASK_EXECUTION_FAILED = "TASK_EXECUTION_FAILED", gettext_lazy("附件任务执行失败")
    TASK_EXECUTION_TIMEOUT = "TASK_EXECUTION_TIMEOUT", gettext_lazy("附件任务执行超时")
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


class AttachmentExportFormat(TextChoices):
    """Attachment Handler 可声明的后端导出格式。"""

    MARKDOWN = "MARKDOWN", gettext_lazy("Markdown")
    PDF = "PDF", gettext_lazy("PDF")


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


class StreamArchiveStatus(TextChoices):
    """MySQL 事件归档相对实时流的完整性；仅影响 UI 展示，不影响最终产物。"""

    COMPLETE = "COMPLETE", gettext_lazy("完整")
    DEGRADED = "DEGRADED", gettext_lazy("降级")
    TRUNCATED = "TRUNCATED", gettext_lazy("已截断")


class PlatformStreamEvent(TextChoices):
    """平台保留的流控制事件名称；前端据此切换或结束渲染。"""

    STREAM_RESET = "platform.stream_reset", gettext_lazy("流已切换")
    STREAM_END = "platform.stream_end", gettext_lazy("流已结束")


# AI 标题生成（共用智能体 ALS_TITLE_SUM，System Prompt 平台侧统一配置）：
# 统一 User Prompt 模板（后端侧配置，可经 BKAPP_AI_TITLE_USER_PROMPT_TEMPLATE 覆盖）
AI_TITLE_USER_PROMPT_TEMPLATE = (
    "【场景】{module_name}——{module_description}\n"
    "【任务】请根据【用户输入】，为这次{module_object}生成一个简短准确的标题："
    "不超过{max_length}个字，概括用户的核心意图，直接输出标题文本，不要附加任何其他内容\n"
    '【用户输入】"{input_text}"'
)
# 模块配置（新模块接入 = 加一个条目，模板不动）
AI_TITLE_MODULE_CONFIGS = {
    "log_search_conversation": {
        "module_name": "AI自然语言日志检索",
        "module_description": "用户在会话中用自然语言描述检索意图进行日志检索",
        "module_object": "会话",
    },
}
# 会话标题默认最大长度（BKAPP_AI_CONVERSATION_TITLE_MAX_LENGTH 覆盖）
AI_CONVERSATION_TITLE_MAX_LENGTH = 20
