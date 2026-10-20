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

        关键验证：将已发起的在途节点标记为 V3 后再次执行审批节点，应依 sn 走
        api.bk_itsm.ticket_approve_result 查询状态，且不重新发起（不调用 V4 ticket_create）。
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

        复现 review 场景：输入 title(特殊)、tags(特殊)、risk_level(普通配置字段)、
        raw_event_id(回退字段) 四字段，断言：
        1. fields 每个元素为独立的 {"key": 裸key, "value": 值}，无共享引用、无重复对象；
        2. 特殊字段 title 含套餐名、tags 来自 risk.get_tag_names()；
        3. 普通配置字段 risk_level 取自 approve_config（非遗漏）；
        4. 回退字段 raw_event_id 取自 risk 对象属性（非遗漏）。
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
                form_data, fields = handler._build_approve_form_data(v3_service_detail)

                # 字段数量与顺序完整（4 个，无遗漏、无重复）
                self.assertEqual([item["key"] for item in fields], ["title", "tags", "risk_level", "raw_event_id"])
                # 每个元素是独立的 {"key": 裸key, "value": 值} 字典
                self.assertEqual(fields[0], {"key": "title", "value": gettext("【审计中心】执行%s审批") % pa.name})
                self.assertEqual(fields[1], {"key": "tags", "value": ";".join(risk.get_tag_names())})
                # 普通配置字段：取自 approve_config，不再是遗漏项
                self.assertEqual(fields[2], {"key": "risk_level", "value": "critical"})
                # 回退字段：取自 risk 对象属性，不再是遗漏项
                self.assertEqual(fields[3], {"key": "raw_event_id", "value": risk.raw_event_id})
                # 所有元素为独立对象（无共享引用，避免累积成重复对象）
                self.assertEqual(len({id(item) for item in fields}), len(fields))
                # form_data 同样包含全部字段（供 V4 使用，本测试仅作一致性校验）
                self.assertEqual(set(form_data.keys()), {"title", "tags", "risk_level", "raw_event_id"})
