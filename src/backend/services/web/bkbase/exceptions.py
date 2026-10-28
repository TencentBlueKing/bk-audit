"""BKBase业务能力及资源归属的显式错误。"""
from django.utils.translation import gettext_lazy

from apps.exceptions import CoreException


class BKBaseOperationSuperseded(Exception):
    """异步Flow操作已被后续请求替代，调用方应放弃旧操作的推进。"""


class BKBaseException(CoreException):
    MODULE_CODE = CoreException.Modules.BKBASE


class BKBaseCapabilityNotReady(BKBaseException):
    """V4缺少已确认契约时阻止旧版调用泄漏。"""

    ERROR_CODE = "001"
    STATUS_CODE = 503
    MESSAGE = gettext_lazy("BKBase能力尚未就绪")

    def __init__(self, blocker_id, operation, **kwargs):
        self.blocker_id = blocker_id
        self.operation = operation
        super().__init__(message=f"{self.MESSAGE}: {operation} ({blocker_id})", **kwargs)


class BKBaseResourceMappingError(BKBaseException):
    ERROR_CODE = "002"
    MESSAGE = gettext_lazy("BKBase资源引用缺失或不唯一")


class BKBaseSharedResourceProtected(BKBaseException):
    ERROR_CODE = "003"
    MESSAGE = gettext_lazy("共享结果表的创建者清洗不能通过普通删源删除")


class BKBaseCapabilityDeprecated(BKBaseException):
    ERROR_CODE = "004"
    STATUS_CODE = 410
    MESSAGE = gettext_lazy("BKBase V4不再支持场景方案和模型审计")
