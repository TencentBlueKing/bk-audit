# -*- coding: utf-8 -*-
from django.utils.translation import gettext_lazy

from apps.exceptions import CoreException


class SceneException(CoreException):
    MODULE_CODE = "08"


class SceneNotExist(SceneException):
    MESSAGE = gettext_lazy("场景不存在")
    ERROR_CODE = "001"


class SceneDisabled(SceneException):
    MESSAGE = gettext_lazy("场景已停用")
    ERROR_CODE = "002"


class SceneHasRelatedResources(SceneException):
    MESSAGE = gettext_lazy("场景存在关联资源，无法删除")
    ERROR_CODE = "003"


class PanelNotExist(SceneException):
    MESSAGE = gettext_lazy("报表不存在")
    ERROR_CODE = "004"


class PanelCannotDelete(SceneException):
    MESSAGE = gettext_lazy("已上架的报表不可删除")
    ERROR_CODE = "005"


class ToolNotExist(SceneException):
    MESSAGE = gettext_lazy("工具不存在")
    ERROR_CODE = "006"


class ToolCannotDelete(SceneException):
    MESSAGE = gettext_lazy("已上架的工具不可删除")
    ERROR_CODE = "007"
