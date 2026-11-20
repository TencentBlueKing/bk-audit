"""验证正式 Flow 配置失败、等待和错误详情的业务投影。"""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, override_settings

from services.web.bkbase import flow


@override_settings(BKBASE_API_VERSION="v4")
class FlowFailureMessageTests(SimpleTestCase):
    def setUp(self):
        self.context = {"tenant": "tenant_a", "namespace": "audit"}
        ref = {"kind": "Flow", "tenant": "tenant_a", "namespace": "audit", "name": "flow_a"}
        self.strategy = SimpleNamespace(
            backend_data={"bkbase_v4": {"flow": ref, "operation_id": "op_a", "requested_action": "start"}}
        )
        self.cr = {"metadata": ref, "spec": {}, "status": {"phase": "Failed", "message": ""}}
        self.enterContext(mock.patch("services.web.bkbase.flow.get_bkbase_context", return_value=self.context))
        self.enterContext(mock.patch("services.web.bkbase.flow._save_operation_binding"))
        self.enterContext(mock.patch("services.web.bkbase.flow.api.bk_base_v4.flow_get", return_value=self.cr))

    def test_configuration_failure_without_message_has_generic_message(self):
        result = flow.strategy_deploy_data(self.strategy)
        self.assertEqual(result["status"], "failure")
        self.assertEqual(result["logs"], [{"level": "ERROR", "message": "Flow configuration failed to apply."}])

    def test_pending_configuration_does_not_report_failure(self):
        self.cr["status"] = {"phase": "Pending"}
        result = flow.strategy_deploy_data(self.strategy)
        self.assertEqual(result["status"], "other")
        self.assertEqual(result["logs"], [])

    def test_stopped_configuration_is_not_start_completion(self):
        self.cr["status"] = {"phase": "Ok"}
        self.cr["metadata"] = {**self.cr["metadata"], "annotations": {"task_stopped": "true"}}
        result = flow.strategy_deploy_data(self.strategy)
        self.assertEqual(result["status"], "other")
        self.assertEqual(result["flow_status"], "stopped")

    def test_failure_preserves_existing_resource_message(self):
        self.cr["status"]["message"] = "existing diagnostic"
        result = flow.strategy_deploy_data(self.strategy)
        self.assertEqual(result["status"], "failure")
        self.assertEqual(result["logs"], [{"level": "ERROR", "message": "existing diagnostic"}])
