from django.utils.translation import gettext_lazy

from apps.exceptions import CoreException


class ToolException(CoreException):
    MODULE_CODE = "02"


class BkVisionChartIdExistsError(ToolException):
    MESSAGE = gettext_lazy("BK Vision 图表 ID 已存在: {uid}")
    ERROR_CODE = "001"

    def __init__(self, uid, *args, **kwargs):
        self.MESSAGE = self.MESSAGE.format(uid=uid)
        super().__init__(*args, **kwargs)
