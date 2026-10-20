# -*- coding: utf-8 -*-
from unittest import mock

from django.test import SimpleTestCase

from apps.itsm.constants import TicketStatus
from services.web.risk.handlers.ticket import (
    ITSM_V4_STATUS_MAPPING,
    get_itsm_ticket_status,
)


class TestGetItsmTicketStatus(SimpleTestCase):
    """验证 V4 ticket_detail 返回的状态词汇能被正确映射。

    review 关注点：V3 与 V4 共用 ITSM 后端、工单 id 互通，真实 V3 旧单形状为
    {id, sn}。用该 id 调 V4 ticket_detail 查询时，返回的 status 字段是 V4 词汇
    （小写 running/finished/...），必须能被 ITSM_V4_STATUS_MAPPING 映射到
    TicketStatus，否则当前_status 会失效、下游误判。
    """

    def test_v4_status_word_mapped_correctly(self):
        detail = {
            "id": 101,
            "sn": "NO20240101001",
            "title": "V3 迁移单",
            "status": "finished",
            "updated_at": "2024-01-01 00:00:00",
            "frontend_url": "https://itsm.example.com/ticket/101",
            "approve_result": True,
            "current_processors": [{"processor_type": "user", "processor": "admin"}],
        }
        with mock.patch(
            "services.web.risk.handlers.ticket.api.bk_itsm_v4.ticket_detail",
            mock.Mock(return_value=detail),
        ):
            status = get_itsm_ticket_status("101")

        self.assertEqual(status["id"], 101)
        self.assertEqual(status["sn"], "NO20240101001")
        self.assertEqual(status["approve_result"], True)
        self.assertEqual(status["current_status"], TicketStatus.FINISHED.value)
        # 映射结果与常量表一致
        self.assertEqual(status["current_status"], ITSM_V4_STATUS_MAPPING["finished"])

    def test_running_status_mapped_and_processor_extracted(self):
        detail = {
            "id": 102,
            "sn": "NO20240101002",
            "status": "running",
            "approve_result": False,
            "current_processors": [
                {"processor_type": "role", "processor": "xxx"},
                {"processor_type": "user", "processor": ["admin", "ops"]},
            ],
        }
        with mock.patch(
            "services.web.risk.handlers.ticket.api.bk_itsm_v4.ticket_detail",
            mock.Mock(return_value=detail),
        ):
            status = get_itsm_ticket_status("102")

        self.assertEqual(status["current_status"], TicketStatus.RUNNING.value)
        # 仅取 user 类型处理人，且多值用分号拼接
        self.assertEqual(status["updated_by"], "admin;ops")

    def test_unknown_status_falls_back_to_raw_value(self):
        detail = {"id": 103, "sn": "NO20240101003", "status": "weird_state"}
        with mock.patch(
            "services.web.risk.handlers.ticket.api.bk_itsm_v4.ticket_detail",
            mock.Mock(return_value=detail),
        ):
            status = get_itsm_ticket_status("103")

        # 未命中映射表时回退为原始 status 字符串，而不是被吞掉
        self.assertEqual(status["current_status"], "weird_state")
