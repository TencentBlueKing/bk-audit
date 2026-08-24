from django.utils.translation import gettext_lazy

from apps.exceptions import CoreException


class AIAssistantException(CoreException):
    """AI 助手平台业务异常基类。"""

    MODULE_CODE = "08"


class UnsupportedMessageType(AIAssistantException):
    MESSAGE = gettext_lazy("不支持的消息类型")
    ERROR_CODE = "001"
    STATUS_CODE = 400


class MessageSnapshotValidationError(AIAssistantException):
    MESSAGE = gettext_lazy("消息数据格式错误")
    ERROR_CODE = "002"
    STATUS_CODE = 400


class InvalidParentMessage(AIAssistantException):
    MESSAGE = gettext_lazy("父消息无效")
    ERROR_CODE = "003"
    STATUS_CODE = 400


class StaleMessageTask(AIAssistantException):
    MESSAGE = gettext_lazy("消息任务已失效")
    ERROR_CODE = "004"


class MessageExecutionFailed(AIAssistantException):
    MESSAGE = gettext_lazy("消息执行失败，请稍后重试")
    ERROR_CODE = "005"


class ConversationNotFound(AIAssistantException):
    MESSAGE = gettext_lazy("会话不存在")
    ERROR_CODE = "006"
    STATUS_CODE = 404


class ConversationGroupNotFound(AIAssistantException):
    MESSAGE = gettext_lazy("会话分组不存在")
    ERROR_CODE = "007"
    STATUS_CODE = 404


class SidebarNodeNotFound(AIAssistantException):
    MESSAGE = gettext_lazy("侧栏节点不存在")
    ERROR_CODE = "008"
    STATUS_CODE = 404


class InvalidSidebarContainer(AIAssistantException):
    MESSAGE = gettext_lazy("侧栏目标容器无效")
    ERROR_CODE = "009"
    STATUS_CODE = 400


class InvalidSidebarAnchor(AIAssistantException):
    MESSAGE = gettext_lazy("侧栏移动锚点无效")
    ERROR_CODE = "010"
    STATUS_CODE = 400


class SidebarNodeNotMovable(AIAssistantException):
    MESSAGE = gettext_lazy("当前侧栏节点不可移动")
    ERROR_CODE = "011"
    STATUS_CODE = 400


class SidebarNodeNotPinnable(AIAssistantException):
    MESSAGE = gettext_lazy("当前侧栏节点不可置顶")
    ERROR_CODE = "012"
    STATUS_CODE = 400


class InvalidInitialMessage(AIAssistantException):
    """会话携带的初始化消息不满足平台约束。"""

    MESSAGE = gettext_lazy("会话初始化消息无效")
    ERROR_CODE = "013"
    STATUS_CODE = 400


class MessageNotFound(AIAssistantException):
    MESSAGE = gettext_lazy("消息不存在")
    ERROR_CODE = "014"
    STATUS_CODE = 404


class InvalidMessageAnchor(AIAssistantException):
    MESSAGE = gettext_lazy("消息历史锚点无效")
    ERROR_CODE = "015"
    STATUS_CODE = 400


class UnsupportedAttachmentType(AIAssistantException):
    MESSAGE = gettext_lazy("不支持的附件类型")
    ERROR_CODE = "016"
    STATUS_CODE = 400


class AttachmentSnapshotValidationError(AIAssistantException):
    MESSAGE = gettext_lazy("附件数据格式错误")
    ERROR_CODE = "017"
    STATUS_CODE = 400


class InvalidAttachmentSource(AIAssistantException):
    MESSAGE = gettext_lazy("附件来源无效")
    ERROR_CODE = "018"
    STATUS_CODE = 400


class AttachmentNotFound(AIAssistantException):
    MESSAGE = gettext_lazy("附件不存在")
    ERROR_CODE = "019"
    STATUS_CODE = 404


class StaleAttachmentTask(AIAssistantException):
    MESSAGE = gettext_lazy("附件任务已失效")
    ERROR_CODE = "020"


class AttachmentExecutionFailed(AIAssistantException):
    MESSAGE = gettext_lazy("附件执行失败，请稍后重试")
    ERROR_CODE = "021"


class AttachmentNotEditable(AIAssistantException):
    MESSAGE = gettext_lazy("当前附件不可编辑")
    ERROR_CODE = "022"
    STATUS_CODE = 400


class InvalidAttachmentState(AIAssistantException):
    MESSAGE = gettext_lazy("附件状态无效")
    ERROR_CODE = "023"
    STATUS_CODE = 400


class AttachmentExportNotSupported(AIAssistantException):
    """附件类型未声明请求的导出格式。"""

    MESSAGE = gettext_lazy("当前附件不支持该导出格式")
    ERROR_CODE = "030"
    STATUS_CODE = 400


class AttachmentContentTooLarge(AIAssistantException):
    """Markdown 原文超过同步导出允许的字节上限。"""

    MESSAGE = gettext_lazy("附件内容过大")
    ERROR_CODE = "031"
    STATUS_CODE = 400


class AttachmentExportFailed(AIAssistantException):
    """导出器内部失败时返回的稳定公开错误。"""

    MESSAGE = gettext_lazy("附件导出失败，请稍后重试")
    ERROR_CODE = "032"
    STATUS_CODE = 500


class AttachmentOutputValidationError(AIAssistantException):
    MESSAGE = gettext_lazy("附件产物格式错误")
    ERROR_CODE = "024"


class InvalidAttachmentPreparation(AIAssistantException):
    MESSAGE = gettext_lazy("附件准备结果无效")
    ERROR_CODE = "025"
    STATUS_CODE = 400


class InvalidMessageState(AIAssistantException):
    MESSAGE = gettext_lazy("消息状态无效")
    ERROR_CODE = "026"
    STATUS_CODE = 400


class FeedbackSourceNotFound(AIAssistantException):
    MESSAGE = gettext_lazy("反馈来源不存在")
    ERROR_CODE = "027"
    STATUS_CODE = 404


class FeedbackNotSupported(AIAssistantException):
    MESSAGE = gettext_lazy("当前对象不支持反馈")
    ERROR_CODE = "028"
    STATUS_CODE = 400


class InvalidFeedbackSourceState(AIAssistantException):
    MESSAGE = gettext_lazy("当前对象状态不支持反馈")
    ERROR_CODE = "029"
    STATUS_CODE = 400


class SystemSelectionRequired(AIAssistantException):
    """当前会话不存在可绑定的成功系统选择消息（父消息由后端解析绑定）。"""

    MESSAGE = gettext_lazy("当前会话尚未选择系统，请先选择检索系统")
    ERROR_CODE = "033"
    STATUS_CODE = 400


class InvalidMessageSnapshot(AIAssistantException):
    """父消息快照缺失或无法恢复执行所需的字段上下文。"""

    MESSAGE = gettext_lazy("父消息快照无效，请重新选择系统后重试")
    ERROR_CODE = "034"
    STATUS_CODE = 400


class LogExportFailed(AIAssistantException):
    """日志导出（预览/全量）执行失败。"""

    MESSAGE = gettext_lazy("日志导出失败，请稍后重试")
    ERROR_CODE = "035"
    STATUS_CODE = 500


class LogExportPermissionDenied(AIAssistantException):
    """当前用户无目标系统的日志导出权限。"""

    MESSAGE = gettext_lazy("无目标系统的日志导出权限")
    ERROR_CODE = "036"
    STATUS_CODE = 403
