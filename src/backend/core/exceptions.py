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

import json

from blueapps.core.exceptions import BlueException
from django.conf import settings
from django.utils.translation import gettext, gettext_lazy


class ApiError(BlueException):
    pass


class ValidationError(BlueException):
    MESSAGE = gettext_lazy("参数验证失败")
    ERROR_CODE = "001"

    def __init__(self, *args, data=None, **kwargs):
        if args:
            custom_message = args[0]
            if isinstance(custom_message, tuple):
                super(ValidationError, self).__init__(custom_message[1], data=custom_message[0], **kwargs)
            else:
                super(ValidationError, self).__init__(custom_message, **kwargs)
        else:
            super(ValidationError, self).__init__(**kwargs)


class ApiResultError(ApiError):
    MESSAGE = gettext_lazy("远程服务请求结果异常")
    ERROR_CODE = "002"


class ComponentCallError(BlueException):
    MESSAGE = gettext_lazy("组件调用异常")
    ERROR_CODE = "003"


class LocalError(BlueException):
    MESSAGE = gettext_lazy("组件调用异常")
    ERROR_CODE = "004"


class LanguageDoseNotSupported(BlueException):
    MESSAGE = gettext_lazy("语言不支持")
    ERROR_CODE = "005"


class LockError(BlueException):
    MESSAGE = gettext_lazy("获取锁失败")
    ERROR_CODE = "006"


class InstanceNotFound(BlueException):
    MESSAGE = gettext_lazy("资源实例获取失败")
    ERROR_CODE = "007"


class ApiRequestError(ApiError):
    MESSAGE = gettext_lazy("服务不稳定，请检查组件健康状况")
    ERROR_CODE = "015"


class PermissionException(BlueException):
    ERROR_CODE = "403"
    MESSAGE = gettext_lazy("权限校验不通过")
    STATUS_CODE = 403

    def __init__(self, action_name, permission, apply_url=settings.BK_IAM_SAAS_HOST):
        message = gettext("当前用户无 [%(action_name)s] 权限") % {"action_name": action_name}
        data = {"permission": permission, "apply_url": apply_url}
        super(PermissionException, self).__init__(message, data=json.dumps(data), code="9900403")


class AppPermissionDenied(BlueException):
    ERROR_CODE = "403"
    MESSAGE = gettext_lazy("应用身份校验失败")
    STATUS_CODE = 403


class RiskStatusInvalid(BlueException):
    ERROR_CODE = "400"
    MESSAGE = gettext_lazy("风险状态异常 (%s)")
    STATUS_CODE = 400


class RiskRuleNotMatch(BlueException):
    ERROR_CODE = "500"
    MESSAGE = gettext_lazy("无命中的风险处理规则，风险ID %s")
    STATUS_CODE = 500


class RiskRuleInUse(BlueException):
    ERROR_CODE = "400"
    MESSAGE = gettext_lazy("该处理规则有未关单风险")
    STATUS_CODE = 400


class CoreException(BlueException):
    class Module:
        Vision = "100"
