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
from django.utils.translation import gettext

from apps.itsm.constants import TicketStatus
from services.web.risk.constants import ItsmVersion, RiskDisplayStatus, RiskStatus
from services.web.risk.handlers import ticket as ticket_handlers
from services.web.risk.handlers.ticket import ForApprove, NewRisk
from tests.test_risk.test_tickets.base import RiskContext, RuleContext, TicketTest
from tests.test_risk.test_tickets.constants import (
    APPROVE_SERVICE_INFO,
    APPROVE_TICKET_DETAIL,
    APPROVE_TICKET_STATUS,
    CUSTOM_AUTO_PROCESS_PARAMS,
    SOPS_TEMPLATE_INFO,
    PA_INFO,
)


class ForApproveTest(TicketTest):
    @mock.patch(
        "services.web.risk.handlers.ticket.get_itsm_ticket_status",
        mock.Mock(return_value=APPROVE_TICKET_STATUS),
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_itsm_v4.workflows", mock.Mock(return_value=APPROVE_SERVICE_INFO)
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_itsm_v4.ticket_create", mock.Mock(return_value=APPROVE_TICKET_DETAIL)
    )
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
    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_sops.get_template_info",
        mock.Mock(return_value=SOPS_TEMPLATE_INFO),
    )
    def test_custom_approve(self):
        """
        测试人工发起审批
        关键验证：指定套餐、状态
        """

        with RuleContext() as (pa, _):
            with RiskContext() as risk:
                # 执行
                pa_config = {**CUSTOM_AUTO_PROCESS_PARAMS, "pa_id": pa.id}
                resource.risk.custom_auto_process(risk_id=risk.risk_id, **pa_config)
                risk.refresh_from_db()
                # 检测风险状态
                self.assertEquals(risk.status, RiskStatus.FOR_APPROVE)
                # display_status 同步为 FOR_APPROVE
                self.assertEquals(risk.display_status, RiskDisplayStatus.FOR_APPROVE)
                # 检测单据是否符合预期
                self.assertEquals(risk.last_history.extra["pa_config"], pa_config)

    @mock.patch(
        "services.web.risk.handlers.ticket.get_itsm_ticket_status",
        mock.Mock(return_value=APPROVE_TICKET_STATUS),
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_itsm_v4.workflows", mock.Mock(return_value=APPROVE_SERVICE_INFO)
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_itsm_v4.ticket_create", mock.Mock(return_value=APPROVE_TICKET_DETAIL)
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.auth_current_operator", mock.Mock(return_value=None)
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.notice_current_operator", mock.Mock(return_value=None)
    )
    def test_create_approve(self):
        """
        测试自动发起审批
        关键验证：状态、单据
        """

        with RuleContext() as (_, _):
            with RiskContext() as risk:
                # 初始化
                operator = uuid.uuid1().hex
                NewRisk(risk_id=risk.risk_id, operator=operator).run()
                risk.refresh_from_db()
                # 检测风险状态
                self.assertEquals(risk.status, RiskStatus.FOR_APPROVE)
                # display_status 同步为 FOR_APPROVE
                self.assertEquals(risk.display_status, RiskDisplayStatus.FOR_APPROVE)
                # 执行审批节点
                ForApprove(risk_id=risk.risk_id, operator=operator).run()
                risk.refresh_from_db()
                # 检测单据号一致
                self.assertEquals(risk.last_history.process_result["ticket"]["sn"], APPROVE_TICKET_DETAIL["sn"])
                # V4 ticket_create 调用约定校验：使用 workflow_key + operator + form_data（不再使用 service_id/creator/fields）
                self.assertTrue(ticket_handlers.api.bk_itsm_v4.ticket_create.called)
                _, ticket_create_kwargs = ticket_handlers.api.bk_itsm_v4.ticket_create.call_args
                self.assertIn("workflow_key", ticket_create_kwargs)
                self.assertIn("operator", ticket_create_kwargs)
                self.assertIn("form_data", ticket_create_kwargs)
                self.assertNotIn("service_id", ticket_create_kwargs)
                self.assertNotIn("creator", ticket_create_kwargs)
                self.assertNotIn("fields", ticket_create_kwargs)
                # form_data 为字段 key -> value 字典
                self.assertIsInstance(ticket_create_kwargs["form_data"], dict)
                self.assertEqual(ticket_create_kwargs["workflow_key"], PA_INFO["approve_service_id"])
                with mock.patch(
                    "services.web.risk.handlers.ticket.get_itsm_ticket_status",
                    mock.Mock(
                        return_value={
                            **APPROVE_TICKET_STATUS,
                            "current_status": TicketStatus.FINISHED.value,
                        }
                    ),
                ):
                    # 再次执行审批节点
                    ForApprove(risk_id=risk.risk_id, operator=operator).run()
                risk.refresh_from_db()
                # 检测风险状态
                self.assertEquals(risk.status, RiskStatus.AUTO_PROCESS)
                # 审批通过后 display_status 同步为 AUTO_PROCESS
                self.assertEquals(risk.display_status, RiskDisplayStatus.AUTO_PROCESS)

    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_itsm.ticket_approve_result",
        mock.Mock(return_value=[APPROVE_TICKET_STATUS]),
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.get_itsm_ticket_status",
        mock.Mock(return_value=APPROVE_TICKET_STATUS),
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_itsm_v4.workflows", mock.Mock(return_value=APPROVE_SERVICE_INFO)
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_itsm_v4.ticket_create", mock.Mock(return_value=APPROVE_TICKET_DETAIL)
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.auth_current_operator", mock.Mock(return_value=None)
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.notice_current_operator", mock.Mock(return_value=None)
    )
    def test_create_approve_v3(self):
        """
        测试存量 V3 审批节点走 V3 分支。
        """
        with RuleContext() as (_, _):
            with RiskContext() as risk:
                # 初始化：默认 V4 发起，建立含 ticket(sn) 的历史节点
                operator = uuid.uuid1().hex
                NewRisk(risk_id=risk.risk_id, operator=operator).run()
                risk.refresh_from_db()
                ForApprove(risk_id=risk.risk_id, operator=operator).run()
                risk.refresh_from_db()
                # 模拟存量迁移：将该在途节点标记为 V3
                node = risk.last_history
                node.itsm_version = ItsmVersion.V3
                node.save(update_fields=["itsm_version"])
                # 重置 V4 发起 mock，以便断言第二次未重新发起
                ticket_handlers.api.bk_itsm_v4.ticket_create.reset_mock()
                # 再次执行审批节点，应走 V3 状态查询分支
                ForApprove(risk_id=risk.risk_id, operator=operator).run()
                risk.refresh_from_db()
                # V3 分支通过 sn 查询状态
                self.assertTrue(ticket_handlers.api.bk_itsm.ticket_approve_result.called)
                # V3 分支不重新发起单据
                self.assertFalse(ticket_handlers.api.bk_itsm_v4.ticket_create.called)
                # 风险仍处于审批中
                self.assertEquals(risk.status, RiskStatus.FOR_APPROVE)
                # display_status 同步为 FOR_APPROVE
                self.assertEquals(risk.display_status, RiskDisplayStatus.FOR_APPROVE)

    @mock.patch(
        "services.web.risk.handlers.ticket.get_itsm_ticket_status",
        mock.Mock(return_value={**APPROVE_TICKET_STATUS, "current_status": TicketStatus.FAILED.value}),
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_itsm_v4.workflows", mock.Mock(return_value=APPROVE_SERVICE_INFO)
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_itsm_v4.ticket_create", mock.Mock(return_value=APPROVE_TICKET_DETAIL)
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.auth_current_operator", mock.Mock(return_value=None)
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.notice_current_operator", mock.Mock(return_value=None)
    )
    def test_approve_failed(self):
        """
        测试审批失败
        关键验证：状态
        """

        with RuleContext() as (_, _):
            with RiskContext() as risk:
                # 初始化
                operator = uuid.uuid1().hex
                NewRisk(risk_id=risk.risk_id, operator=operator).run()
                risk.refresh_from_db()
                # 检测风险状态
                self.assertEquals(risk.status, RiskStatus.FOR_APPROVE.value)
                # display_status 同步为 FOR_APPROVE
                self.assertEquals(risk.display_status, RiskDisplayStatus.FOR_APPROVE)
                # 执行审批节点
                ForApprove(risk_id=risk.risk_id, operator=operator).run()
                risk.refresh_from_db()
                # 检测风险状态
                self.assertEquals(risk.status, RiskStatus.AWAIT_PROCESS)
                # 审批失败后 display_status 使用默认映射：AWAIT_PROCESS → PROCESSING
                self.assertEquals(risk.display_status, RiskDisplayStatus.PROCESSING)
                # 检测处理人
                self.assertEquals(risk.current_operator, ForApprove.load_security_person())

    def test_build_approve_form_data_v3(self):
        """
        测试 V3 首次建单的表单构造（_build_approve_form_data）。
        """

        # V3 get_service_detail 返回的原生结构：fields 元素带 key/name/type
        v3_service_detail = {
            "fields": [
                {"key": "title", "name": "标题", "type": "STRING"},
                {"key": "tags", "name": "标签", "type": "STRING"},
                {"key": "risk_level", "name": "风险等级", "type": "STRING"},
                {"key": "raw_event_id", "name": "原始事件ID", "type": "STRING"},
            ]
        }

        with RuleContext(pa_info={"approve_config": {"risk_level": {"value": "critical"}}}) as (pa, rule):
            with RiskContext() as risk:
                handler = ForApprove(risk_id=risk.risk_id, operator="admin")
                # 直接驱动被测试方法，隔离验证 V3 表单构造（不触发真实建单）
                handler.process_application = pa
                form_data = handler._build_approve_form_data(v3_service_detail)

                # 字段数量与顺序完整（4 个，无遗漏、无重复）
                self.assertEqual(list(form_data.keys()), ["title", "tags", "risk_level", "raw_event_id"])
                # 特殊字段：title 含套餐名
                self.assertEqual(form_data["title"], gettext("【审计中心】执行%s审批") % pa.name)
                # 标签来自 risk.get_tag_names()
                self.assertEqual(form_data["tags"], ";".join(risk.get_tag_names()))
                # 普通配置字段：取自 approve_config
                self.assertEqual(form_data["risk_level"], "critical")
                # 回退字段：取自 risk 对象属性
                self.assertEqual(form_data["raw_event_id"], risk.raw_event_id)

    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_itsm.get_service_detail",
        # V3 接口内部对 service_id 做 int() 转换，对 V4 workflow_key 字符串会抛 ValueError。
        # 若该接口被命中，说明新建分支错误沿用了 V3 版本，用例应失败。
        mock.Mock(side_effect=ValueError("V3 get_service_detail 不应被命中")),
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.get_itsm_ticket_status",
        mock.Mock(return_value=APPROVE_TICKET_STATUS),
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_itsm_v4.workflows", mock.Mock(return_value=APPROVE_SERVICE_INFO)
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.api.bk_itsm_v4.ticket_create", mock.Mock(return_value=APPROVE_TICKET_DETAIL)
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.auth_current_operator", mock.Mock(return_value=None)
    )
    @mock.patch(
        "services.web.risk.handlers.ticket.RiskFlowBaseHandler.notice_current_operator", mock.Mock(return_value=None)
    )
    def test_create_approve_fallback_v4_without_ticket(self):
        """
        升级前 FOR_APPROVE、无既有单据、套餐已替换为 V4。
        """
        with RuleContext(pa_info={"approve_service_id": "audit_v4_approval"}) as (_, _):
            with RiskContext() as risk:
                operator = uuid.uuid1().hex
                # 初始化：NewRisk 落库（默认 last_history 为 NewRisk 节点，itsm_version=V4），无 ticket
                NewRisk(risk_id=risk.risk_id, operator=operator).run()
                risk.refresh_from_db()
                # 模拟迁移 0066：将上一（NewRisk）节点标为 V3，且无 ticket/sn（符合 review 边界）
                node = risk.last_history
                self.assertFalse(node.process_result.get("ticket"))
                node.itsm_version = ItsmVersion.V3
                node.save(update_fields=["itsm_version"])
                # 后台自动续跑：不传 pa_config，走「未发起则发起」分支
                ForApprove(risk_id=risk.risk_id, operator=operator).run()
                risk.refresh_from_db()
                # 新建分支按 V4 创建
                self.assertTrue(ticket_handlers.api.bk_itsm_v4.ticket_create.called)
                # V3 get_service_detail 接口（int(workflow_key) 会抛 ValueError）未被命中
                self.assertFalse(ticket_handlers.api.bk_itsm.get_service_detail.called)
                # 新写入的 ForApprove 节点版本为 V4（record_history 默认 inherits V4）。
                # 此处用直接查询取真正的最新节点：risk.last_history 是 cached_property，
                # 上方对该实例访问过会缓存旧节点，refresh_from_db 不会清除该缓存。
                from services.web.risk.models import TicketNode

                last_node = TicketNode.objects.filter(risk_id=risk.risk_id).order_by("-timestamp").first()
                self.assertEquals(last_node.action, ForApprove.__name__)
                self.assertEquals(last_node.itsm_version, ItsmVersion.V4)
                # 风险仍处于审批中
                self.assertEquals(risk.status, RiskStatus.FOR_APPROVE)
