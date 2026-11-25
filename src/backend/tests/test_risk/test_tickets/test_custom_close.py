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
from services.web.risk.constants import RiskDisplayStatus, RiskLabel, RiskStatus, TicketNodeStatus
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


class RunClosedGuardTest(TicketTest):
    """run() 级并发约束（BKSEC 1578946 评审意见）：行锁内刷新最新状态后由 pre_check 终止整个流转。

    覆盖评审指出的两个缺口：① 外部调用与状态写入之前拦截（不再产生处理人/节点/授权/通知）；
    ② CloseRisk 对已关单保持幂等（ConfirmAsMisReport 依赖）。
    """

    def _assert_no_side_effect(self, risk: Risk, handler_cls, operator: str):
        node_count = TicketNode.objects.filter(risk_id=risk.risk_id).count()
        operator_before = Risk.objects.get(risk_id=risk.risk_id).current_operator
        handler = handler_cls(risk_id=risk.risk_id, operator=operator)
        # 模拟并发时序：handler 构造已读到旧状态，人工关单随后提交
        Risk.objects.filter(risk_id=risk.risk_id).update(status=RiskStatus.CLOSED)
        with self.assertRaises(RiskStatusInvalid):
            handler.run()
        risk.refresh_from_db()
        self.assertEqual(risk.status, RiskStatus.CLOSED, "FAIL: 状态被流转改写")
        self.assertEqual(TicketNode.objects.filter(risk_id=risk.risk_id).count(), node_count, "FAIL: 产生了流转节点")
        self.assertEqual(risk.current_operator, operator_before, "FAIL: 处理人被写入")

    def test_for_approve_run_terminated_when_closed(self):
        """审批流转遇已关单：整个 run 终止（无外部调用副作用、无节点、无处理人写入）"""
        with RiskContext(
            risk_info={"status": RiskStatus.FOR_APPROVE, "display_status": RiskDisplayStatus.FOR_APPROVE}
        ) as risk:
            self._assert_no_side_effect(risk, ForApprove, "run-guard-tester")

    def test_auto_process_run_terminated_when_closed(self):
        """套餐流转遇已关单：整个 run 终止"""
        with RiskContext(
            risk_info={"status": RiskStatus.AUTO_PROCESS, "display_status": RiskDisplayStatus.AUTO_PROCESS}
        ) as risk:
            self._assert_no_side_effect(risk, AutoProcess, "run-guard-tester")

    def test_close_risk_remains_idempotent_when_closed(self):
        """CloseRisk 对已关单保持幂等放行（ConfirmAsMisReport 二次关单依赖此语义）"""
        with RiskContext(risk_info={"status": RiskStatus.CLOSED, "display_status": RiskDisplayStatus.CLOSED}) as risk:
            CloseRisk(risk_id=risk.risk_id, operator="idempotent-tester").run(description="已关单重复关单")
            risk.refresh_from_db()
            self.assertEqual(risk.status, RiskStatus.CLOSED)
            # 幂等关单仅追加历史节点，状态不变
            self.assertEqual(TicketNode.objects.filter(risk_id=risk.risk_id, action="CloseRisk").count(), 1)


class RetryLockOrderTest(TicketTest):
    """复审 P1（BKSEC 1578946）：RetryAutoProcess 与流转 run() 加锁顺序统一（先风险单后套餐节点）。

    锁顺序倒挂会在并发时形成"持节点锁等风险单锁"的 AB-BA 死锁：死锁回滚时外部重试动作已发出，
    本地记录与 SOPS 实际状态不一致。
    """

    SOPS_STATUS = {"state": "FAILED", "children": {"n1": {"id": "n1", "state": "FAILED"}}}

    def _make_node(self, risk_id: str) -> TicketNode:
        import time as time_mod
        from uuid import uuid4

        return TicketNode.objects.create(
            id=uuid4().hex,
            risk_id=risk_id,
            action="AutoProcess",
            operator="retry-origin",
            timestamp=time_mod.time(),
            time="2026-11-25 12:00:00",
            process_result={"task": {"task_id": "T1000"}, "status": {"state": "FAILED"}},
        )

    def test_lock_order_risk_before_node(self):
        """锁顺序特征：RetryAutoProcess 先锁风险单再锁套餐节点（与流转 run() 一致）"""
        import inspect

        from services.web.risk.resources import risk as risk_res

        src = inspect.getsource(risk_res.RetryAutoProcess.perform_request)
        risk_lock_pos = src.find("Risk.objects.select_for_update")
        node_lock_pos = src.find("TicketNode.objects.select_for_update")
        self.assertGreaterEqual(risk_lock_pos, 0, "缺少风险单行锁")
        self.assertGreater(node_lock_pos, risk_lock_pos, "锁顺序倒挂：套餐节点锁先于风险单锁")

    def test_retry_updates_risk_and_local_records(self):
        """并发回归：重试链路（SOPS 外部动作已 mock）本地记录按预期落库"""
        with RiskContext(
            risk_info={"status": RiskStatus.AWAIT_PROCESS, "display_status": RiskDisplayStatus.AWAIT_PROCESS}
        ) as risk:
            node = self._make_node(risk.risk_id)
            with mock.patch(
                "services.web.risk.resources.risk.api.bk_sops.get_task_status",
                return_value=self.SOPS_STATUS,
            ), mock.patch(
                "services.web.risk.resources.risk.api.bk_sops.get_node_data", return_value={"inputs": {}}
            ), mock.patch(
                "services.web.risk.resources.risk.api.bk_sops.operate_node", return_value=None
            ), mock.patch(
                "services.web.risk.resources.risk.sync_auto_result"
            ) as mock_sync:
                resource.risk.retry_auto_process.perform_request({"risk_id": risk.risk_id, "node_id": node.id})
            node.refresh_from_db()
            risk.refresh_from_db()
            # 节点回执行中，被重试节点计入累计清单，兜底同步任务已调度
            self.assertEqual(node.status, TicketNodeStatus.RUNNING)
            self.assertIn("n1", node.process_result["retried_node_ids"])
            mock_sync.apply_async.assert_called_once()
            # 最后一个节点为套餐节点：风险单转自动处理中并清空处理人（本地记录一致性）
            self.assertEqual(risk.status, RiskStatus.AUTO_PROCESS)
            self.assertEqual(risk.current_operator, [])
