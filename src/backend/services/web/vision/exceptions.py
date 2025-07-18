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

from core.exceptions import CoreException


class VisionException(CoreException):
    MODULE_CODE = CoreException.Module.Vision


class VisionPermissionInvalid(VisionException):
    ERROR_CODE = "001"
    STATUS_CODE = 500
    MESSAGE = gettext_lazy("不支持的权限，请联系管理员")


class VisionHandlerInvalid(VisionException):
    ERROR_CODE = "002"
    STATUS_CODE = 500
    MESSAGE = gettext_lazy("不支持的VisionHandler:{handler}，请联系管理员")

    def __init__(self, handler: str, *args, **kwargs):
        self.MESSAGE = self.MESSAGE.format(handler=handler)
        super().__init__(*args, **kwargs)


class SingleSystemDiagnosisSystemParamsError(VisionException):
    ERROR_CODE = "003"
    STATUS_CODE = 500
    MESSAGE = gettext_lazy("单系统诊断系统参数错误")
