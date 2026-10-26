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

from unittest import mock

from bk_resource import resource
from bk_resource.exceptions import ValidateException
from rest_framework.exceptions import ValidationError

from apps.permission.handlers.actions import ActionEnum
from services.web.risk.constants import RiskDisplayStatus, RiskStatus
from services.web.risk.models import Risk
from services.web.risk.resources.risk import CustomTransRisk
from services.web.strategy_v2.models import Strategy
from tests.base import TestCase as BaseTestCase


class TestBulkCustomTransRisk(BaseTestCase):
    """批量人工转单：逐条 {success_count, failed[]} 返回"""

    def setUp(self):
        super().setUp()
        patcher = mock.patch("services.web.risk.resources.risk.get_request_username", return_value="tester")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.strategy = Strategy.objects.create(
            strategy_id=1,
            strategy_name="测试策略",
            strategy_type="model",
            namespace=self.namespace,
            status="running",
        )
        self.risks = [
            Risk.objects.create(
                risk_id=f"test_risk_{idx}",
                strategy=self.strategy,
                status=RiskStatus.AWAIT_PROCESS,
                display_status=RiskDisplayStatus.AWAIT_PROCESS,
                scene_id=1,
                event_time="2024-01-01T00:00:00Z",
                raw_event_id=f"event_{idx}",
                current_operator=["tester"],
            )
            for idx in range(1, 4)
        ]

    @mock.patch("bk_audit.contrib.bk_audit.client.bk_audit_client.add_event")
    @mock.patch("services.web.risk.resources.risk.CustomTransRisk.perform_request")
    def test_all_success(self, mock_perform, add_event):
        mock_perform.return_value = None
        result = resource.risk.bulk_custom_trans_risk(
            risk_ids=[r.risk_id for r in self.risks],
            new_operators=[{"type": "user", "value": "user1"}, {"type": "user", "value": "user2"}],
            description="批量转单",
        )
        self.assertEqual(result["success_count"], 3)
        self.assertEqual(result["failed"], [])
        self.assertEqual(mock_perform.call_count, 3)
        for call in mock_perform.call_args_list:
            args = call[0][0]
            self.assertEqual(args["new_operators"], ["user1", "user2"])
            self.assertEqual(args["description"], "批量转单")
        self.assertEqual(add_event.call_count, 3)
        for call in add_event.call_args_list:
            self.assertEqual(call.kwargs["action"], ActionEnum.PROCESS_RISK)

    def test_backward_compat_string_operators(self):
        """旧协议：new_operators 直接是字符串列表"""
        with mock.patch("services.web.risk.resources.risk.CustomTransRisk.perform_request") as mock_perform:
            mock_perform.return_value = None
            result = resource.risk.bulk_custom_trans_risk(
                risk_ids=[self.risks[0].risk_id],
                new_operators=["alice", "bob"],
                description="批量转单",
            )
            self.assertEqual(result["success_count"], 1)
            self.assertEqual(mock_perform.call_args[0][0]["new_operators"], ["alice", "bob"])

    def test_missing_risk_reported_as_failure(self):
        with mock.patch("services.web.risk.resources.risk.CustomTransRisk.perform_request") as mock_perform:
            mock_perform.return_value = None
            result = resource.risk.bulk_custom_trans_risk(
                risk_ids=[self.risks[0].risk_id, "not-exist"],
                new_operators=["alice"],
                description="批量转单",
            )
            self.assertEqual(result["success_count"], 1)
            self.assertEqual(len(result["failed"]), 1)
            self.assertEqual(result["failed"][0]["risk_id"], "not-exist")

    def test_per_item_failure_collected(self):
        """单条抛异常不影响其他条目"""

        def side_effect(payload):
            if payload["risk_id"] == "test_risk_2":
                raise ValueError("boom")

        with mock.patch("services.web.risk.resources.risk.CustomTransRisk.perform_request", side_effect=side_effect):
            result = resource.risk.bulk_custom_trans_risk(
                risk_ids=[r.risk_id for r in self.risks],
                new_operators=["alice"],
                description="批量转单",
            )
        self.assertEqual(result["success_count"], 2)
        self.assertEqual({item["risk_id"] for item in result["failed"]}, {"test_risk_2"})

    def test_dedup_risk_ids(self):
        with mock.patch("services.web.risk.resources.risk.CustomTransRisk.perform_request") as mock_perform:
            mock_perform.return_value = None
            result = resource.risk.bulk_custom_trans_risk(
                risk_ids=[self.risks[0].risk_id, self.risks[0].risk_id, self.risks[1].risk_id],
                new_operators=["alice"],
                description="批量转单",
            )
        self.assertEqual(result["success_count"], 2)

    def test_serializer_rejects_empty(self):
        with self.assertRaises(ValidateException):
            resource.risk.bulk_custom_trans_risk(risk_ids=[], new_operators=["user1"], description="测试")
        with self.assertRaises(ValidateException):
            resource.risk.bulk_custom_trans_risk(risk_ids=[self.risks[0].risk_id], new_operators=[], description="测试")

    @mock.patch("services.web.risk.handlers.ticket.RiskFlowBaseHandler.notice_current_operator", return_value=None)
    @mock.patch("services.web.risk.handlers.ticket.RiskFlowBaseHandler.auth_current_operator", return_value=None)
    @mock.patch("bk_audit.contrib.bk_audit.client.bk_audit_client.add_event")
    def test_single_string_operators_stay_usernames(self, add_event, _auth, _notice):
        """旧协议 new_operators=["sample_user"] 经 request() 后仍写入用户名列表。"""
        risk = self.risks[0]
        CustomTransRisk().request({"risk_id": risk.risk_id, "new_operators": ["sample_user"], "description": "单条转单"})
        risk.refresh_from_db()
        self.assertEqual(risk.current_operator, ["sample_user"])
        add_event.assert_called_once()
        self.assertEqual(add_event.call_args.kwargs["action"], ActionEnum.PROCESS_RISK)
        self.assertEqual(add_event.call_args.kwargs["instance"].instance_id, risk.risk_id)

    @mock.patch("services.web.risk.handlers.ticket.RiskFlowBaseHandler.notice_current_operator", return_value=None)
    @mock.patch("services.web.risk.handlers.ticket.RiskFlowBaseHandler.auth_current_operator", return_value=None)
    def test_single_user_ref_resolves_to_username(self, _auth, _notice):
        risk = self.risks[0]
        CustomTransRisk().request(
            {
                "risk_id": risk.risk_id,
                "new_operators": [{"type": "user", "value": "sample_user"}],
                "description": "单条转单",
            }
        )
        risk.refresh_from_db()
        self.assertEqual(risk.current_operator, ["sample_user"])

    @mock.patch("services.web.risk.handlers.ticket.RiskFlowBaseHandler.notice_current_operator", return_value=None)
    @mock.patch("services.web.risk.handlers.ticket.RiskFlowBaseHandler.auth_current_operator", return_value=None)
    def test_single_field_ref_resolves_before_trans(self, _auth, _notice):
        risk = self.risks[0]
        risk.operator = ["from-field"]
        risk.save(update_fields=["operator"])
        CustomTransRisk().request(
            {
                "risk_id": risk.risk_id,
                "new_operators": [{"type": "field", "value": "operator"}],
                "description": "单条转单",
            }
        )
        risk.refresh_from_db()
        self.assertEqual(risk.current_operator, ["from-field"])

    def test_single_empty_operators_rejected(self):
        risk = self.risks[0]
        with self.assertRaises(ValidationError):
            CustomTransRisk().request(
                {
                    "risk_id": risk.risk_id,
                    "new_operators": [{"type": "field", "value": "event_data.missing"}],
                    "description": "单条转单",
                }
            )
