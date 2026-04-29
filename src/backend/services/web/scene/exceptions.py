# -*- coding: utf-8 -*-
from typing import Any, Sequence, TypedDict

from django.utils.translation import gettext_lazy

from apps.exceptions import CoreException


class RelatedResourceDetail(TypedDict):
    resource_type: str
    resource_type_name: str
    resource_id: str


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

    def __init__(
        self,
        related_resources: Sequence[RelatedResourceDetail] | None = None,
        *args: object,
        **kwargs: Any,
    ):
        related_resources = list(related_resources or [])
        kwargs.setdefault("data", {"related_resources": related_resources})
        kwargs.setdefault("message", self.build_message(related_resources))
        super().__init__(*args, **kwargs)

    @classmethod
    def build_message(cls, related_resources: Sequence[RelatedResourceDetail]) -> str:
        if not related_resources:
            return str(cls.MESSAGE)
        details = [
            f"{resource['resource_type_name']}({resource['resource_id']})" for resource in related_resources[:10]
        ]
        if len(related_resources) > 10:
            details.append(f"等 {len(related_resources)} 个资源")
        return f"{cls.MESSAGE}，请先删除：{'; '.join(details)}"


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
