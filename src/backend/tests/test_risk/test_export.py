# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at https://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
import datetime
import io
from unittest import mock

import openpyxl
from bk_resource import resource

from services.web.risk.constants import RAW_EVENT_ID_REMARK, RiskExportField, RiskStatus
from services.web.risk.models import Risk
from services.web.risk.resources import ListEvent
from services.web.risk.serializers import RetrieveRiskStrategyInfoResponseSerializer
from services.web.strategy_v2.constants import RiskLevel
from services.web.strategy_v2.models import Strategy
from tests.base import TestCase


class TestRiskExport(TestCase):
    """
    测试风险导出
    """

    def setUp(self):
        super().setUp()
        self.maxDiff = None
        # 创建策略
        self.strategy_1 = Strategy.objects.create(
            strategy_id=1,
            strategy_name="Strategy A",
            risk_level=RiskLevel.HIGH,
            event_data_field_configs=[
                {"field_name": "user", "display_name": "Username", "duplicate_field": False},
                {"field_name": "action", "display_name": "Action", "duplicate_field": False},
            ],
        )
        self.strategy_2 = Strategy.objects.create(
            strategy_id=2,
            strategy_name="Strategy B",
            risk_level=RiskLevel.MIDDLE,
            event_data_field_configs=[{"field_name": "ip", "display_name": "Source IP", "duplicate_field": False}],
        )
        # 创建风险
        self.risk_1 = Risk.objects.create(
            risk_id="risk001",
            title="Risk 1 Title",
            strategy=self.strategy_1,
            status=RiskStatus.NEW,
            event_time=datetime.datetime(2023, 1, 1, 10, 0, 0),
            event_end_time=datetime.datetime(2023, 1, 1, 11, 0, 0),
            event_type=["login"],
            operator=["admin"],
            current_operator=["admin"],
            notice_users=["user_a"],
        )
        self.risk_2 = Risk.objects.create(
            risk_id="risk002",
            title="Risk 2 Title",
            strategy=self.strategy_1,
            status=RiskStatus.AWAIT_PROCESS,
            event_time=datetime.datetime(2023, 1, 2, 10, 0, 0),
            event_end_time=datetime.datetime(2023, 1, 2, 11, 0, 0),
            event_type=["delete"],
            operator=["user_b"],
            current_operator=["user_b"],
            notice_users=["user_c"],
        )
        self.risk_3 = Risk.objects.create(
            risk_id="risk003",
            title="Risk 3 Title",
            strategy=self.strategy_2,
            status=RiskStatus.CLOSED,
            event_time=datetime.datetime(2023, 1, 3, 10, 0, 0),
            event_end_time=datetime.datetime(2023, 1, 3, 11, 0, 0),
            event_type=["download"],
            operator=["user_d"],
            current_operator=[],
            notice_users=[],
        )
        # 风险4没有关联事件
        self.risk_4 = Risk.objects.create(
            risk_id="risk004",
            title="Risk 4 Title",
            strategy=self.strategy_2,
            status=RiskStatus.NEW,
            event_time=datetime.datetime(2023, 1, 4, 10, 0, 0),
            event_end_time=datetime.datetime(2023, 1, 4, 11, 0, 0),
            event_type=["upload"],
            operator=["user_e"],
            current_operator=["user_e"],
            notice_users=[],
        )

    def mock_get_event_list(self, risk_id, **kwargs):
        return [
            {
                "results": [
                    {"event_data": {"user": "alice", "action": "login_success"}},
                    {"event_data": {"user": "alice", "action": "login_fail"}},
                ]
            },
            {"results": [{"event_data": {"user": "bob", "action": "delete_file"}}]},
            {"results": [{"event_data": {"ip": "127.0.0.1"}}, {"event_data": {"ip": "192.168.1.1"}}]},
            {"results": []},
        ]

    @mock.patch("services.web.risk.models.Risk.load_authed_risks")
    @mock.patch.object(ListEvent, "bulk_request")
    def test_risk_export(self, mock_get_event_list, mock_load_authed_risks):
        # Mock
        mock_load_authed_risks.return_value = Risk.objects.all()
        mock_get_event_list.side_effect = self.mock_get_event_list

        # Call resource
        risk_ids = ["risk001", "risk002", "risk003", "risk004"]
        resp = resource.risk.risk_export(risk_ids=risk_ids)

        # Verify response
        self.assertIn("attachment; filename*", resp["Content-Disposition"])

        # Verify excel content
        workbook = openpyxl.load_workbook(io.BytesIO(b"".join(resp.streaming_content)))

        # 1. Check sheets
        sheet1_name = self.strategy_1.build_sheet_name()
        sheet2_name = self.strategy_2.build_sheet_name()
        self.assertEqual(workbook.sheetnames, [sheet1_name, sheet2_name])

        # 2. Check Sheet 1 (Strategy A)
        sheet1 = workbook[sheet1_name]
        # Check headers
        expected_headers1 = [f.display_name for f in RiskExportField.export_fields()] + ["Username", "Action"]
        actual_headers1 = [cell.value for cell in sheet1[1]]
        self.assertEqual(actual_headers1, expected_headers1)
        # Check data rows
        self.assertEqual(sheet1.max_row, 4)  # 1 header + 3 data rows
        # Create header map
        header_map1 = {cell.value: i for i, cell in enumerate(sheet1[1], 1)}
        # Row 1 (risk001, event 1)
        self.assertEqual(sheet1.cell(row=2, column=header_map1[str(RiskExportField.RISK_ID.label)]).value, "risk001")
        self.assertEqual(sheet1.cell(row=2, column=header_map1["Username"]).value, "alice")
        self.assertEqual(sheet1.cell(row=2, column=header_map1["Action"]).value, "login_success")
        # Row 2 (risk001, event 2)
        self.assertEqual(sheet1.cell(row=3, column=header_map1[str(RiskExportField.RISK_ID.label)]).value, "risk001")
        self.assertEqual(sheet1.cell(row=3, column=header_map1["Username"]).value, "alice")
        self.assertEqual(sheet1.cell(row=3, column=header_map1["Action"]).value, "login_fail")
        # Row 3 (risk002, event 1)
        self.assertEqual(sheet1.cell(row=4, column=header_map1[str(RiskExportField.RISK_ID.label)]).value, "risk002")
        self.assertEqual(sheet1.cell(row=4, column=header_map1["Username"]).value, "bob")
        self.assertEqual(sheet1.cell(row=4, column=header_map1["Action"]).value, "delete_file")

        # 3. Check Sheet 2 (Strategy B)
        sheet2 = workbook[sheet2_name]
        # Check headers
        expected_headers2 = [f.display_name for f in RiskExportField.export_fields()] + ["Source IP"]
        actual_headers2 = [cell.value for cell in sheet2[1]]
        self.assertEqual(actual_headers2, expected_headers2)
        # Check data rows
        self.assertEqual(sheet2.max_row, 4)  # 1 header + 3 data rows
        # Create header map
        header_map2 = {cell.value: i for i, cell in enumerate(sheet2[1], 1)}
        # Row 1 (risk003, event 1)
        self.assertEqual(sheet2.cell(row=2, column=header_map2[str(RiskExportField.RISK_ID.label)]).value, "risk003")
        self.assertEqual(sheet2.cell(row=2, column=header_map2["Source IP"]).value, "127.0.0.1")
        # Row 2 (risk003, event 2)
        self.assertEqual(sheet2.cell(row=3, column=header_map2[str(RiskExportField.RISK_ID.label)]).value, "risk003")
        self.assertEqual(sheet2.cell(row=3, column=header_map2["Source IP"]).value, "192.168.1.1")
        # Row 3 (risk004, no events)
        self.assertEqual(sheet2.cell(row=4, column=header_map2[str(RiskExportField.RISK_ID.label)]).value, "risk004")
        self.assertEqual(sheet2.cell(row=4, column=header_map2["Source IP"]).value, None)

    def test_retrieve_strategy_serializer_populates_raw_event_description(self):
        strategy = Strategy(
            strategy_id=3,
            strategy_name="Strategy C",
            risk_level=RiskLevel.LOW,
            event_basic_field_configs=[
                {
                    "field_name": "raw_event_id",
                    "display_name": "raw_event_id",
                    "description": "",
                    "is_priority": True,
                    "duplicate_field": False,
                }
            ],
        )

        serializer = RetrieveRiskStrategyInfoResponseSerializer(instance=strategy)
        data = serializer.data
        raw_config = next(
            cfg for cfg in data.get("event_basic_field_configs", []) if cfg.get("field_name") == "raw_event_id"
        )

        self.assertEqual(raw_config["description"], str(RAW_EVENT_ID_REMARK))
