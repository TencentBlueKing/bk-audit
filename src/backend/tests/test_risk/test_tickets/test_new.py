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

from services.web.risk.constants import RiskDisplayStatus, RiskStatus
from services.web.risk.handlers.ticket import NewRisk
from tests.test_risk.test_tickets.base import RiskContext, RuleContext, TicketTest


class NewTest(TicketTest):
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.auth_current_operator", mock.Mock(return_value=None)
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.notice_current_operator", mock.Mock(return_value=None)
    )
    def test_no_rule(self):
        """
        测试无规则命中
        关键验证：处理人，状态
        """

        with RiskContext() as risk:
            # 运行
            operator = uuid.uuid1().hex
            NewRisk(risk_id=risk.risk_id, operator=operator).run()
            risk.refresh_from_db()
            # 风险状态
            self.assertEquals(risk.status, RiskStatus.AWAIT_PROCESS)
            # NewRisk 覆盖映射：AWAIT_PROCESS → AWAIT_PROCESS（待处理）
            self.assertEquals(risk.display_status, RiskDisplayStatus.AWAIT_PROCESS)
            # 有当前处理人且为安全责任人
            self.assertEquals(risk.current_operator, NewRisk.load_security_person())

    def _test_rule(self, risk_status: str, expected_display_status: str = None, pa_info: dict = None):
        """
        测试规则
        关键验证：有规则，状态，display_status
        """

        with RuleContext(pa_info=pa_info) as (_, rule):
            with RiskContext() as risk:
                # 运行
                operator = uuid.uuid1().hex
                NewRisk(risk_id=risk.risk_id, operator=operator).run()
                risk.refresh_from_db()
                # 有命中的规则
                self.assertEquals(risk.rule_id, rule.rule_id)
                # 风险状态
                self.assertEquals(risk.status, risk_status)
                # display_status 同步验证
                if expected_display_status:
                    self.assertEquals(risk.display_status, expected_display_status)

    def test_rule_for_approve(self):
        """测试审批"""

        self._test_rule(RiskStatus.FOR_APPROVE, expected_display_status=RiskDisplayStatus.FOR_APPROVE)

    def test_rule_auto_process(self):
        """测试自动处理"""

        self._test_rule(
            RiskStatus.AUTO_PROCESS,
            expected_display_status=RiskDisplayStatus.AUTO_PROCESS,
            pa_info={"need_approve": False},
        )
