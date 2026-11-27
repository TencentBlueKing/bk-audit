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


class RedisRegistrationPending(BKBaseResourceMappingError):
    """BKBase 已受理 Redis 登记，正式资产尚不可见。"""

    def __init__(self, asset_name, **kwargs):
        self.asset_name = asset_name
        super().__init__(**kwargs)


class BKBaseSharedResourceProtected(BKBaseException):
    ERROR_CODE = "003"
    MESSAGE = gettext_lazy("共享结果表的创建者清洗不能通过普通删源删除")


class BKBaseCapabilityDeprecated(BKBaseException):
    ERROR_CODE = "004"
    STATUS_CODE = 410
    MESSAGE = gettext_lazy("BKBase V4不再支持场景方案和模型审计")


class BKBaseFlowOperationPending(BKBaseException):
    """同一正式 Flow 尚有未决写入，不能叠加相反目标、改图或重启。"""

    ERROR_CODE = "005"
    STATUS_CODE = 409
    MESSAGE = gettext_lazy("Flow存在未决操作，请先核实当前操作结果")


class BKBaseFlowWriteFailed(BKBaseException):
    """同步发送已结束但未成功取得回执，由用户显式重试。"""

    ERROR_CODE = "006"
    MESSAGE = gettext_lazy("Flow发送失败或受理结果未知，请重试")


class BKBaseReadTimeout(BKBaseException):
    """列表预算或单次HTTP超时，不返回未完整读取的权限或候选表。"""

    ERROR_CODE = "007"
    STATUS_CODE = 504
    MESSAGE = gettext_lazy("BKBase列表读取超时，请重试")
