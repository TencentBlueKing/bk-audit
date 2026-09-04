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


class SystemWorkflowList(BKITSMV4):
    # 对应 itsm 的 GetServices（服务列表查询）
    name = gettext_lazy("V4-系统流程列表")
    method = "GET"
    action = "/api/v1/system_workflow/list/"


class Workflows(BKITSMV4):
    # 对应 itsm 的 GetServiceDetail（获取服务详情）
    name = gettext_lazy("V4-获取流程的启用版本详情")
    method = "GET"
    action = "/api/v1/workflows/"


class GetTicketDetail(BKITSMV4):
    # 对应 itsm 的 GetTicketStatus（单据状态查询）,itsm 的查询审批结果用这个查，返回字段有 approve_result
    name = gettext_lazy("V4-单据详情")
    method = "GET"
    action = "/api/v1/ticket/detail/"


class ApprovalTasks(BKITSMV4):
    # 对应 itsm 的 TicketApproveResult（查询审批结果），但是返回结果缺少必要的字段 approve_result，废弃
    name = gettext_lazy("V4-获取审批节点任务列表")
    method = "POST"
    action = "/api/v1/approval_tasks/"


class TicketHandle(BKITSMV4):
    # 对应 itsm 的 OperateTicket（操作单据）
    name = gettext_lazy("V4-操作单据")
    method = "POST"
    action = "/api/v1/ticket/handle/"


class FullTextSearch(BKITSMV4):
    name = gettext_lazy("V4-查订单列表")
    method = "POST"
    action = "/api/v1/ticket_search/full_text_search/"
