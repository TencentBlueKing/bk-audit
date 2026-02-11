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

from core.exceptions import RiskStatusInvalid
from services.web.risk.constants import RiskDisplayStatus, RiskStatus
from services.web.risk.handlers.ticket import ReOpen
from tests.test_risk.test_tickets.base import RiskContext, TicketTest


class ReOpenTest(TicketTest):
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.auth_current_operator", mock.Mock(return_value=None)
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.notice_current_operator", mock.Mock(return_value=None)
    )
    def test_reopen(self):
        """
        测试重开单据
        关键验证：处理人
        """

        with RiskContext() as risk:
            # 重开失败
            with self.assertRaises(RiskStatusInvalid):
                ReOpen(risk_id=risk.risk_id, operator=uuid.uuid1().hex).run()
            risk.status = RiskStatus.CLOSED
            risk.save()
            # 重开
            ReOpen(risk_id=risk.risk_id, operator=uuid.uuid1().hex).run(new_operators=ReOpen.load_security_person())
            risk.refresh_from_db()
            # 验证状态
            self.assertEquals(risk.status, RiskStatus.AWAIT_PROCESS)
            # ReOpen 使用默认映射：AWAIT_PROCESS → PROCESSING（处理中）
            self.assertEquals(risk.display_status, RiskDisplayStatus.PROCESSING)
            self.assertEquals(risk.current_operator, ReOpen.load_security_person())
