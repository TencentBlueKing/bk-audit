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

import uuid
from unittest import mock

from bk_resource import resource
from bk_resource.settings import bk_resource_settings

from apps.itsm.constants import TicketStatus
from services.web.risk.constants import RiskDisplayStatus, RiskStatus
from services.web.risk.handlers.ticket import ForApprove, NewRisk
from tests.test_risk.test_tickets.base import RiskContext, RuleContext, TicketTest
from tests.test_risk.test_tickets.constants import (
    APPROVE_SERVICE_INFO,
    APPROVE_TICKET_DETAIL,
    APPROVE_TICKET_STATUS,
    CUSTOM_AUTO_PROCESS_PARAMS,
)


class ForApproveTest(TicketTest):
    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_itsm.ticket_approve_result",
        mock.Mock(return_value=[APPROVE_TICKET_STATUS]),
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_itsm.get_service_detail", mock.Mock(return_value=APPROVE_SERVICE_INFO)
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_itsm.create_ticket", mock.Mock(return_value=APPROVE_TICKET_DETAIL)
    )
    @mock.patch(
        "services.web.risk.resources.risk.get_request_username",
        mock.Mock(return_value=bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME),
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.auth_current_operator", mock.Mock(return_value=None)
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.notice_current_operator", mock.Mock(return_value=None)
    )
    def test_custom_approve(self):
        """
        测试人工发起审批
        关键验证：指定套餐、状态
        """

        with RuleContext() as (pa, _):
            with RiskContext() as risk:
                # 执行
                pa_config = {**CUSTOM_AUTO_PROCESS_PARAMS, "pa_id": pa.id}
                resource.risk.custom_auto_process(risk_id=risk.risk_id, **pa_config)
                risk.refresh_from_db()
                # 检测风险状态
                self.assertEquals(risk.status, RiskStatus.FOR_APPROVE)
                # display_status 同步为 FOR_APPROVE
                self.assertEquals(risk.display_status, RiskDisplayStatus.FOR_APPROVE)
                # 检测单据是否符合预期
                self.assertEquals(risk.last_history.extra["pa_config"], pa_config)

    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_itsm.ticket_approve_result",
        mock.Mock(return_value=[APPROVE_TICKET_STATUS]),
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_itsm.get_service_detail", mock.Mock(return_value=APPROVE_SERVICE_INFO)
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_itsm.create_ticket", mock.Mock(return_value=APPROVE_TICKET_DETAIL)
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.auth_current_operator", mock.Mock(return_value=None)
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.notice_current_operator", mock.Mock(return_value=None)
    )
    def test_create_approve(self):
        """
        测试自动发起审批
        关键验证：状态、单据
        """

        with RuleContext() as (_, _):
            with RiskContext() as risk:
                # 初始化
                operator = uuid.uuid1().hex
                NewRisk(risk_id=risk.risk_id, operator=operator).run()
                risk.refresh_from_db()
                # 检测风险状态
                self.assertEquals(risk.status, RiskStatus.FOR_APPROVE)
                # display_status 同步为 FOR_APPROVE
                self.assertEquals(risk.display_status, RiskDisplayStatus.FOR_APPROVE)
                # 执行审批节点
                ForApprove(risk_id=risk.risk_id, operator=operator).run()
                risk.refresh_from_db()
                # 检测单据号一致
                self.assertEquals(risk.last_history.process_result["ticket"]["sn"], APPROVE_TICKET_DETAIL["sn"])
                with mock.patch(
                    "services.web.risk.handlers.ticket.api.bk_itsm.ticket_approve_result",
                    mock.Mock(return_value=[{**APPROVE_TICKET_STATUS, "current_status": TicketStatus.FINISHED.value}]),
                ):
                    # 再次执行审批节点
                    ForApprove(risk_id=risk.risk_id, operator=operator).run()
                risk.refresh_from_db()
                # 检测风险状态
                self.assertEquals(risk.status, RiskStatus.AUTO_PROCESS)
                # 审批通过后 display_status 同步为 AUTO_PROCESS
                self.assertEquals(risk.display_status, RiskDisplayStatus.AUTO_PROCESS)

    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_itsm.ticket_approve_result",
        mock.Mock(return_value=[{**APPROVE_TICKET_STATUS, "current_status": TicketStatus.FAILED.value}]),
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_itsm.get_service_detail", mock.Mock(return_value=APPROVE_SERVICE_INFO)
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_itsm.create_ticket", mock.Mock(return_value=APPROVE_TICKET_DETAIL)
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.auth_current_operator", mock.Mock(return_value=None)
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.notice_current_operator", mock.Mock(return_value=None)
    )
    def test_approve_failed(self):
        """
        测试审批失败
        关键验证：状态
        """

        with RuleContext() as (_, _):
            with RiskContext() as risk:
                # 初始化
                operator = uuid.uuid1().hex
                NewRisk(risk_id=risk.risk_id, operator=operator).run()
                risk.refresh_from_db()
                # 检测风险状态
                self.assertEquals(risk.status, RiskStatus.FOR_APPROVE.value)
                # display_status 同步为 FOR_APPROVE
                self.assertEquals(risk.display_status, RiskDisplayStatus.FOR_APPROVE)
                # 执行审批节点
                ForApprove(risk_id=risk.risk_id, operator=operator).run()
                risk.refresh_from_db()
                # 检测风险状态
                self.assertEquals(risk.status, RiskStatus.AWAIT_PROCESS)
                # 审批失败后 display_status 使用默认映射：AWAIT_PROCESS → PROCESSING
                self.assertEquals(risk.display_status, RiskDisplayStatus.PROCESSING)
                # 检测处理人
                self.assertEquals(risk.current_operator, ForApprove.load_security_person())
