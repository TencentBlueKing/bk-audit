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
