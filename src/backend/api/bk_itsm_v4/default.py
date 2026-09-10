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
import abc

from client_throttler import Throttler, ThrottlerConfig
from django.conf import settings
from django.utils.translation import gettext_lazy

from api.constants import APIProvider
from api.domains import BK_ITSM_V4_API_URL
from api.utils import get_endpoint
from core.bk_api_base import AuditBkApiResource


class BKITSMV4(AuditBkApiResource, abc.ABC):
    """ITSM V4 接口基类"""

    module_name = "bk_itsm_v4"
    platform_authorization = True

    @property
    def base_url(self):
        if self.use_multi_tenant_mode():
            return get_endpoint(settings.BK_CW_AITSM_APIGW_NAME, APIProvider.APIGW, stage="prod")
        return BK_ITSM_V4_API_URL

    def perform_request(self, validated_request_data):
        return Throttler(
            config=ThrottlerConfig(
                func=super().perform_request,
                key=f"{self.__module__}.{self.__class__.__name__}",
                rate=settings.ITSM_API_RATE_LIMIT,
            )
        )(validated_request_data)


class TicketCreate(BKITSMV4):
    """创建审批单据"""

    name = gettext_lazy("V4-创建审批单据")
    method = "POST"
    action = "/api/v1/ticket/create/"


class TicketLogs(BKITSMV4):
    """查询工单操作日志"""

    name = gettext_lazy("V4-查询工单操作日志")
    method = "GET"
    action = "/api/v1/ticket/logs/"
