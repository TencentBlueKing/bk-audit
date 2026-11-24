# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from unittest import mock

from bk_resource import resource

from apps.itsm.constants import TicketStatus
from apps.sops.constants import SOPSTaskStatus
from core.exceptions import RiskStatusInvalid
from services.web.risk.constants import RiskDisplayStatus, RiskLabel, RiskStatus
from services.web.risk.handlers.ticket import (
    AutoProcess,
    CloseRisk,
    ForApprove,
    MisReport,
)
from services.web.risk.models import Risk, TicketNode
from tests.test_risk.test_tickets.base import RiskContext, TicketTest


class CustomCloseRiskGuardTest(TicketTest):
    """人工关单入口状态校验（BKSEC 1578946）：与批量规则共用同一套判定。"""

    username = "close-guard-tester"

    def setUp(self):
        super().setUp()
        patcher = mock.patch("services.web.risk.resources.risk.get_request_username", return_value=self.username)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _close(self, risk: Risk):
        return resource.risk.custom_close_risk.perform_request({"risk_id": risk.risk_id, "description": "状态校验测试"})

    def _assert_rejected_without_side_effect(self, risk: Risk):
        risk.refresh_from_db()
        origin_status = risk.status
        node_count = TicketNode.objects.filter(risk_id=risk.risk_id).count()
        with self.assertRaises(RiskStatusInvalid):
            self._close(risk)
        risk.refresh_from_db()
        self.assertEqual(risk.status, origin_status)
        self.assertEqual(TicketNode.objects.filter(risk_id=risk.risk_id).count(), node_count)

    def test_close_rejected_in_auto_process(self):
        """套餐处理中禁止人工关单（工单主断言场景）"""
        with RiskContext(
            risk_info={"status": RiskStatus.AUTO_PROCESS, "display_status": RiskDisplayStatus.AUTO_PROCESS}
        ) as risk:
            self._assert_rejected_without_side_effect(risk)
            self.assertEqual(risk.status, RiskStatus.AUTO_PROCESS)

    def test_close_rejected_in_for_approve(self):
        """审批中禁止人工关单"""
        with RiskContext(
            risk_info={"status": RiskStatus.FOR_APPROVE, "display_status": RiskDisplayStatus.FOR_APPROVE}
        ) as risk:
            self._assert_rejected_without_side_effect(risk)
            self.assertEqual(risk.status, RiskStatus.FOR_APPROVE)

    def test_close_rejected_in_new(self):
        """新建瞬态禁止人工关单（与批量口径一致）"""
        with RiskContext(risk_info={"status": RiskStatus.NEW, "display_status": RiskDisplayStatus.NEW}) as risk:
            self._assert_rejected_without_side_effect(risk)
            self.assertEqual(risk.status, RiskStatus.NEW)

    def test_close_rejected_in_pending_confirm(self):
        """待确认禁止人工关单（原由后置预检拒绝，现入口层先拒）"""
        with RiskContext(
            risk_info={
                "status": RiskStatus.PENDING_CONFIRM,
                "display_status": RiskDisplayStatus.PENDING_CONFIRM,
            }
        ) as risk:
            self._assert_rejected_without_side_effect(risk)
            self.assertEqual(risk.status, RiskStatus.PENDING_CONFIRM)

    def test_close_rejected_in_closed(self):
        """已关单禁止重复关单"""
        with RiskContext(risk_info={"status": RiskStatus.CLOSED, "display_status": RiskDisplayStatus.CLOSED}) as risk:
            self._assert_rejected_without_side_effect(risk)
            self.assertEqual(risk.status, RiskStatus.CLOSED)

    def test_close_success_in_await_process(self):
        """待处理状态正常关单（回归）"""
        with RiskContext(
            risk_info={
                "status": RiskStatus.AWAIT_PROCESS,
                "display_status": RiskDisplayStatus.AWAIT_PROCESS,
            }
        ) as risk:
            self._close(risk)
            risk.refresh_from_db()
            self.assertEqual(risk.status, RiskStatus.CLOSED)
            self.assertEqual(risk.display_status, RiskDisplayStatus.CLOSED)
            # 双节点留痕：CustomProcess（关单意图）+ CloseRisk（关单动作）
            actions = list(TicketNode.objects.filter(risk_id=risk.risk_id).values_list("action", flat=True))
            self.assertEqual(actions.count("CustomProcess"), 1)
            self.assertEqual(actions.count("CloseRisk"), 1)

    def test_close_rejected_when_status_display_drift(self):
        """status/display_status 字段漂移时双查拦截，任一命中处理中即拒绝"""
        # display 看似可关（处理中），实际 status 处于套餐处理中
        with RiskContext(
            risk_info={
                "status": RiskStatus.AUTO_PROCESS,
                "display_status": RiskDisplayStatus.PROCESSING,
            }
        ) as risk:
            self._assert_rejected_without_side_effect(risk)
        # 反向：status 看似待处理，display 仍是套餐处理中
        with RiskContext(
            risk_info={
                "status": RiskStatus.AWAIT_PROCESS,
                "display_status": RiskDisplayStatus.AUTO_PROCESS,
            }
        ) as risk:
            self._assert_rejected_without_side_effect(risk)


class InternalClosePathTest(TicketTest):
    """内部自动关单路径不受入口收口影响（共用 CloseRisk，不经过 CustomCloseRisk）。"""

    def test_close_risk_handler_allows_auto_process(self):
        """套餐处理中状态经 CloseRisk 流转类仍可关单（套餐成功自动关单依赖此行为）"""
        with RiskContext() as risk:
            risk.status = RiskStatus.AUTO_PROCESS
            risk.display_status = RiskDisplayStatus.AUTO_PROCESS
            risk.save()
            CloseRisk(risk_id=risk.risk_id, operator="auto-close").run(description="套餐执行成功后自动关单")
            risk.refresh_from_db()
            self.assertEqual(risk.status, RiskStatus.CLOSED)

    def test_misreport_auto_close_in_auto_process(self):
        """处理中标记误报仍可有序关单（拍板：误报保持现状不禁）"""
        with RiskContext() as risk:
            risk.status = RiskStatus.AUTO_PROCESS
            risk.display_status = RiskDisplayStatus.AUTO_PROCESS
            risk.save()
            MisReport(risk_id=risk.risk_id, operator="misreport-tester").run(description="标记误报", revoke_process=True)
            risk.refresh_from_db()
            self.assertEqual(risk.status, RiskStatus.CLOSED)
            self.assertEqual(risk.risk_label, RiskLabel.MISREPORT)


class StatusUpdateClosedGuardTest(TicketTest):
    """并发一致性（BKSEC 1578946）：状态回写前复查已关单则跳过，防止已关单被拉回处理中。"""

    def test_for_approve_skips_update_when_closed(self):
        with RiskContext(
            risk_info={"status": RiskStatus.FOR_APPROVE, "display_status": RiskDisplayStatus.FOR_APPROVE}
        ) as risk:
            handler = ForApprove(risk_id=risk.risk_id, operator="flow-tester")
            # 模拟并发时序：流转已读取旧状态后，人工关单先提交
            Risk.objects.filter(risk_id=risk.risk_id).update(status=RiskStatus.CLOSED)
            # 审批通过的结果回写不得覆盖 CLOSED
            handler.update_status(
                process_result={"status": {"current_status": TicketStatus.FINISHED, "approve_result": True}}
            )
            risk.refresh_from_db()
            self.assertEqual(risk.status, RiskStatus.CLOSED)

    def test_for_approve_updates_when_not_closed(self):
        """未关单时审批状态正常回写（复检不影响正常流转）"""
        with RiskContext(
            risk_info={"status": RiskStatus.FOR_APPROVE, "display_status": RiskDisplayStatus.FOR_APPROVE}
        ) as risk:
            handler = ForApprove(risk_id=risk.risk_id, operator="flow-tester")
            handler.update_status(
                process_result={"status": {"current_status": TicketStatus.FINISHED, "approve_result": True}}
            )
            risk.refresh_from_db()
            self.assertEqual(risk.status, RiskStatus.AUTO_PROCESS)

    def test_auto_process_skips_update_when_closed(self):
        with RiskContext(
            risk_info={"status": RiskStatus.AUTO_PROCESS, "display_status": RiskDisplayStatus.AUTO_PROCESS}
        ) as risk:
            handler = AutoProcess(risk_id=risk.risk_id, operator="flow-tester")
            Risk.objects.filter(risk_id=risk.risk_id).update(status=RiskStatus.CLOSED)
            handler.update_status(process_result={"status": {"state": SOPSTaskStatus.FINISHED}})
            risk.refresh_from_db()
            self.assertEqual(risk.status, RiskStatus.CLOSED)
