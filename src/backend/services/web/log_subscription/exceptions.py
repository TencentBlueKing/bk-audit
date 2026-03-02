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


class LogSubscriptionException(CoreException):
    """日志订阅异常基类"""

    MODULE_CODE = CoreException.Modules.LOG_SUBSCRIPTION


class LogSubscriptionNotFound(LogSubscriptionException):
    """订阅配置不存在或未启用"""

    MESSAGE = gettext_lazy("订阅配置不存在或未启用")
    STATUS_CODE = 404
    ERROR_CODE = "001"


class DataSourceNotFound(LogSubscriptionException):
    """数据源不存在或未启用"""

    MESSAGE = gettext_lazy("数据源 {source_id} 不存在或未启用")
    STATUS_CODE = 404
    ERROR_CODE = "002"

    def __init__(self, source_id: str, *args, **kwargs):
        self.source_id = source_id
        message = self.MESSAGE.format(source_id=source_id)
        super().__init__(message=message, *args, **kwargs)


class DataSourceNotInSubscription(LogSubscriptionException):
    """数据源不在订阅配置中"""

    MESSAGE = gettext_lazy("数据源 {source_id} 不在当前订阅配置中")
    STATUS_CODE = 403
    ERROR_CODE = "003"

    def __init__(self, source_id: str, *args, **kwargs):
        self.source_id = source_id
        message = self.MESSAGE.format(source_id=source_id)
        super().__init__(message=message, *args, **kwargs)


class FieldNotAllowed(LogSubscriptionException):
    """请求字段不在数据源允许的字段范围内"""

    MESSAGE = gettext_lazy("请求字段 {fields} 不在数据源 {source_id} 允许的字段范围内，允许的字段: {allowed_fields}")
    STATUS_CODE = 400
    ERROR_CODE = "004"

    def __init__(self, fields: list, source_id: str, allowed_fields: list, *args, **kwargs):
        self.fields = fields
        self.source_id = source_id
        self.allowed_fields = allowed_fields
        message = self.MESSAGE.format(
            fields=", ".join(fields),
            source_id=source_id,
            allowed_fields=", ".join(allowed_fields),
        )
        super().__init__(message=message, *args, **kwargs)
