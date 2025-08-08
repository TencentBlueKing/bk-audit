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


class MetaException(CoreException):
    MODULE_CODE = CoreException.Modules.META


class NamespaceNotExists(MetaException):
    ERROR_CODE = "001"
    MESSAGE = gettext_lazy("Namespace不存在")


class BKAppNotExists(MetaException):
    ERROR_CODE = "002"
    MESSAGE = gettext_lazy("应用信息不存在")


class TagNameInValid(MetaException):
    ERROR_CODE = "003"
    STATUS_CODE = 400
    MESSAGE = gettext_lazy("Tag Name Invalid")


class SystemRoleMemberEmpty(MetaException):
    ERROR_CODE = "004"
    STATUS_CODE = 500
    MESSAGE = gettext_lazy("系统角色成员为空")


class SystemDiagnosisPushTemplateEmpty(MetaException):
    ERROR_CODE = "005"
    STATUS_CODE = 500
    MESSAGE = gettext_lazy("系统诊断推送模板为空")


class EnumMappingRelationInvalid(MetaException):
    ERROR_CODE = "006"
    STATUS_CODE = 500
    MESSAGE = gettext_lazy("枚举映射集合和关联对象没有从属关系")
