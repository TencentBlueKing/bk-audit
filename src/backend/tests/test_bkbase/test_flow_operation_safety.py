"""旧 Flow 操作不能穿过新代，失败后不由后台补发。"""
from copy import deepcopy
from unittest import mock

import requests
from django.test import TransactionTestCase, override_settings

from services.web.analyze.controls.rule_audit import RuleAuditController
from services.web.bkbase import flow
from services.web.bkbase.common import get_bkbase_context
from services.web.bkbase.exceptions import BKBaseOperationSuperseded
from services.web.strategy_v2.constants import StrategyStatusChoices
from services.web.strategy_v2.models import Strategy
from tests.test_bkbase.test_flow_pure_operation import FlowFixture


@override_settings(
    BKBASE_API_VERSION="v4", BKBASE_V4_TENANT="tenant_a", BKBASE_V4_NAMESPACE="audit", BKBASE_V4_MCP_PROJECT_ID=11
)
class FlowOperationSafetyTests(FlowFixture, TransactionTestCase):
    def old_context(self):
        data = deepcopy(self.strategy.backend_data)
        data["bkbase_v4"]["operation_id"] = "old"
        self.strategy.backend_data = data
        newer = deepcopy(data)
        newer["bkbase_v4"]["operation_id"] = "new"
        Strategy.objects.filter(pk=self.strategy.pk).update(backend_data=newer)
        return {**get_bkbase_context(), "operation_id": "old"}

    def test_superseded_create_cannot_send_remote_write(self):
        context = self.old_context()
        with mock.patch.object(flow.api.bk_base_v4, "flow_create") as create:
            with self.assertRaises(BKBaseOperationSuperseded):
                flow.apply_rule_flow(context, self.strategy, {"nodes": [{"name": "source"}]})
        create.assert_not_called()
        self.assertEqual(self.writes(), [])

    def test_superseded_stop_cannot_update_remote_flow(self):
        context = self.old_context()
        with mock.patch.object(flow.api.bk_base_v4, "flow_update") as update:
            with self.assertRaises(BKBaseOperationSuperseded):
                flow.operate_rule_flow(context, self.strategy, action="stop")
        update.assert_not_called()
        self.assertEqual(self.writes(), [])

    def test_superseded_restart_cannot_send_remote_restart(self):
        context = self.old_context()
        observed = {"task_state": "running", "engine_flow_id": 1, "deployment": {"status": "success"}}
        with mock.patch.object(flow, "get_rule_flow_status", return_value=observed), mock.patch.object(
            flow.api.bk_base_v4, "flow_restart"
        ) as restart:
            with self.assertRaises(BKBaseOperationSuperseded):
                flow.operate_rule_flow(context, self.strategy, action="restart")
        restart.assert_not_called()
        self.assertEqual(self.writes(), [])

    def test_toggle_transport_error_records_failure_without_automatic_retry(self):
        self.write_error = requests.Timeout("transport timeout")
        RuleAuditController(self.strategy.pk).disabled()
        self.strategy.refresh_from_db()
        self.assertEqual(self.strategy.status, StrategyStatusChoices.STOP_FAILED)
        self.assertTrue(self.binding()["pure_operation"]["outcome_unknown"])
        self.observe()
        self.assertEqual(len(self.writes()), 1)
