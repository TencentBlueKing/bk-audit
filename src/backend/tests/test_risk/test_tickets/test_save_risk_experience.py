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

from services.web.risk.constants import RiskStatus
from services.web.risk.handlers.ticket import RiskExperienceRecord
from services.web.risk.models import TicketNode
from tests.test_risk.test_tickets.base import RiskContext, TicketTest


class RiskExperienceRecordTest(TicketTest):
    def test_creates_ticket_node_new(self):
        """首次保存经验应写入「添加风险总结」"""

        with RiskContext() as risk:
            operator = uuid.uuid1().hex
            description = "%s 添加风险总结" % operator
            RiskExperienceRecord(risk_id=risk.risk_id, operator=operator).run(description=description)
            node = TicketNode.objects.filter(risk_id=risk.risk_id, action="RiskExperienceRecord").first()
            self.assertIsNotNone(node)
            self.assertEqual(node.operator, operator)
            self.assertEqual(node.extra.get("description"), description)

    def test_creates_ticket_node_update(self):
        """更新经验应写入「修改风险总结」"""

        with RiskContext() as risk:
            operator = uuid.uuid1().hex
            description = "%s 修改风险总结" % operator
            RiskExperienceRecord(risk_id=risk.risk_id, operator=operator).run(description=description)
            node = TicketNode.objects.filter(risk_id=risk.risk_id, action="RiskExperienceRecord").first()
            self.assertIsNotNone(node)
            self.assertEqual(node.extra.get("description"), description)

    def test_does_not_change_status(self):
        """保存经验不应变更风险状态"""

        with RiskContext() as risk:
            original_status = risk.status
            RiskExperienceRecord(risk_id=risk.risk_id, operator=uuid.uuid1().hex).run()
            risk.refresh_from_db()
            self.assertEqual(risk.status, original_status)

    def test_does_not_change_operator(self):
        """保存经验不应变更当前处理人"""

        with RiskContext() as risk:
            original_operator = risk.current_operator
            RiskExperienceRecord(risk_id=risk.risk_id, operator=uuid.uuid1().hex).run()
            risk.refresh_from_db()
            self.assertEqual(risk.current_operator, original_operator)

    def test_works_on_closed_risk(self):
        """已关单风险也应能保存经验"""

        with RiskContext(risk_info={"status": RiskStatus.CLOSED}) as risk:
            operator = uuid.uuid1().hex
            RiskExperienceRecord(risk_id=risk.risk_id, operator=operator).run()
            node = TicketNode.objects.filter(risk_id=risk.risk_id, action="RiskExperienceRecord").first()
            self.assertIsNotNone(node)

    def test_multiple_saves_create_multiple_nodes(self):
        """多次保存应产生多条 TicketNode"""

        with RiskContext() as risk:
            for _ in range(3):
                RiskExperienceRecord(risk_id=risk.risk_id, operator=uuid.uuid1().hex).run()
            count = TicketNode.objects.filter(risk_id=risk.risk_id, action="RiskExperienceRecord").count()
            self.assertEqual(count, 3)
