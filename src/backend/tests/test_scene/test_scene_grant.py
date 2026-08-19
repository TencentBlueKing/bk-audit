# -*- coding: utf-8 -*-
"""
场景授权功能单元测试

覆盖：
- ITSM 工单日志状态推断
- 拒绝理由提取
- 申请状态更新
- 申请列表查询逻辑
"""
from unittest import mock

from django.utils import timezone

from services.web.scene.constants import (
    ApplicationStatus,
    GrantStatus,
    ITSMV4TicketStatus,
)
from services.web.scene.models import Scene, ScenePermissionApplication
from services.web.scene.permission import (
    _extract_reject_reason_from_logs,
    apply_ticket_result,
    parse_itsm_ticket_from_logs,
)
from tests.base import TestCase

# ==================== parse_itsm_ticket_from_logs 测试 ====================


class TestParseItsTicketFromLogs(TestCase):
    """测试从 ITSM V4 工单日志推断工单状态"""

    def test_empty_logs_returns_running(self):
        """空日志返回 RUNNING 状态"""
        result = parse_itsm_ticket_from_logs({"items": []})
        self.assertEqual(
            result,
            {
                "status": ITSMV4TicketStatus.RUNNING,
                "approve_result": False,
                "is_terminal": False,
                "is_terminated": False,
            },
        )

    def test_logs_without_end_returns_running(self):
        """没有 end 日志返回 RUNNING 状态"""
        logs_data = {
            "items": [
                {"action": "start", "activity_type": None},
                {"action": "submit", "activity_type": "SUBMIT"},
            ]
        }
        result = parse_itsm_ticket_from_logs(logs_data)
        self.assertEqual(
            result,
            {
                "status": ITSMV4TicketStatus.RUNNING,
                "approve_result": False,
                "is_terminal": False,
                "is_terminated": False,
            },
        )

    def test_logs_with_approve_and_end_returns_finished(self):
        """审批通过 + end 日志返回 FINISHED（approve_result=True）"""
        logs_data = {
            "items": [
                {"action": "start", "activity_type": None},
                {"action": "submit", "activity_type": "SUBMIT"},
                {"action": "approve", "activity_type": "APPROVE_TASK"},
                {"action": "end", "activity_type": None},
            ]
        }
        result = parse_itsm_ticket_from_logs(logs_data)
        self.assertEqual(
            result,
            {
                "status": ITSMV4TicketStatus.FINISHED,
                "approve_result": True,
                "is_terminal": True,
                "is_terminated": False,
            },
        )

    def test_logs_with_refuse_and_end_returns_finished(self):
        """审批拒绝 + end 日志返回 FINISHED（approve_result=False）"""
        logs_data = {
            "items": [
                {"action": "start", "activity_type": None},
                {"action": "submit", "activity_type": "SUBMIT"},
                {"action": "refuse", "activity_type": "APPROVE_TASK"},
                {"action": "end", "activity_type": None},
            ]
        }
        result = parse_itsm_ticket_from_logs(logs_data)
        self.assertEqual(
            result,
            {
                "status": ITSMV4TicketStatus.FINISHED,
                "approve_result": False,
                "is_terminal": True,
                "is_terminated": False,
            },
        )

    def test_logs_with_multiple_approve_tasks_uses_first(self):
        """多个审批节点取第一个审批节点的结果"""
        logs_data = {
            "items": [
                {"action": "start", "activity_type": None},
                {"action": "approve", "activity_type": "APPROVE_TASK"},
                {"action": "approve", "activity_type": "APPROVE_TASK"},
                {"action": "end", "activity_type": None},
            ]
        }
        result = parse_itsm_ticket_from_logs(logs_data)
        self.assertTrue(result["approve_result"])

    def test_logs_without_approve_task_returns_false(self):
        """没有审批节点时 approve_result 为 False"""
        logs_data = {
            "items": [
                {"action": "start", "activity_type": None},
                {"action": "end", "activity_type": None},
            ]
        }
        result = parse_itsm_ticket_from_logs(logs_data)
        self.assertEqual(
            result,
            {
                "status": ITSMV4TicketStatus.FINISHED,
                "approve_result": False,
                "is_terminal": True,
                "is_terminated": False,
            },
        )


# ==================== _extract_reject_reason_from_logs 测试 ====================


class TestExtractRejectReasonFromLogs(TestCase):
    """测试从已获取的 ITSM V4 工单日志数据中提取拒绝理由"""

    def test_empty_logs_returns_empty(self):
        """空日志返回空字符串"""
        result = _extract_reject_reason_from_logs({"items": []})
        self.assertEqual(result, "")

    def test_no_refuse_action_returns_empty(self):
        """没有 refuse 操作返回空字符串"""
        logs_data = {
            "items": [
                {"action": "approve", "extra": []},
            ]
        }
        result = _extract_reject_reason_from_logs(logs_data)
        self.assertEqual(result, "")

    def test_refuse_with_opinion_extracts_reason(self):
        """refuse 操作有审批意见时提取理由"""
        logs_data = {
            "items": [
                {
                    "action": "refuse",
                    "extra": [{"type": "name_value", "name": "审批意见", "value": "不通过，理由不充分"}],
                },
            ]
        }
        result = _extract_reject_reason_from_logs(logs_data)
        self.assertEqual(result, "不通过，理由不充分")

    def test_refuse_without_opinion_returns_empty(self):
        """refuse 操作没有审批意见时返回空字符串"""
        logs_data = {
            "items": [
                {
                    "action": "refuse",
                    "extra": [],
                },
            ]
        }
        result = _extract_reject_reason_from_logs(logs_data)
        self.assertEqual(result, "")

    def test_refuse_with_whitespace_opinion_strips(self):
        """refuse 操作审批意见有空格时去除空格"""
        logs_data = {
            "items": [
                {
                    "action": "refuse",
                    "extra": [{"type": "name_value", "name": "审批意见", "value": "  理由  "}],
                },
            ]
        }
        result = _extract_reject_reason_from_logs(logs_data)
        self.assertEqual(result, "理由")

    def test_multiple_refuses_uses_last(self):
        """多个 refuse 操作取最后一个"""
        logs_data = {
            "items": [
                {
                    "action": "refuse",
                    "extra": [{"type": "name_value", "name": "审批意见", "value": "第一次拒绝"}],
                },
                {
                    "action": "refuse",
                    "extra": [{"type": "name_value", "name": "审批意见", "value": "第二次拒绝"}],
                },
            ]
        }
        result = _extract_reject_reason_from_logs(logs_data)
        self.assertEqual(result, "第二次拒绝")


# ==================== apply_ticket_result 测试 ====================


class TestApplyTicketResult(TestCase):
    """测试根据 ITSM 工单结果更新申请状态"""

    def setUp(self):
        """创建测试场景和申请单"""
        self.scene = Scene.objects.create(
            name="测试场景",
            description="测试场景描述",
        )
        self.application = ScenePermissionApplication._objects.create(
            scene=self.scene,
            applicant="test_user",
            role="user",
            status=ApplicationStatus.PENDING,
            itsm_sn="test_sn",
            itsm_ticket_id="test_ticket_id",
        )

    def test_approve_grants_permission(self):
        """审批通过时更新状态为 APPROVED 并执行授权"""
        parsed = {
            "status": ITSMV4TicketStatus.FINISHED,
            "approve_result": True,
            "is_terminal": True,
        }
        with mock.patch(
            "services.web.scene.permission.grant_scene_role", return_value={"success": True, "method": "v4_role_grant"}
        ):
            apply_ticket_result(self.application, parsed, operator="admin")
            self.application.save()

        self.application.refresh_from_db()
        self.assertEqual(self.application.status, ApplicationStatus.APPROVED)
        self.assertEqual(self.application.grant_status, GrantStatus.SUCCESS)

    def test_reject_sets_rejected_status(self):
        """审批驳回时更新状态为 REJECTED"""
        parsed = {
            "status": ITSMV4TicketStatus.FINISHED,
            "approve_result": False,
            "is_terminal": True,
        }
        apply_ticket_result(self.application, parsed, reject_reason="理由不充分")
        self.application.save()

        self.application.refresh_from_db()
        self.assertEqual(self.application.status, ApplicationStatus.REJECTED)
        self.assertEqual(self.application.reject_reason, "理由不充分")
        self.assertIsNotNone(self.application.finished_at)

    def test_running_keeps_pending(self):
        """流程进行中时保持 PENDING 状态"""
        parsed = {
            "status": ITSMV4TicketStatus.RUNNING,
            "approve_result": False,
            "is_terminal": False,
        }
        apply_ticket_result(self.application, parsed)

        self.application.refresh_from_db()
        self.assertEqual(self.application.status, ApplicationStatus.PENDING)


# ==================== 无权限场景列表查询逻辑测试 ====================


class TestListNoPermissionScenes(TestCase):
    """测试无权限场景列表查询逻辑（与 ListMyScenePermissionApplications 一致）"""

    def setUp(self):
        """创建测试数据"""
        self.scene1 = Scene.objects.create(name="场景1", description="描述1")
        self.scene2 = Scene.objects.create(name="场景2", description="描述2")
        self.scene3 = Scene.objects.create(name="场景3", description="描述3")

    def test_get_latest_application_per_scene(self):
        """同一场景多条申请时返回最新一条"""
        # 场景1 创建两条申请
        ScenePermissionApplication._objects.create(
            scene=self.scene1,
            applicant="test_user",
            role="user",
            status=ApplicationStatus.REJECTED,
            created_at=timezone.now() - timezone.timedelta(days=2),
            itsm_sn="sn_old",
            itsm_ticket_id="ticket_old",
        )
        app_new = ScenePermissionApplication._objects.create(
            scene=self.scene1,
            applicant="test_user",
            role="user",
            status=ApplicationStatus.PENDING,
            created_at=timezone.now() - timezone.timedelta(days=1),
            itsm_sn="sn_new",
            itsm_ticket_id="ticket_new",
        )

        # 查询用户对场景1的最新申请
        from django.db.models import Max

        latest = (
            ScenePermissionApplication.objects.filter(
                applicant="test_user",
                scene_id=self.scene1.scene_id,
            )
            .values("scene_id")
            .annotate(latest_id=Max("id"))
            .order_by("-latest_id")
            .first()
        )

        self.assertIsNotNone(latest)
        self.assertEqual(latest["latest_id"], app_new.id)

    def test_only_returns_user_applications(self):
        """只返回当前用户的申请"""
        ScenePermissionApplication._objects.create(
            scene=self.scene1,
            applicant="test_user",
            role="user",
            status=ApplicationStatus.PENDING,
            itsm_sn="sn_user",
            itsm_ticket_id="ticket_user",
        )
        ScenePermissionApplication._objects.create(
            scene=self.scene1,
            applicant="other_user",
            role="user",
            status=ApplicationStatus.PENDING,
            itsm_sn="sn_other",
            itsm_ticket_id="ticket_other",
        )

        result = ScenePermissionApplication.objects.filter(applicant="test_user")
        self.assertEqual(result.count(), 1)
        self.assertEqual(result.first().applicant, "test_user")
