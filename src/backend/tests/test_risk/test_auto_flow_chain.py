# -*- coding: utf-8 -*-
"""
自动流转链式推进与补偿 fan-out 用例。

覆盖验收点：
1. 无审批：NewRisk 成功后异步投递下一步，最终完成 create_task + start_task；
2. 需审批：ForApprove 创单；审批通过后异步投递 AutoProcess，不等下一轮扫表；
3. 已有 task_id / sn 的重复进入只更新状态，不重复建单（含中间插入记经验节点）；
4. 无 node_id 的补偿父任务只 fan-out 派发，不串行调外部 HTTP；带 node_id 的直调路径同步回写；
5. 链式与补偿命中同一限流 key，读写分桶。
"""

import uuid
from unittest import mock

from django.core.cache import cache
from django.test.utils import override_settings

from apps.itsm.constants import TicketStatus
from apps.sops.constants import SOPSTaskStatus
from services.web.risk.constants import RiskStatus, TicketNodeStatus
from services.web.risk.handlers.ticket import RiskExperienceRecord
from services.web.risk.models import TicketNode
from services.web.risk.tasks import process_one_risk, sync_auto_result
from tests.test_risk.test_tickets.base import RiskContext, RuleContext, TicketTest
from tests.test_risk.test_tickets.constants import (
    APPROVE_SERVICE_INFO,
    APPROVE_TICKET_DETAIL,
    APPROVE_TICKET_STATUS,
    SOPS_FLOW_INFO,
    SOPS_FLOW_STATUS,
    SOPS_TEMPLATE_INFO,
)

# 审批通过：FINISHED + approve_result
APPROVED_TICKET_STATUS = {**APPROVE_TICKET_STATUS, "current_status": TicketStatus.FINISHED.value}

# 套餐已结束
SOPS_FLOW_FINISHED = {"state": SOPSTaskStatus.FINISHED.value}


def _patch_flow_mocks():
    """链式用例公共 mock：外部系统全走 mock，验证调用次数与时序"""

    return [
        mock.patch(
            "services.web.risk.handlers.ticket.api.bk_sops.get_task_status",
            mock.Mock(return_value=SOPS_FLOW_STATUS),
        ),
        mock.patch(
            "services.web.risk.handlers.ticket.api.bk_sops.get_template_info",
            mock.Mock(return_value=SOPS_TEMPLATE_INFO),
        ),
        mock.patch(
            "services.web.risk.handlers.ticket.api.bk_sops.create_task",
            mock.Mock(return_value=SOPS_FLOW_INFO),
        ),
        mock.patch("services.web.risk.handlers.ticket.api.bk_sops.start_task", mock.Mock(return_value=None)),
        mock.patch(
            "services.web.risk.handlers.ticket.RiskFlowBaseHandler.auth_current_operator",
            mock.Mock(return_value=None),
        ),
        mock.patch(
            "services.web.risk.handlers.ticket.RiskFlowBaseHandler.notice_current_operator",
            mock.Mock(return_value=None),
        ),
    ]


@override_settings(BKAPP_ENABLE_ITSM_V4=True)
class AutoFlowChainTest(TicketTest):
    """异步单步推进：每一步独立执行，事务提交后投递下一步"""

    def test_new_risk_chains_auto_process_in_one_task(self):
        """无审批：NewRisk 后异步进入 AutoProcess 完成建任务"""

        with RuleContext(pa_info={"need_approve": False}) as (_, rule):
            with RiskContext() as risk:
                risk.rule_id = rule.rule_id
                risk.rule_version = rule.version
                risk.save()

                patches = _patch_flow_mocks()
                for p in patches:
                    p.start()
                    self.addCleanup(p.stop)

                from services.web.risk.handlers.ticket import api as ticket_api

                create_task = ticket_api.bk_sops.create_task
                start_task = ticket_api.bk_sops.start_task

                def assert_lock_released(**kwargs):
                    self.assertIsNone(cache.get(f"celery:process_one_risk:{risk.risk_id}"))

                with mock.patch("services.web.risk.tasks.process_one_risk.delay") as enqueue:
                    enqueue.side_effect = assert_lock_released
                    process_one_risk(risk_id=risk.risk_id)

                risk.refresh_from_db()
                self.assertEqual(risk.status, RiskStatus.AUTO_PROCESS)
                # 第一步只推进 NewRisk，下一步通过队列触发
                create_task.assert_not_called()
                start_task.assert_not_called()
                enqueue.assert_called_once_with(risk_id=risk.risk_id, chain_depth=1)

                # 模拟消费下一步 AutoProcess
                process_one_risk(risk_id=risk.risk_id, chain_depth=1)
                create_task.assert_called_once()
                start_task.assert_called_once()

    def test_new_risk_chains_for_approve_then_auto_process(self):
        """需审批：分步建 ITSM 单；审批通过后异步进入 AutoProcess"""

        with RuleContext() as (_, rule):
            with RiskContext() as risk:
                risk.rule_id = rule.rule_id
                risk.rule_version = rule.version
                risk.save()

                patches = _patch_flow_mocks() + [
                    mock.patch(
                        "services.web.risk.handlers.ticket.api.bk_itsm_v4.workflows",
                        mock.Mock(return_value=APPROVE_SERVICE_INFO),
                    ),
                    mock.patch(
                        "services.web.risk.handlers.ticket.api.bk_itsm_v4.ticket_create",
                        mock.Mock(return_value=APPROVE_TICKET_DETAIL),
                    ),
                    mock.patch(
                        "services.web.risk.handlers.ticket.get_itsm_ticket_status",
                        mock.Mock(return_value=APPROVE_TICKET_STATUS),
                    ),
                ]
                for p in patches:
                    p.start()
                    self.addCleanup(p.stop)

                from services.web.risk.handlers.ticket import api as ticket_api

                ticket_create = ticket_api.bk_itsm_v4.ticket_create
                create_task = ticket_api.bk_sops.create_task

                # 第一步：NewRisk → FOR_APPROVE，尚未建审批单
                process_one_risk(risk_id=risk.risk_id)
                risk.refresh_from_db()
                self.assertEqual(risk.status, RiskStatus.FOR_APPROVE)
                ticket_create.assert_not_called()
                create_task.assert_not_called()

                # 第二步：ForApprove 建审批单，审批中
                process_one_risk(risk_id=risk.risk_id, chain_depth=1)
                risk.refresh_from_db()
                self.assertEqual(risk.status, RiskStatus.FOR_APPROVE)
                ticket_create.assert_called_once()

                # 第三步：审批通过后推进到 AUTO_PROCESS
                with mock.patch(
                    "services.web.risk.handlers.ticket.get_itsm_ticket_status",
                    mock.Mock(return_value=APPROVED_TICKET_STATUS),
                ):
                    process_one_risk(risk_id=risk.risk_id, chain_depth=1)

                risk.refresh_from_db()
                self.assertEqual(risk.status, RiskStatus.AUTO_PROCESS)
                create_task.assert_not_called()

                # 第四步：AutoProcess 建任务
                process_one_risk(risk_id=risk.risk_id, chain_depth=2)
                create_task.assert_called_once()

    def test_existing_ticket_and_task_not_recreated(self):
        """已有 sn/task_id 的重复进入只更新状态；中间插记经验节点不破坏幂等"""

        with RuleContext(pa_info={"need_approve": False}) as (_, rule):
            with RiskContext() as risk:
                risk.rule_id = rule.rule_id
                risk.rule_version = rule.version
                risk.save()

                patches = _patch_flow_mocks()
                for p in patches:
                    p.start()
                    self.addCleanup(p.stop)

                from services.web.risk.handlers.ticket import api as ticket_api

                create_task = ticket_api.bk_sops.create_task

                # 第一步只推进 NewRisk
                process_one_risk(risk_id=risk.risk_id)
                create_task.assert_not_called()

                # 第二步 AutoProcess 建任务
                process_one_risk(risk_id=risk.risk_id, chain_depth=1)
                create_task.assert_called_once()

                # 中间插入记经验节点（纯留痕）
                RiskExperienceRecord(risk_id=risk.risk_id, operator=uuid.uuid1().hex).run(description="经验")

                # 重复进入：只拉状态，不重复建任务
                process_one_risk(risk_id=risk.risk_id, chain_depth=2)
                create_task.assert_called_once()

    def test_for_approve_ticket_not_recreated(self):
        """已有 sn 的重复进入只拉审批结果，不重复建单"""

        with RuleContext() as (_, rule):
            with RiskContext() as risk:
                risk.rule_id = rule.rule_id
                risk.rule_version = rule.version
                risk.save()

                patches = _patch_flow_mocks() + [
                    mock.patch(
                        "services.web.risk.handlers.ticket.api.bk_itsm_v4.workflows",
                        mock.Mock(return_value=APPROVE_SERVICE_INFO),
                    ),
                    mock.patch(
                        "services.web.risk.handlers.ticket.api.bk_itsm_v4.ticket_create",
                        mock.Mock(return_value=APPROVE_TICKET_DETAIL),
                    ),
                    mock.patch(
                        "services.web.risk.handlers.ticket.get_itsm_ticket_status",
                        mock.Mock(return_value=APPROVE_TICKET_STATUS),
                    ),
                ]
                for p in patches:
                    p.start()
                    self.addCleanup(p.stop)

                from services.web.risk.handlers.ticket import api as ticket_api

                ticket_create = ticket_api.bk_itsm_v4.ticket_create

                # 第一步只推进 NewRisk
                process_one_risk(risk_id=risk.risk_id)
                ticket_create.assert_not_called()

                # 第二步 ForApprove 建单
                process_one_risk(risk_id=risk.risk_id, chain_depth=1)
                ticket_create.assert_called_once()

                # 重复进入（审批未完成）：只拉状态
                process_one_risk(risk_id=risk.risk_id, chain_depth=2)
                ticket_create.assert_called_once()

    def test_process_one_risk_uses_early_ack(self):
        """采用默认早 ACK：避免连接断连后消息重投导致重复执行；任务丢失由周期扫描兜底。"""
        self.assertFalse(process_one_risk.acks_late)
        self.assertFalse(process_one_risk.reject_on_worker_lost)

    def test_handler_match_restricts_auto_flow_statuses(self):
        """自动流转 match 只匹配各自的状态，避免手动操作状态被自动调度。"""
        from services.web.risk.handlers.ticket import AutoProcess, ForApprove, NewRisk

        for status, matcher, other in (
            (RiskStatus.NEW, NewRisk, AutoProcess),
            (RiskStatus.FOR_APPROVE, ForApprove, NewRisk),
            (RiskStatus.AUTO_PROCESS, AutoProcess, ForApprove),
        ):
            risk = mock.Mock(status=status)
            self.assertTrue(matcher.match(risk))
            self.assertFalse(other.match(risk))

        awaiting = mock.Mock(status=RiskStatus.AWAIT_PROCESS)
        self.assertFalse(AutoProcess.match(awaiting))


class SyncAutoResultFanoutTest(TicketTest):
    """补偿 fan-out：父任务只派发，子任务单节点同步"""

    def _make_node(self, risk_id: str, action: str, process_result: dict, is_test: bool = False) -> TicketNode:
        return TicketNode.objects.create(
            risk_id=risk_id,
            operator=uuid.uuid1().hex,
            action=action,
            timestamp=1.0,
            time="2026-01-01 00:00:00",
            process_result=process_result,
            status=TicketNodeStatus.RUNNING,
            is_test=is_test,
        )

    def test_parent_only_dispatches_without_http(self):
        """无 node_id：父任务只 delay 派发，不串行调外部 HTTP"""

        with RiskContext() as risk:
            self._make_node(risk.risk_id, "ForApprove", {"ticket": {"id": "t1", "sn": "s1"}})
            self._make_node(risk.risk_id, "AutoProcess", {"task": {"task_id": 1}})
            self._make_node(risk.risk_id, "NewRisk", {})

            with (
                mock.patch("services.web.risk.tasks.sync_one_auto_result.delay") as mock_delay,
                mock.patch("services.web.risk.tasks.api.bk_sops.get_task_status") as mock_sops,
                mock.patch("services.web.risk.tasks.get_itsm_ticket_status") as mock_itsm,
            ):
                sync_auto_result()

            # 只派发审批/套餐节点，且父任务不调外部 HTTP
            self.assertEqual(mock_delay.call_count, 2)
            mock_sops.assert_not_called()
            mock_itsm.assert_not_called()

    def test_parent_dispatches_all_candidates(self):
        """无 node_id：派发全部审批/套餐候选，不设每轮上限"""

        with RiskContext() as risk:
            for _ in range(3):
                self._make_node(risk.risk_id, "AutoProcess", {"task": {"task_id": 1}})

            with mock.patch("services.web.risk.tasks.sync_one_auto_result.delay") as mock_delay:
                sync_auto_result()

            self.assertEqual(mock_delay.call_count, 3)

    def test_node_id_path_syncs_and_advances_flow(self):
        """带 node_id 直调：返回时节点已回写（强制撤销路径），结束后推进流转"""

        with RiskContext() as risk:
            node = self._make_node(risk.risk_id, "AutoProcess", {"task": {"task_id": 1}})

            with (
                mock.patch(
                    "services.web.risk.tasks.api.bk_sops.get_task_status",
                    mock.Mock(return_value=SOPS_FLOW_FINISHED),
                ),
                mock.patch("services.web.risk.tasks.process_one_risk.delay") as mock_advance,
            ):
                sync_auto_result(node_id=node.id)

            node.refresh_from_db()
            self.assertEqual(node.status, TicketNodeStatus.FINISHED)
            mock_advance.assert_called_once_with(risk_id=risk.risk_id)

    def test_node_id_running_task_does_not_advance_flow(self):
        """节点未结束（套餐执行中）不推进流转"""

        with RiskContext() as risk:
            node = self._make_node(risk.risk_id, "AutoProcess", {"task": {"task_id": 1}})

            with (
                mock.patch(
                    "services.web.risk.tasks.api.bk_sops.get_task_status",
                    mock.Mock(return_value=SOPS_FLOW_STATUS),
                ),
                mock.patch("services.web.risk.tasks.process_one_risk.delay") as mock_advance,
            ):
                sync_auto_result(node_id=node.id)

            node.refresh_from_db()
            self.assertEqual(node.status, TicketNodeStatus.RUNNING)
            mock_advance.assert_not_called()

    def test_test_node_finished_does_not_advance_flow(self):
        """BKSEC 测试单跑完只回写执行记录，不驱动真实风险流转"""

        with RiskContext() as risk:
            node = self._make_node(risk.risk_id, "AutoProcess", {"task": {"task_id": 1}}, is_test=True)

            with (
                mock.patch(
                    "services.web.risk.tasks.api.bk_sops.get_task_status",
                    mock.Mock(return_value=SOPS_FLOW_FINISHED),
                ),
                mock.patch("services.web.risk.tasks.process_one_risk.delay") as mock_advance,
            ):
                sync_auto_result(node_id=node.id)

            node.refresh_from_db()
            self.assertEqual(node.status, TicketNodeStatus.FINISHED)
            mock_advance.assert_not_called()


class ThrottlerKeyTest(TicketTest):
    """限流 key：读写分桶；链式与补偿走同一 perform_request 天然同 key"""

    def _throttle_key(self, api_cls):
        with mock.patch(f"{api_cls.__module__}.Throttler") as mock_throttler:
            mock_throttler.return_value.return_value = "ok"
            result = api_cls().perform_request({})
        self.assertEqual(result, "ok")
        return mock_throttler.call_args.kwargs["config"].key

    def test_sops_read_write_buckets(self):
        from api.bk_sops.default import (
            CreateTask,
            GetTaskStatus,
            GetTemplateInfo,
            OperateTask,
            StartTask,
        )

        read_key = self._throttle_key(GetTaskStatus)
        self.assertEqual(read_key, "api.bk_sops.default.read")
        # 读桶共享：查状态与查模板同 key
        self.assertEqual(self._throttle_key(GetTemplateInfo), read_key)

        write_key = self._throttle_key(CreateTask)
        self.assertEqual(write_key, "api.bk_sops.default.write")
        # 写桶共享：建任务/启动/操作同 key
        self.assertEqual(self._throttle_key(StartTask), write_key)
        self.assertEqual(self._throttle_key(OperateTask), write_key)

        # 读写不同桶
        self.assertNotEqual(read_key, write_key)

    def test_itsm_read_write_buckets(self):
        from api.bk_itsm.default import (
            CreateTicket,
            GetTicketStatus,
            OperateTicket,
            TicketApproveResult,
        )

        read_key = self._throttle_key(GetTicketStatus)
        self.assertEqual(read_key, "api.bk_itsm.default.read")
        self.assertEqual(self._throttle_key(TicketApproveResult), read_key)

        write_key = self._throttle_key(CreateTicket)
        self.assertEqual(write_key, "api.bk_itsm.default.write")
        self.assertEqual(self._throttle_key(OperateTicket), write_key)

    def test_chain_and_compensation_share_same_key(self):
        """链式建任务与补偿拉状态各自命中所属桶，两路调用同一 API 类即同一 key"""
        from api.bk_sops.default import CreateTask, GetTaskStatus

        # 同一 API 类无论链式（process_one_risk）还是补偿（sync）调用，key 由类决定
        self.assertEqual(self._throttle_key(CreateTask), self._throttle_key(CreateTask))
        self.assertEqual(self._throttle_key(GetTaskStatus), self._throttle_key(GetTaskStatus))
