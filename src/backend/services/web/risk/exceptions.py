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


class RiskException(CoreException):
    MODULE_CODE = CoreException.Modules.RISK


class ExportRiskNoPermission(RiskException):
    MESSAGE = gettext_lazy("您没有权限导出风险:{risk_ids}")
    STATUS_CODE = 400
    ERROR_CODE = "001"

    def __init__(self, risk_ids: str, *args, **kwargs):
        self.MESSAGE = self.MESSAGE.format(risk_ids=risk_ids)
        super().__init__(*args, **kwargs)


class RiskEventSubscriptionNotFound(RiskException):
    MESSAGE = gettext_lazy("订阅 Token 不存在或未启用")
    STATUS_CODE = 404
    ERROR_CODE = "002"
