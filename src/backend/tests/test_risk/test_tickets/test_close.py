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

from django.utils.translation import gettext

from services.web.risk.constants import RiskDisplayStatus, RiskStatus
from services.web.risk.handlers.ticket import CloseRisk
from tests.test_risk.test_tickets.base import RiskContext, TicketTest


class CloseTest(TicketTest):
    def test_close(self):
        """
        测试关单
        关键验证：状态，处理人
        """

        with RiskContext() as risk:
            # 运行
            operator = uuid.uuid1().hex
            description = gettext("%s 操作关单") % operator
            CloseRisk(risk_id=risk.risk_id, operator=operator).run(description=description)
            risk.refresh_from_db()
            # 风险状态
            self.assertEquals(risk.status, RiskStatus.CLOSED)
            # display_status 同步为 CLOSED
            self.assertEquals(risk.display_status, RiskDisplayStatus.CLOSED)
            # 节点操作人
            self.assertEquals(risk.last_history.operator, operator)
