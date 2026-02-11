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

from apps.sops.constants import SOPSTaskStatus
from services.web.risk.constants import RiskDisplayStatus, RiskLabel, RiskStatus
from tests.test_risk.test_tickets.base import RiskContext, RuleContext, TicketTest
from tests.test_risk.test_tickets.constants import (
    APPROVE_SERVICE_INFO,
    APPROVE_TICKET_DETAIL,
    APPROVE_TICKET_STATUS,
    CUSTOM_AUTO_PROCESS_PARAMS,
    SOPS_FLOW_INFO,
    SOPS_FLOW_STATUS,
    SOPS_TEMPLATE_INFO,
)


class RiskLabelTest(TicketTest):
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
    def test_misreport(self):
        """
        测试误报
        关键验证：状态，处理人
        """

        with RiskContext() as risk:
            # 处理误报
            resource.risk.update_risk_label(
                risk_id=risk.risk_id, risk_label=RiskLabel.MISREPORT, description=uuid.uuid1().hex
            )
            risk.refresh_from_db()
            # 检测关单
            self.assertEquals(risk.status, RiskStatus.CLOSED.value)
            self.assertEquals(risk.risk_label, RiskLabel.MISREPORT)
            # MisReport→CloseRisk: display_status 同步为 CLOSED
            self.assertEquals(risk.display_status, RiskDisplayStatus.CLOSED)
            # 解除误报
            operator = uuid.uuid1().hex
            resource.risk.update_risk_label(risk_id=risk.risk_id, risk_label=RiskLabel.NORMAL, new_operators=[operator])
            risk.refresh_from_db()
            # 检测状态
            self.assertEquals(risk.status, RiskStatus.AWAIT_PROCESS.value)
            # ReOpenMisReport→ReOpen: 使用默认映射 AWAIT_PROCESS → PROCESSING
            self.assertEquals(risk.display_status, RiskDisplayStatus.PROCESSING)
            self.assertEquals(risk.current_operator, [operator])

    @mock.patch(
        "services.web.risk.resources.risk.get_request_username",
        mock.Mock(return_value=bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME),
    )
    @mock.patch(
        "services.web.risk.resources.risk.api.bk_itsm.ticket_approve_result",
        mock.Mock(return_value=[APPROVE_TICKET_STATUS]),
    )
    @mock.patch(
        "services.web.risk.resources.risk.sync_auto_result",
        mock.Mock(return_value=None),
    )
    @mock.patch(
        "services.web.risk.resources.risk.api.bk_itsm.operate_ticket",
        mock.Mock(return_value=None),
    )
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
    def test_misreport_approve(self):
        """
        测试误报（审批中时）
        关键验证：状态
        """

        with RuleContext() as (pa, _):
            with RiskContext() as risk:
                # 转为审批中
                pa_config = {**CUSTOM_AUTO_PROCESS_PARAMS, "pa_id": pa.id}
                resource.risk.custom_auto_process(risk_id=risk.risk_id, **pa_config)
                risk.refresh_from_db()
                # 处理误报
                resource.risk.update_risk_label(
                    risk_id=risk.risk_id, risk_label=RiskLabel.MISREPORT, description=uuid.uuid1().hex
                )
                risk.refresh_from_db()
                # 检测关单
                self.assertEquals(risk.status, RiskStatus.CLOSED.value)
                self.assertEquals(risk.risk_label, RiskLabel.MISREPORT)
                # MisReport（审批中）→CloseRisk: display_status 同步为 CLOSED
                self.assertEquals(risk.display_status, RiskDisplayStatus.CLOSED)

    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_sops.get_task_status",
        mock.Mock(return_value=SOPS_FLOW_STATUS),
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_sops.get_template_info", mock.Mock(return_value=SOPS_TEMPLATE_INFO)
    )
    @mock.patch("services.web.risk.handlers.ticket.api.bk_sops.create_task", mock.Mock(return_value=SOPS_FLOW_INFO))
    @mock.patch("services.web.risk.handlers.ticket.api.bk_sops.start_task", mock.Mock(return_value=None))
    @mock.patch(
        "services.web.risk.resources.risk.get_request_username",
        mock.Mock(return_value=bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME),
    )
    @mock.patch(
        "services.web.risk.resources.risk.api.bk_sops.get_task_status",
        mock.Mock(return_value={"state": SOPSTaskStatus.RUNNING.value}),
    )
    @mock.patch(
        "services.web.risk.resources.risk.api.bk_sops.operate_task",
        mock.Mock(return_value=None),
    )
    @mock.patch(
        "services.web.risk.resources.risk.sync_auto_result",
        mock.Mock(return_value=None),
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.auth_current_operator", mock.Mock(return_value=None)
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.notice_current_operator", mock.Mock(return_value=None)
    )
    def test_misreport_auto_process(self):
        """
        测试误报（自动处理中时）
        关键验证：状态
        """

        with RuleContext(pa_info={"need_approve": False}) as (pa, _):
            with RiskContext() as risk:
                risk.status = RiskStatus.AWAIT_PROCESS
                risk.save()
                # 转为自动处理中
                pa_config = {**CUSTOM_AUTO_PROCESS_PARAMS, "pa_id": pa.id}
                resource.risk.custom_auto_process(risk_id=risk.risk_id, **pa_config)
                risk.refresh_from_db()
                # 处理误报
                resource.risk.update_risk_label(
                    risk_id=risk.risk_id,
                    risk_label=RiskLabel.MISREPORT,
                    description=uuid.uuid1().hex,
                    revoke_process=False,
                )
                risk.refresh_from_db()
                # 检测状态 —— MisReport 不关单（套餐继续执行），display_status 保持不变
                self.assertEquals(risk.status, RiskStatus.AUTO_PROCESS)
                self.assertEquals(risk.risk_label, RiskLabel.MISREPORT)
                # MisReport.update_status 为 pass，不改变 status，display_status 保持 AUTO_PROCESS
                self.assertEquals(risk.display_status, RiskDisplayStatus.AUTO_PROCESS)
                # 解除误报
                resource.risk.update_risk_label(risk_id=risk.risk_id, risk_label=RiskLabel.NORMAL)
                risk.refresh_from_db()
                # 检测状态 —— ReOpenMisReport 不改变 status（仍为 AUTO_PROCESS）
                self.assertEquals(risk.status, RiskStatus.AUTO_PROCESS)
                self.assertEquals(risk.risk_label, RiskLabel.NORMAL)
                # display_status 保持 AUTO_PROCESS
                self.assertEquals(risk.display_status, RiskDisplayStatus.AUTO_PROCESS)
                # 处理误报
                resource.risk.update_risk_label(
                    risk_id=risk.risk_id,
                    risk_label=RiskLabel.MISREPORT,
                    description=uuid.uuid1().hex,
                    revoke_process=True,
                )
                risk.refresh_from_db()
                # 检测关单
                self.assertEquals(risk.status, RiskStatus.CLOSED.value)
                self.assertEquals(risk.risk_label, RiskLabel.MISREPORT)
                # MisReport（强制终止套餐）→CloseRisk: display_status 同步为 CLOSED
                self.assertEquals(risk.display_status, RiskDisplayStatus.CLOSED)
