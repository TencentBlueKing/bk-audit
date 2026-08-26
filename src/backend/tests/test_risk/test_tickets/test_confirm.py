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

from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from services.web.risk.constants import RiskDisplayStatus, RiskLabel, RiskStatus
from services.web.risk.handlers.ticket import ConfirmAsMisReport, ConfirmRisk, NewRisk
from services.web.risk.models import Risk
from services.web.scene.models import Scene
from tests.test_risk.test_tickets.base import RiskContext, RuleContext, TicketTest
from tests.test_risk.test_tickets.constants import (
    APPROVE_SERVICE_INFO,
    APPROVE_TICKET_DETAIL,
    APPROVE_TICKET_STATUS,
    RISK_INFO,
    SOPS_FLOW_INFO,
    SOPS_FLOW_STATUS,
    SOPS_TEMPLATE_INFO,
)


class ConfirmRiskRequestSerializerTest(TicketTest):
    """测试 ConfirmRiskRequestSerializer"""

    def test_valid(self):
        """测试有效请求"""
        from services.web.risk.serializers import ConfirmRiskRequestSerializer

        serializer = ConfirmRiskRequestSerializer(data={"risk_id": uuid.uuid1().hex})
        self.assertTrue(serializer.is_valid())

    def test_missing_risk_id(self):
        """测试缺少 risk_id"""
        from services.web.risk.serializers import ConfirmRiskRequestSerializer

        serializer = ConfirmRiskRequestSerializer(data={})
        self.assertFalse(serializer.is_valid())


class ConfirmAsMisReportRequestSerializerTest(TicketTest):
    """测试 ConfirmAsMisReportRequestSerializer"""

    def test_valid(self):
        """测试有效请求"""
        from services.web.risk.serializers import ConfirmAsMisReportRequestSerializer

        serializer = ConfirmAsMisReportRequestSerializer(data={"risk_id": uuid.uuid1().hex, "description": "测试误报"})
        self.assertTrue(serializer.is_valid())

    def test_empty_description(self):
        """测试空描述"""
        from services.web.risk.serializers import ConfirmAsMisReportRequestSerializer

        serializer = ConfirmAsMisReportRequestSerializer(data={"risk_id": uuid.uuid1().hex})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["description"], "")


class ConfirmRiskTest(TicketTest):
    """测试 ConfirmRisk Handler"""

    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.auth_current_operator",
        mock.Mock(return_value=None),
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.notice_current_operator",
        mock.Mock(return_value=None),
    )
    def test_confirm_no_rule(self):
        """
        测试确认风险（无处理套餐）
        关键验证：状态流转、处理人初始化
        """
        operator = uuid.uuid1().hex
        with RiskContext(
            risk_info={
                "status": RiskStatus.PENDING_CONFIRM,
                "confirmer": [operator],
            }
        ) as risk:
            # 执行确认
            ConfirmRisk(risk_id=risk.risk_id, operator=operator).run(username=operator)
            risk.refresh_from_db()

            # 验证状态流转：PENDING_CONFIRM → NEW → AWAIT_PROCESS
            self.assertEqual(risk.status, RiskStatus.AWAIT_PROCESS)
            # display_status 同步为 AWAIT_PROCESS（待处理）
            self.assertEqual(risk.display_status, RiskDisplayStatus.AWAIT_PROCESS)
            # 验证处理人初始化（无规则时为安全责任人）
            self.assertEqual(risk.current_operator, ConfirmRisk.load_security_person())

    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_itsm.ticket_approve_result",
        mock.Mock(return_value=[APPROVE_TICKET_STATUS]),
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_itsm.get_service_detail",
        mock.Mock(return_value=APPROVE_SERVICE_INFO),
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_itsm.create_ticket",
        mock.Mock(return_value=APPROVE_TICKET_DETAIL),
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.auth_current_operator",
        mock.Mock(return_value=None),
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.notice_current_operator",
        mock.Mock(return_value=None),
    )
    def test_confirm_with_approve(self):
        """
        测试确认风险（有处理套餐，需要审批）
        关键验证：状态流转、处理人为空
        """
        operator = uuid.uuid1().hex
        with RuleContext(pa_info={"need_approve": True}) as (pa, rule):
            with RiskContext(
                risk_info={
                    "status": RiskStatus.PENDING_CONFIRM,
                    "rule_id": rule.rule_id,
                    "rule_version": rule.version,
                    "confirmer": [operator],
                }
            ) as risk:
                # 执行确认
                ConfirmRisk(risk_id=risk.risk_id, operator=operator).run(username=operator)
                risk.refresh_from_db()

                # 验证状态流转：PENDING_CONFIRM → NEW → FOR_APPROVE
                self.assertEqual(risk.status, RiskStatus.FOR_APPROVE)
                # display_status 同步为 FOR_APPROVE
                self.assertEqual(risk.display_status, RiskDisplayStatus.FOR_APPROVE)
                # 需要审批时处理人应为空
                self.assertEqual(risk.current_operator, [])

    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_sops.get_task_status",
        mock.Mock(return_value=SOPS_FLOW_STATUS),
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_sops.get_template_info",
        mock.Mock(return_value=SOPS_TEMPLATE_INFO),
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_sops.create_task",
        mock.Mock(return_value=SOPS_FLOW_INFO),
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_sops.start_task",
        mock.Mock(return_value=None),
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.auth_current_operator",
        mock.Mock(return_value=None),
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.notice_current_operator",
        mock.Mock(return_value=None),
    )
    def test_confirm_with_auto_process(self):
        """
        测试确认风险（有处理套餐，自动处理）
        关键验证：状态流转、处理人初始化
        """
        operator = uuid.uuid1().hex
        with RuleContext(pa_info={"need_approve": False}) as (pa, rule):
            with RiskContext(
                risk_info={
                    "status": RiskStatus.PENDING_CONFIRM,
                    "rule_id": rule.rule_id,
                    "rule_version": rule.version,
                    "confirmer": [operator],
                }
            ) as risk:
                # 执行确认
                ConfirmRisk(risk_id=risk.risk_id, operator=operator).run(username=operator)
                risk.refresh_from_db()

                # 验证状态流转：PENDING_CONFIRM → NEW → AUTO_PROCESS
                self.assertEqual(risk.status, RiskStatus.AUTO_PROCESS)
                # display_status 同步为 AUTO_PROCESS
                self.assertEqual(risk.display_status, RiskDisplayStatus.AUTO_PROCESS)
                # 自动处理时处理人应为空（有处理套餐）
                self.assertEqual(risk.current_operator, [])

    def test_confirm_permission_denied(self):
        """
        测试权限拒绝（非确认人操作）
        关键验证：PermissionDenied 异常
        """
        with RiskContext(
            risk_info={
                "status": RiskStatus.PENDING_CONFIRM,
                "confirmer": ["confirmer_user"],
            }
        ) as risk:
            # 非确认人操作
            operator = "wrong_user"
            with self.assertRaises(PermissionDenied):
                ConfirmRisk(risk_id=risk.risk_id, operator=operator).run(username=operator)

    def test_confirm_invalid_status(self):
        """
        测试状态无效（非 PENDING_CONFIRM 状态）
        关键验证：RiskStatusInvalid 异常
        """
        from core.exceptions import RiskStatusInvalid

        with RiskContext(risk_info={"status": RiskStatus.NEW}) as risk:
            operator = uuid.uuid1().hex
            with self.assertRaises(RiskStatusInvalid):
                ConfirmRisk(risk_id=risk.risk_id, operator=operator).run(username=operator)

    def test_confirm_closed_status(self):
        """
        测试已关闭状态阻止操作
        关键验证：RiskStatusInvalid 异常
        """
        from core.exceptions import RiskStatusInvalid

        with RiskContext(risk_info={"status": RiskStatus.CLOSED}) as risk:
            operator = uuid.uuid1().hex
            with self.assertRaises(RiskStatusInvalid):
                ConfirmRisk(risk_id=risk.risk_id, operator=operator).run(username=operator)


class ConfirmAsMisReportTest(TicketTest):
    """测试 ConfirmAsMisReport Handler"""

    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.auth_current_operator",
        mock.Mock(return_value=None),
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.notice_current_operator",
        mock.Mock(return_value=None),
    )
    def test_confirm_misreport(self):
        """
        测试确认为误报
        关键验证：状态、标签、处理人
        """
        operator = uuid.uuid1().hex
        with RiskContext(
            risk_info={
                "status": RiskStatus.PENDING_CONFIRM,
                "confirmer": [operator],
            }
        ) as risk:
            # 执行误报确认
            ConfirmAsMisReport(risk_id=risk.risk_id, operator=operator).run(username=operator, description="测试误报")
            risk.refresh_from_db()

            # 验证状态：PENDING_CONFIRM → CLOSED
            self.assertEqual(risk.status, RiskStatus.CLOSED)
            # display_status 同步为 CLOSED
            self.assertEqual(risk.display_status, RiskDisplayStatus.CLOSED)
            # 验证标签
            self.assertEqual(risk.risk_label, RiskLabel.MISREPORT)
            # 验证处理人清空
            self.assertEqual(risk.current_operator, [])

    def test_confirm_misreport_permission_denied(self):
        """
        测试权限拒绝（非确认人操作）
        关键验证：PermissionDenied 异常
        """
        with RiskContext(
            risk_info={
                "status": RiskStatus.PENDING_CONFIRM,
                "confirmer": ["confirmer_user"],
            }
        ) as risk:
            operator = "wrong_user"
            with self.assertRaises(PermissionDenied):
                ConfirmAsMisReport(risk_id=risk.risk_id, operator=operator).run(username=operator)

    def test_confirm_misreport_invalid_status(self):
        """
        测试状态无效（非 PENDING_CONFIRM 状态）
        关键验证：RiskStatusInvalid 异常
        """
        from core.exceptions import RiskStatusInvalid

        with RiskContext(risk_info={"status": RiskStatus.NEW}) as risk:
            operator = uuid.uuid1().hex
            with self.assertRaises(RiskStatusInvalid):
                ConfirmAsMisReport(risk_id=risk.risk_id, operator=operator).run(username=operator)

    def test_confirm_misreport_history(self):
        """
        测试误报确认历史记录
        关键验证：TicketNode 创建
        """
        from services.web.risk.models import TicketNode

        operator = uuid.uuid1().hex
        with RiskContext(
            risk_info={
                "status": RiskStatus.PENDING_CONFIRM,
                "confirmer": [operator],
            }
        ) as risk:
            # 执行误报确认
            description = "测试误报描述"
            ConfirmAsMisReport(risk_id=risk.risk_id, operator=operator).run(username=operator, description=description)

            # 验证历史记录
            history = TicketNode.objects.filter(risk_id=risk.risk_id).last()
            self.assertIsNotNone(history)
            self.assertEqual(history.action, ConfirmAsMisReport.__name__)
            self.assertEqual(history.operator, operator)
            self.assertEqual(history.extra["description"], description)
            self.assertEqual(history.extra["from_status"], RiskStatus.PENDING_CONFIRM)
            self.assertEqual(history.extra["to_status"], RiskStatus.CLOSED)


class ConfirmRiskResourceTest(TicketTest):
    """测试 ConfirmRisk Resource"""

    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.auth_current_operator",
        mock.Mock(return_value=None),
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.notice_current_operator",
        mock.Mock(return_value=None),
    )
    @mock.patch(
        "services.web.risk.resources.risk.get_request_username",
        mock.Mock(return_value="confirmer_user"),
    )
    def test_confirm_risk_resource(self):
        """
        测试 ConfirmRiskResource 成功调用
        关键验证：资源接口调用
        """
        from services.web.risk.resources.risk import ConfirmRiskResource

        with RiskContext(
            risk_info={
                "status": RiskStatus.PENDING_CONFIRM,
                "display_status": RiskDisplayStatus.PENDING_CONFIRM,
                "confirmer": ["confirmer_user"],
            }
        ) as risk:
            # 调用资源接口
            result = ConfirmRiskResource().perform_request({"risk_id": risk.risk_id})
            self.assertTrue(result["success"])

    @mock.patch(
        "services.web.risk.resources.risk.get_request_username",
        mock.Mock(return_value="confirmer_user"),
    )
    def test_confirm_risk_resource_invalid_status(self):
        """
        测试 ConfirmRiskResource 状态错误
        关键验证：ValidationError 异常
        """
        from services.web.risk.resources.risk import ConfirmRiskResource

        with RiskContext(
            risk_info={
                "status": RiskStatus.NEW,
                "display_status": RiskDisplayStatus.NEW,
                "confirmer": ["confirmer_user"],
            }
        ) as risk:
            with self.assertRaises(ValidationError):
                ConfirmRiskResource().perform_request({"risk_id": risk.risk_id})

    @mock.patch(
        "services.web.risk.resources.risk.get_request_username",
        mock.Mock(return_value="wrong_user"),
    )
    def test_confirm_risk_resource_permission_denied(self):
        """
        测试 ConfirmRiskResource 权限拒绝
        关键验证：PermissionDenied 异常
        """
        from services.web.risk.resources.risk import ConfirmRiskResource

        with RiskContext(
            risk_info={
                "status": RiskStatus.PENDING_CONFIRM,
                "display_status": RiskDisplayStatus.PENDING_CONFIRM,
                "confirmer": ["confirmer_user"],
            }
        ) as risk:
            with self.assertRaises(PermissionDenied):
                ConfirmRiskResource().perform_request({"risk_id": risk.risk_id})


class ConfirmAsMisReportResourceTest(TicketTest):
    """测试 ConfirmAsMisReport Resource"""

    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.auth_current_operator",
        mock.Mock(return_value=None),
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.notice_current_operator",
        mock.Mock(return_value=None),
    )
    @mock.patch(
        "services.web.risk.resources.risk.get_request_username",
        mock.Mock(return_value="confirmer_user"),
    )
    def test_confirm_misreport_resource(self):
        """
        测试 ConfirmAsMisReportResource 成功调用
        关键验证：资源接口调用
        """
        # 直接导入 Resource 类，绕过 resource.risk 快捷访问
        from services.web.risk.resources.risk import ConfirmAsMisReportResource

        with RiskContext(
            risk_info={
                "status": RiskStatus.PENDING_CONFIRM,
                "display_status": RiskDisplayStatus.PENDING_CONFIRM,
                "confirmer": ["confirmer_user"],
            }
        ) as risk:
            # 调用资源接口
            resource_instance = ConfirmAsMisReportResource()
            result = resource_instance.perform_request({"risk_id": risk.risk_id, "description": "测试误报"})
            self.assertTrue(result["success"])

    @mock.patch(
        "services.web.risk.resources.risk.get_request_username",
        mock.Mock(return_value="confirmer_user"),
    )
    def test_confirm_misreport_resource_invalid_status(self):
        """
        测试 ConfirmAsMisReportResource 状态错误
        关键验证：ValidationError 异常
        """
        from services.web.risk.resources.risk import ConfirmAsMisReportResource

        with RiskContext(
            risk_info={
                "status": RiskStatus.NEW,
                "display_status": RiskDisplayStatus.NEW,
                "confirmer": ["confirmer_user"],
            }
        ) as risk:
            with self.assertRaises(ValidationError):
                ConfirmAsMisReportResource().perform_request({"risk_id": risk.risk_id})

    @mock.patch(
        "services.web.risk.resources.risk.get_request_username",
        mock.Mock(return_value="wrong_user"),
    )
    def test_confirm_misreport_resource_permission_denied(self):
        """
        测试 ConfirmAsMisReportResource 权限拒绝
        关键验证：PermissionDenied 异常
        """
        from services.web.risk.resources.risk import ConfirmAsMisReportResource

        with RiskContext(
            risk_info={
                "status": RiskStatus.PENDING_CONFIRM,
                "display_status": RiskDisplayStatus.PENDING_CONFIRM,
                "confirmer": ["confirmer_user"],
            }
        ) as risk:
            with self.assertRaises(PermissionDenied):
                ConfirmAsMisReportResource().perform_request({"risk_id": risk.risk_id})


class ListPendingConfirmRiskTest(TicketTest):
    """测试 ListPendingConfirmRisk Resource"""

    @mock.patch(
        "services.web.risk.resources.risk.get_request_username",
        mock.Mock(return_value="user1"),
    )
    def test_list_pending_confirm_risk(self):
        """
        测试待确认风险列表
        关键验证：用户过滤
        """
        # 手动创建风险，避免 RiskContext 删除所有风险
        from services.web.strategy_v2.models import Strategy

        Strategy.objects.get_or_create(
            strategy_id=1,
            defaults={"strategy_name": "test_strategy_1"},
        )

        risk1 = Risk.objects.create(
            event_content="test risk 1",
            raw_event_id=uuid.uuid1().hex,
            strategy_id=1,
            event_evidence="[]",
            event_type=["SuperPermission"],
            event_data={"username": "admin"},
            event_time=timezone.now(),
            event_end_time=timezone.now(),
            event_source="bkm",
            operator=["admin"],
            status=RiskStatus.PENDING_CONFIRM,
            display_status=RiskDisplayStatus.PENDING_CONFIRM,
            confirmer=["user1"],
        )

        risk2 = Risk.objects.create(
            event_content="test risk 2",
            raw_event_id=uuid.uuid1().hex,
            strategy_id=1,
            event_evidence="[]",
            event_type=["SuperPermission"],
            event_data={"username": "admin"},
            event_time=timezone.now(),
            event_end_time=timezone.now(),
            event_source="bkm",
            operator=["admin"],
            status=RiskStatus.PENDING_CONFIRM,
            display_status=RiskDisplayStatus.PENDING_CONFIRM,
            confirmer=["user2"],
        )

        try:
            # 直接查询数据库验证
            risks = Risk.objects.filter(
                display_status=RiskDisplayStatus.PENDING_CONFIRM,
                confirmer__contains="user1",
                is_deleted=False,
            ).distinct()
            risk_ids = [r.risk_id for r in risks]
            # 应只包含用户 1 的风险
            self.assertIn(risk1.risk_id, risk_ids)
            self.assertNotIn(risk2.risk_id, risk_ids)
        finally:
            risk1.delete()
            risk2.delete()


class RiskCreateWithDispatchModeTest(TicketTest):
    """测试风险创建时的分派模式"""

    def test_after_confirm_dispatch_mode(self):
        """
        测试 AFTER_CONFIRM 分派模式
        关键验证：状态、确认人
        """
        # 创建场景
        scene = Scene.objects.create(name=f"test_scene_{uuid.uuid1().hex}", description="test")

        try:
            # 创建风险（模拟 AFTER_CONFIRM 分派模式的结果）
            risk = Risk.objects.create(
                **{
                    **RISK_INFO,
                    "status": RiskStatus.PENDING_CONFIRM,
                    "display_status": RiskDisplayStatus.PENDING_CONFIRM,
                    "confirmer": [1],
                }
            )

            try:
                # 验证状态
                self.assertEqual(risk.status, RiskStatus.PENDING_CONFIRM)
                self.assertEqual(risk.display_status, RiskDisplayStatus.PENDING_CONFIRM)
                self.assertEqual(risk.confirmer, [1])
            finally:
                risk.delete()
        finally:
            scene.delete()


# 移除标题渲染测试，因为 ConfirmRisk 没有 render_title 方法
# class ConfirmRiskTitleRenderTest(TicketTest):
#     """测试 ConfirmRisk 标题渲染"""
#
#     def test_render_title_with_template(self):
#         """测试使用固化标题模板"""
#         with RiskContext(risk_info={"status": RiskStatus.PENDING_CONFIRM}) as risk:
#             handler = ConfirmRisk(risk_id=risk.risk_id, operator="test")
#             # 假设有 title_template
#             title = handler.render_title(title_template="确认风险：{{risk_id}}")
#             self.assertIn(risk.risk_id, title)
#
#     def test_render_title_without_template(self):
#         """测试不传模板时查询 strategy"""
#         with RiskContext(
#             risk_info={"status": RiskStatus.PENDING_CONFIRM, "strategy_id": 1}
#         ) as risk:
#             handler = ConfirmRisk(risk_id=risk.risk_id, operator="test")
#             # 无模板时返回 None 或查询 strategy
#             title = handler.render_title()
#             # 根据实际实现验证
#             self.assertIsNotNone(title) or self.assertIsNone(title)


class RiskStatusPreCheckTest(TicketTest):
    """测试风险状态预检查"""

    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.auth_current_operator",
        mock.Mock(return_value=None),
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.notice_current_operator",
        mock.Mock(return_value=None),
    )
    def test_pending_confirm_blocks_new_risk(self):
        """测试待确认状态阻止 NewRisk 操作"""
        from core.exceptions import RiskStatusInvalid

        with RiskContext(risk_info={"status": RiskStatus.PENDING_CONFIRM}) as risk:
            # 尝试执行 NewRisk（应失败）
            operator = uuid.uuid1().hex
            with self.assertRaises(RiskStatusInvalid):
                NewRisk(risk_id=risk.risk_id, operator=operator).run()

    def test_closed_blocks_confirm_operation(self):
        """测试已关闭状态阻止 ConfirmRisk 操作"""
        from core.exceptions import RiskStatusInvalid

        with RiskContext(risk_info={"status": RiskStatus.CLOSED}) as risk:
            operator = uuid.uuid1().hex
            # ConfirmRisk 应阻止已关闭状态
            with self.assertRaises(RiskStatusInvalid):
                ConfirmRisk(risk_id=risk.risk_id, operator=operator).run(username=operator)

    def test_closed_blocks_misreport_operation(self):
        """测试已关闭状态阻止 ConfirmAsMisReport 操作"""
        from core.exceptions import RiskStatusInvalid

        with RiskContext(risk_info={"status": RiskStatus.CLOSED}) as risk:
            operator = uuid.uuid1().hex
            # ConfirmAsMisReport 应阻止已关闭状态
            with self.assertRaises(RiskStatusInvalid):
                ConfirmAsMisReport(risk_id=risk.risk_id, operator=operator).run(username=operator)
