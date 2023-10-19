# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

from django.utils.translation import gettext_lazy

from apps.exceptions import CoreException


class BaseIAMError(CoreException):
    MODULE_CODE = CoreException.Modules.IAM
    MESSAGE = gettext_lazy("权限中心异常")


class ActionNotExistError(BaseIAMError):
    ERROR_CODE = "001"
    MESSAGE = gettext_lazy("动作ID不存在")


class ResourceNotExistError(BaseIAMError):
    ERROR_CODE = "002"
    MESSAGE = gettext_lazy("资源ID不存在")


class GetSystemInfoError(BaseIAMError):
    ERROR_CODE = "003"
    MESSAGE = gettext_lazy("获取系统信息错误")


class ResourceAttrTypeExists(BaseIAMError):
    ERROR_CODE = "004"
    MESSAGE = gettext_lazy("资源类型已存在")


class ResourceAttrNameExists(BaseIAMError):
    ERROR_CODE = "005"
    MESSAGE = gettext_lazy("资源属性名称已存在")


class ResourceAttrTypeNotExists(BaseIAMError):
    ERROR_CODE = "006"
    MESSAGE = gettext_lazy("资源类型{attr_type}不存在")

    def __init__(self, *args, attr_type, data=None, **kwargs):
        self.MESSAGE = self.MESSAGE.format(attr_type=attr_type)
        super().__init__(**kwargs)


class ResourceAttrTypeIsNotExists(BaseIAMError):
    ERROR_CODE = "007"
    MESSAGE = gettext_lazy("资源属性类型不能为空")


class ResourceAttrTypeConfuse(BaseIAMError):
    ERROR_CODE = "008"
    MESSAGE = gettext_lazy("同一鉴权仅支持一种资源类型")


class ActionSystemConfuse(BaseIAMError):
    ERROR_CODE = "009"
    MESSAGE = gettext_lazy("同一鉴权仅支持一个接入系统")
