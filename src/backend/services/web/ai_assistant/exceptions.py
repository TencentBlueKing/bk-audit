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
