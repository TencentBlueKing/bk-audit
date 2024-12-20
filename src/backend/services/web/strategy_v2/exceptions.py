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
from services.web.strategy_v2.constants import STRATEGY_SCHEDULE_TIME


class StrategyV2Exception(CoreException):
    MODULE_CODE = CoreException.Modules.ANALYZE


class ControlChangeError(StrategyV2Exception):
    STATUS_CODE = 400
    ERROR_CODE = "001"
    MESSAGE = gettext_lazy("Control Changed")


class StrategyPendingError(StrategyV2Exception):
    STATUS_CODE = 400
    ERROR_CODE = "002"
    MESSAGE = gettext_lazy("Strategy Pending")


class FieldsEmptyError(StrategyV2Exception):
    STATUS_CODE = 400
    ERROR_CODE = "003"
    MESSAGE = gettext_lazy("Empty Fields")


class StrategyStatusUnexpected(StrategyV2Exception):
    STATUS_CODE = 500
    ERROR_CODE = "004"
    MESSAGE = gettext_lazy("Strategy Status Unexpected")


class SchedulePeriodInvalid(StrategyV2Exception):
    STATUS_CODE = 500
    ERROR_CODE = "005"
    MESSAGE = gettext_lazy("调度周期超过允许的范围(%s天)") % STRATEGY_SCHEDULE_TIME


class LinkTableHasStrategy(StrategyV2Exception):
    MESSAGE = gettext_lazy("联表存在关联策略")
    ERROR_CODE = "006"
    STATUS_CODE = 400
