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
from apps.sops.constants import SOPSTaskStatus
from services.web.risk.constants import RiskDisplayStatus, RiskStatus
from services.web.risk.handlers.ticket import AutoProcess, ForApprove
from services.web.risk.models import Risk
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


class AutoProcessTest(TicketTest):
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
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.auth_current_operator", mock.Mock(return_value=None)
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.notice_current_operator", mock.Mock(return_value=None)
    )
    def test_custom_auto_process(self):
        """
        测试手动发起
        关键验证：状态，处理套餐
        """

        with RuleContext(pa_info={"need_approve": False}) as (pa, _):
            with RiskContext() as risk:
                risk.status = RiskStatus.AWAIT_PROCESS
                risk.save()
                # 执行
                pa_config = {**CUSTOM_AUTO_PROCESS_PARAMS, "pa_id": pa.id}
                resource.risk.custom_auto_process(risk_id=risk.risk_id, **pa_config)
                risk.refresh_from_db()
                # 检测风险状态
                self.assertEquals(risk.status, RiskStatus.AUTO_PROCESS)
                # display_status 同步为 AUTO_PROCESS
                self.assertEquals(risk.display_status, RiskDisplayStatus.AUTO_PROCESS)
                # 检测单据是否符合预期
                self.assertEquals(risk.last_history.extra["pa_config"], pa_config)

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
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.auth_current_operator", mock.Mock(return_value=None)
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.notice_current_operator", mock.Mock(return_value=None)
    )
    def test_auto_process(self):
        """
        测试自动发起
        关键验证：状态
        """

        with RuleContext(pa_info={"need_approve": False}) as (_, rule):
            with RiskContext() as risk:
                risk.rule_id = rule.rule_id
                risk.rule_version = rule.version
                risk.status = RiskStatus.AUTO_PROCESS
                risk.save()
                # 执行
                operator = uuid.uuid1().hex
                AutoProcess(risk_id=risk.risk_id, operator=operator).run()
                risk.refresh_from_db()
                # 检测风险状态
                self.assertEquals(risk.status, RiskStatus.AUTO_PROCESS)
                # display_status 同步为 AUTO_PROCESS
                self.assertEquals(risk.display_status, RiskDisplayStatus.AUTO_PROCESS)
                # 再次执行
                with mock.patch(
                    "services.web.risk.handlers.ticket.api.bk_sops.get_task_status",
                    mock.Mock(return_value={"state": SOPSTaskStatus.FINISHED.value}),
                ):
                    AutoProcess(risk_id=risk.risk_id, operator=operator).run()
                risk.refresh_from_db()
                # 检测风险状态
                self.assertEquals(risk.status, RiskStatus.AWAIT_PROCESS)
                # 套餐完成且不自动关单，使用默认映射：AWAIT_PROCESS → PROCESSING
                self.assertEquals(risk.display_status, RiskDisplayStatus.PROCESSING)
                self.assertEquals(risk.current_operator, AutoProcess.load_security_person())

    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_sops.get_task_status",
        mock.Mock(return_value={"state": SOPSTaskStatus.FAILED.value}),
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_sops.get_template_info", mock.Mock(return_value=SOPS_TEMPLATE_INFO)
    )
    @mock.patch("services.web.risk.handlers.ticket.api.bk_sops.create_task", mock.Mock(return_value=SOPS_FLOW_INFO))
    @mock.patch("services.web.risk.handlers.ticket.api.bk_sops.start_task", mock.Mock(return_value=None))
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.auth_current_operator", mock.Mock(return_value=None)
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.notice_current_operator", mock.Mock(return_value=None)
    )
    def test_auto_process_failed(self):
        """
        测试自动处理失败
        关键验证：状态，处理人
        """

        with RuleContext(pa_info={"need_approve": False}) as (_, rule):
            with RiskContext() as risk:
                risk.rule_id = rule.rule_id
                risk.rule_version = rule.version
                risk.status = RiskStatus.AUTO_PROCESS
                risk.save()
                # 执行
                operator = uuid.uuid1().hex
                AutoProcess(risk_id=risk.risk_id, operator=operator).run()
                risk.refresh_from_db()
                # 检测风险状态
                self.assertEquals(risk.status, RiskStatus.AWAIT_PROCESS)
                # 套餐执行失败，使用默认映射：AWAIT_PROCESS → PROCESSING
                self.assertEquals(risk.display_status, RiskDisplayStatus.PROCESSING)
                self.assertEquals(risk.current_operator, AutoProcess.load_security_person())

    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_itsm.ticket_approve_result",
        mock.Mock(return_value=[{**APPROVE_TICKET_STATUS, "current_status": TicketStatus.FINISHED.value}]),
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
        "services.web.risk.handlers.ticket.api.bk_sops.get_task_status",
        mock.Mock(return_value={"state": SOPSTaskStatus.FINISHED.value}),
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_sops.get_template_info", mock.Mock(return_value=SOPS_TEMPLATE_INFO)
    )
    @mock.patch("services.web.risk.handlers.ticket.api.bk_sops.create_task", mock.Mock(return_value=SOPS_FLOW_INFO))
    @mock.patch("services.web.risk.handlers.ticket.api.bk_sops.start_task", mock.Mock(return_value=None))
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.auth_current_operator", mock.Mock(return_value=None)
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.notice_current_operator", mock.Mock(return_value=None)
    )
    def test_process_from_approve(self):
        """
        测试审批节点发起
        关键验证：两个节点的处理套餐配置
        """

        with RuleContext() as (pa, _):
            with RiskContext() as risk:
                # 执行
                pa_config = {**CUSTOM_AUTO_PROCESS_PARAMS, "pa_id": pa.id}
                resource.risk.custom_auto_process(risk_id=risk.risk_id, **pa_config)
                risk.refresh_from_db()
                # 检测单据是否符合预期
                self.assertEquals(risk.last_history.action, ForApprove.__name__)
                self.assertEquals(risk.last_history.extra["pa_config"], pa_config)
                # 执行自动处理节点
                operator = uuid.uuid1().hex
                AutoProcess(risk_id=risk.risk_id, operator=operator).run()
                # 检测处理套餐是否符合预期
                risk = Risk.objects.get(risk_id=risk.risk_id)
                self.assertEquals(risk.last_history.action, AutoProcess.__name__)
                self.assertEquals(risk.last_history.extra["pa_config"], pa_config)
